"""Wait for a recent collector if no accepted checkpoint is ready."""

import argparse
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen


SOURCE_ACTIONS = "https://api.github.com/repos/hanshanley/voter-participation/actions"
SOURCE = "hanshanley/voter-participation"
SITE = "hanshanley/margin_of_error"
LATEST = "/workflows/election-night.yml/runs?branch=main&per_page=20"
ACTIVE = {"queued", "in_progress", "requested", "waiting", "pending"}
ARCHIVE_TITLE = "Check late participation archives"
COLLECTION_TITLES = {ARCHIVE_TITLE, "Collect full election results", "Run scoped election results update"}
START = datetime(2026, 11, 3, tzinfo=timezone.utc)
CUTOFF = datetime(2027, 2, 1, tzinfo=timezone.utc)


def is_collection(run, *, late):
    title = run.get("display_title")
    if run["event"] not in {"schedule", "workflow_dispatch"}:
        return False
    if title is None and run["event"] == "workflow_dispatch":
        raise ValueError("Missing collection title")
    if late:
        return title == ARCHIVE_TITLE
    return title in COLLECTION_TITLES or title is None


def fetch_json(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "participation-runtime"}
    with urlopen(Request(url, headers=headers), timeout=15) as response:
        return json.load(response)


def request(path):
    return fetch_json(SOURCE_ACTIONS + path)


def unconsumed_checkpoint(fetch=fetch_json, *, now=None):
    def pointer(repo, tag, file, contract):
        ref = fetch(f"https://api.github.com/repos/{repo}/git/ref/tags/{tag}")["object"]
        if ref["type"] != "commit" or not re.fullmatch(r"[a-f0-9]{40}", ref["sha"]):
            raise ValueError("Invalid checkpoint ref")
        value = fetch(f"https://raw.githubusercontent.com/{repo}/{ref['sha']}/{file}")
        if value["contract"] != contract:
            raise ValueError("Invalid checkpoint contract")
        return value

    try:
        source = pointer(SOURCE, "results-data", "latest.json", "participation.automatic_results_latest.v1")
        live = pointer(SITE, "participation-data", "automatic/latest.json", "participation.automatic_runtime.v1")
        accepted, consumed = source["version"], live["input_results_version"]
        if not all(re.fullmatch(r"[a-f0-9]{64}", version)
                   for version in (accepted, consumed, live["version"])):
            return None
        clocks = [datetime.fromisoformat(item["checked_at"].replace("Z", "+00:00"))
                  for item in (source, live)]
        if all(clock.utcoffset() is not None for clock in clocks) and clocks[0] > clocks[1] and accepted != consumed:
            if now is not None and not (START <= clocks[1] < clocks[0] <= now):
                return None
            return accepted
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def wait_for_collection(fetch=request, *, monotonic=time.monotonic, sleep=time.sleep,
                        pending=unconsumed_checkpoint, now=None, wait_seconds=2400):
    now = now or datetime.now(timezone.utc)
    if now < START:
        return {"status": "outside_collection_window"}
    deadline = monotonic() + wait_seconds
    try:
        runs = fetch(LATEST)["workflow_runs"]
        active = [item for item in runs if item["status"] != "completed" and is_collection(item, late=now >= CUTOFF)]
        if not active:
            return {"status": "no_collection_in_progress"}
        recent = []
        for item in active:
            created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
            if (type(item["id"]) is not int or item["id"] <= 0 or item["status"] not in ACTIVE
                    or item["head_branch"] != "main" or created.utcoffset() is None):
                raise ValueError("Unexpected collection evidence")
            if timedelta(0) <= now - created <= timedelta(minutes=75):
                recent.append(item)
        if not recent:
            return {"status": "no_recent_collection_in_progress"}
        run = next((item for item in recent if item["status"] == "in_progress"), recent[0])
        run_id = run["id"]

        if (version := pending()) is not None:
            return {"status": "accepted_checkpoint_ready", "input_results_version": version}
        # A checkpoint check uses two GitHub API requests in addition to the job poll.
        next_checkpoint_check = monotonic() + 450

        while (remaining := deadline - monotonic()) > 0:
            sleep(min(90, remaining))
            if monotonic() >= deadline:
                break
            observed = fetch(f"/runs/{run_id}")
            if (observed["id"] != run_id or observed["head_branch"] != "main"
                    or observed["event"] != run["event"]
                    or observed.get("display_title") != run.get("display_title")):
                raise ValueError("Collection run identity changed")
            if observed["status"] == "completed":
                return {"status": "collection_completed", "run_id": run_id,
                        "conclusion": observed["conclusion"]}
            if observed["status"] not in ACTIVE:
                raise ValueError("Unknown collection run status")
            if monotonic() >= next_checkpoint_check:
                if (version := pending()) is not None:
                    return {"status": "accepted_checkpoint_ready", "input_results_version": version}
                next_checkpoint_check = monotonic() + 450
        return {"status": "wait_limit_reached", "run_id": run_id}
    except (OSError, ValueError, KeyError, TypeError):
        # This is an ordering hint, never a substitute for validating the accepted pointer.
        return {"status": "collection_status_unavailable"}


def backup_publication(now, fetch=fetch_json):
    if now < START:
        return {"status": "outside_collection_window", "publish": False}
    version = unconsumed_checkpoint(fetch, now=now)
    if version is None:
        return {"status": "no_verified_newer_checkpoint", "publish": False}
    return {"status": "accepted_checkpoint_ready", "input_results_version": version, "publish": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", action="store_true")
    args = parser.parse_args()
    result = backup_publication(datetime.now(timezone.utc)) if args.backup else wait_for_collection()
    print(json.dumps(result))
