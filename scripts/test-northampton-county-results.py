import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

from bs4 import BeautifulSoup
import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "northampton_review", ROOT / "scripts/review-northampton-county-results.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)
ORIGINALS = ROOT / "data/county-source-reviews/20261105-northampton-reviewed-01/originals"


@pytest.fixture(scope="module")
def originals():
    return REVIEW.load_originals(ORIGINALS)


def changed(raw, soup):
    return dict(raw, **{"native-results.html": str(soup).encode()})


def test_native_ballots_parties_and_missing_district_denominators_stay_distinct(originals):
    tables, audit = REVIEW.review(originals)
    row = tables["county-participation.csv"][0]
    assert (row["ballots_cast"], row["registered_voters"], row["house_candidate_votes"]) == (
        129290, 234834, 127555)
    assert [r["ballots_cast"] for r in tables["county-ballot-mode-counts.csv"]] == [91136, 38154, 0]
    house = [r for r in tables["county-office-party-totals.csv"] if r["office"] == "us_house"]
    assert {r["party_html_prefix_literal"]: r["votes"] for r in house} == {
        "DEM": 72478, "REP": 54763, "": 314}
    contests = tables["county-contest-totals.csv"]
    house = next(r for r in contests if r["office"] == "us_house")
    assert house["ballots_minus_candidate_votes_unclassified"] == 1735
    assert all(r["native_under_votes"] is None and r["native_over_votes"] is None for r in contests)
    assert all(r["covered_ballots_cast"] is None for r in contests if not r["covers_all_county_native_units"])
    assert audit["native_units"] == 155 and audit["native_unit_explicit_zeroes"] == 220
    assert len(tables["native-unit-candidate-counts.csv"]) == 2015
    assert not audit["maps_approved"] and not audit["fully_complete"]
    assert "Mail-in Ballots: Partially Reported" in row["counting_qualifications_json"]


def test_missing_explicit_unit_zero_fails_without_changing_any_sum(originals):
    soup = BeautifulSoup(originals["native-results.html"], "html.parser")
    row = next(r for r in soup.select("#precinctListLayer tr.content-row")
               if r.select_one('[dv="true"]').get_text(strip=True) == "0")
    row.decompose()
    with pytest.raises(ValueError, match="Missing native candidate option"):
        REVIEW.review(changed(originals, soup))


@pytest.mark.parametrize("old,new", [
    (b">72,478<", b">72,479<"),
    (b">129,290<", b">129,291<"),
    (b">234,834<", b">134,834<"),
    (b"2026 General Election", b"2024 General Election"),
    (b"DEM BOB BROOKS", b"REP BOB BROOKS"),
])
def test_changed_candidate_ballot_election_or_party_fails(originals, old, new):
    assert old in originals["native-results.html"]
    raw = dict(originals)
    raw["native-results.html"] = raw["native-results.html"].replace(old, new, 1)
    with pytest.raises(ValueError):
        REVIEW.review(raw)


def test_duplicate_native_unit_fails(originals):
    soup = BeautifulSoup(originals["native-results.html"], "html.parser")
    unit = soup.select_one("#precinctListLayer > .list-item-precinct")
    unit.insert_after(BeautifulSoup(str(unit), "html.parser").select_one(".list-item-precinct"))
    with pytest.raises(ValueError, match="Duplicate or missing native unit"):
        REVIEW.review(changed(originals, soup))


def test_partial_districts_cannot_aggregate_more_candidates_than_county_ballots(originals):
    soup = BeautifulSoup(originals["native-results.html"], "html.parser")
    county = next(c for c in soup.select("#contestListLayer > .list-item")
                  if "14TH SENATORIAL" in c.select_one(".race-title").get_text())
    candidate = next(r for r in county.select("tr.content-row")
                     if "DEM NICK MILLER" in r.get_text())
    candidate.select_one('[data-votes="true"]').string = "20,299"
    unit = soup.select_one("#precinctListLayer > .list-item-precinct")
    fragment = next(c for c in unit.select(".list-item-precinct-race")
                    if "14TH SENATORIAL" in c.select_one(".race-title").get_text())
    candidate = next(r for r in fragment.select("tr.content-row")
                     if "DEM NICK MILLER" in r.get_text())
    candidate.select_one('[dv="true"]').string = "4,635"
    with pytest.raises(ValueError, match="Office candidate totals exceed county ballots"):
        REVIEW.review(changed(originals, soup))


@pytest.mark.parametrize("filename", ["official-index.html", "native-results.html"])
@pytest.mark.parametrize("family", ["google", "mapbox", "telemetry"])
def test_keys_fail_in_every_html_even_with_matching_receipts(tmp_path, filename, family):
    folder = tmp_path / "source"
    shutil.copytree(ORIGINALS, folder)
    key = {
        "google": b"AIza" + b"0" * 35,
        "mapbox": b"pk.synthetic-not-a-service-credential",
        "telemetry": b'instrumentationKey: "synthetic-not-a-service-credential"',
    }[family]
    path = folder / filename
    data = path.read_bytes() + b"\n<!-- " + key + b" -->\n"
    path.write_bytes(data)
    receipts = json.loads((folder / "receipts.json").read_bytes())
    receipt = next(r for r in receipts if r["file"] == filename)
    receipt.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    (folder / "receipts.json").write_text(json.dumps(receipts))
    with pytest.raises(ValueError, match="Unredacted public service key"):
        REVIEW.load_originals(folder)


def test_uninventoried_original_or_missing_screening_receipt_fails(tmp_path):
    folder = tmp_path / "source"
    shutil.copytree(ORIGINALS, folder)
    unexpected = folder / "extra.html"
    unexpected.write_text("<html></html>")
    with pytest.raises(ValueError, match="receipt inventory"):
        REVIEW.load_originals(folder)
    unexpected.unlink()
    receipts = json.loads((folder / "receipts.json").read_bytes())
    del receipts[0]["redaction"]
    (folder / "receipts.json").write_text(json.dumps(receipts))
    with pytest.raises(ValueError, match="screening receipt"):
        REVIEW.load_originals(folder)
