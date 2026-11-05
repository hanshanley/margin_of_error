import csv
import importlib.util
import io
import hashlib
import json
from pathlib import Path

import openpyxl
import pytest


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


methods = module("collect-voting-methods")
context = module("collect-participation-context")
local = module("build-local-participation")
current_local = module("collect-current-participation")
current_precincts = module("build-current-precincts")
precinct_results = module("build-precinct-results")
precinct_coverage = module("build-precinct-coverage")
additional_precincts = module("build-additional-precinct-results")
historical_sources = module("acquire-historical-precinct-sources")


def test_historical_source_acquisition_requires_exact_reviewed_bytes_without_inventing_turnout():
    raw = b"county,precinct,office,candidate,votes\nExample,1,House,A,10\nExample,2,House,B,*\n"
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    audit = historical_sources.inspect_csv(raw, blob)
    assert audit["rows"] == 2 and audit["malformed_rows"] == 0
    assert "turnout" not in audit
    modes = b"county,precinct,office,candidate,election_day_votes,advanced_votes\nExample,1,House,A,10,5\n"
    mode_blob = hashlib.sha1(b"blob " + str(len(modes)).encode() + b"\0" + modes).hexdigest()
    assert historical_sources.inspect_csv(modes, mode_blob)["rows"] == 1
    with pytest.raises(ValueError, match="changed"):
        historical_sources.inspect_csv(raw + b"\n", blob)


def test_original_source_downloads_do_not_claim_validated_maps_or_participation():
    batch = dict(year=2022, complete_download_url="full.zip", states={
        "AZ": dict(source_url="immutable.csv", rows=100, next_action="Reconcile and obtain boundaries")})
    row = next(r for r in precinct_coverage.build_rows(source_batches=[batch])
               if r["year"] == 2022 and r["state_code"] == "AZ")
    assert row["candidate_results"] == "acquired_originals_review_pending"
    assert row["join"] == "pending" and row["complete"] == "no"
    assert row["publication"] == "full_originals_download_only"
    assert row["participation"] == "not_acquired"


def test_historical_acquisition_never_produces_a_metadata_only_archive(tmp_path, monkeypatch):
    (tmp_path / "public").mkdir()
    (tmp_path / "public/precinct-source-inventory.json").write_text(json.dumps({
        "states": {"AZ": {"elections": {"1964": []}}}}))
    monkeypatch.setattr(historical_sources, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["acquire", "--year", "1964", "--output", str(tmp_path / "data"),
                                   "--archive", str(tmp_path / "empty.zip")])
    with pytest.raises(ValueError, match="metadata-only"):
        historical_sources.main()
    assert not (tmp_path / "empty.zip").exists()


def mn_fixture():
    precincts, counties, statewide, table = [], [], [], {}
    for district in range(1, 9):
        precinct = str(district).zfill(4)
        table[("01", precinct)] = ["01", precinct, "Precinct " + precinct, str(district)]
        for candidate, party, votes in [("0401", "DFL", 70), ("0302", "R", 30)]:
            row = dict(county="", precinct="", district=str(district), candidate=candidate,
                       name=party, party=party, reported=1, units=1, votes=votes, total=100)
            statewide.append(row)
            counties.append(dict(row, county="01"))
            precincts.append(dict(row, county="01", precinct=precinct))
    return precincts, counties, statewide, {"01": "Example"}, table


def test_mn_precinct_candidates_require_all_three_reporting_levels_to_reconcile():
    args = mn_fixture()
    rows = additional_precincts.mn_results(*args)
    assert len(rows) == 8 and all(r["margin_pp"] == 40 for r in rows)
    assert rows[0]["key"] == "MN|01|0001"
    args[1][0]["votes"] -= 1
    with pytest.raises(ValueError, match="do not reconcile"):
        additional_precincts.mn_results(*args)


def test_mn_candidates_reject_missing_candidates_and_incorrect_geographies():
    args = mn_fixture()
    args[0][0]["party"] = "UNKNOWN"
    with pytest.raises(ValueError, match="candidate/party"):
        additional_precincts.mn_results(*args)
    row = "MN;01;0001;0104;U.S. Representative District 1;1;0401;Example;;;DFL;1;1;70;70;100"
    with pytest.raises(ValueError, match="Duplicate"):
        additional_precincts.mn_candidate_rows(row + "\n" + row, "precinct")
    with pytest.raises(ValueError, match="geography"):
        additional_precincts.mn_candidate_rows(row, "county")
    with pytest.raises(ValueError, match="House contest"):
        additional_precincts.mn_candidate_rows(row.replace("0104", "0105"), "precinct")


