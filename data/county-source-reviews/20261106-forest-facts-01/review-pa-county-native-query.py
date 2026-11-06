"""Reproduce the complete reviewed Elk or Forest factual query offline."""

import argparse
import copy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile


NATIVE = {
    "Elk": "4c02018694dab0e0c8b12cfcfecde73f6da1ca22cc13a322ef86215eac635a15",
    "Forest": "42979c318ffcf2ca80c8e50ba340666860dacda21f73d4d0995374ca524c81cc",
}
ACT88 = "e66b0a739217a12932bc80fad2f5350603d6e6233280c087d2e51cc5106ffa8a"
SOURCES = {
    "Elk": (
        ("elk-index.html", "b78df567281764de7b075823909b9d1722fd869c90df0535897421dbe8bdff5c"),
        ("elk-summary.pdf", "0379761dc4b8ffc4f15906e96b0ae75878828e12f42a2cab363e1b9f0cc86e54"),
        ("elk-statement.pdf", "20169c238f78d8c012ce9fdb70ebdc6e649d4654b583d4542d6848d6fd6cf358"),
        ("elk-act88.pdf", "943d5d3a220511e4582360d5e252b927048666e8c22722b90e7f7b99ad730c84"),
    ),
    "Forest": (
        ("forest-parent.html", "8198bef4fb6079a76b4c8b28c70b5b87b7cb7958a475580e125615e169be057a"),
        ("forest-summary.pdf", "2db4f7eb590d2e718ab76f52ecd56a67bf77b3e920f482d66a5af435b2bd4a8f"),
        ("forest-statement.pdf", "6c0194a63a197e086f8a983427a24b2c895298537716a40942262917244834ff"),
    ),
}
DECLARATIONS = {
    "Elk": [
        dict(file="elk-summary.pdf", label="Official General Election Results (Media Report): November 3, 2026",
             url="https://countyofelkpa.gov/wp-content/uploads/2026M_Media.pdf"),
        dict(file="elk-statement.pdf", label="Official General Election Results (Precinct Report): November 4, 2026",
             url="https://countyofelkpa.gov/wp-content/uploads/2026M_Precinct.pdf"),
        dict(file="elk-act88.pdf", label="2026 General Act 88 Notice",
             url="https://countyofelkpa.gov/wp-content/uploads/scan_20261103205910.pdf"),
    ],
    "Forest": [
        dict(file="forest-summary.pdf", label="2026 November Election Summary report",
             url="https://www.co.forest.pa.us/departments/docs/Summary Report.pdf?t=202611032146150"),
        dict(file="forest-statement.pdf", label="2026 November Election Precinct Summary",
             url="https://www.co.forest.pa.us/departments/docs/Precinct Report.pdf?t=202611032147100"),
    ],
}
TABLES = (
    "county-participation.csv", "county-candidate-results.csv", "county-literal-party-totals.csv",
    "county-contest-accounting.csv", "native-unit-participation.csv",
    "native-unit-participation-modes.csv", "native-unit-candidate-results.csv",
    "native-unit-literal-party-totals.csv", "native-unit-contest-accounting.csv",
    "native-participation-modes.csv", "native-reporting-statistics.csv", "native-mail-receipts.csv",
    "native-source-pages.csv", "native-derived-contest-sums.csv", "native-derived-rate-checks.csv",
    "native-source-declarations.csv",
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_tables(facts):
    county, native = facts["county"], facts["native"]
    assert county in NATIVE and digest(native) == NATIVE[county]
    assert facts["maps_approved"] is False
    elk = county == "Elk"
    modes = ("TOTAL", "Election Day", "Absentee/Mail-In", "Provisional") if elk else ("TOTAL",)
    clock = native["native_clock_literal"] if elk else native["source_update_literal"]
    sources = dict(SOURCES[county])
    tables = {name: [] for name in TABLES}
    if elk:
        assert digest(facts["act88"]) == ACT88
        one = native["reports"]["summary"]["participation"][0]
        units = native["reports"]["statement"]["participation"]
        rows = native["reports"]["summary"]["contests"] + native["reports"]["statement"]["contests"]
        summary_page, printed = 1, "Page 1 of 2"
        ballots, registrations, blanks = one["ballots"], one["registered_voters"], one["blanks"]
        rate = one["printed_turnout"]
        precincts = 29
    else:
        one = native["county_participation"]
        summary_page, printed = 2, "Page 1 of 2"
        ballots, registrations, blanks = [one["ballots_cast"]], one["registered_voters"], [one["blank_ballots"]]
        rate = one["native_printed_turnout"]
        precincts = 9
        units = [dict(report="statement", page=row[0], unit=row[1], registered_voters=row[2],
            ballots=[row[3]], blanks=[row[4]], printed_turnout=row[5]) for row in native["units"]]
        rows = []
        for contest_index, contest in enumerate(native["contests"]):
            rows.append(dict(report="summary", page=1, unit="Forest County",
                contest=contest["contest_literal"],
                candidates=[dict(party=party, choice=name, counts=[count]) for party, name, count in contest["choices"]],
                votes=None, contest_totals=None, overvotes=[contest["native_overvotes"]],
                undervotes=[contest["native_undervotes"]]))
            for unit in native["units"]:
                rows.append(dict(report="statement", page=unit[0], unit=unit[1], contest=contest["contest_literal"],
                    candidates=[dict(party=choice[0], choice=choice[1], counts=[count])
                        for choice, count in zip(contest["choices"], unit[6 + contest_index])],
                    votes=None, contest_totals=None, overvotes=None, undervotes=None))
    assert len(units) == precincts and len({row["unit"] for row in units}) == precincts
    assert sum(row["registered_voters"] for row in units) == registrations
    assert [sum(row["ballots"][index] for row in units) for index in range(len(modes))] == ballots
    assert [sum(row["blanks"][index] for row in units) for index in range(len(modes))] == blanks
    county_row = dict(year=2026, state_code="PA", county=county,
        native_participation_measure_literal="Ballots Cast - Total", ballots_cast=ballots[0],
        registered_voters=registrations, native_printed_turnout=rate,
        election_day_ballots=ballots[1] if elk else "", mail_ballots=ballots[2] if elk else "",
        provisional_ballots=ballots[3] if elk else "", blank_ballots=blanks[0],
        reported_precincts=precincts, total_precincts=precincts, complete_precincts=0,
        partially_reported_precincts=precincts, source_status_literal="UNOFFICIAL RESULTS",
        source_update_literal=clock, declared_timezone="", source_report="summary",
        source_page=summary_page, native_printed_page=printed)
    tables["county-participation.csv"].append(county_row)
    for row in [dict(report="summary", page=summary_page, unit=county + " County",
                     ballots=ballots, registered_voters=registrations, blanks=blanks, printed_turnout=rate)] + units:
        is_county = row["report"] == "summary"
        meta = dict(source_report=row["report"], source_page=row["page"],
            native_printed_page=(f'Page {row["page"]} of {58 if elk else 9}' if not is_county else printed),
            source_update_literal=clock, declared_timezone="")
        if not is_county:
            tables["native-unit-participation.csv"].append(dict(unit_literal=row["unit"],
                registered_voters=row["registered_voters"], ballots_cast=row["ballots"][0],
                blank_ballots=row["blanks"][0], native_printed_turnout=row["printed_turnout"], **meta))
        mode_table = "native-participation-modes.csv" if is_county else "native-unit-participation-modes.csv"
        for index, mode in enumerate(modes):
            tables[mode_table].append(dict(unit_literal=row["unit"], counting_mode_literal=mode,
                ballots_cast=row["ballots"][index], blank_ballots=row["blanks"][index],
                registered_voters=row["registered_voters"] if index == 0 else "",
                native_printed_turnout=row["printed_turnout"] if index == 0 else "", **meta))
        calculated = f'{100 * row["ballots"][0] / row["registered_voters"]:.2f}%'
        tables["native-derived-rate-checks.csv"].append(dict(unit_literal=row["unit"],
            native_ballots_cast=row["ballots"][0], native_registered_voters=row["registered_voters"],
            native_printed_turnout=row["printed_turnout"], calculated_rounded_fraction=calculated,
            native_printed_matches_calculated=row["printed_turnout"] == calculated,
            calculation_role="Derived check only; native printed percentage is never rewritten.", **meta))
    unit_by_name = {row["unit"]: row for row in units}
    for row in rows:
        is_county = row["report"] == "summary"
        prefix = "county-" if is_county else "native-unit-"
        report_pages = 2 if is_county else 58 if elk else 9
        print_page = row["page"] if elk or not is_county else 2
        meta = dict(source_report=row["report"], source_page=row["page"],
            native_printed_page=f"Page {print_page} of {report_pages}",
            source_update_literal=clock, declared_timezone="")
        for candidate in row["candidates"]:
            for index, mode in enumerate(modes):
                result = dict(unit_literal=row["unit"], contest_literal=row["contest"],
                    literal_party=candidate["party"], choice_literal=candidate["choice"],
                    choice_kind="named_candidate" if candidate["party"] else "write_in_total",
                    counting_mode_literal=mode, votes=candidate["counts"][index], **meta)
                tables[prefix + "candidate-results.csv"].append(result)
                if candidate["party"]:
                    tables[prefix + "literal-party-totals.csv"].append(dict(unit_literal=row["unit"],
                        contest_literal=row["contest"], literal_party=candidate["party"],
                        counting_mode_literal=mode, candidate_votes=result["votes"], **meta))
        for index, mode in enumerate(modes):
            choices = sum(candidate["counts"][index] for candidate in row["candidates"])
            participation = ballots[index] if is_county else unit_by_name[row["unit"]]["ballots"][index]
            over = row["overvotes"][index] if row["overvotes"] is not None else ""
            under = row["undervotes"][index] if row["undervotes"] is not None else ""
            assert participation >= choices
            if over != "" and under != "":
                assert choices + over + under == participation
            if row["votes"] is not None:
                assert row["votes"][index] == choices and row["contest_totals"][index] == participation
            tables[prefix + "contest-accounting.csv"].append(dict(unit_literal=row["unit"],
                contest_literal=row["contest"], counting_mode_literal=mode,
                native_total_votes_cast=row["votes"][index] if row["votes"] is not None else "",
                native_contest_totals=row["contest_totals"][index] if row["contest_totals"] is not None else "",
                native_overvotes=over, native_undervotes=under,
                native_participation_header=participation, derived_sum_of_choice_votes=choices,
                derived_participation_minus_choices=participation - choices,
                accounting_scope="Native unit over/undervotes" if elk and not is_county
                    else "Native county over/undervotes; unit accounting not reported" if not elk and is_county
                    else "Over/undervotes not reported in this report/row; residual remains unclassified",
                **meta))
    for county_account in tables["county-contest-accounting.csv"]:
        unit_accounts = [row for row in tables["native-unit-contest-accounting.csv"]
            if row["contest_literal"] == county_account["contest_literal"]
            and row["counting_mode_literal"] == county_account["counting_mode_literal"]]
        assert len(unit_accounts) == precincts
        assert sum(row["derived_sum_of_choice_votes"] for row in unit_accounts) == county_account["derived_sum_of_choice_votes"]
        tables["native-derived-contest-sums.csv"].append(dict(
            contest_literal=county_account["contest_literal"], counting_mode_literal=county_account["counting_mode_literal"],
            complete_units=precincts, sum_unit_choice_votes=sum(row["derived_sum_of_choice_votes"] for row in unit_accounts),
            sum_unit_unclassified_participation_minus_choices=sum(row["derived_participation_minus_choices"] for row in unit_accounts),
            sum_native_unit_overvotes=sum(row["native_overvotes"] for row in unit_accounts) if elk else "",
            sum_native_unit_undervotes=sum(row["native_undervotes"] for row in unit_accounts) if elk else "",
            native_summary_overvotes=county_account["native_overvotes"],
            native_summary_undervotes=county_account["native_undervotes"],
            scope="Derived sums of complete native units; not borrowed or invented report cells."))
    for label, total, ed, mail in (
        ("Election Day Precincts Reporting", precincts, precincts, 0),
        ("Precincts Complete", 0, 0, 0),
        ("Precincts Partially Reported", precincts, precincts, 0),
        ("Absentee/ Early Precincts Reporting", precincts, 0, precincts),
    ):
        tables["native-reporting-statistics.csv"].append(dict(native_statistic_literal=label,
            total=total, electorate_total=precincts, election_day=ed if elk else "",
            mail=mail if elk else "", provisional=0 if elk else "",
            source_report="summary", source_page=summary_page, native_printed_page=printed))
    if elk:
        act = facts["act88"]
        for section, label, kind, issued, returned, sent, received, recorded in act["rows"]:
            tables["native-mail-receipts.csv"].append(dict(section_literal=section,
                native_label_literal=label, row_kind=kind, apps_issued=issued, apps_returned=returned,
                ballots_sent=sent, ballots_returned=received, votes_recorded=recorded,
                native_report_filter_literal=act["native_report_filter_literal"],
                native_print_date_literal=act["report_date_literal"], source_report="act88",
                source_page=1, source_update_literal="", declared_timezone="",
                report_role="act88_receipt_not_counted_mail"))
        for page in native["pages_review"]:
            report = page["report"]
            tables["native-source-pages.csv"].append(dict(source_report=report, source_page=page["page"],
                native_printed_page=f'Page {page["page"]} of {2 if report == "summary" else 58}',
                source_sha256=sources["elk-" + report + ".pdf"], source_update_literal=clock,
                declared_timezone="", entire_page_token_multisets_match=True,
                review_method="PyMuPDF;pdfplumber entire-page tokens and independently equal parsed vectors",
                numerical_query_scope="All participation, choice, mode and accounting rows on this page"))
        tables["native-source-pages.csv"].append(dict(source_report="act88", source_page=1,
            native_printed_page="Page 1 of 1", source_sha256=sources["elk-act88.pdf"],
            source_update_literal="", declared_timezone="", entire_page_token_multisets_match="",
            review_method="Direct visual review of complete scanned page; both text engines empty",
            numerical_query_scope="All23 rows in all3 sections; section totals are not additive"))
    else:
        tables["native-mail-receipts.csv"].append(dict(native_ballots_received=311,
            receipt_scope_literal=native["mail_receipt"]["receipt_scope_literal"],
            deadline_literal=native["mail_receipt"]["deadline_literal"], source_report="index",
            source_page="", source_update_literal="", declared_timezone="",
            report_role="act88_received_by_deadline_not_counted_mail"))
        for report, count in (("summary", 2), ("statement", 9)):
            for page in range(1, count + 1):
                print_page = 3 - page if report == "summary" else page
                tables["native-source-pages.csv"].append(dict(source_report=report, source_page=page,
                    native_printed_page=f"Page {print_page} of {count}",
                    source_sha256=sources["forest-" + report + ".pdf"], source_update_literal=clock,
                    declared_timezone="", entire_page_token_multisets_match="",
                    review_method="Direct visual review of entire scan and magnified choice panels; both text engines empty",
                    numerical_query_scope="All native participation/statistics/choices/accounting on this page"))
    for declaration in facts["source_declarations"]:
        tables["native-source-declarations.csv"].append(dict(
            declared_label_literal=declaration["label"], requested_url=declaration["url"],
            file=declaration["file"], status_scope="Index wording is not report certification or a report clock."))
    assert all(tables.values())
    return tables


def validate(facts):
    assert facts["tables"] == build_tables(facts)
    county = facts["county"]
    assert facts["source_declarations"] == DECLARATIONS[county]
    receipts = facts["source_receipts"]
    assert [(row["file"], row["sha256"]) for row in receipts] == list(SOURCES[county])
    assert all(row["status"] == 200 and row["bytes"] > 0 for row in receipts)
    declared = {row["file"]: row["url"] for row in DECLARATIONS[county]}
    for row in receipts:
        assert row["final_url"].startswith("https://")
        if row["file"] in declared:
            assert row["requested_url"] == declared[row["file"]]
        for redirect in row["redirects"]:
            assert redirect["status"] == 302 and redirect["location"].startswith("https://cms6.revize.com/revize/forestcounty/")
    candidates = facts["tables"]["county-candidate-results.csv"]
    units = facts["tables"]["native-unit-candidate-results.csv"]
    for row in candidates:
        matching = [unit for unit in units if all(unit[field] == row[field]
                    for field in ("contest_literal", "literal_party", "choice_literal", "counting_mode_literal"))]
        assert len(matching) == (29 if county == "Elk" else 9)
        assert sum(unit["votes"] for unit in matching) == row["votes"]


def render(facts, directory):
    validate(facts)
    directory.mkdir(parents=True, exist_ok=False)
    for name, rows in facts["tables"].items():
        with (directory / name).open("x", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    with (directory / "source-records.json.gz").open("xb") as target:
        with gzip.GzipFile(fileobj=target, mode="wb", filename="", mtime=0) as compressed:
            compressed.write((json.dumps(facts, indent=2) + "\n").encode())
    county = facts["county"]
    audit = dict(scope=facts["scope"], table_rows={key: len(rows) for key, rows in facts["tables"].items()},
        native_ballots_cast=11742 if county == "Elk" else 1877,
        native_registrations=20533 if county == "Elk" else 3275,
        native_measure="Ballots Cast - Total", source_status_literal="UNOFFICIAL RESULTS",
        primary_text_pages_two_engines_agree=60 if county == "Elk" else 0,
        scanned_pages_visually_reviewed=1 if county == "Elk" else 11,
        empty_text_engines_not_claimed_as_transcription=True,
        complete_native_units=29 if county == "Elk" else 9, complete_native_county_contests=3,
        complete_native_unit_contests=87 if county == "Elk" else 27,
        mode_participation_missing_not_zero=county == "Forest",
        native_precincts_complete=0, native_precincts_partial=29 if county == "Elk" else 9,
        report_clocks_preserved_without_repair_or_timezone=True,
        distinct_physical_and_native_printed_page_identity=True,
        receipts_not_substituted_for_counted_ballots=True,
        missing_native_accounting_not_filled_by_derived_rows=True,
        literal_party_labels_not_normalized=True, no_candidate_vote_substitution=True,
        maps_approved=False, no_certification_or_complete_counting_claim=True,
        original_documents_and_presentation_templates="Private; not redistributed or included in this factual query.")
    if county == "Elk":
        audit.update(native_election_day_ballots=9725, native_mail_ballots=2017, native_provisional_ballots=0,
            native_act88_ballots_returned=2035, native_act88_votes_recorded=2018,
            act88_minus_counted_mail_differences_not_reconciled=[18, 1],
            native_printed_rate_disagreement=facts["native"]["native_printed_rate_disagreements"])
    else:
        audit.update(native_act88_received_by_8pm=311, native_counted_mail_ballots="",
            summary_physical_page1_prints="Page 2 of 2", summary_physical_page2_prints="Page 1 of 2")
    for name, value in (("audit.json", audit), ("source-receipts.json", facts["source_receipts"])):
        (directory / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    (directory / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    checksums = {path.name: dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in sorted(directory.iterdir())}
    (directory / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n", encoding="utf-8")
    archive_name = "complete-" + county.lower() + "-2026-county-query-01.zip"
    with zipfile.ZipFile(directory / archive_name, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(directory.iterdir()):
            if path.name != archive_name:
                info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())


def self_test(facts):
    county = facts["county"]
    cases = [
        ("candidate votes substituted", "county-participation.csv", 0, "ballots_cast", 11683 if county == "Elk" else 1872),
        ("receipts substituted as mail", "county-participation.csv", 0, "mail_ballots", 2018 if county == "Elk" else 311),
        ("missing mode or explicit zero erased", "county-participation.csv", 0, "provisional_ballots", "" if county == "Elk" else 0),
        ("partial reporting declared complete", "county-participation.csv", 0, "complete_precincts", 29 if county == "Elk" else 9),
        ("clock silently repaired", "county-participation.csv", 0, "source_update_literal", "2026-11-03T22:08:00-05:00"),
        ("literal party normalized", "county-candidate-results.csv", 0, "literal_party", "Democratic"),
        ("unit choice changed", "native-unit-candidate-results.csv", 0, "votes", 999),
        ("missing native accounting invented", "county-contest-accounting.csv", 0,
            "native_overvotes" if county == "Elk" else "native_total_votes_cast", 10 if county == "Elk" else 1870),
        ("row identity changed", "native-unit-participation.csv", 0, "unit_literal", "Other unit"),
        ("native page identity changed", "native-source-pages.csv", 0, "native_printed_page", "Page 99 of 99"),
        ("empty image engines called transcription", "native-source-pages.csv", 60 if county == "Elk" else 0,
            "entire_page_token_multisets_match", True),
        ("derived unit accounting borrowed", "native-derived-contest-sums.csv", 0,
            "native_summary_overvotes" if county == "Elk" else "sum_native_unit_overvotes", 0),
        ("receipt role dropped", "native-mail-receipts.csv", 0, "report_role", "counted_mail_ballots"),
    ]
    if county == "Elk":
        cases += [
            ("native printed rate repaired", "native-unit-participation.csv", 23, "native_printed_turnout", "55.09%"),
            ("Act88 eligibility filter lost", "native-mail-receipts.csv", 0, "native_report_filter_literal", ""),
            ("blank ballot style invented", "native-mail-receipts.csv", 10, "native_label_literal", "All styles"),
            ("distinct misspelled party collapsed", "native-mail-receipts.csv", 17, "native_label_literal", "INDEPENDENT"),
        ]
    for label, table, index, field, replacement in cases:
        invalid = copy.deepcopy(facts)
        assert invalid["tables"][table][index][field] != replacement, label
        invalid["tables"][table][index][field] = replacement
        try:
            validate(invalid)
        except AssertionError:
            continue
        raise AssertionError("Invalid native observation accepted: " + label)
    swapped = copy.deepcopy(facts)
    rows = swapped["tables"]["native-unit-candidate-results.csv"]
    other = 40 if county == "Elk" else 4
    assert rows[0]["votes"] != rows[other]["votes"]
    rows[0]["votes"], rows[other]["votes"] = rows[other]["votes"], rows[0]["votes"]
    try:
        validate(swapped)
    except AssertionError:
        pass
    else:
        raise AssertionError("Unit choice identity swap accepted.")
    print(f'{county}: {len(cases) + 1} focused participation/provenance/identity rejection cases pass.')


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
    validate(facts)
    if args.self_test:
        self_test(facts)
    if args.verify:
        with tempfile.TemporaryDirectory() as temporary:
            reproduced = Path(temporary) / "query"
            render(facts, reproduced)
            assert {path.name for path in reproduced.iterdir()} == {path.name for path in args.verify.iterdir()}
            for path in reproduced.iterdir():
                assert path.read_bytes() == (args.verify / path.name).read_bytes(), path.name
        print("Every entire file and deterministic ZIP reproduces byte-identically offline.")
    else:
        render(facts, args.output)


if __name__ == "__main__":
    main()
