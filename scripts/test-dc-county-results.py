import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dc_results", ROOT / "scripts/review-dc-2026-county-results.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SOURCE = ROOT / "data/county-source-reviews/20261105-dc-official-01/originals"


@pytest.fixture
def raw():
    return module.load_originals(SOURCE)


def replace_csv(raw, mutate):
    rows = list(csv.DictReader(io.StringIO(raw["report.csv"].decode("utf-8-sig"))))
    mutate(rows)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=module.HEADERS)
    writer.writeheader()
    writer.writerows(rows)
    raw["report.csv"] = output.getvalue().encode()


def test_native_counts_preserve_accounting_and_missing_rcv_status(raw):
    tables, audit = module.review(raw)
    assert audit["native_csv_rows"] == 10011
    assert audit["xml_summary_rows"] == 1478
    assert audit["accounting_party_literal_disagreements"] == 722
    assert audit["delegate_literal_party_totals"] == {
        "DEM": 157979, "NPN": 1142, "REP": 11583, "STG": 10275}
    assert audit["participation"]["unresolved_ballot_accounting_difference"] == 324
    assert audit["participation"]["ballots_cast"] == 185086
    assert audit["participation"]["registered_voters"] == 457371
    assert not audit["final_rcv_round_verified"]
    assert not audit["new_maps_approved"]
    accounting = tables["county-delegate-ballot-accounting.csv"]
    assert {r["party_csv_literal"] for r in accounting} == {""}
    assert {r["party_json_literal"] for r in accounting} == {"REP"}
    assert audit["native_csv_zero_rows"] == 1235
    assert sum(r["Votes"] == "0" for r in tables["native-unit-delegate-counts.csv"]) == 13
    assert not audit["participation"]["early_ballot_total_established"]


@pytest.mark.parametrize("value", ["", "-1", "1.5", "1e2"])
def test_missing_negative_or_fractional_native_votes_rejected(raw, value):
    replace_csv(raw, lambda rows: rows[2].update(Votes=value))
    with pytest.raises(ValueError, match="integer"):
        module.review(raw)


def test_duplicate_native_row_rejected(raw):
    replace_csv(raw, lambda rows: rows.append(dict(rows[2])))
    with pytest.raises(ValueError, match="Duplicate native"):
        module.review(raw)


def test_missing_zero_option_rejected_even_when_sums_match(raw):
    replace_csv(raw, lambda rows: rows.remove(next(
        r for r in rows if r["ContestNumber"] == "4" and r["Votes"] == "0")))
    with pytest.raises(ValueError, match="Missing delegate option"):
        module.review(raw)


def test_changed_candidate_party_rejected(raw):
    replace_csv(raw, lambda rows: [r.update(Party="OTHER") for r in rows
                                  if r["ContestNumber"] == "4" and r["Candidate"] == "Write-in"])
    with pytest.raises(ValueError, match="party disagreement"):
        module.review(raw)


def test_unreconciled_xml_rejected(raw):
    raw["report.xml"] = raw["report.xml"].replace(b"<Votes>11583</Votes>", b"<Votes>11584</Votes>", 1)
    with pytest.raises(ValueError, match="XML summary"):
        module.review(raw)


def test_citywide_vote_disagreement_rejected(raw):
    data = json.loads(raw["citywide.json"])
    data[0]["ElectionData"][0]["Votes"] += 1
    raw["citywide.json"] = json.dumps(data).encode()
    with pytest.raises(ValueError, match="city JSON"):
        module.review(raw)


@pytest.mark.parametrize("field,value", [
    ("ElectionDate", "2024-11-05T00:00:00"),
    ("ElectionResultsTypeName", "Testing in Progress"),
])
def test_wrong_election_or_test_data_rejected(raw, field, value):
    data = json.loads(raw["election.json"])
    data[field] = value
    raw["election.json"] = json.dumps(data).encode()
    with pytest.raises(ValueError, match="Wrong election"):
        module.review(raw)


def test_city_participation_mismatch_rejected(raw):
    data = json.loads(raw["voters.json"])
    data["TotalBallotsCast"] += 1
    raw["voters.json"] = json.dumps(data).encode()
    with pytest.raises(ValueError, match="city summary"):
        module.review(raw)


def test_changed_original_bytes_rejected(tmp_path):
    import shutil
    shutil.copytree(SOURCE, tmp_path / "source")
    (tmp_path / "source/report.csv").write_bytes(b"changed")
    with pytest.raises(ValueError, match="acquisition receipt"):
        module.load_originals(tmp_path / "source")
