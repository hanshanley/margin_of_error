"""Reproduce the complete reviewed Mifflin numerical query without source templates."""

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


TABLES = (
    "county-participation.csv", "county-candidate-results.csv", "county-literal-party-totals.csv",
    "county-contest-accounting.csv", "native-unit-participation.csv",
    "native-unit-participation-modes.csv", "native-unit-candidate-results.csv",
    "native-unit-literal-party-totals.csv", "native-unit-contest-accounting.csv",
    "native-participation-modes.csv", "native-reporting-statistics.csv", "native-mail-receipts.csv",
    "native-source-pages.csv", "native-derived-contest-sums.csv", "native-derived-rate-checks.csv",
    "native-source-declarations.csv", "native-write-in-breakdowns.csv",
    "native-unit-write-in-availability.csv",
)
MODES = ("TOTAL", "Election Day", "Mail Votes", "Provisional Votes")
REVIEW_SHA256 = "20d4f560e7e3e07fad789bf69c07b0474d1a26249b28030584594f71729d7f17"
SOURCES = {
    "mifflin-parent.html": "866a571d9042a8f081056a526064f26757834de565f5c1c616e693cc108ef806",
    "mifflin-summary.pdf": "682d68966949e5386cf45cf0c25697de28e7de1b67c30d2dacb2e8b2d4a733e5",
    "mifflin-statement.pdf": "64a47dcd6f3d119a3d481000039126774037a000474deeb3df5f95fab184699c",
}
DECLARATIONS = [
    dict(role="summary", label="Unofficial Summary Results",
         url="https://mifflincountypa.gov/getmedia/bfebf5a8-dde3-45f7-8014-3d4449fdd28f/Election-Results",
         previous_heading="2026 General Election"),
    dict(role="statement", label="Unofficial Precinct Results",
         url="https://mifflincountypa.gov/getmedia/f5ec47b1-c763-4194-a9d3-665a6f73ccf0/All-Precincts-Unofficial-Results",
         previous_heading="2026 General Election"),
]
RECEIPT_LITERAL = "Mifflin County received a total of 2435 mail-in and absentee ballots by 8pm on Primary Election Day, November 3, 2026"
ARCHIVE = "complete-mifflin-county-native-query-01.zip"


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_tables(facts):
    assert facts["county"] == "Mifflin" and facts["year"] == 2026 and facts["maps_approved"] is False
    reviewed = facts["reviewed_input"]
    assert digest(reviewed) == facts["reviewed_input_sha256"] == REVIEW_SHA256
    receipts = facts["source_receipts"]
    assert {row["file"]: row["sha256"] for row in receipts} == SOURCES
    assert all(row["status"] == 200 and row["bytes"] > 0 for row in receipts)
    declared = facts["source_declarations"]
    assert declared == DECLARATIONS and facts["parent_receipt_literal"] == RECEIPT_LITERAL
    for row in declared:
        receipt = next(item for item in receipts if item["file"] == "mifflin-" + row["role"] + ".pdf")
        assert row["url"] == receipt["requested_url"]
    tables = {name: [] for name in TABLES}
    native = reviewed["native"]
    units = {unit["unit"]: unit for unit in reviewed["units"]}
    county = native["summary"][0]["statistics"]
    assert len(units) == 26 and county["ballots"] == [14439, 12017, 2422, 0]
    assert county["registered_voters"] == 0 and county["printed_turnout"] == "0.00%"
    assert county["blank_ballots"] == [6, 6, 0, 0]
    assert sum(unit["statistics"]["registered_voters"] for unit in units.values()) == 0
    for field in ("ballots", "blank_ballots"):
        assert county[field] == [sum(unit["statistics"][field][mode] for unit in units.values()) for mode in range(4)]
    for role, pages in native.items():
        assert len(pages) == (2 if role == "summary" else 52)
        for page in pages:
            meta = dict(source_report=role, source_page=page["physical_page"],
                native_printed_page=f'Page {page["printed_page"]} of {page["printed_total_pages"]}',
                source_status_literal=page["native_status_literal"],
                source_update_literal=page["native_clock_literal"], declared_timezone=page["declared_timezone"])
            assert meta["source_status_literal"] == "UNOFFICIAL RESULTS" and meta["declared_timezone"] == ""
            assert meta["source_update_literal"] == ("11/03/2026 09:28PM" if role == "summary" else "11/03/2026 09:26PM")
            unit = page.get("unit", "Mifflin County")
            tables["native-source-pages.csv"].append(dict(
                source_file="mifflin-" + role + ".pdf", source_sha256=SOURCES["mifflin-" + role + ".pdf"],
                entire_page_token_multisets_match_both_engines=True,
                entire_parsed_page_vectors_match_both_engines=True, all_layout_lines_consumed=True, **meta))
            if "statistics" in page:
                stats = page["statistics"]
                assert stats["registered_voters"] == 0 and stats["printed_turnout"] == "0.00%"
                assert stats["derived_registered_voter_fraction_percent"] is None
                if role == "summary":
                    tables["county-participation.csv"].append(dict(year=2026, state_code="PA", county="Mifflin",
                        native_participation_measure_literal="Ballots Cast - Total", ballots_cast=stats["ballots"][0],
                        registered_voters=0, native_printed_turnout=stats["printed_turnout"],
                        election_day_ballots=stats["ballots"][1], mail_ballots=stats["ballots"][2],
                        provisional_ballots=stats["ballots"][3], blank_ballots=stats["blank_ballots"][0],
                        registered_turnout_pct="", rate_unavailable_reason=stats["rate_unavailable_reason"],
                        reported_precincts=26, total_precincts=26, complete_precincts=0,
                        partially_reported_precincts=26, **meta))
                    for report in page["native_reporting"]:
                        tables["native-reporting-statistics.csv"].append(dict(
                            statistic_literal=report["label"], native_total_numerator=report["total_fraction"][0],
                            native_total_denominator=report["total_fraction"][1],
                            native_election_day_column=report["mode_columns"][0],
                            native_mail_column=report["mode_columns"][1],
                            native_provisional_column=report["mode_columns"][2], **meta))
                else:
                    tables["native-unit-participation.csv"].append(dict(unit_literal=unit,
                        registered_voters=0, ballots_cast=stats["ballots"][0],
                        blank_ballots=stats["blank_ballots"][0], native_printed_turnout=stats["printed_turnout"],
                        registered_turnout_pct="", rate_unavailable_reason=stats["rate_unavailable_reason"], **meta))
                for mode, label in enumerate(MODES):
                    table = "native-participation-modes.csv" if role == "summary" else "native-unit-participation-modes.csv"
                    tables[table].append(dict(unit_literal=unit, counting_mode_literal=label,
                        ballots_cast=stats["ballots"][mode], blank_ballots=stats["blank_ballots"][mode],
                        registered_voters=0 if mode == 0 else "",
                        native_printed_turnout=stats["printed_turnout"] if mode == 0 else "", **meta))
                tables["native-derived-rate-checks.csv"].append(dict(unit_literal=unit,
                    native_ballots_cast=stats["ballots"][0], native_registered_voters=0,
                    native_printed_turnout=stats["printed_turnout"],
                    calculated_rounded_fraction="", derived_rate_usable=False,
                    reason=stats["rate_unavailable_reason"], **meta))
            for contest in page["contests"]:
                prefix = "county-" if role == "summary" else "native-unit-"
                rows = contest["rows"]
                by_label = {row["label"]: row for row in rows}
                choices = [row for row in rows if row["kind"] in ("candidate", "write_in_total")]
                assert by_label["Not Assigned"]["vector"] == by_label["Write-In Totals"]["vector"]
                for row in rows:
                    assert row["vector"][0] == sum(row["vector"][1:])
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
                        elif row["kind"] == "unassigned_write_in":
                            tables["native-write-in-breakdowns.csv"].append(dict(unit_literal=unit,
                                contest_literal=contest["title"], choice_literal=row["label"],
                                counting_mode_literal=label, votes=row["vector"][mode],
                                accounting_role="Explicit Not Assigned breakdown of Write-In Totals; do not add twice.", **meta))
                if role == "statement":
                    tables["native-unit-write-in-availability.csv"].append(dict(unit_literal=unit,
                        contest_literal=contest["title"], native_breakdown_present=True,
                        named_identities_reported=False, unassigned_write_in_votes=by_label["Not Assigned"]["vector"][0],
                        missingness_role="Explicit Not Assigned counts are retained; named identities are not reported.", **meta))
                for mode, label in enumerate(MODES):
                    counted = sum(row["vector"][mode] for row in choices)
                    votes, over, under, electorate = (by_label[name]["vector"][mode]
                        for name in ("Total Votes Cast", "Overvotes", "Undervotes", "Contest Totals"))
                    assert counted == votes and votes + over + under == electorate
                    if role == "statement":
                        assert electorate == units[unit]["statistics"]["ballots"][mode]
                    tables[prefix + "contest-accounting.csv"].append(dict(unit_literal=unit,
                        contest_literal=contest["title"], counting_mode_literal=label,
                        native_total_votes_cast=votes, native_overvotes=over, native_undervotes=under,
                        native_contest_totals=electorate, derived_sum_of_choice_votes=counted,
                        electorate_scope="Native contest electorate, not necessarily all county ballots.", **meta))
    for row in tables["county-candidate-results.csv"]:
        actual = [unit for unit in tables["native-unit-candidate-results.csv"]
                  if all(unit[field] == row[field] for field in
                         ("contest_literal", "literal_party", "choice_literal", "choice_kind", "counting_mode_literal"))]
        assert actual and sum(unit["votes"] for unit in actual) == row["votes"]
    for contest in reviewed["reconciliations"]:
        tables["native-derived-contest-sums.csv"].append(dict(contest_literal=contest["contest"],
            native_units=contest["units"], total=contest["native_contest_electorate"][0],
            election_day=contest["native_contest_electorate"][1], mail=contest["native_contest_electorate"][2],
            provisional=contest["native_contest_electorate"][3],
            all_native_choice_write_in_and_accounting_vectors_match=True))
    tables["native-mail-receipts.csv"].append(dict(native_ballots_received=2435,
        receipt_scope_literal=facts["parent_receipt_literal"],
        native_calendar_and_stage_wording_contradiction_preserved=True,
        counted_mail_ballots=2422, derived_receipts_minus_counted_mail_unexplained=13,
        report_role="Parent receipts, not counted ballots; contradictory Primary wording is not repaired.",
        source_report="parent", source_update_literal="", declared_timezone=""))
    for declaration in declared:
        tables["native-source-declarations.csv"].append(dict(
            source_report=declaration["role"], declared_label_literal=declaration["label"],
            declared_url=declaration["url"], preceding_heading_literal=declaration["previous_heading"]))
    assert all(tables.values()) and len(tables["native-unit-write-in-availability.csv"]) == 104
    return tables


