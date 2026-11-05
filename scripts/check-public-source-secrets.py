#!/usr/bin/env python3
"""Reject copied Google API keys without printing their values."""

import argparse
import io
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile


GOOGLE_KEY = re.compile(rb"AIza[0-9A-Za-z_-]{35}")


def findings(data, location):
    results = [
        (location, data[:match.start()].count(b"\n") + 1)
        for match in GOOGLE_KEY.finditer(data)
    ]
    if data.startswith((b"PK\x03\x04", b"PK\x05\x06")):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.infolist():
                results.extend(findings(archive.read(member), location + "!" + member.filename))
    return results


def history_findings(root):
    results = []
    blobs = 0
    with tempfile.TemporaryFile() as revisions:
        subprocess.run(
            ["git", "rev-list", "--objects", "--no-object-names", "--all"],
            cwd=root, stdout=revisions, check=True,
        )
        revisions.seek(0)
        process = subprocess.Popen(
            ["git", "cat-file", "--batch"], cwd=root,
            stdin=revisions, stdout=subprocess.PIPE,
        )
        try:
            for header in iter(process.stdout.readline, b""):
                oid, kind, size = header.split()
                data = process.stdout.read(int(size))
                if len(data) != int(size) or process.stdout.read(1) != b"\n":
                    raise ValueError("Incomplete Git object stream")
                if kind == b"blob":
                    blobs += 1
                    results.extend(findings(data, "git-blob:" + oid.decode("ascii")))
            if process.wait():
                raise ValueError("Git history inspection failed")
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.terminate()
                process.wait()
    return results, blobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="Also inspect all reachable history")
    args = parser.parse_args()
    root = Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True,
    ).strip())
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).split(b"\0")
    results = []
    files = 0
    for raw_path in filter(None, paths):
        path = Path(raw_path.decode("utf-8"))
        results.extend(findings((root / path).read_bytes(), str(path)))
        files += 1
    blobs = 0
    if args.history:
        historical, blobs = history_findings(root)
        results.extend(historical)
    for location, line in results:
        safe_location = GOOGLE_KEY.sub(b"[REDACTED]", location.encode()).decode()
        print("{}:{}: Google API key pattern; value omitted".format(safe_location, line))
    if results:
        raise SystemExit(1)
    print("No Google API key patterns in {} tracked files and {} historical blobs.".format(files, blobs))


if __name__ == "__main__":
    main()
