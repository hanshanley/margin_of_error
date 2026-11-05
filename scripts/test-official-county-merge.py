import csv
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
    (*merge.PACKAGES[0], 60481, 35157, 25190),
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
    fips, name, package = merge.PACKAGES[0]
    target = tmp_path / package
    shutil.copytree(ROOT / "data/county-source-reviews" / package, target)
    next((target / "originals").glob("*.html")).write_text("changed")
    with pytest.raises(ValueError, match="Changed"):
        merge.official_row(target, fips, name, REFERENCE)
    with pytest.raises(ValueError, match="identity"):
        merge.official_row(ROOT / "data/county-source-reviews" / package, "42017", name, REFERENCE)
