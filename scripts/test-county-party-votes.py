import copy
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest


spec = importlib.util.spec_from_file_location("party_exports", Path(__file__).with_name("export-county-party-votes.py"))
exports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exports)


def fixture():
    candidates = [dict(name="Jordan", party="Democratic", votes=10),
                  dict(name="Jordan", party="Working Families", votes=2),
                  dict(name="Lee", party="Republican", votes=8),
                  dict(name="Green", party="Green", votes=0)]
    source = dict(district="AL-01", source_key="county",
                  source_url="https://example.test/1", source_updated_at="2026-11-05",
                  candidates=candidates)
    counties = [dict(year=2026, state_code="AL", geography="01001",
                     geography_name="Autauga County", total_votes=20, district_fragments=[source])]
    district = copy.deepcopy(source)
    district["candidates"][2]["votes"] += 2
    district["candidates"][3]["votes"] += 1
    district["state_code"] = "AL"
    missing = dict(district="ME-01", state_code="ME", source_url="https://example.test/2",
                   source_updated_at="2026-11-05",
                   candidates=[dict(name="Independent", party="Independent", votes=12)])
    return counties, [district, missing]


def test_literal_fusion_lines_explicit_zero_and_unlocated_votes_are_preserved():
    counties, districts = fixture()
    tables = exports.party_tables(counties, districts)
    county = {row["party"]: row["votes"] for row in tables["county-party-totals.csv.gz"]}
    assert county == {"Democratic": 10, "Working Families": 2, "Republican": 8, "Green": 0}
    assert "Independent" not in county
    candidates = tables["county-district-candidate-totals.csv.gz"]
    assert [(row["name"], row["party"], row["votes"]) for row in candidates[:2]] == [
        ("Jordan", "Democratic", 10), ("Jordan", "Working Families", 2)]
    state = {(row["state_code"], row["party"]): row for row in tables["state-party-totals.csv.gz"]}
    assert state["AL", "Republican"]["unlocated_votes"] == 2
    assert state["AL", "Green"]["unlocated_votes"] == 1
    assert state["ME", "Independent"]["votes"] == 12
    assert state["ME", "Independent"]["located_county_votes"] is None
    assert state["ME", "Independent"]["unlocated_votes"] is None


def test_changed_county_totals_and_missing_native_votes_fail_closed():
    counties, districts = fixture()
    counties[0]["total_votes"] += 1
    with pytest.raises(ValueError, match="reconcile"):
        exports.party_tables(counties, districts)
    counties, districts = fixture()
    counties[0]["district_fragments"][0]["candidates"][0]["votes"] = None
    with pytest.raises(ValueError, match="explicit"):
        exports.party_tables(counties, districts)


def test_county_party_votes_cannot_exceed_their_actual_district_source():
    counties, districts = fixture()
    districts[0]["candidates"][0]["votes"] = 9
    with pytest.raises(ValueError, match="exceed"):
        exports.party_tables(counties, districts)


def test_original_backed_archive_reproduces_without_repo_and_withholds_test_data(tmp_path):
    source = Path(__file__).resolve().parents[1] / "data/county-results/20261105-house-02"
    archive_path = tmp_path / "complete.zip"
    audit = exports.export(source, tmp_path / "tables", archive_path)
    assert audit["withheld_states"] == ["PA"]
    assert all(key.startswith("pa-") for key in audit["excluded_districts"])
    with gzip.open(tmp_path / "tables/state-party-totals.csv.gz", "rt") as file:
        import csv
        rows = list(csv.DictReader(file))
    assert "PA" not in {row["state_code"] for row in rows}
    assert all(row["located_county_votes"] == "" for row in rows if row["state_code"] == "ME")
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        archive.extractall(extracted)
    subprocess.run([sys.executable, "export-county-party-votes.py",
                    "--source", "source/" + source.name, "--output", "reproduced"],
                   cwd=extracted, check=True, capture_output=True)
    for name in audit["files"]:
        assert (extracted / "reproduced" / name).read_bytes() == (tmp_path / "tables" / name).read_bytes()
    assert json.loads((extracted / "reproduced/audit.json").read_text()) == audit
