"""Reproduce complete Minnesota participation facts without candidate-vote proxies."""

import argparse
from collections import Counter
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile


HERE = Path(__file__).resolve().parent
SCHEMAS = {
    "counties": ("county_id", "county_name", "native_precinct_count"),
    "parties": ("party_abbreviation", "party_name", "party_id"),
    "precincts": ("county_id", "precinct_id", "precinct_name", "congressional_district",
                  "legislative_district", "county_commissioner_district", "judicial_district",
                  "soil_water_conservation_district", "mcd_fips", "school_district"),
    "pctstats": ("state", "county_id", "precinct_id", "precinct_name", "has_reported_statistics",
                 "registered_7am", "registered_election_day", "roster_signatures",
                 "regular_military_overseas_absentee", "federal_only_absentee",
                 "president_only_absentee", "total_number_voted"),
    "county-results": ("state", "county_id", "native_precinct_field", "office_id", "office_name",
                       "district", "candidate_order_code", "candidate_name", "suffix",
                       "incumbent_code", "party_abbreviation", "precincts_reporting",
                       "precincts_for_office", "candidate_votes", "printed_candidate_percentage",
                       "office_votes"),
}
SCHEMAS["precinct-results"] = SCHEMAS["county-results"]
PROGRAMS = ("review-minnesota-bulk-participation.py",
            "acquire-minnesota-bulk-participation.py",
            "test-review-minnesota-bulk-participation.py")


def digest(body):
    return hashlib.sha256(body).hexdigest()


def number(value):
    if not value.isascii() or not value.isdecimal():
        raise ValueError("Non-native unsigned integer")
    return int(value)


