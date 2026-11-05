"""Acquire immutable original OpenElections files without claiming validated maps."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import subprocess
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def inspect_csv(raw, expected_blob):
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if blob != expected_blob:
        raise ValueError("Source bytes changed since the reviewed Git inventory")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    fields = reader.fieldnames
    if not fields or not any(field.lower() == "votes" or field.lower().endswith("_votes") for field in fields):
        raise ValueError("Expected an original election CSV with a votes column")
    rows, malformed = 0, 0
    for row in reader:
        rows += 1
        malformed += None in row or None in row.values()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                git_blob=blob, rows=rows, fields=fields, malformed_rows=malformed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    if (args.output / "acquisition.json").exists() or args.archive.exists():
        raise ValueError("Use a new unpublished output and archive")
    inventory = json.loads((ROOT / "public/precinct-source-inventory.json").read_text())
    leads = []
    for code, state in sorted(inventory["states"].items()):
        files = [file for file in state["elections"][str(args.year)]
                 if len(Path(file["path"]).parts) == 2 and file["path"].count("__") == 3]
        if len(files) > 1:
            raise ValueError(f"{code}: review multiple statewide source leads")
        if files:
            leads.append((code, state, files[0]))
    if not leads:
        raise ValueError("No matching original source files; refusing a metadata-only archive")
    args.output.mkdir(parents=True, exist_ok=True)

    def acquire(lead):
        code, state, file = lead
        commit = subprocess.run(
            ["gh", "api", f'repos/{state["repository"]}/commits/{state["branch"]}', "--jq", ".sha"],
            check=True, capture_output=True, text=True).stdout.strip()
        base = f'https://raw.githubusercontent.com/{state["repository"]}/{commit}/'
        response = requests.get(base + file["path"], timeout=(15, 180))
        response.raise_for_status()
        audit = inspect_csv(response.content, file["git_blob"])
        target = args.output / f"{code}.csv.gz"
        target.write_bytes(gzip.compress(response.content, mtime=0))
        readme = requests.get(base + "README.md", timeout=(15, 60))
        if readme.ok:
            (args.output / f"{code}-README.md").write_bytes(readme.content)
        audit.update(year=args.year, state_code=code, file=target.name, commit=commit,
                     source_url=base + file["path"], repository=state["repository"],
                     candidate_results="acquired_originals_review_pending",
                     participation="not_inferred_from_candidate_votes", join="not_attempted",
                     next_action="Review contest and ballot scope; reconcile official totals and acquire exact-election boundaries.")
        print(code, audit["rows"], "original CSV rows; Git blob verified", flush=True)
        return code, audit

    states = dict(ThreadPoolExecutor(max_workers=4).map(acquire, leads))
    report = dict(year=args.year, states=states,
                  scope="Complete original statewide CSV leads from the reviewed archive, not certified complete state coverage. "
                        "Candidate/statistic row semantics, missing ballot modes and boundaries still require review. "
                        "No map joins or participation rates are inferred.",
                  complete_download=args.archive.name)
    (args.output / "acquisition.json").write_text(json.dumps(report, indent=2) + "\n")
    checksums = {p.name: dict(bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                 for p in sorted(args.output.iterdir()) if p.is_file()}
    (args.output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.iterdir()):
            archive.write(path, path.name)
    print("Acquired", len(states), "jurisdictions; full original files retained", flush=True)


if __name__ == "__main__":
    main()
