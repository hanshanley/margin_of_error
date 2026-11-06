"""Reproduce the complete reviewed Juniata, Mercer or Montour numerical query offline."""

import argparse
import copy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import zipfile


SPECS = {
    "Juniata": dict(
        review="426b96391f338e0d05a93917b3dbf847dd74f484fc8bb2c8b9ab410598291980",
        parent="a6eb82571496f8db68c2934f94e4008a3f54b960f1b1678def13be9501fe28dc",
        summary="0892cac4b4926b21c37e031314cdf9052053e57f5fb0d6d8267d007b85debd00",
        statement="dc53cac0e7d57f1a32c8fa63552501f19266fb8725f53a5507da0cc170ffc73d",
        urls=(
            "https://www.juniatacountypa.gov/238/Latest-Election-Results",
            "https://www.juniatacountypa.gov/DocumentCenter/View/570/2026-General-Election-Unofficial-Summary-PDF",
            "https://www.juniatacountypa.gov/DocumentCenter/View/571/2026-General-Election-Unofficial-Precinct-results-PDF"),
        ballots=[8258, 7160, 1098, 0], registrations=14095, blanks=1, units=18,
        pages=(4, 36), county_contests=5, unit_contests=72,
        clocks=("11/03/2026 10:31 PM", "11/03/2026 10:34 PM"),
        modes=("TOTAL", "Election Day", "Mail Votes", "Provisional Votes")),
    "Mercer": dict(
        review="fe14f95c34ad887027fc9314aeeef9c399ccd0b88d8410f68f39d2c721ce06cb",
        parent="39351d8f7753168e416093a9cc7acd46be8c70da324d2636dcb875139de1dcd8",
        summary="62dd7982282aa5f47a499851064742e83aa59e7c2f8ef30ff3720b40932d9d22",
        statement="c8dde57ee0a8d8f1bce56654a6bd9991dc238412efe6c150219d292b2520a43d",
        urls=(
            "https://www.mercercountypa.gov/election/Election.Results/default.htm",
            "https://www.mercercountypa.gov/election/Election.Results/2026/GENERAL/Summary.pdf",
            "https://www.mercercountypa.gov/election/Election.Results/2026/GENERAL/PRECINCT.pdf"),
        ballots=[39121, 31943, 7178, 0], registrations=72238, blanks=6, units=90,
        pages=(3, 91), county_contests=7, unit_contests=362,
        clocks=("11/05/2026 11:05 AM", "11/05/2026 11:07 AM"),
        modes=("TOTAL", "Election Day", "Absentee", "Provision\nal")),
    "Montour": dict(
        review="7d02454eeac36a7709463f8c76d332376a7528f3af96176f632668afdfcf48dc",
        parent="fb58a50a024f4f16defb56f32c72c925655cd70ffb73a9364f36982ec28705c2",
        summary="4959aac26b5c14906515bd17709b26dfd80eaa7dca96c7ddb17ce2a4faa23818",
        statement="45dd95b833d7601d4f306526260e89772d615d443790c3e07157178d331a8467",
        urls=(
            "https://montourcounty.gov/departments/elections/results",
            "https://montourcounty.gov/getmedia/8fab59c7-7dc9-4879-8e3c-adb2c26d07dd/Unofficial-Election-Summary.pdf",
            "https://montourcounty.gov/getmedia/6d246221-b65e-4675-9ae6-c20bf9e70758/Unofficial-Precinct-Summary.pdf"),
        ballots=[7008, 5554, 1429, 25], registrations=12418, blanks=0, units=15,
        pages=(4, 45), county_contests=3, unit_contests=45,
        clocks=("11/05/2026 10:14AM", "11/05/2026 10:16AM"),
        modes=("TOTAL", "Election Day", "Mail Votes", "Provisional Votes")),
}
TABLES = (
    "county-participation.csv", "county-candidate-results.csv", "county-literal-party-totals.csv",
    "county-contest-accounting.csv", "native-unit-participation.csv",
    "native-unit-participation-modes.csv", "native-unit-candidate-results.csv",
    "native-unit-literal-party-totals.csv", "native-unit-contest-accounting.csv",
    "native-participation-modes.csv", "native-reporting-statistics.csv", "native-source-pages.csv",
    "native-derived-contest-sums.csv", "native-derived-rate-checks.csv",
    "native-source-declarations.csv", "native-write-in-breakdowns.csv",
    "native-unit-write-in-availability.csv",
)


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def archive_name(county):
    return "complete-" + county.lower() + "-county-native-query-01.zip"


