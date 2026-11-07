import csv
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import shutil

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("official_merge", Path(__file__).with_name("merge-official-county-results.py"))
merge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge)
REFERENCE = merge.read(ROOT / "data/county-results/20261105-house-02/county-reference.json.gz")


@pytest.mark.parametrize("fips,name,package,total,dem,rep", [
    ("42089", "Monroe", "20261105-monroe-official-01", 60481, 35157, 25190),
    (*merge.PACKAGES[1], 302786, 158908, 142796),
    (*merge.PACKAGES[2], 389901, 268823, 120367),
])
def test_original_backed_house_vectors_preserve_all_literal_parties(fips, name, package, total, dem, rep):
    row = merge.official_row(ROOT / "data/county-source-reviews" / package, fips, name, REFERENCE)
    assert (row["total_votes"], row["democratic_votes"], row["republican_votes"]) == (total, dem, rep)
    assert row["margin_pp"] == 100*(dem-rep)/total
    assert sum(c["votes"] for f in row["district_fragments"] for c in f["candidates"]) == total
    assert "ballots" not in row and "registered_voters" not in row
    if name == "Montgomery":
        assert sum(c["votes"] for f in row["district_fragments"] for c in f["candidates"] if c["party"] == "") == 711


@pytest.mark.parametrize("change", ["wrong_year", "wrong_fips", "duplicate", "fractional", "party", "missing_district"])
def test_changed_county_identity_inventory_or_votes_fail_closed(tmp_path, change):
    fips, name, package = merge.PACKAGES[2]
    target = tmp_path / package
    shutil.copytree(ROOT / "data/county-source-reviews" / package, target)
    path = target / "county-candidate-results.csv"
    with path.open() as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    selected = next(r for r in rows if r["office"] == "us_house")
    if change == "wrong_year":
        selected["year"] = "2024"
    elif change == "wrong_fips":
        selected["county_fips"] = "42017"
    elif change == "duplicate":
        rows.append(dict(selected))
    elif change == "fractional":
        selected["votes"] = "29179.5"
    elif change == "party":
        selected["party_literal"] = "Democrat"
    else:
        rows = [r for r in rows if r.get("contest") != selected["contest"]]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    inventory = merge.read(target / "checksums.json")
    inventory[path.name] = merge.checksum(path)
    merge.write(target / "checksums.json", inventory)
    with pytest.raises(ValueError):
        merge.official_row(target, fips, name, REFERENCE)


def test_unreceipted_original_changes_and_wrong_census_identity_are_rejected(tmp_path):
    fips, name, package = "42089", "Monroe", "20261105-monroe-official-01"
    target = tmp_path / package
    shutil.copytree(ROOT / "data/county-source-reviews" / package, target)
    next((target / "originals").glob("*.html")).write_text("changed")
    with pytest.raises(ValueError, match="Changed"):
        merge.official_row(target, fips, name, REFERENCE)
    with pytest.raises(ValueError, match="identity"):
        merge.official_row(ROOT / "data/county-source-reviews" / package, "42017", name, REFERENCE)


def test_current_monroe_preserves_blank_party_and_both_district_vectors():
    fips, name, package = merge.PACKAGES[0]
    row = merge.official_row(ROOT / "data/county-source-reviews" / package, fips, name, REFERENCE)
    assert (row["democratic_votes"], row["republican_votes"], row["other_votes"], row["total_votes"]) == (
        35619, 25343, 134, 61096)
    assert [(part["district"], [candidate["votes"] for candidate in part["candidates"]])
            for part in row["district_fragments"]] == [
                ("PA-07", [2052, 3162, 16]), ("PA-08", [33567, 22181, 118])]
    assert {candidate["party"] for part in row["district_fragments"]
            for candidate in part["candidates"]} == {"DEMOCRATIC", "REPUBLICAN", ""}
    assert "ballots" not in row and "registered_voters" not in row


