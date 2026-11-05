import csv
import copy
import gzip
import importlib.util
import io
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import openpyxl
import pytest


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


methods = module("collect-voting-methods")
context = module("collect-participation-context")
local = module("build-local-participation")
current_local = module("collect-current-participation")
current_precincts = module("build-current-precincts")
precinct_results = module("build-precinct-results")
precinct_coverage = module("build-precinct-coverage")
additional_precincts = module("build-additional-precinct-results")
historical_sources = module("acquire-historical-precinct-sources")
nd_review = module("review-north-dakota-precinct-results")
nd_maps = module("build-north-dakota-precinct-results")
vt_review = module("review-vermont-precinct-results")
vt_maps = module("build-vermont-precinct-results")
id_review = module("review-idaho-precinct-results")
id_maps = module("build-idaho-precinct-results")
sd_review = module("review-south-dakota-precinct-results")
ak_review = module("review-alaska-precinct-results")
ak_boundaries = module("review-alaska-precinct-boundaries")
hi_review = module("review-hawaii-precinct-results")
hi_historical = module("archive-hawaii-historical-sources")
ct_originals = module("archive-connecticut-election-sources")
ri_review = module("review-rhode-island-precinct-results")
ri_maps = module("build-rhode-island-precinct-results")
fl_monroe = module("review-florida-monroe-precinct-results")
mo_christian = module("review-missouri-christian-precinct-results")
clark_originals = module("archive-clark-historical-sources")
dc_maps = module("build-dc-precinct-results")
boston_maps = module("build-boston-precinct-results")
worcester_review = module("review-worcester-precinct-results")
wa_review = module("review-washington-precinct-results")
wa_maps = module("build-washington-precinct-results")
house_county_sources = module("acquire-house-county-results")
house_county_review = module("review-house-county-results")
me_pa_participation = module("review-maine-pennsylvania-participation")
wy_originals = module("archive-wyoming-election-sources")
wy_native_text = module("recover-wyoming-native-pdf-text")
wy_review = module("review-wyoming-precinct-results")
wy_2022 = module("review-wyoming-2022-native-results")
va_2026 = module("review-virginia-2026-native-results")
va_localities = module("review-virginia-2026-locality-results")
va_geometry = module("review-virginia-2026-reference-geometry")
va_maps = module("build-virginia-2026-precinct-results")
ar_2026 = module("review-arkansas-2026-native-results")
al_2026 = module("review-alabama-2026-native-results")
ar_geometry = module("review-arkansas-2026-reference-geometry")
az_2026 = module("review-arizona-2026-native-results")
az_maricopa = module("build-arizona-maricopa-precinct-results")
az_pima = module("review-arizona-pima-2026-native-results")
mi_2026 = module("review-michigan-2026-native-results")
ky_2026 = module("review-kentucky-2026-native-results")
ia_consolidated = module("review-iowa-2026-consolidated-results")
ia_linn = module("review-iowa-linn-2026-native-results")


def iowa_linn_words(values, edges=(198, 238, 278)):
    return [(edge - 18, 176, edge, 187, value) for edge, value in zip(edges, values)]


def test_iowa_linn_columns_keep_missing_registrations_zero_and_separate_percent():
    box = (20, 178, 100, 189)
    assert ia_linn.cells(iowa_linn_words(["1,000"]), box) == ([1000, None, None], None)
    words = iowa_linn_words(["3", "0", "3"], (198, 278, 318))
    words.append((210, 176, 238, 187, "12.34%"))
    assert ia_linn.cells(words, box, contest=True) == ([3, 0, 3], "12.34%")
    with pytest.raises(ValueError, match="Missing"):
        ia_linn.vector([3, None, 3], "ballot")


@pytest.mark.parametrize("change,error", [
    ("duplicate", "Duplicate"), ("position", "position"),
    ("malformed", "integer"), ("percent_as_count", "percentage"),
])
def test_iowa_linn_columns_reject_unreviewed_layout_or_counts(change, error):
    words = iowa_linn_words(["3", "0", "3"], (198, 278, 318))
    if change == "duplicate":
        words.append(words[0])
    elif change == "position":
        words[0] = (180, 176, 202, 187, "3")
    elif change == "malformed":
        words[0] = (180, 176, 198, 187, "1,00")
    else:
        words.append((210, 176, 238, 187, "3"))
    with pytest.raises(ValueError, match=error):
        ia_linn.cells(words, (20, 178, 100, 189), contest=True)


def iowa_linn_tables():
    stats = dict(unit="A", registered=[20, None, None], ballots=[9, 6, 3], blank=[1, 1, 0])
    counts = [[3, 2, 1], [4, 3, 1], [1, 1, 0], [0, 0, 0], [0, 0, 0]]
    house = dict(unit="A", options={label: dict(counts=value) for label, value in zip(ia_linn.OPTIONS, counts)},
                 total=[8, 6, 2])
    other_stats, other_house = copy.deepcopy(stats), copy.deepcopy(house)
    other_stats["unit"] = other_house["unit"] = "B"
    county, county_house = copy.deepcopy(stats), copy.deepcopy(house)
    county["unit"] = county_house["unit"] = "Linn County"
    for field in ("registered", "ballots", "blank"):
        county[field] = [value * 2 if value is not None else None for value in county[field]]
    county_house["total"] = [value * 2 for value in county_house["total"]]
    for option in county_house["options"].values():
        option["counts"] = [value * 2 for value in option["counts"]]
    return ([county], [county_house]), ([stats, other_stats], [house, other_house])


def test_iowa_linn_reconciles_every_native_registration_and_option_mode():
    summary, detail = iowa_linn_tables()
    ia_linn.reconcile(summary, detail)


@pytest.mark.parametrize("change,error", [
    ("duplicate_unit", "Duplicate"), ("missing_ballot", "ballots"),
    ("invented_mode_registration", "registered"), ("candidate_mode", "candidate/mode"),
])
def test_iowa_linn_reconciliation_fails_closed(change, error):
    summary, detail = iowa_linn_tables()
    if change == "duplicate_unit":
        detail[0][1]["unit"] = detail[1][1]["unit"] = "A"
    elif change == "missing_ballot":
        detail[0][1]["ballots"][1] = None
    elif change == "invented_mode_registration":
        detail[0][1]["registered"][1] = 0
    else:
        detail[1][1]["options"]["REP Joe Mitchell"]["counts"][1] += 1
    with pytest.raises(ValueError, match=error):
        ia_linn.reconcile(summary, detail)


def iowa_consolidated_rows():
    return [
        dict(state="IA", level=level, county=county,
             contest="United States Representative District 2",
             candidate=name, party=party, votes=str(votes), contestTotalVotes="12")
        for level, county in [("county", "Linn"), ("state", "")]
        for name, party, votes in [("D", "DEM", 7), ("R", "REP", 4), ("Write-in", "", 1)]
    ]


def test_iowa_consolidated_retains_write_ins_and_native_zero():
    rows = iowa_consolidated_rows()
    selected, tables, _ = ia_consolidated.review_house_rows(rows)
    assert len(selected) == 6
    assert tables["county"][0]["other_and_write_in_votes"] == 1
    assert tables["county"][0]["dem_minus_rep_pct"] == 25
    for row in rows:
        row["votes"] = row["contestTotalVotes"] = "0"
    _, tables, _ = ia_consolidated.review_house_rows(rows)
    assert tables["county"][0]["total_candidate_votes"] == 0
    assert tables["county"][0]["dem_minus_rep_pct"] is None


@pytest.mark.parametrize("change,error", [
    ("missing", "Missing"), ("duplicate", "Duplicate"),
    ("native_total", "native contest total"), ("state_vector", "statewide district"),
])
def test_iowa_consolidated_rejects_missing_duplicate_or_unreconciled_vectors(change, error):
    rows = iowa_consolidated_rows()
    if change == "missing":
        rows[0]["votes"] = ""
    elif change == "duplicate":
        rows.append(dict(rows[0]))
    elif change == "native_total":
        rows[0]["contestTotalVotes"] = "13"
    else:
        rows[3]["votes"], rows[4]["votes"] = "6", "5"
    with pytest.raises(ValueError, match=error):
        ia_consolidated.review_house_rows(rows)


def kentucky_words(values):
    return [(edge - 18, 176, edge, 184, value)
            for edge, value in zip(ky_2026.EDGES, values)]


def test_kentucky_numeric_columns_preserve_zero_and_reject_missing_cells():
    words = kentucky_words(["1,000", "0", "2", "3", "1,005"])
    assert ky_2026.count_cells(words) == [1000, 0, 2, 3, 1005]
    assert ky_2026.count_cells([]) == [None] * 5
    with pytest.raises(ValueError, match="Missing"):
        ky_2026.count_cells(words[:-1])


@pytest.mark.parametrize("change,error", [
    ("duplicate", "Duplicate"), ("position", "position"),
    ("malformed", "integer"), ("mode_sum", "total differs"),
])
def test_kentucky_numeric_columns_fail_closed(change, error):
    words = kentucky_words(["1", "0", "2", "3", "6"])
    if change == "duplicate":
        words.append(words[0])
    elif change == "position":
        words[0] = (240, 176, 267, 184, "1")
    elif change == "malformed":
        words[0] = (240, 176, ky_2026.EDGES[0], 184, "1,00")
    else:
        words[-1] = (620, 176, ky_2026.EDGES[-1], 184, "7")
    with pytest.raises(ValueError, match=error):
        ky_2026.count_cells(words)


@pytest.mark.parametrize("change,error", [
    ("duplicate_option", "Duplicate"), ("missing_total", "totals"),
    ("reordered_totals", "totals"), ("mode_conflict", "sum differs"),
])
def test_kentucky_contests_require_every_option_mode_and_printed_total(change, error):
    rows = [
        dict(choice="A", party="REP", counts=[2, 0, 1, 1, 4]),
        dict(choice="B", party="DEM", counts=[0, 1, 0, 0, 1]),
        dict(choice="Cast Votes:", party="", counts=[2, 1, 1, 1, 5]),
        dict(choice="Undervotes:", party="", counts=[0] * 5),
        dict(choice="Overvotes:", party="", counts=[0] * 5),
    ]
    if change == "duplicate_option":
        rows[1]["choice"] = "A"
    elif change == "missing_total":
        rows.pop()
    elif change == "reordered_totals":
        rows[-1], rows[-2] = rows[-2], rows[-1]
    else:
        rows[0]["counts"] = [1, 1, 1, 1, 4]
    with pytest.raises(ValueError, match=error):
        ky_2026.finish_contest(dict(contest="Example", source_pdf_page=1, rows=rows))


@pytest.fixture(scope="module")
def kentucky_source():
    return Path(__file__).parents[1] / "data/precinct-source-reviews/20261105/KY-2026-native-county-counts-01/source"


def test_kentucky_complete_report_retains_unnamed_zero_option_and_separate_ballots(kentucky_source):
    contests, (ballots, reporting), house = ky_2026.review_pdf(
        (kentucky_source / ky_2026.ORIGINAL).read_bytes())
    assert len(contests) == 36 and reporting == "17 of 17 = 100.00%"
    assert sum(len(contest["rows"]) for contest in contests) == 181
    unnamed = [row for contest in contests for row in contest["rows"] if not row["choice"]]
    assert unnamed == [dict(choice="", party="", counts=[0] * 5)]
    assert ballots == 31918 and house["rows"][-3]["counts"][4] == 31521
    assert sum(row["counts"][4] for row in house["rows"][-3:]) == ballots


def test_kentucky_archive_only_rebuild_preserves_all_counts_and_original(kentucky_source, tmp_path):
    archives = []
    source = kentucky_source
    for name in ["first", "second"]:
        output, archive = tmp_path / name, tmp_path / (name + ".zip")
        audit = ky_2026.build(source, output, archive)
        assert not audit["maps_approved"] and audit["registered_voters"] is None
        participation = list(csv.DictReader((output / "county-participation.csv").open()))
        assert len(participation) == 1 and participation[0]["ballots_cast_total"] == "31918"
        assert participation[0]["registered_voters_total"] == participation[0]["turnout_rate"] == ""
        all_rows = list(csv.DictReader((output / "all-contest-results.csv").open()))
        assert len(all_rows) == len({row["source_row_id"] for row in all_rows}) == 181
        assert sum(row["kind"] == "unnamed_option" for row in all_rows) == 1
        assert (output / "source" / ky_2026.ORIGINAL).read_bytes() == (
            kentucky_source / ky_2026.ORIGINAL).read_bytes()
        archives.append(archive.read_bytes())
        with zipfile.ZipFile(archive) as package:
            checksums = json.loads(package.read("checksums.json"))
            assert set(package.namelist()) == set(checksums) | {"checksums.json"}
            for member, expected in checksums.items():
                raw = package.read(member)
                assert len(raw) == expected["bytes"]
                assert hashlib.sha256(raw).hexdigest() == expected["sha256"]
            if name == "first":
                package.extractall(tmp_path / "extracted")
                source = tmp_path / "extracted/source"
        with pytest.raises(ValueError, match="overwrite"):
            ky_2026.build(kentucky_source, output, tmp_path / "other.zip")
    assert archives[0] == archives[1]


def test_michigan_pdf_cells_align_right_edges_and_keep_missing_distinct_from_zero():
    words = [(178, 121.45, 198, 132.44, "1,061"),
             (218, 121.13, 238, 132.12, "1,005"),
             (274, 121.13, 278, 132.12, "0"),
             (309, 121.13, 318, 132.12, "56")]
    box = (20, 123.45, 88, 134.44)
    assert mi_2026.pdf_cells(words, box) == [1061, 1005, 0, 56]
    assert mi_2026.pdf_cells(words[:1], box) == [1061, None, None, None]
    with pytest.raises(ValueError, match="Duplicate"):
        mi_2026.pdf_cells(words + words[:1], box)
    with pytest.raises(ValueError, match="position"):
        mi_2026.pdf_cells(words + [(320, 121, 325, 132, "1")], box)
    with pytest.raises(ValueError, match="integer"):
        mi_2026.pdf_cells([(178, 121, 198, 132, "1,06")], box)


def bay_example():
    row = dict(precinct="Auburn City, Pct 1", source_pdf_page=1,
        registered_voters_total=10, ballots=[4, 2, 1, 1], blank=[0, 0, 0, 0],
        native_turnout_percent="40.00")
    vectors = [[2, 1, 1, 0], [1, 1, 0, 0], [1, 0, 0, 1]] + [[0] * 4] * 3
    house = dict(precinct=row["precinct"], source_pdf_page=2,
                 candidates=dict(zip(mi_2026.BAY_CANDIDATES, vectors)))
    county, total = copy.deepcopy(row), copy.deepcopy(house)
    county["precinct"] = total["precinct"] = "Bay County"
    return ([county], [total]), ([row], [house])


def test_michigan_bay_counts_are_not_rates_or_inferred_native_ids():
    counts, results = mi_2026.review_bay(*bay_example())
    assert counts[0]["ballots_cast_total"] == results[0]["total_votes"] == 4
    assert counts[0]["turnout_rate"] == counts[0]["native_precinct_id"] == ""
    assert not counts[0]["maps_approved"]
    assert counts[0]["source_row_id"] == "bay:pdf:1"


@pytest.mark.parametrize("change", ["duplicate", "identity", "ballots", "candidate_mode"])
def test_michigan_bay_rejects_incomplete_or_conflicting_unit_reconciliation(change):
    summary, detail = bay_example()
    if change == "duplicate":
        detail[0].append(copy.deepcopy(detail[0][0]))
        detail[1].append(copy.deepcopy(detail[1][0]))
    elif change == "identity":
        detail[1][0]["precinct"] = "Another city, Pct 1"
    elif change == "ballots":
        detail[0][0]["ballots"][1] += 1
    else:
        detail[1][0]["candidates"][mi_2026.BAY_CANDIDATES[0]][2] += 1
    with pytest.raises(ValueError):
        mi_2026.review_bay(summary, detail)


@pytest.fixture(scope="module")
def michigan_isabella_native():
    root = Path(__file__).parents[1] / (
        "data/precinct-source-reviews/20261105/MI-2026-native-county-counts-01/source")
    receipts = json.loads((root / "sources.json").read_text())
    workbook = gzip.decompress(
        (root / receipts["official-isabella-all-results-xlsx"]["file"]).read_bytes())
    payloads = {}
    for folder in ["dashboard-network", "dashboard-followup-network"]:
        for receipt in json.loads((root / folder / "responses.json").read_text()):
            if "/data" in receipt["url"]:
                payloads[folder] = json.loads(
                    gzip.decompress((root / folder / receipt["file"]).read_bytes()))
    return payloads["dashboard-network"], payloads["dashboard-followup-network"], \
        mi_2026.workbook_tables(workbook)


def test_michigan_isabella_preserves_ballot_scope_difference_and_unmatched_zero_rows(
        michigan_isabella_native):
    participation, house, unmatched, audit = mi_2026.review_isabella(*michigan_isabella_native)
    assert sum(row["ballots_cast_total"] for row in participation) > \
        sum(row["house_scope_ballots"] for row in house)
    assert all(row["ballots_cast_total"] == row["registered_voters_total"] == 0
               for row in unmatched)
    assert len(unmatched) == len(participation) - len(house)
    assert all(row["turnout_rate"] == "" and not row["maps_approved"] for row in participation)
    for difference in audit["house_ballot_scope_differences"]:
        row = next(r for r in participation if r["native_precinct_id"] ==
                   difference["native_precinct_id"])
        assert row["ballots_cast_total"] == difference["election_ballots"]
        assert "house_ballots_differ" in row["quality_flags"]


@pytest.mark.parametrize("change, message", [
    ("duplicate", "identities"), ("missing_count", "native count"),
    ("boolean_count", "native count"), ("mode_missing", "Incomplete candidate"),
    ("mode_identity", "voting mode"), ("precinct_identity", "unit identity"),
    ("workbook_vote", "workbook/API"), ("snapshot", "snapshots"),
])
def test_michigan_isabella_rejects_conflicting_sources(michigan_isabella_native, change, message):
    data, full, tables = copy.deepcopy(michigan_isabella_native)
    breakdown = full["ballotItemWithBreakdown"]
    if change == "duplicate":
        data["voterTurnout"].append(copy.deepcopy(data["voterTurnout"][0]))
    elif change in {"missing_count", "boolean_count"}:
        data["voterTurnout"][0]["ballotsCast"] = None if change == "missing_count" else True
    elif change == "mode_missing":
        breakdown["breakdownResults"][0]["ballotOptions"][0]["groupResults"].pop()
    elif change == "mode_identity":
        breakdown["breakdownResults"][0]["ballotOptions"][0]["groupResults"][0]["groupName"][0][
            "text"] = "Unreviewed mode"
    elif change == "precinct_identity":
        breakdown["breakdownResults"][0]["precinct"]["id"] = data["precincts"][-1]["id"]
    elif change == "workbook_vote":
        key = next(key for key in tables["Summary Results"]
                   if key[0] == mi_2026.ISABELLA_HOUSE and key[2] == "Ben Ambrose")
        tables["Summary Results"][key] += 1
    full = dict(copy.deepcopy(data), ballotItemWithBreakdown=breakdown)
    if change == "snapshot":
        full["election"]["publishVersionId"] = "another snapshot"
    with pytest.raises(ValueError, match=message):
        mi_2026.review_isabella(data, full, tables)


@pytest.mark.parametrize("change", ["none", "duplicate", "missing_mode", "boolean", "extra_column"])
def test_michigan_workbook_requires_complete_unique_mode_and_column_inventory(change):
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for name, headers in mi_2026.SHEETS.items():
        sheet = workbook.create_sheet(name)
        sheet.append(headers)
        prefix = ["City, Pct 1"] if name.startswith("Precinct") else []
        key = prefix + ["House", "1", "Ballots Cast", "", None]
        rows = [key + [mode, count] for mode, count in zip(mi_2026.MODES, [2, 1, 1])] \
            if name.endswith("Group") else [key + [4]]
        if name == "Summary Results by Group" and change == "missing_mode":
            rows.pop()
        if name == "Summary Results":
            if change == "duplicate":
                rows.append(rows[0][:])
            elif change == "boolean":
                rows[0][-1] = True
            elif change == "extra_column":
                rows[0].append("Unreviewed")
        for row in rows:
            sheet.append(row)
    stream = io.BytesIO()
    workbook.save(stream)
    if change == "none":
        assert mi_2026.workbook_tables(stream.getvalue())["Summary Results"]
    else:
        with pytest.raises(ValueError):
            mi_2026.workbook_tables(stream.getvalue())


def pima_example():
    header = ["COUNTY NUMBER", "PRECINCT CODE", "PRECINCT NAME",
              "REGISTERED VOTERS TOTAL", "BALLOTS CAST TOTAL", "BALLOTS CAST BLANK"]
    labels = ["", "", "", "VOTERS", "BALLOTS CAST", "BALLOTS CAST"]
    for contest, candidates in az_pima.HOUSE.items():
        header.extend(["U.S. Representative in Congress Dist. " + contest[-1]] * len(candidates))
        labels.extend(candidates)
    header.append("")
    labels.append("")
    table = [header, [""] * len(header), labels]
    dashboard, media = {}, []
    for n, registered, ballots, contest in [(1, 20, 5, "AZ-6"), (2, 30, 0, "AZ-7")]:
        name, code = f"Precinct {n:03}", f"{n:04}"
        for component in range(3):
            values = [registered, ballots if component == 0 else 0, 0] + [0] * 12
            if n == 1 and component == 0:
                values[3:10] = [2, 1, 1, 0, 0, 0, 1]
            table.append(["", code, name] + list(map(str, values)) + [""])
        dashboard[name] = dict(ElectionID="7", PrecinctCode=code, PrecinctName=name,
            VoterCount=str(registered), RegularCheckIns=str(ballots),
            RegularTurnout="25" if ballots else "0",
            StatusValue="Reported" if ballots else "Not Reported")
        media.append(dict(year="2026", state_code="AZ", county_code="pima", county="Pima County",
            precinct=name, precinct_code=str(2000 + n), contest_id=contest,
            total_votes="4" if ballots else "0", democratic_votes="2" if ballots else "0",
            republican_votes="1" if ballots else "0", other_votes="1" if ballots else "0",
            native_virtual_precinct="False"))
    totals = [sum(int(row[i]) for row in table[3:]) for i in range(3, len(header) - 1)]
    totals[0] = 50
    table.append(["", "ZZZ", "COUNTY TOTALS"] + list(map(str, totals)) + [""])
    return table, dashboard, media


def test_arizona_pima_reconciles_unnamed_components_without_tripling_registration():
    table, dashboard, media = pima_example()
    results, participation, audit = az_pima.review_tables(table, dashboard, media)
    assert audit["registered_voters"] == 50 and audit["ballots"] == 5
    assert audit["house_votes"] == 4 and len(participation) == 2
    assert participation[1]["ballots_cast_total"] == 0
    assert "not_reported" in participation[1]["quality_flags"]
    assert results[0]["precinct_code"] == "0001"
    assert results[0]["native_media_precinct_code"] == "2001"
    assert not audit["maps_approved"] and not audit["rates_available"]
    assert all(row["turnout_rate"] == "" for row in participation)


@pytest.mark.parametrize("change", ["name_case", "code", "missing_component", "duplicate_component",
    "registration", "ballots", "turnout_display", "negative", "missing_count", "county_total",
    "house_vector", "second_house_scope", "candidate", "wrong_election", "wrong_county",
    "duplicate_media", "duplicate_code"])
def test_arizona_pima_rejects_incomplete_or_conflicting_native_evidence(change):
    table, dashboard, media = pima_example()
    if change == "name_case":
        table[3][2] = "Precinct 001 "
    elif change == "code":
        dashboard["Precinct 001"]["PrecinctCode"] = "1"
    elif change == "missing_component":
        table.pop(5)
    elif change == "duplicate_component":
        table.insert(5, copy.deepcopy(table[3]))
    elif change == "registration":
        table[4][3] = "21"
    elif change == "ballots":
        dashboard["Precinct 001"]["RegularCheckIns"] = "6"
    elif change == "turnout_display":
        dashboard["Precinct 001"]["RegularTurnout"] = "26"
    elif change == "negative":
        table[3][6] = "-1"
    elif change == "missing_count":
        table[3][6] = ""
    elif change == "county_total":
        table[-1][4] = "6"
    elif change == "house_vector":
        media[0]["total_votes"] = "5"
    elif change == "second_house_scope":
        table[3][13] = "1"
    elif change == "candidate":
        table[2][6] = "Unexpected candidate (DEM)"
    elif change == "wrong_election":
        dashboard["Precinct 001"]["ElectionID"] = "6"
    elif change == "wrong_county":
        media[0]["county_code"] = "maricopa"
    elif change == "duplicate_media":
        media.append(copy.deepcopy(media[0]))
    elif change == "duplicate_code":
        table[6][1] = "0001"
    with pytest.raises(ValueError):
        az_pima.review_tables(table, dashboard, media)


def maricopa_example():
    rows, features = [], []
    for number, name, x in [(1, "ACACIA", -112.1), (2, "ACOMA", -112.08)]:
        rows.append(dict(year=2026, state_code="AZ", county_code="maricopa",
            county="Maricopa County", native_virtual_precinct="False", contest_id="AZ-1",
            precinct=f"{number:04} {name}", precinct_code=str(number), total_votes=4,
            democratic_votes=3, republican_votes=1, other_votes=0, margin_pp=50,
            office="U.S. Representative in Congress - District No. 1",
            native_reporting_status="Not Reported"))
        features.append(dict(type="Feature", properties=dict(OBJECTID=number,
            BdVal=f"{number:04}", BdName=name, PctNum=number),
            geometry=dict(type="Polygon", coordinates=[[
                [x, 33.4], [x + 0.01, 33.4], [x + 0.01, 33.41],
                [x, 33.41], [x, 33.4]]])))
    return rows, features


def test_arizona_maricopa_literal_join_preserves_native_geometry_and_counts():
    rows, features = maricopa_example()
    mapped, audit = az_maricopa.mapped_precincts(rows, features)
    assert len(mapped) == 2 and not audit["withheld_units"]
    assert mapped[0]["geometry"] == features[0]["geometry"]
    assert mapped[0]["properties"]["contest_votes"] == 4
    assert mapped[0]["properties"]["native_reporting_status"] == "Not Reported"
    assert not audit["participation_joined"] and not audit["rates_available"]


@pytest.mark.parametrize("change", ["name_case", "name_spacing", "missing", "extra",
    "duplicate_native", "duplicate_reference", "wrong_id", "wrong_reference_id",
    "virtual", "wrong_election", "wrong_county", "wrong_contest", "wrong_margin", "missing_count"])
def test_arizona_maricopa_rejects_ambiguous_or_incomplete_join(change):
    rows, features = maricopa_example()
    if change == "name_case":
        features[0]["properties"]["BdName"] = "Acacia"
    elif change == "name_spacing":
        features[0]["properties"]["BdName"] = "ACACIA "
    elif change == "missing":
        features.pop()
    elif change == "extra":
        rows.pop()
    elif change == "duplicate_native":
        rows.append(copy.deepcopy(rows[0]))
    elif change == "duplicate_reference":
        features.append(copy.deepcopy(features[0]))
    elif change == "wrong_id":
        rows[0]["precinct_code"] = "99"
    elif change == "wrong_reference_id":
        features[0]["properties"]["PctNum"] = 99
    elif change == "virtual":
        rows[0]["native_virtual_precinct"] = "True"
    elif change == "wrong_election":
        rows[0]["year"] = 2024
    elif change == "wrong_county":
        rows[0]["county_code"] = "pima"
    elif change == "wrong_contest":
        rows[0]["contest_id"] = "AZ-10"
    elif change == "wrong_margin":
        rows[0]["margin_pp"] = 0
    elif change == "missing_count":
        rows[0]["democratic_votes"] = None
    with pytest.raises(ValueError):
        az_maricopa.mapped_precincts(rows, features)


def test_arizona_maricopa_preserves_zero_without_filling_missing_margin():
    rows, features = maricopa_example()
    rows[0].update(total_votes=0, democratic_votes=0, republican_votes=0, margin_pp=None)
    mapped, audit = az_maricopa.mapped_precincts(rows, features)
    assert len(mapped) == 2 and audit["colored_units"] == 1
    assert mapped[0]["properties"]["margin_pp"] is None


@pytest.mark.parametrize("geometry", [None, dict(type="Polygon", coordinates=[]),
    dict(type="Point", coordinates=[-112.1, 33.4]),
    dict(type="Polygon", coordinates=[[[-112.1, 33.4], [-112.09, 33.41],
        [-112.09, 33.4], [-112.1, 33.41], [-112.1, 33.4]]])])
def test_arizona_maricopa_withholds_invalid_whole_shape(geometry):
    rows, features = maricopa_example()
    features[0]["geometry"] = geometry
    mapped, audit = az_maricopa.mapped_precincts(rows, features)
    assert len(mapped) == 1
    assert audit["withheld_units"][0]["precinct"] == "0001 ACACIA"


def test_arizona_maricopa_material_overlap_withholds_both_without_repair():
    rows, features = maricopa_example()
    features[1]["geometry"] = copy.deepcopy(features[0]["geometry"])
    original = copy.deepcopy(features)
    mapped, audit = az_maricopa.mapped_precincts(rows, features)
    assert not mapped and len(audit["withheld_units"]) == 2
    assert audit["overlap_pairs"][0]["material"]
    assert features == original


def arizona_native_example(democratic=2):
    def modes(votes):
        return [dict(groupName=name, voteCount=votes if name == "Election Day" else 0,
                     isFromVirtualPrecinct=False) for name in sorted(az_2026.MODES)]

    def option(identity, name, party, votes, precincts):
        return dict(id=identity, name=name, politicalParty=party, voteCount=votes,
                    groupResults=modes(votes), precinctResults=precincts)

    counties, statewide = [], {}
    for number, (code, name) in enumerate(az_2026.COUNTIES.items()):
        key = list(az_2026.HOUSE)[number % 9]
        options = []
        for identity, label, party, votes in [
                ("D", "Native D", "DEM", democratic), ("R", "Native R", "REP", 1)]:
            precinct = dict(id="1", name="Native precinct", isVirtual=False,
                voteCount=votes, reportingStatus="Partially Reported", groupResults=modes(votes))
            options.append(option(identity, label, party, votes, [precinct]))
        contest = dict(id=key, name=az_2026.HOUSE[key], type="State", contestType="Candidate",
                       voteFor=1, rankedChoiceResults=None, ballotOptions=options,
                       precinctsReporting=1, precinctsParticipating=1)
        counties.append(dict(id=code, name=name, ballotItems=[contest]))
        if key not in statewide:
            parent = copy.deepcopy(contest)
            for entry in parent["ballotOptions"]:
                entry.update(voteCount=0, precinctResults=None,
                    politicalParty={"DEM": "Democratic", "REP": "Republican"}[entry["politicalParty"]],
                    groupResults=modes(0))
            statewide[key] = parent
        for parent, child in zip(statewide[key]["ballotOptions"], options):
            parent["voteCount"] += child["voteCount"]
            parent["groupResults"] = modes(parent["voteCount"])
    return dict(electionDate="2026-11-03", electionName="2026 General Election",
        createdAt="2026-11-05T00:00:00Z",
        results=dict(id="01000000-0496-9e5d-0291-08dbda35db79", name="Arizona",
                     ballotItems=list(statewide.values())), localResults=counties)


def arizona_api_example(data):
    text = lambda value: [dict(languageId="en", text=value)]
    uuid = lambda value: f"00000000-0000-0000-0000-{value:012x}"

    def contests(native):
        return [dict(name=text(contest["name"]),
            voteTotal=sum(option["voteCount"] for option in contest["ballotOptions"]),
            summaryResults=dict(ballotOptions=[
                dict(id=uuid(ord(option["id"])), nativeId=option["id"],
                     name=text(option["name"]), voteCount=option["voteCount"],
                     groupResults=[dict(groupName=text(mode["groupName"]), voteCount=mode["voteCount"])
                                   for mode in option["groupResults"]])
                for option in contest["ballotOptions"]])) for contest in native]

    root = dict(jurisdiction=dict(id=data["results"]["id"], name=text("Arizona"),
                mediaExportPath="Arizona/export-110326GeneralElection.json", childLocalities=[]),
                election=dict(electionDate="2026-11-03", isPrimary=False, isProduction=True,
                    isOfficialResults=False, name=text("2026 General Election"),
                    jurisdictionId=data["results"]["id"], totalVoters=150, ballotsCast=0,
                    publishVersionId="fixture", parties=[
                        dict(name=text("Democratic"), abbreviation="DEM"),
                        dict(name=text("Republican"), abbreviation="REP")]),
                ballotItems=contests(data["results"]["ballotItems"]),
                localityElections=[], voterRegistration=[])
    localities = {}
    for number, county in enumerate(data["localResults"], start=1):
        identity = uuid(number)
        election = dict(root["election"], id=uuid(number + 100), jurisdictionId=identity,
                        totalVoters=10.0, ballotsCast=5.0)
        root["jurisdiction"]["childLocalities"].append(dict(id=identity.upper(),
            name=text(county["name"]), turnoutPercent=0.5))
        root["localityElections"].append(election)
        root["voterRegistration"].append(dict(id=identity, localityName=text(county["name"]),
                                              activeVoters=0, inactiveVoters=0, total=10))
        localities[county["name"]] = dict(jurisdiction=dict(id=identity, name=text(county["name"])),
            election=election, ballotItems=contests(county["ballotItems"]),
            precincts=[dict(id=uuid(999), name=text("Native precinct"), isVirtual=False, reportingStatus=2)],
            voterTurnout=[dict(id=uuid(999), precinctName="Native precinct", ballotsCast=5.0,
                              voterTurnout=5, voterRegistration=10)])
    return root, localities