def validate(facts):
    assert facts["tables"] == build_tables(facts)


def render(facts, destination):
    validate(facts)
    destination.mkdir(exist_ok=False)
    for name, rows in facts["tables"].items():
        with (destination / name).open("x", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    with (destination / "source-records.json.gz").open("xb") as target:
        with gzip.GzipFile(fileobj=target, mode="wb", filename="", mtime=0) as compressed:
            compressed.write(json_bytes(facts))
    audit = dict(county="Mifflin", year=2026, table_rows={key: len(rows) for key, rows in facts["tables"].items()},
        native_ballots_cast=14439, native_registered_voters=0, usable_registered_voter_fraction=None,
        native_printed_turnout="0.00%", unusable_zero_denominator_not_zero_participation=True,
        native_election_day_ballots=12017, native_mail_ballots=2422, native_provisional_ballots=0,
        blank_ballots_already_included=6, native_precincts_complete=0, native_precincts_partial=26,
        complete_reviewed_native_units=26, complete_county_contests=5, complete_unit_contests=104,
        county_legislative_contest_electorates=[4409, 10030],
        native_reported_mail_receipts=2435, unexplained_receipt_minus_counted_mail=13,
        parent_primary_wording_contradiction_not_repaired=True, both_native_clocks_preserved=True,
        entire_pages_independently_reviewed_both_engines=54, all_layout_lines_consumed=True,
        explicit_unassigned_write_ins_not_double_counted=True,
        literal_parties_preserved=True, maps_approved=False,
        no_certification_complete_counting_geometry_or_demographic_turnout_claim=True,
        original_documents_and_presentation_templates="Private; not redistributed in this factual query.")
    for name, value in (("audit.json", audit), ("source-receipts.json", facts["source_receipts"])):
        (destination / name).write_bytes(json_bytes(value))
    (destination / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    checksums = {path.name: dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in sorted(destination.iterdir())}
    (destination / "checksums.json").write_bytes(json_bytes(checksums))
    with zipfile.ZipFile(destination / ARCHIVE, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(destination.iterdir()):
            if path.name != ARCHIVE:
                info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())


def self_test(facts):
    cases = (
        ("candidate votes substituted", "county-participation.csv", 0, "ballots_cast", 14324),
        ("zero registrations converted to rate", "county-participation.csv", 0, "registered_turnout_pct", 0),
        ("blank ballots double counted", "county-participation.csv", 0, "ballots_cast", 14445),
        ("receipts substituted as mail", "county-participation.csv", 0, "mail_ballots", 2435),
        ("explicit zero provisional erased", "county-participation.csv", 0, "provisional_ballots", ""),
        ("native zero registrations invented", "county-participation.csv", 0, "registered_voters", 24391),
        ("partial reporting declared complete", "county-participation.csv", 0, "complete_precincts", 26),
        ("clock given invented timezone", "county-participation.csv", 0, "declared_timezone", "America/New_York"),
        ("literal party normalized", "county-candidate-results.csv", 0, "literal_party", "Democratic"),
        ("unit choice changed", "native-unit-candidate-results.csv", 0, "votes", 999),
        ("split electorate replaced by county", "county-contest-accounting.csv", 12, "native_contest_totals", 14439),
        ("native page identity changed", "native-source-pages.csv", 0, "native_printed_page", "Page 99 of 99"),
        ("unassigned count turned into name", "native-write-in-breakdowns.csv", 0, "choice_literal", "Named person"),
        ("contradictory parent stage silently repaired", "native-mail-receipts.csv", 0,
         "native_calendar_and_stage_wording_contradiction_preserved", False),
        ("source clock repaired", "county-participation.csv", 0, "source_update_literal", "11/03/2026 09:26PM"),
        ("unusable rate filled", "native-derived-rate-checks.csv", 0, "calculated_rounded_fraction", "0.00%"),
    )
    for label, table, row, field, value in cases:
        changed = copy.deepcopy(facts)
        changed["tables"][table][row][field] = value
        try:
            validate(changed)
        except AssertionError:
            pass
        else:
            raise AssertionError("Accepted " + label)
    rejected = [case[0] for case in cases]
    for label, field, value in (
        ("native parent stage changed", "parent_receipt_literal", RECEIPT_LITERAL.replace("Primary", "General")),
        ("actual declared source URL replaced", "source_declarations", [
            dict(DECLARATIONS[0], url=DECLARATIONS[0]["url"] + "?different-source=1"), DECLARATIONS[1]]),
    ):
        changed = copy.deepcopy(facts)
        changed[field] = value
        try:
            build_tables(changed)
        except AssertionError:
            rejected.append(label)
        else:
            raise AssertionError("Accepted " + label)
    with tempfile.TemporaryDirectory() as temporary:
        first, second = Path(temporary) / "first", Path(temporary) / "second"
        render(facts, first)
        render(facts, second)
        assert {path.name: path.read_bytes() for path in first.iterdir()} == {
            path.name: path.read_bytes() for path in second.iterdir()}
        with zipfile.ZipFile(first / ARCHIVE) as archive:
            assert set(archive.namelist()) == {path.name for path in first.iterdir() if path.name != ARCHIVE}
            assert all(archive.read(name) == (first / name).read_bytes() for name in archive.namelist())
    return rejected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    facts = json.loads(gzip.decompress(args.snapshot.read_bytes()))
    rejected = self_test(facts)
    if args.output:
        render(facts, args.output)
    print(json.dumps(dict(rejected_cases=rejected, deterministic_full_query_reproduction=True), indent=2))