def test_mn_participation_is_not_candidate_votes_and_checks_ballot_modes():
    *_, names, table = mn_fixture()
    row = "MN;01;0001;Precinct 0001;1;100;10;50;20;0;0;70"
    parsed = additional_precincts.mn_participation(row, names, table)[0]
    assert parsed["denominator"] == 110 and parsed["ballots"] == 70
    assert parsed["reported_pct"] == pytest.approx(100 * 70 / 110)
    assert additional_precincts.mn_participation(row.replace(";1;100;10;", ";0;100;10;"), names, table)[0]["reported_pct"] is None
    inconsistent = additional_precincts.mn_participation(row[:-2] + "71", names, table)[0]
    assert inconsistent["ballots"] == 71 and inconsistent["reported_pct"] is None
    assert not inconsistent["ballot_modes_reconciled"]
    missing = additional_precincts.mn_participation(row.replace(";100;", ";*;"), names, table)[0]
    assert missing["registered_at_open"] is None and missing["reported_pct"] is None
    with pytest.raises(ValueError, match="duplicate"):
        additional_precincts.mn_participation(row + "\n" + row, names, table)


def test_original_2020_results_keep_actual_year_and_boundary_uncertainty():
    feature = {"properties": {"GEOID": "06001-1", "votes_dem": 30, "votes_rep": 10, "votes_total": 50}}
    row = additional_precincts.nyt_result(feature, {"06": "CA"})
    assert row["year"] == 2020 and row["other_votes"] == 10 and row["margin_pp"] == 40
    assert "no per-shape official flag" in row["boundary_provenance"]
    feature["properties"]["votes_total"] = 39
    with pytest.raises(ValueError, match="candidate totals"):
        additional_precincts.nyt_result(feature, {"06": "CA"})
    feature["properties"].update(votes_total=None, votes_dem=None, votes_rep=None)
    missing = additional_precincts.nyt_result(feature, {"06": "CA"})
    assert missing["contest_votes"] is None and missing["margin_pp"] is None
    assert missing["democratic_votes"] is None and missing["other_votes"] is None


def test_precinct_worklist_covers_every_state_and_year_newest_first():
    rows = precinct_coverage.build_rows()
    assert len(rows) == len({(r["state_code"], r["year"]) for r in rows}) == 1632
    assert list(dict.fromkeys(r["year"] for r in rows)) == list(range(2026, 1963, -2))
    for year in range(1964, 2027, 2):
        assert len({r["state_code"] for r in rows if r["year"] == year}) == 51
    assert all(r["complete"] == "no" for r in rows)
    assert next(r for r in rows if r["state_code"] == "AK" and r["year"] == 2024)["candidate_results"] == "absent_from_reviewed_release"


def test_nm_precinct_results_reconcile_and_never_treat_suppression_as_zero():
    candidates = [dict(RaceID=11186, OfficeSeqNo="190", CountyName="Example", PrecinctName="PCT 001",
                       CandidateID=party, PartyCode=party, calcCandidateVotes=votes)
                  for party, votes in [("DEM", "12"), ("REP", "8")]]
    counties = [dict(row) for row in candidates]
    rows = precinct_results.nm_results(candidates, counties)
    assert rows[0]["margin_pp"] == 20
    assert rows[0]["county_reconciled"]
    candidates[0]["calcCandidateVotes"] = "*"
    rows = precinct_results.nm_results(candidates, counties)
    assert rows[0]["democratic_votes"] is None
    assert rows[0]["contest_votes"] is None and rows[0]["margin_pp"] is None
    assert not rows[0]["county_reconciled"]
    candidates[0]["calcCandidateVotes"] = "11"
    with pytest.raises(ValueError, match="do not reconcile"):
        precinct_results.nm_results(candidates, counties)
    with pytest.raises(ValueError, match="Duplicate"):
        precinct_results.nm_results(candidates + candidates, counties)


