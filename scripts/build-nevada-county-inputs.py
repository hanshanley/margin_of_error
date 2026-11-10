"""Freeze new county originals, held Washoe and complete unchanged county context."""

import argparse
import gzip
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-nevada-native-counties-01"


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def freeze(acquisition):
    from shapely.geometry import shape

    target = ROOT / VERSION
    if target.exists():
        raise ValueError("Never overwrite an existing scientific input version")
    receipts = json.loads((acquisition / "source-receipts-without-headers.json").read_bytes())
    bodies = {"source-receipts-without-headers.json": encoded(receipts),
              "access-holds.json": (acquisition / "access-holds.json").read_bytes()}
    for county in ("Clark", "Churchill", "White Pine"):
        name = county.lower().replace(" ", "-")
        raw_name = name + ("-original.html.gz" if county == "Clark" else "-original.pdf")
        raw = (acquisition / raw_name).read_bytes()
        original = gzip.decompress(raw) if county == "Clark" else raw
        receipt = receipts[county]
        if pin(original) != {key: receipt[key] for key in ("bytes", "sha256")} or receipt["status"] != 200:
            raise ValueError("Changed acquired original: " + county)
        facts = (acquisition / (name + "-complete-numerical-facts.json")).read_bytes()
        bodies["originals/" + name + "-complete-numerical-facts.json"] = facts
        if county != "Clark":
            bodies["originals/" + raw_name] = raw
    held = ROOT / "data/county-source-reviews/20261106-washoe-participation-01"
    checksums = json.loads((held / "checksums.json").read_bytes())
    for name, expected in checksums.items():
        body = (held / name).read_bytes()
        if pin(body) != expected:
            raise ValueError("Changed inherited sufficient Washoe input: " + name)
        bodies["held-washoe/" + name] = body
    bodies["held-washoe/checksums.json"] = encoded(checksums)
    pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
    index = json.loads((ROOT / pointer["data_directory"] / "index.json").read_bytes())
    reference = index["coverage"]["NV"]
    url = urlparse(reference["file"])
    if url.hostname != "raw.githubusercontent.com" or len(url.path.split("/")[3]) != 40:
        raise ValueError("Unpinned county reference")
    body = (ROOT / "/".join(url.path.split("/")[4:])).read_bytes()
    decoded = gzip.decompress(body)
    if (pin(body)["sha256"] != reference["sha256"]
            or pin(decoded)["sha256"] != reference["uncompressed_sha256"]
            or reference["counties"] != 17 or index["boundary_reference_year"] != 2026):
        raise ValueError("Changed complete Nevada county context")
    geometry = json.loads(decoded)
    shapes = [(feature["properties"]["key"], shape(feature["geometry"])) for feature in geometry["features"]]
    if len(shapes) != 17 or any(not item.is_valid or item.is_empty for _, item in shapes):
        raise ValueError("Invalid native county reference; no repairs permitted")
    pairs = [dict(first_county_fips=first, second_county_fips=second,
        positive_overlap_area_degrees_squared=a.intersection(b).area)
        for (first, a), (second, b) in itertools.combinations(sorted(shapes), 2)]
    if any(row["positive_overlap_area_degrees_squared"] != 0 for row in pairs):
        raise ValueError("Positive overlap in full Nevada county reference")
    bodies["NV-full-county-reference.geojson.gz"] = body
    bodies["county-reference.json"] = encoded(dict(url=reference["file"],
        sha256=reference["sha256"], uncompressed_sha256=reference["uncompressed_sha256"],
        boundary_year=2026, counties=17, certified_legal_boundaries=False,
        geography_scope="native_county_statistics"))
    bodies["reference-review.json"] = encoded(dict(all17_valid_without_repairs=True,
        all136_county_pairs=pairs, areas_are_coordinate_degrees_squared_not_geodesic=True))
    target.mkdir(parents=True)
    for name, body in bodies.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    (target / "inputs.json").write_bytes(encoded(dict(version=VERSION,
        files={name: pin(body) for name, body in sorted(bodies.items())},
        full_two_native_PDFs_included=True, complete147_Clark_numerical_tables_included=True,
        publisher_application_code_and_acquisition_headers_excluded=True,
        raw_Clark_HTML_retained_privately_with_exact_native_hash=True,
        all_held_Washoe_sufficient_inputs_preserved=True,
        new_acquisitions=3, held_sources_reacquired=False,
        statewide_ballots_inferred=False, analysis_rates_approved=False,
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-nevada-native-counties-20261110-01/complete-analysis.zip")))
    print(json.dumps(dict(status="PASS_frozen_complete_inputs_NOT_production_acceptance",
        sufficient_inputs=len(bodies), new_counties=3, held_counties=1, reference_counties=17)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquisition", type=Path, required=True)
    freeze(parser.parse_args().acquisition)
