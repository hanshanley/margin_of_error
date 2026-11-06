"""Reproduce the complete scoped Perry participation query offline, without source templates."""

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
    "native-unit-participation.csv": 31,
    "county-candidate-results.csv": 104,
    "county-contest-accounting.csv": 8,
    "native-candidate-mode-totals.csv": 32,
    "native-participation-mode-availability.csv": 4,
    "native-reporting-statistics.csv": 32,
    "native-source-pages.csv": 24,
    "native-source-declarations.csv": 2,
    "native-source-receipts.csv": 3,
    "native-party-availability.csv": 13,
    "native-derived-rate-checks.csv": 32,
    "native-derived-contest-sums.csv": 4,
    "native-unit-candidate-availability.csv": 31,
}
ARCHIVE = "complete-perry-county-native-query-01.zip"
REVIEW_SHA256 = "05c0b7971fcdd20d77eafd3b5441e667a8e5f0af2667a550073f92009cdeb919"
SOURCES = {
    "perry-parent.html": "9bde2092d508fed5ad28e60d43ac94c290fbdd4e5cebd860b402d594d3a98a95",
    "perry-summary.pdf": "88ae157b2d96060d81033e38ecfb8c5d6cdbe52d54fd34e35928d5f0cb3834b8",
    "perry-statement.pdf": "8a6963e354fc507ee273417d12c41c8438748dc7b1050298949373424b46fbd3",
}
CLOCKS = {"summary": "2026-11-03 22:49:06", "statement": "2026-11-03 22:30:24"}
MODES = ("Votes", "ED", "MI", "PR")


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def validate(facts):
    tables = facts["tables"]
    assert set(tables) == set(TABLES)
    assert all(len(tables[name]) == count for name, count in TABLES.items())
    assert (facts["year"], facts["state_code"], facts["county"]) == (2026, "PA", "Perry")
    assert facts["maps_approved"] is False and facts["candidate_votes_are_not_participation"] is True
    assert facts["native_parties_inferred"] is False
    county = tables["county-participation.csv"][0]
    assert county["native_participation_measure_literal"] == "Total Ballots Cast"
    assert (county["ballots_cast"], county["registered_voters"], county["native_printed_turnout"]) == (18064, 31391, "57.55%")
    assert county["registered_turnout_pct"] == "57.55"
    assert county["source_report"] == "statement" and county["source_page"] == 23
    assert county["native_fips"] == "" and county["maps_approved"] is False
    assert all(county[field] == "" for field in ("election_day_ballots", "mail_ballots", "provisional_ballots"))
    assert county["reported_precincts"] == county["total_precincts"] == 31
    assert county["counting_complete"] is False
    units = tables["native-unit-participation.csv"]
    assert len({row["unit_literal"] for row in units}) == 31
    assert all(row["unit_literal"] != "All Precincts" for row in units)
    assert sum(row["ballots_cast"] for row in units) == county["ballots_cast"]
    assert sum(row["registered_voters"] for row in units) == county["registered_voters"]
    for row in units:
        assert row["reported_precincts"] == row["total_precincts"] == 1
        assert row["counting_complete"] is False
        assert row["direct_native_header_visual_review"] is True
        assert row["four_native_contest_headers_agree"] is True
        assert type(row["ballots_cast"]) is int and type(row["registered_voters"]) is int
        assert row["registered_voters"] > 0
        assert f'{100 * row["ballots_cast"] / row["registered_voters"]:.2f}%' == row["native_printed_turnout"]
        assert row["registered_turnout_pct"] + "%" == row["native_printed_turnout"]
    for name in TABLES:
        for row in tables[name]:
            if "source_report" in row:
                report = row["source_report"]
                assert row["source_update_literal"] == CLOCKS[report] and row["declared_timezone"] == ""
                assert row["source_status_literal"] == "" and row["parent_status_literal"] == "Unofficial"
                assert row["source_sha256"] == SOURCES["perry-" + report + ".pdf"]
    candidates = tables["county-candidate-results.csv"]
    assert all(row["literal_party"] == "" and type(row["votes"]) is int and row["votes"] >= 0 for row in candidates)
    reports = {}
    for report in ("summary", "statement"):
        rows = [row for row in candidates if row["source_report"] == report]
        reports[report] = {
            (row["contest_literal"], row["choice_literal"], row["choice_kind"], row["counting_mode_literal"]): row["votes"]
            for row in rows
        }
        assert len(reports[report]) == len(rows) == 52
        for row in rows:
            vector = [item["votes"] for item in rows
                      if (item["contest_literal"], item["choice_literal"]) == (row["contest_literal"], row["choice_literal"])]
            assert len(vector) == 4 and vector[0] == sum(vector[1:])
        for account in [row for row in tables["county-contest-accounting.csv"] if row["source_report"] == report]:
            contest_rows = [row for row in rows if row["contest_literal"] == account["contest_literal"]]
            assert account["mode_accounting_available"] is False
            assert account["ballots_cast"] == 18064
            assert account["native_overvoted_ballots"] == account["native_overvotes"]
            assert account["native_total_candidate_votes"] + account["native_overvotes"] + account["native_undervotes"] == 18064
            for mode in MODES:
                total = next(row for row in tables["native-candidate-mode-totals.csv"]
                             if (row["source_report"], row["contest_literal"], row["counting_mode_literal"])
                             == (report, account["contest_literal"], mode))
                assert sum(row["votes"] for row in contest_rows if row["counting_mode_literal"] == mode) == total["native_candidate_vote_total"]
                if mode == "Votes":
                    assert total["native_candidate_vote_total"] == account["native_total_candidate_votes"]
    assert reports["summary"] == reports["statement"]
    modes = tables["native-participation-mode-availability.csv"]
    assert modes[0]["counting_mode_label"] == "Total" and modes[0]["ballots_cast"] == 18064
    assert modes[0]["native_participation_mode_reported"] is True
    assert [row["counting_mode_label"] for row in modes[1:]] == ["ED", "MI", "PR"]
    assert all(row["ballots_cast"] == "" and row["native_participation_mode_reported"] is False for row in modes[1:])
    assert all(row["party_available"] is False and row["literal_party"] == "" for row in tables["native-party-availability.csv"])
    assert all(row["query_includes_unit_candidates"] is False for row in tables["native-unit-candidate-availability.csv"])
    for report, count in (("summary", 1), ("statement", 23)):
        pages = [row for row in tables["native-source-pages.csv"] if row["source_report"] == report]
        assert [row["source_page"] for row in pages] == list(range(1, count + 1))
        assert all((row["native_rotation"], row["correctly_rotated_entire_image_width"],
                    row["correctly_rotated_entire_image_height"]) == (270, 1836, 2376) for row in pages)
    assert {row["file"]: row["sha256"] for row in facts["source_receipts"]} == SOURCES
    assert all(row["status"] == 200 and row["bytes"] > 0 for row in facts["source_receipts"])
    for declaration in tables["native-source-declarations.csv"]:
        receipt = next(row for row in facts["source_receipts"] if row["file"] == "perry-" + declaration["role"] + ".pdf")
        assert declaration["url"] == receipt["requested_url"]
    assert digest(facts) == REVIEW_SHA256


