"""Reproduce the complete Cameron county summary and separate Act88 factual query."""

import argparse
import copy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile


TABLES = {
    "county-participation.csv": 1,
    "county-candidate-results.csv": 30,
    "county-literal-party-totals.csv": 21,
    "native-contest-accounting.csv": 9,
    "native-write-in-children.csv": 9,
    "native-participation-modes.csv": 3,
    "native-reporting-statistics.csv": 4,
    "native-mail-receipts.csv": 11,
    "native-source-pages.csv": 4,
}
ARCHIVE = "complete-cameron-2026-county-query-01.zip"
MODES = ("Total", "Election Day", "Mail")
CLOCK = "11/03/2026 9:13 PM"
SUMMARY_SHA = "0e5c96ca5341fdcb2baf946ff8b1ab6a08e8bffee75ca3a7515e848055c7425b"
ACT88_SHA = "970e8e8a01177943206ae8b808dc59ae5b545adfb5ef39f70ae9390c908d5840"
CONTESTS = (
    ("GOVERNOR AND LIEUTENANT GOVERNOR", 2,
     (("DEM", "SHAPIRO / DAVIS", (536, 357, 179)),
      ("REP", "GARRITY / RICHEY", (1043, 909, 134)),
      ("LIB", "KRAWCHUK / THOMAS", (31, 27, 4))),
     (0, 0, 0), (1610, 1293, 317), (1, 0, 1), (13, 12, 1)),
    ("REPRESENTATIVE IN CONGRESS", 2,
     (("DEM", "RAY BILGER", (436, 289, 147)),
      ("REP", "GLENN GT THOMPSON", (1180, 1008, 172))),
     (1, 1, 0), (1617, 1298, 319), (0, 0, 0), (7, 7, 0)),
    ("REPRESENTATIVE IN THE GENERAL ASSEMBLY", 3,
     (("DEM", "ZACHARY WARE", (375, 253, 122)),
      ("REP", "MARTIN T CAUSER", (1234, 1042, 192))),
     (2, 1, 1), (1611, 1296, 315), (0, 0, 0), (13, 9, 4)),
)
MAIL_UNITS = (
    ("01", "DRIFTWOOD BOROUGH", 7, 7, 7, 7, 7),
    ("10", "EAST SHIPPEN TOWNSHIP", 65, 65, 65, 61, 59),
    ("02", "EAST WARD - BOROUGH OF EMPORIUM", 26, 26, 26, 24, 24),
    ("05", "GIBSON TOWNSHIP", 13, 13, 13, 13, 13),
    ("07", "GROVE TOWNSHIP", 11, 11, 11, 11, 11),
    ("08", "LUMBER TOWNSHIP", 26, 26, 26, 25, 25),
    ("03", "MIDDLE WARD - BOROUGH OF EMPORIUM", 36, 36, 36, 34, 33),
    ("09", "PORTAGE TOWNSHIP", 5, 5, 5, 5, 5),
    ("11", "WEST SHIPPEN TOWNSHIP", 89, 89, 88, 88, 87),
    ("04", "WEST WARD - BOROUGH OF EMPORIUM", 60, 60, 60, 56, 56),
    ("", "Election Totals:", 338, 338, 337, 324, 320),
)


