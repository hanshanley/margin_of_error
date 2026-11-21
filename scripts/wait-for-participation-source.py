"""Let an already-started full election collection finish before publishing."""

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


def is_full_collection(run):
    return (run["event"] == "schedule" and run.get("display_title") != "Check late participation archives") or (
        run["event"] == "workflow_dispatch"
        and run["display_title"] == "Collect full election results"
    )


def fetch_json(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "participation-runtime"}
    with urlopen(Request(url, headers=headers), timeout=15) as response:
        return json.load(response)


def request(path):
    return fetch_json(SOURCE_ACTIONS + path)


def unconsumed_checkpoint(fetch=fetch_json):
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
            return accepted
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def wait_for_collection(fetch=request, *, monotonic=time.monotonic, sleep=time.sleep,
                        pending=unconsumed_checkpoint, now=None, wait_seconds=2400):
    now = now or datetime.now(timezone.utc)
    if not datetime(2026, 11, 3, tzinfo=timezone.utc) <= now < datetime(2027, 2, 1, tzinfo=timezone.utc):
        return {"status": "outside_collection_window"}
    deadline = monotonic() + wait_seconds
    try:
        runs = fetch(LATEST)["workflow_runs"]
        run = next((item for item in runs if is_full_collection(item)), None)
        if run is None or run["status"] == "completed":
            return {"status": "no_collection_in_progress"}
        run_id = run["id"]
        created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
        if (type(run_id) is not int or run_id <= 0 or run["status"] not in ACTIVE
                or run["head_branch"] != "main"
                or created.utcoffset() is None):
            raise ValueError("Unexpected full collection evidence")
        if not timedelta(0) <= now - created <= timedelta(minutes=75):
            return {"status": "no_recent_collection_in_progress"}

        if (version := pending()) is not None:
            return {"status": "accepted_checkpoint_ready", "input_results_version": version}

        while (remaining := deadline - monotonic()) > 0:
            sleep(min(90, remaining))
            if monotonic() >= deadline:
                break
            observed = fetch(f"/runs/{run_id}")
            if (observed["id"] != run_id or observed["head_branch"] != "main"
                    or observed["event"] != run["event"] or not is_full_collection(observed)):
                raise ValueError("Collection run identity changed")
            if observed["status"] == "completed":
                return {"status": "collection_completed", "run_id": run_id,
                        "conclusion": observed["conclusion"]}
            if observed["status"] not in ACTIVE:
                raise ValueError("Unknown collection run status")
        return {"status": "wait_limit_reached", "run_id": run_id}
    except (OSError, ValueError, KeyError, TypeError):
        # This is an ordering hint, never a substitute for validating the accepted pointer.
        return {"status": "collection_status_unavailable"}


if __name__ == "__main__":
    print(json.dumps(wait_for_collection()))
