"""Let an already-started full election collection finish before publishing."""

import json
import time
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen


SOURCE_ACTIONS = "https://api.github.com/repos/hanshanley/voter-participation/actions"
LATEST = "/workflows/election-night.yml/runs?branch=main&per_page=20"
ACTIVE = {"queued", "in_progress", "requested", "waiting", "pending"}


def is_full_collection(run):
    return (run["event"] == "schedule" and run.get("display_title") != "Check late participation archives") or (
        run["event"] == "workflow_dispatch"
        and run["display_title"] == "Collect full election results"
    )


def request(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "participation-runtime"}
    with urlopen(Request(SOURCE_ACTIONS + path, headers=headers), timeout=15) as response:
        return json.load(response)


def wait_for_collection(fetch=request, *, monotonic=time.monotonic, sleep=time.sleep,
                        now=None, wait_seconds=2400):
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
