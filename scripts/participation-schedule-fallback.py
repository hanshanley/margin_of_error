"""Recover a missed election update from an independent Unix scheduler."""

import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


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
ACTIVE = {"queued", "in_progress", "requested", "waiting", "pending"}


def clock(value):
    observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if observed.utcoffset() is None:
        raise ValueError("Naive clock in update evidence")
    return observed


def api(gh, path, *, raw=False, dispatch=False):
    args = [gh, "api", "--hostname", "github.com", path]
    if raw:
        args += ["-H", "Accept: application/vnd.github.raw+json"]
    if dispatch:
        args += ["--method", "POST", "-H", "X-GitHub-Api-Version: 2026-03-10", "-f", "ref=main"]
    result = subprocess.run(args, text=True, capture_output=True, timeout=30, check=True,
                            env={**os.environ, "GH_PROMPT_DISABLED": "1", "GH_PAGER": "cat"})
    return json.loads(result.stdout) if result.stdout else None


def workflow_path(stage):
    repo, workflow = WORKFLOWS[stage]
    return f"repos/{repo}/actions/workflows/{workflow}"


def history(request, stage):
    runs = request(workflow_path(stage) + "/runs?branch=main&per_page=20")["workflow_runs"]
    for run in runs:
        if (run["head_branch"] != "main" or type(run["id"]) is not int
                or run["status"] not in ACTIVE | {"completed"}):
            raise ValueError(f"Unrecognized {stage} run")
    return sorted(runs, key=lambda run: (clock(run["created_at"]), run["id"]), reverse=True)


def pointer(request, repo, tag, file, contract):
    ref = request(f"repos/{repo}/git/ref/tags/{tag}")["object"]
    if ref["type"] != "commit" or not re.fullmatch(r"[a-f0-9]{40}", ref["sha"]):
        raise ValueError(f"Invalid {tag} ref")
    body = request(f"repos/{repo}/contents/{file}?ref={ref['sha']}", raw=True)
    if body["contract"] != contract:
        raise ValueError(f"Unexpected {tag} pointer contract")
    return body


def tick(now, request, journal, record, *, apply=False):
    if not WINDOW[0] <= now < WINDOW[1]:
        return {"decision": "outside_election_window"}
    runs = {stage: history(request, stage) for stage in WORKFLOWS}
    source = pointer(request, SOURCE, "results-data", "latest.json",
                     "participation.automatic_results_latest.v1")
    live = pointer(request, SITE, "participation-data", "automatic/latest.json",
                   "participation.automatic_runtime.v1")
    accepted, consumed = source["version"], live["input_results_version"]
    if not all(re.fullmatch(r"[a-f0-9]{64}", version)
               for version in (accepted, consumed, live["version"])):
        raise ValueError("Invalid source or runtime version")
    changed = accepted != consumed
    if changed and clock(source["checked_at"]) <= clock(live["checked_at"]):
        raise ValueError("Refusing to dispatch a publisher against older or ambiguous source data")

    def active(stage):
        return any(run["status"] in ACTIVE for run in runs[stage])

    def ready(stage):
        return not active(stage) and (stage not in journal or now - clock(journal[stage]) >= RETRY)

    def missed(stage):
        return not runs[stage] or now - clock(runs[stage][0]["created_at"]) >= MISSED

    def cooled(stage):
        return not runs[stage] or now - clock(runs[stage][0]["updated_at"]) >= RETRY

    stage = None
    if changed and ready("publication") and not active("collection") and cooled("publication"):
        stage = "publication"
    elif ready("collection") and not active("publication") and cooled("collection") and (
        missed("collection")
        or (runs["collection"] and runs["collection"][0]["conclusion"] != "success")
    ):
        stage = "collection"
    elif ready("health") and missed("health"):
        stage = "health"
    report = {"decision": "no_dispatch", "latest_source": accepted, "live_source": consumed,
              "active_workflows": [key for key in runs if active(key)]}
    if stage and apply:
        # A lost response can mean GitHub accepted the dispatch; never immediately retry it.
        journal[stage] = now.isoformat()
        record(journal)
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
    parser.add_argument("--apply", action="store_true", help="Allow the three preconfigured dispatches")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    request = lambda path, **kwargs: api(args.gh, path, **kwargs)
    if not (args.apply and WINDOW[0] <= now < WINDOW[1]):
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
            if not isinstance(journal, dict) or set(journal) - WORKFLOWS.keys():
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