def validate(facts):
    tables = facts["tables"]
    assert set(tables) == set(TABLES)
    assert all(len(tables[name]) == count for name, count in TABLES.items())
    county = tables["county-participation.csv"][0]
    assert (county["year"], county["state_code"], county["county"]) == (2026, "PA", "Cameron")
    assert county["native_participation_measure_literal"] == "Ballots Cast - Total"
    assert (county["ballots_cast"], county["registered_voters"], county["native_printed_turnout"]) == (1624, 2885, "56.29%")
    assert (county["election_day_ballots"], county["mail_ballots"], county["provisional_ballots"]) == (1305, 319, "")
    assert county["blank_ballots"] == 1
    assert (county["reported_precincts"], county["total_precincts"],
            county["complete_precincts"], county["partially_reported_precincts"]) == (10, 10, 0, 10)
    assert county["source_status_literal"] == "UNOFFICIAL RESULTS"
    assert county["source_update_literal"] == CLOCK and county["declared_timezone"] == ""
    ballots = (1624, 1305, 319)
    for index, row in enumerate(tables["native-participation-modes.csv"]):
        assert row["counting_mode_literal"] == MODES[index]
        assert row["ballots_cast"] == ballots[index] and row["blank_ballots"] == (1, 1, 0)[index]
        assert row["registered_voters"] == (2885 if index == 0 else "")
        assert row["native_printed_turnout"] == ("56.29%" if index == 0 else "")
    expected_reporting = (
        ("Election Day Precincts Reporting", 10, 10, 0),
        ("Precincts Complete", 0, 0, 0),
        ("Precincts Partially Reported", 10, 10, 0),
        ("Absentee/ Early Precincts Reporting", 10, 0, 10),
    )
    for row, expected in zip(tables["native-reporting-statistics.csv"], expected_reporting):
        assert (row["native_statistic_literal"], row["total"], row["election_day"], row["mail"]) == expected
        assert row["electorate_total"] == 10 and row["source_page"] == 1
    candidates = tables["county-candidate-results.csv"]
    party_rows = []
    for title, page, named, writeins, votes, overvotes, undervotes in CONTESTS:
        rows = [row for row in candidates if row["contest_literal"] == title]
        assert len(rows) == (len(named) + 1) * 3
        assert all(type(row["votes"]) is int and row["votes"] >= 0 and row["source_page"] == page for row in rows)
        expected = [(party, name, MODES[index], vector[index], "named_candidate")
                    for party, name, vector in named for index in range(3)]
        expected += [("", "Write-In Totals", mode, writeins[index], "write_in_total")
                     for index, mode in enumerate(MODES)]
        assert [(row["literal_party"], row["choice_literal"], row["counting_mode_literal"],
                 row["votes"], row["choice_kind"]) for row in rows] == expected
        for row in rows:
            if row["choice_kind"] == "named_candidate":
                party_rows.append(dict(contest_literal=title, literal_party=row["literal_party"],
                    counting_mode_literal=row["counting_mode_literal"], candidate_votes=row["votes"], source_page=page))
        accounts = [row for row in tables["native-contest-accounting.csv"] if row["contest_literal"] == title]
        children = [row for row in tables["native-write-in-children.csv"] if row["contest_literal"] == title]
        assert len(accounts) == len(children) == 3
        for index, (account, child) in enumerate(zip(accounts, children)):
            mode = MODES[index]
            assert account["counting_mode_literal"] == child["counting_mode_literal"] == mode
            assert account["native_contest_totals"] == ballots[index]
            assert account["native_total_votes_cast"] == votes[index] == sum(row["votes"] for row in rows if row["counting_mode_literal"] == mode)
            assert account["native_write_in_totals"] == account["native_not_assigned_subset"] == writeins[index]
            assert (account["native_overvotes"], account["native_undervotes"]) == (overvotes[index], undervotes[index])
            assert votes[index] + overvotes[index] + undervotes[index] == ballots[index]
            assert account["unclassified_participation_minus_votes_overvotes_undervotes"] == 0
            assert account["source_page"] == child["source_page"] == page
            assert account["source_update_literal"] == CLOCK and account["declared_timezone"] == ""
            assert (child["parent_literal"], child["child_literal"], child["votes"]) == ("Write-In Totals", "Not Assigned", writeins[index])
            assert child["additional_to_parent"] is False
    assert tables["county-literal-party-totals.csv"] == party_rows
    fields = ("municipality_id_literal", "municipality_literal", "apps_issued",
              "apps_returned", "ballots_sent", "ballots_returned", "votes_recorded")
    for row, expected in zip(tables["native-mail-receipts.csv"], MAIL_UNITS):
        assert tuple(row[field] for field in fields) == expected
        assert row["native_report_filter_literal"] == "Election ID (N) IS 2026 GENERAL ELECTION AND Federal Voter (Y) IS 0"
        assert row["report_role"] == "act88_receipt_not_counted_mail"
        assert row["source_update_literal"] == row["declared_timezone"] == ""
        assert row["source_page"] == 1
    for field in fields[2:]:
        assert sum(row[field] for row in tables["native-mail-receipts.csv"][:-1]) == tables["native-mail-receipts.csv"][-1][field]
    assert 320 != 319 and 324 != 319
    for index, row in enumerate(tables["native-source-pages.csv"]):
        assert row["source_sha256"] == (SUMMARY_SHA if index < 3 else ACT88_SHA)
        assert row["source_report"] == ("summary" if index < 3 else "act88")
        assert row["source_page"] == (index + 1 if index < 3 else 1)
        assert row["source_update_literal"] == (CLOCK if index < 3 else "")
        assert row["entire_page_token_multisets_match"] is True if index < 3 else row["entire_page_token_multisets_match"] == ""
        assert row["declared_timezone"] == ""
    receipts = facts["source_receipts"]
    assert len(receipts) == 5
    assert [(row["file"], row["status"]) for row in receipts] == [
        ("cameron-index-0.response", 200), ("cameron-act88-0.response", 302),
        ("cameron-act88-1.response", 200), ("cameron-summary-0.response", 302),
        ("cameron-summary-1.response", 200)]
    assert receipts[2]["sha256"] == ACT88_SHA and receipts[4]["sha256"] == SUMMARY_SHA
    assert receipts[1]["location"] == receipts[2]["url"] and receipts[3]["location"] == receipts[4]["url"]


