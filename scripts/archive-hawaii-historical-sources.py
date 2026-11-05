"""Archive complete advertised Hawaii historical originals without claiming reconciled results."""

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile


YEARS = (2024, 2022, 2020, 2018)
SOURCE = "https://elections.hawaii.gov/election-results/"
EXPECTED_FILES = {2024: 10, 2022: 11, 2020: 9, 2018: 9}
CORE = {"histatewide.pdf", "coh.pdf", "com.pdf", "cok.pdf", "cch.pdf",
        "precinct.pdf", "media.txt", "summary.txt"}


def text_inventory(raw):
    encoding = ("utf-16" if raw.startswith(b"\xff\xfe") else
                "utf-16-le" if raw.startswith(b"F\x00o\x00") else "utf-8-sig")
    rows = list(csv.reader(io.StringIO(raw.decode(encoding), newline="")))
    if not rows:
        raise ValueError("Empty historical Hawaii text source")
    metadata = rows[0] == ["Format#1"]
    if metadata:
        rows = rows[1:]
    if len(rows) < 2:
        raise ValueError("Missing historical Hawaii source header or records")
    header, records = rows[0], rows[1:]
    extra_empty = all(len(row) == len(header) + 1 and row[-1] == "" for row in records)
    if not extra_empty and any(len(row) != len(header) for row in records):
        raise ValueError("Truncated or inconsistent historical Hawaii source fields")
    return dict(encoding=encoding, delimiter=",", source_format_metadata="Format#1" if metadata else None,
                native_header=header, native_data_records=len(records),
                native_record_widths=dict(Counter(len(row) for row in records)),
                data_trailing_empty_field_absent_from_header=extra_empty)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable Hawaii historical source archive")
    originals, receipts, elections = {}, {}, {}
    for year in YEARS:
        root = args.cache_root / f"HI-{year}"
        sources = json.loads((root / "sources.json").read_bytes())
        if len(sources) != EXPECTED_FILES[year] or not CORE <= set(sources):
            raise ValueError("Incomplete advertised historical Hawaii original inventory")
        formats = {}
        for name, receipt in sources.items():
            path = Path(name)
            if path.name != name:
                raise ValueError("Invalid historical Hawaii original basename")
            directory = "General" if year == 2024 else "general"
            if receipt["url"] != f"https://files.hawaii.gov/elections/files/results/{year}/{directory}/{name}":
                raise ValueError("Wrong Hawaii historical election-source identity")
            raw = (root / name).read_bytes()
            if len(raw) != receipt["bytes"] or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
                raise ValueError("Changed historical Hawaii original: " + name)
            if name.endswith(".txt"):
                formats[name] = text_inventory(raw)
            elif not raw.startswith(b"%PDF"):
                raise ValueError("Wrong historical Hawaii PDF response")
            key = f"{year}/{name}"
            originals[key] = raw
            receipts[key] = receipt
        elections[str(year)] = dict(year=year, state_code="HI", complete="no",
            candidate_results="acquired_originals_review_pending",
            boundaries="not_acquired_in_this_batch", join="pending",
            validation="complete_source_bytes_and_native_record_structure_verified",
            publication="full_originals_download_only", participation="not_reconciled",
            source_url=SOURCE, original_files=len(sources),
            original_bytes=sum(s["bytes"] for s in sources.values()), text_formats=formats,
            next_action="Independently identify election/contest/candidate and reporting-mode scope, "
                        "reconcile original summaries and recounts, and acquire exact-election boundaries. "
                        "Do not run the 2026 tab-delimited parser on these historical comma-separated sources.")
    args.output.mkdir(parents=True)
    for key, raw in originals.items():
        path = args.output / "originals" / (key + ".gz")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(raw, mtime=0))
    for name, value in {
        "sources.json": receipts,
        "acquisition.json": dict(state_code="HI", elections=elections, original_files=len(originals),
            original_bytes=sum(map(len, originals.values())),
            notes="All 39 advertised general-election originals, including Statements of Vote and three "
                  "recount documents. Full data, not metadata-only exports. Source bytes and CSV record "
                  "structure are verified, not candidate totals, participation denominators or geometry. "
                  "Preserve exact URL case, source encoding, quoted multiline records, omitted trailing "
                  "header fields and historical absentee/early/election mode distinctions.")
    }.items():
        (args.output / name).write_text(json.dumps(value, separators=(",", ":"), ensure_ascii=True))
    (args.output / "checksums.json").write_text(json.dumps({
        str(path.relative_to(args.output)): dict(bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(args.output.rglob("*")) if path.is_file()
    }, separators=(",", ":")))
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(str(path.relative_to(args.output)), date_time=(2026, 11, 5, 0, 0, 0))
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())
    print(json.dumps(dict(original_files=len(originals), elections=elections,
        archive_bytes=args.archive.stat().st_size,
        archive_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest()), indent=2))


if __name__ == "__main__":
    main()
