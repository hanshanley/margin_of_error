import importlib.util
import hashlib
import json
from pathlib import Path
import shutil

from bs4 import BeautifulSoup
import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pa_vendor_review", ROOT / "scripts/review-pa-vendor-county-results.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)
ORIGINALS = ROOT / "data/county-source-reviews/20261105-pa-three-county-01/originals"


@pytest.fixture(scope="module")
def originals():
    return {name: REVIEW.load_originals(ORIGINALS / name.lower(), name) for name in REVIEW.COUNTIES}


def test_complete_native_counts_and_different_ballot_semantics(originals):
    expected = {
        "Chester": (243680, 392304, 243140, {"DEM": 158099, "REP": 84746, "NON": 295}),
        "Franklin": (57533, 105937, 57332, {"DEM": 19005, "REP": 38255, "NON": 72}),
        "Lehigh": (137656, 256728, 136607, {"DEM": 80201, "REP": 56078, "NON": 328}),
    }
    for county, raw in originals.items():
        tables, audit = REVIEW.review(county, raw)
        ballots, registered, house, parties = expected[county]
        row = tables["county-participation.csv"][0]
        assert (row["ballots_counted"], row["registered_voters"], row["house_candidate_votes"]) == (
            ballots, registered, house)
        assert {r["party_literal"]: r["votes"] for r in tables["county-office-party-totals.csv"]
                if r["office"] == "us_house"} == parties
        assert not any(r["office"] == "ballot_question" for r in tables["county-office-party-totals.csv"])
        assert sum(r["native_votes_cast"] for r in tables["native-unit-participation.csv"]) == ballots
        assert len(audit["native_csv_ballot_count_conflicts"]) == (15 if county == "Chester" else 0)
        assert not row["final_certified_turnout"] and not audit["maps_approved"]
        assert not audit["fully_complete"] and not audit["demographic_turnout_approved"]
        assert audit["house_district_number_in_native_title"] == (county != "Franklin")
    _, lehigh = REVIEW.review("Lehigh", originals["Lehigh"])
    assert "Mail Ballots: Partially Reported" in lehigh["participation"]["counting_qualifications_json"]


def test_native_under_overvotes_are_not_unclassified_or_invented(originals):
    for county, expected in {
        "Chester": (540, None, None, 540),
        "Franklin": (201, 195, 6, 0),
        "Lehigh": (1049, 1003, None, 46),
    }.items():
        tables, _ = REVIEW.review(county, originals[county])
        house = next(row for row in tables["county-contest-totals.csv"] if row["office"] == "us_house")
        assert tuple(house[field] for field in [
            "ballots_minus_candidate_or_option_votes", "native_under_votes", "native_over_votes",
            "ballots_minus_votes_unclassified"]) == expected


@pytest.mark.parametrize("old,new", [
    (b'"158099"', b'""'), (b'"158099"', b'"-1"'), (b'"158099"', b'"158099.5"'),
    (b'"50558"', b'"50559"'), (b'"DEM Chrissy Houlahan","DEM"', b'"DEM Chrissy Houlahan","REP"'),
])
def test_bad_candidate_counts_modes_or_parties_fail(originals, old, new):
    raw = dict(originals["Chester"])
    assert old in raw["summary.csv"]
    raw["summary.csv"] = raw["summary.csv"].replace(old, new, 1)
    with pytest.raises(ValueError):
        REVIEW.review("Chester", raw)


def test_missing_explicit_unit_zero_fails_without_changing_any_sum(originals):
    raw = dict(originals["Lehigh"])
    soup = BeautifulSoup(raw["native-results.redacted.html"], "html.parser")
    zero = next(row for row in soup.select("#precinctListLayer tr.content-row")
                if row.select_one('[dv="true"]').get_text(strip=True) == "0")
    zero.decompose()
    raw["native-results.redacted.html"] = str(soup).encode()
    with pytest.raises(ValueError, match="Missing native candidate option"):
        REVIEW.review("Lehigh", raw)


@pytest.mark.parametrize("old,new", [
    (b"2026 General Election", b"2024 General Election"),
    (b">243,680<", b">243,681<"),
])
def test_wrong_election_test_data_or_ballots_fail(originals, old, new):
    raw = dict(originals["Chester"])
    assert old in raw["native-results.redacted.html"]
    raw["native-results.redacted.html"] = raw["native-results.redacted.html"].replace(old, new, 1)
    with pytest.raises(ValueError):
        REVIEW.review("Chester", raw)


def test_source_test_label_fails(originals):
    raw = dict(originals["Chester"])
    soup = BeautifulSoup(raw["native-results.redacted.html"], "html.parser")
    soup.select_one("#lblOfficialResults").string = "Testing in Progress"
    raw["native-results.redacted.html"] = str(soup).encode()
    with pytest.raises(ValueError, match="publication status"):
        REVIEW.review("Chester", raw)


def test_changed_original_or_undeclared_file_fails(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(ORIGINALS / "chester", source)
    (source / "unexpected.json").write_text("{}")
    with pytest.raises(ValueError, match="receipt inventory"):
        REVIEW.load_originals(source, "Chester")
    (source / "unexpected.json").unlink()
    with (source / "summary.csv").open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(ValueError, match="acquisition receipt"):
        REVIEW.load_originals(source, "Chester")


def test_redacted_snapshot_keeps_its_original_receipt(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(ORIGINALS / "franklin", source)
    receipts = json.loads((source / "receipts.json").read_bytes())
    del next(r for r in receipts if r["file"] == "native-results.redacted.html")["redaction"]
    (source / "receipts.json").write_text(json.dumps(receipts))
    with pytest.raises(ValueError, match="explicit redaction"):
        REVIEW.load_originals(source, "Franklin")


@pytest.mark.parametrize("filename", ["official-results-index.html", "native-results.redacted.html"])
@pytest.mark.parametrize("family", ["google", "mapbox", "telemetry"])
def test_service_keys_fail_in_every_html_even_with_matching_receipts(tmp_path, filename, family):
    source = tmp_path / "source"
    shutil.copytree(ORIGINALS / "chester", source)
    path = source / filename
    key = {
        "google": b"AIza" + b"0" * 35,
        "mapbox": b"pk." + b"synthetic-not-a-service-credential",
        "telemetry": b'instrumentationKey: "synthetic-not-a-service-credential"',
    }[family]
    data = path.read_bytes() + b"\n<!-- " + key + b" -->\n"
    path.write_bytes(data)
    receipts = json.loads((source / "receipts.json").read_bytes())
    receipt = next(row for row in receipts if row["file"] == filename)
    receipt.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    (source / "receipts.json").write_text(json.dumps(receipts))
    with pytest.raises(ValueError, match="Unredacted public service key"):
        REVIEW.load_originals(source, "Chester")
