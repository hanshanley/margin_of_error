"""Reproduce the complete reviewed Potter county factual query offline."""

import argparse
import copy
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import zipfile


REVIEW_SHA256 = "7acdc5a89168f2388ef94ddbd1d8275346ab434fec7726d3535a4ffce2445b8f"
SOURCES = {
    "potter-parent.html": "befa4c5f333169feb2913b7d4f882fd51c1bfc6af09c04a14b3b8cc0d1357e4a",
    "potter-summary.pdf": "da311d4bf39feb077e833e40e06b2275bea8e34f12893fec6c5fd3eb1cdce0bd",
    "potter-statement.pdf": "02d73d608299fd9b17d2c7603b4cb56a0df35d565e2808cc7ea83e744cf7eda1",
}
DECLARATIONS = [
    dict(role="summary", file="potter-summary.pdf", label="Potter County 2026 UNOFFICIAL Summary Results",
         url="https://www.pottercountypa.gov/Documents/Departments/Voter Registration and Elections/2026/Results/Summary_Results6_11032026.pdf?t=202611041445440"),
    dict(role="statement", file="potter-statement.pdf", label="Potter County 2026 UNOFFICIAL Precinct Results",
         url="https://www.pottercountypa.gov/Documents/Departments/Voter Registration and Elections/2026/Results/Precinct_Summary_Results6_11032026.pdf?t=202611041446150"),
]
TABLES = (
    "county-participation.csv", "county-candidate-results.csv", "county-literal-party-totals.csv",
    "county-contest-accounting.csv", "native-unit-participation.csv",
    "native-unit-participation-modes.csv", "native-unit-candidate-results.csv",
    "native-unit-literal-party-totals.csv", "native-unit-contest-accounting.csv",
    "native-participation-modes.csv", "native-reporting-statistics.csv", "native-mail-receipts.csv",
    "native-source-pages.csv", "native-derived-contest-sums.csv", "native-derived-rate-checks.csv",
    "native-source-declarations.csv", "native-named-write-ins.csv",
    "native-unit-named-write-in-availability.csv",
)
MODES = ("TOTAL", "Election Day", "Mail", "Provision al")
ARCHIVE = "complete-potter-county-native-query-01.zip"


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_tables(facts):
    reviewed = facts["reviewed_input"]
    assert digest(reviewed) == REVIEW_SHA256
    assert facts["county"] == "Potter" and facts["year"] == 2026 and facts["maps_approved"] is False
    assert facts["source_declarations"] == DECLARATIONS
    receipts = reviewed["source_receipts"]
    assert {row["file"]: row["sha256"] for row in receipts} == SOURCES
    assert all(row["status"] == 200 and row["bytes"] > 0 for row in receipts)
    tables = {name: [] for name in TABLES}
    native = reviewed["native"]
    county = native["summary"][0]["statistics"]
    units = native["statement"]
    assert len(units) == 32 and len({row["unit"] for row in units}) == 32
    assert sum(unit["statistics"]["registered_voters"] for unit in units) == county["registered_voters"]
    for field in ("ballots", "blank_ballots"):
        assert [sum(unit["statistics"][field][mode] for unit in units) for mode in range(4)] == county[field]
    for role, pages in native.items():
        assert len(pages) == (3 if role == "summary" else 32)
        for page in pages:
            meta = dict(source_report=role, source_page=page["physical_page"],
                native_printed_page=f'{page["printed_page"]} of {page["printed_total_pages"]}',
                source_status_literal=page["native_status_literal"],
                source_update_literal=page["native_clock_literal"], declared_timezone=page["declared_timezone"])
            assert meta["source_status_literal"] == "UNOFFICIAL RESULTS" and meta["declared_timezone"] == ""
            tables["native-source-pages.csv"].append(dict(
                source_file="potter-" + role + ".pdf", source_sha256=SOURCES["potter-" + role + ".pdf"],
                text_page_nonempty=True, entire_page_tokens_match_both_engines=True,
                entire_parsed_page_vectors_match_both_engines=True, **meta))
            unit = page.get("unit", "Potter County")
            if "statistics" in page:
                stats = page["statistics"]
                if role == "summary":
                    tables["county-participation.csv"].append(dict(year=2026, state_code="PA", county="Potter",
                        native_participation_measure_literal="Ballots Cast - Total", ballots_cast=stats["ballots"][0],
                        registered_voters=stats["registered_voters"], native_printed_turnout=stats["printed_turnout"],
                        election_day_ballots=stats["ballots"][1], mail_ballots=stats["ballots"][2],
                        provisional_ballots=stats["ballots"][3], blank_ballots=stats["blank_ballots"][0],
                        reported_precincts=32, total_precincts=32, complete_precincts=0,
                        partially_reported_precincts=32, **meta))
                    for report in page["native_reporting"]:
                        tables["native-reporting-statistics.csv"].append(dict(
                            statistic_literal=report["label"], native_total_numerator=report["total_fraction"][0],
                            native_total_denominator=report["total_fraction"][1],
                            native_election_day_column=report["mode_columns"][0],
                            native_mail_column=report["mode_columns"][1],
                            native_provisional_column=report["mode_columns"][2], **meta))
                else:
                    tables["native-unit-participation.csv"].append(dict(unit_literal=unit,
                        registered_voters=stats["registered_voters"], ballots_cast=stats["ballots"][0],
                        blank_ballots=stats["blank_ballots"][0], native_printed_turnout=stats["printed_turnout"], **meta))
                for mode, label in enumerate(MODES):
                    table = "native-participation-modes.csv" if role == "summary" else "native-unit-participation-modes.csv"
                    tables[table].append(dict(unit_literal=unit, counting_mode_literal=label,
                        ballots_cast=stats["ballots"][mode], blank_ballots=stats["blank_ballots"][mode],
                        registered_voters=stats["registered_voters"] if mode == 0 else "",
                        native_printed_turnout=stats["printed_turnout"] if mode == 0 else "", **meta))
                tables["native-derived-rate-checks.csv"].append(dict(unit_literal=unit,
                    native_ballots_cast=stats["ballots"][0], native_registered_voters=stats["registered_voters"],
                    native_printed_turnout=stats["printed_turnout"],
                    calculated_rounded_fraction=stats["derived_registered_voter_fraction_percent"] + "%",
                    native_printed_matches_calculated=stats["printed_fraction_matches_two_decimal_derivation"], **meta))
            for contest in page["contests"]:
                prefix = "county-" if role == "summary" else "native-unit-"
                rows = contest["rows"]
                by_label = {row["label"]: row for row in rows}
                choices = [row for row in rows if row["kind"] in ("candidate", "write_in_total")]
                if role == "summary":
                    breakdown = [row for row in rows if row["kind"] in ("named_write_in", "unassigned_write_in")]
                    assert [sum(row["vector"][mode] for row in breakdown) for mode in range(4)] == by_label["Write-In Totals"]["vector"]
                for row in rows:
                    for mode, label in enumerate(MODES):
                        if row["kind"] in ("candidate", "write_in_total"):
                            party, choice = row["label"].split(" ", 1) if row["kind"] == "candidate" else ("", row["label"])
                            record = dict(unit_literal=unit, contest_literal=contest["title"],
                                literal_party=party, choice_literal=choice, choice_kind=row["kind"],
                                counting_mode_literal=label, votes=row["vector"][mode], **meta)
                            tables[prefix + "candidate-results.csv"].append(record)
                            if party:
                                tables[prefix + "literal-party-totals.csv"].append(dict(unit_literal=unit,
                                    contest_literal=contest["title"], literal_party=party,
                                    counting_mode_literal=label, candidate_votes=row["vector"][mode], **meta))
                        elif row["kind"] in ("named_write_in", "unassigned_write_in"):
                            tables["native-named-write-ins.csv"].append(dict(unit_literal=unit,
                                contest_literal=contest["title"], choice_literal=row["label"], choice_kind=row["kind"],
                                counting_mode_literal=label, votes=row["vector"][mode],
                                accounting_role="Breakdown of Write-In Totals; do not add twice.", **meta))
                if role == "statement":
                    assert not any(row["kind"] in ("named_write_in", "unassigned_write_in") for row in rows)
                    tables["native-unit-named-write-in-availability.csv"].append(dict(
                        unit_literal=unit, contest_literal=contest["title"], named_breakdown_reported=False,
                        native_write_in_total=by_label["Write-In Totals"]["vector"][0],
                        missingness_role="Named unit write-in identities are not reported, not zero; county names are not allocated.", **meta))
                for mode, label in enumerate(MODES):
                    summed = sum(row["vector"][mode] for row in choices)
                    participation = county["ballots"][mode] if role == "summary" else page["statistics"]["ballots"][mode]
                    over, under = (by_label[name]["vector"][mode] for name in ("Overvotes", "Undervotes"))
                    assert summed + over + under == participation
                    for field, expected in (("Total Votes Cast", summed), ("Contest Totals", participation)):
                        if field in by_label:
                            assert by_label[field]["vector"][mode] == expected
                    tables[prefix + "contest-accounting.csv"].append(dict(unit_literal=unit,
                        contest_literal=contest["title"], counting_mode_literal=label,
                        native_total_votes_cast=by_label["Total Votes Cast"]["vector"][mode] if "Total Votes Cast" in by_label else "",
                        native_contest_totals=by_label["Contest Totals"]["vector"][mode] if "Contest Totals" in by_label else "",
                        native_overvotes=over, native_undervotes=under, native_participation_header=participation,
                        derived_sum_of_choice_votes=summed, derived_participation_minus_choices=participation-summed, **meta))
    for candidate in tables["county-candidate-results.csv"]:
        identities = ("contest_literal", "literal_party", "choice_literal", "counting_mode_literal")
        observed = [row for row in tables["native-unit-candidate-results.csv"]
                    if all(row[field] == candidate[field] for field in identities)]
        assert len(observed) == 32 and sum(row["votes"] for row in observed) == candidate["votes"]
    for county_row in tables["county-contest-accounting.csv"]:
        unit_rows = [row for row in tables["native-unit-contest-accounting.csv"]
                     if (row["contest_literal"], row["counting_mode_literal"]) ==
                     (county_row["contest_literal"], county_row["counting_mode_literal"])]
        assert len(unit_rows) == 32
        derived = {field: sum(row[field] for row in unit_rows) for field in
                   ("native_overvotes", "native_undervotes", "derived_sum_of_choice_votes", "native_participation_header")}
        assert all(county_row[field] == value for field, value in derived.items())
        tables["native-derived-contest-sums.csv"].append(dict(
            contest_literal=county_row["contest_literal"], counting_mode_literal=county_row["counting_mode_literal"],
            unit_rows=32, **derived, matches_native_county_accounting=True,
            calculation_role="Derived sum of observed native unit cells; absent unit Total Votes Cast/Contest Totals stay absent."))
    tables["native-mail-receipts.csv"].append(dict(county="Potter",
        source_file="potter-parent.html", source_sha256=SOURCES["potter-parent.html"],
        election_literal="November, 2026, General Election", cutoff_literal="8pm",
        declared_timezone="", returned_mail_absentee_ballots=reviewed["separate_parent_receipts"],
        separately_counted_mail_ballots=county["ballots"][2],
        derived_receipts_minus_counted_mail=reviewed["returned_minus_counted_mail"],
        accounting_role="Separate returned receipts; difference16 is unexplained, not added to counted ballots."))
    tables["native-source-declarations.csv"] = copy.deepcopy(DECLARATIONS)
    assert all(tables.values())
    return tables


