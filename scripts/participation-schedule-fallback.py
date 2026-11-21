"""Recover a missed election update from an independent Unix scheduler."""

import argparse
import base64
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlencode


SOURCE = "hanshanley/voter-participation"
SITE = "hanshanley/margin_of_error"
WORKFLOWS = {
    "collection": (SOURCE, "election-night.yml"),
    "publication": (SITE, "automatic-runtime.yml"),
    "health": (SITE, "participation-health.yml"),
}
WINDOW = (datetime(2026, 11, 3, tzinfo=timezone.utc),
          datetime(2027, 2, 1, tzinfo=timezone.utc))
MISSED = timedelta(minutes=90)
RETRY = timedelta(minutes=30)
PUBLICATION_SETTLE = timedelta(minutes=5)
ARCHIVE_RETRY = timedelta(hours=6)
ARCHIVE_TITLE = "Check late participation archives"
FULL_COLLECTION_TITLE = "Collect full election results"
ACTIVE = {"queued", "in_progress", "requested", "waiting", "pending"}
MAX_WORKFLOW_BYTES = 64 * 1024
COLLECTOR_ONLY_PATHS = {
    ".github/workflows/election-night.yml",
    "scripts/results_intake.py",
    "docs/RESULTS_INTAKE.md",
    "tests/test_election_night_workflow.py",
    "tests/test_results_intake.py",
}


def clock(value):
    observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if observed.utcoffset() is None:
        raise ValueError("Naive clock in update evidence")
    return observed


def api(gh, path, *, raw=False, dispatch=False, archive_only=False):
    args = [gh, "api", "--hostname", "github.com", path]
    if raw:
        args += ["-H", "Accept: application/vnd.github.raw+json"]
    if dispatch:
        args += ["--method", "POST", "-H", "X-GitHub-Api-Version: 2026-03-10", "-f", "ref=main"]
        if archive_only:
            args += ["-F", "inputs[archive_only]=true"]
    result = subprocess.run(args, text=True, capture_output=True, timeout=30, check=True,
                            env={**os.environ, "GH_PROMPT_DISABLED": "1", "GH_PAGER": "cat"})
    return json.loads(result.stdout) if result.stdout else None


def workflow_path(stage):
    repo, workflow = WORKFLOWS[stage]
    return f"repos/{repo}/actions/workflows/{workflow}"


def history(request, stage):
    runs = request(workflow_path(stage) + "/runs?branch=main&per_page=20")["workflow_runs"]
    return ordered_runs(runs, stage)


def ordered_runs(runs, stage):
    for run in runs:
        if (run["head_branch"] != "main" or type(run["id"]) is not int
                or run["status"] not in ACTIVE | {"completed"}):
            raise ValueError(f"Unrecognized {stage} run")
    return sorted(runs, key=lambda run: (clock(run["created_at"]), run["id"]), reverse=True)


def archive_due(now, request):
    utc = now.astimezone(timezone.utc)
    slot = (utc - timedelta(days=utc.weekday())).replace(hour=10, minute=19, second=0, microsecond=0)
    if now < slot + MISSED:
        return False
    seen = set()
    # Hourly skipped jobs share this workflow and can hide Monday's run after a day.
    for page in range(1, 4):
        query = urlencode({"branch": "main", "created": f">={slot.isoformat()}",
                           "per_page": 100, "page": page})
        response = request(workflow_path("collection") + "/runs?" + query)
        runs = ordered_runs(response["workflow_runs"], "archive")
        for run in runs:
            if run["id"] in seen or not slot <= clock(run["created_at"]) <= now:
                return False
            seen.add(run["id"])
            if run.get("display_title") == ARCHIVE_TITLE and run.get("event") in {"schedule", "workflow_dispatch"}:
                if (run["status"] in ACTIVE or run.get("conclusion") == "success"
                        or now - clock(run["updated_at"]) < ARCHIVE_RETRY):
                    return False
        if len(seen) == response["total_count"]:
            return True
        if len(runs) < 100:
            return False
    return False


