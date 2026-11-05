import importlib.util
import json
from pathlib import Path
import shutil

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "bucks_review", ROOT / "scripts/review-bucks-2026-county-results.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)
ORIGINALS = ROOT / "data/county-source-reviews/20261105-bucks-reviewed-02/originals"


@pytest.fixture(scope="module")
def originals():
    return REVIEW.load_originals(ORIGINALS)


def test_complete_counts_parties_and_partial_counting_remain_separate(originals):
    tables, audit = REVIEW.review(originals)
    assert audit["native_units"] == 304
    assert audit["native_contests"] == 15
    assert audit["native_unit_candidate_rows"] == 3949
    assert audit["native_unit_explicit_zeroes"] == 343
    assert audit["house_literal_party_votes"] == {"Dem": 158908, "Rep": 142796, "Nonpart": 1082}
    county = tables["county-participation.csv"][0]
    assert county["ballots_counted"] == 305485
    assert county["registered_voters"] == 487385
    assert county["house_candidate_votes"] == 302786
    assert county["mail_counting_status"].endswith("Partially Reported")
    assert county["in_person_counting_status"].endswith("Partially Reported")
    assert not county["final_certified_turnout"]
    house = next(r for r in tables["county-contest-totals.csv"] if r["office"] == "us_house")
    assert house["ballots_minus_candidate_votes_unclassified"] == 2699
    assert sum(r["native_votes_cast"] for r in tables["native-unit-participation.csv"]) == 305485
    assert {r["party_csv_literal"] for r in tables["county-candidate-results.csv"]} == {
        "Dem", "Rep", "Lib", "Nonpart", "Ind", "Fwi"}
    assert all(r["mode_votes"] == 0 for r in tables["county-candidate-mode-counts.csv"]
               if r["voting_mode_literal"] == "Provisional Votes")
    native = next(r for r in tables["native-unit-participation.csv"]
                  if r["native_unit_name"] == "Bensalem Twp Upper # 1")
    assert native["native_geo_key"] == "Bensalem Twp Upper #1"
    assert not audit["new_maps_approved"] and not audit["fully_complete"]


@pytest.mark.parametrize("value", [b"", b"-1", b"1.5"])
def test_missing_negative_or_fractional_native_votes_fail(originals, value):
    raw = dict(originals)
    raw["native-units.csv"] = raw["native-units.csv"].replace(b'"1044"', b'"' + value + b'"', 1)
    with pytest.raises(ValueError, match="invalid explicit integer"):
        REVIEW.review(raw)


def test_duplicate_native_observation_fails(originals):
    raw = dict(originals)
    line = raw["native-units.csv"].splitlines(keepends=True)[3]
    raw["native-units.csv"] += line
    with pytest.raises(ValueError, match="Duplicate or unknown native candidate"):
        REVIEW.review(raw)


def test_missing_explicit_zero_fails_even_when_all_sums_are_unchanged(originals):
    raw = dict(originals)
    line = b'"Bedminster Twp East","GOVERNOR AND LIEUTENANT GOVERNOR","Write-in","0","66.38%"\r\n'
    assert line in raw["native-units.csv"]
    raw["native-units.csv"] = raw["native-units.csv"].replace(line, b"", 1)
    with pytest.raises(ValueError, match="Missing native candidate option"):
        REVIEW.review(raw)


def test_candidate_mode_disagreement_fails(originals):
    raw = dict(originals)
    raw["summary.csv"] = raw["summary.csv"].replace(b'"72067"', b'"72068"', 1)
    with pytest.raises(ValueError, match="candidate modes"):
        REVIEW.review(raw)


def test_pdf_party_disagreement_fails_even_if_csv_and_html_match(originals):
    raw = dict(originals)
    raw["summary.csv"] = raw["summary.csv"].replace(
        b'"Bob Harvie","Dem"', b'"Bob Harvie","Rep"', 1)
    raw["native-results.redacted.html"] = raw["native-results.redacted.html"].replace(
        b"Bob Harvie (Dem)", b"Bob Harvie (Rep)").replace(
        b"Bob Harvie, DEM", b"Bob Harvie, REP")
    with pytest.raises(ValueError, match="Unknown PDF candidate or literal party"):
        REVIEW.review(raw)


def test_participation_disagreement_fails(originals):
    raw = dict(originals)
    raw["native-results.redacted.html"] = raw["native-results.redacted.html"].replace(
        b">305,485<", b">305,486<", 1)
    with pytest.raises(ValueError, match="County participation"):
        REVIEW.review(raw)


def test_district_ballot_disagreement_fails(originals):
    raw = dict(originals)
    raw["contests.csv"] = raw["contests.csv"].replace(b'"123132"', b'"123133"', 1)
    with pytest.raises(ValueError, match="contest partition or ballot total"):
        REVIEW.review(raw)


@pytest.mark.parametrize("old,new", [
    (b"2026 General Election", b"2024 General Election"),
    (b"UNOFFICIAL RESULTS", b"Testing in Progress"),
    (b"Partially Reported", b"Fully Reported"),
])
def test_wrong_election_testing_or_changed_counting_status_fails(originals, old, new):
    raw = dict(originals)
    raw["native-results.redacted.html"] = raw["native-results.redacted.html"].replace(old, new)
    with pytest.raises(ValueError):
        REVIEW.review(raw)


def test_changed_original_bytes_fail_receipt_verification(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(ORIGINALS, source)
    with (source / "summary.csv").open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(ValueError, match="acquisition receipt"):
        REVIEW.load_originals(source)


def test_redacted_snapshot_cannot_be_misrepresented_as_an_original(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(ORIGINALS, source)
    receipts = json.loads((source / "receipts.json").read_bytes())
    native = next(r for r in receipts if r["file"] == "native-results.redacted.html")
    del native["redaction"]
    (source / "receipts.json").write_text(json.dumps(receipts))
    with pytest.raises(ValueError, match="HTML token-redaction receipt"):
        REVIEW.load_originals(source)
