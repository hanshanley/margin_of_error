"""Reproduce the scoped complete Carbon county summary and unit-participation query."""

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
    "county-candidate-results.csv": 104,
    "county-literal-party-totals.csv": 56,
    "native-contest-accounting.csv": 32,
    "native-participation-modes.csv": 8,
    "native-unit-participation.csv": 55,
    "native-source-pages.csv": 27,
    "native-report-observations.csv": 3,
    "native-source-selection.csv": 4,
}
ARCHIVE = "complete-carbon-2026-county-query-01.zip"
MODES = ("Election Day", "Mail-In", "Provisional", "Total")
CLOCKS = dict(summary="11/3/2026 10:36:36 PM", zero="11/3/2026 7:05:24 PM", statement="11/3/2026 10:19:13 PM")
HASHES = dict(summary="342a3ba77d58248af19cfe68299ee0fb894483d88acb1371a56818562eab8100",
    zero="1ec74479aba6557864ae80ab88fb65388a9dfdd3247a3d9e53ea68d3ed953f73",
    statement="4f0e2487c53ac170b1bf6ade70ec9109dfdf2fe62b4700ab571e39d57eae52be")
UNIT_IDENTITY_SHA = "658fb7454aea3e9d8be9cfb4adcfaaa9527531a6496ba1f879a09d8c9dcd1b63"
CONTESTS = (
    ("Governor and Lieutenant Governor (Vote for 1)",
     (("Josh Shapiro/Austin Davis", "DEM", (7957, 3178, 0, 11135)),
      ("Stacy Garrity/Jason Richey", "REP", (11706, 1106, 0, 12812)),
      ("Ken Krawchuk/John Thomas", "LIB", (464, 50, 0, 514))),
     (25, 4, 0, 29), (223, 127, 0, 350), 45896),
    ("Representative in Congress 7th District (Vote for 1)",
     (("Bob Brooks", "DEM", (6854, 2895, 0, 9749)),
      ("Ryan Mackenzie", "REP", (13194, 1467, 0, 14661))),
     (43, 6, 0, 49), (284, 97, 0, 381), 45896),
    ("Representative in the General Assembly 122nd District (Vote for 1)",
     (("Christian Bartulovich", "DEM", (7379, 2499, 0, 9878)),
      ("Doyle Heffley", "REP", (12754, 1874, 0, 14628))),
     (34, 12, 0, 46), (208, 80, 0, 288), 45896),
    ("Kidder Township Ballot Referendum (Vote for 1)",
     (("Yes", "", (461, 91, 0, 552)), ("No", "", (175, 50, 0, 225))),
     (0, 0, 0, 0), (24, 6, 0, 30), 1457),
)


