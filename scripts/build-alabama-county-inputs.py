"""Freeze held Alabama counts and complete county references without acquisition."""

import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-alabama-native-county-counts-02"
SOURCE = ROOT / "data/precinct-source-reviews/20261105/AL-2026-native-counts"
SAFE_RECEIPT_FIELDS = {
    "url", "effective_url", "status", "bytes", "sha256", "content_type",
    "fetched_at_utc", "started_at_utc", "finished_at_utc",
}


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def freeze(preflight):
    target = ROOT / VERSION
    if target.exists():
        raise ValueError("Never overwrite an existing scientific source version")
    checksums = json.loads((SOURCE / "checksums.json").read_bytes())
    for name, expected in checksums.items():
        if pin((SOURCE / name).read_bytes()) != expected:
            raise ValueError("Changed held native source: " + name)
    review = json.loads((SOURCE / "counts-review.json").read_bytes())
    if not (review["native_counties"] == 67 and review["native_ballots"] == 1693621
            and review["all_county_state_participation_scopes_reconcile"]):
        raise ValueError("Changed held native count qualification")
    bodies = {}
    for original, name in [
        ("native-source/originals/official-declared-native-export.gz", "originals/full-native-export.gz"),
        ("review-alabama-2026-native-results.py", "code/held-native-reader.py"),
        ("county-participation.csv", "legacy/all67-native-county-participation.csv"),
        ("counts-review.json", "legacy/prior-counts-review.json"),
        ("checksums.json", "legacy/full-held-source-checksums.json"),
    ]:
        bodies[name] = (SOURCE / original).read_bytes()
    spec = importlib.util.spec_from_file_location("held_alabama_reader", SOURCE / "review-alabama-2026-native-results.py")
    held = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(held)
    receipts = json.loads((SOURCE / "native-source/sources.json").read_bytes())
    facts, safe_receipts = {}, {}
    for name, receipt in receipts.items():
        body = gzip.decompress((SOURCE / "native-source/originals" / (name + ".gz")).read_bytes())
        if receipt["status"] != 200 or pin(body) != {key: receipt[key] for key in ["bytes", "sha256"]}:
            raise ValueError("Changed held original receipt: " + name)
        safe_receipts[name] = {key: value for key, value in receipt.items() if key in SAFE_RECEIPT_FIELDS}
        if name.startswith("official-county-") and name != "official-declared-county-selector":
            page = held.NativePage()
            page.feed(body.decode())
            facts[name] = dict(native_county_code=receipt["county_code"],
                native_county_name=receipt["county_name"], literal_source_fields=page.values)
        elif name == "official-statewide-results":
            page = held.NativePage()
            page.feed(body.decode())
            facts[name] = dict(literal_source_fields=page.values)
    if len(receipts) != 70 or len(facts) != 68:
        raise ValueError("Incomplete held native factual projection")
    bodies["originals/all67-county-and-state-literal-fields.json"] = encoded(facts)
    bodies["source-receipts-without-headers.json"] = encoded(safe_receipts)
    pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
    index = json.loads((ROOT / pointer["data_directory"] / "index.json").read_bytes())
    reference = index["coverage"]["AL"]
    url = urlparse(reference["file"])
    if url.hostname != "raw.githubusercontent.com" or len(url.path.split("/")[3]) != 40:
        raise ValueError("Unpinned county reference")
    reference_body = (ROOT / "/".join(url.path.split("/")[4:])).read_bytes()
    decoded = gzip.decompress(reference_body)
    if (pin(reference_body)["sha256"] != reference["sha256"]
            or pin(decoded)["sha256"] != reference["uncompressed_sha256"]
            or index["boundary_reference_year"] != 2026 or reference["counties"] != 67):
        raise ValueError("Changed complete county reference")
    bodies["AL-full-county-reference.geojson.gz"] = reference_body
    bodies["county-reference.json"] = encoded(dict(
        url=reference["file"], sha256=reference["sha256"],
        uncompressed_sha256=reference["uncompressed_sha256"], boundary_year=2026, counties=67,
        certified_election_boundaries=False))
    proof = json.loads((preflight / "proof.json").read_bytes())
    query = (preflight / "queries.json").read_bytes()
    if not proof["status"].startswith("PASS") or pin(query) != proof["query"]:
        raise ValueError("Changed complete county identity/pair preflight")
    bodies["prior-join-review/queries.json"] = query
    bodies["prior-join-review/proof.json"] = encoded(proof)
    target.mkdir(parents=True)
    for name, body in bodies.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    inputs = dict(version=VERSION,
        files={name: pin(body) for name, body in sorted(bodies.items())},
        original_county_codes_are_ordinals_not_FIPS=True,
        complete_native_workbook_included=True,
        all67_county_and_state_factual_fields_included=True,
        native_HTML_factual_projection_not_publisher_application=True,
        native_HTML_originals_retained_in_prior_complete_release=True,
        acquisition_headers_and_compiled_publisher_app_code_excluded=True,
        inherited_source_pins_verified=len(checksums), original_source_receipts=70,
        source_reacquired=False, source_counts_repaired=False,
        native_measure_literal="Ballots Cast", native_county_count=67,
        native_county_ballot_sum=1693621, source_certification_inferred=False,
        native_update_timezone=None, analysis_rates_approved=False,
        precinct_coverage_approved=False, candidate_votes_used_as_ballots=False,
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-alabama-native-county-counts-20261110-02/complete-analysis.zip")
    (target / "inputs.json").write_bytes(encoded(inputs))
    print(json.dumps(dict(status="PASS_frozen_complete_held_inputs_NOT_website_acceptance",
        source_version=VERSION, sufficient_inputs=len(bodies), native_counties=67,
        original_native_workbook_bytes=len(gzip.decompress(bodies["originals/full-native-export.gz"])),
        new_acquisitions=0, application_and_headers_excluded=True)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", type=Path, required=True)
    freeze(parser.parse_args().preflight)
