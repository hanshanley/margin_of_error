import importlib.util
import io
from pathlib import Path

from bs4 import BeautifulSoup
from openpyxl import load_workbook
import pytest


spec = importlib.util.spec_from_file_location(
    "monroe", Path(__file__).with_name("review-monroe-2026-county-results.py"))
monroe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monroe)
SOURCE = Path(__file__).resolve().parents[1] / "data/county-source-reviews/20261105-monroe-official-01/originals"


def test_full_originals_reconcile_without_conflating_votes_ballots_and_party_names():
    tables, audit = monroe.review(SOURCE)
    candidates = tables["county-candidate-results"]
    modes = tables["county-candidate-mode-counts"]
    units = tables["native-unit-candidate-counts"]
    for row in candidates:
        identity = (row["native_contest"], row["candidate"])
        for collection in [modes, units]:
            assert row["votes"] == sum(r["votes"] for r in collection
                                      if (r["native_contest"], r["candidate"]) == identity)
    house = [r for r in candidates if r["office"] == "us_house"]
    assert sum(r["votes"] for r in house) != audit["total_ballots_tabulated"]
    assert all(r["party"] == "Nonpartisan" and r["party_html"] == ""
               for r in candidates if r["candidate"] == "Write-in")
    assert any(r["votes"] == 0 for r in modes)
    assert any(r["votes"] == 0 for r in units)
    assert not audit["maps_approved"] and not audit["fully_complete"]


def test_testing_pages_and_wrong_election_are_rejected():
    with pytest.raises(ValueError, match="test/testing"):
        monroe.checked_html((SOURCE / "philadelphia.html").read_bytes())
    raw = (SOURCE / "monroe.html").read_bytes()
    with pytest.raises(ValueError, match="Wrong election"):
        monroe.county_summary(monroe.checked_html(raw.replace(b"2026 General Election", b"2026 General Primary")))


@pytest.mark.parametrize("value", [None, "", -1, 1.5, True, "1,23", "12.0"])
def test_missing_fractional_negative_or_malformed_counts_are_not_zero_filled(value):
    with pytest.raises(ValueError, match="integer"):
        monroe.integer(value)


def test_mode_count_disagreement_fails_closed():
    soup = BeautifulSoup((SOURCE / "monroe.html").read_bytes(), "html.parser")
    table = soup.select("table:has(> thead)")[0]
    target = table.select_one("button[data-bs-toggle='modal']")["data-bs-target"]
    soup.select_one(target).select(".modal-body span")[0].string = "0"
    with pytest.raises(ValueError, match="modes do not reconcile"):
        monroe.html_contest(table, soup)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "wrong_sum"])
def test_incomplete_duplicate_or_unreconciled_native_units_are_rejected(mutation):
    soup = BeautifulSoup((SOURCE / "monroe-contest-01.html").read_bytes(), "html.parser")
    _, candidates, totals = monroe.html_contest(soup.select("table:has(> thead)")[0], soup)
    rows = soup.select("table.table-bordered tr")
    if mutation == "missing":
        rows[-1].decompose()
    elif mutation == "duplicate":
        rows[-1].select("td")[0].string = rows[1].select("td")[0].get_text()
    else:
        rows[-1].select("td")[1].string = "0"
    with pytest.raises(ValueError, match="reporting units|vectors do not reconcile"):
        monroe.native_units(soup, candidates, totals)


@pytest.mark.parametrize("mutation", ["unmatched_row", "wrong_candidate_total"])
def test_workbook_rows_cannot_be_dropped_or_disagree_with_html(monkeypatch, mutation):
    original = monroe.read_original

    def changed(source, name):
        raw, receipt = original(source, name)
        if name == "monroe-all-contests.xlsx":
            book = load_workbook(io.BytesIO(raw))
            if mutation == "unmatched_row":
                book.active.append(["EXTRA CONTEST", 1, 0, 0, 0, "OTHER", "Extra", 0])
            else:
                book.active.cell(2, 8).value = 0
            stream = io.BytesIO()
            book.save(stream)
            raw = stream.getvalue()
        return raw, receipt

    monkeypatch.setattr(monroe, "read_original", changed)
    with pytest.raises(ValueError, match="unmatched rows|fields disagree"):
        monroe.review(SOURCE)


def test_district_overlap_cannot_be_hidden_by_reconciled_candidate_totals(monkeypatch):
    original = monroe.native_units

    def overlapping(soup, candidates, totals):
        units = original(soup, candidates, totals)
        if candidates[0]["candidate_html"] == "BOB BROOKS":
            units[0] = ("Barrett One", units[0][1])
        return units

    monkeypatch.setattr(monroe, "native_units", overlapping)
    with pytest.raises(ValueError, match="overlap or do not cover"):
        monroe.review(SOURCE)