def render(facts, directory):
    validate(facts)
    directory.mkdir(parents=True, exist_ok=False)
    for name, rows in facts["tables"].items():
        with (directory / name).open("x", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    with (directory / "source-records.json.gz").open("xb") as target:
        with gzip.GzipFile(fileobj=target, mode="wb", filename="", mtime=0) as compressed:
            compressed.write((json.dumps(facts, indent=2) + "\n").encode())
    audit = dict(scope=facts["scope"], table_rows=TABLES, primary_summary_entire_pages_two_engines_agree=3,
        act88_scanned_pages_visually_reviewed=1, act88_text_engine_agreement_claimed=False,
        native_ballots_cast=1624, native_registrations=2885, native_printed_turnout="56.29%",
        native_measure="Ballots Cast - Total", native_status="UNOFFICIAL RESULTS",
        native_election_day_ballots=1305, native_mail_ballots=319, provisional_participation_not_reported=True,
        native_precincts_complete=0, native_precincts_partial=10, native_blank_ballots=1,
        native_act88_ballots_returned=324, native_act88_votes_recorded=320,
        act88_minus_counted_mail_differences_not_reconciled=[5, 1],
        native_act88_federal_voter_filter_preserved=True,
        nested_not_assigned_not_additional_to_write_in_totals=True,
        native_timezone_not_declared=True, no_candidate_vote_substitution=True,
        maps_approved=False, no_certification_or_complete_counting_claim=True,
        original_documents_and_presentation_templates="Private; not redistributed or included in this factual query.")
    for name, value in (("audit.json", audit), ("source-receipts.json", facts["source_receipts"])):
        (directory / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    (directory / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    checksums = {path.name: dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in sorted(directory.iterdir())}
    (directory / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(directory / ARCHIVE, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(directory.iterdir()):
            if path.name != ARCHIVE:
                info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())


def self_test(facts):
    validate(facts)
    cases = (
        ("candidate votes substituted", "county-participation.csv", 0, "ballots_cast", 1617),
        ("missing provisional changed to zero", "county-participation.csv", 0, "provisional_ballots", 0),
        ("Act88 recorded substituted", "county-participation.csv", 0, "mail_ballots", 320),
        ("Act88 returned substituted", "county-participation.csv", 0, "mail_ballots", 324),
        ("nested write-in added", "native-write-in-children.csv", 3, "additional_to_parent", True),
        ("partial reporting treated as complete", "county-participation.csv", 0, "complete_precincts", 10),
        ("native party normalized", "county-candidate-results.csv", 0, "literal_party", "Democratic"),
        ("Act88 filter dropped", "native-mail-receipts.csv", 0, "native_report_filter_literal", ""),
        ("mode reallocated", "county-candidate-results.csv", 1, "votes", 358),
        ("image claimed two-engine matched", "native-source-pages.csv", 3, "entire_page_token_multisets_match", True),
    )
    for label, table, index, field, replacement in cases:
        invalid = copy.deepcopy(facts)
        invalid["tables"][table][index][field] = replacement
        try:
            validate(invalid)
        except AssertionError:
            continue
        raise AssertionError("Invalid native observation accepted: " + label)
    print("Ten focused participation, missingness, Act88, write-in, partial-reporting and provenance rejections pass.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.verify:
        facts = json.loads(gzip.decompress((args.verify / "source-records.json.gz").read_bytes()))
    else:
        assert args.source and args.output
        facts = json.loads(args.source.read_text())
    if args.self_test:
        self_test(facts)
    if args.verify:
        with tempfile.TemporaryDirectory() as temporary:
            reproduced = Path(temporary) / "query"
            render(facts, reproduced)
            assert {path.name for path in reproduced.iterdir()} == {path.name for path in args.verify.iterdir()}
            for path in reproduced.iterdir():
                assert path.read_bytes() == (args.verify / path.name).read_bytes(), path.name
        print("All 15 files and every complete ZIP member reproduce byte-identically offline.")
    else:
        render(facts, args.output)


if __name__ == "__main__":
    main()