def validate(facts):
    assert set(facts) == {"county", "year", "maps_approved", "reviewed_input", "source_declarations", "tables"}
    assert facts["tables"] == build_tables(facts)


def rejection_tests(facts):
    cases = []
    def reject(name, change):
        broken = copy.deepcopy(facts)
        change(broken)
        try:
            validate(broken)
        except (AssertionError, KeyError, TypeError, ValueError):
            cases.append(name)
        else:
            raise AssertionError("Accepted invalid input: " + name)
    def stats(value):
        return value["reviewed_input"]["native"]["summary"][0]["statistics"]
    reject("candidate total is not ballots", lambda value: stats(value)["ballots"].__setitem__(0, 6221))
    reject("mail receipts are not counted mail", lambda value: stats(value)["ballots"].__setitem__(2, 871))
    reject("blank ballots already included", lambda value: stats(value)["ballots"].__setitem__(0, 6246))
    reject("explicit zero provisional is not missing", lambda value: value["tables"]["county-participation.csv"][0].__setitem__("provisional_ballots", ""))
    reject("no invented timezone", lambda value: value["reviewed_input"]["native"]["summary"][0].__setitem__("declared_timezone", "Eastern"))
    reject("unofficial status retained", lambda value: value["reviewed_input"]["native"]["summary"][0].__setitem__("native_status_literal", "OFFICIAL RESULTS"))
    reject("zero complete is not32 complete", lambda value: value["reviewed_input"]["native"]["summary"][0]["native_reporting"][1]["total_fraction"].__setitem__(0, 32))
    reject("separate source clocks", lambda value: value["reviewed_input"]["native"]["statement"][0].__setitem__("native_clock_literal", "11/04/2026 2:44 PM"))
    reject("physical participation page preserved", lambda value: value["tables"]["county-participation.csv"][0].__setitem__("source_page", 2))
    reject("native unit total-votes absence not zero", lambda value: value["tables"]["native-unit-contest-accounting.csv"][0].__setitem__("native_total_votes_cast", 0))
    reject("named unit write-ins not allocated", lambda value: value["tables"]["native-unit-named-write-in-availability.csv"][0].__setitem__("named_breakdown_reported", True))
    reject("literal party not standardized", lambda value: value["tables"]["county-candidate-results.csv"][0].__setitem__("literal_party", "Democratic"))
    reject("source declaration identity", lambda value: value["source_declarations"][0].__setitem__("label", "Official Results"))
    reject("actual source bytes", lambda value: value["reviewed_input"]["source_receipts"][0].__setitem__("sha256", "0"*64))
    reject("map approval not inferred", lambda value: value.__setitem__("maps_approved", True))
    reject("whole query not subset", lambda value: value["tables"]["native-unit-participation.csv"].pop())
    def swap(value):
        a, b = [unit["contests"][0]["rows"][0] for unit in value["reviewed_input"]["native"]["statement"][:2]]
        assert a["vector"] != b["vector"]
        a["vector"], b["vector"] = b["vector"], a["vector"]
    reject("same-candidate same-contest cross-unit swap", swap)
    reject("native contradictory reporting columns preserved", lambda value: value["reviewed_input"]["native"]["summary"][0]["native_reporting"][1]["mode_columns"].__setitem__(0, 0))
    return cases