def pointer(request, repo, tag, file, contract):
    ref = request(f"repos/{repo}/git/ref/tags/{tag}")["object"]
    if ref["type"] != "commit" or not re.fullmatch(r"[a-f0-9]{40}", ref["sha"]):
        raise ValueError(f"Invalid {tag} ref")
    body = request(f"repos/{repo}/contents/{file}?ref={ref['sha']}", raw=True)
    if body["contract"] != contract:
        raise ValueError(f"Unexpected {tag} pointer contract")
    return body


def same_clock_successor(request, source, live):
    staged = source.get("results_commit", "")
    if not re.fullmatch(r"[a-f0-9]{40}", staged):
        return False
    commit = request(f"repos/{SOURCE}/git/commits/{staged}")
    parents = commit["parents"]
    if commit["sha"] != staged or len(parents) != 1:
        return False
    parent = parents[0]["sha"]
    if not re.fullmatch(r"[a-f0-9]{40}", parent):
        return False
    previous = request(f"repos/{SOURCE}/contents/latest.json?ref={parent}", raw=True)
    if (previous.get("contract") != "participation.automatic_results_latest.v1"
            or previous.get("version") != live["input_results_version"]
            or clock(previous["checked_at"]) != clock(source["checked_at"])):
        return False
    body = (json.dumps(previous, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()
    return live.get("input_results_pointer") == {
        "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
    }


def workflow_source(request, stage, ref):
    repo, workflow = WORKFLOWS[stage]
    path = f".github/workflows/{workflow}"
    file = request(f"repos/{repo}/contents/{path}?ref={ref}")
    size = file["size"]
    if (file["path"] != path or file["encoding"] != "base64"
            or type(size) is not int or not 0 < size <= MAX_WORKFLOW_BYTES):
        raise ValueError("Unexpected workflow contents")
    encoded = "".join(file["content"].split())
    if len(encoded) != 4 * ((size + 2) // 3):
        raise ValueError("Incomplete workflow contents")
    body = base64.b64decode(encoded, validate=True)
    if len(body) != size:
        raise ValueError("Incomplete workflow contents")
    return body.decode("utf-8")


def producer_pin(request, ref):
    pattern = (rf"(?m)^[ \t]+repository: {re.escape(SOURCE)}[ \t]*\r?\n"
               r"[ \t]+ref: ([a-f0-9]{40})[ \t]*\r?\n[ \t]+path: research-source[ \t]*\r?$")
    matches = re.findall(pattern, workflow_source(request, "publication", ref))
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous reviewed producer pin")
    return matches[0]


def new_producer_pin(request, publications):
    last_good = next((run for run in publications if run["status"] == "completed"
                      and run["conclusion"] == "success"), None)
    if not last_good or not re.fullmatch(r"[a-f0-9]{40}", last_good.get("head_sha", "")):
        return False
    try:
        main = request(f"repos/{SITE}/git/ref/heads/main")["object"]
        if main["type"] != "commit" or not re.fullmatch(r"[a-f0-9]{40}", main["sha"]):
            raise ValueError("Invalid publisher branch ref")
        previous = last_good["head_sha"]
        return main["sha"] != previous and producer_pin(request, main["sha"]) != producer_pin(request, previous)
    except (KeyError, TypeError, ValueError, subprocess.SubprocessError):
        # An unreadable workflow is not evidence that the publisher changed.
        return False


def without_validation_selectors(body):
    header = re.compile(r"(?m)^        id: validation_tests\n"
                        r"        if: [^\n]+\n"
                        r"        run: >\n")
    matches = list(header.finditer(body))
    if len(matches) != 1:
        return body
    start = matches[0].end()
    test = r"tests/test_[A-Za-z0-9_]+\.py"
    command = re.match(rf"          python -m pytest -q(?: {test})+(?:\n          "
                       rf"{test}(?: {test})*)*\n(?![ \t]*\S)", body[start:])
    if command is None:
        return body
    return body[:start] + "          python -m pytest -q\n" + body[start + command.end():]


def collector_change(request, files, base, tip):
    names = {name for file in files for name in (file["filename"], file.get("previous_filename", ""))}
    if any(re.fullmatch(r"scripts/results_[^/]+\.py|data/results-intake/registry\.json", name)
           for name in names):
        return True
    path = f".github/workflows/{WORKFLOWS['collection'][1]}"
    if path not in names:
        return False
    try:
        before, after = (workflow_source(request, "collection", ref) for ref in (base, tip))
        return without_validation_selectors(before) != without_validation_selectors(after)
    except (KeyError, TypeError, ValueError, subprocess.SubprocessError):
        # If we cannot prove selector-only changes, keep the ordinary collection behavior.
        return True


def forward_comparison(request, base, tip):
    diff = request(f"repos/{SOURCE}/compare/{base}...{tip}?per_page=1")
    files = diff["files"]
    # GitHub caps the complete file list at 300, even on a paginated commit response.
    if (diff["status"] != "ahead" or diff["merge_base_commit"]["sha"] != base
            or not isinstance(files, list) or not 0 < len(files) < 300):
        return []
    return files


def new_reviewed_collection(request, collections):
    previous = next((run for run in collections if run["status"] == "completed"
                     and run["conclusion"] == "success"
                     and run.get("display_title") == FULL_COLLECTION_TITLE), None)
    if not previous or not re.fullmatch(r"[a-f0-9]{40}", previous.get("head_sha", "")):
        return False
    try:
        main = request(f"repos/{SOURCE}/git/ref/heads/main")["object"]
        if main["type"] != "commit" or not re.fullmatch(r"[a-f0-9]{40}", main["sha"]):
            return False
        sha, base = main["sha"], previous["head_sha"]
        if sha == base:
            return False
        pin = producer_pin(request, "main")
        files = forward_comparison(request, base, sha)
        if not files or not collector_change(request, files, base, sha):
            return False
        if pin == sha:
            return True
        since_pin = files if pin == base else forward_comparison(request, pin, sha)
        return bool(since_pin) and all(
            file["status"] == "modified" and "previous_filename" not in file
            and file["filename"] in COLLECTOR_ONLY_PATHS for file in since_pin)
    except (KeyError, TypeError, ValueError, subprocess.SubprocessError):
        return False


def tick(now, request, journal, record, *, apply=False):
    if now < WINDOW[0]:
        return {"decision": "outside_election_window"}
    hourly = now < WINDOW[1]
    runs = {stage: history(request, stage) for stage in WORKFLOWS if hourly or stage != "health"}
    full_collections = [run for run in runs["collection"] if run.get("display_title") == FULL_COLLECTION_TITLE]
    source = pointer(request, SOURCE, "results-data", "latest.json",
                     "participation.automatic_results_latest.v1")
    live = pointer(request, SITE, "participation-data", "automatic/latest.json",
                   "participation.automatic_runtime.v1")
    accepted, consumed = source["version"], live["input_results_version"]
    if not all(re.fullmatch(r"[a-f0-9]{64}", version)
               for version in (accepted, consumed, live["version"])):
        raise ValueError("Invalid source or runtime version")
    changed = accepted != consumed
    if changed:
        source_time, live_time = clock(source["checked_at"]), clock(live["checked_at"])
        if source_time < live_time or (source_time == live_time and not same_clock_successor(request, source, live)):
            raise ValueError("Refusing to dispatch a publisher against older or ambiguous source data")

    def active(stage):
        return any(run["status"] in ACTIVE for run in runs[stage])

    def ready(stage):
        return not active(stage) and (stage not in journal or now - clock(journal[stage]) >= RETRY)

    def missed(entries):
        return not entries or now - clock(entries[0]["created_at"]) >= MISSED

    def cooled(entries):
        return not entries or now - clock(entries[0]["updated_at"]) >= RETRY

    stage, publish_reason, collect_reason = None, None, None
    # A known collector cannot invalidate an accepted checkpoint already awaiting publication.
    blocking_collection = any(
        run["status"] in ACTIVE and (not changed or run.get("display_title") not in
                                    {FULL_COLLECTION_TITLE, "Run scoped election results update", ARCHIVE_TITLE})
        for run in runs["collection"])
    can_publish = ready("publication") and not blocking_collection and cooled(runs["publication"])
    # A successful run may have pinned the previous checkpoint before its successor activated.
    latest_publish = next(iter(runs["publication"]), None)
    if (changed and latest_publish and latest_publish["status"] == "completed"
            and latest_publish["conclusion"] == "success"
            and now - clock(latest_publish["updated_at"]) >= PUBLICATION_SETTLE
            and ("publication" not in journal
                 or clock(latest_publish["created_at"]) >= clock(journal["publication"]))):
        can_publish = not active("publication") and not blocking_collection
    can_collect = ready("collection") and not active("publication") and cooled(full_collections)
    if changed and can_publish:
        stage, publish_reason = "publication", "unconsumed_source"
    elif not changed and hourly and can_collect:
        if missed(full_collections):
            collect_reason = "missed_schedule"
        elif full_collections[0]["conclusion"] != "success":
            collect_reason = "collection_failed"
        elif new_reviewed_collection(request, full_collections):
            collect_reason = "reviewed_collector_changed"
        if collect_reason:
            stage = "collection"
    if stage is None and not changed and can_publish and new_producer_pin(request, runs["publication"]):
        stage, publish_reason = "publication", "reviewed_producer_changed"
    if (stage is None and not hourly and not changed and can_collect
            and ("archive" not in journal or now - clock(journal["archive"]) >= ARCHIVE_RETRY)
            and archive_due(now, request)):
        stage, collect_reason = "archive", "missed_weekly_archive"
    if stage is None and hourly and ready("health") and missed(runs["health"]):
        stage = "health"
    report = {"decision": "no_dispatch", "latest_source": accepted, "live_source": consumed,
              "active_workflows": [key for key in runs if active(key)]}
    if publish_reason:
        report["publication_reason"] = publish_reason
    if collect_reason:
        report["collection_reason"] = collect_reason
    if stage and apply:
        # A lost response can mean GitHub accepted the dispatch; never immediately retry it.
        journal[stage] = now.isoformat()
        record(journal)
        if stage == "archive":
            receipt = request(workflow_path("collection") + "/dispatches", dispatch=True, archive_only=True)
        else:
            receipt = request(workflow_path(stage) + "/dispatches", dispatch=True)
        if receipt is not None:
            run_id = receipt["workflow_run_id"]
            if type(run_id) is not int or run_id < 1:
                raise ValueError("Invalid dispatch run receipt")
            report["run_id"] = run_id
        report["decision"] = f"dispatched_{stage}"
    elif stage:
        report["decision"] = f"would_dispatch_{stage}"
    return report


def save(path, journal):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as out:
        try:
            json.dump(journal, out, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
            os.replace(out.name, path)
        finally:
            Path(out.name).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gh", default="gh")
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Allow the preconfigured dispatches")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    request = lambda path, **kwargs: api(args.gh, path, **kwargs)
    if not (args.apply and WINDOW[0] <= now):
        print(json.dumps(tick(now, request, {}, None), sort_keys=True))
        return
    os.umask(0o077)
    args.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with (args.state_dir / "lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            if request("user")["login"] != "hanshanley":
                raise ValueError("Unexpected GitHub account; no dispatch was made")
            path = args.state_dir / "dispatches.json"
            journal = json.loads(path.read_text()) if path.exists() else {}
            if not isinstance(journal, dict) or set(journal) - (WORKFLOWS.keys() | {"archive"}):
                raise ValueError("Invalid fallback journal")
            if any(clock(value) > now for value in journal.values()):
                raise ValueError("Fallback journal clock is in the future")
            report = tick(now, request, journal, lambda data: save(path, data), apply=True)
            if report["decision"] != "no_dispatch":
                print(json.dumps({"checked_at": now.isoformat(), **report}, sort_keys=True))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        parser.exit(1, "GitHub fallback request failed; no immediate retry\n")


if __name__ == "__main__":
    main()
