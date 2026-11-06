"""Reproduce the complete factual Clarion county summary without original templates."""

import argparse
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import csv
import tempfile
import zipfile


TABLES = {
    "county-participation.csv": 1,
    "county-candidate-results.csv": 13,
    "county-literal-party-totals.csv": 7,
    "native-contest-accounting.csv": 4,
    "native-source-pages.csv": 2,
}
ARCHIVE = "complete-clarion-2026-county-query-01.zip"


def validate(facts):
    tables = facts["tables"]
    assert set(tables) == set(TABLES)
    assert all(len(tables[name]) == count for name, count in TABLES.items())
    county = tables["county-participation.csv"][0]
    assert county["year"] == 2026 and county["state_code"] == "PA" and county["county"] == "Clarion"
    assert county["native_participation_measure_literal"] == "Voters Cast"
    assert county["reported_voters_cast"] == 12975 and county["registered_voters"] == 23306
    assert county["native_printed_turnout"] == "55.67%"
    assert county["source_status_literal"] == "UNOFFICIAL ELECTION RESULTS"
    assert county["reported_precincts"] == county["total_precincts"] == 40
    assert county["source_update_literal"] == "11/3/2026 9:49:20 PM"
    for row in [county] + tables["native-contest-accounting.csv"]:
        assert row["declared_timezone"] == ""
        assert all(row[field] == "" for field in ("election_day_count", "mail_in_count", "provisional_count"))
    candidates = tables["county-candidate-results.csv"]
    party_rows = []
    for index, contest in enumerate(tables["native-contest-accounting.csv"]):
        assert contest["native_undervotes"] == contest["native_overvotes"] == ""
        expected_scope = ("Foxburg Borough", 82, 116) if index == 3 else ("Clarion County", 12975, 23306)
        assert (contest["geography_scope"], contest["reported_times_cast"], contest["registered_voters"]) == expected_scope
        rows = [row for row in candidates if row["contest_literal"] == contest["contest_literal"]]
        assert rows and all(type(row["votes"]) is int and row["votes"] >= 0 for row in rows)
        assert all(row["source_page"] == contest["source_page"] for row in rows)
        named = [row for row in rows if row["choice_kind"] == "named_candidate"]
        options = [row for row in rows if row["choice_kind"] == "ballot_option"]
        unresolved = [row for row in rows if row["choice_kind"] == "unresolved_write_in"]
        assert len(unresolved) == 1 and len(named) + len(options) + 1 == len(rows)
        assert all(row["literal_party"] in ("DEM", "REP", "LIB") for row in named)
        assert all(row["literal_party"] == "" for row in options + unresolved)
        assert unresolved[0]["choice_literal"] == "Unresolved Write-In"
        assert unresolved[0]["votes"] == contest["unresolved_write_in"]
        assert sum(row["votes"] for row in named + options) == contest["native_total_votes_excluding_separate_unresolved_write_in"]
        complete = sum(row["votes"] for row in rows)
        assert complete == contest["candidate_or_option_plus_separate_unresolved_write_in"]
        assert contest["reported_times_cast"] - complete == contest["unclassified_participation_minus_all_reported_choices"]
        assert contest["unclassified_participation_minus_all_reported_choices"] >= 0
        assert (bool(options) and not named) if index == 3 else (bool(named) and not options)
        for row in named:
            party_rows.append(dict(contest_literal=row["contest_literal"], source_page=row["source_page"],
                                   literal_party=row["literal_party"], candidate_votes=row["votes"]))
    assert party_rows == tables["county-literal-party-totals.csv"]
    assert [row["unclassified_participation_minus_all_reported_choices"]
            for row in tables["native-contest-accounting.csv"]] == [108, 68, 95, 3]
    for index, page in enumerate(tables["native-source-pages.csv"], 1):
        assert page["source_page"] == index and page["entire_page_token_multisets_match"] is True
        assert page["source_sha256"] == "6bf8f71aaef129a91bb44b4fe37df53084c89856960ec057262f885c99797cd9"
        assert page["source_update_literal"] == county["source_update_literal"] and page["declared_timezone"] == ""


def render(facts, directory):
    validate(facts)
    directory.mkdir(exist_ok=False)
    for name, rows in facts["tables"].items():
        with (directory / name).open("x", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    with (directory / "source-records.json.gz").open("xb") as target:
        with gzip.GzipFile(fileobj=target, mode="wb", filename="", mtime=0) as compressed:
            compressed.write((json.dumps(facts, indent=2) + "\n").encode())
    audit = dict(
        scope=facts["scope"], table_rows=TABLES, primary_source_two_engines_agree=True,
        native_voters_cast=12975, native_registrations=23306, native_printed_turnout="55.67%",
        native_measure="Voters Cast", native_modes_not_separately_reported=True,
        native_status="UNOFFICIAL ELECTION RESULTS", native_timezone_not_declared=True,
        native_total_votes_excludes_separate_unresolved_write_in=True,
        no_candidate_vote_substitution=True, no_native_undervotes_or_overvotes_supplied=True,
        separate_foxburg_electorate_not_added_to_county=True,
        participation_minus_choices_unclassified_by_contest=[108, 68, 95, 3],
        maps_approved=False, no_certification_or_complete_counting_claim=True,
        original_documents_and_presentation_templates="Private; not redistributed or included in this factual query.")
    for name, value in [("audit.json", audit), ("source-receipts.json", facts["source_receipts"])]:
        (directory / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    (directory / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    checksums = {path.name: dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in sorted(directory.iterdir())}
    (directory / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(directory / ARCHIVE, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(directory.iterdir()):
            if path.name == ARCHIVE:
                continue
            info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def self_test(facts):
    validate(facts)
    invalid = []
    value = copy.deepcopy(facts)
    value["tables"]["county-participation.csv"][0]["reported_voters_cast"] = 12893
    invalid.append(value)
    value = copy.deepcopy(facts)
    value["tables"]["county-participation.csv"][0]["provisional_count"] = 0
    invalid.append(value)
    value = copy.deepcopy(facts)
    value["tables"]["native-contest-accounting.csv"][3]["registered_voters"] = 23306
    invalid.append(value)
    value = copy.deepcopy(facts)
    value["tables"]["county-candidate-results.csv"][-1]["votes"] = 1
    invalid.append(value)
    value = copy.deepcopy(facts)
    value["tables"]["county-candidate-results.csv"][-2]["literal_party"] = "REP"
    invalid.append(value)
    for value in invalid:
        try:
            validate(value)
        except AssertionError:
            continue
        raise AssertionError("Invalid native observation was accepted")
    print("Five focused substitution, missing-mode, electorate, write-in and ballot-option cases pass.")


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
        print("All 11 files and every complete ZIP member reproduce byte-identically offline.")
    else:
        render(facts, args.output)


if __name__ == "__main__":
    main()
