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
STATIC = ("source-qualification.json", "methods.json", "review-counties.py", "test_review_counties.py")
HEADERS = (
    "County SOE Website", "Voter Turnout", "Eligible Active Registered Voters",
    "Turnout Percentage", "Precincts Reporting", "Precincts Completed",
    "Vote-by-Mail Ballots Completed", "Early Voting Ballots Completed",
    "Provisional Ballots Completed", "10-day Overseas Vote-by-Mail Completed",
)


def integer(text):
    if not isinstance(text, str) or not re.fullmatch(r"(?:0|[1-9]\d{0,2}(?:,\d{3})*)", text):
        raise ValueError("Invalid native comma-delimited integer")
    return int(text.replace(",", ""))


def review(source):
    if any(source[key] is not False for key in
           ("generic_turnout_approved", "county_fips_join_approved", "map_approved", "certified")):
        raise ValueError("Native qualification cannot grant analysis, geography or certification approval")
    if source["source_as_of"] is not None or source["source_timezone"] is not None:
        raise ValueError("An acquisition clock is not a native source update time")
    if source["headers"] != list(HEADERS) or source["election_date"] != "2026-11-03":
        raise ValueError("Unexpected native election or table columns")
    rows = source["county_rows"]
    catalog = source["native_county_catalog"]
    names = [row[0]["text"] for row in rows]
    codes = [row["native_county_code"] for row in catalog]
    if len(rows) != 67 or len(set(names)) != 67 or len(catalog) != 67 or len(set(codes)) != 67:
        raise ValueError("Incomplete or repeated native county inventory")
    by_name = {row["county_literal"]: row for row in catalog}
    if set(by_name) != set(names) or any(row["native_fips"] is not None for row in catalog):
        raise ValueError("Native county codes are not approved Census FIPS")
    if any(not re.fullmatch("[A-Z]{3}", code) for code in codes):
        raise ValueError("Invalid native county code")
    total = source["statewide_row"]
    if total[0]["text"] != "TOTAL" or "TOTAL" in names:
        raise ValueError("Statewide aggregate must remain distinct from county rows")
    counties = []
    statewide = []
    cells = []
    for ordinal, row in enumerate(rows + [total]):
        if len(row) != 10:
            raise ValueError("Incomplete native reporting row")
        name = row[0]["text"]
        count = integer(row[1]["text"])
        denominator = integer(row[2]["text"])
        if denominator <= 0 or count > denominator:
            raise ValueError("Invalid native participant or registration total")
        for index in (3, 4):
            if not re.fullmatch(r"\d+(?:\.\d{1,2})?%", row[index]["text"]):
                raise ValueError("Invalid native percentage")
        printed = Decimal(row[3]["text"][:-1])
        derived = Decimal(count) * 100 / denominator
        if derived.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) != printed:
            raise ValueError("Native percentage does not reconcile to native counts")
        flags = []
        for cell in row[5:]:
            classes = cell["span_classes"]
            if ordinal < 67:
                if classes not in ([["Y"]], [["N"]]):
                    raise ValueError("County completion status must remain a literal Y/N, not an inferred zero")
                flags.append(classes[0][0])
            else:
                if classes not in ([], [[]]):
                    raise ValueError("Do not invent a statewide completion status")
                flags.append(None)
        if ordinal < 67 and row[0]["hrefs"] != [by_name[name]["declared_county_soe_url"]]:
            raise ValueError("County SOE link does not match the source inventory")
        result = dict(
            native_county=name,
            native_county_code=by_name[name]["native_county_code"] if ordinal < 67 else None,
            reported_participants=count,
            eligible_active_registered_voters=denominator,
            native_turnout_percentage=row[3]["text"],
            independently_derived_registered_fraction_percent=str(derived),
            native_precincts_reporting=row[4]["text"],
            native_precincts_completed=flags[0],
            native_vote_by_mail_completed=flags[1],
            native_early_voting_completed=flags[2],
            native_provisional_completed=flags[3],
            native_10_day_overseas_completed=flags[4],
            source_as_of=None, source_timezone=None,
            native_fips=None, analysis_rate_approved=False, map_approved=False,
        )
        (counties if ordinal < 67 else statewide).append(result)
        for index, cell in enumerate(row):
            cells.append(dict(source_row_ordinal=ordinal, native_county=name,
                column_ordinal=index, column_label=HEADERS[index], literal_text=cell["text"],
                native_span_classes=json.dumps(cell["span_classes"], separators=(",", ":")),
                declared_hrefs=json.dumps(cell["hrefs"], separators=(",", ":"))))
    for field in ("reported_participants", "eligible_active_registered_voters"):
        if sum(row[field] for row in counties) != statewide[0][field]:
            raise ValueError("County totals do not reconcile to the separate statewide total")
    return dict(counties=counties, statewide=statewide, catalog=catalog, cells=cells)


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
    filenames = dict(counties="county-participation.csv", statewide="statewide-participation.csv",
                     catalog="native-county-catalog.csv", cells="source-native-cells.csv")
    for key, filename in filenames.items():
        rows = parsed[key]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / filename).write_bytes(stream.getvalue().encode())
    counties = parsed["counties"]
    audit = dict(
        row_counts={filenames[key]: len(rows) for key, rows in parsed.items()},
        reported_participants=sum(row["reported_participants"] for row in counties),
        eligible_active_registered_voters=sum(row["eligible_active_registered_voters"] for row in counties),
        county_sums_equal_separate_statewide_totals=True,
        all_68_printed_percentages_reconcile=True,
        native_completion_status_counts={
            field: {flag: sum(row[field] == flag for row in counties) for flag in ("Y", "N")}
            for field in counties[0] if field.endswith("_completed")
        },
        source_as_of_missing=True, source_timezone_missing=True,
        native_codes_not_census_fips=True,
        unfinished_ballot_flags_preserved=True,
        no_statewide_aggregate_added_to_counties=True,
        no_candidate_vote_or_received_ballot_substitution=True,
        analysis_rate_approvals=0, map_approvals=0,
        scope="Complete portable numerical query over the official 67-county reporting table and "
              "separate statewide aggregate, with every native table cell and completion flag. "
              "Not certified turnout, a raw HTML mirror, candidate/party results, demographic "
              "participation, a geographic join, CVAP/VAP/VEP rates or a live explorer update.",
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
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.output), indent=2))