def test_precinct_worklist_requires_live_verification_and_never_marks_partial_complete():
    coverage = dict(partial=True, source_url="source", next_action="Verify remaining precincts",
                    notes="Residential ballots only")
    index = {"coverage": {"2026": {"NC": coverage}}}
    for published, expected in [(False, "snapshot_ready"), (True, "published_partial")]:
        rows = precinct_coverage.build_rows(index, published=published)
        nc = next(row for row in rows if row["year"] == 2026 and row["state_code"] == "NC")
        nm = next(row for row in rows if row["year"] == 2026 and row["state_code"] == "NM")
        de = next(row for row in rows if row["year"] == 2026 and row["state_code"] == "DE")
        assert nc["publication"] == expected
        assert nc["join"] == "validated_partial" and nc["complete"] == "no"
        assert nm["publication"] == "not_published"
        assert de["candidate_results"] == "acquired_reconciled" and de["join"] == "withheld"
        assert de["publication"] == "full_counts_download_only" and de["complete"] == "no"
    index["coverage"]["2026"]["MN"] = dict(coverage, live_verified=False)
    rows = precinct_coverage.build_rows(index, published=True)
    mn = next(row for row in rows if row["year"] == 2026 and row["state_code"] == "MN")
    assert mn["publication"] == "snapshot_ready"
    assert mn["participation"] == "acquired_precinct_counts_and_registration"


def test_precinct_join_withholds_whole_mismatched_or_unreconciled_counties():
    def shape(county, precinct):
        return {"properties": {"county": county, "precinct": precinct}}
    features = [shape("Matched", "1"), shape("Mismatch", "1"), shape("Mismatch", "2"),
                shape("Suppressed", "1")]
    rows = [dict(county=county, precinct="1", reporting_unit_kind="precinct",
                 county_reconciled=county != "Suppressed", margin_pp=20)
            for county in ["Matched", "Mismatch", "Suppressed"]]
    audit = precinct_results.join_counties(features, rows)
    assert sum(row["colored_precincts"] for row in audit) == 1
    assert features[0]["properties"]["match_status"] == "matched"
    assert all(f["properties"]["match_status"] != "matched" for f in features[1:])
    assert all("margin_pp" not in f["properties"] for f in features[1:])


def test_de_results_reconcile_every_candidate_and_ballot_mode_before_geometry():
    source = [dict(zip(["Contest Title", "Election Id", "Election District", "Candidate Name",
                       "Party Name", "Machine Votes", "Absentee Votes", "Early Voting Votes", "Total Votes"],
                      ["Representative In Congress", "GE2026", "Election District 01-01",
                       party, party, "5", "2", "3", "10"]))
              for party in ["Democratic Party", "Republican Party"]]
    statewide = [dict(row, **{"Election Date": "2026-11-03"}) for row in source]
    rows = precinct_results.de_results(source, statewide)
    assert len(rows) == 1 and rows[0]["precinct"] == "01-01" and rows[0]["contest_votes"] == 20
    with pytest.raises(ValueError, match="ballot modes"):
        precinct_results.de_results([dict(source[0], **{"Total Votes": "11"}), source[1]], statewide)
    with pytest.raises(ValueError, match="Duplicate"):
        precinct_results.de_results(source + source, statewide)
    with pytest.raises(ValueError, match="precinct/state"):
        precinct_results.de_results(source[:1], statewide)


def test_nc_results_keep_nonresidential_votes_separate_and_check_ballot_modes():
    base = dict(zip(["County", "Precinct", "Contest Name", "Choice", "Choice Party",
                     "Election Date", "Real Precinct", "Election Day", "Early Voting",
                     "Absentee by Mail", "Provisional", "Total Votes"],
                    ["WAKE", "01-01", "US HOUSE OF REPRESENTATIVES DISTRICT 02", "Candidate",
                     "DEM", "11/03/2026", "Y", "10", "0", "0", "0", "10"]))
    administrative = dict(base, Precinct="EARLY SITE", **{"Real Precinct": "N", "Election Day": "0", "Early Voting": "10"})
    rows = precinct_results.nc_results([base, administrative])
    assert [r["reporting_unit_kind"] for r in rows] == ["precinct", "administrative"]
    assert sum(r["contest_votes"] for r in rows) == 20
    assert "excludes separately reported" in rows[0]["ballot_scope"]
    with pytest.raises(ValueError, match="modes do not reconcile"):
        precinct_results.nc_results([dict(base, **{"Total Votes": "11"})])


