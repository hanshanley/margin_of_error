"""Preserve the complete Indiana statistics query and its independent county identities."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import runpy
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261109-indiana-voter-statistics-01"
TURNOUT_SHA = "eb240d626034c20959e443dec0246b1e137aefcf2fe1054f5df4991444846d80"


def build(native, settings, candidate, parents, output, monroe_counts=None, monroe_geometry=None, monroe_url=None):
    if output.exists():
        raise ValueError("Refuse to replace an Indiana source snapshot")
    raw_turnout = gzip.decompress(native.read_bytes())
    if hashlib.sha256(raw_turnout).hexdigest() != TURNOUT_SHA:
        raise ValueError("Wrong original Indiana statistics query")
    raw_settings = gzip.decompress(settings.read_bytes())
    raw_candidate = gzip.decompress(candidate.read_bytes())
    meta = json.loads(raw_settings)["Root"]
    source = json.loads(raw_candidate)["Root"]
    if (meta["StateFP"] != "18" or meta["CurrentElection"] != "11/03/2026"
            or meta["ElectionType"] != "G" or meta["Certified"] != "F"
            or source["OfficeCategory"]["OFFICECATEGORYID"] != "1041"
            or source["OfficeCategory"]["OFFICE_CATEGORY_NAME"] != "Secretary of State"):
        raise ValueError("Incorrect Indiana source election or county-identity control")
    regions = source["OfficeCategory"]["Regions"]["Region"]
    if len(regions) != 92 or len({row["MAP_FIPS"] for row in regions}) != 92:
        raise ValueError("Incomplete native Indiana county-identity inventory")
    roster = dict(year=2026, state_code="IN", office_category_id="1041",
        office_category_name="Secretary of State", source_write_time=source["WriteTime"],
        source_url="https://enr.indianavoters.in.gov/site/data/OffCatC_1041_B.json",
        original_bytes=len(raw_candidate), original_sha256=hashlib.sha256(raw_candidate).hexdigest(),
        excluded_fields="Office_Info contacts and candidate identity/party text; every county identity and numerical candidate vector is retained",
        purpose="Contradiction check only. Candidate votes are never participation estimates.", rows=[])
    for region in regions:
        race = region["RegionSummary"]["Race"]
        values = race["Candidates"]["Candidate"]
        values = values if isinstance(values, list) else [values]
        roster["rows"].append(dict(
            county_fips=region["MAP_FIPS"], native_county_name=region["MAP_JURISDICTION_NAME"],
            native_jurisdiction_id=region["MAP_JURISDICTIONID"],
            native_jurisdiction_type=region["MAP_JURISDICTION_TYPE"],
            number_of_seats=race["NumofSeats"], office_id=race["OFFICEID"],
            candidate_counts=[row["TOTAL"] for row in values]))
    pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
    index = json.loads((ROOT / pointer["data_directory"] / "index.json").read_bytes())
    source_reference = index["coverage"]["IN"]
    path = "/".join(urlsplit(source_reference["file"]).path.split("/")[4:])
    geometry = (ROOT / path).read_bytes()
    if (index["boundary_reference_year"] != 2026 or source_reference["counties"] != 92
            or hashlib.sha256(geometry).hexdigest() != source_reference["sha256"]
            or hashlib.sha256(gzip.decompress(geometry)).hexdigest() != source_reference["uncompressed_sha256"]):
        raise ValueError("Incorrect full Indiana 2026 county reference")
    county_parents = json.loads(parents.read_bytes()) if parents else []
    members = {
        "original-statewide-turnout.json.gz": gzip.compress(raw_turnout, mtime=0),
        "original-settings.json.gz": gzip.compress(raw_settings, mtime=0),
        "native-county-identity-control.json.gz": gzip.compress(
            (json.dumps(roster, indent=2) + "\n").encode(), mtime=0),
    }
    for parent in county_parents:
        original = Path(parent.pop("held_original_path")).read_bytes()
        if (len(original) != parent["original_bytes"]
                or hashlib.sha256(original).hexdigest() != parent["original_sha256"]):
            raise ValueError("Changed independently reviewed Indiana county report")
        filename = "originals/" + parent["county_fips"] + Path(parent["original_filename"]).suffix
        if filename in members:
            raise ValueError("Duplicate independent county original")
        members[filename] = original
        parent["original_path"] = VERSION + "/" + filename
    members["independent-county-parents.json"] = (json.dumps(county_parents, indent=2) + "\n").encode()
    public_members = {}
    monroe = None
    if monroe_counts or monroe_geometry:
        if not (monroe_counts and monroe_geometry and monroe_url):
            raise ValueError("Monroe count/reference originals and source URL must be supplied together")
        normalize = runpy.run_path(str(ROOT / "scripts/indiana-monroe-reference.py"))["build_monroe"]
        extra, public_members, audit = normalize(
            monroe_counts.read_bytes(), monroe_geometry.read_bytes(), monroe_url)
        members.update(extra)
        monroe = dict(participation_file=VERSION + "/monroe-reporting-units.json.gz",
            source_count_file=VERSION + "/monroe-original-counts.json",
            selected_reference_file=VERSION + "/monroe-selected-polygons.json",
            audit_file=VERSION + "/monroe-reference-review.json",
            normalized_reference_file="public/participation-precincts/20261109-indiana-monroe-01/IN.geojson.gz",
            original_source_rows=103, mapped_polygons=audit["mapped_polygons"])
    files = {f"{VERSION}/{name}": dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
             for name, body in members.items()}
    files[path] = dict(bytes=len(geometry), sha256=hashlib.sha256(geometry).hexdigest())
    for name, body in public_members.items():
        if (ROOT / name).exists():
            raise ValueError("Refuse to replace an existing Monroe browser reference")
        files[name] = dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    inputs = dict(version=VERSION, year=2026, state_code="IN", files=files,
        source_data_url="https://enr.indianavoters.in.gov/site/data/statewideTurnout_B.json",
        original_stats_bytes=len(raw_turnout), original_stats_sha256=TURNOUT_SHA,
        reference=dict(path=path, url=source_reference["file"], sha256=source_reference["sha256"],
            uncompressed_sha256=source_reference["uncompressed_sha256"], boundary_year=2026, counties=92,
            review_id="indiana-native-voter-statistics-20261109-01"),
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-county-indiana-voter-statistics-20261109-01/complete-analysis.zip",
        state_full_election_participation_qualified=False, analysis_rates_approved=False,
        precincts_approved=False, monroe=monroe)
    output.mkdir(parents=True)
    for name, body in members.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
    (output / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    for name, body in public_members.items():
        destination = ROOT / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
    print(json.dumps(dict(original_statistics_queries=93, native_county_identities=92,
        county_parent_originals=len(county_parents), all_source_zeros_preserved=True)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--county-parents", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / VERSION)
    parser.add_argument("--monroe-counts", type=Path)
    parser.add_argument("--monroe-geometry", type=Path)
    parser.add_argument("--monroe-source-url")
    args = parser.parse_args()
    build(args.native, args.settings, args.candidate, args.county_parents, args.output,
          args.monroe_counts, args.monroe_geometry, args.monroe_source_url)
