"""Freeze genuinely new statistics and the entire immutable prior reference package once."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-minnesota-complete-native-03"


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def freeze(args):
    target = ROOT / VERSION
    if target.exists():
        raise ValueError("Never replace frozen complete native inputs")
    baseline = args.previous_archive.read_bytes()
    if pin(baseline) != dict(bytes=50849478, sha256="7e66d26c48c0ca45555101ac1e04cf5306119b7a97482c03345edc365457a07b"):
        raise ValueError("Changed complete immutable previous original/reference package")
    bodies = {"baseline-complete-native-analysis.zip": baseline}
    for original, name in [
        ("pctstats.txt", "originals/pctstats.txt"),
        ("pctstats.txt.receipt.json", "originals/pctstats.txt.receipt.json"),
        ("complete-official-page-factual-fields.json", "official-page-factual-fields.json"),
        ("private-official-statistics-page.html.receipt.json", "official-page-receipt-without-headers.json"),
        ("all4105-native-snapshot-comparisons.json.gz", "preflight/all4105-complete-comparisons.json.gz"),
        ("qualified-complete-native-queries.json.gz", "preflight/qualified-complete-native-queries.json.gz"),
        ("qualified-source-summary.json", "preflight/qualified-source-summary.json"),
    ]:
        bodies[name] = (args.source / original).read_bytes()
    if pin(bodies["originals/pctstats.txt"]) != dict(bytes=206137,
            sha256="54085ea0fa1f183ad7e12c19d259a9c8d8e90bad6d682c7b7f8b0be7ef62e7e2"):
        raise ValueError("Changed newly acquired native source")
    target.mkdir(parents=True)
    for name, body in bodies.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    (target / "inputs.json").write_text(json.dumps(dict(version=VERSION,
        files={name: pin(body) for name, body in sorted(bodies.items())},
        original_previous_complete_package_included=True,
        all_native_originals_and_prior_reference_reviews_retained=True,
        all_new_4105_literal_comparisons_and_qualified_queries_included=True,
        source_native_clock="11/10/26 8:08 AM", source_native_timezone=None,
        new_acquisitions=0, new_geometry_acquisitions=0,
        raw_page_HTML_application_and_acquisition_headers_excluded=True,
        full_numerical_page_projection_included=True,
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-minnesota-complete-native-statistics-20261110-03/complete-analysis.zip"), indent=2) + "\n")
    print(json.dumps(dict(status="PASS_frozen_complete_new_native_inputs_NOT_view_acceptance",
        sufficient_inputs=len(bodies), source_reacquired=False)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--previous-archive", type=Path, required=True)
    freeze(parser.parse_args())