def build_tables(facts):
    name = facts["county"]
    spec = SPECS[name]
    reviewed = facts["reviewed_input"]
    assert facts["year"] == 2026 and facts["maps_approved"] is False
    assert facts["reviewed_input_sha256"] == digest(reviewed) == spec["review"]
    receipts = facts["source_receipts"]
    assert len(receipts) == 3
    for role, url in zip(("parent", "summary", "statement"), spec["urls"]):
        receipt = next(row for row in receipts if row["source_report"] == role)
        assert receipt["status"] == 200 and receipt["sha256"] == spec[role]
        assert receipt["requested_url"] == url and receipt["bytes"] > 0
    declarations = facts["source_declarations"]
    assert [row["role"] for row in declarations] == ["summary", "statement"]
    assert [row["url"] for row in declarations] == list(spec["urls"][1:])
    tables = {table: [] for table in TABLES}
    native = reviewed["native"]
    units = {unit["unit"]: unit for unit in reviewed["units"]}
    assert len(units) == spec["units"]
    assert sum(len(unit["contests"]) for unit in units.values()) == spec["unit_contests"]
    county = native["summary"][0]["statistics"]
    assert county["registered_voters"] == spec["registrations"] and county["ballots"] == spec["ballots"]
    assert county["blank_ballots"][0] == spec["blanks"]
    assert sum(unit["statistics"]["registered_voters"] for unit in units.values()) == spec["registrations"]
    for field in ("ballots", "blank_ballots"):
        assert county[field] == [sum(unit["statistics"][field][mode] for unit in units.values())
                                 for mode in range(4)]
    for role, pages in native.items():
        assert len(pages) == spec["pages"][0 if role == "summary" else 1]
        for page in pages:
            meta = dict(source_report=role, source_page=page["physical_page"],
                native_printed_page=page["printed_page"], native_printed_total_pages=page["printed_total_pages"],
                source_status_literal=page["native_status_literal"],
                source_update_literal=page["native_clock_literal"], declared_timezone=page["declared_timezone"])
            assert meta["source_status_literal"] == "UNOFFICIAL RESULTS" and meta["declared_timezone"] == ""
            assert meta["source_update_literal"] == spec["clocks"][0 if role == "summary" else 1]
            unit = page.get("unit", name + " County")
            tables["native-source-pages.csv"].append(dict(
                source_file=name.lower() + "-" + role + ".pdf", source_sha256=spec[role],
                entire_page_token_multisets_match_both_engines=True,
                entire_parsed_page_vectors_match_both_engines=True, all_layout_lines_consumed=True, **meta))
            if "statistics" in page:
                stats = page["statistics"]
                fraction = stats["ballots"][0] * 100 / stats["registered_voters"]
                if role == "summary":
                    reports = {row["label"]: row for row in page["native_reporting"]}
                    tables["county-participation.csv"].append(dict(year=2026, state_code="PA", county=name,
                        native_participation_measure_literal="Ballots Cast - Total", ballots_cast=stats["ballots"][0],
                        registered_voters=stats["registered_voters"], native_printed_turnout=stats["printed_turnout"],
                        election_day_ballots=stats["ballots"][1], mail_ballots=stats["ballots"][2],
                        native_mail_mode_literal=spec["modes"][2], provisional_ballots=stats["ballots"][3],
                        native_provisional_mode_literal=spec["modes"][3], blank_ballots=stats["blank_ballots"][0],
                        registered_turnout_pct=fraction,
                        reported_precincts=reports["Election Day Precincts Reporting"]["total_fraction"][0],
                        total_precincts=reports["Election Day Precincts Reporting"]["total_fraction"][1],
                        complete_precincts=reports["Precincts Complete"]["total_fraction"][0],
                        partially_reported_precincts=reports["Precincts Partially Reported"]["total_fraction"][0],
                        complete_counting=False, source_fips="", maps_approved=False, **meta))
                    for report in page["native_reporting"]:
                        tables["native-reporting-statistics.csv"].append(dict(statistic_literal=report["label"],
                            native_total_numerator=report["total_fraction"][0],
                            native_total_denominator=report["total_fraction"][1],
                            native_election_day_column=report["mode_columns"][0],
                            native_mail_column=report["mode_columns"][1], native_mail_heading=spec["modes"][2],
                            native_provisional_column=report["mode_columns"][2],
                            native_provisional_heading=spec["modes"][3], **meta))
                else:
                    tables["native-unit-participation.csv"].append(dict(unit_literal=unit,
                        registered_voters=stats["registered_voters"], ballots_cast=stats["ballots"][0],
                        blank_ballots=stats["blank_ballots"][0], native_printed_turnout=stats["printed_turnout"],
                        registered_turnout_pct=fraction, **meta))
                for mode, label in enumerate(spec["modes"]):
                    table = "native-participation-modes.csv" if role == "summary" else "native-unit-participation-modes.csv"
                    tables[table].append(dict(unit_literal=unit, counting_mode_literal=label,
                        ballots_cast=stats["ballots"][mode], blank_ballots=stats["blank_ballots"][mode],
                        registered_voters=stats["registered_voters"] if mode == 0 else "",
                        native_printed_turnout=stats["printed_turnout"] if mode == 0 else "", **meta))
                tables["native-derived-rate-checks.csv"].append(dict(unit_literal=unit,
                    native_ballots_cast=stats["ballots"][0], native_registered_voters=stats["registered_voters"],
                    native_printed_turnout=stats["printed_turnout"], calculated_fraction_pct=fraction,
                    calculated_rounded_fraction=stats["derived_registered_voter_fraction_percent"],
                    rounded_fraction_matches_native=stats["printed_fraction_matches_two_decimal_derivation"], **meta))
            for contest in page["contests"]:
                prefix = "county-" if role == "summary" else "native-unit-"
                rows = contest["rows"]
                by_label = {row["label"]: row for row in rows}
                choices = [row for row in rows if row["kind"] in
                           ("candidate", "write_in_total", "ballot_question_choice")]
                for row in rows:
                    assert row["vector"][0] == sum(row["vector"][1:])
                    for mode, label in enumerate(spec["modes"]):
                        if row["kind"] in ("candidate", "write_in_total", "ballot_question_choice"):
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
                            tables["native-write-in-breakdowns.csv"].append(dict(unit_literal=unit,
                                contest_literal=contest["title"], choice_literal=row["label"], choice_kind=row["kind"],
                                counting_mode_literal=label, votes=row["vector"][mode],
                                accounting_role="Native breakdown of Write-In Totals; do not add twice.", **meta))
                if role == "statement" and "Write-In Totals" in by_label:
                    detail = [row for row in rows if row["kind"] in ("named_write_in", "unassigned_write_in")]
                    tables["native-unit-write-in-availability.csv"].append(dict(unit_literal=unit,
                        contest_literal=contest["title"], native_breakdown_present=bool(detail),
                        named_identities_reported=any(row["kind"] == "named_write_in" for row in detail),
                        unassigned_write_in_votes=by_label["Not Assigned"]["vector"][0]
                        if "Not Assigned" in by_label else "",
                        missingness_role="Native absent breakdown remains absent; native names/spellings not harmonized.",
                        **meta))
                for mode, label in enumerate(spec["modes"]):
                    counted = sum(row["vector"][mode] for row in choices)
                    votes = by_label["Total Votes Cast"]["vector"][mode]
                    electorate = by_label["Contest Totals"]["vector"][mode]
                    over = by_label["Overvotes"]["vector"][mode] if "Overvotes" in by_label else ""
                    under = by_label["Undervotes"]["vector"][mode] if "Undervotes" in by_label else ""
                    assert counted == votes
                    if over != "":
                        assert votes + over + under == electorate
                    else:
                        assert name == "Mercer" and under == "" and electorate >= votes
                    if role == "statement":
                        assert electorate == units[unit]["statistics"]["ballots"][mode]
                    tables[prefix + "contest-accounting.csv"].append(dict(unit_literal=unit,
                        contest_literal=contest["title"], counting_mode_literal=label,
                        native_total_votes_cast=votes, native_overvotes=over, native_undervotes=under,
                        native_contest_totals=electorate, derived_sum_of_choice_votes=counted,
                        derived_unclassified_contest_minus_valid_votes=electorate-votes if over == "" else "",
                        electorate_scope="Native participating-unit contest electorate, not necessarily all county ballots.",
                        **meta))
    for row in tables["county-candidate-results.csv"]:
        actual = [unit for unit in tables["native-unit-candidate-results.csv"]
                  if all(unit[field] == row[field] for field in
                         ("contest_literal", "literal_party", "choice_literal", "choice_kind", "counting_mode_literal"))]
        assert actual and sum(unit["votes"] for unit in actual) == row["votes"]
    for contest in reviewed["reconciliations"]:
        tables["native-derived-contest-sums.csv"].append(dict(contest_literal=contest["contest"],
            native_units=contest["selected_unit_count"], total=contest["native_contest_electorate"][0],
            election_day=contest["native_contest_electorate"][1], mail=contest["native_contest_electorate"][2],
            native_mail_mode_literal=spec["modes"][2], provisional=contest["native_contest_electorate"][3],
            all_native_choice_and_accounting_vectors_match=True))
    for declaration in declarations:
        tables["native-source-declarations.csv"].append(dict(source_report=declaration["role"],
            declared_label_literal=declaration["label"], declared_url=declaration["url"],
            declaration_scope="Exact parent anchor; native election/stage independently confirmed in every report page."))
    assert len(tables["county-participation.csv"]) == 1
    assert len(tables["county-contest-accounting.csv"]) == spec["county_contests"] * 4
    return tables