def self_test(facts):
    validate(facts)
    cases = (
        ("candidate votes substituted as ballots", "county-participation.csv", 0, "ballots_cast", 17965),
        ("candidate ED total substituted as ballot mode", "county-participation.csv", 0, "election_day_ballots", 15276),
        ("candidate PR zero substituted as participation zero", "county-participation.csv", 0, "provisional_ballots", 0),
        ("missing participation mode filled", "native-participation-mode-availability.csv", 3, "ballots_cast", 0),
        ("party inferred from candidate", "county-candidate-results.csv", 0, "literal_party", "DEM"),
        ("reported units treated as completed counting", "native-reporting-statistics.csv", 0, "counting_complete", True),
        ("source native FIPS invented", "county-participation.csv", 0, "native_fips", "42099"),
        ("source map approval invented", "county-participation.csv", 0, "maps_approved", True),
        ("unit candidate transcription falsely approved", "native-unit-candidate-availability.csv", 0, "query_includes_unit_candidates", True),
        ("summary clock borrowed by statement", "native-unit-participation.csv", 0, "source_update_literal", CLOCKS["summary"]),
        ("native timezone invented", "county-participation.csv", 0, "declared_timezone", "America/New_York"),
        ("parent unofficial status attributed to PDF", "county-participation.csv", 0, "source_status_literal", "Unofficial"),
        ("native registration changed", "native-unit-participation.csv", 0, "registered_voters", 138),
        ("native rate repaired", "native-unit-participation.csv", 0, "native_printed_turnout", "62.05%"),
        ("county overvotes erased", "county-contest-accounting.csv", 0, "native_overvotes", 0),
        ("declared original URL changed", "native-source-declarations.csv", 1, "url", "https://perryco.org/other.pdf"),
    )
    invalids = []
    for label, table, index, field, replacement in cases:
        invalid = copy.deepcopy(facts)
        invalid["tables"][table][index][field] = replacement
        invalids.append((label, invalid))
    swapped = copy.deepcopy(facts)
    units = swapped["tables"]["native-unit-participation.csv"]
    for field in ("ballots_cast", "registered_voters", "native_printed_turnout", "registered_turnout_pct"):
        units[0][field], units[1][field] = units[1][field], units[0][field]
    invalids.append(("unit counts swapped with county sums unchanged", swapped))
    aggregate = copy.deepcopy(facts)
    aggregate["tables"]["native-unit-participation.csv"].append(copy.deepcopy(aggregate["tables"]["county-participation.csv"][0]))
    invalids.append(("county aggregate added to actual units", aggregate))
    source = copy.deepcopy(facts)
    source["source_receipts"][0]["sha256"] = "0" * 64
    invalids.append(("original source hash substituted", source))
    for label, invalid in invalids:
        try:
            validate(invalid)
        except AssertionError:
            continue
        raise AssertionError("Invalid reviewed fact accepted: " + label)
    return [label for label, invalid in invalids]


