"""Package all WV county/mode queries and sufficient permitted native inputs for offline replay."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261109-west-virginia-modes-01"
REPRODUCE = """import { loadWestVirginiaCountyModes } from './scripts/west-virginia-county-modes.mjs';
process.stdout.write(JSON.stringify(loadWestVirginiaCountyModes(), null, 2) + '\\n');
"""
REPRODUCE_WORKBOOKS = """import gzip,json,runpy
from pathlib import Path
version=Path('data/county-source-reviews/20261109-west-virginia-modes-01')
inputs=json.loads((version/'inputs.json').read_bytes())
geometry=json.loads(gzip.decompress(Path(inputs['reference']['path']).read_bytes()))
identities={r['properties']['key']:r['properties']['name'] for r in geometry['features']}
module=runpy.run_path('scripts/west-virginia-workbooks.py')
print(json.dumps(module['review_workbooks'](version,identities),indent=2))
"""


def build(output, sources):
    if output.exists() or (ROOT / VERSION / "queries.json.gz").exists():
        raise ValueError("Refuse to replace an immutable WV query package")
    raw = subprocess.check_output(["node", "--input-type=module", "-e", REPRODUCE], cwd=ROOT)
    queries = json.loads(raw)
    inputs = json.loads((ROOT / VERSION / "inputs.json").read_bytes())
    paths = set(inputs["files"]) | {VERSION + "/inputs.json",
        "scripts/west-virginia-county-modes.mjs", "scripts/west-virginia-county-modes.test.mjs",
        "scripts/west-virginia-workbooks.py", "scripts/build-west-virginia-mode-inputs.py",
        "scripts/package-west-virginia-county-modes.py", "public/scripts/participation-geography.js"}
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, receipt in inputs["files"].items():
        body = members[name]
        if len(body) != receipt["bytes"] or hashlib.sha256(body).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed sufficient WV source input")
    acquisition = json.loads((sources / "county-report-pass-01/complete-55-county-query.json").read_bytes())
    captures = json.loads((sources / "county-enr-capture-02/complete-county-captures.json").read_bytes())
    safe_queries = []
    for row in acquisition["rows"]:
        safe_queries.append(dict(county=row["county"], county_fips=row["county_fips"],
            initial_disposition=row["disposition"], selected_all_method_count=next(
                item["source_count"] for item in queries["counties"] if item["county_fips"] == row["county_fips"]),
            requests=[{key: value for key, value in request.items() if key in {
                "url", "http_status", "final_url", "bytes", "sha256", "disposition",
                "captured_at_utc", "acquisition_session_headers_saved"}}
                for request in row["requests"]]))
    members["source-followups/complete-55-county-query.json"] = (
        json.dumps(safe_queries, indent=2) + "\n").encode()
    members["source-followups/county-portal-dispositions.json"] = (json.dumps([
        dict(county=row["county"], county_fips=row["county_fips"], url=row["url"],
            disposition=row["disposition"], captured_at_utc=row["captured_at_utc"],
            responses=[{key: value for key, value in item.items() if key in
                {"url", "http_status", "disposition"}} for item in row["responses"]])
        for row in captures], indent=2) + "\n").encode()
    members["reproduce.mjs"] = REPRODUCE.encode()
    members["reproduce-workbooks.py"] = REPRODUCE_WORKBOOKS.encode()
    members["queries.json"] = raw
    table = io.StringIO()
    columns = ["year", "state_code", "county_fips", "county", "source_mode", "source_count",
        "participation_measure_label", "literal_total_field", "denominator", "reported_pct",
        "source_url", "source_update_label", "source_status_literal", "source_reporting_label",
        "cast_ballot_count_qualified", "unique_voter_count_qualified", "native_party_counts"]
    writer = csv.DictWriter(table, columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for mode, rows in [("all_method_county_snapshot", queries["counties"]),
                      *queries["county_frames"].items(), ("absentee_requested", queries["absentee_requests"])]:
        for row in rows:
            writer.writerow(dict(row, source_mode=mode,
                native_party_counts=json.dumps(row.get("native_party_counts"), separators=(",", ":"))))
    members["complete-county-mode-queries.csv"] = table.getvalue().encode()
    members["README.txt"] = (
        "West Virginia2026: complete55-county source/mode query, NOT full-election statewide turnout\n"
        "All55all-method county decisions:3native parents,52held. Wood22935/Kanawha48729/Monongalia28614\n"
        "are separateNov3 snapshots, not a common cutoff or a researcher statewide total.\n"
        "All55counties in each separate official workbook:162349early in-person/9735absentee requested/\n"
        "7001absentee returned. Every raw county/party cell, original state parent and empty worksheet\n"
        "is retained. TOTAL VOTERS is the literal field, not a certified unique-person definition.\n"
        "TheNov2agency release describes the period throughOct31. Native clocks/timezones are absent.\n"
        "The source's169350combined figure mixes early cast and returned; it is context only, NOT a\n"
        "qualified cast total. Never add, relabel or allocate these modes. All rates/denominatorsNULL.\n"
        "Seven native party categories are not candidate choices; operational affiliation definitions\n"
        "are unqualified. No party-choice inference, demographic allocation, survey fitting or fakeCI.\n"
        "All55county identities match a separately verified2026Census reference, not precincts.\n"
        "Monongalia0complete/43partially reported remains; no final/certified completion claim.\n"
        "All selected/held queries, sufficient originalXLSX/PDF/HTML data, source facts, geometry,\n"
        "code/tests/results are included. Non-numerical website prose, compiled publisher appcode,\n"
        "private contacts, record-search/challenge bodies and session headers are excluded.\n"
        "Extract every member into an empty directory; Node22+ and Python3.9+ need no network/packages:\n"
        "  node reproduce.mjs > reproduced-queries.json\n"
        "Compare byte-for-byte to queries.json. Then:\n"
        "  python3 reproduce-workbooks.py > reproduced-workbooks.json\n"
        "Compare byte-for-byte to decompressed native-mode-queries.json.gz under data/county-source-reviews.\n"
        "  node --test scripts/west-virginia-county-modes.test.mjs\n"
        "Older immutable archives and the frozen default reader are unchanged.\n"
    ).encode()
    manifest = dict(summary=queries["summary"], files={
        name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        for name, body in sorted(members.items())})
    members["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output.mkdir(parents=True)
    for name in ["queries.json", "complete-county-mode-queries.csv", "README.txt", "manifest.json"]:
        (output / name).write_bytes(members[name])
    archive = output / "complete-analysis.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as target:
        for name, body in sorted(members.items()):
            target.writestr(name, body)
    receipt = dict(url=inputs["complete_download_url"], bytes=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), members=len(members),
        all_method_county_queries=55, native_mode_county_queries=165, analysis_rates_approved=False)
    (ROOT / VERSION / "queries.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (ROOT / VERSION / "summary.json").write_text(json.dumps(queries["summary"], indent=2) + "\n")
    (ROOT / VERSION / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    args = parser.parse_args()
    build(args.output, args.sources)