def validate(facts):
    assert facts["tables"] == build_tables(facts)


def render(facts, destination):
    validate(facts)
    name = facts["county"]
    spec = SPECS[name]
    destination.mkdir(exist_ok=False)
    for filename, rows in facts["tables"].items():
        fields = list(rows[0]) if rows else [
            "unit_literal", "contest_literal", "choice_literal", "choice_kind", "counting_mode_literal",
            "votes", "accounting_role", "source_report", "source_page", "native_printed_page",
            "native_printed_total_pages", "source_status_literal", "source_update_literal", "declared_timezone"]
        assert rows or filename == "native-write-in-breakdowns.csv" and name == "Mercer"
        with (destination / filename).open("x", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    with (destination / "source-records.json.gz").open("xb") as target:
        with gzip.GzipFile(fileobj=target, mode="wb", filename="", mtime=0) as compressed:
            compressed.write(json_bytes(facts))
    stats = facts["reviewed_input"]["native"]["summary"][0]["statistics"]
    audit = dict(county=name, year=2026, table_rows={key: len(rows) for key, rows in facts["tables"].items()},
        native_ballots_cast=spec["ballots"][0], native_registered_voters=spec["registrations"],
        usable_registered_voter_fraction=spec["ballots"][0] / spec["registrations"],
        native_printed_turnout=stats["printed_turnout"],
        native_election_day_ballots=spec["ballots"][1], native_mail_ballots=spec["ballots"][2],
        native_mail_mode_literal=spec["modes"][2], native_provisional_ballots=spec["ballots"][3],
        native_provisional_mode_literal=spec["modes"][3], blank_ballots_already_included=spec["blanks"],
        native_precincts_complete=0, native_precincts_partial=spec["units"],
        complete_reviewed_native_units=spec["units"], complete_county_contests=spec["county_contests"],
        complete_unit_contests=spec["unit_contests"], both_native_clocks_preserved=True,
        entire_pages_independently_reviewed_both_engines=sum(spec["pages"]), all_layout_lines_consumed=True,
        native_overvotes_and_undervotes_absent=name == "Mercer",
        montour_reporting_counter_contradictions_preserved=name == "Montour",
        printed_rate_discrepancies=facts["reviewed_input"]["printed_fraction_discrepancies"],
        restricted_electorates=facts["reviewed_input"]["reconciliations"][3:],
        literal_parties_and_unharmonized_native_write_in_names_preserved=True,
        complete_counting=False, maps_approved=False, native_source_fips="",
        no_certification_complete_counting_geometry_or_demographic_turnout_claim=True,
        original_documents_and_presentation_templates="Private; not redistributed in this factual query.")
    for filename, value in (("audit.json", audit), ("source-receipts.json", facts["source_receipts"])):
        (destination / filename).write_bytes(json_bytes(value))
    (destination / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    checksums = {path.name: dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in sorted(destination.iterdir())}
    (destination / "checksums.json").write_bytes(json_bytes(checksums))
    with zipfile.ZipFile(destination / archive_name(name), "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(destination.iterdir()):
            if path.name == archive_name(name):
                continue
            info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def self_test(facts):
    cases = [
        ("candidate votes substituted as ballots", "county-participation.csv", "ballots_cast", 1),
        ("blank ballots double counted", "county-participation.csv", "ballots_cast",
         facts["tables"]["county-participation.csv"][0]["ballots_cast"] + 1),
        ("registration denominator invented", "county-participation.csv", "registered_voters", 0),
        ("provisional column erased", "county-participation.csv", "provisional_ballots", ""),
        ("counting declared complete", "county-participation.csv", "complete_counting", True),
        ("partial reporting declared complete", "county-participation.csv", "complete_precincts", 90),
        ("timezone invented", "county-participation.csv", "declared_timezone", "America/New_York"),
        ("native status certified", "county-participation.csv", "source_status_literal", "Certified"),
        ("source map approval invented", "county-participation.csv", "maps_approved", True),
        ("source FIPS invented", "county-participation.csv", "source_fips", "42000"),
        ("native party normalized", "county-candidate-results.csv", "literal_party", "Democratic"),
        ("native clock harmonized", "county-participation.csv", "source_update_literal", "2026-11-06"),
        ("printed rate replaced", "county-participation.csv", "native_printed_turnout", "0.00%"),
        ("mode label harmonized", "county-participation.csv", "native_mail_mode_literal", "Early voting"),
        ("restricted electorate replaced", "county-contest-accounting.csv", "native_contest_totals", 0),
        ("unit registration replaced", "native-unit-participation.csv", "registered_voters", 0),
        ("reporting vector corrected", "native-reporting-statistics.csv", "native_total_numerator", 0),
    ]
    if facts["county"] == "Mercer":
        cases.extend([
            ("missing overvotes inferred", "county-contest-accounting.csv", "native_overvotes", 0),
            ("missing undervotes inferred", "county-contest-accounting.csv", "native_undervotes", 0),
        ])
    else:
        cases.append(("write-in literal harmonized", "native-write-in-breakdowns.csv", "choice_literal", "Other"))
    rejected = []
    for label, table, field, value in cases:
        changed = copy.deepcopy(facts)
        assert changed["tables"][table][0][field] != value, label
        changed["tables"][table][0][field] = value
        try:
            validate(changed)
        except AssertionError:
            rejected.append(label)
        else:
            raise AssertionError("Accepted " + label)
    changed = copy.deepcopy(facts)
    changed["reviewed_input"]["native"]["summary"][0]["statistics"]["ballots"][0] += 1
    try:
        validate(changed)
    except AssertionError:
        rejected.append("frozen native input changed")
    else:
        raise AssertionError("Accepted changed native input")
    return rejected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_records", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    facts = json.loads(gzip.decompress(args.source_records.read_bytes()))
    rejections = self_test(facts)
    render(facts, args.output)
    print(facts["county"], len(rejections), "focused rejection cases; complete offline query rendered")
