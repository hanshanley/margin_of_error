"""Package every original Indiana statistic, selected/held county query and sufficient input."""

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
VERSION = "data/county-source-reviews/20261109-indiana-voter-statistics-01"
REPRODUCE = """import { loadIndianaVoterStatistics } from './scripts/indiana-voter-statistics.mjs';
process.stdout.write(JSON.stringify(loadIndianaVoterStatistics(), null, 2) + '\\n');
"""


def build(output, followups):
    if output.exists() or (ROOT / VERSION / "queries.json.gz").exists():
        raise ValueError("Refuse to replace an Indiana complete query package")
    raw = subprocess.check_output(["node", "--input-type=module", "-e", REPRODUCE], cwd=ROOT)
    queries = json.loads(raw)
    if (len(queries["counties"]) != 92 or queries["summary"]["original_queries"] != 93
            or any(row["denominator"] is not None or row["reported_pct"] is not None
                   for row in queries["counties"])):
        raise ValueError("Incorrect Indiana query or withheld-rate inventory")
    inputs = json.loads((ROOT / VERSION / "inputs.json").read_bytes())
    paths = set(inputs["files"]) | {
        VERSION + "/inputs.json", "scripts/indiana-voter-statistics.mjs",
        "scripts/indiana-voter-statistics.test.mjs", "scripts/build-indiana-voter-statistics-inputs.py",
        "scripts/package-indiana-voter-statistics.py", "scripts/indiana-monroe-reference.py",
        "public/scripts/participation-geography.js",
    }
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, receipt in inputs["files"].items():
        body = members[name]
        if len(body) != receipt["bytes"] or hashlib.sha256(body).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed sufficient Indiana input: " + name)
    if followups:
        inventory = json.loads(followups.read_bytes())
        if len(inventory["county_queries"]) != 24:
            raise ValueError("Incomplete independent Indiana county-source follow-up query")
        for item in inventory["permitted_files"]:
            path = Path(item["held_path"])
            body = path.read_bytes()
            if len(body) != item["bytes"] or hashlib.sha256(body).hexdigest() != item["sha256"]:
                raise ValueError("Changed independent Indiana source/evidence")
            name = item["archive_path"]
            if name.startswith("/") or ".." in Path(name).parts or name in members:
                raise ValueError("Unsafe or duplicate Indiana archive member")
            members[name] = body
        safe_inventory = {key: value for key, value in inventory.items() if key != "permitted_files"}
        safe_inventory["files"] = [{key: value for key, value in item.items() if key != "held_path"}
                                   for item in inventory["permitted_files"]]
        members["county-followups/complete-query.json"] = (
            json.dumps(safe_inventory, indent=2) + "\n").encode()
    members["reproduce.mjs"] = REPRODUCE.encode()
    members["queries.json"] = raw
    table = io.StringIO()
    columns = ["state_code", "county", "county_fips", "participation_measure_label", "source_count",
        "selected_source_kind", "original_state_voters_voting", "original_state_registered_voters",
        "original_state_in_person", "original_state_absentee", "source_candidate_votes_not_participation",
        "denominator", "reported_pct", "cast_ballot_count_qualified", "unique_voter_count_qualified",
        "source_count_qualified", "source_url", "source_update_label", "source_status_literal",
        "source_reporting_label"]
    writer = csv.DictWriter(table, columns, lineterminator="\n")
    writer.writeheader()
    for row in queries["counties"]:
        record = {key: row.get(key) for key in columns}
        native = row["statewide_statistics_native_record"]
        record.update(original_state_voters_voting=native["VotersVoting"],
            original_state_registered_voters=native["REGISTERED_VOTERS"],
            original_state_in_person=native["InPerson"], original_state_absentee=native["Absentee"])
        writer.writerow(record)
    members["queries.csv"] = table.getvalue().encode()
    table = io.StringIO()
    writer = csv.DictWriter(table, fieldnames=[
        "native_precinct_id", "unit", "ballots", "denominator", "reported_pct",
        "match_status", "geometry_withheld_reason", "source_url", "source_reporting_label",
    ], extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(queries["precincts"])
    members["monroe-reporting-units.csv"] = table.getvalue().encode()
    table = io.StringIO()
    native = json.loads(gzip.decompress(members[VERSION + "/original-statewide-turnout.json.gz"]))
    writer = csv.DictWriter(table, fieldnames=list(native["root"]["CountyTurnout"][0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(native["root"]["CountyTurnout"])
    members["native-statistics.csv"] = table.getvalue().encode()
    members["README.txt"] = (
        "Indiana2026: complete native statistics and county-source participation query\n"
        "All93 original statistics rows:92 counties and the unchanged printed state subtotal1055902.\n"
        "The original source includes24 zero-VotersVoting records despite positive native contest votes.\n"
        "Every source zero remains in its original field; unsupported normalized counts are withheld,\n"
        "never shown as zero turnout or replaced with candidate votes. Independent county parents,\n"
        "where reviewed, are separate snapshots with their own literal measures and source clocks.\n"
        "VotersVoting is the native administrative field, not automatically cast ballots or unique people.\n"
        "InPerson/Absentee retain native definitions; Absentee is not relabelled mail received.\n"
        "Partial precinct/mode reporting and conflicting status labels are retained, not repaired.\n"
        "The source's printed state subtotal is partial statistics, not all-election statewide turnout.\n"
        "Every analysis denominator/rate remains null. No survey allocation, model fitting, demographic\n"
        "rates, certification or inferred staying-home population is supplied.\n"
        "All92 identities match the full2026Census county reference, not the site's2013 default map.\n"
        "Monroe: all103 native reporting-unit records are retained, including the federal count241.\n"
        "The publisher-defined Total Ballots Cast indicator42766 is reproduced, not a new researcher total.\n"
        "Only83 distinct nonoverlapping app-reference polygons are mapped; the federal carrier and19\n"
        "overlapping split polygons are held. No geometry repair, clipping or areal allocation occurs.\n"
        "All103 rows say Partially Reporting. The current reference is selected by the official2026 app,\n"
        "not independently certified2026 legal boundaries. The app's copied primary instruction conflict,\n"
        "unknown source clock, raw registration/percentage fields and all native zeros remain explicit.\n"
        "All selected/held queries and sufficient originals,\n"
        "permitted factual tables, numerical contradiction controls, source/evidence and code are included.\n"
        "Office contacts, vendor application code and acquisition session headers are excluded.\n"
        "Extract every member into an empty directory; Node22+ needs no network/npm:\n"
        "  node reproduce.mjs > reproduced-queries.json\n"
        "Compare reproduced-queries.json byte-for-byte with queries.json.\n"
        "  node --test scripts/indiana-voter-statistics.test.mjs\n"
        "The optional geometry normalizer scripts/indiana-monroe-reference.py uses Shapely2.0.7;\n"
        "its complete source counts/polygons and topology decisions are included. Node replay uses\n"
        "the verified normalization and needs neither Python nor Shapely.\n"
        "The dependency-free tests retain the baseline source query and exercise source conflicts,\n"
        "zero-versus-held, unsafe counts, county identities and independent-parent selection.\n"
        "Earlier source archives, website routes and model estimates remain unchanged.\n"
    ).encode()
    manifest = dict(version=VERSION, summary=queries["summary"],
        independent_followup_queries=24 if followups else 0,
        files={name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
               for name, body in sorted(members.items())})
    members["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output.mkdir(parents=True)
    for name in ("queries.json", "queries.csv", "monroe-reporting-units.csv", "native-statistics.csv",
                 "manifest.json", "README.txt"):
        (output / name).write_bytes(members[name])
    archive = output / "complete-analysis.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as target:
        for name, body in sorted(members.items()):
            target.writestr(name, body)
    receipt = dict(url=inputs["complete_download_url"], bytes=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), members=len(members),
        original_statistics_queries=93, selected_counts=queries["summary"]["selected_counts"],
        held_counts=queries["summary"]["held_counts"])
    (ROOT / VERSION / "queries.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (ROOT / VERSION / "queries.csv").write_bytes(members["queries.csv"])
    (ROOT / VERSION / "summary.json").write_text(json.dumps(queries["summary"], indent=2) + "\n")
    (ROOT / VERSION / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--county-followups", type=Path)
    args = parser.parse_args()
    build(args.output, args.county_followups)
