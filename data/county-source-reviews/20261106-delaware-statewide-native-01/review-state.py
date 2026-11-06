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
NATIVE = ("native-turnout.json", "native-state-candidate-results.json", "native-county-candidate-results.json")
STATIC = ("source-qualification.json", "methods.json", "review-state.py", "test_review_state.py", *NATIVE)
TURNOUT_FIELDS = {"Election Id", "Election Name", "Results Type", "Representative District",
                  "Ballots Cast", "Reg Voters", "Percentage"}
KEY_FIELDS = ("Contest Sorting Order", "Contest Title", "Candidate Name", "Party Name", "Pos")


def integer(value):
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9]\d{0,2}(?:,\d{3})*)", value):
        raise ValueError("Invalid native count")
    return int(value.replace(",", ""))


def review(source, turnout, candidates, county_candidates):
    for key in ("native_turnout_update_clock", "native_turnout_timezone", "native_fips"):
        if source[key] is not None:
            raise ValueError("Missing turnout clocks and native FIPS cannot be invented")
    for key in ("analysis_rate_approved", "maps_approved", "all_mode_complete", "certified"):
        if source[key] is not False:
            raise ValueError("Native query cannot grant rate, mapping or completion approval")
    if source["election_id"] != "GE2026" or source["election_date"] != "2026-11-03":
        raise ValueError("Unexpected declared election")
    for rows in (turnout, candidates, county_candidates):
        if any(row["Election Id"] != "GE2026" or row["Election Name"] != "2026 General Election"
               or row["Results Type"] != "UNOFFICIAL RESULTS" for row in rows):
            raise ValueError("Mixed elections or unrecognized native status")
    if len(turnout) != 42 or any(set(row) != TURNOUT_FIELDS for row in turnout):
        raise ValueError("Incomplete or altered native turnout schema")
    identifiers = [row["Representative District"] for row in turnout]
    expected = {f"{index:02}" for index in range(1, 42)} | {"ALL"}
    if len(set(identifiers)) != 42 or set(identifiers) != expected:
        raise ValueError("Missing, repeated or unrecognized representative districts")
    districts, statewide = [], []
    for row in turnout:
        count, denominator = integer(row["Ballots Cast"]), integer(row["Reg Voters"])
        if denominator <= 0 or count > denominator:
            raise ValueError("Invalid native registration fraction")
        percentage = Decimal(count) * 100 / denominator
        if percentage.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) != Decimal(str(row["Percentage"])):
            raise ValueError("Native printed percentage does not reconcile")
        aggregate = row["Representative District"] == "ALL"
        normalized = dict(
            geography_level="statewide" if aggregate else "legislative_district",
            native_representative_district=row["Representative District"],
            ballots_cast=count, registered_voters=denominator,
            native_printed_percent=str(row["Percentage"]),
            independently_derived_registered_fraction_percent=str(percentage),
            native_measure_literal="Ballots Cast", native_denominator_literal="Reg Voters",
            source_status_literal=row["Results Type"],
            native_update_clock=None, declared_timezone=None, native_fips=None,
            maps_approved=False, analysis_rate_approved=False, all_mode_complete=False, certified=False,
        )
        (statewide if aggregate else districts).append(normalized)
    if any(sum(row[field] for row in districts) != statewide[0][field]
           for field in ("ballots_cast", "registered_voters")):
        raise ValueError("District totals do not reconcile to the separate statewide row")
    if len(candidates) != 124 or len(county_candidates) != 124:
        raise ValueError("Incomplete separate candidate/option inventories")
    by_key = {}
    for row in candidates:
        key = tuple(row[field] for field in KEY_FIELDS)
        if key in by_key:
            raise ValueError("Repeated state candidate/option identity")
        by_key[key] = row
        if row["Election Date"] != "2026-11-03" or row["ReportTime"] != "2026-11-04T03:03:18.364-05:00":
            raise ValueError("Unexpected candidate source date or clock")
        if sum(integer(row[field]) for field in ("Machine Votes", "Absentee Votes", "Early Voting Votes")) != integer(row["Total Votes"]):
            raise ValueError("Candidate mode selections do not reconcile")
        total, reported = integer(row["Total Precincts"]), integer(row["Precincts Reported"])
        if total <= 0 or reported > total:
            raise ValueError("Invalid literal per-contest candidate-report unit inventory")
    matched = set()
    for row in county_candidates:
        key = tuple(row[field] for field in KEY_FIELDS)
        if key not in by_key or key in matched:
            raise ValueError("Missing or repeated separate county candidate/option identity")
        matched.add(key)
        if (integer(row["Wilmington"]) + integer(row["Rest of New Castle"]) != integer(row["New Castle"])
                or sum(integer(row[field]) for field in ("New Castle", "Kent", "Sussex")) != integer(row["State"])
                or integer(row["State"]) != integer(by_key[key]["Total Votes"])
                or row["Percentage"] != by_key[key]["Percentage"]):
            raise ValueError("Separate county/city/state candidate vectors do not reconcile")
    parties = [
        dict(election_id=row["Election Id"], contest=row["Contest Title"], candidate=row["Candidate Name"],
             native_candidate_id=row["Candidate Id"], native_party_id=row["Party Id"],
             literal_party_name_json=json.dumps(row["Party Name"], ensure_ascii=True),
             source_row_ordinal=ordinal)
        for ordinal, row in enumerate(candidates)
    ]
    return dict(districts=districts, statewide=statewide, candidates=candidates,
                county_candidates=county_candidates, parties=parties)


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def build(output):
    output = Path(output)
    if output.exists():
        raise ValueError("Refusing to overwrite an existing output")
    source = json.loads((HERE / "source-qualification.json").read_text())
    native = [json.loads((HERE / name).read_bytes()) for name in NATIVE]
    for name in NATIVE:
        original = (HERE / name).read_bytes()
        receipt = source["native_inputs"][name]
        if len(original) != receipt["bytes"] or hashlib.sha256(original).hexdigest() != receipt["sha256"]:
            raise ValueError("Complete native input changed")
    parsed = review(source, *native)
    output.mkdir(parents=True)
    for name in STATIC:
        shutil.copyfile(HERE / name, output / name)
    filenames = dict(districts="district-participation.csv", statewide="statewide-participation.csv",
                     candidates="state-candidate-results.csv", county_candidates="county-candidate-vectors.csv",
                     parties="literal-party-labels.csv")
    for key, filename in filenames.items():
        rows = parsed[key]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / filename).write_bytes(stream.getvalue().encode())
    statewide = parsed["statewide"][0]
    senate = [row for row in parsed["candidates"] if row["Contest Title"] == "U.S. Senator"]
    audit = dict(
        row_counts={filenames[key]: len(rows) for key, rows in parsed.items()},
        native_records={name: len(rows) for name, rows in zip(NATIVE, native)},
        native_ballots_cast=statewide["ballots_cast"], native_registered_voters=statewide["registered_voters"],
        native_printed_percent=statewide["native_printed_percent"],
        all_41_district_ballot_and_registration_sums_equal_separate_statewide_totals=True,
        all_42_native_printed_registered_fractions_reconcile=True,
        all_124_state_candidate_mode_vectors_reconcile=True,
        all_124_county_city_and_state_candidate_vectors_reconcile=True,
        separate_senate_candidate_selections=sum(integer(row["Total Votes"]) for row in senate),
        native_turnout_update_clock_missing=True, native_turnout_timezone_missing=True,
        candidate_clock_not_substituted_for_turnout=True,
        no_turnout_apportioned_to_counties=True, no_statewide_total_added_to_districts=True,
        analysis_rate_approvals=0, map_approvals=0, all_mode_completion_approvals=0,
        scope="Complete native state/district participation and separate state/county candidate/party query. "
              "The turnout feed has no native update clock or timezone; the offset-bearing candidate clock "
              "remains separate. Reported Ballots Cast and same-report Reg Voters are not proof of finished "
              "all-mode counting, certification, final unique voters, population or demographic turnout. "
              "District participation is not apportioned to counties. No live explorer update.",
    )
    (output / "audit.json").write_bytes(encode(audit))
    (output / "checksums.json").write_bytes(encode(dict(files=[
        dict(path=path.name, bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(output.iterdir()) if path.is_file()
    ], scope="Complete inputs, tables, methods and executable query/tests; manifest and ZIP excluded to prevent self-reference.")))
    with zipfile.ZipFile(output / "complete-query.zip", "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(output.iterdir()):
            if path.name == "complete-query.zip":
                continue
            info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reproduce complete native Delaware state/district participation and separate candidate/party queries offline.")
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(build(parser.parse_args().output), indent=2))
