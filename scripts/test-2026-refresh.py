import csv
import gzip
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


def test_unchanged_data_is_not_republished_for_platform_only_gzip_header_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(refresh, "ROOT", tmp_path)
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    (old / "parties").mkdir()
    (new / "party-votes").mkdir(parents=True)
    raw = gzip.compress(b"original rows\n", mtime=0)
    other_platform = bytearray(raw)
    other_platform[9] = 3 if raw[9] != 3 else 255
    (old / "county-results.json.gz").write_bytes(raw)
    (new / "county-results.json.gz").write_bytes(other_platform)
    for folder in (old / "parties", new / "party-votes"):
        refresh.write(folder / "audit.json", {"files": {"county-party-totals.csv.gz": {}}})
    (old / "parties/county-party-totals.csv.gz").write_bytes(raw)
    (new / "party-votes/county-party-totals.csv.gz").write_bytes(other_platform)
    previous = {"data_directory": "old", "party_votes": {"data_directory": "old/parties"}}
    assert refresh.unchanged("county", new, previous)
    (new / "party-votes/county-party-totals.csv.gz").write_bytes(gzip.compress(b"changed votes\n", mtime=0))
    assert not refresh.unchanged("county", new, previous)


def test_pa_ledger_tracks_expanded_map_without_changing_history_or_claiming_final_counts(tmp_path):
    ledger = tmp_path / "coverage.csv"
    ledger.write_text(
        "year,office,state_code,source_counties,arithmetic_matched_counties,integer_accepted_counties,county_candidate_maps,fully_complete\n"
        "2026,house,PA,3,3,3,3,False\n"
        "2024,house,PA,67,67,67,67,False\n"
        "2026,house,ME,0,0,0,0,False\n")
    refresh.update_pa_coverage_ledger({"coverage": {"PA": {"counties": 67}}}, ledger)
    with ledger.open() as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["county_candidate_maps"] == rows[0]["integer_accepted_counties"] == "67"
    assert rows[0]["fully_complete"] == "False"
    assert rows[1]["county_candidate_maps"] == "67"
    assert rows[2]["county_candidate_maps"] == "0"


def test_changed_release_bytes_remain_draft_and_never_update_pointers(tmp_path, monkeypatch):
    archive = tmp_path / "complete.zip"
    archive.write_bytes(b"reviewed complete source bytes")
    calls = []

    def command(*args, **kwargs):
        calls.append(args)
        if args[:3] == ("gh", "release", "download"):
            Path(args[args.index("--output") + 1]).write_bytes(b"changed download")

    monkeypatch.setattr(refresh, "command", command)
    with pytest.raises(ValueError, match="differs"):
        refresh.publish("county", tmp_path, archive, tmp_path, "test-run", {})
    assert "--draft" in calls[0]
    assert not any(args[:3] == ("gh", "release", "edit") for args in calls)
    assert not any(args[0] == "git" for args in calls)


def test_source_credentials_stop_refresh_before_any_release_operation(tmp_path, monkeypatch):
    (tmp_path / "source.json").write_bytes(b'{"copied_key":"' + b"AI" + b"za" + b"A" * 35 + b'"}')
    calls = []
    monkeypatch.setattr(refresh, "command", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(ValueError, match="credential pattern"):
        refresh.publish("county", tmp_path, tmp_path / "complete.zip", tmp_path, "test-run", {})
    assert calls == []