def validate(facts):
    tables = facts["tables"]
    assert set(tables) == set(TABLES)
    assert all(len(tables[name]) == count for name, count in TABLES.items())
    county = tables["county-participation.csv"][0]
    assert (county["year"], county["state_code"], county["county"]) == (2026, "PA", "Carbon")
    assert county["native_participation_measure_literal"] == "Voters Cast"
    assert (county["reported_voters_cast"], county["registered_voters"], county["native_printed_turnout"]) == (24840, 45896, "54.12%")
    assert (county["election_day_count"], county["mail_in_count"], county["provisional_count"]) == (20375, 4465, 0)
    assert type(county["provisional_count"]) is int
    assert county["reported_precincts"] == county["total_precincts"] == 51
    assert county["source_report"] == "summary" and county["source_status_literal"] == "Unofficial Results"
    assert county["source_update_literal"] == CLOCKS["summary"] and county["declared_timezone"] == ""
    expected_party_rows = []
    for report in ("summary", "zero"):
        zero = report == "zero"
        modes = [row for row in tables["native-participation-modes.csv"] if row["source_report"] == report]
        assert len(modes) == 4
        for index, row in enumerate(modes):
            assert row["counting_mode_literal"] == MODES[index]
            assert row["voters_cast"] == (0 if zero else (20375, 4465, 0, 24840)[index])
            assert row["native_mode_registered_voters"] == (45896 if index == 3 else "")
            assert row["native_county_registered_voters"] == 45896
            assert row["native_printed_turnout"] == ("0.00%" if zero else ("44.39%", "9.73%", "0.00%", "54.12%")[index])
            assert row["source_update_literal"] == CLOCKS[report] and row["declared_timezone"] == ""
        for contest_index, (title, choices, writeins, residuals, registrations) in enumerate(CONTESTS):
            page = (1 if contest_index < 3 else 2) if zero else (1 if contest_index < 2 else 2)
            scope = "Kidder Township" if contest_index == 3 else "Carbon County"
            rows = [row for row in tables["county-candidate-results.csv"]
                    if row["source_report"] == report and row["contest_literal"] == title]
            expected = []
            for name, party, vector in choices:
                for index, mode in enumerate(MODES):
                    votes = 0 if zero else vector[index]
                    expected.append((name, party, "named_candidate" if party else "ballot_option", mode, votes))
                    if party:
                        expected_party_rows.append(dict(source_report=report, contest_literal=title,
                            literal_party=party, counting_mode_literal=mode, candidate_votes=votes, source_page=page))
            expected += [("Unresolved Write-In", "", "unresolved_write_in", mode, 0 if zero else writeins[index])
                         for index, mode in enumerate(MODES)]
            assert [(row["choice_literal"], row["literal_party"], row["choice_kind"],
                     row["counting_mode_literal"], row["votes"]) for row in rows] == expected
            assert all(type(row["votes"]) is int and row["source_page"] == page and row["geography_scope"] == scope for row in rows)
            accounts = [row for row in tables["native-contest-accounting.csv"]
                        if row["source_report"] == report and row["contest_literal"] == title]
            assert len(accounts) == 4
            for index, account in enumerate(accounts):
                mode = MODES[index]
                times = (660, 147, 0, 807) if contest_index == 3 else (20375, 4465, 0, 24840)
                assert account["counting_mode_literal"] == mode and account["geography_scope"] == scope
                assert account["native_times_cast"] == (0 if zero else times[index])
                assert account["native_registered_voters"] == (registrations if index == 3 else "")
                assert account["native_printed_turnout"] == (("0.00%" if zero else "55.39%" if contest_index == 3 else "54.12%") if index == 3 else "")
                named = sum(row["votes"] for row in rows if row["counting_mode_literal"] == mode and row["choice_kind"] != "unresolved_write_in")
                unresolved = 0 if zero else writeins[index]
                assert account["named_or_option_choices"] == named
                assert account["unresolved_write_in"] == unresolved
                assert account["all_reported_choices"] == named + unresolved
                assert account["unclassified_participation_minus_all_reported_choices"] == (0 if zero else residuals[index])
                assert named + unresolved + account["unclassified_participation_minus_all_reported_choices"] == account["native_times_cast"]
                assert account["native_undervotes"] == account["native_overvotes"] == ""
                assert account["source_page"] == page and account["source_update_literal"] == CLOCKS[report]
                assert account["declared_timezone"] == ""
    assert tables["county-literal-party-totals.csv"] == expected_party_rows
    units = tables["native-unit-participation.csv"]
    fields = ("unit_literal", "registered_voters", "voters_cast", "native_printed_turnout", "source_page")
    identity = [tuple(row[field] for field in fields) for row in units]
    digest = hashlib.sha256((json.dumps(identity, ensure_ascii=True, separators=(",", ":")) + "\n").encode()).hexdigest()
    assert digest == facts["unit_participation_identity_sha256"] == UNIT_IDENTITY_SHA
    assert all(row["source_report"] == "statement" and row["source_update_literal"] == CLOCKS["statement"]
               and row["declared_timezone"] == "" and row["independent_label_value_rows_match"] is True for row in units)
    assert all(row["row_role"] == "unit" for row in units[:51])
    assert [row["row_role"] for row in units[51:]] == ["county_total", "cumulative_container", "cumulative_total", "repeated_county_total"]
    assert len({row["unit_literal"] for row in units[:51]}) == 51
    assert sum(row["voters_cast"] for row in units[:51]) == 24840
    assert sum(row["registered_voters"] for row in units[:51]) == 45896
    kidder = [row for row in units[:51] if row["unit_literal"].startswith("Kidder Township - ")]
    assert len(kidder) == 2 and sum(row["voters_cast"] for row in kidder) == 807 and sum(row["registered_voters"] for row in kidder) == 1457
    for index, report in enumerate(("summary", "zero", "statement")):
        observation = tables["native-report-observations.csv"][index]
        assert observation["source_report"] == report and observation["source_update_literal"] == CLOCKS[report]
        assert observation["source_status_literal"] == {"summary": "Unofficial Results", "zero": "Official Zero Report", "statement": ""}[report]
        assert observation["observation_role"] == {"summary": "current_unofficial", "zero": "precount_zero", "statement": "current_detailed_statement"}[report]
        assert observation["voters_cast"] == (0 if report == "zero" else 24840)
        assert observation["registered_voters"] == 45896 and observation["declared_timezone"] == ""
        assert observation["native_reported_precincts"] == observation["native_total_precincts"] == (51 if report == "summary" else "")
        pages = [row for row in tables["native-source-pages.csv"] if row["source_report"] == report]
        assert len(pages) == (23 if report == "statement" else 2)
        for page_number, row in enumerate(pages, 1):
            assert row["source_page"] == page_number and row["source_sha256"] == HASHES[report]
            assert row["source_update_literal"] == CLOCKS[report] and row["declared_timezone"] == ""
            assert row["entire_page_token_multisets_match"] is True
    selection = tables["native-source-selection.csv"]
    assert selection[0]["native_link_label"] == "Current" and selection[0]["source_selection_role"] == "stale_primary_not_used"
    assert "2026 General Primary 5-19-2026" in selection[0]["source_url"]
    assert all(row["source_selection_role"] == "declared_general_report" and "2026 General ELection Nov" in row["source_url"] for row in selection[1:])
    receipts = facts["source_receipts"]
    assert len(receipts) == 8 and receipts[0]["status"] == receipts[1]["status"] == 200
    assert receipts[1]["sha256"] == "a7d6aa75c1fc4195d9e5dd176e7cd7d8449094354bcef6ee06b670d7aaa96814"
    for report in ("summary", "zero", "statement"):
        original = next(row for row in receipts if row["file"] == f"carbon-{report}-0.response")
        final = next(row for row in receipts if row["file"] == f"carbon-{report}-redirect-1.response")
        assert original["status"] == 302 and final["status"] == 200
        assert original["location"] == final["url"] and final["sha256"] == HASHES[report]
    assert facts["full_source_pages_two_engines_agree"] == 27
    assert facts["independently_matching_complete_participation_rows"] == 55


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
    audit = dict(scope=facts["scope"], table_rows=TABLES, primary_source_entire_pages_two_engines_agree=27,
        native_voters_cast=24840, native_registrations=45896, native_printed_turnout="54.12%",
        native_measure="Voters Cast", native_status="Unofficial Results", native_timezone_not_declared=True,
        native_election_day_count=20375, native_mail_in_count=4465, native_explicit_provisional_count=0,
        native_reported_precincts=51, reporting_not_complete_counting=True,
        earlier_official_zero_report_separate=True, three_distinct_report_clocks_preserved=True,
        complete_native_unit_participation_rows=51, all_unit_label_value_rows_independently_match=55,
        county_totals_and_cumulative_containers_not_added=True, native_cumulative_NA_not_zero_turnout=True,
        native_mode_electorates_missing_not_imputed=True, stale_current_primary_link_not_used=True,
        separate_kidder_electorate_not_added_to_county=True,
        participation_minus_choices_unclassified_by_contest=[350, 381, 288, 30],
        no_native_undervotes_or_overvotes_supplied=True, no_candidate_vote_substitution=True,
        unit_candidate_tables_outside_numerical_query_scope=True,
        source_terms_reviewed_no_redistribution_permission_claim=True,
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
        ("candidate votes substituted", "county-participation.csv", 0, "reported_voters_cast", 24490),
        ("explicit provisional zero erased", "county-participation.csv", 0, "provisional_count", ""),
        ("earlier zero substituted", "county-participation.csv", 0, "reported_voters_cast", 0),
        ("Kidder uses county electorate", "native-contest-accounting.csv", 15, "native_registered_voters", 45896),
        ("Cumulative NA changed to zero rate", "native-unit-participation.csv", 52, "native_printed_turnout", "0.00%"),
        ("unresolved write-in changed", "county-candidate-results.csv", 12, "votes", 26),
        ("residual relabelled undervotes", "native-contest-accounting.csv", 3, "native_undervotes", 350),
        ("literal party normalized", "county-candidate-results.csv", 0, "literal_party", "Democratic"),
        ("mode electorate invented", "native-participation-modes.csv", 0, "native_mode_registered_voters", 45896),
        ("statement borrowed summary clock", "native-report-observations.csv", 2, "source_update_literal", CLOCKS["summary"]),
        ("stale primary selected", "native-source-selection.csv", 0, "source_selection_role", "declared_general_report"),
    )
    invalids = []
    for label, table, index, field, replacement in cases:
        invalid = copy.deepcopy(facts)
        invalid["tables"][table][index][field] = replacement
        invalids.append((label, invalid))
    swapped = copy.deepcopy(facts)
    units = swapped["tables"]["native-unit-participation.csv"]
    for field in ("registered_voters", "voters_cast", "native_printed_turnout"):
        units[0][field], units[1][field] = units[1][field], units[0][field]
    invalids.append(("unit counts swapped with county sums unchanged", swapped))
    for label, invalid in invalids:
        try:
            validate(invalid)
        except AssertionError:
            continue
        raise AssertionError("Invalid native observation accepted: " + label)
    print("Twelve focused participation, zero/missingness, electorate, residual, row-identity and provenance rejections pass.")


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