def house_fixture():
    root = Path(__file__).resolve().parents[1] / "public/participation-results"
    pointer = json.loads((root / "latest.json").read_text())
    return json.loads((root / pointer["snapshot_id"] / "originals/house-2026.json").read_text())


def test_house_state_results_cover_all_districts_and_reconcile_every_party():
    source = house_fixture()
    states = {key.split("-")[0].upper() for key in source["region_results"]} | {"DC"}
    rows = context.house_results(source, states, "source")
    districts = [row for row in rows if row["level"] == "district"]
    statewide = [row for row in rows if row["level"] == "state"]
    assert len(districts) == 435
    assert {row["state_code"] for row in statewide} == states - {"DC"}
    expected = context.provider_votes(source["candidates"])
    for index, field in enumerate(["democratic_votes", "republican_votes", "other_votes"]):
        assert sum(row[field] for row in statewide) == expected[index]
    for row in statewide:
        assert row["contest_votes"] == sum(d["contest_votes"] for d in districts
                                          if d["state_code"] == row["state_code"])
        assert row["margin_pp"] == pytest.approx(
            100 * (row["democratic_votes"] - row["republican_votes"]) / row["contest_votes"], abs=.00001)


@pytest.mark.parametrize("field,value", [
    ("test_data", True), ("election_date", "2024-11-05"), ("province", "CA"),
    ("election_type", "Senate"), ("election_scope", "Primary"),
])
def test_house_refresh_rejects_wrong_election_identity(field, value):
    source = house_fixture()
    source[field] = value
    with pytest.raises(ValueError, match="Wrong election"):
        context.house_results(source, {key.split("-")[0].upper() for key in source["region_results"]}, "source")


def test_house_refresh_rejects_missing_duplicate_and_unreconciled_results():
    source = house_fixture()
    states = {key.split("-")[0].upper() for key in source["region_results"]}
    source["region_results"].pop("ak-al")
    with pytest.raises(ValueError, match="435 voting districts"):
        context.house_results(source, states, "source")
    source = house_fixture()
    source["region_results"]["ak-00"] = source["region_results"]["ak-al"]
    with pytest.raises(ValueError, match="Duplicate"):
        context.house_results(source, states, "source")
    source = house_fixture()
    source["candidates"][0]["votes"] += 1
    with pytest.raises(ValueError, match="reconcile"):
        context.house_results(source, states, "source")


def test_failed_house_refresh_keeps_the_previous_published_pointer(tmp_path, monkeypatch):
    source = house_fixture()
    source["test_data"] = True
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return source

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(context.requests, "get", lambda *args, **kwargs: Response())
    pointer = tmp_path / "public/participation-results/latest.json"
    pointer.parent.mkdir(parents=True)
    pointer.write_text('{"snapshot_id":"previous"}')
    with pytest.raises(ValueError, match="Wrong election"):
        context.refresh_results("invalid", set())
    assert json.loads(pointer.read_text()) == {"snapshot_id": "previous"}
    assert not (pointer.parent / "invalid").exists()


def test_current_precinct_number_requires_an_explicit_unambiguous_identity():
    assert current_precincts.precinct_number("PCT 001", "Bernalillo") == "1"
    assert current_precincts.precinct_number("PREC 048", "Rio Arriba") == "48"
    assert current_precincts.precinct_number("001", "Colfax") == "1"
    assert current_precincts.precinct_number("PRECINCT 7- LORDSBURG NORTH/WEST", "Hidalgo") == "7"
    assert current_precincts.precinct_number("PRECINCT 1 - OTHER", "Bernalillo") is None
    assert current_precincts.precinct_number("PRECINCT 1/2", "Hidalgo") is None
    assert current_precincts.precinct_number("EARLY 001", "Colfax") is None


