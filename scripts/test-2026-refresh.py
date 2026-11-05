import csv
import importlib.util
import io
from pathlib import Path

import pytest
import requests


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


uf, refresh = load("collect-uf-turnout"), load("refresh-2026-data")
ORIGINAL = ROOT / "data/uf-turnout/20261105-uf-01/originals/turnout.csv"


def test_catalog_discovers_numeric_latest_and_follows_declared_older_methodology():
    catalog = "".join('<a href="/dataset/2026-general-election-turnout-rates-v' + version + '/">data</a>'
                      for version in ["0-9", "0-2", "0-10"])
    url, version = uf.discover(catalog)
    assert version == "0.10"
    csv_url, doc_url = uf.downloads(
        '<a href="/data-downloads/turnoutdata/Turnout_2026G_v0.10.csv">data</a>'
        '<a href="/data-downloads/turnoutdata/Turnout_2026G_v0.1_doc.txt">docs</a>', url)
    assert csv_url.endswith("v0.10.csv") and doc_url.endswith("v0.1_doc.txt")
    with pytest.raises(ValueError, match="public"):
        uf.downloads('<a href="https://other.example/Turnout_2026G_v0.10.csv">data</a>', url)


def test_real_uf_rows_keep_estimates_explicit_zeros_and_missing_overseas():
    rows = {row["STATE_ABV"]: row for row in uf.parse(ORIGINAL.read_bytes())}
    assert set(rows) == uf.CODES
    assert all(row["ballots_status"] == "estimate" for row in rows.values())
    assert rows["CA"]["INELIGIBLE_PROBATION"] == 0
    assert rows["AL"]["ELIGIBLE_OVERSEAS"] is None
    assert rows["US"]["ELIGIBLE_OVERSEAS"] > 0
    assert rows["US"]["geographic_level"] == "national"
    assert rows["DC"]["geographic_level"] == "state"


@pytest.mark.parametrize("change", ["fractional_count", "inconsistent_rate", "missing_state", "duplicate_state"])
def test_changed_uf_schema_counts_rates_or_inventory_fail_closed(change):
    reader = csv.DictReader(io.StringIO(ORIGINAL.read_text()))
    rows = list(reader)
    if change == "fractional_count":
        rows[0]["TOTAL_BALLOTS_COUNTED"] = "1000.5"
    elif change == "inconsistent_rate":
        rows[0]["VEP_TURNOUT_RATE"] = "99.99%"
    elif change == "missing_state":
        rows.pop()
    else:
        rows.append(rows[0])
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    with pytest.raises(ValueError):
        uf.parse(out.getvalue().encode())


def test_failed_uf_capture_does_not_touch_last_good_pointer(tmp_path, monkeypatch):
    monkeypatch.setattr(refresh, "ROOT", tmp_path)
    pointer = tmp_path / "public/uf-turnout.json"
    pointer.parent.mkdir()
    pointer.write_bytes(b'{"data_directory":"old","base_url":"https://example.test/old/"}\n')
    before = pointer.read_bytes()

    def failed(*args, **kwargs):
        raise requests.ConnectionError("deliberately unavailable source")

    monkeypatch.setattr(uf.requests, "get", failed)
    monkeypatch.setattr(refresh, "load", lambda name: uf)
    with pytest.raises(requests.ConnectionError):
        refresh.refresh("uf", tmp_path / "attempt", "run", do_publish=True)
    assert pointer.read_bytes() == before


def test_county_refresh_cannot_replace_good_publication_with_partial_state_or_county_loss():
    old = dict(year=2026, boundary_reference_year=2026, coverage={"AL": {}, "ME": {}})
    rows = [dict(geography="01001"), dict(geography="23001")]
    with pytest.raises(ValueError, match="state"):
        refresh.validate_county_coverage(old, {**old, "coverage": {"AL": {}}}, rows, rows)
    with pytest.raises(ValueError, match="county"):
        refresh.validate_county_coverage(old, old, rows, rows[:1])
    with pytest.raises(ValueError, match="year"):
        refresh.validate_county_coverage(old, {**old, "boundary_reference_year": 2024}, rows, rows)