def test_arizona_native_counts_keep_county_qualified_ids_and_literal_party_descriptions():
    data = arizona_native_example()
    root, _ = arizona_api_example(data)
    rows, originals, audit = az_2026.review_native(data, az_2026.party_aliases(root))
    assert len(rows) == 15 and len({row["county_code"] for row in rows}) == 15
    assert all(row["precinct_code"] == "1" and row["total_votes"] == 3
               and row["margin_pp"] == pytest.approx(100 / 3)
               and row["turnout_rate"] is None and not row["maps_approved"] for row in rows)
    assert any(row["native_party"] == "DEM" and row["state_declared_party"] == "Democratic"
               for row in originals)
    assert audit["native_party_description_differences"] and not audit["maps_approved"]


@pytest.mark.parametrize("failure", [
    "date", "county", "county_duplicate", "candidate_name", "party", "missing_count",
    "boolean_count", "missing_mode", "duplicate_precinct", "precinct_name", "state_residual",
])
def test_arizona_native_rejects_missing_ambiguous_or_conflicting_source_records(failure):
    data = arizona_native_example()
    root, _ = arizona_api_example(data)
    option = data["localResults"][0]["ballotItems"][0]["ballotOptions"][0]
    if failure == "date":
        data["electionDate"] = "2024-11-05"
    elif failure == "county":
        data["localResults"][0]["name"] = "Another County"
    elif failure == "county_duplicate":
        data["localResults"].append(copy.deepcopy(data["localResults"][0]))
    elif failure == "candidate_name":
        option["name"] = "Native D "
    elif failure == "party":
        option["politicalParty"] = "REP"
    elif failure == "missing_count":
        option["precinctResults"][0].pop("voteCount")
    elif failure == "boolean_count":
        option["precinctResults"][0]["voteCount"] = False
    elif failure == "missing_mode":
        option["precinctResults"][0]["groupResults"].pop()
    elif failure == "duplicate_precinct":
        option["precinctResults"].append(copy.deepcopy(option["precinctResults"][0]))
    elif failure == "precinct_name":
        option["precinctResults"][0]["name"] = "Different precinct"
    elif failure == "state_residual":
        parent = data["results"]["ballotItems"][0]["ballotOptions"][0]
        parent["voteCount"] += 1
        next(mode for mode in parent["groupResults"] if mode["groupName"] == "Election Day")["voteCount"] += 1
    with pytest.raises(ValueError):
        az_2026.review_native(data, az_2026.party_aliases(root))


def test_arizona_explicit_zero_is_preserved_without_turning_votes_into_ballots():
    data = arizona_native_example(democratic=0)
    root, localities = arizona_api_example(data)
    rows, _, _ = az_2026.review_native(data, az_2026.party_aliases(root))
    participation, _, audit = az_2026.review_api(data, root, localities)
    assert rows[0]["democratic_votes"] == 0 and rows[0]["total_votes"] == 1
    assert participation[0]["ballots"] == 5 and participation[0]["turnout_rate"] is None
    assert audit["native_state_ballot_field"] == 0 and audit["observed_county_ballot_sum"] == 75
    assert not audit["native_state_ballot_field_matches_counties"]
    assert not audit["native_registration_components_match_totals"] and not audit["rates_approved"]


def test_arizona_missing_virtual_participation_is_not_zero_or_a_house_precinct():
    data = arizona_native_example()
    root, localities = arizona_api_example(data)
    localities["Mohave County"]["precincts"].append(dict(
        id="00000000-0000-0000-0000-000000000222",
        name=[dict(languageId="en", text="Non-Resident Property Owners")],
        isVirtual=True, reportingStatus=2))
    rows, _, audit = az_2026.review_api(data, root, localities)
    missing = [row for row in rows if not row["native_observation_present"]]
    assert len(missing) == 1 and missing[0]["native_virtual_precinct"]
    assert missing[0]["ballots"] is None and missing[0]["registered_voters"] is None
    assert len(audit["missing_participation_rows"]) == 1


