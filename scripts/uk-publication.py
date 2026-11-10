"""Verify that a successful Pages deployment actually serves this UK publication."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


FILES = (
    "data/site/refresh.json",
    "data/gb_voting_intention_polls.csv",
    "data/gb_voting_intention_average.csv",
    "outputs/polling/source_revisions.json",
    "data/household_energy_prices.csv",
    "data/industrial_electricity_prices.csv",
)
MANIFEST = "data/site/publication.json"
TRANSIENT = {404, 408, 429, 500, 502, 503, 504}


def digest(content):
    return hashlib.sha256(content).hexdigest()


def prepare(root, run_id, commit):
    if not re.fullmatch(r"\d+", run_id) or not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Invalid publication identity")
    manifest = {
        "version": 1, "run_id": run_id, "uk_commit": commit,
        "files": {path: digest((root / path).read_bytes()) for path in FILES},
    }
    content = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    (root / MANIFEST).write_bytes(content)
    return digest(content)


def fetch(url):
    request = Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "UK-publication-check"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def verify(base, expected, timeout=600, interval=20):
    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("Missing or invalid expected publication fingerprint")
    base = base.rstrip("/") + "/"
    deadline = time.monotonic() + timeout
    while True:
        try:
            content = fetch(urljoin(base, MANIFEST) + "?publication=" + expected)
            if digest(content) != expected:
                raise ValueError("Pages still serves a different publication")
            manifest = json.loads(content)
            if manifest.get("version") != 1 or set(manifest.get("files", {})) != set(FILES):
                raise ValueError("Unexpected publication manifest")
            for path, expected_digest in manifest["files"].items():
                actual = fetch(urljoin(base, path) + "?publication=" + expected)
                if digest(actual) != expected_digest:
                    raise ValueError(f"Published file does not match the built artifact: {path}")
            print(f"Verified live UK commit {manifest['uk_commit']} from run {manifest['run_id']}", flush=True)
            return
        except HTTPError as error:
            if error.code not in TRANSIENT:
                raise
            failure = error
        except (URLError, TimeoutError, ValueError) as error:
            failure = error
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(f"UK publication was not verified: {failure}") from failure
        print(f"Waiting for verified UK publication: {failure}", flush=True)
        time.sleep(min(interval, remaining))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("prepare")
    build.add_argument("root", type=Path)
    build.add_argument("--run-id", required=True)
    build.add_argument("--commit", required=True)
    live = commands.add_parser("verify")
    live.add_argument("--base", required=True)
    live.add_argument("--expected", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        print("manifest_sha256=" + prepare(args.root, args.run_id, args.commit))
    else:
        verify(args.base, args.expected)


if __name__ == "__main__":
    main()
