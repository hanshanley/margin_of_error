"""Regression checks against Lancaster's complete screened native originals."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("lancaster_review", HERE / "review-lancaster-county-results.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)
ORIGINALS = HERE.parent / "data/county-source-reviews/20261105-lancaster-reviewed-01/originals"


@pytest.fixture(scope="module")
def original():
    return REVIEW.load_originals(ORIGINALS)


@pytest.fixture
def raw(original):
    return copy.deepcopy(original)


def mutate(raw, callback):
    data = json.loads(raw["data.json"])
    callback(data)
    raw["data.json"] = json.dumps(data).encode()


def test_complete_native_counts_and_qualifications(raw):
    audit, tables = REVIEW.review(raw)
    assert (audit["ballots"], audit["registrations"], audit["native_units"]) == (216221, 366763, 241)
    assert (audit["acquired_contests"], audit["native_options"], audit["explicit_option_zeroes"]) == (14, 43, 13)
    assert audit["native_all_contest_selections_not_ballots"] == 987583
    options = tables["county-option-results.csv"]
    write_ins = [r for r in options if r["option_kind"] == "write_in"]
    assert len(write_ins) == 13
    assert all(r["votes"] == 0 and r["native_party_abbreviation"] == "" for r in write_ins)
    measures = [r for r in options if r["option_kind"] == "ballot_measure_option"]
    assert len(measures) == 2
    assert not {r["contest_id"] for r in measures} & {
        r["contest_id"] for r in tables["county-literal-party-totals.csv"]}
    house = next(r for r in tables["county-contest-accounting.csv"]
                 if r["native_contest"] == "REPRESENTATIVE IN CONGRESS 11TH DISTRICT")
    assert (house["votes"], house["pdf_undervotes"], house["pdf_overvotes"],
            house["remaining_unclassified_ballots"]) == (214875, 947, 36, 363)
    assert house["native_api_undervotes"] is None and house["native_api_overvotes"] is None
    assert all(not r["usable_as_actual_ballot_count"] for r in
               tables["county-contest-accounting-modes.csv"] if r["native_group_name"] != "TOTAL")
    assert all(not r["usable_for_party_participation"] for r in tables["native-party-statistics.csv"])
    senate = [r for r in tables["county-contest-accounting.csv"]
              if r["native_contest"].startswith("SENATOR IN THE GENERAL ASSEMBLY")]
    assert sum(r["total_units"] for r in senate) == 132 < audit["native_units"]


def test_missing_explicit_zero_is_not_inferred(raw):
    mutate(raw, lambda d: d["ballotItems"][0]["summaryResults"]["ballotOptions"].pop())
    with pytest.raises(ValueError, match="summary PDF option inventory"):
        REVIEW.review(raw)


def test_changed_candidate_total_fails_pdf_check(raw):
    def change(data):
        option = data["ballotItems"][0]["summaryResults"]["ballotOptions"][0]
        option["voteCount"] += 1
        option["groupResults"][0]["voteCount"] += 1
        data["ballotItems"][0]["voteTotal"] += 1
    mutate(raw, change)
    with pytest.raises(ValueError, match="summary PDF option inventory"):
        REVIEW.review(raw)


def test_changed_party_is_not_normalized(raw):
    mutate(raw, lambda d: d["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["party"].update(
        abbreviation="OTHER"))
    with pytest.raises(ValueError, match="party identity"):
        REVIEW.review(raw)


def test_missing_mode_is_not_zero(raw):
    mutate(raw, lambda d: d["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["groupResults"].pop())
    with pytest.raises(ValueError, match="Incomplete option voting methods"):
        REVIEW.review(raw)


def test_duplicate_units_fail(raw):
    mutate(raw, lambda d: d["precincts"].append(copy.deepcopy(d["precincts"][0])))
    with pytest.raises(ValueError, match="duplicate native identities"):
        REVIEW.review(raw)


def test_partial_turnout_pagination_fails(raw):
    page = json.loads(raw["turnout.json"])
    page["totalRecordCount"] += 1
    raw["turnout.json"] = json.dumps(page).encode()
    with pytest.raises(ValueError, match="turnout pagination"):
        REVIEW.review(raw)


def test_nonmissing_api_accounting_must_match_pdf(raw):
    mutate(raw, lambda d: d["ballotItems"][0].update(underVoteCount=0))
    with pytest.raises(ValueError, match="Nonmissing API/PDF accounting"):
        REVIEW.review(raw)


@pytest.mark.parametrize("field,value", [("isProduction", False), ("isOfficialResults", True)])
def test_wrong_election_status_fails_without_snapshot_proxy(raw, field, value):
    election = json.loads(raw["election.json"])
    election[field] = value
    raw["election.json"] = json.dumps(election).encode()
    mutate(raw, lambda d: d["election"].update({field: value}))
    with pytest.raises(ValueError, match="Wrong election"):
        REVIEW.review(raw)


def test_partial_auxiliary_registration_does_not_mean_zero(raw):
    page = json.loads(raw["voter-registration.json"])
    page["totalRecordCount"] = 1
    raw["voter-registration.json"] = json.dumps(page).encode()
    with pytest.raises(ValueError, match="auxiliary pagination"):
        REVIEW.review(raw)


def test_duplicate_pdf_rows_fail():
    text = "Lancaster County\n2026 General Election\nNovember 03, 2026\nCONTEST\nName  0\nName  0\n"
    with pytest.raises(ValueError, match="Duplicate native PDF row"):
        REVIEW.pdf_tables(text, {"CONTEST"}, 1)


def test_office_district_ballots_cannot_exceed_county(raw, monkeypatch):
    import re
    extract = REVIEW.pdf_text

    def altered(data):
        text = extract(data)
        if data == raw["summary-voting-methods.pdf"]:
            text, replacements = re.subn(r"(Total Ballots Cast\s+)31,300", r"\g<1>31,301", text)
            assert replacements == 1
        return text

    monkeypatch.setattr(REVIEW, "pdf_text", altered)
    with pytest.raises(ValueError, match="Office district accounting exceeds"):
        REVIEW.review(raw)


@pytest.mark.parametrize("kind", ["service", "telemetry"])
def test_source_screening_catches_keys_not_receipt_drift(tmp_path, original, kind):
    import hashlib
    import shutil
    shutil.copytree(ORIGINALS, tmp_path / "originals")
    folder = tmp_path / "originals"
    data = original["native-landing.html"] + (
        b"AIza" + b"x" * 35 if kind == "service" else b'<script>licenseKey: "test-value"</script>')
    (folder / "native-landing.html").write_bytes(data)
    receipts = json.loads((folder / "receipts.json").read_bytes())
    for receipt in receipts:
        if receipt["file"] == "native-landing.html":
            receipt.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    (folder / "receipts.json").write_text(json.dumps(receipts))
    with pytest.raises(ValueError, match="Unredacted public service key"):
        REVIEW.load_originals(folder)


def test_missing_original_fails_inventory(tmp_path):
    import shutil
    shutil.copytree(ORIGINALS, tmp_path / "originals")
    (tmp_path / "originals/detailed-results.pdf").unlink()
    with pytest.raises(ValueError, match="Incomplete original receipt inventory"):
        REVIEW.load_originals(tmp_path / "originals")