def render(facts, destination):
    validate(facts)
    destination.mkdir(exist_ok=False)
    for name, rows in facts["tables"].items():
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (destination/name).write_bytes(buffer.getvalue().encode())
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0) as zipped:
        zipped.write(json_bytes(facts))
    (destination/"source-records.json.gz").write_bytes(buffer.getvalue())
    (destination/"source-receipts.json").write_bytes(json_bytes(facts["reviewed_input"]["source_receipts"]))
    (destination/"audit.json").write_bytes(json_bytes(dict(
        county="Potter", year=2026, maps_approved=False, native_ballots=6244,
        native_registrations=11041, native_counting_modes=[5389,855,0],
        summary_pages=3, statement_pages=32, native_units=32, native_unit_contests=96,
        entire_pages_dual_engine_verified=35, source_originals_private=True,
        summary_clock_literal="11/04/2026 2:44 PM", statement_clock_literal="11/04/2026 2:45 PM",
        declared_timezone="", separate_returned_mail_absentee_receipts=871,
        derived_unexplained_receipt_difference=16, all_units_partial=True, complete_units=0,
        named_unit_write_in_breakdowns_reported=False,
        full_table_rows={name:len(rows) for name,rows in facts["tables"].items()},
        source_rejection_cases=rejection_tests(facts),
        scope="Complete factual query; original HTML/PDFs and templates stay private. County named write-ins are breakdowns, not additional votes or unit assignments. No source FIPS, new geometry, demographic/party turnout, statewide completion or certification.")))
    (destination/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    checksums = [dict(file=path.name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in sorted(destination.iterdir())]
    (destination/"checksums.json").write_bytes(json_bytes(checksums))
    with zipfile.ZipFile(destination/ARCHIVE, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(destination.iterdir()):
            if path.name == ARCHIVE:
                continue
            info = zipfile.ZipInfo(path.name, date_time=(1980,1,1,0,0,0))
            info.create_system=3
            info.external_attr=0o100644<<16
            info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.verify:
        assert not args.source and not args.output
        facts=json.loads(gzip.decompress((args.verify/"source-records.json.gz").read_bytes()))
    else:
        assert args.source and args.output
        facts=json.loads(args.source.read_text())
    validate(facts)
    if args.self_test:
        print(len(rejection_tests(facts)), "focused rejection cases pass.")
    if args.verify:
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/"reproduced"
            render(facts, output)
            assert {path.name for path in output.iterdir()} == {path.name for path in args.verify.iterdir()}
            for path in output.iterdir():
                assert path.read_bytes() == (args.verify/path.name).read_bytes(), path.name
        print("Every complete table, factual input, proof, reviewer and deterministic ZIP reproduces byte-identically offline.")
    else:
        render(facts, args.output)
        print("Rendered",len(list(args.output.iterdir())),"files and",len(TABLES),"complete CSV tables.")


if __name__ == "__main__":
    main()