@pytest.mark.parametrize("change", ["csv_vector", "audit_clock", "native_facts"])
def test_selected_monroe_rejects_rechecksummed_changes(tmp_path, change):
    fips, name, package = merge.PACKAGES[0]
    target = tmp_path / package
    shutil.copytree(ROOT / "data/county-source-reviews" / package, target)
    if change == "csv_vector":
        path = target / "county-candidate-results.csv"
        with path.open() as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        rows[0]["votes"], rows[1]["votes"] = rows[1]["votes"], rows[0]["votes"]
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    else:
        path = target / ("audit.json" if change == "audit_clock" else "selected-source-facts.json")
        value = merge.read(path)
        if change == "audit_clock":
            value["source_update_literal"] = "11/3/2026 9:19:27 PM"
        else:
            value["participation"]["total_ballots_tabulated"] += 1
        merge.write(path, value)
    inventory = merge.read(target / "checksums.json")
    inventory[path.name] = merge.checksum(path)
    merge.write(target / "checksums.json", inventory)
    with pytest.raises(ValueError, match="pinned native facts|Changed selected source facts"):
        merge.official_row(target, fips, name, REFERENCE)


def overlap_snapshot():
    official = [merge.official_row(ROOT / "data/county-source-reviews" / package, fips, name, REFERENCE)
                for fips, name, package in merge.PACKAGES]
    rows = {key: dict(state_code="PA", geography=key)
            for key, row in REFERENCE.items() if row["STATEFP"] == "42"}
    for row in copy.deepcopy(official):
        row.pop("source_kind")
        for fragment in row["district_fragments"]:
            fragment["candidates"] = [c for c in fragment["candidates"]
                                      if c["party"] in {"DEMOCRATIC", "REPUBLICAN", "Dem", "Rep", "DEM", "REP"}]
        row["other_votes"] = 0
        row["total_votes"] = row["democratic_votes"] + row["republican_votes"]
        rows[row["geography"]] = row
    return {"coverage": {"PA": {"counties": 67}}}, list(rows.values()), official


def test_full_provider_coverage_retains_official_writeins_without_duplicate_majors():
    index, rows, official = overlap_snapshot()
    result = merge.review_provider_overlap(index, rows, official, REFERENCE)
    assert set(result) == {"42089", "42017", "42091"}
    assert sum(row["official_other_votes_retained"] for row in result.values()) == 1927
    assert all(row["provider_row"]["other_votes"] == 0 for row in result.values())


@pytest.mark.parametrize("change", ["partial", "duplicate_county", "district_mismatch", "county_mismatch",
                                   "provider_other_votes", "already_merged"])
def test_overlap_never_waives_incomplete_coverage_or_disagreeing_vectors(change):
    index, rows, official = overlap_snapshot()
    target = next(row for row in rows if row["geography"] == "42091")
    if change == "partial":
        rows.pop()
    elif change == "duplicate_county":
        rows.append(rows[0])
    elif change == "district_mismatch":
        candidates = target["district_fragments"][0]["candidates"]
        candidates[0]["votes"] += 1
        candidates[1]["votes"] -= 1
    elif change == "county_mismatch":
        target["democratic_votes"] += 1
    elif change == "provider_other_votes":
        target["other_votes"] = 1
    else:
        index["official_supplement"] = {"counties": ["42091"]}
    with pytest.raises(ValueError, match="requires explicit review|require explicit review"):
        merge.review_provider_overlap(index, rows, official, REFERENCE)


def test_replacing_county_party_rows_never_appends_duplicate_provider_counts(tmp_path):
    target = tmp_path / "county-party-totals.csv.gz"
    with gzip.open(target, "wt", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["county_fips", "party", "votes"])
        writer.writeheader()
        writer.writerows([dict(county_fips="42091", party="Democratic", votes=268823),
                         dict(county_fips="42011", party="Write-in", votes=0)])
    additions = [dict(county_fips="42091", party="DEM", votes=268823),
                 dict(county_fips="42091", party="", votes=711)]
    assert merge.csv_append(target, additions, {"42091"}) == 3
    with gzip.open(target, "rt") as stream:
        rows = list(csv.DictReader(stream))
    assert [row for row in rows if row["county_fips"] == "42091"] == [
        {k: str(v) for k, v in row.items()} for row in additions]
    assert next(row for row in rows if row["county_fips"] == "42011")["votes"] == "0"