def test_current_precinct_join_is_county_scoped_and_withholds_entire_mismatched_sets():
    def feature(county, number):
        return {"properties": {"county": county, "precinct": str(number)}}

    def row(county, number, ballots=60, denominator=100):
        return {"state_code": "NM", "county": county, "county_id": county,
                "unit": f"PCT {number:03}", "unit_key": f"{county}|{number}", "unit_kind": "precinct",
                "ballots": ballots, "denominator": denominator, "denominator_basis": "source_electorate",
                "reported_pct": ballots / denominator * 100, "source_url": "source", "source_update_label": ""}

    counties = [{"state_code": "NM", "county": county, "county_id": county, "rows_reconcile": True}
                for county in ["Catron", "Mora"]]
    features = [feature("Catron", 1), feature("Mora", 1)]
    rows = [row("Catron", 1), row("Mora", 1, 80), row("Mora", 2)]
    audit = current_precincts.join_precincts(features, rows, counties)
    assert features[0]["properties"]["reported_pct"] == 60
    assert features[0]["properties"]["unit_key"] == "Catron|1"
    assert features[1]["properties"]["reported_pct"] is None
    assert features[1]["properties"]["unit_key"] is None
    assert audit[1]["reporting_only_ids"] == ["2"]
    assert not audit[1]["exact_precinct_set"]
    for invalid_rows, invalid_counties in [
        ([rows[0], rows[0]], counties),
        ([{**rows[0], "unit_kind": "vote_center"}], counties),
        ([{**rows[0], "county_id": "Other office"}], counties),
        ([rows[0]], [{**counties[0], "rows_reconcile": False}]),
    ]:
        polygon = feature("Catron", 1)
        current_precincts.join_precincts([polygon], invalid_rows, invalid_counties)
        assert polygon["properties"]["reported_pct"] is None
    for observation in [row("Catron", 1, 10, 20), {**rows[0], "reported_pct": None}]:
        polygon = feature("Catron", 1)
        current_precincts.join_precincts([polygon], [observation], counties)
        assert polygon["properties"]["reported_pct"] is None
        assert polygon["properties"]["match_status"] == "rate_withheld"


def test_missing_historical_ids_never_merge_duplicate_names_or_elections():
    assert local.historical_source_id(None, 2004, 2) == "source-row:2004:2"
    assert local.historical_source_id("", 2004, 3) != local.historical_source_id(None, 2004, 2)
    assert local.historical_source_id(None, 2006, 2) != local.historical_source_id(None, 2004, 2)
    assert local.historical_source_id("0100100000", 2004, 2) == "0100100000"
    assert local.normalized_id(None) == ""


def test_local_rates_require_exact_identity_and_consistent_denominators():
    row = eavs(2024, [["AL", "0100100000", "Autauga", 80, 60, "", "", "", 20, "", "", ""]])[0]
    key = ("AL", "0100100000", "Autauga")
    registration = {"registered": 100, "registration_field": "a1a", "registration_comment": "Original note"}
    assert local.local_record(row, {key: registration})["turnout_pct"] == 80
    assert local.local_record(row, {("AL", "0100100000", "Another county"): registration})["turnout_pct"] is None
    assert local.local_record(row, {key: {**registration, "registered": 79}})["turnout_pct"] is None
    assert local.local_record(row, {key: registration})["registration_comment"] == "Original note"
    assert local.reported({"a1a": 100, "a1a_notavailable": "X"}, "a1a") is None


def test_local_geography_requires_id_name_and_unique_reporting_area():
    county = {"01001": {"properties": {"name": "Autauga County"}}}
    town = {"5500225": {"properties": {"name": "Ackley town"}}}
    row = {"state_code": "AL", "jurisdiction_id": "0100100000", "jurisdiction": "AUTAUGA",
           "statewide_unit": False, "supplemental_unit": False}
    assert local.match_geography(row, county, {}, "01") == {"level": "county", "key": "01001"}
    assert local.match_geography({**row, "jurisdiction": "Other"}, county, {}, "01") is None
    assert local.match_geography({**row, "statewide_unit": True}, county, {}, "01") is None
    wi = {**row, "jurisdiction_id": "00225", "jurisdiction": "TOWN OF ACKLEY - LANGLADE COUNTY"}
    assert local.match_geography(wi, {}, town, "55") == {"level": "municipality", "key": "5500225"}
    assert local.match_geography({**wi, "jurisdiction": "ACKLEY WARD 1"}, {}, town, "55") is None


