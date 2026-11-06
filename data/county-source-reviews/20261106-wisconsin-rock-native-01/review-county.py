import argparse
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import zipfile


HERE = Path(__file__).resolve().parent
STATIC = ("source-qualification.json", "methods.json", "review-county.py", "test_review_county.py")
FILENAMES = {
    "participation": "county-participation.csv",
    "unit_participation": "native-unit-participation.csv",
    "candidates": "county-candidate-results.csv",
    "unit_candidates": "native-unit-candidate-results.csv",
    "parties": "county-literal-party-results.csv",
    "cells": "source-native-cells.csv",
    "reporting": "native-reporting-statements.csv",
}


def integer(text):
    if not isinstance(text, str) or not re.fullmatch(r"(?:0|[1-9]\d{0,2}(?:,\d{3})*)", text):
        raise ValueError("Invalid native comma-delimited integer")
    return int(text.replace(",", ""))


def percentage(text, numerator, denominator):
    if not isinstance(text, str) or not re.fullmatch(r"\d+\.\d{2}%", text):
        raise ValueError("Invalid printed native percentage")
    derived = Decimal(numerator) * 100 / Decimal(denominator)
    if derived.quantize(Decimal(".01"), rounding=ROUND_HALF_UP) != Decimal(text[:-1]):
        raise ValueError("Printed percentage does not reconcile to its native denominator")
    return str(derived)


