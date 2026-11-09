"""Preserve held Colorado native workbook and a separate complete 2026 county identity review."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261109-colorado-returned-01"
ORIGINAL_SHA = "84eeee2797b0f442f82a8eb509a250eea72c7cd0923f5c8947003316aecebea7"


def build(source):
    output = ROOT / VERSION
    if output.exists():
        raise ValueError("Refuse to replace immutable Colorado inputs")
    original = (source / "originals/20261105GenElectionActivity.xlsx").read_bytes()
    if hashlib.sha256(original).hexdigest() != ORIGINAL_SHA:
        raise ValueError("Changed already-held Colorado workbook")
    qualification = json.loads((source / "source-qualification.json").read_bytes())
    if (qualification["publication_date"] != "2026-11-06"
            or qualification["source_period_end"] != "11:59 PM November 5, 2026"
            or qualification["source_timezone"] is not None
            or qualification["denominator"]["county_denominators_supplied"] is not False):
        raise ValueError("Changed source-specific Colorado frame")
    sheets = runpy.run_path(str(ROOT / "scripts/west-virginia-workbooks.py"))["original_sheets"](
        source / "originals/20261105GenElectionActivity.xlsx")
    pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
    index = json.loads((ROOT / pointer["data_directory"] / "index.json").read_bytes())
    reference = index["coverage"]["CO"]
    path = "data/" + reference["file"].split("/data/", 1)[1]
    geometry = (ROOT / path).read_bytes()
    decoded = gzip.decompress(geometry)
    if (reference["counties"] != 64 or index["boundary_reference_year"] != 2026
            or hashlib.sha256(geometry).hexdigest() != reference["sha256"]
            or hashlib.sha256(decoded).hexdigest() != reference["uncompressed_sha256"]):
        raise ValueError("Changed complete Colorado county reference")
    members = {
        "workbook-original.xlsx": original,
        "workbook-cells.json.gz": gzip.compress((json.dumps(sheets, indent=2) + "\n").encode(), mtime=0),
        "native-county-query.csv": (source / "county-participation.csv").read_bytes(),
    }
    files = {f"{VERSION}/{name}": dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
             for name, body in members.items()}
    files[path] = dict(bytes=len(geometry), sha256=reference["sha256"])
    inputs = dict(year=2026, state_code="CO", files=files,
        source_url=qualification["sources"]["activity_workbook"]["url"],
        publication_date="2026-11-06", source_period_end="11:59 PM November 5, 2026",
        source_timezone=None, rates_approved=False, cast_ballot_count_qualified=False,
        unique_voter_count_qualified=False, precincts_approved=False,
        reference=dict(path=path, url=reference["file"], boundary_year=2026, counties=64,
            sha256=reference["sha256"], uncompressed_sha256=reference["uncompressed_sha256"],
            review_id="colorado-returned-native-counties-20261109-01"),
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-county-colorado-returned-20261109-01/complete-analysis.zip")
    output.mkdir(parents=True)
    for name, body in members.items():
        (output / name).write_bytes(body)
    (output / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    print(json.dumps(dict(county_queries=64, source_workbook_sheets=len(sheets), rates_approved=False)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    build(parser.parse_args().source)