def test_registration_ingestion_preserves_comments_missing_flags_and_exact_names():
    source = (b"State,FIPSCode,Jurisdiction,A1a,A1a_NotAvailable,A1Comments\n"
              b"AL,0100100000,Autauga,100,,Original registration note\n"
              b"AL,0100100000,Other office,90,X,Unavailable despite numeric cell\n")
    rows = local.registration_records(source, "source.csv")
    assert rows[("AL", "0100100000", "Autauga")]["registered"] == 100
    assert rows[("AL", "0100100000", "Autauga")]["registration_comment"] == "Original registration note"
    assert rows[("AL", "0100100000", "Other office")]["registered"] is None
    with pytest.raises(ValueError, match="Duplicate registration identity"):
        local.registration_records(source + source.splitlines(keepends=True)[1], "source.csv")


def test_2008_registration_field_keeps_source_definition_and_unavailable_flag():
    source = (b"JurisID,JurisName,STATE_,A1,A1_NotAvailable,A1_Comments,A2\n"
              b"0100100000,Autauga,AL,100,,Source note,only active voters\n"
              b"0100300000,Baldwin,AL,90,X,Unavailable,both active and inactive\n")
    rows = local.registration_records(source, "source.csv")
    assert rows[("AL", "0100100000", "Autauga")]["registered"] == 100
    assert rows[("AL", "0100100000", "Autauga")]["registration_definition"] == "only active voters"
    assert rows[("AL", "0100100000", "Autauga")]["registration_comment"] == "Source note"
    assert rows[("AL", "0100300000", "Baldwin")]["registered"] is None


def test_state_only_registration_override_requires_matching_fips_and_ignores_blank_rows():
    source = b"JurisID,JurisName,A1a\n4800100000,Anderson,100\n,,\n"
    rows = local.registration_records(source, "source.csv", ("TX", "48"))
    assert rows[("TX", "4800100000", "Anderson")]["registered"] == 100
    with pytest.raises(ValueError, match="different state"):
        local.registration_records(source.replace(b"48001", b"17001"), "source.csv", ("TX", "48"))


def portal_fixture(monkeypatch, rows, county_name="Bernalillo", ballots=80, denominator=100):
    monkeypatch.setitem(current_local.PORTALS, "NM", ("page", "service", 1))
    page = ('<input id="hidElectionDate" value="11/3/2026" />'
            '<input id="hidElectionType" value="General" />'
            '<div class="provisional-results-wrapper"><h1>' + county_name + '</h1>'
            '<div id="countyturnout02"></div>')
    for name, count, electorate in rows:
        page += (f'<div class="county-precinct">{name}</div>'
                 f'<div class="county-cast"><span>{count}</span></div>'
                 f'<div class="county-counted"><span>{electorate}</span></div>')
    payload = [{"CountyID": "02", "CountyName": county_name, "calcVoterTurnout": str(ballots),
                "Voters": denominator, "PrecinctsReporting": len(rows), "TotalPrecincts": len(rows),
                "CountyPercent": ballots / denominator, "CurrentDateTime": None}]
    official = {"ballots": ballots, "denominator": denominator, "denominator_basis": "eligible_voters_source_definition",
                "source_update_label": "11/4/2026"}
    return page, payload, "NM", official, {"source_url": "source"}


def test_2026_precinct_rates_require_reconciled_county_counts(monkeypatch):
    inputs = portal_fixture(monkeypatch, [("PCT 1", 50, 60), ("PCT 2", 30, 40)])
    counties, rows = current_local.parse_portal(*inputs)
    assert counties[0]["rows_reconcile"]
    assert rows[1]["reported_pct"] == 75
    assert rows[1]["denominator_basis"] == "eligible_voters_source_definition"
    page, payload, code, official, provenance = inputs
    bad = page.replace("<span>30</span>", "<span>20</span>")
    counties, rows = current_local.parse_portal(bad, payload, code, official, provenance)
    assert not counties[0]["rows_reconcile"]
    assert all(row["reported_pct"] is None for row in rows)
    with pytest.raises(ValueError, match="statewide totals"):
        current_local.parse_portal(page, payload, code, {**official, "ballots": 81}, provenance)
    with pytest.raises(ValueError, match="election identity"):
        current_local.parse_portal(page.replace("11/3/2026", "11/5/2024"), payload, code, official, provenance)


