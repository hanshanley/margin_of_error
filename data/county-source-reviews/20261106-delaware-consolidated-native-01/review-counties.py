import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import zipfile


HERE = Path(__file__).resolve().parent
STATIC = ("source-qualification.json", "methods.json", "review-counties.py", "test_review_counties.py")
HEADERS = ("Voting Method", "Kent County", "New Castle County", "Sussex County", "Totals")
METHODS = ("Absentee", "Early Voting", "Polling Place", "Grand Totals")


def integer(text):
    if not isinstance(text, str) or not re.fullmatch(r"(?:0|[1-9]\d{0,2}(?:,\d{3})*)", text):
        raise ValueError("Invalid literal native count")
    return int(text.replace(",", ""))


def review(source):
    if source["election_date"] != "2026-11-03" or source["election_heading"] != "2026 General Election Voter Counts by Voting Method":
        raise ValueError("Unexpected election or native participation heading")
    if source["native_update_literal"] != "Tuesday, November 3, 2026 4:01 PM":
        raise ValueError("Do not replace the native afternoon Election Day clock")
    for key in ("source_timezone", "registration_denominators", "native_fips"):
        if source[key] is not None:
            raise ValueError("Missing timezone, registrations and native FIPS must stay missing")
    for key in ("all_mode_completion_approved", "analysis_rate_approved", "map_approved", "certified"):
        if source[key] is not False:
            raise ValueError("Reported methods do not establish finished counting or analysis approval")
    if source["headers"] != list(HEADERS):
        raise ValueError("Missing, repeated or altered county and statewide columns")
    table = source["rows"]
    if len(table) != 4 or any(len(row) != 5 for row in table):
        raise ValueError("Incomplete native method inventory")
    if [row[0] for row in table] != list(METHODS):
        raise ValueError("Unexpected, missing or repeated native method")
    numbers = [[integer(value) for value in row[1:]] for row in table]
    if any(sum(row[:3]) != row[3] for row in numbers):
        raise ValueError("Counties do not reconcile to the separate statewide method total")
    if any(sum(row[column] for row in numbers[:3]) != numbers[3][column] for column in range(4)):
        raise ValueError("Method counts do not reconcile to the literal grand total")
    counties, statewide, modes, cells = [], [], [], []
    for column, county in enumerate(HEADERS[1:]):
        aggregate = county == "Totals"
        row = dict(
            geography_level="statewide" if aggregate else "county",
            native_geography_literal=county,
            native_measure_literal="Grand Totals",
            reported_voter_count=numbers[3][column],
            source_participation_heading=source["election_heading"],
            native_update_literal=source["native_update_literal"],
            source_timezone=None,
            native_registered_voters=None,
            native_fips=None,
            partial_election_day_snapshot=True,
            all_mode_completion_approved=False,
            analysis_rate_approved=False,
            map_approved=False,
            certified=False,
        )
        (statewide if aggregate else counties).append(row)
        for index, method in enumerate(METHODS):
            modes.append(dict(geography_level=row["geography_level"], native_geography_literal=county,
                              native_method_literal=method, native_count_literal=table[index][column + 1],
                              reported_voter_count=numbers[index][column],
                              is_aggregate=method == "Grand Totals"))
    for ordinal, row in enumerate([list(HEADERS), *table]):
        for column, value in enumerate(row):
            cells.append(dict(source_row_ordinal=ordinal, column_ordinal=column,
                              native_column_literal=HEADERS[column], native_cell_literal=value))
    return dict(counties=counties, statewide=statewide, modes=modes, cells=cells)


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def build(output):
    output = Path(output)
    if output.exists():
        raise ValueError("Refusing to overwrite an existing output")
    parsed = review(json.loads((HERE / "source-qualification.json").read_text()))
    output.mkdir(parents=True)
    for name in STATIC:
        shutil.copyfile(HERE / name, output / name)
    filenames = dict(counties="county-participation.csv", statewide="statewide-participation.csv",
                     modes="native-method-counts.csv", cells="source-native-cells.csv")
    for key, filename in filenames.items():
        rows = parsed[key]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / filename).write_bytes(stream.getvalue().encode())
    audit = dict(
        row_counts={filenames[key]: len(rows) for key, rows in parsed.items()},
        source_counties=3,
        reported_voter_count=sum(row["reported_voter_count"] for row in parsed["counties"]),
        native_update_literal="Tuesday, November 3, 2026 4:01 PM",
        source_timezone_missing=True,
        registration_denominators_missing=True,
        native_fips_missing=True,
        all_four_county_sums_equal_separate_statewide_totals=True,
        all_four_method_sums_equal_native_grand_totals=True,
        statewide_and_method_aggregates_not_added_twice=True,
        candidate_votes_not_used=True,
        analysis_rate_approvals=0,
        map_approvals=0,
        all_mode_completion_approvals=0,
        scope="Complete numerical query over the official three-county voter-count-by-method table, "
              "including its separate statewide total and all 25 native header/data cells. "
              "An afternoon Election Day snapshot, not finished counting, certified turnout, "
              "same-report registered fractions, population or demographic turnout, a map join, "
              "candidate/party results, or a live explorer update.",
    )
    (output / "audit.json").write_bytes(encode(audit))
    manifest = dict(files=[
        dict(path=path.name, bytes=path.stat().st_size,
             sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(output.iterdir()) if path.is_file()
    ], scope="Complete numerical input, tables, methods and executable query/tests; manifest and ZIP excluded to prevent self-reference.")
    (output / "checksums.json").write_bytes(encode(manifest))
    with zipfile.ZipFile(output / "complete-query.zip", "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path in sorted(output.iterdir()):
            if path.name == "complete-query.zip":
                continue
            info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reproduce the complete qualified Delaware voter-count snapshot offline.")
    parser.add_argument("--output", required=True, type=Path)
    print(json.dumps(build(parser.parse_args().output), indent=2))
