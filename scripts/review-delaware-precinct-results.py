"""Preserve reconciled 2026 Delaware precinct returns without misdating older boundaries."""

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("precinct_results", Path(__file__).with_name("build-precinct-results.py"))
results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(results)
SERVICE = "https://enterprise.firstmap.delaware.gov/arcgis/rest/services/Boundaries/DE_Political_Boundaries/FeatureServer"
SOURCES = {
    "district-results.json": "https://elections.delaware.gov/results/enr/Election_ByElectionDistrict_ID_GE2026.json",
    "statewide-results.json": "https://elections.delaware.gov/results/enr/Election_StatewideResults_ID_GE2026.json",
    "boundary-service.json": SERVICE + "?f=pjson",
    "boundary-layer.json": SERVICE + "/0?f=pjson",
    "districts.geojson": SERVICE + "/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson&resultRecordCount=2000",
    "results-page.html": results.DE,
    "results-page.js": "https://elections.delaware.gov/results/enr/js/results.js",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    originals = args.output / "originals"
    originals.mkdir()
    for name, url in SOURCES.items():
        response = requests.get(url, timeout=(15, 120))
        response.raise_for_status()
        (originals / name).write_bytes(response.content)
    source = json.loads((originals / "district-results.json").read_text())
    statewide = json.loads((originals / "statewide-results.json").read_text())
    rows = results.de_results(source, statewide)
    shapes = json.loads((originals / "districts.geojson").read_text())
    if shapes.get("exceededTransferLimit") or not shapes.get("features"):
        raise ValueError("Incomplete DE boundary capture")
    shape_ids = [f["properties"]["RDED"] for f in shapes["features"]]
    if len(shape_ids) != len(set(shape_ids)):
        raise ValueError("Duplicate DE boundary identity")
    service = json.loads((originals / "boundary-service.json").read_text())
    if "updated in November 2023" not in service["description"]:
        raise ValueError("DE boundary version changed; review before classifying it")
    csv_text = io.StringIO()
    writer = csv.DictWriter(csv_text, results.CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    (args.output / "results.csv.gz").write_bytes(gzip.compress(csv_text.getvalue().encode(), mtime=0))
    reporting_ids = {row["precinct"] for row in rows}
    audit = dict(year=2026, state_code="DE", candidate_results="acquired_reconciled",
        boundaries="older_reference_withheld", join="withheld", validation="counts_passed_map_withheld",
        publication="full_counts_download_only", complete="no",
        reporting_units=len(rows), source_candidate_rows=len(source),
        boundary_features=len(shape_ids), boundary_vintage="November 2023, per official service metadata",
        reporting_only=sorted(reporting_ids - set(shape_ids)), boundary_only=sorted(set(shape_ids) - reporting_ids),
        source_url=results.DE, sources=SOURCES,
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/voter-precinct-results-20261105/complete-delaware-precinct-source-review.zip",
        candidate_totals={field: sum(row[field] for row in rows) for field in
                          ["democratic_votes", "republican_votes", "other_votes", "contest_votes"]},
        notes="All 2026 House district/candidate ballot-mode totals reconcile exactly to official statewide totals. "
              "The current official boundary service identifies its election-district update as November 2023; "
              "reporting-only and boundary-only IDs are listed in this audit. No older geometry is relabeled 2026 or mapped. "
              "Complete normalized returns and all original source captures are retained in the separate full source ZIP.",
        next_action="Obtain verified 2026 election-district boundaries; resolve reporting-only and boundary-only identities before mapping.")
    (args.output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    checksums = {str(path.relative_to(args.output)): dict(bytes=path.stat().st_size,
                 sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in sorted(args.output.rglob("*")) if path.is_file()}
    (args.output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(args.output)))
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
