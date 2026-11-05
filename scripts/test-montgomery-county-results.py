import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "montgomery", Path(__file__).with_name("review-montgomery-2026-county-results.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SOURCE = Path(__file__).resolve().parents[1] / "data/county-source-reviews/20261105-montgomery-reviewed-01/originals"


@pytest.fixture
def originals():
    return module.load_originals(SOURCE)


def change_csv(originals, transform):
    rows = list(csv.DictReader(io.StringIO(originals["vendor-portions.csv"].decode(), newline="")))
    fields = list(rows[0])
    transform(rows)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    originals["vendor-portions.csv"] = stream.getvalue().encode()


def change_json(originals, transform):
    data = json.loads(originals["montgomery-results.json"])
    transform(data)
    originals["montgomery-results.json"] = json.dumps(data).encode()


def test_full_reports_reconcile_without_conflating_votes_and_participation(originals):
    tables, audit = module.review(originals)
    parties = {r["party_literal"]: r["votes"] for r in audit["house_votes"]}
    assert parties == {"DEM": 268823, "REP": 120367, "": 711}
    assert sum(parties.values()) == 389901
    county = tables["county-participation.csv"][0]
    assert (county["ballots_cast"], county["registered_voters"]) == (392630, 628331)
    assert county["reporting_basis"] == "Election Day in-person only"
    assert not county["final_certified_turnout"] and not audit["new_maps_approved"]
    assert (audit["native_parent_precincts"], audit["native_portions"]) == (428, 431)
    assert audit["native_explicit_zeroes"] == 6
    assert len(tables["native-portion-candidate-counts.csv"]) == 3634
    assert len(tables["county-candidate-results.csv"]) == 71
    processing = {r["native_measure"]: r["count"] for r in tables["county-ballot-processing.csv"]}
    assert processing["Absentee & Mail in Ballots Returned"] == 109191
    assert processing["Absentee & Mail in Ballots Counted"] == 107547


def test_split_portions_are_not_parent_deduplicated(originals):
    tables, _ = module.review(originals)
    portions = [r for r in tables["native-portion-participation.csv"] if r["native_precinct"] == "Lower Merion 11-3"]
    assert {(r["native_split_name"], r["registered_voters"], r["total_ballots"]) for r in portions} == {
        ("Lower Merion 11-3 4th Congressional", 1504, 930),
        ("Lower Merion 11-3 5th Congressional", 7, 1),
    }


def test_pdf_only_multivote_writeins_are_not_ballots_or_a_party(originals):
    tables, _ = module.review(originals)
    contest = next(r for r in tables["county-contest-totals.csv"] if r["contest"] == module.COMMISSION)
    assert (contest["selectable_options"], contest["ballots_cast"], contest["unresolved_write_in_votes"]) == (7, 4113, 6743)
    assert contest["native_under_votes"] == contest["native_over_votes"] == ""
    row = next(r for r in tables["county-candidate-results.csv"] if r["contest"] == module.COMMISSION)
    assert row["party_literal"] == "" and row["row_kind"] == "unresolved_write_in"
    questions = [r for r in tables["county-office-party-totals.csv"] if r["office"] == "ballot_question"]
    assert not questions


@pytest.mark.parametrize("value", ["", "-1", "1.5", "1,23", None, True])
def test_invalid_or_missing_native_vote_counts_are_rejected(originals, value):
    change_csv(originals, lambda rows: rows[0].update(total_votes=value))
    with pytest.raises(ValueError):
        module.review(originals)


def test_duplicate_candidate_observation_is_rejected(originals):
    change_csv(originals, lambda rows: rows.append(dict(rows[0])))
    with pytest.raises(ValueError, match="Duplicated native"):
        module.review(originals)


def test_removed_explicit_zero_fails_even_with_unchanged_vote_sums(originals):
    change_csv(originals, lambda rows: rows.remove(next(r for r in rows if r["total_votes"] == "0")))
    with pytest.raises(ValueError, match="row multisets"):
        module.review(originals)


def test_changed_split_identity_is_rejected(originals):
    change_csv(originals, lambda rows: next(r for r in rows if r["Split_name"]).update(Split_name=""))
    with pytest.raises(ValueError):
        module.review(originals)


def test_changed_candidate_mode_fails_despite_unchanged_total(originals):
    def alter(rows):
        rows[0]["Election Day_votes"] = str(int(rows[0]["Election Day_votes"]) - 1)
        rows[0]["Mail-in_votes"] = str(int(rows[0]["Mail-in_votes"]) + 1)
    change_csv(originals, alter)
    with pytest.raises(ValueError, match="row multisets"):
        module.review(originals)


def test_pdf_party_is_independently_checked_when_json_and_csv_agree(originals):
    change_csv(originals, lambda rows: [r.update(Party_Code="REP") for r in rows
               if r["candidate_name"] == "JOSH SHAPIRO AND AUSTIN DAVIS"])
    def alter(data):
        for r in data["precinct_results"]:
            if r["candidate"] == "JOSH SHAPIRO AND AUSTIN DAVIS":
                r["party"] = "REP"
        for contest in data["contests"]:
            for r in contest["candidates"]:
                if r["candidate"] == "JOSH SHAPIRO AND AUSTIN DAVIS":
                    r["party"] = "REP"
    change_json(originals, alter)
    with pytest.raises(ValueError, match="CSV/PDF"):
        module.review(originals)


def test_native_under_over_fields_are_not_ignored(originals):
    change_csv(originals, lambda rows: [r.update(total_under_votes=str(int(r["total_under_votes"]) + 1))
               for r in rows if r["Precinct_name"] == "Ambler 1" and r["Contest_title"] == module.GOVERNOR])
    with pytest.raises(ValueError, match="mode|residual"):
        module.review(originals)


def test_counted_mail_is_not_substituted_by_returned_mail(originals):
    originals["ballot-data.txt"] = originals["ballot-data.txt"].replace(
        b"Ballots Counted - 107,547", b"Ballots Counted - 109,191")
    with pytest.raises(ValueError, match="counted-mail"):
        module.review(originals)


@pytest.mark.parametrize("field,value", [("status", "test"), ("title", "2024 General Election")])
def test_wrong_election_or_status_is_rejected(originals, field, value):
    change_json(originals, lambda data: data["meta"].update({field: value}))
    with pytest.raises(ValueError, match="election"):
        module.review(originals)


def test_original_receipt_mismatch_fails(tmp_path):
    for path in SOURCE.iterdir():
        (tmp_path / path.name).write_bytes(path.read_bytes())
    with (tmp_path / "vendor-portions.csv").open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(ValueError, match="receipt mismatch"):
        module.load_originals(tmp_path)