def csv_bytes(headers, rows):
    target = io.StringIO(newline="")
    writer = csv.writer(target, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return target.getvalue().encode("utf-8")


def review(tables):
    for name, headers in SCHEMAS.items():
        if not tables[name] or any(len(row) != len(headers) for row in tables[name]):
            raise ValueError("Changed native schema: " + name)
    counties = {row[0]: row for row in tables["counties"]}
    if len(counties) != len(tables["counties"]):
        raise ValueError("Duplicate native county identity")
    references = {(row[0], row[1]): row for row in tables["precincts"]}
    statistics = {(row[1], row[2]): row for row in tables["pctstats"]}
    if (len(references) != len(tables["precincts"])
            or len(statistics) != len(tables["pctstats"])
            or references.keys() != statistics.keys()):
        raise ValueError("Missing or duplicated county-scoped precinct identity")
    for key, row in statistics.items():
        if (row[0] != "MN" or key[0] not in counties or row[3] != references[key][2]
                or row[4] not in ("0", "1")):
            raise ValueError("Changed native statistics identity or reporting flag")
        for value in row[5:]:
            number(value)
    component_residuals, electorate_excesses, summaries = [], [], []
    for row in tables["pctstats"]:
        if row[4] != "1":
            continue
        residual = number(row[11]) - sum(number(value) for value in row[7:11])
        excess = number(row[11]) - number(row[5]) - number(row[6])
        if residual:
            component_residuals.append(row + [residual])
        if excess > 0:
            electorate_excesses.append(row + [excess])
    for county_id, name, declared in tables["counties"]:
        selected = [row for key, row in statistics.items() if key[0] == county_id]
        if len(selected) != number(declared):
            raise ValueError("County does not match the complete reference universe")
        reported = [row for row in selected if row[4] == "1"]
        complete = len(reported) == len(selected)
        voted = sum(number(row[11]) for row in reported)
        registrations = sum(number(row[5]) + number(row[6]) for row in reported)
        excesses = sum(number(row[11]) > number(row[5]) + number(row[6]) for row in reported)
        conflicts = sum(number(row[11]) != sum(map(number, row[7:11])) for row in reported)
        summaries.append([
            county_id, name, "", declared, len(reported), len(selected) - len(reported),
            str(complete).lower(), voted, voted if complete else "",
            sum(number(row[5]) for row in reported) if complete else "",
            sum(number(row[6]) for row in reported) if complete else "",
            registrations if complete else "", excesses, conflicts,
            str(complete and registrations > 0 and voted <= registrations
                and excesses == 0 and conflicts == 0).lower(),
            "Total Number Voted", "Unofficial Results", "", "", "false", "false",
        ])
    counts = {}
    for name in ("county-results", "precinct-results"):
        totals = Counter()
        identities = set()
        for row in tables[name]:
            if (row[0] != "MN" or row[1] not in counties
                    or (name == "county-results" and row[2] != "")
                    or (name == "precinct-results" and (row[1], row[2]) not in references)):
                raise ValueError("Changed candidate geographic scope")
            identity = tuple(row[1:11])
            if identity in identities:
                raise ValueError("Duplicated native candidate/choice identity")
            identities.add(identity)
            for value in (row[11], row[12], row[13], row[15]):
                number(value)
            totals[tuple(row[1:2] + row[3:11])] += number(row[13])
        counts[name] = totals
    reconciliation = [
        list(key) + [counts["county-results"][key], counts["precinct-results"][key],
                     counts["county-results"][key] - counts["precinct-results"][key]]
        for key in sorted(counts["county-results"].keys() | counts["precinct-results"].keys())
    ]
    return {
        "county-participation.csv": csv_bytes((
            "native_county_id", "county_name", "native_fips", "reference_precincts",
            "reported_statistics", "missing_statistics", "all_statistics_reported",
            "reported_total_number_voted_subtotal", "complete_total_number_voted",
            "complete_registered_7am", "complete_registered_election_day",
            "derived_complete_7am_plus_election_day_registrations",
            "reported_precinct_electorate_excesses", "reported_precinct_component_conflicts",
            "eligible_for_registration_fraction_review", "native_numerator_label",
            "native_status", "native_update_clock", "native_timezone",
            "maps_approved", "rates_approved"), summaries),
        "statistic-component-residuals.csv": csv_bytes(
            SCHEMAS["pctstats"] + ("total_minus_roster_and_three_absentee_fields",),
            component_residuals),
        "statistic-electorate-excesses.csv": csv_bytes(
            SCHEMAS["pctstats"] + ("voted_minus_7am_and_election_day_registrations",),
            electorate_excesses),
        "county-choice-reconciliation.csv": csv_bytes(
            SCHEMAS["county-results"][1:2] + SCHEMAS["county-results"][3:11]
            + ("county_candidate_votes", "precinct_candidate_votes_sum", "county_minus_precinct_sum"),
            reconciliation),
    }


def original_tables(directory):
    spec = importlib.util.spec_from_file_location(
        "mn_acquire", HERE / "acquire-minnesota-bulk-participation.py")
    acquire = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(acquire)
    index = (directory / "media-index.html").read_bytes()
    declared = {"media-index.html": acquire.INDEX, **acquire.declared_sources(index)}
    receipts, bodies = [], {}
    for name, url in declared.items():
        body = (directory / name).read_bytes()
        receipt = json.loads((directory / (name + ".receipt.json")).read_text())
        if (receipt["url"] != url or receipt["final_url"] != url or receipt["status"] != 200
                or receipt["bytes"] != len(body) or receipt["sha256"] != digest(body)):
            raise ValueError("Native original does not match its complete receipt: " + name)
        receipts.append(dict(source_file=name, **receipt))
        bodies[name] = body
    acquire.statistic_inventory(bodies["pctstats.txt"])
    if b"Has Reported Statistics (1 = yes, 0 = no)" not in bodies["layout.txt"]:
        raise ValueError("Changed native reporting-flag definition")
    if b"Unofficial Results" not in index:
        raise ValueError("Unreviewed native certification status")
    tables = {}
    for name in SCHEMAS:
        body = bodies[name + ".txt"]
        try:
            text = body.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = body.decode("cp1252")
        tables[name] = list(csv.reader(io.StringIO(text), delimiter=";"))
    return tables, json.dumps(receipts, indent=2).encode() + b"\n"


def reproduce(originals, snapshot, output):
    if snapshot:
        for line in (snapshot / "checksums.sha256").read_text().splitlines():
            expected, name = line.split("  ", 1)
            if Path(name).name != name or digest((snapshot / name).read_bytes()) != expected:
                raise ValueError("Changed full snapshot file: " + name)
        tables = {}
        for name, headers in SCHEMAS.items():
            rows = list(csv.reader(io.StringIO((snapshot / (name + ".csv")).read_text())))
            if rows[0] != list(headers):
                raise ValueError("Changed snapshot header: " + name)
            tables[name] = rows[1:]
        sources = (snapshot / "sources.json").read_bytes()
    else:
        tables, sources = original_tables(originals)
    files = {name + ".csv": csv_bytes(SCHEMAS[name], rows) for name, rows in tables.items()}
    files.update(review(tables))
    files["sources.json"] = sources
    for name in PROGRAMS:
        files[name] = (HERE / name).read_bytes()
    audit = dict(
        election_date="2026-11-03", election_stage="general", native_status="Unofficial Results",
        native_update_clock=None, native_timezone=None,
        complete_native_rows={name: len(rows) for name, rows in tables.items()},
        reported_statistics=sum(row[4] == "1" for row in tables["pctstats"]),
        unreported_statistics=sum(row[4] == "0" for row in tables["pctstats"]),
        maps_approved=False, rates_approved=False,
        files={name: dict(bytes=len(body), sha256=digest(body)) for name, body in sorted(files.items())},
        scope="Complete native-field tables, not metadata-only downloads. Reporting flag1 is required "
              "for actual participation, including true zero. Partial counties retain subtotals but "
              "no complete participation or electorate. Native Total Number Voted is not candidate "
              "votes or inferred ballot modes. Roster signatures and three native absentee fields "
              "are not relabeled as ballot types; component conflicts and electorate excesses remain "
              "explicit and disqualify rate-review eligibility. All candidate and question responses, "
              "literal parties, printed fractions, office totals, scopes and ESTIMATED BLANKS survive "
              "without pooling across offices or assigning residuals to actual blank ballots. "
              "Native county IDs are not FIPS. Result-table precinct fields match native reference IDs "
              "despite the layout's printed 'Precinct name' label. Fetch clocks are not update clocks. "
              "No Census identity, county geometry, demographic turnout or certification is inferred.")
    files["audit.json"] = json.dumps(audit, indent=2).encode() + b"\n"
    files["checksums.sha256"] = "".join(
        digest(body) + "  " + name + "\n" for name, body in sorted(files.items())).encode()
    if snapshot:
        for name, body in files.items():
            if (snapshot / name).read_bytes() != body:
                raise ValueError("Offline reproduction differs: " + name)
    output.mkdir(parents=True, exist_ok=False)
    for name, body in files.items():
        (output / name).write_bytes(body)
    archive = output / "complete-minnesota-native-query.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
        for name, body in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            target.writestr(info, body, compresslevel=9)
    if (snapshot and (snapshot / archive.name).is_file()
            and archive.read_bytes() != (snapshot / archive.name).read_bytes()):
        raise ValueError("Offline complete archive differs")
    print(json.dumps(dict(output=str(output), files=len(files) + 1,
                          archive_bytes=archive.stat().st_size, archive_sha256=digest(archive.read_bytes()),
                          complete_native_rows=audit["complete_native_rows"]), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--originals", type=Path)
    source.add_argument("--snapshot", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reproduce(args.originals, args.snapshot, args.output)