def review(source):
    if any(source[key] is not False for key in (
        "generic_turnout_approved", "county_fips_join_approved", "map_approved",
        "certified", "all_mode_definition_approved",
    )):
        raise ValueError("Numerical source review cannot grant analysis, scope or geography approval")
    if source["source_timezone"] is not None or source["native_fips"] is not None:
        raise ValueError("Do not invent a timezone or native FIPS")
    if (source["election_date"] != "2026-11-03"
            or source["native_title"] != "Rock County Wisconsin - Election Results"
            or source["native_heading"] != "November 3, 2026 - General Election - Unofficial Results"
            or source["native_update_literal"] != "November 03, 2026 at 10:56 PM"
            or source["scope_literal"] != "Votes reflect Rock County ONLY"):
        raise ValueError("Unexpected native election, geography, update or scope")
    tables = source["tables"]
    if len(tables) != 53 or tables[0] != [["", "", "", "", ""]]:
        raise ValueError("Incomplete native tables or changed blank layout table")
    statements = source["reporting_statements"]
    if len(statements) != 26:
        raise ValueError("Incomplete native reporting statements")
    parsed = {key: [] for key in FILENAMES}
    for table_ordinal, table in enumerate(tables):
        for row_ordinal, row in enumerate(table):
            for column, literal in enumerate(row):
                parsed["cells"].append(dict(
                    source_table_ordinal=table_ordinal, source_row_ordinal=row_ordinal,
                    source_column_ordinal=column, literal_text=literal,
                ))
    summary, detail = tables[1:3]
    if (len(summary) != 3 or summary[0] != ["Voters and Ballots", "", "", "Votes"]
            or summary[1][:3] != ["Registered Voters", "", ""]
            or summary[2][:2] != ["Ballots Cast", ""]
            or detail[0] != ["", "Precinct", "Registered Voters - Total", "Ballots Cast - Total"]
            or len(detail) != 108):
        raise ValueError("Incomplete native participation table")
    registrations, ballots = integer(summary[1][3]), integer(summary[2][3])
    if registrations <= 0 or ballots > registrations:
        raise ValueError("Invalid native county ballots or registration denominator")
    fraction = percentage(summary[2][2], ballots, registrations)
    parsed["participation"].append(dict(
        native_county="Rock County", native_state="Wisconsin",
        reported_ballots_cast=ballots, reported_registered_voters=registrations,
        native_registered_percentage=summary[2][2],
        independently_derived_registered_fraction_percent=fraction,
        native_update_literal=source["native_update_literal"], source_timezone=None,
        native_fips=None, all_mode_definition_approved=False,
        analysis_rate_approved=False, map_approved=False, certified=False,
    ))
    unit_ballots = {}
    seen_contests = set()
    vector_checks = 0
    for pair_ordinal in range(26):
        table_ordinal = 1 + pair_ordinal * 2
        summary, detail = tables[table_ordinal:table_ordinal + 2]
        contest = summary[0][0]
        if contest in seen_contests or not contest:
            raise ValueError("Repeated or missing native contest")
        seen_contests.add(contest)
        if (len(summary[0]) != 4 or any(len(row) != 4 for row in summary)
                or detail[0][0] != "" or detail[-1][:2] != ["", "Total"]
                or len(detail[0]) != len(summary) + 1
                or any(len(row) != len(detail[0]) for row in detail)):
            raise ValueError("Changed native table shape")
        units = [row[1] for row in detail[1:-1]]
        if len(set(units)) != len(units) or not all(units) or "Total" in units:
            raise ValueError("Missing or repeated native reporting units")
        if pair_ordinal and (summary[0][1:] != ["Vote For 1", "", "Votes"]
                             or detail[0][1] != contest
                             or not set(units).issubset(unit_ballots)):
            raise ValueError("Changed candidate contest scope or reporting-unit identity")
        statement = re.fullmatch(r"Precincts Reporting: (\d+) of (\d+) for (\d+)%", statements[pair_ordinal])
        if not statement or (int(statement[1]), int(statement[2]), int(statement[3])) != (len(units), len(units), 100):
            raise ValueError("Reporting statement does not match the complete native units")
        parsed["reporting"].append(dict(
            source_table_ordinal=table_ordinal, native_contest=contest,
            native_statement=statements[pair_ordinal], native_units=len(units),
            certified=False, all_mode_definition_approved=False,
        ))
        for column in range(2, len(detail[0])):
            values = [integer(row[column]) for row in detail[1:-1]]
            if sum(values) != integer(detail[-1][column]):
                raise ValueError("Native unit vector does not reconcile to its printed total")
            vector_checks += 1
        if pair_ordinal == 0:
            if [integer(cell) for cell in detail[-1][2:]] != [registrations, ballots]:
                raise ValueError("Participation summary and detail disagree")
            for row_ordinal, row in enumerate(detail[1:-1], 1):
                denominator, count = integer(row[2]), integer(row[3])
                if count > denominator:
                    raise ValueError("Unit ballot count exceeds its native registration count")
                unit_ballots[row[1]] = count
                parsed["unit_participation"].append(dict(
                    source_table_ordinal=table_ordinal + 1, source_row_ordinal=row_ordinal,
                    native_unit=row[1], registered_voters=denominator, ballots_cast=count,
                    native_turnout_percentage=None, native_fips=None,
                    analysis_rate_approved=False, map_approved=False,
                ))
            continue
        total_selections = sum(integer(row[3]) for row in summary[1:])
        if total_selections > sum(unit_ballots[unit] for unit in units):
            raise ValueError("Single-selection contest exceeds its scoped reported ballots")
        for candidate_ordinal, row in enumerate(summary[1:]):
            label, _, printed, count_literal = row
            match = re.fullmatch(r"(.+) \(([^()]*)\)", label)
            name, party = match.groups() if match else (label, None)
            if detail[0][candidate_ordinal + 2] != name:
                raise ValueError("Candidate summary and detail headers disagree")
            count = integer(count_literal)
            if count != integer(detail[-1][candidate_ordinal + 2]):
                raise ValueError("Native candidate summary does not match its detail total")
            percentage(printed, count, total_selections)
            common = dict(
                native_contest=contest, native_option=name, native_label=label,
                native_party=party, native_write_in=name.lower().startswith("write-in:"),
            )
            parsed["candidates"].append(dict(
                source_table_ordinal=table_ordinal, source_row_ordinal=candidate_ordinal + 1,
                **common, votes=count, native_percentage=printed,
                contest_reported_selections=total_selections, county_ballots_cast=ballots,
                selections_are_participants=False,
            ))
            if party is not None:
                parsed["parties"].append(dict(
                    **common, votes=count, no_cross_contest_aggregation=True,
                    write_in_party_not_inferred=common["native_write_in"],
                ))
            for row_ordinal, unit in enumerate(detail[1:-1], 1):
                parsed["unit_candidates"].append(dict(
                    source_table_ordinal=table_ordinal + 1, source_row_ordinal=row_ordinal,
                    native_unit=unit[1], **common, votes=integer(unit[candidate_ordinal + 2]),
                ))
    if len(parsed["candidates"]) != 65 or vector_checks != 67:
        raise ValueError("Incomplete county candidate options or native vectors")
    return parsed


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def build(output):
    output = Path(output)
    if output.exists():
        raise ValueError("Refusing to overwrite an existing output")
    source = json.loads((HERE / "source-qualification.json").read_text())
    parsed = review(source)
    output.mkdir(parents=True)
    for name in STATIC:
        shutil.copyfile(HERE / name, output / name)
    for key, filename in FILENAMES.items():
        stream = io.StringIO(newline="")
        rows = parsed[key]
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / filename).write_bytes(stream.getvalue().encode())
    audit = dict(
        row_counts={FILENAMES[key]: len(rows) for key, rows in parsed.items()},
        county_ballots_cast=parsed["participation"][0]["reported_ballots_cast"],
        county_registered_voters=parsed["participation"][0]["reported_registered_voters"],
        native_tables=53, native_summary_detail_pairs=26,
        all_67_native_vectors_reconcile=True, all_66_printed_percentages_reconcile=True,
        unit_zero_registration_and_zero_ballots=sum(
            row["registered_voters"] == row["ballots_cast"] == 0
            for row in parsed["unit_participation"]),
        unit_nonzero_registration_and_zero_ballots=sum(
            row["registered_voters"] > 0 and row["ballots_cast"] == 0
            for row in parsed["unit_participation"]),
        native_update_literal=source["native_update_literal"], source_timezone=None,
        no_candidate_vote_or_received_ballot_substitution=True,
        no_cross_contest_party_aggregation=True, write_in_party_not_inferred=True,
        analysis_rate_approvals=0, map_approvals=0, all_mode_definition_approvals=0,
        scope="Complete native numerical query, not final/certified turnout, demographic "
              "participation, an all-mode definition, Census identity or map approval, "
              "CVAP/VAP/VEP rates, a raw webpage mirror or live explorer promotion.",
    )
    (output / "audit.json").write_bytes(encode(audit))
    manifest = dict(files=[
        dict(path=path.name, bytes=path.stat().st_size,
             sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(output.iterdir()) if path.is_file()
    ], scope="Complete numerical input, tables, methods and executable query/tests; "
             "manifest and ZIP excluded to prevent self-reference.")
    (output / "checksums.json").write_bytes(encode(manifest))
    with zipfile.ZipFile(output / "complete-query.zip", "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path in sorted(output.iterdir()):
            if path.name == "complete-query.zip":
                continue
            entry = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, path.read_bytes())
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    print(json.dumps(build(parser.parse_args().output), indent=2))
