"""Reuse held Hawaii reports and group complete Census components into four native election administrations."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261109-hawaii-administrations-01"
GEOMETRY = "public/participation-county-administrations/20261109-hawaii-01/HI.geojson.gz"
AREAS = [
    ("HI-HONOLULU", "Honolulu election administration", "cch.pdf", ["15003"]),
    ("HI-HAWAII", "Hawaii election administration", "coh.pdf", ["15001"]),
    ("HI-KAUAI", "Kauai election administration", "cok.pdf", ["15007"]),
    ("HI-MAUI", "Maui election administration (includes Kalawao)", "com.pdf", ["15009", "15005"]),
]


def encoded(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def build(proof_path, scope_path):
    output = ROOT / VERSION
    geometry_output = ROOT / GEOMETRY
    if output.exists() or geometry_output.exists():
        raise ValueError("Refuse to replace immutable Hawaii inputs")
    prior = ROOT / "data/precinct-source-reviews/20261105/HI"
    receipts = json.loads((prior / "sources.json").read_bytes())
    reviewed = {row["file"]: row for row in json.loads(proof_path.read_bytes())}
    scope = json.loads(scope_path.read_bytes())
    reference_path = scope["held_2026_reference_path"]
    pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
    index = json.loads((ROOT / pointer["data_directory"] / "index.json").read_bytes())
    reference = index["coverage"]["HI"]
    raw_reference = (ROOT / reference_path).read_bytes()
    decoded_reference = gzip.decompress(raw_reference)
    if (hashlib.sha256(raw_reference).hexdigest() != reference["sha256"]
            or hashlib.sha256(decoded_reference).hexdigest() != reference["uncompressed_sha256"]
            or reference["counties"] != 5 or index["boundary_reference_year"] != 2026):
        raise ValueError("Changed complete Hawaii Census reference")
    original = json.loads(decoded_reference)
    features = {row["properties"]["key"]: row for row in original["features"]}
    if (set(features) != {"15001", "15003", "15005", "15007", "15009"}
            or any(row["properties"]["state_code"] != "HI"
                   or row["properties"]["boundary_year"] != 2026
                   or not shape(row["geometry"]).is_valid for row in features.values())):
        raise ValueError("Unqualified Hawaii source geometry; never repair it")
    members, grid, derived = {}, [], []
    for identity, label, name, components in AREAS:
        review = reviewed[name]
        body = gzip.decompress((prior / "originals" / (name + ".gz")).read_bytes())
        if (hashlib.sha256(body).hexdigest() != receipts[name]["sha256"]
                or review["receipt"]["sha256"] != receipts[name]["sha256"]
                or review["reader_agreement"] is not True
                or "GENERAL ELECTION 2026" not in review["source_header"][0]
                or review["source_header"][1] != "November 3, 2026"):
            raise ValueError("Changed independently reviewed Hawaii original")
        members["originals/" + name] = body
        text = "\n".join(review["full_PyMuPDF_text"])
        section = text.split("REGISTRATION AND TURNOUT\n", 1)[1].split("*****", 1)[0].strip()
        grid.append(dict(source_administration_id=identity, administration=label,
            component_county_fips=components, source_header=review["source_header"],
            native_values=review["literal_values"], native_turnout_section=section,
            source_url=receipts[name]["final_url"], source_original="originals/" + name,
            source_clock_literal=review["source_header"][5], source_timezone=None))
        combined = unary_union([shape(features[fips]["geometry"]) for fips in components])
        if not combined.is_valid:
            raise ValueError("Invalid grouped reference; no make_valid, buffer or clipping")
        derived.append(dict(type="Feature", properties=dict(key=identity, name=label,
            state_code="HI", boundary_year=2026, source_administration_id=identity,
            component_county_fips=components,
            geography_scope="Derived election administration from full 2026 Census components; not precincts"),
            geometry=mapping(combined)))
    if sorted(fips for row in grid for fips in row["component_county_fips"]) != sorted(features):
        raise ValueError("Duplicate or omitted Hawaii Census component")
    for name in ["histatewide.pdf", "media.txt"]:
        body = gzip.decompress((prior / "originals" / (name + ".gz")).read_bytes())
        if hashlib.sha256(body).hexdigest() != receipts[name]["sha256"]:
            raise ValueError("Changed held Hawaii statewide/source-unit original")
        members["originals/" + name] = body
    members["native-administration-grid.json"] = encoded(grid)
    members["native-unit-participation.json.gz"] = (prior / "participation.json.gz").read_bytes()
    members["source-audit.json"] = (prior / "audit.json").read_bytes()
    members["scope-facts.json"] = encoded(dict(
        scope_url=scope["official_scope_url"], scope_page=scope["official_scope_page"],
        scope_fact=scope["scope_fact"], administration_count=4, Census_counties=5,
        membership={r["source_administration_id"]: r["component_county_fips"] for r in grid},
        original_geometry_path=reference_path, counts_allocated=False, geometry_repaired=False,
        grouping_operation="unary_union of declared full components, not repaired or clipped polygons",
        certified_election_day_geography=False, rates_approved=False))
    derived_body = gzip.compress(encoded(dict(type="FeatureCollection", features=derived)), mtime=0)
    files = {f"{VERSION}/{name}": dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
             for name, body in members.items()}
    files[reference_path] = dict(bytes=len(raw_reference), sha256=reference["sha256"])
    files[GEOMETRY] = dict(bytes=len(derived_body), sha256=hashlib.sha256(derived_body).hexdigest())
    inputs = dict(year=2026, state_code="HI", files=files, rates_approved=False,
        cast_ballot_count_qualified=False, unique_voter_count_qualified=False, precincts_approved=False,
        reference=dict(path=GEOMETRY, url="/" + GEOMETRY.removeprefix("public/"),
            boundary_year=2026, counties=4, administration_count=4, Census_counties=5,
            geography_scope="native_election_administration", identity_field="source_administration_id",
            sha256=hashlib.sha256(derived_body).hexdigest(),
            uncompressed_sha256=hashlib.sha256(gzip.decompress(derived_body)).hexdigest(),
            review_id="hawaii-election-administrations-20261109-01"),
        original_reference=dict(path=reference_path, sha256=reference["sha256"],
            uncompressed_sha256=reference["uncompressed_sha256"], counties=5),
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-county-hawaii-administrations-20261109-01/complete-analysis.zip")
    output.mkdir(parents=True)
    for name, body in members.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    (output / "inputs.json").write_bytes(encoded(inputs))
    geometry_output.parent.mkdir(parents=True, exist_ok=True)
    geometry_output.write_bytes(derived_body)
    print(json.dumps(dict(administrations=4, Census_county_decisions=5,
        derived_geometry_bytes=len(derived_body), no_count_allocation=True, no_geometry_repairs=True)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    args = parser.parse_args()
    build(args.proof, args.scope)