def test_vote_centers_duplicate_names_and_countywide_rows_are_not_precinct_rates(monkeypatch):
    inputs = portal_fixture(monkeypatch, [("Church Hall", 0, 100), ("Church Hall", 80, 100)],
                            county_name="Oglala Lakota (Vote Center)")
    counties, rows = current_local.parse_portal(*inputs)
    assert not counties[0]["rows_reconcile"]
    assert len({row["unit_key"] for row in rows}) == 2
    assert all(row["unit_kind"] == "vote_center" and row["reported_pct"] is None for row in rows)
    inputs = portal_fixture(monkeypatch, [("PCT 1", 80, 100), ("Countywide", 0, 100)])
    _, rows = current_local.parse_portal(*inputs)
    assert rows[1]["unit_kind"] == "countywide"
    assert all(row["reported_pct"] is None for row in rows)


def eavs(year, rows):
    prefix = "QF1" if 2010 <= year <= 2014 else "F1"
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["State", "FIPSCode", "Jurisdiction", *[prefix + c for c in "abcdefg"], prefix + "_Comment", "F2"])
    writer.writerows(rows)
    return methods.normalize_eavs(stream.getvalue().encode(), "source.csv", year, {"AL", "AK", "ME"}, "https://www.eac.gov/source")


@pytest.mark.parametrize("value", [None, "", -99, "-88", "-77", "-888888: Not Applicable",
                                  "-999999: Data Not Available", "Does not apply", "Data not available"])
def test_missing_is_not_zero(value):
    assert methods.count(value) is None
    assert methods.count("0") == 0


def test_2008_other_and_later_mail_are_not_interchangeable():
    record = ["AL", "0100100000", "Autauga", 100, 50, 1, 10, 4, 30, 5, "Absentee includes in-person", "Vote history"]
    old = eavs(2008, [record])[0]
    later = eavs(2012, [record])[0]
    assert "all_mail" not in old["methods"]
    assert later["methods"]["all_mail"] == 5
    assert later["methods"]["provisional"] == 4
    assert later["methods"]["early_in_person"] == 30
    assert later["source_details"]["qf1_comment"] == "Absentee includes in-person"
    assert later["source_details"]["f2"] == "Vote history"


def test_matched_denominators_and_invalid_shares():
    records = eavs(2024, [
        ["AL", "1", "A", 100, 40, "", "", "", 10, "", "", ""],
        ["AL", "2", "B", 900, "", "", "", "", "", "", "", ""],
        ["AL", "3", "C", "", 20, "", "", "", "", "", "", ""],
        ["AL", "4", "D", 10, 30, "", "", "", "", "", "", ""],
    ])
    row = next(r for r in methods.state_summaries(records) if r["mode"] == "election_day")
    assert row["reported_count"] == 90
    assert row["matched_count"] == 40
    assert row["matched_participation"] == 100
    assert row["share_pct"] == 40
    assert row["matched_units"] == 1
    assert row["total_units"] == 4
    assert row["invalid_share_units"] == 1
    missing = next(r for r in methods.state_summaries(records) if r["mode"] == "uocava")
    assert missing["reported_count"] is None
    assert missing["share_pct"] is None


def test_statewide_and_special_units_do_not_double_count():
    records = eavs(2024, [
        ["AK", "0200000000", "ALASKA", 100, 60, "", "", "", 40, "", "", ""],
        ["AK", "0200100000", "Component", 100, 60, "", "", "", 40, "", "", ""],
        ["ME", "23", "UOCAVA-ME", 5, 0, 5, "", "", "", "", "", ""],
        ["ME", "2300100000", "Local unit", 200, 80, 5, "", "", 50, "", "", ""],
    ])
    rows = methods.state_summaries(records)
    ak = next(r for r in rows if r["state_code"] == "AK" and r["mode"] == "election_day")
    assert ak["reported_count"] == 60
    assert ak["excluded_component_units"] == 1
    me = next(r for r in rows if r["state_code"] == "ME" and r["mode"] == "uocava")
    assert me["reported_count"] == 5
    assert len(records) == 4


def test_repeated_source_ids_preserve_distinct_wards_but_reject_duplicates():
    record = ["AL", "1", "Ward 1", 100, 50, "", "", "", 30, "", "", ""]
    other = record.copy()
    other[2] = "Ward 2"
    assert len(eavs(2014, [record, other])) == 2
    with pytest.raises(ValueError, match="duplicate reporting unit"):
        eavs(2014, [record, record])