def test_arizona_county_api_different_native_ids_are_not_assumed_to_be_media_ids():
    data = arizona_native_example()
    root, localities = arizona_api_example(data)
    localities["Apache County"]["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["nativeId"] = "local-id"
    _, _, audit = az_2026.review_api(data, root, localities)
    matched = next(row for row in audit["api_option_correspondence"]
                   if row["county_code"] == "01" and row["media_option_id"] == "D")
    assert matched["api_native_option_id"] == "local-id"
    assert not matched["certifies_shared_id_namespace"]


@pytest.mark.parametrize("failure", [
    "test_election", "wrong_date", "wrong_option", "mode", "precinct_label",
    "registration", "fractional_ballots", "county_scope",
])
def test_arizona_api_rejects_identity_mode_denominator_and_election_conflicts(failure):
    data = arizona_native_example()
    root, localities = arizona_api_example(data)
    first = next(iter(localities.values()))
    if failure == "test_election":
        first["election"]["isProduction"] = False
    elif failure == "wrong_date":
        first["election"]["electionDate"] = "2024-11-05"
    elif failure == "wrong_option":
        root["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["nativeId"] = "unknown"
    elif failure == "mode":
        root["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["groupResults"][0]["voteCount"] += 1
    elif failure == "precinct_label":
        first["voterTurnout"][0]["precinctName"] = "Native precinct "
    elif failure == "registration":
        first["voterTurnout"][0]["voterRegistration"] = 0
    elif failure == "fractional_ballots":
        first["voterTurnout"][0]["ballotsCast"] = 5.5
    elif failure == "county_scope":
        localities.pop("Apache County")
    with pytest.raises(ValueError):
        az_2026.review_api(data, root, localities)


def arkansas_reference_fixture():
    feature = dict(type="Feature", properties=dict(objectid=1, state_fips="05",
        county_fips="001", county_name="Arkansas", precinct="McFall", precinct_code_1="12",
        edit_date=None),
        geometry=dict(type="Polygon", coordinates=[
            [[-91.5, 34], [-91.4, 34], [-91.4, 34.1], [-91.5, 34.1], [-91.5, 34]]]))
    row = dict(year="2026", state_code="AR", county_code="05001", county="Arkansas",
               precinct_code="12", precinct="McFall", contest_id="house1")
    return row, feature


def test_arkansas_reference_exact_identity_does_not_approve_election_geometry():
    row, feature = arkansas_reference_fixture()
    report, diagnostic = ar_geometry.audit([row], [feature])
    assert diagnostic[0]["classification"] == "exact_id_and_literal_name"
    assert not report["maps_approved"] and not report["election_day_geometry_certified"]


@pytest.mark.parametrize("change,expected", [
    ({"precinct": "Other"}, "id_only_unconfirmed"),
    ({"precinct_code_1": "99"}, "unique_literal_name_only_unconfirmed"),
    ({"precinct_code_1": "99", "precinct": "Other"}, "unmatched"),
    ({"county_fips": "003", "county_name": "Ashley"}, "unmatched"),
])
def test_arkansas_reference_unconfirmed_links(change, expected):
    row, feature = arkansas_reference_fixture()
    feature["properties"].update(change)
    assert ar_geometry.diagnose([row], [feature])[0][0]["classification"] == expected


def test_arkansas_reference_conflicting_id_and_name_is_not_name_join():
    row, feature = arkansas_reference_fixture()
    other = copy.deepcopy(feature)
    feature["properties"]["precinct"] = "Other"
    other["properties"].update(objectid=2, precinct_code_1="99")
    result = ar_geometry.diagnose([row], [feature, other])[0][0]
    assert result["classification"] == "conflicting_id_and_literal_name"


def test_arkansas_reference_duplicate_reference_name_remains_ambiguous():
    row, feature = arkansas_reference_fixture()
    other = copy.deepcopy(feature)
    other["properties"].update(objectid=2, precinct_code_1="99")
    assert ar_geometry.diagnose([row], [feature, other])[0][0][
        "classification"] == "ambiguous_reference_identity"


def test_arkansas_reference_county_label_conflict_and_split_house_scope_retained():
    row, feature = arkansas_reference_fixture()
    feature["properties"]["county_name"] = "Wrong county"
    other = dict(row, contest_id="house2")
    result = ar_geometry.diagnose([row, other], [feature])[0]
    assert all(value["conflicting_county_label_objects"] == [1]
               and value["house_vectors_for_identity"] == 2
               and not value["maps_approved"] for value in result)


def test_arkansas_reference_duplicate_result_identity_rejected():
    row, feature = arkansas_reference_fixture()
    with pytest.raises(ValueError, match="Duplicate native"):
        ar_geometry.diagnose([row, row], [feature])


@pytest.mark.parametrize("geometry,expected", [
    (None, "native_null_geometry"),
    ({"type": "Point", "coordinates": [-91, 34]}, "native_nonpolygon_geometry"),
    ({"type": "Polygon", "coordinates": []}, "native_empty_geometry"),
])
def test_arkansas_reference_invalid_geometry_not_repaired(geometry, expected):
    assert ar_geometry.geometry_issue(geometry) == expected


def test_arkansas_reference_self_intersection_not_repaired():
    geometry = dict(type="Polygon", coordinates=[
        [[-91.5, 34], [-91.4, 34.1], [-91.5, 34.1], [-91.4, 34], [-91.5, 34]]])
    assert "Self-intersection" in ar_geometry.geometry_issue(geometry)


def test_arkansas_reference_material_overlap_is_reported_without_repair():
    row, feature = arkansas_reference_fixture()
    other = copy.deepcopy(feature)
    other["properties"].update(objectid=2, precinct_code_1="99", precinct="Other")
    report, _ = ar_geometry.audit([row], [feature, other])
    assert len(report["material_overlaps"]) == 1
    assert report["material_overlaps"][0]["smaller_precinct_fraction"] == pytest.approx(1)
    assert not report["geometry_repaired"] and not report["maps_approved"]


def alabama_native_example():
    rows = []
    for county, name, districts in [("01", "Jefferson", range(1, 8)), ("04", "Autauga", [1])]:
        for title, district in al_2026.HOUSE.items():
            if district not in districts:
                continue
            for number, candidate, votes, party in [
                ("001", "Native D", "2", "DEM"), ("002", "Native R", "1", "REP"),
                ("003", "Write-In", "1", "NON"),
            ]:
                rows.append(dict(zip(al_2026.HEADERS["AllResults"], [
                    "1001305", "2026 GENERAL ELECTION", county, name, "H" + str(district),
                    title, number, candidate, votes, party])))
    statistics = [dict(zip(al_2026.HEADERS["Statistics"],
        ["1001305", "2026 GENERAL ELECTION", code, str(ballots), "1", "1", "46330"]))
        for code, ballots in [("01", 31), ("04", 7)]]

    def native_page(records, ballots, registrations, percent, name=None):
        labels = dict(lblElectionName="2026 GENERAL ELECTION", lblTotalBallotsCast=str(ballots),
                      lblTotalRegisteredVoters=str(registrations), lblVoterTurnout=percent,
                      lblLastUpdated="11/04/2026 12:00:00 AM")
        labels.update(dict(lblCountyName=name + " County") if name else dict(lblCountiesReported="2"))
        html = "".join(f'<span id="{key}">{value}</span>' for key, value in labels.items())
        groups = {}
        for record in records:
            title = record["Contest Title"]
            label = record["Candidate Name"] + (
                "" if record["Party Code"] == "NON" else " (" + record["Party Code"] + ")")
            group = groups.setdefault(title, {})
            group[label] = group.get(label, 0) + int(record["Votes"])
        for title, candidates in groups.items():
            html += f'<table><tr><td class="enrContestHeader">{title}</td></tr>'
            for label, votes in candidates.items():
                html += ('<tr><td class="enrCandidateListItemCol enrCandNameCol">' + label
                         + '</td><td class="enrCandidateListItemCol enrCandVoteNumCol"><div>'
                         + str(votes) + '</div></td></tr>')
            html += ('</table><div class="enrCandidatesFooter enrCandVoteNumCol"><span>'
                     + str(sum(candidates.values())) + '</span></div>')
        return al_2026.page(html.encode())

    counties = {code: native_page([row for row in rows if row["County Code"] == code],
                                 ballots, registrations, percent, name)
                for code, name, ballots, registrations, percent in [
                    ("01", "Jefferson", 31, 100, "31.00%"), ("04", "Autauga", 7, 20, "35.00%")]}
    return (dict(AllResults=rows, Statistics=statistics),
            native_page(rows, 38, 120, "31.67%"), counties, {"01": "Jefferson", "04": "Autauga"})


def alabama_native_workbook(sheets):
    strings = []
    members = {}
    relations = ET.Element("Relationships")
    workbook = ET.Element(al_2026.XML + "workbook")
    sheet_nodes = ET.SubElement(workbook, al_2026.XML + "sheets")
    for index, (name, records) in enumerate(sheets.items(), 1):
        relationship = "rId" + str(index)
        ET.SubElement(sheet_nodes, al_2026.XML + "sheet", {
            "name": name, "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id": relationship})
        ET.SubElement(relations, "Relationship", Id=relationship, Target=f"worksheets/sheet{index}.xml")
        document = ET.Element(al_2026.XML + "worksheet")
        ET.SubElement(document, al_2026.XML + "dimension", ref=f"A1:J{len(records) + 3}")
        data = ET.SubElement(document, al_2026.XML + "sheetData")
        header = list(al_2026.HEADERS[name])
        values = [header] + [[record[field] for field in header] for record in records] + [[None], [None]]
        for number, row in enumerate(values, 1):
            node = ET.SubElement(data, al_2026.XML + "row", r=str(number))
            for column, value in enumerate(row):
                cell = ET.SubElement(node, al_2026.XML + "c", r=chr(65 + column) + str(number), s="0")
                if value is not None:
                    strings.append(value)
                    cell.set("t", "s")
                    ET.SubElement(cell, al_2026.XML + "v").text = str(len(strings) - 1)
        members[f"xl/worksheets/sheet{index}.xml"] = ET.tostring(document)
    shared = ET.Element(al_2026.XML + "sst")
    for string in strings:
        ET.SubElement(ET.SubElement(shared, al_2026.XML + "si"), al_2026.XML + "t").text = string
    members.update({"xl/sharedStrings.xml": ET.tostring(shared),
                    "xl/workbook.xml": ET.tostring(workbook),
                    "xl/_rels/workbook.xml.rels": ET.tostring(relations)})
    body = io.BytesIO()
    with zipfile.ZipFile(body, "w") as archive:
        for path, content in members.items():
            archive.writestr(path, content)
    return body.getvalue()


def test_alabama_native_counties_are_not_fips_and_participation_is_separate():
    counts, participants, audit = al_2026.review(*alabama_native_example())
    assert len(counts) == 8 and len(participants) == 2
    assert {row["county_code"]: row["county"] for row in counts} == {"01": "Jefferson", "04": "Autauga"}
    assert all(row["total_votes"] == 4 and row["margin"] == 25 and not row["maps_approved"] for row in counts)
    assert [row["ballots"] for row in participants] == [31, 7]
    assert [row["registered_voters"] for row in participants] == [100, 20]
    assert all(row["turnout_rate"] is None for row in participants)
    assert audit["native_ballots"] == 38 and audit["native_registered_voters"] == 120
    assert not audit["maps_approved"] and not audit["rates_available"]


@pytest.mark.parametrize("failure", [
    "election", "duplicate_candidate", "negative", "missing", "party", "county_name",
    "candidate_identity", "state_candidate", "county_candidate", "timestamp",
    "ballot", "registration", "duplicate_statistic", "omitted_statistic", "missing_house",
])
def test_alabama_rejects_native_identity_scope_and_parent_conflicts(failure):
    sheets, statewide, counties, declarations = alabama_native_example()
    first = sheets["AllResults"][0]
    if failure == "election":
        first["Election Code"] = "1001304"
    elif failure == "duplicate_candidate":
        sheets["AllResults"].append(copy.deepcopy(first))
    elif failure in {"negative", "missing"}:
        first["Votes"] = "-1" if failure == "negative" else None
    elif failure == "party":
        first["Party Code"] = "UNREVIEWED"
    elif failure == "county_name":
        first["County Name"] = "Another County"
    elif failure == "candidate_identity":
        sheets["AllResults"][-3]["Candidate Name"] = "Changed identity"
    elif failure == "state_candidate":
        statewide.contests[0]["candidates"][0]["votes"] += 1
    elif failure == "county_candidate":
        counties["01"].contests[0]["candidates"][0]["votes"] += 1
    elif failure == "timestamp":
        counties["01"].values["lblLastUpdated"] = "11/05/2026 12:00:00 AM"
    elif failure == "ballot":
        sheets["Statistics"][0]["Ballots Cast"] = "30"
    elif failure == "registration":
        statewide.values.update(lblTotalRegisteredVoters="121", lblVoterTurnout="31.40%")
    elif failure == "duplicate_statistic":
        sheets["Statistics"].append(copy.deepcopy(sheets["Statistics"][0]))
    elif failure == "omitted_statistic":
        sheets["Statistics"].pop()
    elif failure == "missing_house":
        counties["01"].contests.pop()
    with pytest.raises(ValueError):
        al_2026.review(sheets, statewide, counties, declarations)


def test_alabama_formatted_blank_rows_do_not_create_zero_observations():
    sheets, statewide, counties, declarations = alabama_native_example()
    parsed, audit = al_2026.read_workbook(alabama_native_workbook(sheets))
    assert parsed == sheets
    assert audit["Statistics"]["observed_rows"] == 2
    assert audit["Statistics"]["empty_xml_rows"] == 2
    counts, participants, _ = al_2026.review(parsed, statewide, counties, declarations)
    assert len(participants) == 2 and len(counts) == 8


def test_alabama_explicit_zero_candidate_is_not_a_missing_count():
    sheets, statewide, counties, declarations = alabama_native_example()
    sheets["AllResults"][2]["Votes"] = "0"
    statewide.contests[0]["candidates"][2]["votes"] -= 1
    statewide.contests[0]["total"] -= 1
    counties["01"].contests[0]["candidates"][2]["votes"] = 0
    counties["01"].contests[0]["total"] -= 1
    counts, _, _ = al_2026.review(sheets, statewide, counties, declarations)
    row = next(row for row in counts if row["county_code"] == "01" and row["district"] == 1)
    assert row["total_votes"] == 3 and json.loads(row["candidates"])["003"]["votes"] == 0
    assert row["margin"] == pytest.approx(100 / 3)


def arkansas_native_example():
    modes = {"abs": dict(description="Absentee"), "early": dict(description="Early Voting"),
             "day": dict(description="Election Day"), "all": dict(description="TV - Total Votes")}

    def candidates(missing=False, multiplier=1):
        return [dict(ChoiceID=party, Name=name, PartyID=party,
                     **({} if missing else {"TotalVotes": votes * multiplier}),
                     Votes=[dict(VoteTypeID=mode, Votes=0 if missing or mode != "day"
                                 else votes * multiplier) for mode in ["abs", "early", "day"]])
                for party, name, votes in [("d", "DEM Native D", 2), ("r", "REP Native R", 1)]]

    locations, turnout, counties = {}, {}, {}
    for code, name in [("05001", "Arkansas"), ("05003", "Ashley")]:
        locations[code] = dict(locationID=code, locationName=name, locations={
            key: dict(locationID=key, locationName=label, locations={})
            for key, label in [("7", "Native A"), ("8", "Native B")]})
        turnout[code] = dict(LocationID=code, TotalBallotsCast=4,
            RegisteredVoters=10, TotalPrecincts=2, Locations={
            "7": dict(LocationID="7", TotalBallotsCast=4, RegisteredVoters=10,
                      BallotsCast=[dict(VoteTypeID="all", BallotsCast=4)]),
            "8": dict(LocationID="8", BallotsCast=[dict(VoteTypeID="all", BallotsCast=0)])})
        counties[code] = dict(LocationID=code, LocationName=name, TotalVotes=3,
            Choices=candidates(), Locations={
                "7": dict(LocationID="7", LocationName="Native A", TotalVotes=3,
                          Choices=candidates()),
                "8": dict(LocationID="8", LocationName="Native B", Choices=candidates(True))})
    data = dict(ElectionData=dict(ElectionID=ar_2026.ELECTION, IsOfficial=False),
        TurnoutData=dict(TotalBallotsCast=8, RegisteredVoters=20,
                         TotalPrecincts=4, Locations=turnout),
        ContestData=[dict(ContestID=str(district), ContestName=f"U.S. Congress District 0{district}",
            TotalVotes=6, Choices=candidates(multiplier=2), Locations=copy.deepcopy(counties))
            for district in range(1, 5)])
    identity = dict(electionID=ar_2026.ELECTION, isOfficial=False, versionID="fixture",
        turnout=dict(totalBallotsCast=8), response=dict(id=ar_2026.ELECTION,
            date="2026-11-03T00:00:00", name="2026 General Election & Judical Runoff",
            parties={"d": dict(partyName="Democratic"), "r": dict(partyName="Republican")},
            voteTypes=modes, locations=locations))
    return data, identity


def test_arkansas_preserves_omissions_and_county_qualified_precinct_identity():
    data, identity = arkansas_native_example()
    rows, participation, audit, _ = ar_2026.review(data, identity)
    assert len(rows) == 16 and len(participation) == 4
    assert len({(row["county_code"], row["precinct_code"]) for row in participation}) == 4
    missing = [row for row in rows if row["precinct_code"] == "8"]
    assert all(row["total_votes"] is None and row["democratic_votes"] is None
               and row["republican_votes"] is None and row["margin_pp"] is None for row in missing)
    assert all(row["ballots"] is None for row in participation if row["precinct_code"] == "8")
    assert all(row["turnout_rate"] is None for row in participation + rows)
    assert audit["native_ballots"] == 8 and audit["omitted_native_ballot_totals"] == 2
    assert audit["maps_approved"] is False
    assert all(row["margin_pp"] == pytest.approx(100 / 3)
               for row in rows if row["precinct_code"] == "7")


@pytest.mark.parametrize("failure", [
    "wrong_election", "wrong_party", "duplicate_candidate", "missing_mode",
    "negative_count", "positive_mode_missing_total", "county_mode_residual", "ballot_residual",
])
def test_arkansas_rejects_identity_mode_and_ballot_conflicts(failure):
    data, identity = arkansas_native_example()
    precinct = data["ContestData"][0]["Locations"]["05001"]["Locations"]["7"]
    if failure == "wrong_election":
        data["ElectionData"]["ElectionID"] = "2024"
    elif failure == "wrong_party":
        precinct["Choices"][0]["PartyID"] = "unknown"
    elif failure == "duplicate_candidate":
        precinct["Choices"].append(copy.deepcopy(precinct["Choices"][0]))
    elif failure == "missing_mode":
        precinct["Choices"][0]["Votes"].pop()
    elif failure == "negative_count":
        precinct["Choices"][0]["TotalVotes"] = -1
    elif failure == "positive_mode_missing_total":
        precinct["Choices"][0].pop("TotalVotes")
    elif failure == "county_mode_residual":
        candidate = precinct["Choices"][0]
        candidate["Votes"][0]["Votes"] = 1
        candidate["Votes"][2]["Votes"] -= 1
    elif failure == "ballot_residual":
        data["TurnoutData"]["Locations"]["05001"]["TotalBallotsCast"] += 1
    with pytest.raises(ValueError):
        ar_2026.review(data, identity)


@pytest.mark.parametrize("changed", [False, True])
def test_arkansas_csv_zero_serialization_does_not_repair_json(changed):
    data, identity = arkansas_native_example()
    modes = {"abs": "Absentee", "early": "Early Voting", "day": "Election Day"}
    columns = ["Contest ID", "Contest Name", "Location ID", "Location Name", "Candidate ID",
               "Candidate Name", "Party ID", "Candidate Votes", "Total Votes", *modes.values()]
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerow(columns)
    for contest in data["ContestData"]:
        for county in contest["Locations"].values():
            for node in [county, *county["Locations"].values()]:
                for candidate in node["Choices"]:
                    signature = list(ar_2026.csv_signature(contest, county, node, candidate, modes))
                    if changed and node["LocationID"] == "8":
                        signature[7] = "1"
                    writer.writerow(signature)
    if changed:
        with pytest.raises(ValueError, match="CSV/JSON"):
            ar_2026.compare_csv(data, text.getvalue(), modes)
    else:
        result = ar_2026.compare_csv(data, text.getvalue(), modes)
        assert result["json_omitted_candidate_totals"] == 16
        assert "TotalVotes" not in data["ContestData"][0]["Locations"]["05001"]["Locations"]["8"]


@pytest.mark.parametrize("failure", [None, "version", "ballots", "candidate", "county_scope"])
def test_arkansas_independent_native_api_versions_and_counts(failure):
    data, identity = arkansas_native_example()
    extra = copy.deepcopy(data["ContestData"][0])
    extra["ContestID"] = "senate"
    data["ContestData"].append(extra)

    def api_contest(node):
        return dict(totalVotes=node["TotalVotes"],
            choices=[dict(choiceID=choice["ChoiceID"], partyID=choice["PartyID"],
                          totalVotes=choice.get("TotalVotes", 0)) for choice in node["Choices"]])

    turnout = dict(electionID=ar_2026.ELECTION, versionID="fixture", isOfficial=False,
        response=dict(totalBallotsCast=8, registeredVoters=20, totalPrecincts=4,
            locations={code: dict(totalBallotsCast=4, registeredVoters=10, totalPrecincts=2)
                       for code in ["05001", "05003"]}))
    federal = dict(electionID=ar_2026.ELECTION, versionID="fixture", isOfficial=False,
        response=dict(contests={node["ContestID"]: dict(api_contest(node),
            contestID=node["ContestID"],
            locations={code: api_contest(county) for code, county in node["Locations"].items()})
            for node in data["ContestData"]}))
    if failure == "version":
        federal["versionID"] = "different"
    elif failure == "ballots":
        turnout["response"]["locations"]["05001"]["totalBallotsCast"] += 1
    elif failure == "candidate":
        federal["response"]["contests"]["1"]["choices"][0]["totalVotes"] += 1
    elif failure == "county_scope":
        federal["response"]["contests"]["1"]["locations"].pop("05001")
    if failure:
        with pytest.raises(ValueError):
            ar_2026.compare_api(data, identity, turnout, federal)
    else:
        audit = ar_2026.compare_api(data, identity, turnout, federal)
        assert audit["full_file_api_counts_match"] and audit["federal_summary_candidate_cells"] == 30


@pytest.mark.parametrize("kind", [
    "all_candidate_denominator", "zero", "missing", "negative", "wrong_party", "wrong_total",
    "incomplete_scope",
])
def test_virginia_mapped_candidate_counts_keep_write_ins_and_do_not_infer_turnout(kind):
    translated = lambda text: [dict(languageId="en", text=text)]
    candidates = {
        "d": dict(votes=5, party=dict(abbreviation="D", name=translated("Democratic"))),
        "r": dict(votes=3, party=dict(abbreviation="R", name=translated("Republican"))),
        "i": dict(votes=1, party=dict(abbreviation="I", name=translated("Independent"))),
        "write-in": dict(votes=1, party=None),
    }
    if kind == "zero":
        for candidate in candidates.values():
            candidate["votes"] = 0
    elif kind == "missing":
        candidates["d"]["votes"] = None
    elif kind == "negative":
        candidates["d"]["votes"] = -1
    elif kind == "wrong_party":
        candidates["d"]["party"]["name"] = translated("Republican")
    row = dict(locality_code="001", locality="Native locality", precinct="136 - NATIVE",
        district="2", precinct_uuid="native-uuid", source="native-detail",
        precinct_mode_allocation_complete="False" if kind == "incomplete_scope" else "True",
        candidates=json.dumps(candidates), candidate_votes="0" if kind == "zero" else "10")
    if kind == "wrong_total":
        row["candidate_votes"] = "11"
    if kind in {"missing", "negative", "wrong_party", "wrong_total"}:
        with pytest.raises(ValueError):
            va_maps.normalized_result(row, "0136 ")
        return
    result = va_maps.normalized_result(row, "0136 ")
    assert result["precinct_code"] == "0136" and result["original_precinct_id"] == "0136 "
    assert result["margin_pp"] == (None if kind == "zero" else 20)
    assert result["other_votes"] == (0 if kind == "zero" else 2)
    assert "participation" not in result and "turnout_rate" not in result
    assert ("may omit those modes" in result["ballot_scope"]) == (kind == "incomplete_scope")


@pytest.mark.parametrize("failure", [None, "dangling_webmap", "different_layer", "old_edit", "old_capture"])
def test_virginia_current_reference_requires_actual_agency_link_and_2026_data_edit(
        tmp_path, monkeypatch, failure):
    source = {
        "official-current-boundary-map": dict(url=va_maps.REFERENCE, fetched_at="2026-11-05"),
        "official-district-union-layer": dict(url="https://official.example/FeatureServer/0?f=pjson"),
        "official-linked-webmap-item": {}, "official-linked-webmap-data": {},
    }
    payloads = {
        "official-current-boundary-map": ("map showing webmap-identity; maps showing the current "
                                           "election district and precinct boundaries").encode(),
        "official-linked-webmap-item": json.dumps(
            dict(id="webmap-identity", orgId="M3dium4ePYpmdT4B")).encode(),
        "official-linked-webmap-data": json.dumps(dict(operationalLayers=[
            dict(url="https://official.example/FeatureServer/0")])).encode(),
        "official-district-union-layer": json.dumps(
            dict(editingInfo=dict(lastEditDate=1790081101678))).encode(),
    }
    if failure == "dangling_webmap":
        payloads["official-current-boundary-map"] = (
            b"maps showing the current election district and precinct boundaries")
    elif failure == "different_layer":
        payloads["official-linked-webmap-data"] = json.dumps(dict(
            operationalLayers=[dict(url="https://different.example/FeatureServer/0")])).encode()
    elif failure == "old_edit":
        payloads["official-district-union-layer"] = json.dumps(
            dict(editingInfo=dict(lastEditDate=1727040000000))).encode()
    elif failure == "old_capture":
        source["official-current-boundary-map"]["fetched_at"] = "2024-11-05"
    (tmp_path / "sources.json").write_text(json.dumps(source))
    monkeypatch.setattr(va_maps.geometry.native.reports, "verified",
                        lambda _source, key, _receipt: payloads[key])
    if failure:
        with pytest.raises(ValueError):
            va_maps.qualify_current_reference(tmp_path)
    else:
        result = va_maps.qualify_current_reference(tmp_path)
        assert result["data_edit_utc"].startswith("2026-09-22")
        assert "Not certified election-day shapes." in result["scope"]


@pytest.mark.parametrize("kind", ["null", "empty", "line", "crossed_ring", "valid"])
def test_virginia_native_geometry_withholds_null_and_invalid_fragments_without_repair(kind):
    geometry = dict(type="Polygon", coordinates=[[[0, 0], [1, 0], [1, 1], [0, 0]]])
    if kind == "null":
        geometry = None
    elif kind == "empty":
        geometry["coordinates"] = []
    elif kind == "line":
        geometry = dict(type="LineString", coordinates=[[0, 0], [1, 1]])
    elif kind == "crossed_ring":
        geometry["coordinates"] = [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]
    original = json.dumps(geometry)
    issue = va_geometry.fragment_issue(geometry)
    assert (issue is None) == (kind == "valid")
    if kind == "null":
        assert issue == "native_null_geometry"
    assert json.dumps(geometry) == original


@pytest.mark.parametrize("raw,expected", [
    ("101", "0101"), ("0136 ", "0136"), ("0101", "0101"),
    ("00101", None), ("01A1", None), ("-101", None),
])
def test_virginia_geometry_identity_formatting_never_guesses_non_numeric_codes(raw, expected):
    if expected is None:
        with pytest.raises(ValueError):
            va_geometry.precinct_code(raw)
    else:
        assert va_geometry.precinct_code(raw) == expected


def test_virginia_geometry_requires_literal_names_not_abbreviations_or_fuzzy_aliases():
    assert va_geometry.literal_names_match({"101 - CHINCOTEAGUE"}, {" Chincoteague "})
    assert not va_geometry.literal_names_match({"104 - AGNOR-HURT"}, {"Agnor Hurt"})
    assert not va_geometry.literal_names_match({"102 - STUARTS DRAFT ELEMENTARY"}, {"Stuarts Draft Elem."})


@pytest.mark.parametrize("kind", [
    "partial", "complete", "negative_residual", "missing_mode", "missing_count",
    "duplicate_candidate", "duplicate_precinct", "wrong_contest", "wrong_total",
])
def test_virginia_native_locality_mode_residuals_are_retained_without_allocation(kind):
    translated = lambda text: [dict(languageId="en", text=text)]

    def option(early):
        counts = {"Election Day": 2, "Early Voting": early, "Mailed Absentee": 1,
                  "Provisional": 0, "Post-Election": 0}
        return dict(nativeId="cs1", name=translated("Candidate"), party=None, isWriteIn=False,
            voteCount=sum(counts.values()), groupResults=[
                dict(groupId=mode, groupName=translated(mode), voteCount=value)
                for mode, value in counts.items()])

    summary = option(0 if kind == "complete" else 4)
    precinct = option(5 if kind == "negative_residual" else 0)
    row = dict(parentBallotItemId="house-1", precinct=dict(id="precinct-1"),
               voteTotal=precinct["voteCount"], ballotOptions=[precinct])
    item = dict(id="house-1", summaryResults=dict(ballotOptions=[summary]),
                voteTotal=summary["voteCount"], breakdownResultCount=1, breakdownResults=[row])
    if kind == "missing_mode":
        precinct["groupResults"].pop()
    elif kind == "missing_count":
        precinct["groupResults"][0]["voteCount"] = None
    elif kind == "duplicate_candidate":
        row["ballotOptions"].append(precinct)
    elif kind == "duplicate_precinct":
        item["breakdownResults"].append(row)
        item["breakdownResultCount"] = 2
    elif kind == "wrong_contest":
        row["parentBallotItemId"] = "different-house"
    elif kind == "wrong_total":
        row["voteTotal"] += 1
    if kind not in {"partial", "complete", "negative_residual"}:
        with pytest.raises(ValueError):
            va_localities.review_scope(item)
        return
    review, units = va_localities.review_scope(item)
    residual = {"partial": 4, "complete": 0, "negative_residual": -1}[kind]
    assert review["mode_residuals"]["Early Voting"] == {"cs1": residual}
    assert review["precinct_mode_allocation_complete"] == (kind == "complete")
    assert review["negative_residual_conflict"] == (kind == "negative_residual")
    assert units[0]["candidates"]["cs1"]["votes"] == precinct["voteCount"]
    assert units[0]["candidates"]["cs1"]["modes"]["Early Voting"] == (
        5 if kind == "negative_residual" else 0)


@pytest.mark.parametrize("kind", ["candidate", "write_in", "zero", "both_fields", "missing", "negative"])
def test_virginia_native_write_in_field_is_a_count_not_a_boolean(kind):
    row = dict(CandidateId="cs1", OfficeId="cc1", CandidateName="Candidate",
               TOTAL_VOTES="10", WriteInVote="0")
    if kind in {"write_in", "zero", "both_fields"}:
        row.update(CandidateId="wi-cc1", CandidateName="WRITE IN VOTES", TOTAL_VOTES="",
                   WriteInVote="0" if kind == "zero" else "3")
    if kind == "both_fields":
        row["TOTAL_VOTES"] = "3"
    elif kind == "missing":
        row["TOTAL_VOTES"] = ""
    elif kind == "negative":
        row["TOTAL_VOTES"] = "-1"
    if kind in {"both_fields", "missing", "negative"}:
        with pytest.raises(ValueError):
            va_2026.candidate_count(row)
    else:
        assert va_2026.candidate_count(row) == (
            (10, "TOTAL_VOTES") if kind == "candidate" else
            (0 if kind == "zero" else 3, "WriteInVote"))


@pytest.mark.parametrize("failure", [None, "duplicate", "applications", "returned", "negative"])
def test_virginia_demographics_keep_applications_returns_and_missing_receipts_separate(failure):
    rows = []
    for age, gender, receipt, value in [
        ("18 to 25", "F", "", "3"), ("18 to 25", "F", "Mail", "2"),
        ("Over 65", "U", "", "4"), ("41 to 65", "M", "In Person", "0"),
    ]:
        rows.append(dict(zip(va_2026.DEMOGRAPHIC_FIELDS,
            ["COUNTY", "01", age, gender, "", "In Person", receipt, value])))
    translated = lambda text: [dict(languageId="en", text=text)]
    data = dict(statistics=[dict(name=translated("Absentee (updates at noon each day)"),
        groups=[dict(name=translated("Absentee Applications by Application Type"),
                     children=[dict(name=translated("In Person"), value=9)]),
                dict(name=translated("Absentee Ballots Returned by Method"),
                     children=[dict(name=translated("Mail"), value=2),
                               dict(name=translated("In Person"), value=0)])])])
    if failure == "duplicate":
        rows.append(rows[0].copy())
    elif failure == "applications":
        data["statistics"][0]["groups"][0]["children"][0]["value"] = 10
    elif failure == "returned":
        data["statistics"][0]["groups"][1]["children"][0]["value"] = 3
    elif failure == "negative":
        rows[0]["TheCount"] = "-1"
    if failure:
        with pytest.raises(ValueError):
            va_2026.review_demographics(rows, data)
    else:
        review, normalized, grouped = va_2026.review_demographics(rows, data)
        assert review["absentee_applications"] == 9 and review["returned_absentee_ballots"] == 2
        assert [row["returned_ballots"] for row in normalized] == [None, 2, None, 0]
        assert [(row["absentee_applications"], row["returned_absentee_ballots"]) for row in grouped] == [
            (5, 2), (0, 0), (4, None)]
        assert all(row["registered_voters"] is row["turnout_rate"] is None for row in grouped)


def test_virginia_candidate_summary_conflict_is_retained_without_changing_precinct_counts():
    rows, items = [], []
    for district, suffix in enumerate(["st", "nd", "rd"] + ["th"] * 8, 1):
        office = f"Member, House of Representatives ({district}{suffix} District)"
        options = []
        for candidate, name, value in [("d", "Democrat", 5), ("r", "Republican", 4), ("wi", "WRITE IN VOTES", 1)]:
            identity = f"wi-cc{district}" if candidate == "wi" else f"cs-{candidate}-{district}"
            options.append(dict(nativeId=identity, voteCount=value))
            rows.append(dict(CandidateId=identity, CandidateName=name,
                TOTAL_VOTES="" if candidate == "wi" else str(value),
                WriteInVote=str(value) if candidate == "wi" else "0",
                ElectionName="2026 November General", ElectionDate="2026-11-03",
                ElectionType="General", OfficeTitle=office, OfficeId=f"cc{district}",
                DistrictType="congressional", DistrictName=f"{district:02d}", NumberOfSeats="1",
                LocalityCode="001", LocalityName="COUNTY", PrecinctId="0101",
                PrecinctName="101 - NATIVE", Party=candidate))
        items.append(dict(name=[dict(languageId="en", text=office)],
                          summaryResults=dict(ballotOptions=options), voteTotal=10))
    items[0]["summaryResults"]["ballotOptions"][0]["voteCount"] = 6
    items[0]["voteTotal"] = 11
    review, units = va_2026.review_candidates(rows, dict(ballotItems=items))
    assert len(review["candidate_vector_conflicts"]) == 1
    assert review["original_csv_candidate_votes"] == 110 and review["summary_candidate_votes"] == 111
    assert all(unit["candidate_votes"] == 10 and unit["ballots"] is None for unit in units)
    assert sum(not unit["state_candidate_vector_matches"] for unit in units) == 1
    assert all(not unit["maps_approved"] for unit in units)


@pytest.mark.parametrize("failure", [
    None, "wrong_year", "wrong_format", "wrong_time", "duplicate", "negative", "missing_total",
])
def test_wyoming_2022_native_excel_display_and_ballot_conflict_are_not_silently_repaired(failure):
    from datetime import datetime

    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append([None, "Wyoming General Election - November 8, 2022"])
    sheet.append([None, None])
    sheet.append(["Precinct", "Total Ballots Cast"])
    sheet.append([datetime(2022, 1, 2), 10])
    sheet["A4"].number_format = "mm-dd"
    sheet.append(["Precincts Continue\non Next Page", None])
    sheet.append(["02-02", 0])
    sheet.append(["Total", 12])
    if failure == "wrong_year":
        sheet["B1"] = "November 3, 2026"
    elif failure == "wrong_format":
        sheet["A4"].number_format = "yyyy-mm-dd"
    elif failure == "wrong_time":
        sheet["A4"] = datetime(2022, 1, 2, 1)
    elif failure == "duplicate":
        sheet["A6"] = "01-02"
    elif failure == "negative":
        sheet["B6"] = -1
    elif failure == "missing_total":
        sheet.delete_rows(7)
    if failure:
        with pytest.raises(ValueError):
            wy_2022.table(sheet, False)
    else:
        units, printed, crosswalk, markers = wy_2022.table(sheet, False)
        assert units == {"01-02": dict(values=[10], row=4), "02-02": dict(values=[0], row=6)}
        assert printed == [12] and sum(item["values"][0] for item in units.values()) == 10
        assert crosswalk == {"2022-01-02 00:00:00": dict(acquired_csv_literal="2022-01-02 00:00:00",
            native_excel_format="mm-dd", displayed_precinct="01-02")} and markers == 1


@pytest.mark.parametrize("wrong_header", [False, True])
def test_wyoming_2022_native_house_categories_must_retain_original_order(wrong_header):
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append([None, "November 8, 2022"])
    sheet.append([None] * 8)
    sheet.append([None, "United States Representative"])
    labels = wy_2022.CATEGORIES.copy()
    if wrong_header:
        labels[2:4] = labels[2:4][::-1]
    sheet.append(["Precinct", *labels])
    sheet.append(["001", 1, 2, 3, 4, 0, 0, 0])
    sheet.append(["Total", 1, 2, 3, 4, 0, 0, 0])
    if wrong_header:
        with pytest.raises(ValueError):
            wy_2022.table(sheet, True)
    else:
        units, total, _, _ = wy_2022.table(sheet, True)
        assert units == {"001": dict(values=[1, 2, 3, 4, 0, 0, 0], row=5)}
        assert total == [1, 2, 3, 4, 0, 0, 0]


@pytest.mark.parametrize("failure", [
    None, "missing_value", "negative", "duplicate", "wrong_year", "wrong_categories", "missing_total",
])
def test_wyoming_native_precinct_parser_preserves_zero_counts_and_rejects_bad_rows(failure):
    rows = ["Wyoming General Election - November 3, 2026", "United States Representative",
            "Chuck Lisa Shawn Jeffrey", "Gray (R) Kinney (D) Johnson (L) Haggit (C)",
            "Write-Ins Overvotes Undervotes", "Precinct", "01-01 1 2 3 4 0 0 0",
            "Total 1 2 3 4 0 0 0", "Page 1 of 1"]
    if failure == "missing_value":
        rows[6] = "01-01 1 2 3 4 0 0"
    elif failure == "negative":
        rows[6] = "01-01 1 2 3 -4 0 0 0"
    elif failure == "duplicate":
        rows.insert(7, rows[6])
    elif failure == "wrong_year":
        rows[0] = rows[0].replace("2026", "2024")
    elif failure == "wrong_categories":
        rows[3] = "Gray (R) Kinney (D) Haggit (C) Johnson (L)"
    elif failure == "missing_total":
        rows.pop(7)
    if failure:
        with pytest.raises(ValueError):
            wy_review.parse_precinct_pages([rows], "source.pdf", True)
    else:
        units, total, pages = wy_review.parse_precinct_pages([rows], "source.pdf", True)
        assert units == {"01-01": dict(values=[1, 2, 3, 4, 0, 0, 0], page=1)}
        assert total == [1, 2, 3, 4, 0, 0, 0] and pages == [1]


def test_wyoming_separate_ballots_exclude_numeric_page_footers_and_keep_continuations():
    header = ["Wyoming General Election - November 3, 2026", "Total Ballots Cast", "Precinct"]
    pages = [header + ["01-01 10", "PrecinctsContinue", "onNextPage", "Page 1 of 2"],
             header + ["02-01 0", "Total 10", "Page 2 of 2"]]
    units, total, source_pages = wy_review.parse_precinct_pages(pages, "ballots.pdf", False)
    assert units == {"01-01": dict(values=[10], page=1), "02-01": dict(values=[0], page=2)}
    assert total == [10] and source_pages == [1, 2]


@pytest.mark.parametrize("failure", [None, "missing", "duplicate", "wrong_total"])
def test_wyoming_statewide_ballots_require_all_23_native_counties_and_printed_sum(failure):
    rows = ["Wyoming General Election - November 3, 2026", "Total Ballots Cast",
            "Counties Reporting: 23 of 23"] + [county + " 1" for county in wy_review.COUNTIES]
    rows += ["Total", "23", "Page1of1"]
    if failure == "missing":
        rows.pop(3)
    elif failure == "duplicate":
        rows.insert(3, rows[3])
    elif failure == "wrong_total":
        rows[-2] = "24"
    if failure:
        with pytest.raises(ValueError):
            wy_review.parse_statewide_pages([rows], "statewide.pdf", False)
    else:
        counties, total = wy_review.parse_statewide_pages([rows], "statewide.pdf", False)
        assert len(counties) == 23 and total == [23]


@pytest.mark.parametrize("failure", [
    None, "source", "encoding", "drawing", "unreviewed", "method", "character", "font",
])
def test_wyoming_native_text_requires_exact_reviewed_source_encoding_and_vector_glyph(failure):
    with wy_native_text.fitz.open() as document:
        page = document.new_page(width=200, height=200)

        def obj(value, stream=None):
            xref = document.get_new_xref()
            document.update_object(xref, value)
            if stream is not None:
                document.update_stream(xref, stream)
            return xref

        drawing = b"1 0 0 0 1 1 d1 0 0 0.3 1 re f"
        glyph = obj("<<>>", drawing)
        procedures = obj(f"<< /first {glyph} 0 R >>")
        encoding = obj("<< /Type /Encoding /Differences [0 /first] >>")
        font = obj(f"<< /Type /Font /Subtype /Type3 /Name /T1 /FontBBox [0 0 1 1] "
                   f"/FontMatrix [1 0 0 1 0 0] /FirstChar 0 /LastChar 0 /Widths [1] "
                   f"/CharProcs {procedures} 0 R /Encoding {encoding} 0 R /Resources <<>> >>")
        resources = obj(f"<< /Font << /T1 {font} 0 R >> >>")
        contents = obj("<<>>", b"BT /T1 30 Tf 1 0 0 1 50 50 Tm <00> Tj ET")
        document.xref_set_key(page.xref, "Resources", f"{resources} 0 R")
        document.xref_set_key(page.xref, "Contents", f"{contents} 0 R")
        raw = document.tobytes()
    digest = hashlib.sha256(drawing).hexdigest()
    record = dict(source_sha256=hashlib.sha256(raw).hexdigest(), fonts=[
        dict(font_xref=font, glyphs=[dict(code=0, glyph_name="first", drawing_sha256=digest)])])
    reviews = {digest: dict(character="1", method="direct_native_glyph_render_review")}
    if failure == "source":
        record["source_sha256"] = "0" * 64
    elif failure == "encoding":
        record["fonts"][0]["glyphs"][0]["code"] = 1
    elif failure == "drawing":
        record["fonts"][0]["glyphs"][0]["drawing_sha256"] = "0" * 64
    elif failure == "unreviewed":
        reviews.clear()
    elif failure == "method":
        reviews[digest]["method"] = "guessed"
    elif failure == "character":
        reviews[digest]["character"] = "12"
    elif failure == "font":
        record["fonts"] = []
    if failure:
        with pytest.raises(ValueError):
            wy_native_text.recover_pdf(raw, record, reviews)
    else:
        recovered, renders = wy_native_text.recover_pdf(raw, record, reviews)
        with recovered:
            assert recovered[0].get_text().strip() == "1"
            assert len(renders) == 1


@pytest.mark.parametrize("failure", [None, "missing_county", "wrong_year"])
def test_wyoming_original_inventory_requires_all_county_results_and_ballot_sources(failure):
    year = 2026
    names = [f"{year}_{county.replace(' ', '_')}_County_General_PbP{suffix}.pdf"
             for county in wy_originals.COUNTIES for suffix in ("", "_TBC")]
    names += [f"{year}_General_Statewide_{kind}_Summary.pdf"
              for kind in ("Candidates", "Total_Ballots_Cast")]
    if failure == "missing_county":
        names.pop(0)
    prefix = f"/Elections/Docs/{2022 if failure == 'wrong_year' else year}/Results/General/"
    raw = "".join(f'<a href="{prefix}{name}">Original</a>' for name in names).encode()
    raw += b'<a href="/Elections/Docs/2026/2026_Election_Calendar.pdf">Calendar</a>'
    if failure:
        with pytest.raises(ValueError, match="county/precinct/ballot"):
            wy_originals.advertised_files(raw, year)
    else:
        result = wy_originals.advertised_files(raw, year)
        assert len(result) == 48 and all("Calendar" not in url for url in result)


@pytest.mark.parametrize("failure", [None, "wrong_year", "truncated"])
def test_wyoming_original_pdf_requires_complete_native_election_identity(failure):
    with wy_originals.fitz.open() as document:
        page = document.new_page()
        page.insert_text((30, 50), "Wyoming General Election - November "
                         + ("8, 2022" if failure == "wrong_year" else "3, 2026"))
        raw = document.tobytes()
    if failure == "truncated":
        raw = raw[:-10]
    if failure:
        with pytest.raises(ValueError):
            wy_originals.document_inventory(raw, "results.pdf", 2026)
    else:
        assert wy_originals.document_inventory(raw, "results.pdf", 2026)["pdf_pages"] == 1


@pytest.mark.parametrize("failure", [None, "changed_source", "wrong_date"])
def test_wyoming_visual_identity_is_bound_to_exact_reviewed_bytes_and_election(failure):
    with wy_originals.fitz.open() as document:
        page = document.new_page()
        page.insert_text((30, 50), "Unreadable source date requires a separate direct visual review")
        raw = document.tobytes()
    identity = dict(year=2026, method="direct_rendered_header_review",
                    source_sha256=hashlib.sha256(raw).hexdigest(),
                    literal_election_date="November 3, 2026")
    if failure == "changed_source":
        identity["source_sha256"] = "0" * 64
    if failure == "wrong_date":
        identity["literal_election_date"] = "November 8, 2022"
    if failure:
        with pytest.raises(ValueError, match="exact visual source review"):
            wy_originals.document_inventory(raw, "native.pdf", 2026, identity)
    else:
        assert wy_originals.document_inventory(raw, "native.pdf", 2026, identity)[
            "election_date_verification"] == "direct_rendered_header_review"


@pytest.mark.parametrize("failure", [None, "missing", "inconsistent", "duplicate"])
def test_lewiston_voter_table_keeps_central_counts_unallocated_and_rejects_bad_columns(failure):
    doc = me_pa_participation.fitz.open()
    page = doc.new_page()
    page.insert_text((25, 70), "Total Number of Voters by Ward during the Election.", fontsize=9)
    labels = [str(n) for n in range(1, 8)] + ["C-V", "Total"]
    values = ["10"] * 7 + ["80", "150"]
    if failure == "missing":
        values[2] = ""
    elif failure == "inconsistent":
        values[-1] = "151"
    elif failure == "duplicate":
        labels[1] = "1"
    for i, (label, value) in enumerate(zip(labels, values)):
        page.insert_text((30 + 55 * i, 95), label, fontsize=9)
        if value:
            page.insert_text((30 + 55 * i, 115), value, fontsize=9)
    if failure:
        with pytest.raises(ValueError):
            me_pa_participation.lewiston_voters(page)
    else:
        units, total = me_pa_participation.lewiston_voters(page)
        assert units == {**{str(n): 10 for n in range(1, 8)}, "C-V": 80}
        assert total == 150
    doc.close()


@pytest.mark.parametrize("native, expected", [(None, None), ("%", None), ("60%", 60)])
def test_lewiston_printed_turnout_ignores_referendum_percentages_and_retains_blanks(native, expected):
    doc = me_pa_participation.fitz.open()
    page = doc.new_page()
    page.insert_text((30, 40), "Question: Limit property taxes to 1% of assessed value", fontsize=9)
    if native is not None:
        page.insert_text((30, 100), "Percentage of Voter Turnout:", fontsize=9)
        page.insert_text((220, 100), native, fontsize=9)
    assert me_pa_participation.printed_turnout(page) == expected
    doc.close()


def house_county_review_fixture(code="WA", state_fips="53"):
    def candidates(dem, rep, other):
        return [dict(name=name, party=party, votes=votes) for name, party, votes in
                [("D", "Democratic", dem), ("R", "Republican", rep), ("Write-in", "Nonpartisan", other)]]
    reference = {state_fips + suffix: dict(GEOID=state_fips + suffix, STATEFP=state_fips,
        NAME=name, NAMELSAD=name + " County") for suffix, name in [("001", "First"), ("003", "Second")]}
    declared = dict(state_code=code, district=code + "-01", url="https://example.test/actual-id")
    data = dict(test_data=False, country="US", province=code, district=declared["district"],
                election_date="2026-11-03", election_type="House of Representatives",
                election_scope="General", candidates=candidates(10, 20, 2), last_updated="native timestamp",
                region_results={name: dict(name=name, type="County", fips=fips,
                candidates=candidates(6, 10, 2) if name == "First" else candidates(4, 10, 0))
                for fips, name in [(state_fips + "001", "First"), (state_fips + "003", "Second")]})
    return data, declared, reference


def test_house_county_review_preserves_each_native_vector_and_aggregates_only_complete_states():
    data, declared, reference = house_county_review_fixture()
    result = house_county_review.district_counties(data, declared, "53", reference)
    rows = house_county_review.state_counties("WA", {"wa-01": declared},
                                             {"wa-01": result}, reference, "53")
    assert len(rows) == 2 and sum(row["total_votes"] for row in rows) == 32
    assert rows[0]["margin_pp"] == 100 * (6 - 10) / 18
    assert rows[1]["other_votes"] == 0 and rows[1]["level"] == "county"
    assert rows[0]["district_fragments"][0]["candidates"] == data["region_results"]["First"]["candidates"]
    assert not any(key in rows[0] for key in ["turnout_rate", "registration", "voters", "ballots"])
    data["candidates"][0]["votes"], data["candidates"][1]["votes"] = 20, 10
    for region in data["region_results"].values():
        region["candidates"][0]["votes"], region["candidates"][1]["votes"] = (
            region["candidates"][1]["votes"], region["candidates"][0]["votes"])
    result = house_county_review.district_counties(data, declared, "53", reference)
    rows = house_county_review.state_counties("WA", {"wa-01": declared}, {"wa-01": result}, reference, "53")
    assert all(row["margin_pp"] > 0 for row in rows)


@pytest.mark.parametrize("change", ["missing-vote", "missing-candidate", "duplicate-candidate", "party",
                                   "negative", "float", "boolean", "district-sum", "test-data",
                                   "wrong-state-fips", "unknown-fips", "duplicate-county", "unknown-level"])
def test_house_county_review_rejects_bad_vectors_scope_and_geography_without_zero_filling(change):
    data, declared, reference = house_county_review_fixture()
    first = data["region_results"]["First"]
    if change == "missing-vote":
        first["candidates"][0].pop("votes")
    elif change == "missing-candidate":
        first["candidates"].pop()
    elif change == "duplicate-candidate":
        first["candidates"].append(dict(first["candidates"][0]))
    elif change == "party":
        first["candidates"][0]["party"] = "Different literal party"
    elif change in {"negative", "float", "boolean", "district-sum"}:
        first["candidates"][0]["votes"] = {"negative": -1, "float": 6.0,
                                          "boolean": True, "district-sum": 7}[change]
    elif change == "test-data":
        data["test_data"] = True
    elif change == "wrong-state-fips":
        first["fips"] = "01001"
    elif change == "unknown-fips":
        first["fips"] = "53999"
    elif change == "duplicate-county":
        data["region_results"]["Second"]["fips"] = first["fips"]
    else:
        first["type"] = "Unreviewed Region"
    with pytest.raises(ValueError):
        house_county_review.district_counties(data, declared, "53", reference)


def test_house_county_review_keeps_overseas_unlocated_and_never_adds_parallel_town_totals():
    import copy
    data, declared, reference = house_county_review_fixture()
    data["region_results"]["parallel-town"] = dict(copy.deepcopy(data["region_results"]["First"]), type="Town")
    overseas = copy.deepcopy(data["region_results"]["Second"])
    overseas.update(type="Overseas", name="Explicit overseas", fips=None)
    for candidate in overseas["candidates"]:
        candidate["votes"] = 1 if candidate["party"] == "Republican" else 0
    data["region_results"]["Second"]["candidates"][1]["votes"] -= 1
    data["region_results"]["overseas"] = overseas
    result = house_county_review.district_counties(data, declared, "53", reference)
    assert len(result["counties"]) == 2 and len(result["unlocated_regions"]) == 1
    assert result["ignored_nested_regions"] == [dict(source_key="parallel-town", native_type="Town")]
    rows = house_county_review.state_counties("WA", {"wa-01": declared}, {"wa-01": result}, reference, "53")
    assert sum(row["total_votes"] for row in rows) == 31
    assert sum(c["votes"] for c in result["unlocated_regions"][0]["candidates"]) == 1


@pytest.mark.parametrize("change", [None, "nonzero", "missing-vote", "missing-candidate",
                                   "party", "wrong-fips", "reporting", "other-name",
                                   "other-state", "missing-cook", "wrong-cook"])
def test_house_county_review_keeps_only_explicit_zero_chicago_placeholders_unlocated(change):
    import copy
    data, declared, reference = house_county_review_fixture("IL", "17")
    cook = data["region_results"].pop("First")
    cook.update(name="Cook", fips="17031")
    data["region_results"]["cook"] = cook
    reference.pop("17001")
    reference["17031"] = dict(GEOID="17031", STATEFP="17", NAME="Cook", NAMELSAD="Cook County")
    chicago = copy.deepcopy(cook)
    chicago.update(name="Chicago", fips=None, percent_reporting=0)
    for candidate in chicago["candidates"]:
        candidate["votes"] = 0
    data["region_results"]["chicago"] = chicago
    if change == "nonzero":
        chicago["candidates"][0]["votes"] = 1
        data["candidates"][0]["votes"] += 1
    elif change == "missing-vote":
        chicago["candidates"][0].pop("votes")
    elif change == "missing-candidate":
        chicago["candidates"].pop()
    elif change == "party":
        chicago["candidates"][0]["party"] = "Different literal party"
    elif change == "wrong-fips":
        chicago["fips"] = "1703"
    elif change == "reporting":
        chicago["percent_reporting"] = 1
    elif change == "other-name":
        chicago["name"] = "Other City"
    elif change == "other-state":
        data["province"] = declared["state_code"] = "WA"
        data["district"] = declared["district"] = "WA-01"
    elif change == "missing-cook":
        data["region_results"].pop("cook")
    elif change == "wrong-cook":
        cook["fips"] = "17003"
    if change is not None:
        with pytest.raises(ValueError):
            house_county_review.district_counties(data, declared, "17", reference)
        return
    result = house_county_review.district_counties(data, declared, "17", reference)
    assert len(result["counties"]) == 2 and len(result["unlocated_regions"]) == 1
    retained = result["unlocated_regions"][0]
    assert retained["source_key"] == "chicago" and retained["candidates"] == chicago["candidates"]
    assert retained["geographic_status"] == "explicit_zero_unlocated_chicago_reporting_row"
    rows = house_county_review.state_counties("IL", {"il-01": declared},
                                             {"il-01": result}, reference, "17")
    assert sum(row["total_votes"] for row in rows) == 32
    assert next(row for row in rows if row["geography"] == "17031")["total_votes"] == 18


def test_house_county_review_uses_current_connecticut_planning_regions_not_overlapping_old_counties():
    import copy
    data, declared, reference = house_county_review_fixture("CT", "09")
    data["region_results"]["obsolete-county"] = copy.deepcopy(data["region_results"]["First"])
    for name in ["First", "Second"]:
        data["region_results"][name].update(type="Planning Region", fips=None)
    result = house_county_review.district_counties(data, declared, "09", reference)
    assert len(result["counties"]) == 2 and len(result["ignored_nested_regions"]) == 1
    assert all(r["join_strategy"] == "unique_census_name_casefold_periods" for r in result["counties"])


def test_house_county_review_accepts_only_unique_literal_names_not_aliases_or_padded_identifiers():
    data, _, reference = house_county_review_fixture()
    region = dict(data["region_results"]["First"], fips=None, name="FIRST COUNTY")
    assert house_county_review.county_identity(region, "53", reference)[0] == "53001"
    for changed in [dict(region, name="First Co."), dict(region, name="First County", fips="5301")]:
        with pytest.raises(ValueError):
            house_county_review.county_identity(changed, "53", reference)
    reference["53005"] = dict(GEOID="53005", STATEFP="53", NAME="First", NAMELSAD="First city")
    with pytest.raises(ValueError):
        house_county_review.county_identity(dict(region, name="First"), "53", reference)
    assert house_county_review.county_identity(dict(region, name="First city"), "53", reference)[0] == "53005"


def test_house_county_review_matches_period_only_typography_but_never_expands_saint_or_ambiguous_names():
    reference = {"18141": dict(GEOID="18141", STATEFP="18", NAME="St. Joseph",
                               NAMELSAD="St. Joseph County")}
    region = dict(name="St Joseph", fips=None)
    assert house_county_review.county_identity(region, "18", reference)[0] == "18141"
    with pytest.raises(ValueError):
        house_county_review.county_identity(dict(region, name="Saint Joseph"), "18", reference)
    reference["18999"] = dict(GEOID="18999", STATEFP="18", NAME="St Joseph", NAMELSAD="St Joseph city")
    with pytest.raises(ValueError):
        house_county_review.county_identity(region, "18", reference)


def test_house_county_geometry_preserves_real_rings_and_rejects_invalid_polygons_without_repairs():
    from shapely.geometry import Polygon, mapping, shape
    valid = Polygon([(0, 0), (0, 3), (3, 3), (3, 0)],
                    holes=[[(1, 1), (2, 1), (2, 2), (1, 2)]])
    projected = house_county_review.projected_county(mapping(valid), lambda x, y: (x, y))
    assert shape(projected).equals_exact(valid, 0)
    assert len(projected["coordinates"]) == 2
    with pytest.raises(ValueError):
        house_county_review.projected_county(
            mapping(Polygon([(0, 0), (1, 1), (0, 1), (1, 0)])), lambda x, y: (x, y))


@pytest.mark.parametrize("failure", ["missing-district", "rejected-district", "missing-county"])
def test_house_county_review_withholds_whole_state_when_declared_inputs_or_county_coverage_fail(failure):
    data, declared, reference = house_county_review_fixture()
    result = house_county_review.district_counties(data, declared, "53", reference)
    inventory, reviewed = {"wa-01": declared}, {"wa-01": result}
    if failure == "missing-district":
        inventory["wa-02"] = dict(declared, district="WA-02")
    elif failure == "rejected-district":
        reviewed["wa-01"] = dict(error="Original explicitly marked test data")
    else:
        reference["53005"] = dict(GEOID="53005", STATEFP="53", NAME="Third", NAMELSAD="Third County")
    with pytest.raises(ValueError):
        house_county_review.state_counties("WA", inventory, reviewed, reference, "53")


def house_county_source_fixture():
    regions = {}
    for index, code in enumerate(sorted(house_county_sources.STATES)):
        for district in range(1, 10 if index < 35 else 9):
            regions[f"{code.lower()}-{district:02}"] = dict(
                type="Congressional District", election_id=len(regions) + 1)
    return dict(test_data=False, country="US", province="US", election_date="2026-11-03T05:00:00Z",
                election_type="House of Representatives", election_scope="General", region_results=regions)


def test_house_county_acquisition_uses_only_complete_unique_declared_district_endpoints():
    source = house_county_source_fixture()
    declared = house_county_sources.declared_districts(source)
    assert declared["al-01"]["url"] == house_county_sources.API + str(
        source["region_results"]["al-01"]["election_id"])
    assert declared["al-01"]["district"] == "AL-01"


@pytest.mark.parametrize("change", ["test-data", "date", "scope", "missing-district", "duplicate-id", "boolean-id"])
def test_house_county_acquisition_rejects_wrong_election_and_ambiguous_endpoint_inventories(change):
    source = house_county_source_fixture()
    if change == "test-data":
        source["test_data"] = True
    elif change == "date":
        source["election_date"] = "2024-11-05"
    elif change == "scope":
        source["election_scope"] = "Primary"
    elif change == "missing-district":
        source["region_results"].pop("al-01")
    elif change == "duplicate-id":
        source["region_results"]["al-02"]["election_id"] = source["region_results"]["al-01"]["election_id"]
    else:
        source["region_results"]["al-01"]["election_id"] = True
    with pytest.raises(ValueError):
        house_county_sources.declared_districts(source)


def test_house_county_acquisition_binds_child_state_and_district_without_relabeling_noncounty_regions():
    declared = house_county_sources.declared_districts(house_county_source_fixture())["al-01"]
    data = dict(test_data=False, country="US", province="AL", district="AL-01",
                election_date="2026-11-03", election_type="House of Representatives",
                election_scope="General", region_results={"overseas": dict(type="Overseas")})
    house_county_sources.district_scope(data, declared)
    assert data["region_results"]["overseas"]["type"] == "Overseas"
    for changed in [dict(data, province="AK"), dict(data, district="AL-02"),
                    dict(data, region_results=[])]:
        with pytest.raises(ValueError):
            house_county_sources.district_scope(changed, declared)


def test_washington_geometry_requires_complete_literal_names_or_explicit_numbers_and_cd():
    rows = [dict(key="WA-one", county="Example County", precinct="1", congressional_district="4")]
    base = dict(County="53001", CountyName="Example", PrecinctNa="Other spelling",
                PrecinctNu=1, St_Code="EX0001", CD=4, LD=1, _index=0)
    selected, audits = wa_maps.select_references(rows, dict(precincts=[base], splits=[]))
    assert audits["Example County"]["strategy"] == "precincts/PrecinctNu"
    assert "Example County" in selected
    for changed in [dict(base, CD=5), dict(base, PrecinctNu=2), dict(base, St_Code="")]:
        selected, _ = wa_maps.select_references(rows, dict(precincts=[changed], splits=[]))
        assert not selected
    selected, _ = wa_maps.select_references(
        rows, dict(precincts=[base, dict(base, PrecinctNu=2, St_Code="EX0002")], splits=[]))
    assert not selected


def test_washington_geometry_never_guesses_padded_codes_or_aliases_or_multiple_source_ids():
    rows = [dict(key="WA-one", county="Example County", precinct="01", congressional_district="4")]
    base = dict(County="53001", CountyName="Example", PrecinctNa="1", PrecinctNu=1,
                St_Code="EX0001", CD=4, LD=1, _index=0)
    selected, _ = wa_maps.select_references(rows, dict(precincts=[base], splits=[]))
    assert not selected
    rows[0]["precinct"] = "1"
    selected, _ = wa_maps.select_references(
        rows, dict(precincts=[base, dict(base, St_Code="DIFFERENT")], splits=[]))
    assert not selected


def test_washington_geometry_rejects_complete_but_contradictory_name_number_crosswalks():
    rows = [dict(key="WA-" + p, county="Example County", precinct=p, congressional_district="4")
            for p in ["1", "2"]]
    base = dict(County="53001", CountyName="Example", PrecinctNa="1", PrecinctNu=2,
                St_Code="EX0001", CD=4, LD=1, _index=0)
    selected, audits = wa_maps.select_references(rows, dict(precincts=[
        base, dict(base, PrecinctNa="2", PrecinctNu=1, St_Code="EX0002", _index=1)], splits=[]))
    assert not selected and audits["Example County"]["conflicting_complete_crosswalks"]


@pytest.mark.parametrize("overlap", [False, True, "full"])
def test_washington_geometry_dissolves_once_and_excludes_ambiguity_without_allocating_counts(overlap):
    from types import SimpleNamespace
    from shapely.geometry import shape

    def square(x):
        return SimpleNamespace(parts=[0], points=[(x, 0), (x, 1), (x + 1, 1), (x + 1, 0), (x, 0)])

    shapes = [square(0), square(2), square(0 if overlap == "full" else .5 if overlap else 4)]
    reader = SimpleNamespace(shape=lambda index: shapes[index])
    rows = [dict(key="WA-" + p, county="Example County", precinct=p, congressional_district="4",
                 democratic_votes=10, republican_votes=20, other_votes=0, contest_votes=30)
            for p in ["1", "2"]]
    base = dict(County="53001", CountyName="Example", PrecinctNa="1", PrecinctNu=1,
                St_Code="EX0001", CD=4, LD=1, _index=0)
    references = dict(precincts=[base, dict(base, LD=2, _index=1),
                                dict(base, PrecinctNa="2", PrecinctNu=2, St_Code="EX0002", _index=2)],
                      splits=[])
    features, audit = wa_maps.mapped_precincts(rows, references, dict(precincts=reader))
    if overlap == "full":
        assert not features and audit["all_reference_overlap_pairs"]
        assert not audit["counties"]["Example County"]["exact"]
    else:
        assert len(features) == 2
        assert bool(audit["all_reference_overlap_pairs"]) == bool(overlap)
        assert shape(features[0]["geometry"]).intersection(shape(features[1]["geometry"])).area == 0
        first = next(f for f in features if f["properties"]["precinct"] == "1")
        assert len(first["properties"]["source_object_ids"]) == 2
        assert first["properties"]["contest_votes"] == 30
        if overlap:
            assert audit["masked_reporting_units"] and audit["ambiguity_mask"]["features"]
            assert all("overlapping strips withheld" in f["properties"]["geometry_scope"] for f in features)


def washington_fixture():
    import copy
    office = "Congressional District 4 - U.S. Representative"
    values = [("Ballots Cast", "", "", 36), ("D", "42", "(Prefers Democratic Party)", 10),
              ("R", "18", "(Prefers Republican Party)", 20), ("Write-in", "48", "", 2),
              ("Over Votes", "", "", 1), ("Under Votes", "", "", 3)]
    summary = [dict(zip(wa_review.SUMMARY_FIELDS, [office, "10", name, choice, party, total]))
               for name, choice, party, total in values]
    precincts = [dict(row, Precinct=precinct, Total=row["Total"] if precinct == "1" else 0)
                 for precinct in ["1", "1A"] for row in summary]
    original = {"Summary Results": summary, "Precinct Results": precincts}
    detailed = {name: [dict(row, **{"Votes Allowed": 1}) for row in rows] for name, rows in original.items()}
    options = [dict(nativeId=choice, name=[dict(languageId="en", text=name)],
                    party=dict(name=[dict(languageId="en", text=party)] if party else None,
                               standardName=None), voteCount=total)
               for name, choice, party, total in values if choice]
    native = dict(election=dict(electionDate="2026-11-03"),
                  ballotItems=[dict(name=[dict(languageId="en", text=office)],
                                    summaryResults=dict(ballotOptions=options), voteTotal=32)])
    return copy.deepcopy(original), copy.deepcopy(detailed), copy.deepcopy(native)


def test_washington_reconciles_every_export_and_native_candidate_without_filling_zero_rows():
    original, detailed, native = washington_fixture()
    rows, audit = wa_review.reconcile_county(original, detailed, native, "Example County", "county-id")
    assert len(rows) == 2 and rows[0]["reported_ballots"] == 36 and rows[0]["contest_votes"] == 32
    assert rows[0]["other_votes"] == 2 and rows[0]["margin_pp"] == -31.25
    assert rows[1]["precinct"] == "1A" and rows[1]["margin_pp"] is None
    assert rows[0]["key"] != rows[1]["key"] and audit["all_native_house_candidate_names_ids_parties_counts_reconcile"]
    assert not any(key in rows[0] for key in ["turnout_rate", "registration", "voters"])


def test_washington_democratic_lead_uses_positive_shared_renderer_margin_convention():
    original, detailed, native = washington_fixture()
    for book in [original, detailed]:
        for rows in book.values():
            for row in rows:
                if row["Ballot Name"] == "D" and row["Total"]:
                    row["Total"] = 20
                elif row["Ballot Name"] == "R" and row["Total"]:
                    row["Total"] = 10
    native["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["voteCount"] = 20
    native["ballotItems"][0]["summaryResults"]["ballotOptions"][1]["voteCount"] = 10
    rows, _ = wa_review.reconcile_county(original, detailed, native, "Example County", "county-id")
    assert rows[0]["margin_pp"] == 31.25


@pytest.mark.parametrize("value", [None, "", "0", "1l", -1, 1.5, True, float("inf"), float("nan")])
def test_washington_missing_or_invalid_counts_are_not_repaired_or_zero_filled(value):
    original, detailed, native = washington_fixture()
    detailed["Precinct Results"][0]["Total"] = value
    with pytest.raises(ValueError):
        wa_review.reconcile_county(original, detailed, native, "Example County", "county-id")


@pytest.mark.parametrize("change", ["duplicate", "exports", "summary", "accounting", "date",
                                   "candidate-id", "candidate-name", "party", "native-count", "native-inventory"])
def test_washington_rejects_bad_inventories_totals_scope_and_candidate_bindings(change):
    original, detailed, native = washington_fixture()
    if change == "duplicate":
        original["Precinct Results"].append(dict(original["Precinct Results"][0]))
    elif change == "exports":
        original["Precinct Results"][1]["Total"] += 1
    elif change == "summary":
        original["Precinct Results"][1]["Total"] += 1
        detailed["Precinct Results"][1]["Total"] += 1
    elif change == "accounting":
        for book in [original, detailed]:
            book["Summary Results"][4]["Total"] += 1
            book["Precinct Results"][4]["Total"] += 1
    elif change == "date":
        native["election"]["electionDate"] = "2024-11-05"
    elif change == "candidate-id":
        native["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["nativeId"] = "99"
    elif change == "candidate-name":
        native["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["name"][0]["text"] = "Other"
    elif change == "party":
        native["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["party"]["name"][0]["text"] = "Other"
    elif change == "native-count":
        native["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["voteCount"] += 1
    else:
        native["ballotItems"].append(dict(native["ballotItems"][0]))
    with pytest.raises(ValueError):
        wa_review.reconcile_county(original, detailed, native, "Example County", "county-id")


def test_washington_reader_rejects_unknown_columns_and_preserves_literal_split_labels(tmp_path):
    original, detailed, _ = washington_fixture()
    path = tmp_path / "source.xlsx"
    book = openpyxl.Workbook()
    book.remove(book.active)
    for name, fields in [("Summary Results", wa_review.SUMMARY_FIELDS),
                         ("Precinct Results", wa_review.PRECINCT_FIELDS)]:
        sheet = book.create_sheet(name)
        sheet.append(fields)
        for row in original[name]:
            sheet.append([row[field] for field in fields])
    book.save(path)
    actual = wa_review.read_workbook(path, False)
    assert {row["Precinct"] for row in actual["Precinct Results"]} == {"1", "1A"}
    assert actual["Precinct Results"][6]["Total"] == 0
    book["Precinct Results"].cell(2, 8, "Unexpected observation")
    book.save(path)
    with pytest.raises(ValueError, match="Unexpected nonempty"):
        wa_review.read_workbook(path, False)


def test_washington_blank_original_is_retained_and_only_explicit_detailed_count_is_used():
    original, detailed, native = washington_fixture()
    original["Precinct Results"][0]["Total"] = None
    rows, audit = wa_review.reconcile_county(original, detailed, native, "Example County", "county-id")
    assert original["Precinct Results"][0]["Total"] is None
    assert rows[0]["reported_ballots"] == 36
    assert audit["office_reviews"][detailed["Summary Results"][0]["Office Name"]]["missing_original_count_cells"] == 1


def test_washington_preserves_native_party_whitespace_but_classifies_its_explicit_democratic_label():
    original, detailed, native = washington_fixture()
    for book in [original, detailed]:
        for rows in book.values():
            for row in rows:
                if row["Party"] == "(Prefers Democratic Party)":
                    row["Party"] = " " + row["Party"]
    native["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["party"]["name"][0]["text"] = \
        " (Prefers Democratic Party)"
    rows, _ = wa_review.reconcile_county(original, detailed, native, "Example County", "county-id")
    assert rows[0]["democratic_votes"] == 10 and rows[0]["other_votes"] == 2
    assert detailed["Summary Results"][1]["Party"] == " (Prefers Democratic Party)"


def test_washington_bad_local_contest_is_audited_without_discarding_reconciled_house_rows():
    import copy
    original, detailed, native = washington_fixture()
    for book in [original, detailed]:
        for name in book:
            book[name] += [dict(row, **{"Office Name": "Local office"}) for row in copy.deepcopy(book[name])]
    local_contest = copy.deepcopy(native["ballotItems"][0])
    local_contest["name"][0]["text"] = "Local office"
    native["ballotItems"].append(local_contest)
    detailed["Precinct Results"][-1]["Total"] += 1
    rows, audit = wa_review.reconcile_county(original, detailed, native, "Example County", "county-id")
    assert len(rows) == 2 and audit["office_reviews"]["Local office"]["status"] == "not_reconciled"


def worcester_reading_fixture():
    precincts = [f"{ward}-{precinct}" for ward in range(1, 11) for precinct in range(1, 7)]
    for code in ("4-2A", "7-5A"):
        precincts.insert(precincts.index(code[:-1]) + 1, code)
    entries = []
    for first, factor in ((15, 6), (27, 1), (39, 2), (51, 3)):
        for offset, count in ((0, 38), (1, 25)):
            for row in range(1, count + 1):
                for column in range(1, 6):
                    value = factor * column
                    if offset == 1 and row == 24:
                        value = 0
                    elif offset == 1 and row == 25:
                        value *= 61
                    entries.append(dict(file=f"page-{first + offset:03}-row-{row:03}-col-{column}.png",
                                        result=[[str(value), 1.0]]))
    return entries, precincts


def test_worcester_complete_source_groups_preserve_split_precincts_and_printed_zeros():
    entries, precincts = worcester_reading_fixture()
    values, footers = worcester_review.reconcile_counts(entries, {}, precincts)
    assert values["overall"]["4-2A"] == [6, 12, 18, 24, 30]
    assert values["overall"]["7-5A"] == [6, 12, 18, 24, 30]
    assert values["overall"]["10-6"] == [0] * 5
    assert footers["overall"] == [61 * n for n in [6, 12, 18, 24, 30]]


@pytest.mark.parametrize("result", [None, [], [["1l", .99]], [["", 1]], [["-1", 1]],
                                   [["1.5", 1]], [["1", 1], ["2", 1]]])
def test_worcester_missing_or_ambiguous_ocr_is_never_zero_or_repaired(result):
    entries, precincts = worcester_reading_fixture()
    entries[0]["result"] = result
    with pytest.raises(ValueError, match="Missing or ambiguous"):
        worcester_review.reconcile_counts(entries, {}, precincts)
    values, _ = worcester_review.reconcile_counts(entries, {entries[0]["file"]: 6}, precincts)
    assert values["overall"]["1-1"][0] == 6


@pytest.mark.parametrize("change", ["duplicate", "missing", "footer", "mode", "identity", "review"])
def test_worcester_rejects_incomplete_inventory_bad_footers_and_mode_disagreement(change):
    entries, precincts = worcester_reading_fixture()
    manual = {}
    if change == "duplicate":
        entries[-1] = entries[0]
    elif change == "missing":
        entries.pop()
    elif change == "footer":
        entries[-1]["result"][0][0] = "9999"
    elif change == "mode":
        for name in ("page-027-row-001-col-1.png", "page-028-row-025-col-1.png"):
            entry = next(entry for entry in entries if entry["file"] == name)
            entry["result"][0][0] = str(int(entry["result"][0][0]) + 1)
    elif change == "identity":
        precincts[-1] = precincts[0]
    else:
        manual["page-999-row-001-col-1.png"] = 0
    with pytest.raises(ValueError):
        worcester_review.reconcile_counts(entries, manual, precincts)


def boston_page_fixture(columns=None):
    from types import SimpleNamespace

    columns = columns or [("01-01", [90, 17, 4, 0, 4, 115])]
    words = []
    for row, label in enumerate(boston_maps.LABELS):
        x, y = 20, 409.39 + 14.52 * row
        for word in label.split():
            words.append((x, y, x + len(word) * 5, y + 10, word))
            x += len(word) * 5 + 3
    for column, (code, values) in enumerate(columns):
        left = 185.6 + column * 49.2
        if code == "TOTAL":
            words.append((left + 5, 173, left + 35, 183, "TOTAL"))
        else:
            ward, precinct = map(int, code.split("-"))
            for text, x, y in [("WARD", left + 5, 159), (f"{ward},", left + 34, 159),
                               ("PRECINCT", left + 5, 173), (str(precinct), left + 40, 173)]:
                words.append((x, y, x + 5, y + 10, text))
        for row, value in enumerate(values):
            right, y = left + 49.8, 409.75 + 14.52 * row
            text = str(value)
            words.append((right - len(text) * 5, y, right, y + 10, text))
    text = ("UNOFFICIAL BOSTON STATE ELECTION NOVEMBER 2026 (CENTRAL TABULATION) "
            "GOVERNOR & LIEUTENANT HEALEY AND DRISCOLL")
    return SimpleNamespace(rect=SimpleNamespace(width=1008, height=612),
        words=words, text=text,
        get_text=lambda mode=None: words if mode == "words" else text)


def test_boston_native_font_offset_and_candidate_blank_accounting_are_separate():
    page = boston_page_fixture()
    assert boston_maps.page_counts(page) == [
        dict(precinct_code="01-01", values=[90, 17, 4, 0, 4, 115])]


@pytest.mark.parametrize("change", ["none", "footer", "duplicate", "missing_page"])
def test_boston_requires_complete_precinct_inventory_and_exact_native_city_footer(monkeypatch, change):
    from types import SimpleNamespace

    columns = [(f"{i // 12 + 1:02}-{i % 12 + 1:02}", [90, 17, 4, 0, 4, 115])
               for i in range(275)]
    if change == "duplicate":
        columns[-1] = columns[0]
    totals = [275 * n for n in [90, 17, 4, 0, 4, 115]]
    if change == "footer":
        totals[0] += 1
        totals[-1] += 1
    columns.append(("TOTAL", totals))
    pages = [SimpleNamespace(get_text=lambda: "Another contest") for _ in range(288)]
    for slab in range(18):
        pages[slab * 16] = boston_page_fixture(columns[slab * 16:(slab + 1) * 16])
    if change == "missing_page":
        pages.pop()
    monkeypatch.setattr(boston_maps.fitz, "open", lambda **kwargs: pages)
    if change == "none":
        records, audit = boston_maps.review_pdf(b"native PDF bytes")
        assert len(records) == 275 and audit["central_tabulation_ballots"] == 275 * 115
    else:
        with pytest.raises(ValueError):
            boston_maps.review_pdf(b"native PDF bytes")


@pytest.mark.parametrize("change", ["wrong_year", "wrong_mode", "wrong_office",
                                   "missing", "fractional", "unreconciled"])
def test_boston_rejects_wrong_scope_and_missing_counts_without_filling_zero(change):
    page = boston_page_fixture()
    if change.startswith("wrong"):
        old, new = {"wrong_year": ("2026", "2024"),
                    "wrong_mode": ("CENTRAL TABULATION", "COMBINED RESULTS"),
                    "wrong_office": ("GOVERNOR & LIEUTENANT", "ATTORNEY GENERAL")}[change]
        page.get_text = lambda mode=None: page.words if mode == "words" else page.text.replace(old, new)
    elif change == "missing":
        page.words.pop()
    else:
        last = page.words[-1]
        page.words[-1] = (*last[:4], "115.5" if change == "fractional" else "116")
    with pytest.raises(ValueError):
        boston_maps.page_counts(page)


def boston_reference_fixture():
    return dict(type="FeatureCollection", features=[dict(type="Feature",
        properties=dict(ObjectId=1, DISTRICT="01-01", Ward_and_Precinct="01-01",
            Ward="01", Precinct="01", WDPCT="0101", Ward_1787082447332=1,
            Precinct_1787082447332="1"),
        geometry=dict(type="Polygon", coordinates=[
            [[-71.1, 42.3], [-71.09, 42.3], [-71.09, 42.31], [-71.1, 42.31], [-71.1, 42.3]]]))])


def test_boston_preserves_mode_and_zero_counts_without_inventing_turnout_or_winners():
    records = {"01-01": dict(values=[1, 2, 10, 0, 4, 17], source_page=1)}
    parties = {name: dict(party=party) for name, party in zip(boston_maps.NAMES, ["DEM", "REP", "IND"])}
    inventory = dict(objectIdFieldName="ObjectId", objectIds=[1])
    rows, features = boston_maps.mapped_precincts(records, boston_reference_fixture(), inventory, parties)
    assert rows[0]["contest_votes"] == 13 and rows[0]["ballots"] == 17
    assert rows[0]["county"] == "Suffolk" and rows[0]["precinct"] == "Boston Ward 1, Precinct 1"
    assert rows[0]["source_url"] == boston_maps.SOURCE
    assert rows[0]["margin_pp"] == pytest.approx(-100 / 13)
    assert "NOT combined" in rows[0]["ballot_scope"]
    assert "winner" not in rows[0] and "participation" not in features[0]["properties"]
    records["01-01"]["values"] = [0] * 6
    rows, _ = boston_maps.mapped_precincts(records, boston_reference_fixture(), inventory, parties)
    assert rows[0]["contest_votes"] == 0 and rows[0]["margin_pp"] is None


@pytest.mark.parametrize("change", ["unknown", "conflict", "duplicate", "truncated", "invalid", "overlap"])
def test_boston_rejects_ambiguous_or_incomplete_native_reference(change):
    import copy

    records = {"01-01": dict(values=[90, 17, 4, 0, 4, 115], source_page=1)}
    parties = {name: dict(party=party) for name, party in zip(boston_maps.NAMES, ["DEM", "REP", "IND"])}
    reference, inventory = boston_reference_fixture(), dict(objectIdFieldName="ObjectId", objectIds=[1])
    p = reference["features"][0]["properties"]
    if change == "unknown":
        p["DISTRICT"] = "99-99"
    elif change == "conflict":
        p["WDPCT"] = "0102"
    elif change == "truncated":
        reference["exceededTransferLimit"] = True
    elif change == "invalid":
        reference["features"][0]["geometry"]["coordinates"] = [
            [[-71.1, 42.3], [-71.09, 42.31], [-71.1, 42.31], [-71.09, 42.3], [-71.1, 42.3]]]
    else:
        second = copy.deepcopy(reference["features"][0])
        second["properties"]["ObjectId"] = 2
        inventory["objectIds"].append(2)
        reference["features"].append(second)
        if change == "overlap":
            second["properties"].update(DISTRICT="01-02", Ward_and_Precinct="01-02",
                Precinct="02", WDPCT="0102", Precinct_1787082447332="2")
            records["01-02"] = records["01-01"]
    with pytest.raises(ValueError):
        boston_maps.mapped_precincts(records, reference, inventory, parties)


@pytest.mark.parametrize("change", ["wrong_year", "wrong_office", "missing", "low_confidence", "duplicate"])
def test_boston_requires_unambiguous_explicit_native_ticket_party_labels(change):
    lines = [dict(bounds=[.032, .26, .2, .012], candidates=[dict(text=text, confidence=1)])
             for text in ["11/03/2026 STATE ELECTION", "GOVERNOR AND LIEUTENANT GOVERNOR",
                          *(f"{name} ({party})" for name, party in
                            zip(boston_maps.NAMES, ["DEM", "REP", "IND"]))]]
    assert len(boston_maps.party_evidence([dict(lines=lines)])) == 3
    if change == "wrong_year":
        lines[0]["candidates"][0]["text"] = "11/03/2024 STATE ELECTION"
    elif change == "wrong_office":
        lines[1]["candidates"][0]["text"] = "ATTORNEY GENERAL"
    elif change == "missing":
        lines.pop()
    elif change == "low_confidence":
        lines[-1]["candidates"][0]["confidence"] = .9
    else:
        lines.append(lines[-1])
    with pytest.raises(ValueError):
        boston_maps.party_evidence([dict(lines=lines)])


def dc_count_fixture():
    import xml.etree.ElementTree as ET

    info = dict(ElectionName="General Election", ElectionCode="G",
        ElectionDate="2026-11-03T00:00:00", LastUpdated="2026-11-04T04:36:21.283Z",
        ElectionResultsTypeName="Election Night Unofficial Results",
        PrecintsJsonMap="OCTO_VotingPrecinct_2019.json", TotalPrecincts=2, PrecinctsCounted=2)
    names = ["DEM Candidate A", "REP Candidate B", "Write-in", "OVER VOTES", "UNDER VOTES"]
    parties = ["DEM", "REP", "NPN", "", ""]
    votes = [[35, 15, 1, 1, 8], [10, 5, 1, 1, 3]]
    totals = [45, 20, 2, 2, 11]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(dc_maps.HEADERS)
    precinct_map = []
    for pid, registered, ballots, counts in [(1, 100, 60, votes[0]), (2, 50, 20, votes[1])]:
        for cid, name, candidate, party, value in [
            ("-2", "REGISTERED VOTERS - TOTAL", "", "CITYWIDE", registered),
            ("-1", "BALLOTS CAST - TOTAL", "", "CITYWIDE", ballots),
            *(("6", dc_maps.OFFICE, name, party, value)
              for name, party, value in zip(names, parties, counts)),
        ]:
            writer.writerow(["11/3/2026 12:00:00 AM", "General Election", cid, name,
                             pid, 1, candidate, party, value])
        precinct_map.append(dict(ContestNumber=6, OfficeName=dc_maps.OFFICE,
            IsRCV=False, PrecinctNumber=pid,
            ElectionData=[dict(Contestant=n, Votes=v, PartyCode=p or "REP")
                          for n, p, v in zip(names, parties, counts)]))
    citywide = dict(ContestNumber=6, OfficeName=dc_maps.OFFICE, IsRCV=False,
        ElectionData=[dict(Contestant=n, Votes=v, PartyCode=p or "REP")
                      for n, p, v in zip(names, parties, totals)])
    xml = ET.Element("XmlExportViewModel")
    ET.SubElement(xml, "ElectionName").text = "General Election"
    ET.SubElement(xml, "ElectionDate").text = "2026-11-03T00:00:00"
    contests = ET.SubElement(xml, "ContestList")
    for name, values in [(dc_maps.OFFICE, dict(zip(names, totals))),
                         ("REGISTERED VOTERS - TOTAL", {"": 150}),
                         ("BALLOTS CAST - TOTAL", {"": 80})]:
        contest = ET.SubElement(contests, "ContestDataExportViewModel")
        ET.SubElement(contest, "ContestName").text = name
        data = ET.SubElement(contest, "ElectionData")
        for candidate, value in values.items():
            item = ET.SubElement(data, "ElectionDataExportViewModel")
            if candidate:
                ET.SubElement(item, "Candidate").text = candidate
            ET.SubElement(item, "Votes").text = str(value)
    return dict(raw=stream.getvalue().encode(), info=info,
        inventory=dict(PrecinctNumberList=[1, 2]), citywide=[citywide], xml_raw=ET.tostring(xml),
        summary=dict(SummaryType="c", WardNumber=None, PrecinctNumber=None, Party=None,
                     RegisteredVoters=150, TotalBallotsCast=80, ElectionDayVoters=50,
                     EarlyVotes=0, AbsenteeSpecialBallotVotes=30),
        precinct_map=dict(cityWideResults=[citywide], wardPrecinctResults=precinct_map))


def dc_topology_fixture():
    return dict(type="Topology", transform=dict(scale=[0.001, 0.001], translate=[-77, 38.9]),
        arcs=[[[0, 0], [1, 0], [0, 1], [-1, 0], [0, -1]],
              [[5, 0], [1, 0], [0, 1], [-1, 0], [0, -1]]],
        objects=dict(precinct_octo=dict(type="GeometryCollection", geometries=[
            dict(type="Polygon", properties=dict(NAME="Precinct 1", OBJECTID=1), arcs=[[0]]),
            dict(type="Polygon", properties=dict(NAME="Precinct 2", OBJECTID=2), arcs=[[-2]])])))


def test_dc_reconciles_precinct_csv_native_json_xml_and_separate_participation():
    rows, statistics, audit = dc_maps.review_counts(**dc_count_fixture())
    assert rows[0]["contest_votes"] == 51
    assert rows[0]["republican_votes"] == 15
    assert rows[0]["other_votes"] == 1
    assert rows[0]["overvotes"] == 1 and rows[0]["undervotes"] == 8
    assert statistics[0]["ballots"] == 60 and statistics[0]["registered"] == 100
    assert statistics[0]["reported_pct"] == 60
    assert "not final turnout" in statistics[0]["basis"]
    assert audit["final_turnout_rates"] == audit["demographic_rates"] == 0
    assert audit["registered"] == 150 and audit["ballots"] == 80
    assert audit["separate_contest_accounting_differences"] == []


@pytest.mark.parametrize("change", ["wrong_election", "rcv", "duplicate", "missing_precinct",
                                   "native_count", "aggregate", "party", "negative", "xml"])
def test_dc_rejects_wrong_scope_ambiguous_rows_and_nonreconciling_counts(change):
    args = dc_count_fixture()
    if change == "wrong_election":
        args["info"]["ElectionDate"] = "2024-11-05T00:00:00"
    elif change == "rcv":
        args["citywide"][0]["IsRCV"] = True
    elif change == "duplicate":
        args["raw"] += args["raw"].splitlines(keepends=True)[1]
    elif change == "missing_precinct":
        args["precinct_map"]["wardPrecinctResults"].pop()
    elif change == "native_count":
        args["precinct_map"]["wardPrecinctResults"][0]["ElectionData"][0]["Votes"] += 1
    elif change == "aggregate":
        args["summary"]["TotalBallotsCast"] -= 1
    elif change == "party":
        args["raw"] = args["raw"].replace(b"DEM Candidate A,DEM", b"DEM Candidate A,REP")
    elif change == "negative":
        args["raw"] = args["raw"].replace(b"CITYWIDE,100", b"CITYWIDE,-100")
    elif change == "xml":
        args["xml_raw"] = args["xml_raw"].replace(b"<Votes>150", b"<Votes>149")
    with pytest.raises(ValueError):
        dc_maps.review_counts(**args)


def test_dc_withholds_inconsistent_rates_without_repairing_native_ballot_counts():
    args = dc_count_fixture()
    args["raw"] = args["raw"].replace(b"CITYWIDE,100", b"CITYWIDE,50")
    args["xml_raw"] = args["xml_raw"].replace(b"<Votes>150", b"<Votes>100")
    args["summary"]["RegisteredVoters"] = 100
    _, stats, audit = dc_maps.review_counts(**args)
    assert stats[0]["registered"] == 50 and stats[0]["ballots"] == 60
    assert stats[0]["reported_pct"] is None
    assert stats[1]["reported_pct"] == 40
    assert audit["provisional_reported_fractions"] == 1


def test_dc_retains_contest_accounting_difference_without_using_votes_as_ballots():
    args = dc_count_fixture()
    args["raw"] = args["raw"].replace(b"CITYWIDE,60", b"CITYWIDE,61")
    args["xml_raw"] = args["xml_raw"].replace(b"<Votes>80", b"<Votes>81")
    args["summary"].update(TotalBallotsCast=81, ElectionDayVoters=51)
    rows, stats, audit = dc_maps.review_counts(**args)
    assert rows[0]["contest_votes"] == 51 and stats[0]["ballots"] == 61
    assert audit["separate_contest_accounting_differences"] == [
        dict(precinct=1, ballots_minus_contest_accounting=1)]


def test_dc_decodes_forward_and_reversed_native_arcs_and_joins_complete_ids():
    features = dc_maps.topology_features(dc_topology_fixture())
    rows, stats, _ = dc_maps.review_counts(**dc_count_fixture())
    mapped, audit = dc_maps.mapped_precincts(rows, stats, features)
    assert len(mapped) == audit["mapped_units"] == 2
    assert mapped[0]["properties"]["source_object_ids"] == [1]
    assert mapped[0]["properties"]["participation"]["ballots"] == 60
    assert mapped[1]["geometry"]["coordinates"][0][0] == pytest.approx([-76.995, 38.9])


@pytest.mark.parametrize("change", ["missing", "duplicate", "unknown", "projection", "arc"])
def test_dc_rejects_ambiguous_reference_sets_invalid_arcs_and_geometry(change):
    topology = dc_topology_fixture()
    if change == "arc":
        topology["objects"]["precinct_octo"]["geometries"][0]["arcs"] = [[999]]
    features = None
    if change != "arc":
        features = dc_maps.topology_features(topology)
        if change == "missing":
            features.pop()
        elif change == "duplicate":
            features.append(features[0])
        elif change == "unknown":
            features[0]["properties"]["NAME"] = "Precinct 3"
        elif change == "projection":
            features[0]["geometry"]["coordinates"][0][0][0] = 100000
    rows, stats, _ = dc_maps.review_counts(**dc_count_fixture())
    with pytest.raises(ValueError):
        dc_maps.mapped_precincts(rows, stats, features or dc_maps.topology_features(topology))


def test_dc_withholds_ambiguous_strips_from_both_precincts_without_allocating_counts():
    topology = dc_topology_fixture()
    topology["arcs"][1][0][0] = 0
    topology["arcs"][1][1][0] = 2
    topology["arcs"][1][3][0] = -2
    features = dc_maps.topology_features(topology)
    rows, stats, _ = dc_maps.review_counts(**dc_count_fixture())
    mapped, audit = dc_maps.mapped_precincts(rows, stats, features)
    assert len(mapped) == 1 and audit["withheld_units"] == ["1"]
    assert len(audit["all_reference_overlap_pairs"]) == 1
    assert len(audit["ambiguity_mask"]["features"]) == 2
    assert audit["topology_repairs"] == []
    assert mapped[0]["properties"]["contest_votes"] == 16
    assert mapped[0]["properties"]["participation"]["ballots"] == 20
    assert "never an allocation" in mapped[0]["properties"]["boundary_provenance"]


def test_explicit_mapped_participation_updates_only_its_exact_coverage_cell():
    index = dict(coverage={})
    before = precinct_coverage.build_rows(index)
    index["coverage"] = {"2026": {"DC": dict(partial=True, source_url="reviewed",
        next_action="Review certification", notes="Not final turnout",
        participation="acquired_precinct_counts_and_registration")}}
    after = precinct_coverage.build_rows(index)
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    assert len(before) == len(after) == 1632
    assert len(changed) == 1
    assert changed[0][1]["state_code"] == "DC" and changed[0][1]["year"] == 2026
    assert changed[0][1]["participation"] == "acquired_precinct_counts_and_registration"
    assert changed[0][1]["complete"] == "no"


def test_dc_extracts_only_the_election_declared_literal_module_without_executing_code():
    prefix = ('webpackJsonp([0],Array(10).concat([function(e){'
              'var i={"./reference.json":11};},function(e){e.exports=')
    bundle = (prefix + json.dumps(dc_topology_fixture()) + "}]))").encode()
    extracted = dc_maps.extract_reference(bundle, "reference.json")
    assert extracted == dict(module_id=11, topology=dc_topology_fixture())
    with pytest.raises(ValueError):
        dc_maps.extract_reference(bundle, "another-year.json")
    executable = (prefix + '(()=>{throw Error("must not execute")})()' + "}]))").encode()
    with pytest.raises(ValueError, match="Executable expression"):
        dc_maps.extract_reference(executable, "reference.json")


def clark_index_fixture():
    links = "".join(
        f'<a href="https://elections.clarkcountynv.gov/electionresultsTV/SOV/24G/'
        f'CONTEST%20{i:03d}.{extension}">{extension}</a>'
        for i in range(100) for extension in ("pdf", "txt"))
    return ('<select name="ddlElection"><option selected value="24G">'
            '2024 GENERAL ELECTION (11/05/2024)</option></select>'
            '<select name="ddlCategory"><option selected value="3">'
            'STATEMENT OF VOTE (RESULTS BY PRECINCT)</option></select>' + links).encode()


def clark_data_fixture():
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["Precinct", "Tally Type", "Registration", "Turnout", "Total Votes",
                     "Candidate A", "Candidate B"])
    for mode, turnout, total, votes in [
        ("Totals", 3, 3, ["*", "*"]), ("Election Day", 0, 0, ["0", "0"]),
        ("Early Vote", 3, 3, ["*", "*"]), ("Mail", 0, 0, ["0", "0"]),
    ]:
        writer.writerow(["1000", mode, 1, turnout, total, *votes])
    writer.writerow(["Totals", "Tally Type", "# Voters", "Voters/Turnout"])
    for mode in clark_originals.MODES[1:]:
        writer.writerow([mode, "3" if mode == "Early Vote" else "0", "0.0%"])
    return stream.getvalue().encode()


def test_clark_declared_full_queries_preserve_both_report_formats():
    urls = clark_originals.report_links(clark_index_fixture(), 2024)
    assert len(urls) == 200
    assert sum(url.endswith(".pdf") for url in urls) == 100
    assert sum(url.endswith(".txt") for url in urls) == 100


@pytest.mark.parametrize("old,new", [
    (b'value="24G"', b'value="26PE"'),
    (b'2024 GENERAL ELECTION (11/05/2024)', b'2024 PRIMARY ELECTION (06/11/2024)'),
    (b'value="3"', b'value="4"'),
    (b'/SOV/24G/CONTEST%20000.pdf', b'/SOV/22G/CONTEST%20000.pdf'),
    (b'/SOV/24G/CONTEST%20000.pdf', b'/SOV/24G/CONTEST%20001.pdf'),
    (b'/SOV/24G/CONTEST%20000.txt', b'/SOV/24G/OTHER%20000.txt'),
    (b'/SOV/24G/CONTEST%20000.pdf', b'/SOV/24G/CONTEST%20000.pdf?alternate=1'),
    (b'/SOV/24G/CONTEST%20000.pdf', b'/SOV/24G/other%2FCONTEST%20000.pdf'),
])
def test_clark_rejects_wrong_election_scope_missing_pairs_and_changed_declarations(old, new):
    with pytest.raises(ValueError):
        clark_originals.report_links(clark_index_fixture().replace(old, new), 2024)


def test_clark_data_inventory_flags_suppression_and_bad_denominator_without_repairs():
    result = clark_originals.text_inventory(clark_data_fixture())
    assert result["native_data_records"] == 4
    assert result["privacy_suppressed_candidate_fields"] == 4
    assert result["totals_records_turnout_exceeds_registration"] == 1
    assert result["rows_by_tally_type"] == dict.fromkeys(clark_originals.MODES, 1)
    assert result["strict_csv_error"] is None


def test_clark_native_quoting_error_is_reported_not_canonicalized_as_candidate_identity():
    raw = clark_data_fixture().replace(b"Candidate A", b'"Candidate "Nickname" Name"')
    result = clark_originals.text_inventory(raw)
    assert result["strict_csv_error"]["physical_line"] == 1
    assert result["native_data_records"] == 4
    assert result["privacy_suppressed_candidate_fields"] == 4


@pytest.mark.parametrize("old,new", [
    (b"Precinct,Tally Type", b"County,Tally Type"),
    (b"1000,Mail", b"1001,Mail"),
    (b"1000,Early Vote", b"1000,Unknown"),
    (b"1000,Mail,1,0,0,0,0\r\n", b""),
    (b"Totals,Tally Type,# Voters,Voters/Turnout", b""),
    (b"Mail,0,0.0%\r\n", b"Mail,0,0.0%,extra\r\n"),
])
def test_clark_truncated_or_changed_native_records_fail_closed(old, new):
    raw = clark_data_fixture()
    assert old in raw
    with pytest.raises(ValueError):
        clark_originals.text_inventory(raw.replace(old, new))


@pytest.mark.parametrize("field,value", [
    ("url", "https://example.org/results.aspx"),
    ("resolved_url", "https://example.org/results.aspx"),
    ("status", 403), ("method", "POST"), ("bytes", 1), ("sha256", "0" * 64),
])
def test_clark_failed_or_changed_original_receipt_is_rejected(tmp_path, field, value):
    raw = clark_index_fixture()
    receipt = dict(url=clark_originals.SOURCE, resolved_url=clark_originals.SOURCE,
                   status=200, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    (tmp_path / "source.html").write_bytes(raw)
    receipt[field] = value
    (tmp_path / "source.html.receipt.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        clark_originals.original(tmp_path, "source.html", clark_originals.SOURCE)


@pytest.mark.parametrize("wrong", ["year", "date", "county", None])
def test_clark_pdf_checks_actual_election_date_and_county(wrong):
    lines = ["2024 General Election", "November 05, 2024", "Statement of Vote", "Clark County"]
    if wrong == "year":
        lines[0] = "2026 General Election"
    elif wrong == "date":
        lines[1] = "November 08, 2022"
    elif wrong == "county":
        lines[3] = "Washoe County"
    with clark_originals.fitz.open() as doc:
        doc.new_page().insert_text((72, 72), "\n".join(lines))
        raw = doc.tobytes()
    if wrong is None:
        assert clark_originals.pdf_inventory(raw, 2024)["pages"] == 1
    else:
        with pytest.raises(ValueError):
            clark_originals.pdf_inventory(raw, 2024)


@pytest.mark.parametrize("continuation", [
    "native", "wrong_election", "blank_terminal", "blank_middle", "textless_marks"])
def test_clark_pdf_preserves_native_continuations_and_blank_endings_but_rejects_conflicts(continuation):
    with clark_originals.fitz.open() as doc:
        doc.new_page().insert_text((72, 72),
            "2024 General Election\nNovember 05, 2024\nStatement of Vote\nClark County")
        page = doc.new_page()
        if continuation == "native":
            page.insert_text((72, 72), "Registered\nTurnout\nPercent\nEarly Vote\n100\nMail\n200")
        elif continuation == "wrong_election":
            page.insert_text((72, 72),
                "2022 General Election\nNovember 08, 2022\nStatement of Vote\nClark County")
        elif continuation == "blank_middle":
            doc.new_page().insert_text((72, 72), "Registered\nTurnout\nPercent\nMail")
        elif continuation == "textless_marks":
            page.draw_rect(clark_originals.fitz.Rect(72, 72, 100, 100), fill=(0, 0, 0))
        raw = doc.tobytes()
    if continuation in {"native", "blank_terminal"}:
        result = clark_originals.pdf_inventory(raw, 2024)
        assert result["pages"] == 2 and result["pages_with_election_identity"] == 1
        assert result["continuation_pages_without_repeated_identity"] == (continuation == "native")
        assert result["blank_terminal_pages"] == ([2] if continuation == "blank_terminal" else [])
    else:
        with pytest.raises(ValueError):
            clark_originals.pdf_inventory(raw, 2024)


def missouri_christian_fixture():
    units, statement = {}, {}
    for label, registered, ballots, votes in [
        ("1. SHARED/2. COMBINED", 100, 40, [20, 10, 5]),
        ("3. SHARED", 200, 80, [35, 30, 5]),
        ("ABSENTEE", 0, 30, [20, 5, 0]),
    ]:
        candidates = dict(zip(mo_christian.CANDIDATES, votes))
        units[label] = dict(registered=registered, ballots=ballots, candidate_votes=candidates,
            source_reported_percent="40.00%" if registered else "N/A", source_pages=[1, 2])
        statement[label] = {mode: dict(registered=registered,
            candidate_votes=candidates.copy() if (mode == "Absentee") == (label == "ABSENTEE")
            else dict.fromkeys(candidates, 0)) for mode in ("Normal", "Absentee")}
    totals = {name: sum(unit["candidate_votes"][name] for unit in units.values())
              for name in mo_christian.CANDIDATES}
    summary = dict(registered=300, ballots=150, source_reported_percent="50.00%", candidate_votes=totals)
    statement["Total"] = {mode: dict(registered=300, candidate_votes={
        name: sum(values[mode]["candidate_votes"][name] for values in statement.values())
        for name in mo_christian.CANDIDATES}) for mode in ("Normal", "Absentee")}
    statement["Total"]["Total"] = dict(registered=300, candidate_votes=totals.copy())
    return units, summary, statement


def missouri_house_lines(votes, summary=False):
    lines = [mo_christian.CONTEST]
    if summary:
        lines += ["Number of Precincts", "27", "Precincts Reporting", "27"]
    lines += ["Vote For 1"]
    for name, value in votes.items():
        lines += [name + "  (" + mo_christian.CANDIDATES[name] + ")", str(value),
                  f"{100 * value / sum(votes.values()):.2f}%"]
    return lines + [str(sum(votes.values())), "Total Votes"]


def missouri_statement_pages(statement):
    pages = []
    for i, unit in enumerate(list(statement)[:-1], 1):
        body = [f"Page {i}/3", mo_christian.CONTEST, *mo_christian.STATEMENT_HEADER]
        if i == 1:
            body += ["Jurisdiction Wide"]
        for label in ([unit, "Total"] if i == 3 else [unit]):
            body += label.rsplit(" ", 1) if "/" in label else [label]
            for mode, values in statement[label].items():
                votes = values["candidate_votes"]
                total = sum(votes.values())
                body += [mode, str(values["registered"]), str(total)]
                for value in votes.values():
                    body += [str(value), f"{100 * value / total:.2f}%" if total else "-"]
        pages.append(body)
    return pages


def test_missouri_christian_preserves_combined_units_absentee_and_unique_registration():
    units, summary, statement = missouri_christian_fixture()
    results, participation = mo_christian.review(units, summary, statement, expected_units=3)
    assert len({row["key"] for row in results}) == 3
    assert results[0]["source_unit_id"] == "1. SHARED/2. COMBINED"
    assert results[-1]["source_unit_kind"] == "countywide_absentee"
    assert sum(row["contest_votes"] for row in results) == 130
    assert sum(row["registered"] for row in participation) == 300
    assert sum(row["ballots"] for row in participation) == 150
    assert participation[-1]["registered"] == 0 and participation[-1]["ballots"] == 30
    assert all(row["turnout_rate"] is None for row in participation)
    assert participation[0]["source_reported_percent"] == "40.00%"
    assert participation[-1]["source_reported_percent"] == "N/A"
    assert all("registered" not in row for row in results)


@pytest.mark.parametrize("change,message", [
    ("missing-unit", "unit sets"),
    ("extra-unit", "unit sets"),
    ("scope", "unit sets"),
    ("absentee-denominator", "absentee scope"),
    ("allocated-absentee", "mode scope"),
    ("unit-vector", "House vector"),
    ("unit-registration", "registration differs"),
    ("county-ballots", "county totals"),
    ("county-registration", "county totals"),
    ("county-candidate", "county totals"),
    ("statement-mode-total", "mode totals"),
    ("repeated-county-registration", "county totals"),
    ("votes-exceed-ballots", "relationship"),
])
def test_missouri_christian_rejects_allocation_scope_and_independent_mismatches(change, message):
    units, summary, statement = missouri_christian_fixture()
    expected_units = 3
    if change == "missing-unit":
        statement.pop("3. SHARED")
    elif change == "extra-unit":
        statement["4. EXTRA"] = statement["3. SHARED"]
    elif change == "scope":
        expected_units = 4
    elif change == "absentee-denominator":
        units["ABSENTEE"]["registered"] = 300
    elif change == "allocated-absentee":
        statement["3. SHARED"]["Normal"]["candidate_votes"]["ERIC W. BURLISON"] -= 1
        statement["3. SHARED"]["Absentee"]["candidate_votes"]["ERIC W. BURLISON"] = 1
    elif change == "unit-vector":
        units["3. SHARED"]["candidate_votes"]["MISSI HESKETH"] += 1
    elif change == "unit-registration":
        statement["3. SHARED"]["Normal"]["registered"] += 1
    elif change == "county-ballots":
        summary["ballots"] += 1
    elif change == "county-registration":
        summary["registered"] += 300
    elif change == "county-candidate":
        summary["candidate_votes"]["MISSI HESKETH"] += 1
    elif change == "statement-mode-total":
        statement["Total"]["Normal"]["candidate_votes"]["MISSI HESKETH"] += 1
    elif change == "repeated-county-registration":
        statement["Total"]["Total"]["registered"] *= 3
    elif change == "votes-exceed-ballots":
        units["3. SHARED"]["ballots"] = 1
    with pytest.raises(ValueError, match=message):
        mo_christian.review(units, summary, statement, expected_units=expected_units)


def test_missouri_christian_parses_independent_statement_modes_without_summing_denominators():
    _, _, statement = missouri_christian_fixture()
    pages = missouri_statement_pages(statement)
    parsed = mo_christian.statement_units(pages)
    assert parsed == statement


@pytest.mark.parametrize("change,message", [
    ("missing-page", "page sequence"),
    ("party", "candidate columns"),
    ("repeated-registration", "registration"),
    ("missing-count", "native count"),
    ("sum", "sum differs"),
    ("percentage", "percentage"),
    ("duplicate-unit", "duplicate"),
])
def test_missouri_christian_rejects_malformed_independent_statement(change, message):
    _, _, statement = missouri_christian_fixture()
    pages = missouri_statement_pages(statement)
    if change == "missing-page":
        pages.pop(1)
    elif change == "party":
        pages[0][pages[0].index("(DEM)")] = "(REP)"
    elif change == "duplicate-unit":
        pages[1][pages[1].index("3. SHARED")] = "ABSENTEE"
    else:
        offset = pages[0].index("Normal")
        if change == "repeated-registration":
            pages[0][pages[0].index("Absentee") + 1] = "200"
        elif change == "missing-count":
            pages[0][offset + 3] = "-"
        elif change == "sum":
            pages[0][offset + 2] = "36"
        elif change == "percentage":
            pages[0][offset + 4] = "100.00%"
    with pytest.raises(ValueError, match=message):
        mo_christian.statement_units(pages)


@pytest.mark.parametrize("change", ["duplicate", "party", "missing", "sum", "percentage"])
def test_missouri_christian_rejects_incomplete_or_conflicting_house_vectors(change):
    votes = next(iter(missouri_christian_fixture()[0].values()))["candidate_votes"]
    lines = missouri_house_lines(votes)
    if change == "duplicate":
        lines[5] = lines[2]
    elif change == "party":
        lines[2] = lines[2].replace("(REP)", "(DEM)")
    elif change == "missing":
        lines[3] = "-"
    elif change == "sum":
        lines[-2] = "36"
    elif change == "percentage":
        lines[4] = "100.00%"
    with pytest.raises(ValueError):
        mo_christian.house_vector(lines)


@pytest.mark.parametrize("change", ["county", "year", "election", "official"])
def test_missouri_christian_requires_exact_pdf_election_identity(change):
    lines = ["Precinct Summary Report", "GENERAL ELECTION", "CHRISTIAN COUNTY, MISSOURI",
             "TUESDAY, NOVEMBER 3, 2026", "ELECTION RESULTS", "UNOFFICIAL", "Date: 11/3/2026"]
    if change == "county":
        lines[2] = "OTHER COUNTY, MISSOURI"
    elif change == "year":
        lines[3] = "TUESDAY, NOVEMBER 5, 2024"
    elif change == "election":
        lines[1] = "PRIMARY ELECTION"
    else:
        lines[5] = "OFFICIAL"
    with mo_christian.fitz.open() as pdf:
        pdf.new_page().insert_text((30, 30), "\n".join(lines))
        with pytest.raises(ValueError, match="identity"):
            mo_christian.pdf_pages(pdf.tobytes(), "Precinct Summary Report")


def missouri_precinct_pages(units):
    pages = []
    for label, values in units.items():
        counts = (f"Registered Voters {values['registered']} - Total Ballots {values['ballots']}"
                  f" : {values['source_reported_percent']}")
        for number in (1, 2):
            page = ["Precinct Summary Report", "GENERAL ELECTION", "CHRISTIAN COUNTY, MISSOURI",
                    "TUESDAY, NOVEMBER 3, 2026", "ELECTION RESULTS", label, "UNOFFICIAL",
                    "Date: 11/3/2026", f"Page {number}/2", counts]
            if number == 1:
                page += missouri_house_lines(values["candidate_votes"])
            pages.append(page)
    return pages


def test_missouri_christian_parses_complete_native_pairs_and_retains_source_pages():
    units, _, _ = missouri_christian_fixture()
    parsed = mo_christian.precinct_units(missouri_precinct_pages(units), expected_units=3)
    assert list(parsed) == list(units)
    assert parsed["ABSENTEE"]["registered"] == 0
    assert parsed["ABSENTEE"]["source_pages"] == [5, 6]
    assert parsed["1. SHARED/2. COMBINED"]["candidate_votes"] == units["1. SHARED/2. COMBINED"]["candidate_votes"]


@pytest.mark.parametrize("change,message", [
    ("missing-page", "Incomplete"),
    ("page-order", "page identity"),
    ("unit-name", "unit or page identity"),
    ("duplicate-unit", "Duplicate"),
    ("repeated-count", "Conflicting"),
    ("double-house", "Conflicting"),
    ("missing-house", "House contest"),
])
def test_missouri_christian_rejects_bad_native_pairs_and_repeated_fields(change, message):
    units, _, _ = missouri_christian_fixture()
    pages = missouri_precinct_pages(units)
    if change == "missing-page":
        pages.pop()
    elif change == "page-order":
        pages[0], pages[1] = pages[1], pages[0]
    elif change == "unit-name":
        pages[1][5] = "9. OTHER"
    elif change == "duplicate-unit":
        pages[2][5] = pages[3][5] = pages[0][5]
    elif change == "repeated-count":
        pages[1][-1] = pages[1][-1].replace("Ballots 40 : 40.00%", "Ballots 50 : 50.00%")
    elif change == "double-house":
        pages[1].append(mo_christian.CONTEST)
    elif change == "missing-house":
        pages[0].remove(mo_christian.CONTEST)
    with pytest.raises(ValueError, match=message):
        mo_christian.precinct_units(pages, expected_units=3)


@pytest.mark.parametrize("field,bad_value", [
    ("url", "https://example.invalid/other-election"),
    ("resolved_url", "https://example.invalid/challenge"),
    ("status", 403),
    ("bytes", 100),
    ("sha256", "0" * 64),
])
def test_missouri_christian_rejects_changed_original_receipts(tmp_path, monkeypatch, field, bad_value):
    name = "official-election-index.html"
    raw = b"original"
    (tmp_path / name).write_bytes(raw)
    receipt = dict(url=mo_christian.SOURCE, resolved_url=mo_christian.SOURCE, status=200,
                   bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    receipt[field] = bad_value
    (tmp_path / (name + ".receipt.json")).write_text(json.dumps(receipt))
    monkeypatch.setattr("sys.argv", ["review", "--cache-directory", str(tmp_path),
        "--output", str(tmp_path / "output"), "--archive", str(tmp_path / "archive.zip")])
    with pytest.raises(ValueError, match="receipt"):
        mo_christian.main()


def florida_monroe_fixture():
    rows, summary = [], []
    for name, party, total in [('Candidate "One"', "DEM", 60), ("Two", "REP", 60), ("Three", "NPA", 6)]:
        common = dict(zip(fl_monroe.SUMMARY_FIELDS[:3], [fl_monroe.CONTEST, name, party]))
        for unit in ("1-Shared Hall", "2-Shared Hall"):
            modes = ["0", "20", "20", "20"] if total == 60 else ["-", "-", "-", "-"]
            rows.append(dict(common, **dict(zip(fl_monroe.MODES, modes)),
                             **{"Precinct Name": unit, "Total Votes": str(total), "% of Total Votes": "0.00"}))
        modes = ["0", "40", "40", "40"] if total == 60 else ["0", "4", "4", "4"]
        summary.append(dict(common, **dict(zip(fl_monroe.MODES, modes)),
                            **{"Total Votes": str(total * 2), "% of Total Votes": "0.00"}))
    return rows, summary


def test_florida_monroe_reconciles_candidates_without_merging_polling_places_or_imputing_modes():
    rows, summary = florida_monroe_fixture()
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fl_monroe.PRECINCT_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    results, native, audit = fl_monroe.review(fl_monroe.read_table(buffer.getvalue().encode()),
                                              summary, expected_units=2)
    assert len(results) == 2 and len({row["key"] for row in results}) == 2
    assert sum(row["contest_votes"] for row in results) == 252
    assert json.loads(results[0]["candidate_votes"])['Candidate "One"'] == 60
    assert native[-1]["parsed_votes"]["modes"] == dict.fromkeys(fl_monroe.MODES)
    assert audit["suppressed_native_mode_fields"] == 8
    comparisons = [row for row in audit["mode_comparisons"] if row["party"] == "NPA"]
    assert all(row["status"] == "withheld_suppressed" for row in comparisons)
    assert all("registered" not in row and "turnout_rate" not in row for row in results)


@pytest.mark.parametrize("change,message", [
    ("duplicate", "Duplicate"),
    ("missing", "total differs|matrix"),
    ("blank-mode", "Invalid or missing"),
    ("suppressed-total", "Invalid or missing"),
    ("wrong-contest", "House contest"),
    ("summary-total", "total differs"),
    ("mode-total", "mode total differs"),
    ("scope", "reporting scope"),
    ("name-collision", "candidate/party scope"),
])
def test_florida_monroe_rejects_bad_scope_missing_counts_and_independent_mismatches(change, message):
    rows, summary = florida_monroe_fixture()
    units = 2
    if change == "duplicate":
        rows.append(rows[0].copy())
    elif change == "missing":
        rows.pop(0)
    elif change == "blank-mode":
        rows[0]["Mail Votes"] = ""
    elif change == "suppressed-total":
        rows[0]["Total Votes"] = "-"
    elif change == "wrong-contest":
        rows[0]["Contest"] = "Representative in Congress Dist 27"
    elif change == "summary-total":
        summary[0].update({"Total Votes": "121", "Mail Votes": "41"})
    elif change == "mode-total":
        summary[0].update({"Mail Votes": "41", "Early Votes": "39"})
    elif change == "scope":
        units = 3
    elif change == "name-collision":
        for row in rows + summary:
            if row["Party"] == "REP":
                row["Candidate Issue"] = 'Candidate "One"'
    with pytest.raises(ValueError, match=message):
        fl_monroe.review(rows, summary, expected_units=units)


@pytest.mark.parametrize("change", ["bytes", "county", "year", "failed"])
def test_florida_monroe_rejects_changed_or_wrong_source_receipts(tmp_path, change):
    raw, url = b"<html>original</html>", fl_monroe.SOURCE + "Reports/"
    name = "official-reports.html"
    receipt = dict(url=url, resolved_url=url, status_code=200, bytes=len(raw),
                   sha256=hashlib.sha256(raw).hexdigest())
    if change == "bytes":
        raw += b"changed"
    elif change in ("county", "year"):
        receipt["url"] = url.replace("MON", "PAL") if change == "county" else url.replace("4109", "2024")
    else:
        receipt["status_code"] = 403
    (tmp_path / name).write_bytes(raw)
    (tmp_path / (name + ".source.json")).write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="original receipt"):
        fl_monroe.original(tmp_path, name, url)


@pytest.mark.parametrize("old,new,message", [
    ("2026", "2024", "election identity"),
    ("/MON/", "/PAL/", "election identity"),
    ("Registered Voters:", "Missing field:", "participation field"),
    ("33 / 33", "32 / 33", "reporting scope"),
])
def test_florida_monroe_checks_independent_html_election_county_and_count_scope(old, new, message):
    raw = ('<img src="//s3.amazonaws.com/vr-enr/MON/wf_banner.jpg">'
           '<div id="ElectionName"><h1>November 3, 2026 General</h1></div>'
           '<h2>Election Date: 11/3/2026</h2>'
           '<div class="TurnoutLabel">Registered Voters: </div><div class="TurnoutValue">54,704</div>'
           '<div class="TurnoutLabel">Ballots Cast: </div><div class="TurnoutValue">32,506</div>'
           '<div class="TurnoutLabel">Voter Turnout: </div><div class="TurnoutValue">59.42%</div>'
           '<div class="PrecinctsValue">33 / 33</div>')
    assert fl_monroe.html_statistics(raw.encode())["ballots"] == 32506
    with pytest.raises(ValueError, match=message):
        fl_monroe.html_statistics(raw.replace(old, new).encode())


def connecticut_report_fixture():
    rows = [
        ["STATE OF CONNECTICUT OFFICE OF THE SECRETARY OF THE STATE"],
        ["Election Results by Voting District "], ct_originals.CANDIDATES,
        ["November 2026 State Election", "Town", "State Election", "November 03' 2026",
         "Clerk", "Representative in Congress 1", "Candidate\nOne", "Democratic Party",
         "DISTRICT 1-Town Hall", "5", "2", "3", "0", "0", "10", ""],
        [], ct_originals.REGISTRY,
        ["Town", "DISTRICT 1-Town Hall", "100", "5", ""],
        ["Town", "DISTRICT 1-Town Hall", "100", "5", ""],
        [], ct_originals.MODES,
        ["Town", "DISTRICT 1-Town Hall", "5", "2", "0", "0", "3", "0", "0", "0", ""],
        [], ct_originals.QUESTIONS,
        ["Election 2026", "State Election", "Town", "1", "Question\nwith quoted text", "-", "2", "-", "-", ""],
    ]
    output = io.StringIO(newline="")
    csv.writer(output).writerows(rows)
    return output.getvalue().encode()


def test_ct_original_report_keeps_multiline_records_sections_and_repeated_denominators_separate():
    inventory = ct_originals.report_inventory(connecticut_report_fixture(), 2026, {"Town"})
    candidate, registry, modes = inventory["sections"]
    assert candidate["native_records"] == 1 and candidate["house_candidate_party_records"] == 1
    assert candidate["house_native_mode_sum_discrepancies"] == 0
    assert registry["native_records"] == 2 and modes["native_records"] == 1
    assert registry["duplicate_literal_town_polling_labels"] == [
        dict(town="Town", polling_label="DISTRICT 1-Town Hall", records=2)]
    assert "precinct_rates" not in inventory and inventory["full_report_strict_csv_error"] is None


@pytest.mark.parametrize("old,new,message", [
    (b"November 03' 2026", b"November 03' 2024", "election year"),
    (b",5,2,3,0,0,10,", b",-,2,3,0,0,10,", "invalid native count"),
    (b"No. Checked as Having Voted", b"Missing section", "report section"),
])
def test_ct_original_report_rejects_mixed_years_missing_counts_and_incomplete_sections(old, new, message):
    raw = connecticut_report_fixture()
    assert old in raw
    with pytest.raises(ValueError, match=message):
        ct_originals.report_inventory(raw.replace(old, new), 2026, {"Town"})


def test_ct_original_receipts_reject_changed_bytes_and_metadata_only_batches(tmp_path):
    with pytest.raises(ValueError, match="metadata-only"):
        ct_originals.election_originals(tmp_path, 2026, "108")
    (tmp_path / "Version.json").write_bytes(b"changed")
    (tmp_path / "Version.json.source.json").write_text(json.dumps(dict(
        status_code=200, bytes=7, sha256="wrong")))
    with pytest.raises(ValueError, match="Changed or failed"):
        ct_originals.election_originals(tmp_path, 2026, "108")


def test_ct_original_negative_adjustments_are_preserved_and_flagged_not_clamped():
    raw = connecticut_report_fixture().replace(b",5,2,3,0,0,10,", b",5,2,3,0,-12,10,")
    candidate = ct_originals.report_inventory(raw, 2026, {"Town"})["sections"][0]
    assert candidate["negative_native_fields"] == [
        dict(section_record=1, field="Unknown", source_value="-12")]
    assert candidate["house_native_mode_sum_discrepancies"] == 1


def test_ct_original_nonstandard_candidate_quoting_is_recorded_without_rewriting_source():
    raw = connecticut_report_fixture().replace(b'"Candidate\nOne"', b'"Candidate "One""')
    inventory = ct_originals.report_inventory(raw, 2026, {"Town"})
    assert inventory["sections"][0]["native_records"] == 1
    assert inventory["full_report_strict_csv_error"]["error"] == "',' expected after '\"'"


def rhode_island_fixture():
    import copy
    names = [("Town", "00000000-0000-0000-0000-000000000001"),
             ("Federal", "00000000-0000-0000-0000-000000000002")]
    state, public, localities = [], [], []
    for identity, title in ri_review.CONTESTS.items():
        options, independent = [], []
        for cid, name, party in [("1", "Democrat", "DEMOCRAT"),
                                 ("2", "Republican", "REPUBLICAN"), ("3", "Write-in", None)]:
            groups = [dict(groupName=m, voteCount=2, isFromVirtualPrecinct=False)
                      for m in sorted(ri_review.MODES)]
            options.append(dict(id=cid, name=name, politicalParty=party,
                                voteCount=6, groupResults=groups))
            independent.append(dict(nativeId=cid, name=[dict(languageId="en", text=name)],
                voteCount=6, party=dict(name=[dict(languageId="en", text=party)]) if party else dict(name=None),
                groupResults=[dict(groupName=[dict(languageId="en", text=g["groupName"])],
                                   voteCount=g["voteCount"]) for g in groups]))
        state.append(dict(id=identity, name=title, contestType="Candidate", voteFor=1, ballotOptions=options))
        public.append(dict(name=[dict(languageId="en", text=title)],
                           summaryResults=dict(ballotOptions=independent)))
    for name, lid in names:
        contests = copy.deepcopy(state)
        for contest in contests:
            contest["precinctsParticipating"] = 0
            for candidate in contest["ballotOptions"]:
                groups = [dict(groupName=m, voteCount=1, isFromVirtualPrecinct=False)
                          for m in sorted(ri_review.MODES)]
                candidate.update(voteCount=3, groupResults=groups,
                    precinctResults=[dict(id="unit", name="LIMITED ONLY" if name == "Town" else "Federal #1",
                        isVirtual=False, reportingStatus="Election Night Complete",
                        voteCount=3, groupResults=groups)])
        localities.append(dict(id=lid, name=name, ballotItems=contests))
    election = dict(electionDate="2026-11-03", name=[dict(languageId="en", text="Statewide General Election")],
                    ballotsCast=0, totalVoters=10)
    parent = dict(election=election, ballotItems=public,
        jurisdiction=dict(name=[dict(languageId="en", text="Rhode Island")],
            childLocalities=[dict(id=lid.upper(), name=[dict(languageId="en", text=name)]) for name, lid in names]),
        localityElections=[dict(jurisdictionId=lid, asOf="source-time", ballotsCast=0, totalVoters=5)
                           for name, lid in names])
    return dict(electionDate="2026-11-03", electionName="Statewide General Election",
                results=dict(name="Rhode Island", ballotItems=state), localResults=localities), parent


def test_rhode_island_retains_nonresidential_units_zero_counts_and_separate_locality_statistics():
    results, statistics, audit = ri_review.review(*rhode_island_fixture())
    assert len(results) == 4 and len({r["key"] for r in results}) == 4
    assert audit["unique_native_units"] == 2 and len(audit["native_vs_declared_precinct_counts"]) == 4
    assert {r["reporting_unit_kind"] for r in results} == {"federal_reporting_unit", "limited_only_office"}
    assert all(r["other_votes"] == 3 and not r["source_is_virtual"] for r in results)
    assert len(statistics) == 2 and all(r["reported_pct"] is None and r["ballots"] == 0 for r in statistics)


@pytest.mark.parametrize("change", ["mode", "candidate", "public", "unit", "duplicate", "locality", "date"])
def test_rhode_island_rejects_missing_or_conflicting_native_scope_and_independent_totals(change):
    media, parent = rhode_island_fixture()
    candidate = media["localResults"][0]["ballotItems"][0]["ballotOptions"][0]
    if change == "mode":
        candidate["precinctResults"][0]["groupResults"][0]["voteCount"] = 2
    elif change == "candidate":
        candidate["politicalParty"] = "Other"
    elif change == "public":
        parent["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["voteCount"] = 9
    elif change == "unit":
        candidate["precinctResults"] = []
    elif change == "duplicate":
        candidate["precinctResults"].append(candidate["precinctResults"][0])
    elif change == "locality":
        media["localResults"].pop()
    else:
        media["electionDate"] = "2024-11-05"
    with pytest.raises(ValueError):
        ri_review.review(media, parent)


@pytest.mark.parametrize("value", [None, True, -1, 1.5, float("inf")])
def test_rhode_island_never_imputes_missing_invalid_or_boolean_counts(value):
    with pytest.raises(ValueError):
        ri_review.count(value)


def rhode_island_map_fixture():
    rows = ri_review.review(*rhode_island_fixture())[0]
    features = []
    for i, row in enumerate([r for r in rows if r["locality"] == "Town"], 1):
        row["precinct"] = f"SCHOOL (TOWN 010{i})"
        row["reporting_unit_kind"] = "native_reporting_unit_geography_unverified"
        x = -71 + i * .02
        features.append(dict(attributes=dict(OBJECTID=i, TOWN="Town", DISTRICT=f"010{i}",
            DISTRICTN=100 + i, Congress=i), geometry=dict(rings=[
                [[x, 41], [x, 41.01], [x + .01, 41.01], [x + .01, 41], [x, 41]]])))
    limited = dict(rows[0], key="limited", precinct="TOWN HALL - LIMITED (TOWN 0103)",
                   democratic_votes=0, republican_votes=1, other_votes=0, contest_votes=1)
    rows.append(limited)
    return rows, dict(geometryType="esriGeometryPolygon",
                     spatialReference=dict(wkid=4326), features=features)


def test_rhode_island_maps_complete_town_sets_without_allocating_federal_or_nonzero_limited_votes():
    rows, boundary = rhode_island_map_fixture()
    rows[0].update(democratic_votes=0, republican_votes=0, other_votes=0, contest_votes=0)
    mapped, audit = ri_maps.mapped_precincts(rows, boundary)
    assert len(mapped) == 2 and audit["towns"]["Town"]["exact"]
    assert audit["rates_available"] == 0 and len(audit["excluded_reporting_units"]) == 3
    assert next(f["properties"] for f in mapped if f["properties"]["key"] == rows[0]["key"])["margin_pp"] is None
    assert all("participation" not in f["properties"] and
               "2022-2032" in f["properties"]["boundary_date"] for f in mapped)
    assert "limited" in audit["withheld_units"]


@pytest.mark.parametrize("change", ["set", "congress", "unassigned", "overlap", "label", "virtual"])
def test_rhode_island_withholds_entire_town_for_reference_scope_or_geometry_conflicts(change):
    rows, boundary = rhode_island_map_fixture()
    if change == "set":
        boundary["features"].pop()
    elif change == "congress":
        boundary["features"][1]["attributes"]["Congress"] = 1
    elif change == "unassigned":
        boundary["features"][1]["attributes"].update(DISTRICT="28XX", Congress=0)
    elif change == "overlap":
        boundary["features"][1]["geometry"] = boundary["features"][0]["geometry"]
    elif change == "label":
        rows[0]["precinct"] = "SCHOOL (OTHER TOWN 0101)"
    else:
        rows[0]["source_is_virtual"] = True
    mapped, audit = ri_maps.mapped_precincts(rows, boundary)
    assert not mapped and not audit["towns"]["Town"]["exact"]


@pytest.mark.parametrize("change", ["result", "reference"])
def test_rhode_island_rejects_duplicate_mapping_identities(change):
    rows, boundary = rhode_island_map_fixture()
    if change == "result":
        rows.append(rows[0])
    else:
        boundary["features"].append(boundary["features"][0])
    with pytest.raises(ValueError):
        ri_maps.mapped_precincts(rows, boundary)


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le"])
def test_hawaii_historical_sources_preserve_utf16_and_missing_trailing_header_fields(encoding):
    text = 'Format#1\r\nCandidate_name,Votes\r\n"Quoted\r\ncandidate",12,\r\nOther,0,\r\n'
    audit = hi_historical.text_inventory(text.encode(encoding))
    assert audit["encoding"] == encoding and audit["source_format_metadata"] == "Format#1"
    assert audit["native_data_records"] == 2 and audit["native_record_widths"] == {3: 2}
    assert audit["data_trailing_empty_field_absent_from_header"]


def test_hawaii_historical_sources_do_not_relabel_absentee_early_and_election_columns():
    audit = hi_historical.text_inventory(
        b"Candidate_name,Absentee_votes,Early_votes,Election_Votes\r\nCandidate,10,2,3\r\n")
    assert audit["encoding"] == "utf-8-sig"
    assert audit["native_header"][1:] == ["Absentee_votes", "Early_votes", "Election_Votes"]
    assert not audit["data_trailing_empty_field_absent_from_header"]


def test_hawaii_historical_sources_reject_ragged_rows_instead_of_truncating_data():
    with pytest.raises(ValueError, match="fields"):
        hi_historical.text_inventory(b"Candidate,Votes\nPerson,12,\nAnother,3,unexpected\n")


def hawaii_fixture():
    rows, summary = [], []
    for contest, label, overseas, names in [
            ("30", "20-01", "OS I", ["(D) CASE, Ed", "(R) LAM, Adriel C.",
                                    "(G) CONLEY, Jordan S.", "(N) BERNING, Nathan M."]),
            ("5", "01-01", "OS II", ["(D) TOKUDA, Jill N.", "(R) AWA, Brenton"])]:
        for i, name in enumerate(names, 1):
            record = dict.fromkeys(hi_review.SUMMARY_HEADER, "")
            record.update({"#Contest ID": contest, "Contest Title": hi_review.CONTESTS[contest],
                "Contest Type": "OF", "Registered Voters": "200", "Total Precincts": "3",
                "Counted Precincts": "2", "Candidate ID": str(i), "Candidate Name": name,
                "Mail Votes": "3", "In-Person Votes": "2", "Total Votes": "5", "_source_lines": [2, 2]})
            for mode in hi_review.MODES:
                for kind in ("Blank", "Over", "Invalid"):
                    record[f"{mode} {kind} Votes"] = "1" if (mode, kind) == ("Mail", "Blank") else "0"
            summary.append(record)
            for suffix, split, unit_label, votes, ballots, registration, reporting in [
                    ("1", "", label, "3", str(len(names) * 3 + 1), "100", "1"),
                    ("2", "VSC", label, "2", str(len(names) * 2), "0", "0"),
                    ("3", "", overseas, "0", "0", "0", "1")]:
                row = dict.fromkeys(hi_review.MEDIA_HEADER, "")
                row.update({hi_review.LABEL: unit_label, "Split_Name": split,
                    "precinct_splitId": contest + suffix, "Reg_voters": registration, "Ballots": ballots,
                    "Reporting": reporting, "Contest_id": contest,
                    "Contest_title": hi_review.CONTESTS[contest], "Choice_id": str(i),
                    "Candidate_name": name, "Candidate_Type": "C",
                    "Mail votes": "0" if split else votes, "In-Person votes": votes if split else "0",
                    "_source_lines": [len(rows) + 4, len(rows) + 4]})
                rows.append(row)
    return rows, summary


def test_hawaii_reconciles_modes_without_merging_vsc_or_double_counting_registration():
    results, statistics, audit = hi_review.review(*hawaii_fixture())
    assert len(results) == len(statistics) == 6 and len({r["key"] for r in results}) == 6
    assert sum(r["registered"] for r in statistics) == 200
    assert all(r["reported_pct"] is None for r in statistics)
    vsc = [r for r in results if r["source_split_label"] == "VSC"]
    assert len(vsc) == 2 and all(r["source_reporting"] == 0 and r["contest_votes"] > 0 for r in vsc)
    assert sum(r["other_votes"] for r in results) == 10
    assert audit["reporting_unit_kinds"]["overseas_reporting_unit"] == 2
    assert all(v["native_minus_summary"] == 0 for v in audit["ballot_accounting_by_mode"].values())


def test_hawaii_retains_ballot_discrepancies_without_repairing_counts_or_creating_rates():
    rows, summary = hawaii_fixture()
    for row in rows:
        if row["precinct_splitId"] == "301":
            row["Ballots"] = "14"
    results, statistics, audit = hi_review.review(rows, summary)
    assert next(r for r in statistics if r["source_unit_id"] == "301")["ballots"] == 14
    assert audit["ballot_accounting_by_mode"]["Mail"]["native_minus_summary"] == 1
    assert all(r["reported_pct"] is None for r in statistics)
    assert sum(r["contest_votes"] for r in results) == 30


@pytest.mark.parametrize("change", ["candidate_id", "candidate_name", "party", "missing_count",
                                   "mode_swap", "duplicate_candidate", "missing_unit", "unit_facts",
                                   "unknown_split", "summary_scope", "summary_registration"])
def test_hawaii_rejects_ambiguous_source_identity_missing_counts_and_incomplete_scope(change):
    rows, summary = hawaii_fixture()
    if change == "candidate_id":
        rows[0]["Choice_id"] = "999"
    elif change == "candidate_name":
        rows[0]["Candidate_name"] = "(D) Different person"
    elif change == "party":
        rows[0]["Choice_party"] = "R"
    elif change == "missing_count":
        rows[0]["Mail votes"] = ""
    elif change == "mode_swap":
        rows[0]["In-Person votes"] = "1"
    elif change == "duplicate_candidate":
        rows.append(dict(rows[0]))
    elif change == "missing_unit":
        rows[:] = [r for r in rows if r["precinct_splitId"] != "302"]
    elif change == "unit_facts":
        rows[0]["Ballots"] = "999"
    elif change == "unknown_split":
        for row in rows:
            if row["precinct_splitId"] == "302":
                row["Split_Name"] = "UNKNOWN"
    elif change == "summary_scope":
        for row in summary:
            if row["#Contest ID"] == "30":
                row["Counted Precincts"] = "3"
    else:
        for row in summary:
            if row["#Contest ID"] == "30":
                row["Registered Voters"] = "100"
    with pytest.raises(ValueError):
        hi_review.review(rows, summary)


def test_hawaii_multiline_native_csv_preserves_actual_source_line_ranges():
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter="\t")
    writer.writerow([f"Column{i}" for i in range(1, 17)])
    writer.writerow(["#FormatVersion 1"] + [""] * 15)
    writer.writerow(hi_review.MEDIA_HEADER)
    first = [""] * 16
    first[10] = "(D) A quoted name\nand running mate"
    writer.writerow(first)
    writer.writerow([""] * 16)
    records = hi_review.read_table(buffer.getvalue().encode(), media=True)
    assert records[0]["Candidate_name"] == first[10]
    assert records[0]["_source_lines"] == [4, 5] and records[1]["_source_lines"] == [6, 6]
    with pytest.raises(ValueError, match="header"):
        hi_review.read_table(buffer.getvalue().replace("precinct_splitId", "unknown").encode(), media=True)


def test_hawaii_rejects_missing_candidate_and_wrong_summary_mode_totals():
    rows, summary = hawaii_fixture()
    with pytest.raises(ValueError, match="candidate"):
        hi_review.review(rows[1:], summary)
    summary[0]["Total Votes"] = "6"
    with pytest.raises(ValueError, match="ballot modes"):
        hi_review.review(rows, summary)


def test_hawaii_pdf_comparison_keeps_native_zero_denominators_and_pdf_only_overseas_modes():
    results, statistics, _ = hi_review.review(*hawaii_fixture())
    observations = []
    for row, stats in zip(results, statistics):
        mode = "In-Person" if row["source_split_label"] else "Mail"
        registration = 100 if row["source_split_label"] else stats["registered"]
        observations.append(dict(label=mode + " " + row["source_precinct_label"], pages=[1],
            participation={"PRECINCT REGISTRATION": registration, mode + " TURNOUT": stats["ballots"]},
            candidate_votes={row["source_office"] + "|" + name: votes
                             for name, votes in json.loads(row["candidate_votes"]).items()}))
    for name in ("OS I", "OS II"):
        observations.append(dict(label="In-Person " + name, pages=[99], candidate_votes={},
            participation={"PRECINCT REGISTRATION": 0, "In-Person TURNOUT": 0}))
    pdfs = {"precinct.pdf": dict(printed_on="test", records=observations)}
    for name in ("cch.pdf", "coh.pdf", "cok.pdf", "com.pdf", "histatewide.pdf"):
        pdfs[name] = dict(printed_on="test", records=[dict(candidate_votes={}, participation={})])
    audit = hi_review.compare_pdf_observations(results, statistics, pdfs)
    assert audit["native_units_compared"] == 6 and audit["pdf_units"] == 8
    assert audit["difference_fields"] == {"registered": 2}
    assert len(audit["pdf_only_units"]) == 2
    assert all(r["registered"] == 0 for r in statistics if r["source_split_label"])
    assert all(r["reported_pct"] is None for r in statistics)


def test_hawaii_rejects_wrong_election_pdf_even_with_a_correct_looking_precinct_label():
    with hi_review.fitz.open() as document:
        page = document.new_page()
        page.insert_text((20, 20), "GENERAL ELECTION 2024 - State of Hawaii - Statewide\n"
                         "November 5, 2024\nREPORT 3\nMail 01-01")
        original = document.tobytes()
    with pytest.raises(ValueError, match="election"):
        hi_review.pdf_observations({"cch.pdf": original})


def alaska_boundary_fixture(overlap=False):
    features, geographic_features, geojson_features, precincts = [], [], [], []
    for oid, west in [(1, -150), (2, -149.95 if overlap else -149.8)]:
        ring = [[west, 61], [west, 61.1], [west + .1, 61.1], [west + .1, 61], [west, 61]]
        number, name = f"01-{oid}00", f"Precinct {oid}"
        attributes = dict(OBJECTID=oid, Precinct_Number=f"{number} {name}",
            HouseDistrict="01", CreationDate=1655494956944, Sample_Ballot_URL=None)
        projected = [[math.radians(lon) * 6378137,
                      math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * 6378137]
                     for lon, lat in ring]
        features.append(dict(attributes=dict(attributes), geometry=dict(rings=[projected])))
        geographic_features.append(dict(attributes=dict(attributes), geometry=dict(rings=[ring])))
        geojson_features.append(dict(type="Feature", properties=dict(attributes),
            geometry=dict(type="Polygon", coordinates=[[list(p) for p in ring]])))
        precincts.append(dict(number=number, name=name))
    return (dict(spatialReference=dict(wkid=102100), geometryType="esriGeometryPolygon",
                 features=features),
            dict(spatialReference=dict(wkid=4326), geometryType="esriGeometryPolygon",
                 features=geographic_features),
            dict(type="FeatureCollection", features=geojson_features),
            dict(name="Alaska 2026 General Election", precincts=precincts))


def test_alaska_locator_matching_ids_and_current_use_do_not_establish_election_vintage():
    audit = ak_boundaries.audit_references(*alaska_boundary_fixture())
    assert audit["reference_features"] == audit["valid_polygon_units"] == 2
    assert audit["overlap_scope_complete"] and not audit["overlap_pairs"]
    assert audit["join"] == "withheld" and audit["complete"] is False
    assert "not independently established" in audit["boundary_vintage"]
    assert audit["reference_creation_dates"] == {"1655494956944": 2}


def test_alaska_locator_audits_labels_without_silently_substituting_aliases():
    fixture = alaska_boundary_fixture()
    fixture[3]["precincts"][0]["name"] = "Different official label"
    audit = ak_boundaries.audit_references(*fixture)
    assert audit["name_differences"] == [dict(precinct="01-100",
        reference_name="Precinct 1", election_name="Different official label")]
    assert audit["join"] == "withheld"


def test_alaska_locator_checks_overlaps_against_every_reference_including_conflicting_labels():
    fixture = alaska_boundary_fixture(overlap=True)
    fixture[3]["precincts"][1]["name"] = "Different label"
    audit = ak_boundaries.audit_references(*fixture)
    assert audit["overlap_scope_complete"] and len(audit["overlap_pairs"]) == 1
    assert math.isclose(audit["overlap_pairs"][0]["area_degrees_squared"], .005)
    assert audit["join"] == "withheld"


def test_alaska_locator_preserves_geojson_defects_without_replacing_native_ring_roles():
    fixture = alaska_boundary_fixture()
    ring = fixture[2]["features"][0]["geometry"]["coordinates"][0]
    ring[1], ring[2] = ring[2], ring[1]
    audit = ak_boundaries.audit_references(*fixture)
    assert audit["valid_polygon_units"] == 2
    assert audit["native_vs_service_geojson_differences"] == [
        dict(precinct="01-100", geojson_invalid=True)]


def test_alaska_locator_does_not_call_a_subset_overlap_audit_statewide():
    native, geographic, geojson, results = alaska_boundary_fixture()
    for data in [native, geographic]:
        ring = data["features"][0]["geometry"]["rings"][0]
        ring[1], ring[2] = ring[2], ring[1]
    audit = ak_boundaries.audit_references(native, geographic, geojson, results)
    assert audit["valid_polygon_units"] == 1
    assert len(audit["invalid_reference_units"]) == 1
    assert audit["overlap_scope_complete"] is False
    assert audit["join"] == "withheld"


@pytest.mark.parametrize("problem", [
    "wrong_election", "wrong_projection", "truncated", "duplicate_object",
    "missing_unit", "different_attributes", "unknown_id", "wrong_district",
    "projection_disagreement", "ring_structure", "nonfinite_coordinate",
])
def test_alaska_locator_rejects_mixed_incomplete_or_inconsistent_exports(problem):
    native, geographic, geojson, results = alaska_boundary_fixture()
    if problem == "wrong_election":
        results["name"] = "Alaska 2024 General Election"
    elif problem == "wrong_projection":
        geographic["spatialReference"]["wkid"] = 3857
    elif problem == "truncated":
        native["exceededTransferLimit"] = True
    elif problem == "duplicate_object":
        native["features"][1] = native["features"][0]
    elif problem == "missing_unit":
        geographic["features"].pop()
    elif problem == "different_attributes":
        geojson["features"][0]["properties"]["HouseDistrict"] = "02"
    elif problem in {"unknown_id", "wrong_district"}:
        for data, field in [(native, "attributes"), (geographic, "attributes"), (geojson, "properties")]:
            data["features"][0][field]["Precinct_Number" if problem == "unknown_id" else "HouseDistrict"] = (
                "01-999 Unknown" if problem == "unknown_id" else "02")
    elif problem == "projection_disagreement":
        native["features"][0]["geometry"]["rings"][0][0][0] += 100
    elif problem == "ring_structure":
        native["features"][0]["geometry"]["rings"][0].pop()
    elif problem == "nonfinite_coordinate":
        geographic["features"][0]["geometry"]["rings"][0][0][0] = float("nan")
    with pytest.raises(ValueError):
        ak_boundaries.audit_references(native, geographic, geojson, results)


def alaska_fixture():
    names = ["R Candidate (REP)", "D Candidate (DEM)", "Other Candidate (NON)"]
    raw, geographic = [], []
    totals = [0, 0, 0]
    for sequence, identifier, label in [
        ("1", "01-100", "01-100 First"), ("2", "01-200", "01-200 Second"),
        ("3", "99-999", "HD99 Fed Overseas Absentee"),
        ("4", "1-1", "District 1 - Absentee"), ("5", "", "District 1 - Early Voting"),
        ("6", "", "District 1  - Question"),
    ]:
        votes = [20, 10, 5]
        registration = 100 if int(sequence) <= 3 else 0
        for index, (name, party) in enumerate([("R Candidate", "REP"), ("D Candidate", "DEM"),
                                             ("Other Candidate", "NON")]):
            totals[index] += votes[index]
            row = dict(Pct_seq_nbr=sequence, Pct_Id=identifier, Precinct_name=label,
                Contest_title=ak_review.OFFICE, Contest_Id="8", candidate_id=str(index),
                candidate_name=name, Party_Code=party, Selectable_Options="1",
                Reg_voters=str(registration), total_ballots="40", total_votes=str(votes[index]),
                total_under_votes="4", total_over_votes="1")
            row.update({mode + "_votes": str(votes[index] if mode == "Election Day" else 0)
                        for mode in ak_review.MODES})
            raw.append(row)
        if int(sequence) <= 2:
            geographic.append(dict(number=identifier, name=label.split(" ", 1)[1],
                contests=[dict(n=0, b=40, v=100, t=35, c=[
                    dict(n=i, t=votes[i]) for i in [2, 0, 1]])]))
    data = dict(name="Alaska 2026 General Election", certified=False, updated="11/04/2026 2:11 PM",
        format="2024", contestNames=[ak_review.OFFICE], candidateNames=names,
        totals=[dict(n=0, b=240, v=300, t=210, p=3, r=2,
                     c=[dict(n=i, t=v) for i, v in enumerate(totals)])],
        precincts=geographic, districts=[dict(number="1")])
    state = json.loads(json.dumps(data))
    state.pop("precincts")
    return raw, state, data, [dict(number=r["number"], coords=[]) for r in geographic]


def test_alaska_preserves_pooled_and_federal_units_without_allocating_or_inferring_rates():
    rows, statistics, audit = ak_review.review(*alaska_fixture())
    assert len(rows) == len(statistics) == 6 and len({r["key"] for r in rows}) == 6
    assert sum(r["democratic_votes"] for r in rows) == 60
    assert sum(r["other_votes"] for r in rows) == 30
    assert audit["geographic_precincts"] == 2 and audit["pooled_reporting_units"] == 3
    assert sum(r["ballots"] for r in statistics) == 240
    assert all(r["reported_pct"] is None for r in statistics)
    assert rows[-1]["source_precinct_id"] == rows[-2]["source_precinct_id"] == ""
    assert rows[-1]["key"] != rows[-2]["key"]
    assert rows[2]["reporting_unit_kind"] == "federal_overseas"
    assert "pooled_district_ballots_not_allocated_to_residential_precincts" in statistics[0]["quality_flags"]


def test_alaska_retains_ballot_balance_discrepancies_without_repairing_counts():
    raw, state, data, shapes = alaska_fixture()
    for row in raw[:3]:
        row["total_under_votes"] = "3"
    rows, statistics, audit = ak_review.review(raw, state, data, shapes)
    assert rows[0]["contest_votes"] == 35 and statistics[0]["ballots"] == 40
    assert statistics[0]["source_under_votes"] == 3 and statistics[0]["reported_pct"] is None
    assert audit["quality_flag_counts"]["candidate_votes_plus_source_under_over_disagree_with_ballots"] == 1


@pytest.mark.parametrize("problem", [
    "wrong_election", "wrong_format", "mixed_snapshot", "unknown_party", "duplicate_candidate",
    "missing_count", "repeated_ballots", "candidate_mode_sum", "native_geographic_count",
    "literal_precinct_name", "unknown_pooled_label", "duplicate_pooled", "missing_pooled",
    "missing_shape", "duplicate_shape", "statewide_count", "statewide_ballots",
])
def test_alaska_rejects_mixed_incomplete_or_ambiguous_originals(problem):
    raw, state, data, shapes = alaska_fixture()
    if problem == "wrong_election":
        data["name"] = state["name"] = "Alaska 2024 General Election"
    elif problem == "wrong_format":
        data["format"] = state["format"] = "2022"
    elif problem == "mixed_snapshot":
        data["updated"] = "different snapshot"
    elif problem == "unknown_party":
        raw[0]["Party_Code"] = "Unverified Party"
    elif problem == "duplicate_candidate":
        raw[1]["candidate_id"] = raw[0]["candidate_id"]
    elif problem == "missing_count":
        raw[0]["total_votes"] = ""
    elif problem == "repeated_ballots":
        raw[0]["total_ballots"] = "41"
    elif problem == "candidate_mode_sum":
        raw[0]["Absentee_votes"] = "1"
    elif problem == "native_geographic_count":
        data["precincts"][0]["contests"][0]["v"] += 1
    elif problem == "literal_precinct_name":
        for row in raw[:3]:
            row["Precinct_name"] = "01-100 Similar But Unverified"
    elif problem == "unknown_pooled_label":
        for row in raw[-3:]:
            row["Precinct_name"] = "Unknown nonresidential unit"
    elif problem == "duplicate_pooled":
        for row in raw[-3:]:
            row["Precinct_name"] = "District 1 - Absentee"
    elif problem == "missing_pooled":
        raw = raw[:-3]
    elif problem == "missing_shape":
        shapes.pop()
    elif problem == "duplicate_shape":
        shapes.append(shapes[0])
    elif problem == "statewide_count":
        for source in (data, state):
            source["totals"][0]["c"][0]["t"] += 1
            source["totals"][0]["t"] += 1
    else:
        data["totals"][0]["b"] = state["totals"][0]["b"] = 241
    with pytest.raises(ValueError):
        ak_review.review(raw, state, data, shapes)


def south_dakota_fixture():
    candidates = ["R  Candidate ", "D Candidate"]

    def sheet(items, label, county=None):
        body = [(None, name, r, d) for name, d, r in items]
        rows = [("2026 Unofficial General Election Results", None, None, None),
            ("State of South Dakota", None, None, None),
            ("Precincts 3 of 3 Reporting (Precincts Partially Reported: 0/3)", None, None, None),
            (county, None, None, None), (None,) * 4, (None,) * 4,
            (sd_review.OFFICE, "Precinct" if county else "County", *candidates), *body,
            (None, "TOTALS", sum(v[2] for v in body), sum(v[3] for v in body))]
        return sd_review.house_sheet(rows, label, 3)

    sheets = {"01": sheet([("Precinct 1 ", 20, 40), ("Precinct 2", 10, 30)], "first.xlsx", "First County"),
              "02": sheet([("Center Hall", 5, 15)], "center.xlsx", "Center County")}
    statewide = sheet([("First", 30, 70), ("Center (Vote Center)", 5, 15)], "statewide.xlsx")
    facts = dict(year=2026, election="General Election November 3, 2026", counties=[])
    api = []
    for code, county, records, registrations, center in [
        ("01", "First", [("Precinct 1", 65, 100), ("Precinct 2", 45, 100)], 200, False),
        ("02", "Center", [("Center Hall", 22, 300)], 300, True),
    ]:
        facts["counties"].append(dict(code=code, county=county, vote_center=center,
            records=[dict(label=name, raw_label=name, source_row=i, ballots=b, registered=r)
                     for i, (name, b, r) in enumerate(records, 1)]))
        api.append(dict(CountyID=code, CountyName=county + (" (Vote Center)" if center else ""),
            IsReported=True, PartialPrecincts=0,
            PrecinctsReporting=len(records), TotalPrecincts=len(records), Voters=registrations,
            calcVoterTurnout=sum(r[1] for r in records)))
    catalog = [dict(desc=sd_review.OFFICE, name="D Candidate", Party="Democratic"),
               dict(desc=sd_review.OFFICE, name="R Candidate", Party="Republican")]
    return sheets, statewide, facts, api, catalog


def test_south_dakota_reconciles_candidates_by_name_and_never_uses_vote_center_denominators():
    inputs = south_dakota_fixture()
    # Statewide candidate order may differ from every county workbook.
    inputs[1]["totals"] = dict(reversed(list(inputs[1]["totals"].items())))
    rows, statistics, audit = sd_review.review(*inputs)
    assert len(rows) == len(statistics) == 3
    assert sum(r["democratic_votes"] for r in rows) == 35
    assert sum(r["republican_votes"] for r in rows) == 85
    assert statistics[0]["reported_pct"] == 65 and statistics[1]["reported_pct"] == 45
    assert statistics[2]["registered"] == 300 and statistics[2]["reported_pct"] is None
    assert statistics[2]["denominator_scope"] == "county_repeated_at_vote_centers"
    assert audit["02"]["vote_center"]
    assert rows[0]["raw_precinct"] == "Precinct 1 "


def test_south_dakota_preserves_duplicate_name_rows_without_cross_source_pairing():
    sheets, statewide, facts, api, catalog = south_dakota_fixture()
    sheets["01"]["records"][1]["label"] = "Precinct 1"
    facts["counties"][0]["records"][1]["label"] = "Precinct 1"
    rows, statistics, audit = sd_review.review(sheets, statewide, facts, api, catalog)
    assert len(rows) == len({r["key"] for r in rows}) == 3
    assert len(statistics) == len({r["key"] for r in statistics}) == 3
    assert all(r["reported_pct"] is None for r in statistics)
    assert all("ambiguous_reporting_unit_name_no_cross_source_row_pairing" in r["quality_flags"]
               for r in statistics[:2])
    assert {r["key"] for r in rows[:2]}.isdisjoint(r["key"] for r in statistics[:2])
    assert audit["01"]["duplicate_reporting_labels"] == ["Precinct 1"]


@pytest.mark.parametrize("problem", ["statewide_total", "candidate", "county_scope", "ballot_total",
                                     "missing_count", "vote_center_scope", "unknown_party",
                                     "missing_vote_center_marker"])
def test_south_dakota_rejects_unreconciled_or_ambiguous_source_data(problem):
    sheets, statewide, facts, api, catalog = south_dakota_fixture()
    if problem == "statewide_total":
        statewide["records"][0]["votes"]["D Candidate"] += 1
    elif problem == "candidate":
        sheets["01"]["records"][0]["votes"]["Unknown Candidate"] = 1
    elif problem == "county_scope":
        api[0]["CountyID"] = "03"
    elif problem == "ballot_total":
        api[0]["calcVoterTurnout"] += 1
    elif problem == "missing_count":
        facts["counties"][0]["records"][0]["ballots"] = None
    elif problem == "vote_center_scope":
        facts["counties"][1]["records"][0]["registered"] = 22
    elif problem == "missing_vote_center_marker":
        api[1]["CountyName"] = "Center"
    else:
        catalog[0]["Party"] = "Unverified Party"
    with pytest.raises(ValueError):
        sd_review.review(sheets, statewide, facts, api, catalog)


def test_south_dakota_keeps_ballot_and_registration_disagreements_without_repairing_rates():
    sheets, statewide, facts, api, catalog = south_dakota_fixture()
    facts["counties"][0]["records"][0]["ballots"] = 40
    api[0]["calcVoterTurnout"] = 85
    api[0]["Voters"] = 201
    rows, statistics, audit = sd_review.review(sheets, statewide, facts, api, catalog)
    assert rows[0]["contest_votes"] == 60 and statistics[0]["ballots"] == 40
    assert statistics[0]["reported_pct"] is None
    assert "house_votes_exceed_separately_reported_ballots" in statistics[0]["quality_flags"]
    assert "county_registration_disagrees_with_api" in statistics[1]["quality_flags"]
    assert audit["01"]["registration_disagrees"]


def test_south_dakota_extracts_every_displayed_fact_without_copying_page_frontend():
    raw = b'''<input name="ctl00$hidElectionType" value="General">
      <input name="ctl00$hidElectionDate" value="11/3/2026">
      <div><div class="turnout-results-box-a"><h1>First</h1><input countyid="01"></div></div>
      <div id="countyturnout01"><div class="odd"><div class="county-precinct">Precinct 1</div>
      <div class="county-cast"><span>1,234</span></div>
      <div class="county-counted"><span>2,000</span></div></div></div><script>unrelated_code()</script>'''
    facts = sd_review.turnout_facts(raw)
    row = facts["counties"][0]["records"][0]
    assert row["ballots"] == 1234 and row["registered"] == 2000
    assert "unrelated_code" not in str(facts)
    with pytest.raises(ValueError):
        sd_review.turnout_facts(raw.replace(b"11/3/2026", b"6/2/2026"))
    with pytest.raises(ValueError):
        sd_review.turnout_facts(raw.replace(b"1,234", b""))


def idaho_fixture():
    from collections import Counter

    text = lambda value: [dict(languageId="en", text=value)]
    metadata = dict(election=dict(id=id_review.ELECTION, jurisdictionId=id_review.JURISDICTION,
        electionDate="2026-11-03", isPrimary=False, isProduction=True,
        name=text("General Election - November 3, 2026")),
        voterRegistration=[dict(localityName=text("First County"), total=200),
                           dict(localityName=text("Second County"), total=100)], ballotItems=[])
    precincts, ballots, summary = [], [], Counter()
    for district, county, identifiers in [(1, "First County", ["001", "002"]), (2, "Second County", ["003"])]:
        candidates = [dict(nativeId=f"{party}{district}", name=text(f"{party} candidate {district}"),
            party=dict(abbreviation=party), voteCount=votes * len(identifiers))
            for party, votes in [("DEM", 20), ("REP", 7), ("IND", 1)]]
        metadata["ballotItems"].append(dict(name=text(f"United States Representative District {district}"),
            voteFor=text("Vote for 1"), voteTotal=28 * len(identifiers),
            summaryResults=dict(ballotOptions=candidates)))
        for precinct in identifiers:
            options = [(c["name"][0]["text"], c["nativeId"], id_review.PARTIES[c["party"]["abbreviation"]],
                        c["voteCount"] // len(identifiers)) for c in candidates]
            options += [("Ballots Cast", "", None, 30), ("Over Votes", "", None, 1), ("Under Votes", "", None, 1)]
            for name, choice, party, votes in options:
                row = (county, f"United States Representative District {district}", f"usrep{district}",
                       name, choice, party, votes, 1)
                precincts.append((precinct,) + row)
                summary[row[:6] + (row[7],)] += votes
            ballots.append((county, precinct, 95, 5, 100, 30, "30 %"))
    summary = [key[:6] + (votes, key[6]) for key, votes in summary.items()]
    return summary, precincts, ballots, metadata


def test_idaho_reconciles_candidates_statistics_and_separate_participation():
    rows, statistics, audit = id_review.idaho_results(*idaho_fixture())
    assert len(rows) == len(statistics) == 3
    assert rows[0]["precinct"] == "001" and rows[0]["contest_votes"] == 28
    assert rows[0]["other_votes"] == 1 and rows[0]["reported_ballots"] == 30
    assert rows[0]["margin_pp"] == pytest.approx(1300 / 28)
    assert all(r["reported_pct"] == 30 and r["quality_flags"] == [] for r in statistics)
    assert audit["original_precinct_rows"] == 18 and not audit["county_registration_disagreements"]


def test_idaho_accepts_only_explicit_terminal_party_label_variants():
    summary, precincts, ballots, metadata = idaho_fixture()
    summary = [r[:5] + (r[5] + " Party" if r[5] else r[5],) + r[6:] for r in summary]
    precincts = [r[:6] + (r[6] + " Party" if r[6] else r[6],) + r[7:] for r in precincts]
    rows, statistics, _ = id_review.idaho_results(summary, precincts, ballots, metadata)
    assert sum(r["contest_votes"] for r in rows) == 84
    assert all(r["reported_pct"] == 30 for r in statistics)


@pytest.mark.parametrize("problem", ["duplicate", "missing", "county_total", "district_total",
                                     "candidate_name", "party", "wrong_election", "negative", "noninteger"])
def test_idaho_rejects_bad_candidate_scope_and_counts(problem):
    summary, precincts, ballots, metadata = idaho_fixture()
    if problem == "duplicate":
        precincts.append(precincts[0])
    elif problem == "missing":
        precincts.pop(0)
    elif problem == "county_total":
        row = list(summary[0]); row[6] += 1; summary[0] = tuple(row)
    elif problem == "district_total":
        metadata["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["voteCount"] += 1
        metadata["ballotItems"][0]["voteTotal"] += 1
    elif problem == "candidate_name":
        metadata["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["name"][0]["text"] = "Different"
    elif problem == "party":
        metadata["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["party"]["abbreviation"] = "REP"
    elif problem == "wrong_election":
        metadata["election"]["electionDate"] = "2024-11-05"
    else:
        row = list(precincts[0]); row[7] = -1 if problem == "negative" else 20.5; precincts[0] = tuple(row)
    with pytest.raises(ValueError):
        id_review.idaho_results(summary, precincts, ballots, metadata)


def test_idaho_withholds_entire_pooled_county_without_allocating_ballots():
    summary, precincts, ballots, metadata = idaho_fixture()
    precincts = [("Absentee",) + r[1:] if r[0] == "002" else r for r in precincts]
    ballots = [(r[0], "Absentee") + r[2:] if r[1] == "002" else r for r in ballots]
    rows, statistics, audit = id_review.idaho_results(summary, precincts, ballots, metadata)
    assert audit["pooled_counties"] == ["First County"]
    assert sum(r["ballots"] for r in statistics) == 90
    assert [r["reported_pct"] for r in statistics] == [None, None, 30]
    assert rows[1]["reporting_unit_kind"] == "pooled_absentee_or_early_unit"


def test_idaho_county_registration_disagreement_withholds_only_affected_county():
    summary, precincts, ballots, metadata = idaho_fixture()
    metadata["voterRegistration"][0]["total"] = 201
    _, statistics, audit = id_review.idaho_results(summary, precincts, ballots, metadata)
    assert [r["reported_pct"] for r in statistics] == [None, None, 30]
    assert audit["county_registration_disagreements"] == [dict(county="First County", workbook=200, api=201)]


@pytest.mark.parametrize("problem", ["small", "components", "over_registration", "ballot_mismatch",
                                     "duplicate_ballot", "missing_ballot", "missing_statistic"])
def test_idaho_missing_and_inconsistent_ballot_denominators(problem):
    summary, precincts, ballots, metadata = idaho_fixture()
    row = list(ballots[0])
    if problem == "small":
        row[2:5] = [20, 0, 20]
    elif problem == "components":
        row[2] = 94
    elif problem == "over_registration":
        row[2:5] = [24, 5, 29]
    elif problem == "ballot_mismatch":
        row[5] = 29
    elif problem == "duplicate_ballot":
        ballots.append(ballots[0])
    elif problem == "missing_ballot":
        ballots.pop()
    elif problem == "missing_statistic":
        precincts = [r for r in precincts if r[4] != "Under Votes"]
        summary = [r for r in summary if r[3] != "Under Votes"]
    ballots[0] = tuple(row)
    if problem in {"small", "components", "over_registration", "ballot_mismatch"}:
        _, statistics, _ = id_review.idaho_results(summary, precincts, ballots, metadata)
        assert statistics[0]["reported_pct"] is None
        assert statistics[0]["ballots"] == (29 if problem == "ballot_mismatch" else 30)
        assert statistics[0]["house_contest_ballots"] == 30
        assert statistics[-1]["reported_pct"] == 30
    else:
        with pytest.raises(ValueError):
            id_review.idaho_results(summary, precincts, ballots, metadata)


def idaho_map_fixture():
    rows, statistics, _ = id_review.idaho_results(*idaho_fixture())
    features = []
    for i, row in enumerate(rows):
        x, y = -116 + 2 * i, 43
        features.append(dict(attributes=dict(OBJECTID=i + 1, COUNTY=row["county"][:-7],
            PCNCT_NME="000" + row["precinct"], STATE_PR_ID=f"reference-{i}",
            CNTY_PR_ID=f"unrelated-{i}", CONGR_DIST=row["congressional_district"],
            ACTIVE="Y", DATE_ACT=1704067200000, DATE_INACT=32503680000000),
            geometry=dict(rings=[[[x, y], [x, y + 1], [x + 1, y + 1], [x + 1, y], [x, y]]])))
    return rows, statistics, dict(geometryType="esriGeometryPolygon",
        spatialReference=dict(wkid=4326), features=features)


def test_idaho_map_preserves_counts_and_source_defined_participation_without_decoding_ids():
    rows, statistics, boundary = idaho_map_fixture()
    mapped, audit = id_maps.mapped_precincts(rows, statistics, boundary)
    assert len(mapped) == 3 and all(c["exact"] for c in audit["counties"].values())
    for feature, row in zip(mapped, rows):
        p = feature["properties"]
        assert all(p[field] == value for field, value in row.items())
        assert p["participation"]["measure"] == "reported_ballots_and_registration"
        assert p["participation"]["reported_pct"] == 30
        assert p["participation"]["ballots"] == 30
        assert p["participation"]["registered"] == 100
        assert p["reference_county_precinct_id"].startswith("unrelated-")


@pytest.mark.parametrize("problem", ["name", "district", "invalid_ring", "future"])
def test_idaho_map_withholds_whole_county_for_scope_district_geometry_or_date_conflicts(problem):
    rows, statistics, boundary = idaho_map_fixture()
    feature = boundary["features"][0]
    if problem == "name":
        feature["attributes"]["PCNCT_NME"] = "Different precinct"
    elif problem == "district":
        feature["attributes"]["CONGR_DIST"] = "2"
    elif problem == "future":
        feature["attributes"]["DATE_ACT"] = id_maps.ELECTION_MS + 1
    else:
        feature["geometry"]["rings"][0].pop()
    mapped, audit = id_maps.mapped_precincts(rows, statistics, boundary)
    assert len(mapped) == 1 and mapped[0]["properties"]["county"] == "Second County"
    assert not audit["counties"]["First"]["exact"]
    assert audit["counties"]["Second"]["exact"]


def test_idaho_map_uses_election_activity_interval_not_only_current_active_flag():
    rows, statistics, boundary = idaho_map_fixture()
    boundary["features"][0]["attributes"]["ACTIVE"] = "N"
    mapped, _ = id_maps.mapped_precincts(rows, statistics, boundary)
    assert len(mapped) == 3


def test_idaho_map_audits_overlaps_against_unmatched_reference_features_too():
    rows, statistics, boundary = idaho_map_fixture()
    boundary["features"][0]["attributes"]["PCNCT_NME"] = "Unmatched"
    boundary["features"][0]["geometry"] = boundary["features"][2]["geometry"]
    mapped, audit = id_maps.mapped_precincts(rows, statistics, boundary)
    assert not mapped and len(audit["all_reference_overlap_pairs"]) == 1
    assert all(not c["exact"] for c in audit["counties"].values())


def test_idaho_map_retains_pooled_units_in_downloads_without_allocating_them():
    rows, statistics, boundary = idaho_map_fixture()
    pooled = dict(rows[0], key="ID|First County|Absentee", precinct="Absentee",
                  reporting_unit_kind="pooled_absentee_or_early_unit")
    rows.append(pooled)
    statistics.append(dict(statistics[0], key=pooled["key"], precinct="Absentee",
        reported_pct=None, quality_flags=["pooled_nongeographic_reporting_unit"]))
    mapped, audit = id_maps.mapped_precincts(rows, statistics, boundary)
    assert len(mapped) == 3 and audit["reporting_units"] == 4
    assert audit["excluded_pooled_reporting_units"] == audit["withheld_units"] == [pooled["key"]]


@pytest.mark.parametrize("problem", ["duplicate_feature", "ambiguous_name", "truncated",
                                     "projection", "missing_statistics"])
def test_idaho_map_rejects_duplicate_or_incomplete_sources(problem):
    rows, statistics, boundary = idaho_map_fixture()
    if problem == "duplicate_feature":
        boundary["features"].append(boundary["features"][0])
    elif problem == "ambiguous_name":
        boundary["features"][1]["attributes"]["PCNCT_NME"] = "0001"
    elif problem == "truncated":
        boundary["exceededTransferLimit"] = True
    elif problem == "projection":
        boundary["spatialReference"]["wkid"] = 102605
    else:
        statistics.pop()
    with pytest.raises(ValueError):
        id_maps.mapped_precincts(rows, statistics, boundary)


def vt_fixture():
    towns = [dict(townId=1, townName="FIRST"), dict(townId=2, townName="SECOND")]
    districts, nodes, compact = [], [], []
    for tid, district in [(1, "A"), (2, "A"), (2, "B")]:
        town = towns[tid - 1]["townName"]
        districts.append(dict(townId=tid, townName=town, repDistrict=district,
                              senateDistrict="S", countyId=1, countyName="EXAMPLE"))
        rc = [dict(cid=cid, cn=name, pn=party, vc=votes) for cid, name, party, votes in
              [(1, "A", "DEMOCRATIC", 7), (2, "B", "REPUBLICAN", 3), (3, "C", "INDEPENDENT", 2)]]
        nodes.append(dict(tid=tid, tn=town, repd=district, send="S", vf=1, sc=15, sv=1, bv=1,
                          rc=rc, wc=[dict(cid=0, cn="OTHER WRITE-IN", pn=None, vc=1)]))
        compact.append(dict(tn=town, repd=district, send="S", vc1=7, vc2=3, vc3=2, ovc=3))
    parent = json.loads(json.dumps(nodes[0]))
    parent.update(tid=0, tn="STATE WIDE", sc=45, sv=3, bv=3)
    for candidate in parent["rc"] + parent["wc"]:
        candidate["vc"] *= 3
    source = dict(d=[dict(pid=0, o=[dict(oid=4, on="REPRESENTATIVE TO CONGRESS",
        vf=1, cid1=1, cid2=2, cid3=3, cs=nodes + [parent], cd=compact)])])
    metadata = dict(electionDetails=dict(electionId=7100, electionGuid=vt_review.GUID,
        electionName="2026 GENERAL ELECTION", electionDate="2026-11-03T00:00:00",
        isGeneralElection=True, isOfficial=False), towns=towns, townDistricts=districts)
    turnout = dict(d=[dict(tid=tid, tn=town["townName"], tvr=100 * tid, tvc=15 * tid,
        tabs=0, tdis=tid, tdisr=tid, hl=[]) for tid, town in enumerate(towns, 1)])
    return source, metadata, turnout


def test_vt_splits_reconcile_without_relabeling_municipal_turnout_as_precinct_data():
    rows, statistics = vt_review.vt_results(*vt_fixture())
    assert len(rows) == 3 and len({r["key"] for r in rows}) == 3
    assert rows[0]["contest_votes"] == 13 and rows[0]["reported_contest_total"] == 15
    assert rows[0]["other_votes"] == 3 and rows[0]["margin_pp"] == pytest.approx(400 / 13)
    assert all(r["reporting_unit_kind"] == "town_legislative_split" for r in rows)
    assert len(statistics) == 2 and statistics[1]["ballots"] == 30
    assert statistics[1]["registered_turnout_pct"] == 15
    assert statistics[1]["reporting_unit_kind"] == "municipality"
    assert sum(r["ballots"] for r in statistics) == 45


def test_vt_municipal_discrepancies_withhold_rates_without_modifying_counts():
    source, metadata, turnout = vt_fixture()
    turnout["d"][1]["tvc"] = 29
    rows, statistics = vt_review.vt_results(source, metadata, turnout)
    assert sum(r["reported_contest_total"] for r in rows) == 45
    assert statistics[1]["ballots"] == 29 and statistics[1]["registered_turnout_pct"] is None
    assert statistics[0]["registered_turnout_pct"] == 15
    assert "house_contest_total_differs_from_municipal_votes_cast" in statistics[1]["quality_flags"]


def test_vt_sparse_named_writeins_keep_source_identity_and_party():
    source, metadata, turnout = vt_fixture()
    office = source["d"][0]["o"][0]
    named = dict(cid=40, cn="A", pn=None, vc=2)
    office["cs"][0]["wc"].append(named)
    office["cs"][-1]["wc"].append(named)
    office["cs"][0]["sc"] += 2
    office["cs"][-1]["sc"] += 2
    office["cd"][0]["ovc"] += 2
    turnout["d"][0]["tvc"] += 2
    rows, _ = vt_review.vt_results(source, metadata, turnout)
    assert rows[0]["democratic_votes"] == 7 and rows[0]["other_votes"] == 5
    assert sum(r["other_votes"] for r in rows) == 11


@pytest.mark.parametrize("change", ["duplicate", "missing_count", "wrong_election", "wrong_split", "wrong_rollup"])
def test_vt_rejects_ambiguous_units_missing_counts_and_inconsistent_rollups(change):
    source, metadata, turnout = vt_fixture()
    office = source["d"][0]["o"][0]
    if change == "duplicate":
        office["cs"].insert(0, office["cs"][0])
    elif change == "missing_count":
        office["cs"][0]["rc"][0]["vc"] = None
    elif change == "wrong_election":
        metadata["electionDetails"]["electionDate"] = "2024-11-05T00:00:00"
    elif change == "wrong_split":
        office["cs"][0]["send"] = "OTHER"
    else:
        office["cs"][-1]["rc"][0]["vc"] += 1
        office["cs"][-1]["sc"] += 1
    with pytest.raises(ValueError):
        vt_review.vt_results(source, metadata, turnout)


@pytest.mark.parametrize("districts,reported", [(1, 0), (2, 2)])
def test_vt_incomplete_or_different_municipal_district_scope_withholds_the_rate(districts, reported):
    source, metadata, turnout = vt_fixture()
    turnout["d"][0].update(tdis=districts, tdisr=reported)
    _, statistics = vt_review.vt_results(source, metadata, turnout)
    assert statistics[0]["registered_turnout_pct"] is None
    assert "incomplete_or_different_district_scope" in statistics[0]["quality_flags"]


def vt_boundary_fixture():
    features = []
    for oid, town, district, west, tid in [
            (1, "FIRST", "A", -73, 1), (2, "SECOND", "A", -72.7, 2),
            (3, "SECOND", "B", -72.5, 2)]:
        features.append(dict(attributes=dict(OBJECTID=oid, TOWN=town, HOUSE_NAME=district,
            SEN_NAME="S", TOWN_GEOID=f"50001{tid:05}", CNTY="1"),
            geometry=dict(rings=[[[west, 43], [west, 43.1], [west + .1, 43.1],
                                  [west + .1, 43], [west, 43]]])))
    return dict(geometryType="esriGeometryPolygon", spatialReference=dict(wkid=4326), features=features)


def test_vt_maps_dissolve_wards_once_without_allocating_municipal_participation():
    rows, _ = vt_review.vt_results(*vt_fixture())
    boundary = vt_boundary_fixture()
    extra = json.loads(json.dumps(boundary["features"][0]))
    extra["attributes"]["OBJECTID"] = 4
    for point in extra["geometry"]["rings"][0]:
        point[0] += .1
    boundary["features"].append(extra)
    mapped, audit = vt_maps.mapped_splits(rows, boundary)
    assert len(mapped) == 3 and sum(f["properties"]["contest_votes"] for f in mapped) == 39
    first = mapped[0]
    assert first["properties"]["source_object_ids"] == [1, 4]
    assert nd_maps.shape(first["geometry"]).area == pytest.approx(.02)
    assert first["properties"]["reporting_unit_kind"] == "town_legislative_split"
    assert "participation" not in first["properties"] and not audit["withheld_units"]


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_vt_maps_require_the_entire_town_split_set(change):
    rows, _ = vt_review.vt_results(*vt_fixture())
    boundary = vt_boundary_fixture()
    if change == "missing":
        boundary["features"].pop()
    else:
        extra = json.loads(json.dumps(boundary["features"][-1]))
        extra["attributes"].update(OBJECTID=4, HOUSE_NAME="C")
        for point in extra["geometry"]["rings"][0]:
            point[0] += .2
        boundary["features"].append(extra)
    mapped, audit = vt_maps.mapped_splits(rows, boundary)
    assert len(mapped) == 1 and mapped[0]["properties"]["town"] == "FIRST"
    assert not audit["towns"]["SECOND"]["exact"] and len(audit["withheld_units"]) == 2


def test_vt_maps_normalize_district_separators_but_never_infer_town_aliases():
    rows, _ = vt_review.vt_results(*vt_fixture())
    boundary = vt_boundary_fixture()
    rows[0].update(house_district="CHITTENDEN-1", senate_district="CHITTENDEN-CENTRAL_")
    boundary["features"][0]["attributes"].update(
        HOUSE_NAME="Chittenden 1", SEN_NAME="Chittenden Central")
    mapped, _ = vt_maps.mapped_splits(rows, boundary)
    assert len(mapped) == 3
    rows[0]["town"] = "FIRST CITY"
    mapped, audit = vt_maps.mapped_splits(rows, boundary)
    assert len(mapped) == 2 and not audit["towns"]["FIRST CITY"]["exact"]


@pytest.mark.parametrize("unreported", [False, True])
def test_vt_maps_withhold_whole_towns_for_overlapping_reference_units(unreported):
    rows, _ = vt_review.vt_results(*vt_fixture())
    boundary = vt_boundary_fixture()
    if unreported:
        extra = json.loads(json.dumps(boundary["features"][0]))
        extra["attributes"].update(OBJECTID=4, TOWN="UNREPORTED", TOWN_GEOID="5000100003")
        boundary["features"].append(extra)
    else:
        boundary["features"][1]["geometry"] = boundary["features"][0]["geometry"]
    mapped, audit = vt_maps.mapped_splits(rows, boundary)
    assert len(mapped) == (2 if unreported else 0)
    assert audit["overlap_pairs"] and not audit["towns"]["FIRST"]["exact"]
    if not unreported:
        assert not audit["towns"]["SECOND"]["exact"]


def test_vt_maps_reject_overlapping_ward_parts_in_the_same_reporting_split():
    rows, _ = vt_review.vt_results(*vt_fixture())
    boundary = vt_boundary_fixture()
    extra = json.loads(json.dumps(boundary["features"][0]))
    extra["attributes"]["OBJECTID"] = 4
    boundary["features"].append(extra)
    mapped, audit = vt_maps.mapped_splits(rows, boundary)
    assert len(mapped) == 2 and audit["internal_overlaps"]
    assert not audit["towns"]["FIRST"]["exact"]


@pytest.mark.parametrize("change", ["duplicate", "wrong_geoid", "wrong_county", "projection", "truncated"])
def test_vt_maps_reject_incomplete_or_inconsistent_geographic_identity(change):
    rows, _ = vt_review.vt_results(*vt_fixture())
    boundary = vt_boundary_fixture()
    if change == "duplicate":
        boundary["features"].append(boundary["features"][0])
    elif change == "wrong_geoid":
        boundary["features"][0]["attributes"]["TOWN_GEOID"] = "5100100001"
    elif change == "wrong_county":
        boundary["features"][0]["attributes"]["CNTY"] = "3"
    elif change == "projection":
        boundary["spatialReference"]["wkid"] = 3857
    else:
        boundary["exceededTransferLimit"] = True
    with pytest.raises(ValueError):
        vt_maps.mapped_splits(rows, boundary)


def test_vt_maps_reject_reporting_identity_collisions_after_normalization():
    rows, _ = vt_review.vt_results(*vt_fixture())
    rows.append(dict(rows[0], house_district="A_"))
    with pytest.raises(ValueError, match="collide"):
        vt_maps.mapped_splits(rows, vt_boundary_fixture())


def nd_boundary_fixture():
    def part(object_id, west):
        return dict(attributes=dict(OBJECTID=object_id, CountyID=38001, CountyName="Adams",
                                    Precinct="013901", PPartID="0139010" + str(object_id)),
                    geometry=dict(rings=[[[west, 46], [west, 47], [west + 1, 47],
                                          [west + 1, 46], [west, 46]]]))
    return dict(geometryType="esriGeometryPolygon", spatialReference=dict(wkid=4326),
                features=[part(1, -103), part(2, -102)])


def test_nd_maps_dissolve_splits_without_duplicating_votes_or_inventing_turnout():
    rows, stats = nd_review.nd_results(*nd_fixture())
    mapped, audit = nd_maps.mapped_precincts(rows, stats, nd_boundary_fixture())
    assert len(mapped) == 1 and mapped[0]["properties"]["contest_votes"] == 100
    assert nd_maps.shape(mapped[0]["geometry"]).area == pytest.approx(2)
    assert mapped[0]["properties"]["source_object_ids"] == [1, 2]
    assert mapped[0]["properties"]["participation"]["denominator"] is None
    assert audit["counties"]["38001"]["exact"]


def test_nd_maps_withhold_whole_counties_for_wrong_parent_or_reporting_sets():
    rows, stats = nd_review.nd_results(*nd_fixture())
    for field, value in [("CountyID", 30859), ("Precinct", "01390")]:
        boundary = nd_boundary_fixture()
        boundary["features"][0]["attributes"][field] = value
        mapped, audit = nd_maps.mapped_precincts(rows, stats, boundary)
        assert mapped == [] and not audit["counties"]["38001"]["exact"]
    boundary = nd_boundary_fixture()
    boundary["features"].append(boundary["features"][0])
    with pytest.raises(ValueError, match="Duplicate"):
        nd_maps.mapped_precincts(rows, stats, boundary)
    boundary["exceededTransferLimit"] = True
    with pytest.raises(ValueError, match="Incomplete"):
        nd_maps.mapped_precincts(rows, stats, boundary)


def test_nd_native_ring_roles_keep_holes_and_reject_substantive_repairs():
    outer = [[-103, 46], [-103, 48], [-101, 48], [-101, 46], [-103, 46]]
    hole = [[-102.5, 46.5], [-101.5, 46.5], [-101.5, 47.5], [-102.5, 47.5], [-102.5, 46.5]]
    polygon, repair = nd_maps.esri_polygon([outer, hole])
    assert polygon.area == pytest.approx(3) and repair is None
    with pytest.raises(ValueError, match="changes polygon area"):
        nd_maps.esri_polygon([[[-103, 46], [-101, 48], [-103, 48], [-101, 46], [-103, 46]]])


def test_nd_maps_withhold_counties_with_overlapping_reporting_units():
    rows, stats = nd_review.nd_results(*nd_fixture())
    rows.append(dict(rows[0], key="ND|38001|3902", precinct="3902"))
    stats.append(dict(stats[0], key="ND|38001|3902", precinct="3902", precinct_name="013902"))
    boundary = nd_boundary_fixture()
    boundary["features"][1]["attributes"]["Precinct"] = "013902"
    boundary["features"][1]["geometry"] = boundary["features"][0]["geometry"]
    mapped, audit = nd_maps.mapped_precincts(rows, stats, boundary)
    assert mapped == [] and not audit["counties"]["38001"]["exact"]
    assert len(audit["source_cross_precinct_overlaps"]) == 1


def test_nd_maps_mask_ambiguous_strips_without_reallocating_votes():
    rows, stats = nd_review.nd_results(*nd_fixture())
    rows.append(dict(rows[0], key="ND|38001|3902", precinct="3902"))
    stats.append(dict(stats[0], key="ND|38001|3902", precinct="3902", precinct_name="013902"))
    boundary = nd_boundary_fixture()
    boundary["features"][1]["attributes"]["Precinct"] = "013902"
    boundary["features"][1]["geometry"]["rings"] = [
        [[-102.5, 46], [-102.5, 47], [-101.5, 47], [-101.5, 46], [-102.5, 46]]]
    mapped, audit = nd_maps.mapped_precincts(rows, stats, boundary)
    assert len(mapped) == 2 and len(audit["masked_reporting_units"]) == 2
    polygons = [nd_maps.shape(f["geometry"]) for f in mapped]
    assert sum(p.area for p in polygons) == pytest.approx(1)
    assert polygons[0].intersection(polygons[1]).area == 0
    assert [f["properties"]["contest_votes"] for f in mapped] == [100, 100]
    assert all("Counts still describe the entire reporting unit" in f["properties"]["boundary_provenance"]
               for f in mapped)


def nd_fixture():
    choices = [dict(Name=name, PartyID=party, TotalVotes=votes,
                    Votes=[dict(VoteTypeID="1", Votes=votes)])
               for name, party, votes in [("A", "DEM", 70), ("B", "REP", 30), ("write-in", "NON", 0)]]
    precinct = dict(LocationID="3901", LocationName="013901", TotalVotes=100, Choices=choices)
    county = dict(LocationID="38001", LocationName="Adams", TotalVotes=100,
                  Choices=choices, Locations={"3901": precinct})
    house = dict(ContestID="22055", ContestName="Representative in Congress",
                 TotalVotes=100, Choices=choices, TotalPrecincts=1, PrecinctsReporting=1,
                 Locations={"38001": county})
    ballot = dict(LocationID="3901", TotalBallotsCast=110,
                  BallotsCast=[dict(VoteTypeID="1", BallotsCast=110)])
    county_ballot = dict(ballot, LocationID="38001", Locations={"3901": ballot})
    turnout = dict(ballot, TotalPrecincts=1, PrecinctsReporting=1, Locations={"38001": county_ballot})
    source = dict(ElectionData=dict(ElectionID="348", IsOfficial=False),
                  TurnoutData=turnout, ContestData=[house])
    identity = dict(electionID="348", isOfficial=False, turnout=dict(totalBallotsCast=110),
                    response=dict(id="348", name="2026 General Election", date="2026-11-03T00:00:00",
                                  parties={"DEM": {}, "REP": {}, "NON": {}}))
    return json.loads(json.dumps(source)), identity


def test_nd_counts_reconcile_without_relabeling_candidate_votes_or_borrowing_denominators():
    source, identity = nd_fixture()
    rows, participation = nd_review.nd_results(source, identity)
    assert rows[0]["contest_votes"] == 100 and rows[0]["margin_pp"] == 40
    assert participation[0]["ballots"] == 110
    assert participation[0]["denominator"] is None and participation[0]["reported_pct"] is None
    precinct = source["ContestData"][0]["Locations"]["38001"]["Locations"]["3901"]
    precinct["Choices"][0]["TotalVotes"] = precinct["Choices"][0]["Votes"][0]["Votes"] = 71
    precinct["TotalVotes"] = 101
    with pytest.raises(ValueError, match="counts do not reconcile"):
        nd_review.nd_results(source, identity)


def test_nd_explicit_zero_buckets_are_not_missing_counts_and_inconsistent_modes_are_rejected():
    source, _ = nd_fixture()
    house = source["ContestData"][0]
    zero = house["Choices"][-1]
    del zero["TotalVotes"]
    assert nd_review.candidate_totals(house)[("write-in", "NON")] == 0
    del zero["Votes"][0]["Votes"]
    with pytest.raises(ValueError, match="do not substitute zero"):
        nd_review.candidate_totals(house)
    source, identity = nd_fixture()
    source["ContestData"][0]["Choices"][0]["Votes"].append(dict(VoteTypeID="2", Votes=70))
    with pytest.raises(ValueError, match="one explicit All"):
        nd_review.nd_results(source, identity)
    source, identity = nd_fixture()
    identity["response"]["date"] = "2024-11-05T00:00:00"
    with pytest.raises(ValueError, match="election identity"):
        nd_review.nd_results(source, identity)


def test_source_review_accepts_manifest_provenance_without_claiming_mapped_participation(tmp_path, monkeypatch):
    states = tmp_path / "public/voter-participation/data"
    states.mkdir(parents=True)
    (states / "states.geojson").write_text(
        (precinct_coverage.ROOT / "public/voter-participation/data/states.geojson").read_text())
    review = dict(year=2026, state_code="ND", candidate_results="acquired_reconciled",
                  boundaries="reference_crosswalk_pending", join="withheld",
                  validation="counts_passed_map_withheld", publication="full_counts_download_only",
                  participation="acquired_precinct_ballot_counts", next_action="Review polygon splits",
                  source_url="full-results.json", boundary_source="manifest.json",
                  notes="Counts only", complete_download_url="full.zip")
    (tmp_path / "review.json").write_text(json.dumps(review))
    (tmp_path / "public/precinct-results.json").write_text(json.dumps({"source_reviews": ["review.json"]}))
    monkeypatch.setattr(precinct_coverage, "ROOT", tmp_path)
    row = next(r for r in precinct_coverage.build_rows() if r["year"] == 2026 and r["state_code"] == "ND")
    assert row["publication"] == "full_counts_download_only" and row["join"] == "withheld"
    assert row["participation"] == "acquired_precinct_ballot_counts"
    assert row["boundary_source"] == "manifest.json" and row["complete"] == "no"
    review.update(state_code="VT", boundary_source="", sources={"election.json": "election.json"})
    (tmp_path / "review.json").write_text(json.dumps(review))
    row = next(r for r in precinct_coverage.build_rows() if r["year"] == 2026 and r["state_code"] == "VT")
    assert row["boundary_source"] == "" and row["join"] == "withheld"
    review.update(state_code="ID")
    review.pop("sources")
    (tmp_path / "review.json").write_text(json.dumps(review))
    row = next(r for r in precinct_coverage.build_rows() if r["year"] == 2026 and r["state_code"] == "ID")
    assert row["boundary_source"] == "" and row["publication"] == "full_counts_download_only"


def test_city_count_review_keeps_the_existing_mapped_subset_and_separate_participation(tmp_path, monkeypatch):
    states = tmp_path / "public/voter-participation/data"
    states.mkdir(parents=True)
    (states / "states.geojson").write_bytes(
        (precinct_coverage.ROOT / "public/voter-participation/data/states.geojson").read_bytes())
    review = dict(year=2026, state_code="MA", municipality="Worcester",
                  candidate_results="acquired_reconciled_city_subset", boundaries="reference_pending",
                  join="withheld", validation="counts_passed_map_withheld",
                  publication="full_counts_download_only", participation="not_inferred_from_contest_counts",
                  source_url="worcester-source", next_action="Review exact reference",
                  notes="Worcester governor counts only; no map or turnout", complete_download_url="worcester.zip")
    (tmp_path / "review.json").write_text(json.dumps(review))
    (tmp_path / "public/precinct-results.json").write_text(json.dumps({"source_reviews": ["review.json"]}))
    monkeypatch.setattr(precinct_coverage, "ROOT", tmp_path)
    coverage = dict(partial=True, live_verified=True, source_url="boston-source",
                    boundary_source="boston-reference", next_action="Acquire more cities",
                    notes="Boston central-only mapped subset",
                    participation="central_only_counts_no_registration_or_rates")
    rows = precinct_coverage.build_rows({"coverage": {"2026": {"MA": coverage}}})
    row = next(row for row in rows if row["year"] == 2026 and row["state_code"] == "MA")
    assert len(rows) == 1632 and all(row["complete"] == "no" for row in rows)
    assert row["publication"] == "published_partial" and row["join"] == "validated_partial"
    assert row["participation"] == coverage["participation"] and row["results_source"] == "boston-source"
    assert row["boundary_source"] == "boston-reference"
    assert all(text in row["notes"] for text in [coverage["notes"], review["notes"], "worcester.zip"])


def test_historical_source_acquisition_requires_exact_reviewed_bytes_without_inventing_turnout():
    raw = b"county,precinct,office,candidate,votes\nExample,1,House,A,10\nExample,2,House,B,*\n"
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    audit = historical_sources.inspect_csv(raw, blob)
    assert audit["rows"] == 2 and audit["malformed_rows"] == 0
    assert "turnout" not in audit
    modes = b"county,precinct,office,candidate,election_day_votes,advanced_votes\nExample,1,House,A,10,5\n"
    mode_blob = hashlib.sha1(b"blob " + str(len(modes)).encode() + b"\0" + modes).hexdigest()
    assert historical_sources.inspect_csv(modes, mode_blob)["rows"] == 1
    with pytest.raises(ValueError, match="changed"):
        historical_sources.inspect_csv(raw + b"\n", blob)


def test_participation_reviews_change_only_the_scoped_counts_and_notes():
    review = dict(complete_download_url="complete.zip", coverage=[
        dict(state_code="ME", years=[2026, 2002], status="reviewed_city_only_voter_counts",
             notes="City voters, not statewide or demographic turnout."),
        dict(state_code="PA", years=[2026], status="reviewed_county_mail_returns_only",
             notes="Mail returns, not final turnout.")])
    before = precinct_coverage.build_rows(participation_reviews=[])
    after = precinct_coverage.build_rows(participation_reviews=[review])
    assert len(before) == len(after) == 1632
    expected = {(2026, "ME"), (2002, "ME"), (2026, "PA")}
    changed = set()
    for old, new in zip(before, after):
        if old != new:
            changed.add((new["year"], new["state_code"]))
            assert {k: v for k, v in old.items() if k not in {"participation", "notes"}} == {
                k: v for k, v in new.items() if k not in {"participation", "notes"}}
            assert "complete.zip" in new["notes"] and new["complete"] == "no"
    assert changed == expected


def test_city_participation_review_does_not_downgrade_existing_validated_counts():
    coverage = dict(partial=True, source_url="reviewed-map", next_action="Review remaining units",
                    notes="Approved subset.", participation="published_counts_and_reference_map")
    review = dict(complete_download_url="complete.zip", coverage=[
        dict(state_code="ME", years=[2026], status="reviewed_city_only_voter_counts",
             notes="Additional limited city-only counts.")])
    row = next(r for r in precinct_coverage.build_rows(
        {"coverage": {"2026": {"ME": coverage}}}, published=True, participation_reviews=[review])
        if r["year"] == 2026 and r["state_code"] == "ME")
    assert row["participation"] == "published_counts_and_reference_map"
    assert row["publication"] == "published_partial" and row["complete"] == "no"
    assert "Additional limited city-only counts." in row["notes"]


def test_original_source_downloads_do_not_claim_validated_maps_or_participation():
    batch = dict(year=2022, complete_download_url="full.zip", states={
        "AZ": dict(source_url="immutable.csv", rows=100, next_action="Reconcile and obtain boundaries")})
    row = next(r for r in precinct_coverage.build_rows(source_batches=[batch])
               if r["year"] == 2022 and r["state_code"] == "AZ")
    assert row["candidate_results"] == "acquired_originals_review_pending"
    assert row["join"] == "pending" and row["complete"] == "no"
    assert row["publication"] == "full_originals_download_only"
    assert row["participation"] == "not_acquired"
    batch["states"]["AZ"]["participation"] = "not_reconciled"
    batch["states"]["NC"] = batch["states"]["AZ"]
    rows = precinct_coverage.build_rows(source_batches=[batch])
    assert next(r for r in rows if r["year"] == 2022 and r["state_code"] == "AZ")[
        "participation"] == "not_reconciled"
    assert next(r for r in rows if r["year"] == 2022 and r["state_code"] == "NC")[
        "participation"] == "published_counts_and_reference_map"


def test_multiyear_original_downloads_preserve_years_and_do_not_override_validated_map_scope():
    batch = dict(complete_download_url="full.zip", elections={str(year): dict(
        year=year, state_code="HI", original_files=9, original_bytes=1000,
        source_url="official", next_action="Reconcile and obtain boundaries",
        participation="not_reconciled",
        validation="complete_source_bytes_and_native_record_structure_verified")
        for year in (2024, 2022, 2020, 2018)})
    coverage = dict(partial=True, source_url="reviewed-map", next_action="Verify remaining precincts",
                    notes="Reviewed partial map")
    rows = precinct_coverage.build_rows({"coverage": {"2024": {"HI": coverage}}},
                                       published=True, source_batches=[batch])
    hi = {r["year"]: r for r in rows if r["state_code"] == "HI"}
    for year in (2022, 2020, 2018):
        assert hi[year]["candidate_results"] == "acquired_originals_review_pending"
        assert hi[year]["publication"] == "full_originals_download_only"
        assert hi[year]["validation"] == "complete_source_bytes_and_native_record_structure_verified"
        assert hi[year]["participation"] == "not_reconciled" and hi[year]["complete"] == "no"
        assert "9 files, 1,000 uncompressed bytes" in hi[year]["notes"]
    assert hi[2024]["publication"] == "published_partial" and hi[2024]["results_source"] == "reviewed-map"
    assert hi[2024]["participation"] == "not_reconciled"
    assert hi[2024]["complete"] == "no"
    assert hi[2016]["publication"] == "not_published"


def test_county_original_acquisitions_retain_scope_without_downgrading_existing_maps():
    batch = dict(complete_download_url="full.zip", elections={str(year): dict(
        year=year, state_code="NV", county_name="Clark", county_fips="32003",
        original_files=202, original_bytes=1000,
        source_url="official", next_action="Reconcile Clark and continue other counties",
        notes="Clark County only, not statewide Nevada.", participation="not_reconciled")
        for year in (2024, 2022)})
    coverage = dict(partial=True, source_url="existing-map", next_action="Continue other counties",
                    notes="Previously validated map scope")
    rows = precinct_coverage.build_rows({"coverage": {"2024": {"NV": coverage}}},
                                       published=True, source_batches=[batch])
    nevada = {r["year"]: r for r in rows if r["state_code"] == "NV"}
    assert "Clark County only, not statewide Nevada." in nevada[2022]["notes"]
    assert nevada[2022]["complete"] == "no" and nevada[2022]["join"] == "pending"
    assert nevada[2022]["participation"] == "not_reconciled"
    assert nevada[2024]["notes"] == "Previously validated map scope"
    assert nevada[2024]["publication"] == "published_partial"
    assert nevada[2024]["results_source"] == "existing-map"
    assert nevada[2024]["participation"] == "not_acquired"


def test_historical_acquisition_never_produces_a_metadata_only_archive(tmp_path, monkeypatch):
    (tmp_path / "public").mkdir()
    (tmp_path / "public/precinct-source-inventory.json").write_text(json.dumps({
        "states": {"AZ": {"elections": {"1964": []}}}}))
    monkeypatch.setattr(historical_sources, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["acquire", "--year", "1964", "--output", str(tmp_path / "data"),
                                   "--archive", str(tmp_path / "empty.zip")])
    with pytest.raises(ValueError, match="metadata-only"):
        historical_sources.main()
    assert not (tmp_path / "empty.zip").exists()


def mn_fixture():
    precincts, counties, statewide, table = [], [], [], {}
    for district in range(1, 9):
        precinct = str(district).zfill(4)
        table[("01", precinct)] = ["01", precinct, "Precinct " + precinct, str(district)]
        for candidate, party, votes in [("0401", "DFL", 70), ("0302", "R", 30)]:
            row = dict(county="", precinct="", district=str(district), candidate=candidate,
                       name=party, party=party, reported=1, units=1, votes=votes, total=100)
            statewide.append(row)
            counties.append(dict(row, county="01"))
            precincts.append(dict(row, county="01", precinct=precinct))
    return precincts, counties, statewide, {"01": "Example"}, table


def test_mn_precinct_candidates_require_all_three_reporting_levels_to_reconcile():
    args = mn_fixture()
    rows = additional_precincts.mn_results(*args)
    assert len(rows) == 8 and all(r["margin_pp"] == 40 for r in rows)
    assert rows[0]["key"] == "MN|01|0001"
    args[1][0]["votes"] -= 1
    with pytest.raises(ValueError, match="do not reconcile"):
        additional_precincts.mn_results(*args)


def test_mn_candidates_reject_missing_candidates_and_incorrect_geographies():
    args = mn_fixture()
    args[0][0]["party"] = "UNKNOWN"
    with pytest.raises(ValueError, match="candidate/party"):
        additional_precincts.mn_results(*args)
    row = "MN;01;0001;0104;U.S. Representative District 1;1;0401;Example;;;DFL;1;1;70;70;100"
    with pytest.raises(ValueError, match="Duplicate"):
        additional_precincts.mn_candidate_rows(row + "\n" + row, "precinct")
    with pytest.raises(ValueError, match="geography"):
        additional_precincts.mn_candidate_rows(row, "county")
    with pytest.raises(ValueError, match="House contest"):
        additional_precincts.mn_candidate_rows(row.replace("0104", "0105"), "precinct")


def test_mn_participation_is_not_candidate_votes_and_checks_ballot_modes():
    *_, names, table = mn_fixture()
    row = "MN;01;0001;Precinct 0001;1;100;10;50;20;0;0;70"
    parsed = additional_precincts.mn_participation(row, names, table)[0]
    assert parsed["denominator"] == 110 and parsed["ballots"] == 70
    assert parsed["reported_pct"] == pytest.approx(100 * 70 / 110)
    assert additional_precincts.mn_participation(row.replace(";1;100;10;", ";0;100;10;"), names, table)[0]["reported_pct"] is None
    inconsistent = additional_precincts.mn_participation(row[:-2] + "71", names, table)[0]
    assert inconsistent["ballots"] == 71 and inconsistent["reported_pct"] is None
    assert not inconsistent["ballot_modes_reconciled"]
    missing = additional_precincts.mn_participation(row.replace(";100;", ";*;"), names, table)[0]
    assert missing["registered_at_open"] is None and missing["reported_pct"] is None
    with pytest.raises(ValueError, match="duplicate"):
        additional_precincts.mn_participation(row + "\n" + row, names, table)


def test_original_2020_results_keep_actual_year_and_boundary_uncertainty():
    feature = {"properties": {"GEOID": "06001-1", "votes_dem": 30, "votes_rep": 10, "votes_total": 50}}
    row = additional_precincts.nyt_result(feature, {"06": "CA"})
    assert row["year"] == 2020 and row["other_votes"] == 10 and row["margin_pp"] == 40
    assert "no per-shape official flag" in row["boundary_provenance"]
    feature["properties"]["votes_total"] = 39
    with pytest.raises(ValueError, match="candidate totals"):
        additional_precincts.nyt_result(feature, {"06": "CA"})
    feature["properties"].update(votes_total=None, votes_dem=None, votes_rep=None)
    missing = additional_precincts.nyt_result(feature, {"06": "CA"})
    assert missing["contest_votes"] is None and missing["margin_pp"] is None
    assert missing["democratic_votes"] is None and missing["other_votes"] is None


def test_precinct_worklist_covers_every_state_and_year_newest_first():
    rows = precinct_coverage.build_rows()
    assert len(rows) == len({(r["state_code"], r["year"]) for r in rows}) == 1632
    assert list(dict.fromkeys(r["year"] for r in rows)) == list(range(2026, 1963, -2))
    for year in range(1964, 2027, 2):
        assert len({r["state_code"] for r in rows if r["year"] == year}) == 51
    assert all(r["complete"] == "no" for r in rows)
    assert next(r for r in rows if r["state_code"] == "AK" and r["year"] == 2024)["candidate_results"] == "absent_from_reviewed_release"


def test_nm_precinct_results_reconcile_and_never_treat_suppression_as_zero():
    candidates = [dict(RaceID=11186, OfficeSeqNo="190", CountyName="Example", PrecinctName="PCT 001",
                       CandidateID=party, PartyCode=party, calcCandidateVotes=votes)
                  for party, votes in [("DEM", "12"), ("REP", "8")]]
    counties = [dict(row) for row in candidates]
    rows = precinct_results.nm_results(candidates, counties)
    assert rows[0]["margin_pp"] == 20
    assert rows[0]["county_reconciled"]
    candidates[0]["calcCandidateVotes"] = "*"
    rows = precinct_results.nm_results(candidates, counties)
    assert rows[0]["democratic_votes"] is None
    assert rows[0]["contest_votes"] is None and rows[0]["margin_pp"] is None
    assert not rows[0]["county_reconciled"]
    candidates[0]["calcCandidateVotes"] = "11"
    with pytest.raises(ValueError, match="do not reconcile"):
        precinct_results.nm_results(candidates, counties)
    with pytest.raises(ValueError, match="Duplicate"):
        precinct_results.nm_results(candidates + candidates, counties)


def test_precinct_worklist_requires_live_verification_and_never_marks_partial_complete():
    coverage = dict(partial=True, source_url="source", next_action="Verify remaining precincts",
                    notes="Residential ballots only")
    index = {"coverage": {"2026": {"NC": coverage}}}
    for published, expected in [(False, "snapshot_ready"), (True, "published_partial")]:
        rows = precinct_coverage.build_rows(index, published=published)
        nc = next(row for row in rows if row["year"] == 2026 and row["state_code"] == "NC")
        nm = next(row for row in rows if row["year"] == 2026 and row["state_code"] == "NM")
        de = next(row for row in rows if row["year"] == 2026 and row["state_code"] == "DE")
        assert nc["publication"] == expected
        assert nc["join"] == "validated_partial" and nc["complete"] == "no"
        assert nm["publication"] == "not_published"
        assert de["candidate_results"] == "acquired_reconciled" and de["join"] == "withheld"
        assert de["publication"] == "full_counts_download_only" and de["complete"] == "no"
    index["coverage"]["2026"]["MN"] = dict(coverage, live_verified=False)
    rows = precinct_coverage.build_rows(index, published=True)
    mn = next(row for row in rows if row["year"] == 2026 and row["state_code"] == "MN")
    assert mn["publication"] == "snapshot_ready"
    assert mn["participation"] == "acquired_precinct_counts_and_registration"


def test_precinct_join_withholds_whole_mismatched_or_unreconciled_counties():
    def shape(county, precinct):
        return {"properties": {"county": county, "precinct": precinct}}
    features = [shape("Matched", "1"), shape("Mismatch", "1"), shape("Mismatch", "2"),
                shape("Suppressed", "1")]
    rows = [dict(county=county, precinct="1", reporting_unit_kind="precinct",
                 county_reconciled=county != "Suppressed", margin_pp=20)
            for county in ["Matched", "Mismatch", "Suppressed"]]
    audit = precinct_results.join_counties(features, rows)
    assert sum(row["colored_precincts"] for row in audit) == 1
    assert features[0]["properties"]["match_status"] == "matched"
    assert all(f["properties"]["match_status"] != "matched" for f in features[1:])
    assert all("margin_pp" not in f["properties"] for f in features[1:])


def test_de_results_reconcile_every_candidate_and_ballot_mode_before_geometry():
    source = [dict(zip(["Contest Title", "Election Id", "Election District", "Candidate Name",
                       "Party Name", "Machine Votes", "Absentee Votes", "Early Voting Votes", "Total Votes"],
                      ["Representative In Congress", "GE2026", "Election District 01-01",
                       party, party, "5", "2", "3", "10"]))
              for party in ["Democratic Party", "Republican Party"]]
    statewide = [dict(row, **{"Election Date": "2026-11-03"}) for row in source]
    rows = precinct_results.de_results(source, statewide)
    assert len(rows) == 1 and rows[0]["precinct"] == "01-01" and rows[0]["contest_votes"] == 20
    with pytest.raises(ValueError, match="ballot modes"):
        precinct_results.de_results([dict(source[0], **{"Total Votes": "11"}), source[1]], statewide)
    with pytest.raises(ValueError, match="Duplicate"):
        precinct_results.de_results(source + source, statewide)
    with pytest.raises(ValueError, match="precinct/state"):
        precinct_results.de_results(source[:1], statewide)


def test_nc_results_keep_nonresidential_votes_separate_and_check_ballot_modes():
    base = dict(zip(["County", "Precinct", "Contest Name", "Choice", "Choice Party",
                     "Election Date", "Real Precinct", "Election Day", "Early Voting",
                     "Absentee by Mail", "Provisional", "Total Votes"],
                    ["WAKE", "01-01", "US HOUSE OF REPRESENTATIVES DISTRICT 02", "Candidate",
                     "DEM", "11/03/2026", "Y", "10", "0", "0", "0", "10"]))
    administrative = dict(base, Precinct="EARLY SITE", **{"Real Precinct": "N", "Election Day": "0", "Early Voting": "10"})
    rows = precinct_results.nc_results([base, administrative])
    assert [r["reporting_unit_kind"] for r in rows] == ["precinct", "administrative"]
    assert sum(r["contest_votes"] for r in rows) == 20
    assert "excludes separately reported" in rows[0]["ballot_scope"]
    with pytest.raises(ValueError, match="modes do not reconcile"):
        precinct_results.nc_results([dict(base, **{"Total Votes": "11"})])


def house_fixture():
    root = Path(__file__).resolve().parents[1] / "public/participation-results"
    pointer = json.loads((root / "latest.json").read_text())
    return json.loads((root / pointer["snapshot_id"] / "originals/house-2026.json").read_text())


def test_house_state_results_cover_all_districts_and_reconcile_every_party():
    source = house_fixture()
    states = {key.split("-")[0].upper() for key in source["region_results"]} | {"DC"}
    rows = context.house_results(source, states, "source")
    districts = [row for row in rows if row["level"] == "district"]
    statewide = [row for row in rows if row["level"] == "state"]
    assert len(districts) == 435
    assert {row["state_code"] for row in statewide} == states - {"DC"}
    expected = context.provider_votes(source["candidates"])
    for index, field in enumerate(["democratic_votes", "republican_votes", "other_votes"]):
        assert sum(row[field] for row in statewide) == expected[index]
    for row in statewide:
        assert row["contest_votes"] == sum(d["contest_votes"] for d in districts
                                          if d["state_code"] == row["state_code"])
        assert row["margin_pp"] == pytest.approx(
            100 * (row["democratic_votes"] - row["republican_votes"]) / row["contest_votes"], abs=.00001)


@pytest.mark.parametrize("field,value", [
    ("test_data", True), ("election_date", "2024-11-05"), ("province", "CA"),
    ("election_type", "Senate"), ("election_scope", "Primary"),
])
def test_house_refresh_rejects_wrong_election_identity(field, value):
    source = house_fixture()
    source[field] = value
    with pytest.raises(ValueError, match="Wrong election"):
        context.house_results(source, {key.split("-")[0].upper() for key in source["region_results"]}, "source")


def test_house_refresh_rejects_missing_duplicate_and_unreconciled_results():
    source = house_fixture()
    states = {key.split("-")[0].upper() for key in source["region_results"]}
    source["region_results"].pop("ak-al")
    with pytest.raises(ValueError, match="435 voting districts"):
        context.house_results(source, states, "source")
    source = house_fixture()
    source["region_results"]["ak-00"] = source["region_results"]["ak-al"]
    with pytest.raises(ValueError, match="Duplicate"):
        context.house_results(source, states, "source")
    source = house_fixture()
    source["candidates"][0]["votes"] += 1
    with pytest.raises(ValueError, match="reconcile"):
        context.house_results(source, states, "source")


def test_failed_house_refresh_keeps_the_previous_published_pointer(tmp_path, monkeypatch):
    source = house_fixture()
    source["test_data"] = True
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return source

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(context.requests, "get", lambda *args, **kwargs: Response())
    pointer = tmp_path / "public/participation-results/latest.json"
    pointer.parent.mkdir(parents=True)
    pointer.write_text('{"snapshot_id":"previous"}')
    with pytest.raises(ValueError, match="Wrong election"):
        context.refresh_results("invalid", set())
    assert json.loads(pointer.read_text()) == {"snapshot_id": "previous"}
    assert not (pointer.parent / "invalid").exists()


def test_current_precinct_number_requires_an_explicit_unambiguous_identity():
    assert current_precincts.precinct_number("PCT 001", "Bernalillo") == "1"
    assert current_precincts.precinct_number("PREC 048", "Rio Arriba") == "48"
    assert current_precincts.precinct_number("001", "Colfax") == "1"
    assert current_precincts.precinct_number("PRECINCT 7- LORDSBURG NORTH/WEST", "Hidalgo") == "7"
    assert current_precincts.precinct_number("PRECINCT 1 - OTHER", "Bernalillo") is None
    assert current_precincts.precinct_number("PRECINCT 1/2", "Hidalgo") is None
    assert current_precincts.precinct_number("EARLY 001", "Colfax") is None


def test_current_precinct_join_is_county_scoped_and_withholds_entire_mismatched_sets():
    def feature(county, number):
        return {"properties": {"county": county, "precinct": str(number)}}

    def row(county, number, ballots=60, denominator=100):
        return {"state_code": "NM", "county": county, "county_id": county,
                "unit": f"PCT {number:03}", "unit_key": f"{county}|{number}", "unit_kind": "precinct",
                "ballots": ballots, "denominator": denominator, "denominator_basis": "source_electorate",
                "reported_pct": ballots / denominator * 100, "source_url": "source", "source_update_label": ""}

    counties = [{"state_code": "NM", "county": county, "county_id": county, "rows_reconcile": True}
                for county in ["Catron", "Mora"]]
    features = [feature("Catron", 1), feature("Mora", 1)]
    rows = [row("Catron", 1), row("Mora", 1, 80), row("Mora", 2)]
    audit = current_precincts.join_precincts(features, rows, counties)
    assert features[0]["properties"]["reported_pct"] == 60
    assert features[0]["properties"]["unit_key"] == "Catron|1"
    assert features[1]["properties"]["reported_pct"] is None
    assert features[1]["properties"]["unit_key"] is None
    assert audit[1]["reporting_only_ids"] == ["2"]
    assert not audit[1]["exact_precinct_set"]
    for invalid_rows, invalid_counties in [
        ([rows[0], rows[0]], counties),
        ([{**rows[0], "unit_kind": "vote_center"}], counties),
        ([{**rows[0], "county_id": "Other office"}], counties),
        ([rows[0]], [{**counties[0], "rows_reconcile": False}]),
    ]:
        polygon = feature("Catron", 1)
        current_precincts.join_precincts([polygon], invalid_rows, invalid_counties)
        assert polygon["properties"]["reported_pct"] is None
    for observation in [row("Catron", 1, 10, 20), {**rows[0], "reported_pct": None}]:
        polygon = feature("Catron", 1)
        current_precincts.join_precincts([polygon], [observation], counties)
        assert polygon["properties"]["reported_pct"] is None
        assert polygon["properties"]["match_status"] == "rate_withheld"


def test_missing_historical_ids_never_merge_duplicate_names_or_elections():
    assert local.historical_source_id(None, 2004, 2) == "source-row:2004:2"
    assert local.historical_source_id("", 2004, 3) != local.historical_source_id(None, 2004, 2)
    assert local.historical_source_id(None, 2006, 2) != local.historical_source_id(None, 2004, 2)
    assert local.historical_source_id("0100100000", 2004, 2) == "0100100000"
    assert local.normalized_id(None) == ""


def test_local_rates_require_exact_identity_and_consistent_denominators():
    row = eavs(2024, [["AL", "0100100000", "Autauga", 80, 60, "", "", "", 20, "", "", ""]])[0]
    key = ("AL", "0100100000", "Autauga")
    registration = {"registered": 100, "registration_field": "a1a", "registration_comment": "Original note"}
    assert local.local_record(row, {key: registration})["turnout_pct"] == 80
    assert local.local_record(row, {("AL", "0100100000", "Another county"): registration})["turnout_pct"] is None
    assert local.local_record(row, {key: {**registration, "registered": 79}})["turnout_pct"] is None
    assert local.local_record(row, {key: registration})["registration_comment"] == "Original note"
    assert local.reported({"a1a": 100, "a1a_notavailable": "X"}, "a1a") is None


def test_local_geography_requires_id_name_and_unique_reporting_area():
    county = {"01001": {"properties": {"name": "Autauga County"}}}
    town = {"5500225": {"properties": {"name": "Ackley town"}}}
    row = {"state_code": "AL", "jurisdiction_id": "0100100000", "jurisdiction": "AUTAUGA",
           "statewide_unit": False, "supplemental_unit": False}
    assert local.match_geography(row, county, {}, "01") == {"level": "county", "key": "01001"}
    assert local.match_geography({**row, "jurisdiction": "Other"}, county, {}, "01") is None
    assert local.match_geography({**row, "statewide_unit": True}, county, {}, "01") is None
    wi = {**row, "jurisdiction_id": "00225", "jurisdiction": "TOWN OF ACKLEY - LANGLADE COUNTY"}
    assert local.match_geography(wi, {}, town, "55") == {"level": "municipality", "key": "5500225"}
    assert local.match_geography({**wi, "jurisdiction": "ACKLEY WARD 1"}, {}, town, "55") is None


def test_registration_ingestion_preserves_comments_missing_flags_and_exact_names():
    source = (b"State,FIPSCode,Jurisdiction,A1a,A1a_NotAvailable,A1Comments\n"
              b"AL,0100100000,Autauga,100,,Original registration note\n"
              b"AL,0100100000,Other office,90,X,Unavailable despite numeric cell\n")
    rows = local.registration_records(source, "source.csv")
    assert rows[("AL", "0100100000", "Autauga")]["registered"] == 100
    assert rows[("AL", "0100100000", "Autauga")]["registration_comment"] == "Original registration note"
    assert rows[("AL", "0100100000", "Other office")]["registered"] is None
    with pytest.raises(ValueError, match="Duplicate registration identity"):
        local.registration_records(source + source.splitlines(keepends=True)[1], "source.csv")


def test_2008_registration_field_keeps_source_definition_and_unavailable_flag():
    source = (b"JurisID,JurisName,STATE_,A1,A1_NotAvailable,A1_Comments,A2\n"
              b"0100100000,Autauga,AL,100,,Source note,only active voters\n"
              b"0100300000,Baldwin,AL,90,X,Unavailable,both active and inactive\n")
    rows = local.registration_records(source, "source.csv")
    assert rows[("AL", "0100100000", "Autauga")]["registered"] == 100
    assert rows[("AL", "0100100000", "Autauga")]["registration_definition"] == "only active voters"
    assert rows[("AL", "0100100000", "Autauga")]["registration_comment"] == "Source note"
    assert rows[("AL", "0100300000", "Baldwin")]["registered"] is None


def test_state_only_registration_override_requires_matching_fips_and_ignores_blank_rows():
    source = b"JurisID,JurisName,A1a\n4800100000,Anderson,100\n,,\n"
    rows = local.registration_records(source, "source.csv", ("TX", "48"))
    assert rows[("TX", "4800100000", "Anderson")]["registered"] == 100
    with pytest.raises(ValueError, match="different state"):
        local.registration_records(source.replace(b"48001", b"17001"), "source.csv", ("TX", "48"))


def portal_fixture(monkeypatch, rows, county_name="Bernalillo", ballots=80, denominator=100):
    monkeypatch.setitem(current_local.PORTALS, "NM", ("page", "service", 1))
    page = ('<input id="hidElectionDate" value="11/3/2026" />'
            '<input id="hidElectionType" value="General" />'
            '<div class="provisional-results-wrapper"><h1>' + county_name + '</h1>'
            '<div id="countyturnout02"></div>')
    for name, count, electorate in rows:
        page += (f'<div class="county-precinct">{name}</div>'
                 f'<div class="county-cast"><span>{count}</span></div>'
                 f'<div class="county-counted"><span>{electorate}</span></div>')
    payload = [{"CountyID": "02", "CountyName": county_name, "calcVoterTurnout": str(ballots),
                "Voters": denominator, "PrecinctsReporting": len(rows), "TotalPrecincts": len(rows),
                "CountyPercent": ballots / denominator, "CurrentDateTime": None}]
    official = {"ballots": ballots, "denominator": denominator, "denominator_basis": "eligible_voters_source_definition",
                "source_update_label": "11/4/2026"}
    return page, payload, "NM", official, {"source_url": "source"}


def test_2026_precinct_rates_require_reconciled_county_counts(monkeypatch):
    inputs = portal_fixture(monkeypatch, [("PCT 1", 50, 60), ("PCT 2", 30, 40)])
    counties, rows = current_local.parse_portal(*inputs)
    assert counties[0]["rows_reconcile"]
    assert rows[1]["reported_pct"] == 75
    assert rows[1]["denominator_basis"] == "eligible_voters_source_definition"
    page, payload, code, official, provenance = inputs
    bad = page.replace("<span>30</span>", "<span>20</span>")
    counties, rows = current_local.parse_portal(bad, payload, code, official, provenance)
    assert not counties[0]["rows_reconcile"]
    assert all(row["reported_pct"] is None for row in rows)
    with pytest.raises(ValueError, match="statewide totals"):
        current_local.parse_portal(page, payload, code, {**official, "ballots": 81}, provenance)
    with pytest.raises(ValueError, match="election identity"):
        current_local.parse_portal(page.replace("11/3/2026", "11/5/2024"), payload, code, official, provenance)


def test_vote_centers_duplicate_names_and_countywide_rows_are_not_precinct_rates(monkeypatch):
    inputs = portal_fixture(monkeypatch, [("Church Hall", 0, 100), ("Church Hall", 80, 100)],
                            county_name="Oglala Lakota (Vote Center)")
    counties, rows = current_local.parse_portal(*inputs)
    assert not counties[0]["rows_reconcile"]
    assert len({row["unit_key"] for row in rows}) == 2
    assert all(row["unit_kind"] == "vote_center" and row["reported_pct"] is None for row in rows)
    inputs = portal_fixture(monkeypatch, [("PCT 1", 80, 100), ("Countywide", 0, 100)])
    _, rows = current_local.parse_portal(*inputs)
    assert rows[1]["unit_kind"] == "countywide"
    assert all(row["reported_pct"] is None for row in rows)


def eavs(year, rows):
    prefix = "QF1" if 2010 <= year <= 2014 else "F1"
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["State", "FIPSCode", "Jurisdiction", *[prefix + c for c in "abcdefg"], prefix + "_Comment", "F2"])
    writer.writerows(rows)
    return methods.normalize_eavs(stream.getvalue().encode(), "source.csv", year, {"AL", "AK", "ME"}, "https://www.eac.gov/source")


@pytest.mark.parametrize("value", [None, "", -99, "-88", "-77", "-888888: Not Applicable",
                                  "-999999: Data Not Available", "Does not apply", "Data not available"])
def test_missing_is_not_zero(value):
    assert methods.count(value) is None
    assert methods.count("0") == 0


def test_2008_other_and_later_mail_are_not_interchangeable():
    record = ["AL", "0100100000", "Autauga", 100, 50, 1, 10, 4, 30, 5, "Absentee includes in-person", "Vote history"]
    old = eavs(2008, [record])[0]
    later = eavs(2012, [record])[0]
    assert "all_mail" not in old["methods"]
    assert later["methods"]["all_mail"] == 5
    assert later["methods"]["provisional"] == 4
    assert later["methods"]["early_in_person"] == 30
    assert later["source_details"]["qf1_comment"] == "Absentee includes in-person"
    assert later["source_details"]["f2"] == "Vote history"


def test_matched_denominators_and_invalid_shares():
    records = eavs(2024, [
        ["AL", "1", "A", 100, 40, "", "", "", 10, "", "", ""],
        ["AL", "2", "B", 900, "", "", "", "", "", "", "", ""],
        ["AL", "3", "C", "", 20, "", "", "", "", "", "", ""],
        ["AL", "4", "D", 10, 30, "", "", "", "", "", "", ""],
    ])
    row = next(r for r in methods.state_summaries(records) if r["mode"] == "election_day")
    assert row["reported_count"] == 90
    assert row["matched_count"] == 40
    assert row["matched_participation"] == 100
    assert row["share_pct"] == 40
    assert row["matched_units"] == 1
    assert row["total_units"] == 4
    assert row["invalid_share_units"] == 1
    missing = next(r for r in methods.state_summaries(records) if r["mode"] == "uocava")
    assert missing["reported_count"] is None
    assert missing["share_pct"] is None


def test_statewide_and_special_units_do_not_double_count():
    records = eavs(2024, [
        ["AK", "0200000000", "ALASKA", 100, 60, "", "", "", 40, "", "", ""],
        ["AK", "0200100000", "Component", 100, 60, "", "", "", 40, "", "", ""],
        ["ME", "23", "UOCAVA-ME", 5, 0, 5, "", "", "", "", "", ""],
        ["ME", "2300100000", "Local unit", 200, 80, 5, "", "", 50, "", "", ""],
    ])
    rows = methods.state_summaries(records)
    ak = next(r for r in rows if r["state_code"] == "AK" and r["mode"] == "election_day")
    assert ak["reported_count"] == 60
    assert ak["excluded_component_units"] == 1
    me = next(r for r in rows if r["state_code"] == "ME" and r["mode"] == "uocava")
    assert me["reported_count"] == 5
    assert len(records) == 4


def test_repeated_source_ids_preserve_distinct_wards_but_reject_duplicates():
    record = ["AL", "1", "Ward 1", 100, 50, "", "", "", 30, "", "", ""]
    other = record.copy()
    other[2] = "Ward 2"
    assert len(eavs(2014, [record, other])) == 2
    with pytest.raises(ValueError, match="duplicate reporting unit"):
        eavs(2014, [record, record])


def test_census_stops_before_margins_of_error():
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Table 14. Method of Voting"])
    sheet.append(["Total", None, 100, 40, 30, 29, 1])
    sheet.append(["Sex", "Female", 55, 39, 31, 29, 1])
    sheet.append(["Margins of Error"])
    sheet.append(["Total", None, 5, 2, 1, 1, 1])
    stream = io.BytesIO()
    book.save(stream)
    rows = methods.census_rows(stream.getvalue(), 2024, "https://www.census.gov/source")
    assert len(rows) == 2
    assert rows[0]["methods"]["unknown"] == 1
    assert rows[0]["reported_voters_thousands"] == 100


def test_margin_uses_all_contest_votes_not_two_party_denominator():
    assert context.margin(45, 40, 15)["margin_pp"] == 5
    assert context.margin(0, 0, 0)["margin_pp"] is None
    with pytest.raises(ValueError):
        context.margin(10, -1, 0)


def test_unavailable_flags_override_contradictory_numeric_cells():
    source = b"State,FIPSCode,Jurisdiction,F1a,F1b,F1f,F1f_NotAvailable\nAL,1,County,100,60,40,X\n"
    row = methods.normalize_eavs(source, "source.csv", 2008, {"AL"}, "source")[0]
    assert row["methods"]["early_in_person"] is None
    assert row["raw_method_fields"]["f"] == "40"
    assert row["source_details"]["f1f_notavailable"] == "X"


def test_1994_recap_reconciles_and_omits_untabulated_louisiana():
    rows = context.clerk_1994("official-source")
    assert len(rows) == 49
    assert not any(row["state_code"] == "LA" for row in rows)
    assert sum(row["contest_votes"] for row in rows) == 70493648
    assert next(row for row in rows if row["state_code"] == "NC")["margin_pp"] < 0


def test_fec_accepts_shifted_state_code_column_without_using_primary_votes(monkeypatch):
    rows = [["2010 VOTES CAST FOR THE U.S. HOUSE OF REPRESENTATIVES BY PARTY"],
            ["Alabama", "AL", 900, 800, 700, 45, 40, 15]]
    monkeypatch.setattr(context, "workbook", lambda *args, **kwargs: {"House": rows})
    row = context.summary_tables(b"", 2010, {"AL": "Alabama"}, "source")[0]
    assert row["democratic_votes"] == 45
    assert row["republican_votes"] == 40
    assert row["contest_votes"] == 100


def test_fec_rejects_missing_state_coverage(monkeypatch):
    monkeypatch.setattr(context, "workbook", lambda *args, **kwargs: {
        "House": [["2010 VOTES CAST FOR THE U.S. HOUSE OF REPRESENTATIVES BY PARTY"]]})
    with pytest.raises(ValueError, match="missing states"):
        context.summary_tables(b"", 2010, {"AL": "Alabama"}, "source")


def test_fec_withholds_bad_presidential_state_without_discarding_reconciled_states(monkeypatch):
    sheets = {
        "House": [["HOUSE OF REPRESENTATIVES BY PARTY"],
                  ["AL", 0, 0, 0, 5, 4, 1], ["NY", 0, 0, 0, 20, 10, 5]],
        "Combined": [["GENERAL ELECTION VOTES CAST BY PARTY"],
                     ["AL", 50, 44, 16], ["NY", 30, 25, 4]],
        "Senate": [["SENATE BY PARTY"]],
        "Totals": [["GENERAL ELECTION VOTES CAST FOR"], ["AL", 100], ["NY", 24]],
    }
    monkeypatch.setattr(context, "workbook", lambda *args, **kwargs: sheets)
    rejected = []
    rows = context.summary_tables(b"", 2000, {"AL": "Alabama", "NY": "New York"}, "source", rejected=rejected)
    assert {(row["office"], row["state_code"]) for row in rows} == {
        ("U.S. House", "AL"), ("U.S. House", "NY"), ("President", "AL")}
    assert next(row for row in rows if row["office"] == "President")["contest_votes"] == 100
    assert len(rejected) == 1
    assert "2000 NY" in rejected[0]["error"]
    with pytest.raises(ValueError, match="2000 NY"):
        context.summary_tables(b"", 2000, {"AL": "Alabama", "NY": "New York"}, "source")
