"""Freeze already-qualified Minnesota originals and full queries, without acquisition."""

import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-minnesota-followup-02"
SAFE_RECEIPT_FIELDS = {
    "attempts", "bytes", "content_type", "final_url", "sha256", "status", "url",
    "receipt_finished_at_utc", "request_started_at_utc", "fetched_at_utc",
    "declared_link_text", "declared_by_reused_original", "source_url",
}


def digest(body):
    return hashlib.sha256(body).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def build(source, previous):
    target = ROOT / VERSION
    if target.exists():
        raise ValueError("Never overwrite an existing scientific source version")
    manifest = {}
    for line in (source / "checksums.sha256").read_text().splitlines():
        expected, name = line.split("  ", 1)
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("Unsafe held source path")
        manifest[name] = expected
    names = [
        "county-participation-current.csv", "county-comparison-to-20261106.csv",
        "county-native-components.csv", "newly-complete-counties.csv",
        "revised-previously-complete-counties.csv", "precinct-quality-exceptions.csv",
        "official-page-estimates-vs-native.csv", "previous-county-participation-20261106.csv",
        "state-summary.json", "current-official-web-observation.json",
        "linked-history-availability.json", "verification-results.json", "build_minnesota_followup.py",
        "originals/pctstats.txt",
        "reused-frozen-originals/counties.txt", "reused-frozen-originals/precincts.txt",
        "reused-frozen-originals/layout.txt",
    ]
    bodies = {}
    for name in names:
        body = (source / name).read_bytes()
        if digest(body) != manifest[name]:
            raise ValueError("Changed already-qualified native input: " + name)
        bodies[name] = body
    bodies["prior-qualification.txt"] = (source / "README.md").read_bytes()
    if digest(bodies["prior-qualification.txt"]) != manifest["README.md"]:
        raise ValueError("Changed prior source qualification")
    declaration_body = (source / "reused-frozen-originals/media-index.html").read_bytes()
    if digest(declaration_body) != manifest["reused-frozen-originals/media-index.html"]:
        raise ValueError("Changed retained source declaration")
    spec = importlib.util.spec_from_file_location("held_followup", source / "build_minnesota_followup.py")
    held = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(held)
    parser = held.LinkParser()
    parser.feed(declaration_body.decode())
    if parser.href != "https://electionresultsfiles.sos.mn.gov/20261103/pctstats.txt":
        raise ValueError("Changed originally declared native statistics product")
    for name in [
        "originals/pctstats.txt.receipt.json", "reused-frozen-originals/counties.txt.receipt.json",
        "reused-frozen-originals/precincts.txt.receipt.json", "reused-frozen-originals/layout.txt.receipt.json",
    ]:
        body = (source / name).read_bytes()
        if digest(body) != manifest[name]:
            raise ValueError("Changed held receipt")
        receipt = json.loads(body)
        bodies[name] = encoded({key: value for key, value in receipt.items() if key in SAFE_RECEIPT_FIELDS})
    old = (previous / "pctstats.txt").read_bytes()
    receipt = json.loads((previous / "pctstats.txt.receipt.json").read_bytes())
    if receipt["status"] != 200 or receipt["sha256"] != digest(old) or receipt["bytes"] != len(old):
        raise ValueError("Changed original earlier native statistics")
    bodies["originals/previous-pctstats.txt"] = old
    bodies["originals/previous-pctstats.txt.receipt.json"] = encoded({
        key: value for key, value in receipt.items() if key in SAFE_RECEIPT_FIELDS})
    pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
    index = json.loads((ROOT / pointer["data_directory"] / "index.json").read_bytes())
    coverage = index["coverage"]["MN"]
    url = urlparse(coverage["file"])
    if (url.hostname != "raw.githubusercontent.com" or len(url.path.split("/")[3]) != 40
            or coverage["counties"] != 87 or index["boundary_reference_year"] != 2026):
        raise ValueError("Unpinned or wrong-vintage county reference")
    path = "/".join(url.path.split("/")[4:])
    geometry = (ROOT / path).read_bytes()
    if digest(geometry) != coverage["sha256"] or digest(gzip.decompress(geometry)) != coverage["uncompressed_sha256"]:
        raise ValueError("Changed complete held county reference")
    bodies["MN-county-reference.geojson.gz"] = geometry
    bodies["county-reference.json"] = encoded(dict(
        url=coverage["file"], sha256=coverage["sha256"],
        uncompressed_sha256=coverage["uncompressed_sha256"], boundary_year=2026, counties=87,
        source_county_ids_are_not_fips=True, certified_election_boundaries=False))
    summary = json.loads(bodies["state-summary.json"])
    if (summary["counties_complete"] != 84 or summary["missing_precinct_statistics"] != 26
            or summary["current_exact_statewide_total_number_voted"] is not None):
        raise ValueError("Changed held completeness qualification")
    target.mkdir(parents=True)
    for name, body in bodies.items():
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
    pins = {name: dict(bytes=len(body), sha256=digest(body)) for name, body in sorted(bodies.items())}
    inputs = dict(version=VERSION, files=pins, held_inputs_reused_without_acquisition=True,
        held_followup_original_manifest_sha256=digest((source / "checksums.sha256").read_bytes()),
        source_native_clock="11/07/26 5:18 PM", source_native_timezone=None,
        source_election_date="2026-11-03", original_source_receipt_headers_excluded=True,
        source_declaration=dict(
            media_url="https://electionresults.sos.mn.gov/Select/MediaFiles/Index?ersElectionId=201",
            native_statistics_url="https://electionresultsfiles.sos.mn.gov/20261103/pctstats.txt",
            link_text="Precinct Reporting Statistics",
            selected_declaration_from_manifest_verified_held_HTML=True,
            raw_page_scripts_and_acquisition_headers_not_redistributed=True,
            previous_complete_source="data/county-source-reviews/20261106-minnesota-facts-01/complete-minnesota-native-query.zip"),
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-minnesota-native-county-followup-20261110-02/complete-analysis.zip",
        statewide_exact_count=None, native_county_rows=87, complete_counties=84, partial_counties=3,
        missing_native_statistics=26, source_counts_repaired=False, candidate_votes_used_as_ballots=False)
    (target / "inputs.json").write_bytes(encoded(inputs))
    print(json.dumps(dict(status="PASS_frozen_existing_inputs_NOT_website_acceptance",
        files=len(pins), native_counties=87, complete_counties=84, partial_counties=3,
        new_acquisitions=0, source_version=VERSION)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--previous-originals", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.previous_originals)