def render(facts, directory):
    rejected = self_test(facts)
    directory.mkdir(parents=True, exist_ok=False)
    for name, rows in facts["tables"].items():
        with (directory / name).open("x", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    with (directory / "source-records.json.gz").open("xb") as target:
        with gzip.GzipFile(fileobj=target, mode="wb", filename="", mtime=0) as compressed:
            compressed.write(json_bytes(facts))
    audit = dict(
        scope=facts["scope"], table_rows=TABLES, complete_native_units=31,
        native_ballots_cast=18064, native_registered_voters=31391, native_printed_turnout="57.55%",
        all31_participation_headers_directly_visually_reviewed=True,
        all124_unit_contest_participation_headers_agree=True,
        four_separate_county_aggregate_headers_not_added_to_units=True,
        complete_county_choice_vectors_match_summary_and_aggregate=True,
        complete_county_contest_vote_overvote_undervote_accounting_reconciles=True,
        independent_ocr_entire_pages=24,
        full_unit_candidate_tables_outside_reviewed_numerical_query_scope=True,
        missing_native_ballot_mode_splits_not_inferred_from_candidate_modes=True,
        missing_native_parties_not_inferred=True,
        parent_unofficial_status_not_attributed_to_pdf=True,
        distinct_native_report_clocks_preserved_without_timezone=True,
        no_certification_or_completed_counting_claim=True,
        native_source_fips="", maps_approved=False,
        rejected_changes=rejected, reviewed_facts_sha256=REVIEW_SHA256,
        original_documents_images_ocr_and_presentation_templates="Private; not redistributed.",
        reproduction="Python standard library only; all native facts are frozen, not a live source refresh.")
    (directory / "audit.json").write_bytes(json_bytes(audit))
    (directory / "source-receipts.json").write_bytes(json_bytes(facts["source_receipts"]))
    (directory / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    checksums = {path.name: dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in sorted(directory.iterdir())}
    (directory / "checksums.json").write_bytes(json_bytes(checksums))
    with zipfile.ZipFile(directory / ARCHIVE, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(directory.iterdir()):
            if path.name != ARCHIVE:
                info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        facts = json.loads(gzip.decompress((args.verify / "source-records.json.gz").read_bytes()))
        with tempfile.TemporaryDirectory() as temporary:
            reproduced = Path(temporary) / "query"
            render(facts, reproduced)
            assert {path.name for path in reproduced.iterdir()} == {path.name for path in args.verify.iterdir()}
            for path in reproduced.iterdir():
                assert path.read_bytes() == (args.verify / path.name).read_bytes(), path.name
        print("All 20 files, 14 complete CSV tables, 19 complete ZIP members and 19 rejection cases reproduce offline.")
    else:
        assert args.source and args.output
        data = args.source.read_bytes()
        facts = json.loads(gzip.decompress(data) if args.source.suffix == ".gz" else data)
        render(facts, args.output)


if __name__ == "__main__":
    main()