def test_census_stops_before_margins_of_error():
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Table 14. Method of Voting"])
    sheet.append(["Total", None, 100, 40, 30, 29, 1])
    sheet.append(["Sex", "Female", 55, 39, 31, 29, 1])
    sheet.append(["Margins of Error"])
    sheet.append(["Total", None, 5, 2, 1, 1, 1])
    stream = io.BytesIO()
    book.save(stream)
    rows = methods.census_rows(stream.getvalue(), 2024, "https://www.census.gov/source")
    assert len(rows) == 2
    assert rows[0]["methods"]["unknown"] == 1
    assert rows[0]["reported_voters_thousands"] == 100


def test_margin_uses_all_contest_votes_not_two_party_denominator():
    assert context.margin(45, 40, 15)["margin_pp"] == 5
    assert context.margin(0, 0, 0)["margin_pp"] is None
    with pytest.raises(ValueError):
        context.margin(10, -1, 0)


def test_unavailable_flags_override_contradictory_numeric_cells():
    source = b"State,FIPSCode,Jurisdiction,F1a,F1b,F1f,F1f_NotAvailable\nAL,1,County,100,60,40,X\n"
    row = methods.normalize_eavs(source, "source.csv", 2008, {"AL"}, "source")[0]
    assert row["methods"]["early_in_person"] is None
    assert row["raw_method_fields"]["f"] == "40"
    assert row["source_details"]["f1f_notavailable"] == "X"


def test_1994_recap_reconciles_and_omits_untabulated_louisiana():
    rows = context.clerk_1994("official-source")
    assert len(rows) == 49
    assert not any(row["state_code"] == "LA" for row in rows)
    assert sum(row["contest_votes"] for row in rows) == 70493648
    assert next(row for row in rows if row["state_code"] == "NC")["margin_pp"] < 0


def test_fec_accepts_shifted_state_code_column_without_using_primary_votes(monkeypatch):
    rows = [["2010 VOTES CAST FOR THE U.S. HOUSE OF REPRESENTATIVES BY PARTY"],
            ["Alabama", "AL", 900, 800, 700, 45, 40, 15]]
    monkeypatch.setattr(context, "workbook", lambda *args, **kwargs: {"House": rows})
    row = context.summary_tables(b"", 2010, {"AL": "Alabama"}, "source")[0]
    assert row["democratic_votes"] == 45
    assert row["republican_votes"] == 40
    assert row["contest_votes"] == 100


def test_fec_rejects_missing_state_coverage(monkeypatch):
    monkeypatch.setattr(context, "workbook", lambda *args, **kwargs: {
        "House": [["2010 VOTES CAST FOR THE U.S. HOUSE OF REPRESENTATIVES BY PARTY"]]})
    with pytest.raises(ValueError, match="missing states"):
        context.summary_tables(b"", 2010, {"AL": "Alabama"}, "source")


def test_fec_withholds_bad_presidential_state_without_discarding_reconciled_states(monkeypatch):
    sheets = {
        "House": [["HOUSE OF REPRESENTATIVES BY PARTY"],
                  ["AL", 0, 0, 0, 5, 4, 1], ["NY", 0, 0, 0, 20, 10, 5]],
        "Combined": [["GENERAL ELECTION VOTES CAST BY PARTY"],
                     ["AL", 50, 44, 16], ["NY", 30, 25, 4]],
        "Senate": [["SENATE BY PARTY"]],
        "Totals": [["GENERAL ELECTION VOTES CAST FOR"], ["AL", 100], ["NY", 24]],
    }
    monkeypatch.setattr(context, "workbook", lambda *args, **kwargs: sheets)
    rejected = []
    rows = context.summary_tables(b"", 2000, {"AL": "Alabama", "NY": "New York"}, "source", rejected=rejected)
    assert {(row["office"], row["state_code"]) for row in rows} == {
        ("U.S. House", "AL"), ("U.S. House", "NY"), ("President", "AL")}
    assert next(row for row in rows if row["office"] == "President")["contest_votes"] == 100
    assert len(rejected) == 1
    assert "2000 NY" in rejected[0]["error"]
    with pytest.raises(ValueError, match="2000 NY"):
        context.summary_tables(b"", 2000, {"AL": "Alabama", "NY": "New York"}, "source")
