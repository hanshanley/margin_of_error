import csv
import importlib.util
import io
import hashlib
import json
import math
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
nd_review = module("review-north-dakota-precinct-results")
nd_maps = module("build-north-dakota-precinct-results")
vt_review = module("review-vermont-precinct-results")
vt_maps = module("build-vermont-precinct-results")
id_review = module("review-idaho-precinct-results")
id_maps = module("build-idaho-precinct-results")
sd_review = module("review-south-dakota-precinct-results")
ak_review = module("review-alaska-precinct-results")
ak_boundaries = module("review-alaska-precinct-boundaries")
hi_review = module("review-hawaii-precinct-results")
hi_historical = module("archive-hawaii-historical-sources")
ri_review = module("review-rhode-island-precinct-results")


def rhode_island_fixture():
    import copy
    names = [("Town", "00000000-0000-0000-0000-000000000001"),
             ("Federal", "00000000-0000-0000-0000-000000000002")]
    state, public, localities = [], [], []
    for identity, title in ri_review.CONTESTS.items():
        options, independent = [], []
        for cid, name, party in [("1", "Democrat", "DEMOCRAT"),
                                 ("2", "Republican", "REPUBLICAN"), ("3", "Write-in", None)]:
            groups = [dict(groupName=m, voteCount=2, isFromVirtualPrecinct=False)
                      for m in sorted(ri_review.MODES)]
            options.append(dict(id=cid, name=name, politicalParty=party,
                                voteCount=6, groupResults=groups))
            independent.append(dict(nativeId=cid, name=[dict(languageId="en", text=name)],
                voteCount=6, party=dict(name=[dict(languageId="en", text=party)]) if party else dict(name=None),
                groupResults=[dict(groupName=[dict(languageId="en", text=g["groupName"])],
                                   voteCount=g["voteCount"]) for g in groups]))
        state.append(dict(id=identity, name=title, contestType="Candidate", voteFor=1, ballotOptions=options))
        public.append(dict(name=[dict(languageId="en", text=title)],
                           summaryResults=dict(ballotOptions=independent)))
    for name, lid in names:
        contests = copy.deepcopy(state)
        for contest in contests:
            contest["precinctsParticipating"] = 0
            for candidate in contest["ballotOptions"]:
                groups = [dict(groupName=m, voteCount=1, isFromVirtualPrecinct=False)
                          for m in sorted(ri_review.MODES)]
                candidate.update(voteCount=3, groupResults=groups,
                    precinctResults=[dict(id="unit", name="LIMITED ONLY" if name == "Town" else "Federal #1",
                        isVirtual=False, reportingStatus="Election Night Complete",
                        voteCount=3, groupResults=groups)])
        localities.append(dict(id=lid, name=name, ballotItems=contests))
    election = dict(electionDate="2026-11-03", name=[dict(languageId="en", text="Statewide General Election")],
                    ballotsCast=0, totalVoters=10)
    parent = dict(election=election, ballotItems=public,
        jurisdiction=dict(name=[dict(languageId="en", text="Rhode Island")],
            childLocalities=[dict(id=lid.upper(), name=[dict(languageId="en", text=name)]) for name, lid in names]),
        localityElections=[dict(jurisdictionId=lid, asOf="source-time", ballotsCast=0, totalVoters=5)
                           for name, lid in names])
    return dict(electionDate="2026-11-03", electionName="Statewide General Election",
                results=dict(name="Rhode Island", ballotItems=state), localResults=localities), parent


def test_rhode_island_retains_nonresidential_units_zero_counts_and_separate_locality_statistics():
    results, statistics, audit = ri_review.review(*rhode_island_fixture())
    assert len(results) == 4 and len({r["key"] for r in results}) == 4
    assert audit["unique_native_units"] == 2 and len(audit["native_vs_declared_precinct_counts"]) == 4
    assert {r["reporting_unit_kind"] for r in results} == {"federal_reporting_unit", "limited_only_office"}
    assert all(r["other_votes"] == 3 and not r["source_is_virtual"] for r in results)
    assert len(statistics) == 2 and all(r["reported_pct"] is None and r["ballots"] == 0 for r in statistics)


@pytest.mark.parametrize("change", ["mode", "candidate", "public", "unit", "duplicate", "locality", "date"])
def test_rhode_island_rejects_missing_or_conflicting_native_scope_and_independent_totals(change):
    media, parent = rhode_island_fixture()
    candidate = media["localResults"][0]["ballotItems"][0]["ballotOptions"][0]
    if change == "mode":
        candidate["precinctResults"][0]["groupResults"][0]["voteCount"] = 2
    elif change == "candidate":
        candidate["politicalParty"] = "Other"
    elif change == "public":
        parent["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["voteCount"] = 9
    elif change == "unit":
        candidate["precinctResults"] = []
    elif change == "duplicate":
        candidate["precinctResults"].append(candidate["precinctResults"][0])
    elif change == "locality":
        media["localResults"].pop()
    else:
        media["electionDate"] = "2024-11-05"
    with pytest.raises(ValueError):
        ri_review.review(media, parent)


@pytest.mark.parametrize("value", [None, True, -1, 1.5, float("inf")])
def test_rhode_island_never_imputes_missing_invalid_or_boolean_counts(value):
    with pytest.raises(ValueError):
        ri_review.count(value)


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le"])
def test_hawaii_historical_sources_preserve_utf16_and_missing_trailing_header_fields(encoding):
    text = 'Format#1\r\nCandidate_name,Votes\r\n"Quoted\r\ncandidate",12,\r\nOther,0,\r\n'
    audit = hi_historical.text_inventory(text.encode(encoding))
    assert audit["encoding"] == encoding and audit["source_format_metadata"] == "Format#1"
    assert audit["native_data_records"] == 2 and audit["native_record_widths"] == {3: 2}
    assert audit["data_trailing_empty_field_absent_from_header"]


def test_hawaii_historical_sources_do_not_relabel_absentee_early_and_election_columns():
    audit = hi_historical.text_inventory(
        b"Candidate_name,Absentee_votes,Early_votes,Election_Votes\r\nCandidate,10,2,3\r\n")
    assert audit["encoding"] == "utf-8-sig"
    assert audit["native_header"][1:] == ["Absentee_votes", "Early_votes", "Election_Votes"]
    assert not audit["data_trailing_empty_field_absent_from_header"]


def test_hawaii_historical_sources_reject_ragged_rows_instead_of_truncating_data():
    with pytest.raises(ValueError, match="fields"):
        hi_historical.text_inventory(b"Candidate,Votes\nPerson,12,\nAnother,3,unexpected\n")


def hawaii_fixture():
    rows, summary = [], []
    for contest, label, overseas, names in [
            ("30", "20-01", "OS I", ["(D) CASE, Ed", "(R) LAM, Adriel C.",
                                    "(G) CONLEY, Jordan S.", "(N) BERNING, Nathan M."]),
            ("5", "01-01", "OS II", ["(D) TOKUDA, Jill N.", "(R) AWA, Brenton"])]:
        for i, name in enumerate(names, 1):
            record = dict.fromkeys(hi_review.SUMMARY_HEADER, "")
            record.update({"#Contest ID": contest, "Contest Title": hi_review.CONTESTS[contest],
                "Contest Type": "OF", "Registered Voters": "200", "Total Precincts": "3",
                "Counted Precincts": "2", "Candidate ID": str(i), "Candidate Name": name,
                "Mail Votes": "3", "In-Person Votes": "2", "Total Votes": "5", "_source_lines": [2, 2]})
            for mode in hi_review.MODES:
                for kind in ("Blank", "Over", "Invalid"):
                    record[f"{mode} {kind} Votes"] = "1" if (mode, kind) == ("Mail", "Blank") else "0"
            summary.append(record)
            for suffix, split, unit_label, votes, ballots, registration, reporting in [
                    ("1", "", label, "3", str(len(names) * 3 + 1), "100", "1"),
                    ("2", "VSC", label, "2", str(len(names) * 2), "0", "0"),
                    ("3", "", overseas, "0", "0", "0", "1")]:
                row = dict.fromkeys(hi_review.MEDIA_HEADER, "")
                row.update({hi_review.LABEL: unit_label, "Split_Name": split,
                    "precinct_splitId": contest + suffix, "Reg_voters": registration, "Ballots": ballots,
                    "Reporting": reporting, "Contest_id": contest,
                    "Contest_title": hi_review.CONTESTS[contest], "Choice_id": str(i),
                    "Candidate_name": name, "Candidate_Type": "C",
                    "Mail votes": "0" if split else votes, "In-Person votes": votes if split else "0",
                    "_source_lines": [len(rows) + 4, len(rows) + 4]})
                rows.append(row)
    return rows, summary


def test_hawaii_reconciles_modes_without_merging_vsc_or_double_counting_registration():
    results, statistics, audit = hi_review.review(*hawaii_fixture())
    assert len(results) == len(statistics) == 6 and len({r["key"] for r in results}) == 6
    assert sum(r["registered"] for r in statistics) == 200
    assert all(r["reported_pct"] is None for r in statistics)
    vsc = [r for r in results if r["source_split_label"] == "VSC"]
    assert len(vsc) == 2 and all(r["source_reporting"] == 0 and r["contest_votes"] > 0 for r in vsc)
    assert sum(r["other_votes"] for r in results) == 10
    assert audit["reporting_unit_kinds"]["overseas_reporting_unit"] == 2
    assert all(v["native_minus_summary"] == 0 for v in audit["ballot_accounting_by_mode"].values())


def test_hawaii_retains_ballot_discrepancies_without_repairing_counts_or_creating_rates():
    rows, summary = hawaii_fixture()
    for row in rows:
        if row["precinct_splitId"] == "301":
            row["Ballots"] = "14"
    results, statistics, audit = hi_review.review(rows, summary)
    assert next(r for r in statistics if r["source_unit_id"] == "301")["ballots"] == 14
    assert audit["ballot_accounting_by_mode"]["Mail"]["native_minus_summary"] == 1
    assert all(r["reported_pct"] is None for r in statistics)
    assert sum(r["contest_votes"] for r in results) == 30


@pytest.mark.parametrize("change", ["candidate_id", "candidate_name", "party", "missing_count",
                                   "mode_swap", "duplicate_candidate", "missing_unit", "unit_facts",
                                   "unknown_split", "summary_scope", "summary_registration"])
def test_hawaii_rejects_ambiguous_source_identity_missing_counts_and_incomplete_scope(change):
    rows, summary = hawaii_fixture()
    if change == "candidate_id":
        rows[0]["Choice_id"] = "999"
    elif change == "candidate_name":
        rows[0]["Candidate_name"] = "(D) Different person"
    elif change == "party":
        rows[0]["Choice_party"] = "R"
    elif change == "missing_count":
        rows[0]["Mail votes"] = ""
    elif change == "mode_swap":
        rows[0]["In-Person votes"] = "1"
    elif change == "duplicate_candidate":
        rows.append(dict(rows[0]))
    elif change == "missing_unit":
        rows[:] = [r for r in rows if r["precinct_splitId"] != "302"]
    elif change == "unit_facts":
        rows[0]["Ballots"] = "999"
    elif change == "unknown_split":
        for row in rows:
            if row["precinct_splitId"] == "302":
                row["Split_Name"] = "UNKNOWN"
    elif change == "summary_scope":
        for row in summary:
            if row["#Contest ID"] == "30":
                row["Counted Precincts"] = "3"
    else:
        for row in summary:
            if row["#Contest ID"] == "30":
                row["Registered Voters"] = "100"
    with pytest.raises(ValueError):
        hi_review.review(rows, summary)


def test_hawaii_multiline_native_csv_preserves_actual_source_line_ranges():
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter="\t")
    writer.writerow([f"Column{i}" for i in range(1, 17)])
    writer.writerow(["#FormatVersion 1"] + [""] * 15)
    writer.writerow(hi_review.MEDIA_HEADER)
    first = [""] * 16
    first[10] = "(D) A quoted name\nand running mate"
    writer.writerow(first)
    writer.writerow([""] * 16)
    records = hi_review.read_table(buffer.getvalue().encode(), media=True)
    assert records[0]["Candidate_name"] == first[10]
    assert records[0]["_source_lines"] == [4, 5] and records[1]["_source_lines"] == [6, 6]
    with pytest.raises(ValueError, match="header"):
        hi_review.read_table(buffer.getvalue().replace("precinct_splitId", "unknown").encode(), media=True)


def test_hawaii_rejects_missing_candidate_and_wrong_summary_mode_totals():
    rows, summary = hawaii_fixture()
    with pytest.raises(ValueError, match="candidate"):
        hi_review.review(rows[1:], summary)
    summary[0]["Total Votes"] = "6"
    with pytest.raises(ValueError, match="ballot modes"):
        hi_review.review(rows, summary)


def test_hawaii_pdf_comparison_keeps_native_zero_denominators_and_pdf_only_overseas_modes():
    results, statistics, _ = hi_review.review(*hawaii_fixture())
    observations = []
    for row, stats in zip(results, statistics):
        mode = "In-Person" if row["source_split_label"] else "Mail"
        registration = 100 if row["source_split_label"] else stats["registered"]
        observations.append(dict(label=mode + " " + row["source_precinct_label"], pages=[1],
            participation={"PRECINCT REGISTRATION": registration, mode + " TURNOUT": stats["ballots"]},
            candidate_votes={row["source_office"] + "|" + name: votes
                             for name, votes in json.loads(row["candidate_votes"]).items()}))
    for name in ("OS I", "OS II"):
        observations.append(dict(label="In-Person " + name, pages=[99], candidate_votes={},
            participation={"PRECINCT REGISTRATION": 0, "In-Person TURNOUT": 0}))
    pdfs = {"precinct.pdf": dict(printed_on="test", records=observations)}
    for name in ("cch.pdf", "coh.pdf", "cok.pdf", "com.pdf", "histatewide.pdf"):
        pdfs[name] = dict(printed_on="test", records=[dict(candidate_votes={}, participation={})])
    audit = hi_review.compare_pdf_observations(results, statistics, pdfs)
    assert audit["native_units_compared"] == 6 and audit["pdf_units"] == 8
    assert audit["difference_fields"] == {"registered": 2}
    assert len(audit["pdf_only_units"]) == 2
    assert all(r["registered"] == 0 for r in statistics if r["source_split_label"])
    assert all(r["reported_pct"] is None for r in statistics)


def test_hawaii_rejects_wrong_election_pdf_even_with_a_correct_looking_precinct_label():
    with hi_review.fitz.open() as document:
        page = document.new_page()
        page.insert_text((20, 20), "GENERAL ELECTION 2024 - State of Hawaii - Statewide\n"
                         "November 5, 2024\nREPORT 3\nMail 01-01")
        original = document.tobytes()
    with pytest.raises(ValueError, match="election"):
        hi_review.pdf_observations({"cch.pdf": original})


def alaska_boundary_fixture(overlap=False):
    features, geographic_features, geojson_features, precincts = [], [], [], []
    for oid, west in [(1, -150), (2, -149.95 if overlap else -149.8)]:
        ring = [[west, 61], [west, 61.1], [west + .1, 61.1], [west + .1, 61], [west, 61]]
        number, name = f"01-{oid}00", f"Precinct {oid}"
        attributes = dict(OBJECTID=oid, Precinct_Number=f"{number} {name}",
            HouseDistrict="01", CreationDate=1655494956944, Sample_Ballot_URL=None)
        projected = [[math.radians(lon) * 6378137,
                      math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * 6378137]
                     for lon, lat in ring]
        features.append(dict(attributes=dict(attributes), geometry=dict(rings=[projected])))
        geographic_features.append(dict(attributes=dict(attributes), geometry=dict(rings=[ring])))
        geojson_features.append(dict(type="Feature", properties=dict(attributes),
            geometry=dict(type="Polygon", coordinates=[[list(p) for p in ring]])))
        precincts.append(dict(number=number, name=name))
    return (dict(spatialReference=dict(wkid=102100), geometryType="esriGeometryPolygon",
                 features=features),
            dict(spatialReference=dict(wkid=4326), geometryType="esriGeometryPolygon",
                 features=geographic_features),
            dict(type="FeatureCollection", features=geojson_features),
            dict(name="Alaska 2026 General Election", precincts=precincts))


def test_alaska_locator_matching_ids_and_current_use_do_not_establish_election_vintage():
    audit = ak_boundaries.audit_references(*alaska_boundary_fixture())
    assert audit["reference_features"] == audit["valid_polygon_units"] == 2
    assert audit["overlap_scope_complete"] and not audit["overlap_pairs"]
    assert audit["join"] == "withheld" and audit["complete"] is False
    assert "not independently established" in audit["boundary_vintage"]
    assert audit["reference_creation_dates"] == {"1655494956944": 2}


def test_alaska_locator_audits_labels_without_silently_substituting_aliases():
    fixture = alaska_boundary_fixture()
    fixture[3]["precincts"][0]["name"] = "Different official label"
    audit = ak_boundaries.audit_references(*fixture)
    assert audit["name_differences"] == [dict(precinct="01-100",
        reference_name="Precinct 1", election_name="Different official label")]
    assert audit["join"] == "withheld"


def test_alaska_locator_checks_overlaps_against_every_reference_including_conflicting_labels():
    fixture = alaska_boundary_fixture(overlap=True)
    fixture[3]["precincts"][1]["name"] = "Different label"
    audit = ak_boundaries.audit_references(*fixture)
    assert audit["overlap_scope_complete"] and len(audit["overlap_pairs"]) == 1
    assert math.isclose(audit["overlap_pairs"][0]["area_degrees_squared"], .005)
    assert audit["join"] == "withheld"


def test_alaska_locator_preserves_geojson_defects_without_replacing_native_ring_roles():
    fixture = alaska_boundary_fixture()
    ring = fixture[2]["features"][0]["geometry"]["coordinates"][0]
    ring[1], ring[2] = ring[2], ring[1]
    audit = ak_boundaries.audit_references(*fixture)
    assert audit["valid_polygon_units"] == 2
    assert audit["native_vs_service_geojson_differences"] == [
        dict(precinct="01-100", geojson_invalid=True)]


def test_alaska_locator_does_not_call_a_subset_overlap_audit_statewide():
    native, geographic, geojson, results = alaska_boundary_fixture()
    for data in [native, geographic]:
        ring = data["features"][0]["geometry"]["rings"][0]
        ring[1], ring[2] = ring[2], ring[1]
    audit = ak_boundaries.audit_references(native, geographic, geojson, results)
    assert audit["valid_polygon_units"] == 1
    assert len(audit["invalid_reference_units"]) == 1
    assert audit["overlap_scope_complete"] is False
    assert audit["join"] == "withheld"


@pytest.mark.parametrize("problem", [
    "wrong_election", "wrong_projection", "truncated", "duplicate_object",
    "missing_unit", "different_attributes", "unknown_id", "wrong_district",
    "projection_disagreement", "ring_structure", "nonfinite_coordinate",
])
def test_alaska_locator_rejects_mixed_incomplete_or_inconsistent_exports(problem):
    native, geographic, geojson, results = alaska_boundary_fixture()
    if problem == "wrong_election":
        results["name"] = "Alaska 2024 General Election"
    elif problem == "wrong_projection":
        geographic["spatialReference"]["wkid"] = 3857
    elif problem == "truncated":
        native["exceededTransferLimit"] = True
    elif problem == "duplicate_object":
        native["features"][1] = native["features"][0]
    elif problem == "missing_unit":
        geographic["features"].pop()
    elif problem == "different_attributes":
        geojson["features"][0]["properties"]["HouseDistrict"] = "02"
    elif problem in {"unknown_id", "wrong_district"}:
        for data, field in [(native, "attributes"), (geographic, "attributes"), (geojson, "properties")]:
            data["features"][0][field]["Precinct_Number" if problem == "unknown_id" else "HouseDistrict"] = (
                "01-999 Unknown" if problem == "unknown_id" else "02")
    elif problem == "projection_disagreement":
        native["features"][0]["geometry"]["rings"][0][0][0] += 100
    elif problem == "ring_structure":
        native["features"][0]["geometry"]["rings"][0].pop()
    elif problem == "nonfinite_coordinate":
        geographic["features"][0]["geometry"]["rings"][0][0][0] = float("nan")
    with pytest.raises(ValueError):
        ak_boundaries.audit_references(native, geographic, geojson, results)


def alaska_fixture():
    names = ["R Candidate (REP)", "D Candidate (DEM)", "Other Candidate (NON)"]
    raw, geographic = [], []
    totals = [0, 0, 0]
    for sequence, identifier, label in [
        ("1", "01-100", "01-100 First"), ("2", "01-200", "01-200 Second"),
        ("3", "99-999", "HD99 Fed Overseas Absentee"),
        ("4", "1-1", "District 1 - Absentee"), ("5", "", "District 1 - Early Voting"),
        ("6", "", "District 1  - Question"),
    ]:
        votes = [20, 10, 5]
        registration = 100 if int(sequence) <= 3 else 0
        for index, (name, party) in enumerate([("R Candidate", "REP"), ("D Candidate", "DEM"),
                                             ("Other Candidate", "NON")]):
            totals[index] += votes[index]
            row = dict(Pct_seq_nbr=sequence, Pct_Id=identifier, Precinct_name=label,
                Contest_title=ak_review.OFFICE, Contest_Id="8", candidate_id=str(index),
                candidate_name=name, Party_Code=party, Selectable_Options="1",
                Reg_voters=str(registration), total_ballots="40", total_votes=str(votes[index]),
                total_under_votes="4", total_over_votes="1")
            row.update({mode + "_votes": str(votes[index] if mode == "Election Day" else 0)
                        for mode in ak_review.MODES})
            raw.append(row)
        if int(sequence) <= 2:
            geographic.append(dict(number=identifier, name=label.split(" ", 1)[1],
                contests=[dict(n=0, b=40, v=100, t=35, c=[
                    dict(n=i, t=votes[i]) for i in [2, 0, 1]])]))
    data = dict(name="Alaska 2026 General Election", certified=False, updated="11/04/2026 2:11 PM",
        format="2024", contestNames=[ak_review.OFFICE], candidateNames=names,
        totals=[dict(n=0, b=240, v=300, t=210, p=3, r=2,
                     c=[dict(n=i, t=v) for i, v in enumerate(totals)])],
        precincts=geographic, districts=[dict(number="1")])
    state = json.loads(json.dumps(data))
    state.pop("precincts")
    return raw, state, data, [dict(number=r["number"], coords=[]) for r in geographic]


def test_alaska_preserves_pooled_and_federal_units_without_allocating_or_inferring_rates():
    rows, statistics, audit = ak_review.review(*alaska_fixture())
    assert len(rows) == len(statistics) == 6 and len({r["key"] for r in rows}) == 6
    assert sum(r["democratic_votes"] for r in rows) == 60
    assert sum(r["other_votes"] for r in rows) == 30
    assert audit["geographic_precincts"] == 2 and audit["pooled_reporting_units"] == 3
    assert sum(r["ballots"] for r in statistics) == 240
    assert all(r["reported_pct"] is None for r in statistics)
    assert rows[-1]["source_precinct_id"] == rows[-2]["source_precinct_id"] == ""
    assert rows[-1]["key"] != rows[-2]["key"]
    assert rows[2]["reporting_unit_kind"] == "federal_overseas"
    assert "pooled_district_ballots_not_allocated_to_residential_precincts" in statistics[0]["quality_flags"]


def test_alaska_retains_ballot_balance_discrepancies_without_repairing_counts():
    raw, state, data, shapes = alaska_fixture()
    for row in raw[:3]:
        row["total_under_votes"] = "3"
    rows, statistics, audit = ak_review.review(raw, state, data, shapes)
    assert rows[0]["contest_votes"] == 35 and statistics[0]["ballots"] == 40
    assert statistics[0]["source_under_votes"] == 3 and statistics[0]["reported_pct"] is None
    assert audit["quality_flag_counts"]["candidate_votes_plus_source_under_over_disagree_with_ballots"] == 1


@pytest.mark.parametrize("problem", [
    "wrong_election", "wrong_format", "mixed_snapshot", "unknown_party", "duplicate_candidate",
    "missing_count", "repeated_ballots", "candidate_mode_sum", "native_geographic_count",
    "literal_precinct_name", "unknown_pooled_label", "duplicate_pooled", "missing_pooled",
    "missing_shape", "duplicate_shape", "statewide_count", "statewide_ballots",
])
def test_alaska_rejects_mixed_incomplete_or_ambiguous_originals(problem):
    raw, state, data, shapes = alaska_fixture()
    if problem == "wrong_election":
        data["name"] = state["name"] = "Alaska 2024 General Election"
    elif problem == "wrong_format":
        data["format"] = state["format"] = "2022"
    elif problem == "mixed_snapshot":
        data["updated"] = "different snapshot"
    elif problem == "unknown_party":
        raw[0]["Party_Code"] = "Unverified Party"
    elif problem == "duplicate_candidate":
        raw[1]["candidate_id"] = raw[0]["candidate_id"]
    elif problem == "missing_count":
        raw[0]["total_votes"] = ""
    elif problem == "repeated_ballots":
        raw[0]["total_ballots"] = "41"
    elif problem == "candidate_mode_sum":
        raw[0]["Absentee_votes"] = "1"
    elif problem == "native_geographic_count":
        data["precincts"][0]["contests"][0]["v"] += 1
    elif problem == "literal_precinct_name":
        for row in raw[:3]:
            row["Precinct_name"] = "01-100 Similar But Unverified"
    elif problem == "unknown_pooled_label":
        for row in raw[-3:]:
            row["Precinct_name"] = "Unknown nonresidential unit"
    elif problem == "duplicate_pooled":
        for row in raw[-3:]:
            row["Precinct_name"] = "District 1 - Absentee"
    elif problem == "missing_pooled":
        raw = raw[:-3]
    elif problem == "missing_shape":
        shapes.pop()
    elif problem == "duplicate_shape":
        shapes.append(shapes[0])
    elif problem == "statewide_count":
        for source in (data, state):
            source["totals"][0]["c"][0]["t"] += 1
            source["totals"][0]["t"] += 1
    else:
        data["totals"][0]["b"] = state["totals"][0]["b"] = 241
    with pytest.raises(ValueError):
        ak_review.review(raw, state, data, shapes)


def south_dakota_fixture():
    candidates = ["R  Candidate ", "D Candidate"]

    def sheet(items, label, county=None):
        body = [(None, name, r, d) for name, d, r in items]
        rows = [("2026 Unofficial General Election Results", None, None, None),
            ("State of South Dakota", None, None, None),
            ("Precincts 3 of 3 Reporting (Precincts Partially Reported: 0/3)", None, None, None),
            (county, None, None, None), (None,) * 4, (None,) * 4,
            (sd_review.OFFICE, "Precinct" if county else "County", *candidates), *body,
            (None, "TOTALS", sum(v[2] for v in body), sum(v[3] for v in body))]
        return sd_review.house_sheet(rows, label, 3)

    sheets = {"01": sheet([("Precinct 1 ", 20, 40), ("Precinct 2", 10, 30)], "first.xlsx", "First County"),
              "02": sheet([("Center Hall", 5, 15)], "center.xlsx", "Center County")}
    statewide = sheet([("First", 30, 70), ("Center (Vote Center)", 5, 15)], "statewide.xlsx")
    facts = dict(year=2026, election="General Election November 3, 2026", counties=[])
    api = []
    for code, county, records, registrations, center in [
        ("01", "First", [("Precinct 1", 65, 100), ("Precinct 2", 45, 100)], 200, False),
        ("02", "Center", [("Center Hall", 22, 300)], 300, True),
    ]:
        facts["counties"].append(dict(code=code, county=county, vote_center=center,
            records=[dict(label=name, raw_label=name, source_row=i, ballots=b, registered=r)
                     for i, (name, b, r) in enumerate(records, 1)]))
        api.append(dict(CountyID=code, CountyName=county + (" (Vote Center)" if center else ""),
            IsReported=True, PartialPrecincts=0,
            PrecinctsReporting=len(records), TotalPrecincts=len(records), Voters=registrations,
            calcVoterTurnout=sum(r[1] for r in records)))
    catalog = [dict(desc=sd_review.OFFICE, name="D Candidate", Party="Democratic"),
               dict(desc=sd_review.OFFICE, name="R Candidate", Party="Republican")]
    return sheets, statewide, facts, api, catalog


def test_south_dakota_reconciles_candidates_by_name_and_never_uses_vote_center_denominators():
    inputs = south_dakota_fixture()
    # Statewide candidate order may differ from every county workbook.
    inputs[1]["totals"] = dict(reversed(list(inputs[1]["totals"].items())))
    rows, statistics, audit = sd_review.review(*inputs)
    assert len(rows) == len(statistics) == 3
    assert sum(r["democratic_votes"] for r in rows) == 35
    assert sum(r["republican_votes"] for r in rows) == 85
    assert statistics[0]["reported_pct"] == 65 and statistics[1]["reported_pct"] == 45
    assert statistics[2]["registered"] == 300 and statistics[2]["reported_pct"] is None
    assert statistics[2]["denominator_scope"] == "county_repeated_at_vote_centers"
    assert audit["02"]["vote_center"]
    assert rows[0]["raw_precinct"] == "Precinct 1 "


def test_south_dakota_preserves_duplicate_name_rows_without_cross_source_pairing():
    sheets, statewide, facts, api, catalog = south_dakota_fixture()
    sheets["01"]["records"][1]["label"] = "Precinct 1"
    facts["counties"][0]["records"][1]["label"] = "Precinct 1"
    rows, statistics, audit = sd_review.review(sheets, statewide, facts, api, catalog)
    assert len(rows) == len({r["key"] for r in rows}) == 3
    assert len(statistics) == len({r["key"] for r in statistics}) == 3
    assert all(r["reported_pct"] is None for r in statistics)
    assert all("ambiguous_reporting_unit_name_no_cross_source_row_pairing" in r["quality_flags"]
               for r in statistics[:2])
    assert {r["key"] for r in rows[:2]}.isdisjoint(r["key"] for r in statistics[:2])
    assert audit["01"]["duplicate_reporting_labels"] == ["Precinct 1"]


@pytest.mark.parametrize("problem", ["statewide_total", "candidate", "county_scope", "ballot_total",
                                     "missing_count", "vote_center_scope", "unknown_party",
                                     "missing_vote_center_marker"])
def test_south_dakota_rejects_unreconciled_or_ambiguous_source_data(problem):
    sheets, statewide, facts, api, catalog = south_dakota_fixture()
    if problem == "statewide_total":
        statewide["records"][0]["votes"]["D Candidate"] += 1
    elif problem == "candidate":
        sheets["01"]["records"][0]["votes"]["Unknown Candidate"] = 1
    elif problem == "county_scope":
        api[0]["CountyID"] = "03"
    elif problem == "ballot_total":
        api[0]["calcVoterTurnout"] += 1
    elif problem == "missing_count":
        facts["counties"][0]["records"][0]["ballots"] = None
    elif problem == "vote_center_scope":
        facts["counties"][1]["records"][0]["registered"] = 22
    elif problem == "missing_vote_center_marker":
        api[1]["CountyName"] = "Center"
    else:
        catalog[0]["Party"] = "Unverified Party"
    with pytest.raises(ValueError):
        sd_review.review(sheets, statewide, facts, api, catalog)


def test_south_dakota_keeps_ballot_and_registration_disagreements_without_repairing_rates():
    sheets, statewide, facts, api, catalog = south_dakota_fixture()
    facts["counties"][0]["records"][0]["ballots"] = 40
    api[0]["calcVoterTurnout"] = 85
    api[0]["Voters"] = 201
    rows, statistics, audit = sd_review.review(sheets, statewide, facts, api, catalog)
    assert rows[0]["contest_votes"] == 60 and statistics[0]["ballots"] == 40
    assert statistics[0]["reported_pct"] is None
    assert "house_votes_exceed_separately_reported_ballots" in statistics[0]["quality_flags"]
    assert "county_registration_disagrees_with_api" in statistics[1]["quality_flags"]
    assert audit["01"]["registration_disagrees"]


def test_south_dakota_extracts_every_displayed_fact_without_copying_page_frontend():
    raw = b'''<input name="ctl00$hidElectionType" value="General">
      <input name="ctl00$hidElectionDate" value="11/3/2026">
      <div><div class="turnout-results-box-a"><h1>First</h1><input countyid="01"></div></div>
      <div id="countyturnout01"><div class="odd"><div class="county-precinct">Precinct 1</div>
      <div class="county-cast"><span>1,234</span></div>
      <div class="county-counted"><span>2,000</span></div></div></div><script>unrelated_code()</script>'''
    facts = sd_review.turnout_facts(raw)
    row = facts["counties"][0]["records"][0]
    assert row["ballots"] == 1234 and row["registered"] == 2000
    assert "unrelated_code" not in str(facts)
    with pytest.raises(ValueError):
        sd_review.turnout_facts(raw.replace(b"11/3/2026", b"6/2/2026"))
    with pytest.raises(ValueError):
        sd_review.turnout_facts(raw.replace(b"1,234", b""))


def idaho_fixture():
    from collections import Counter

    text = lambda value: [dict(languageId="en", text=value)]
    metadata = dict(election=dict(id=id_review.ELECTION, jurisdictionId=id_review.JURISDICTION,
        electionDate="2026-11-03", isPrimary=False, isProduction=True,
        name=text("General Election - November 3, 2026")),
        voterRegistration=[dict(localityName=text("First County"), total=200),
                           dict(localityName=text("Second County"), total=100)], ballotItems=[])
    precincts, ballots, summary = [], [], Counter()
    for district, county, identifiers in [(1, "First County", ["001", "002"]), (2, "Second County", ["003"])]:
        candidates = [dict(nativeId=f"{party}{district}", name=text(f"{party} candidate {district}"),
            party=dict(abbreviation=party), voteCount=votes * len(identifiers))
            for party, votes in [("DEM", 20), ("REP", 7), ("IND", 1)]]
        metadata["ballotItems"].append(dict(name=text(f"United States Representative District {district}"),
            voteFor=text("Vote for 1"), voteTotal=28 * len(identifiers),
            summaryResults=dict(ballotOptions=candidates)))
        for precinct in identifiers:
            options = [(c["name"][0]["text"], c["nativeId"], id_review.PARTIES[c["party"]["abbreviation"]],
                        c["voteCount"] // len(identifiers)) for c in candidates]
            options += [("Ballots Cast", "", None, 30), ("Over Votes", "", None, 1), ("Under Votes", "", None, 1)]
            for name, choice, party, votes in options:
                row = (county, f"United States Representative District {district}", f"usrep{district}",
                       name, choice, party, votes, 1)
                precincts.append((precinct,) + row)
                summary[row[:6] + (row[7],)] += votes
            ballots.append((county, precinct, 95, 5, 100, 30, "30 %"))
    summary = [key[:6] + (votes, key[6]) for key, votes in summary.items()]
    return summary, precincts, ballots, metadata


def test_idaho_reconciles_candidates_statistics_and_separate_participation():
    rows, statistics, audit = id_review.idaho_results(*idaho_fixture())
    assert len(rows) == len(statistics) == 3
    assert rows[0]["precinct"] == "001" and rows[0]["contest_votes"] == 28
    assert rows[0]["other_votes"] == 1 and rows[0]["reported_ballots"] == 30
    assert rows[0]["margin_pp"] == pytest.approx(1300 / 28)
    assert all(r["reported_pct"] == 30 and r["quality_flags"] == [] for r in statistics)
    assert audit["original_precinct_rows"] == 18 and not audit["county_registration_disagreements"]


def test_idaho_accepts_only_explicit_terminal_party_label_variants():
    summary, precincts, ballots, metadata = idaho_fixture()
    summary = [r[:5] + (r[5] + " Party" if r[5] else r[5],) + r[6:] for r in summary]
    precincts = [r[:6] + (r[6] + " Party" if r[6] else r[6],) + r[7:] for r in precincts]
    rows, statistics, _ = id_review.idaho_results(summary, precincts, ballots, metadata)
    assert sum(r["contest_votes"] for r in rows) == 84
    assert all(r["reported_pct"] == 30 for r in statistics)


@pytest.mark.parametrize("problem", ["duplicate", "missing", "county_total", "district_total",
                                     "candidate_name", "party", "wrong_election", "negative", "noninteger"])
def test_idaho_rejects_bad_candidate_scope_and_counts(problem):
    summary, precincts, ballots, metadata = idaho_fixture()
    if problem == "duplicate":
        precincts.append(precincts[0])
    elif problem == "missing":
        precincts.pop(0)
    elif problem == "county_total":
        row = list(summary[0]); row[6] += 1; summary[0] = tuple(row)
    elif problem == "district_total":
        metadata["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["voteCount"] += 1
        metadata["ballotItems"][0]["voteTotal"] += 1
    elif problem == "candidate_name":
        metadata["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["name"][0]["text"] = "Different"
    elif problem == "party":
        metadata["ballotItems"][0]["summaryResults"]["ballotOptions"][0]["party"]["abbreviation"] = "REP"
    elif problem == "wrong_election":
        metadata["election"]["electionDate"] = "2024-11-05"
    else:
        row = list(precincts[0]); row[7] = -1 if problem == "negative" else 20.5; precincts[0] = tuple(row)
    with pytest.raises(ValueError):
        id_review.idaho_results(summary, precincts, ballots, metadata)


def test_idaho_withholds_entire_pooled_county_without_allocating_ballots():
    summary, precincts, ballots, metadata = idaho_fixture()
    precincts = [("Absentee",) + r[1:] if r[0] == "002" else r for r in precincts]
    ballots = [(r[0], "Absentee") + r[2:] if r[1] == "002" else r for r in ballots]
    rows, statistics, audit = id_review.idaho_results(summary, precincts, ballots, metadata)
    assert audit["pooled_counties"] == ["First County"]
    assert sum(r["ballots"] for r in statistics) == 90
    assert [r["reported_pct"] for r in statistics] == [None, None, 30]
    assert rows[1]["reporting_unit_kind"] == "pooled_absentee_or_early_unit"


def test_idaho_county_registration_disagreement_withholds_only_affected_county():
    summary, precincts, ballots, metadata = idaho_fixture()
    metadata["voterRegistration"][0]["total"] = 201
    _, statistics, audit = id_review.idaho_results(summary, precincts, ballots, metadata)
    assert [r["reported_pct"] for r in statistics] == [None, None, 30]
    assert audit["county_registration_disagreements"] == [dict(county="First County", workbook=200, api=201)]


@pytest.mark.parametrize("problem", ["small", "components", "over_registration", "ballot_mismatch",
                                     "duplicate_ballot", "missing_ballot", "missing_statistic"])
def test_idaho_missing_and_inconsistent_ballot_denominators(problem):
    summary, precincts, ballots, metadata = idaho_fixture()
    row = list(ballots[0])
    if problem == "small":
        row[2:5] = [20, 0, 20]
    elif problem == "components":
        row[2] = 94
    elif problem == "over_registration":
        row[2:5] = [24, 5, 29]
    elif problem == "ballot_mismatch":
        row[5] = 29
    elif problem == "duplicate_ballot":
        ballots.append(ballots[0])
    elif problem == "missing_ballot":
        ballots.pop()
    elif problem == "missing_statistic":
        precincts = [r for r in precincts if r[4] != "Under Votes"]
        summary = [r for r in summary if r[3] != "Under Votes"]
    ballots[0] = tuple(row)
    if problem in {"small", "components", "over_registration", "ballot_mismatch"}:
        _, statistics, _ = id_review.idaho_results(summary, precincts, ballots, metadata)
        assert statistics[0]["reported_pct"] is None
        assert statistics[0]["ballots"] == (29 if problem == "ballot_mismatch" else 30)
        assert statistics[0]["house_contest_ballots"] == 30
        assert statistics[-1]["reported_pct"] == 30
    else:
        with pytest.raises(ValueError):
            id_review.idaho_results(summary, precincts, ballots, metadata)


def idaho_map_fixture():
    rows, statistics, _ = id_review.idaho_results(*idaho_fixture())
    features = []
    for i, row in enumerate(rows):
        x, y = -116 + 2 * i, 43
        features.append(dict(attributes=dict(OBJECTID=i + 1, COUNTY=row["county"][:-7],
            PCNCT_NME="000" + row["precinct"], STATE_PR_ID=f"reference-{i}",
            CNTY_PR_ID=f"unrelated-{i}", CONGR_DIST=row["congressional_district"],
            ACTIVE="Y", DATE_ACT=1704067200000, DATE_INACT=32503680000000),
            geometry=dict(rings=[[[x, y], [x, y + 1], [x + 1, y + 1], [x + 1, y], [x, y]]])))
    return rows, statistics, dict(geometryType="esriGeometryPolygon",
        spatialReference=dict(wkid=4326), features=features)


def test_idaho_map_preserves_counts_and_source_defined_participation_without_decoding_ids():
    rows, statistics, boundary = idaho_map_fixture()
    mapped, audit = id_maps.mapped_precincts(rows, statistics, boundary)
    assert len(mapped) == 3 and all(c["exact"] for c in audit["counties"].values())
    for feature, row in zip(mapped, rows):
        p = feature["properties"]
        assert all(p[field] == value for field, value in row.items())
        assert p["participation"]["measure"] == "reported_ballots_and_registration"
        assert p["participation"]["reported_pct"] == 30
        assert p["participation"]["ballots"] == 30
        assert p["participation"]["registered"] == 100
        assert p["reference_county_precinct_id"].startswith("unrelated-")


@pytest.mark.parametrize("problem", ["name", "district", "invalid_ring", "future"])
def test_idaho_map_withholds_whole_county_for_scope_district_geometry_or_date_conflicts(problem):
    rows, statistics, boundary = idaho_map_fixture()
    feature = boundary["features"][0]
    if problem == "name":
        feature["attributes"]["PCNCT_NME"] = "Different precinct"
    elif problem == "district":
        feature["attributes"]["CONGR_DIST"] = "2"
    elif problem == "future":
        feature["attributes"]["DATE_ACT"] = id_maps.ELECTION_MS + 1
    else:
        feature["geometry"]["rings"][0].pop()
    mapped, audit = id_maps.mapped_precincts(rows, statistics, boundary)
    assert len(mapped) == 1 and mapped[0]["properties"]["county"] == "Second County"
    assert not audit["counties"]["First"]["exact"]
    assert audit["counties"]["Second"]["exact"]


def test_idaho_map_uses_election_activity_interval_not_only_current_active_flag():
    rows, statistics, boundary = idaho_map_fixture()
    boundary["features"][0]["attributes"]["ACTIVE"] = "N"
    mapped, _ = id_maps.mapped_precincts(rows, statistics, boundary)
    assert len(mapped) == 3


def test_idaho_map_audits_overlaps_against_unmatched_reference_features_too():
    rows, statistics, boundary = idaho_map_fixture()
    boundary["features"][0]["attributes"]["PCNCT_NME"] = "Unmatched"
    boundary["features"][0]["geometry"] = boundary["features"][2]["geometry"]
    mapped, audit = id_maps.mapped_precincts(rows, statistics, boundary)
    assert not mapped and len(audit["all_reference_overlap_pairs"]) == 1
    assert all(not c["exact"] for c in audit["counties"].values())


def test_idaho_map_retains_pooled_units_in_downloads_without_allocating_them():
    rows, statistics, boundary = idaho_map_fixture()
    pooled = dict(rows[0], key="ID|First County|Absentee", precinct="Absentee",
                  reporting_unit_kind="pooled_absentee_or_early_unit")
    rows.append(pooled)
    statistics.append(dict(statistics[0], key=pooled["key"], precinct="Absentee",
        reported_pct=None, quality_flags=["pooled_nongeographic_reporting_unit"]))
    mapped, audit = id_maps.mapped_precincts(rows, statistics, boundary)
    assert len(mapped) == 3 and audit["reporting_units"] == 4
    assert audit["excluded_pooled_reporting_units"] == audit["withheld_units"] == [pooled["key"]]


@pytest.mark.parametrize("problem", ["duplicate_feature", "ambiguous_name", "truncated",
                                     "projection", "missing_statistics"])
def test_idaho_map_rejects_duplicate_or_incomplete_sources(problem):
    rows, statistics, boundary = idaho_map_fixture()
    if problem == "duplicate_feature":
        boundary["features"].append(boundary["features"][0])
    elif problem == "ambiguous_name":
        boundary["features"][1]["attributes"]["PCNCT_NME"] = "0001"
    elif problem == "truncated":
        boundary["exceededTransferLimit"] = True
    elif problem == "projection":
        boundary["spatialReference"]["wkid"] = 102605
    else:
        statistics.pop()
    with pytest.raises(ValueError):
        id_maps.mapped_precincts(rows, statistics, boundary)


def vt_fixture():
    towns = [dict(townId=1, townName="FIRST"), dict(townId=2, townName="SECOND")]
    districts, nodes, compact = [], [], []
    for tid, district in [(1, "A"), (2, "A"), (2, "B")]:
        town = towns[tid - 1]["townName"]
        districts.append(dict(townId=tid, townName=town, repDistrict=district,
                              senateDistrict="S", countyId=1, countyName="EXAMPLE"))
        rc = [dict(cid=cid, cn=name, pn=party, vc=votes) for cid, name, party, votes in
              [(1, "A", "DEMOCRATIC", 7), (2, "B", "REPUBLICAN", 3), (3, "C", "INDEPENDENT", 2)]]
        nodes.append(dict(tid=tid, tn=town, repd=district, send="S", vf=1, sc=15, sv=1, bv=1,
                          rc=rc, wc=[dict(cid=0, cn="OTHER WRITE-IN", pn=None, vc=1)]))
        compact.append(dict(tn=town, repd=district, send="S", vc1=7, vc2=3, vc3=2, ovc=3))
    parent = json.loads(json.dumps(nodes[0]))
    parent.update(tid=0, tn="STATE WIDE", sc=45, sv=3, bv=3)
    for candidate in parent["rc"] + parent["wc"]:
        candidate["vc"] *= 3
    source = dict(d=[dict(pid=0, o=[dict(oid=4, on="REPRESENTATIVE TO CONGRESS",
        vf=1, cid1=1, cid2=2, cid3=3, cs=nodes + [parent], cd=compact)])])
    metadata = dict(electionDetails=dict(electionId=7100, electionGuid=vt_review.GUID,
        electionName="2026 GENERAL ELECTION", electionDate="2026-11-03T00:00:00",
        isGeneralElection=True, isOfficial=False), towns=towns, townDistricts=districts)
    turnout = dict(d=[dict(tid=tid, tn=town["townName"], tvr=100 * tid, tvc=15 * tid,
        tabs=0, tdis=tid, tdisr=tid, hl=[]) for tid, town in enumerate(towns, 1)])
    return source, metadata, turnout


def test_vt_splits_reconcile_without_relabeling_municipal_turnout_as_precinct_data():
    rows, statistics = vt_review.vt_results(*vt_fixture())
    assert len(rows) == 3 and len({r["key"] for r in rows}) == 3
    assert rows[0]["contest_votes"] == 13 and rows[0]["reported_contest_total"] == 15
    assert rows[0]["other_votes"] == 3 and rows[0]["margin_pp"] == pytest.approx(400 / 13)
    assert all(r["reporting_unit_kind"] == "town_legislative_split" for r in rows)
    assert len(statistics) == 2 and statistics[1]["ballots"] == 30
    assert statistics[1]["registered_turnout_pct"] == 15
    assert statistics[1]["reporting_unit_kind"] == "municipality"
    assert sum(r["ballots"] for r in statistics) == 45


def test_vt_municipal_discrepancies_withhold_rates_without_modifying_counts():
    source, metadata, turnout = vt_fixture()
    turnout["d"][1]["tvc"] = 29
    rows, statistics = vt_review.vt_results(source, metadata, turnout)
    assert sum(r["reported_contest_total"] for r in rows) == 45
    assert statistics[1]["ballots"] == 29 and statistics[1]["registered_turnout_pct"] is None
    assert statistics[0]["registered_turnout_pct"] == 15
    assert "house_contest_total_differs_from_municipal_votes_cast" in statistics[1]["quality_flags"]


def test_vt_sparse_named_writeins_keep_source_identity_and_party():
    source, metadata, turnout = vt_fixture()
    office = source["d"][0]["o"][0]
    named = dict(cid=40, cn="A", pn=None, vc=2)
    office["cs"][0]["wc"].append(named)
    office["cs"][-1]["wc"].append(named)
    office["cs"][0]["sc"] += 2
    office["cs"][-1]["sc"] += 2
    office["cd"][0]["ovc"] += 2
    turnout["d"][0]["tvc"] += 2
    rows, _ = vt_review.vt_results(source, metadata, turnout)
    assert rows[0]["democratic_votes"] == 7 and rows[0]["other_votes"] == 5
    assert sum(r["other_votes"] for r in rows) == 11


@pytest.mark.parametrize("change", ["duplicate", "missing_count", "wrong_election", "wrong_split", "wrong_rollup"])
def test_vt_rejects_ambiguous_units_missing_counts_and_inconsistent_rollups(change):
    source, metadata, turnout = vt_fixture()
    office = source["d"][0]["o"][0]
    if change == "duplicate":
        office["cs"].insert(0, office["cs"][0])
    elif change == "missing_count":
        office["cs"][0]["rc"][0]["vc"] = None
    elif change == "wrong_election":
        metadata["electionDetails"]["electionDate"] = "2024-11-05T00:00:00"
    elif change == "wrong_split":
        office["cs"][0]["send"] = "OTHER"
    else:
        office["cs"][-1]["rc"][0]["vc"] += 1
        office["cs"][-1]["sc"] += 1
    with pytest.raises(ValueError):
        vt_review.vt_results(source, metadata, turnout)


@pytest.mark.parametrize("districts,reported", [(1, 0), (2, 2)])
def test_vt_incomplete_or_different_municipal_district_scope_withholds_the_rate(districts, reported):
    source, metadata, turnout = vt_fixture()
    turnout["d"][0].update(tdis=districts, tdisr=reported)
    _, statistics = vt_review.vt_results(source, metadata, turnout)
    assert statistics[0]["registered_turnout_pct"] is None
    assert "incomplete_or_different_district_scope" in statistics[0]["quality_flags"]


def vt_boundary_fixture():
    features = []
    for oid, town, district, west, tid in [
            (1, "FIRST", "A", -73, 1), (2, "SECOND", "A", -72.7, 2),
            (3, "SECOND", "B", -72.5, 2)]:
        features.append(dict(attributes=dict(OBJECTID=oid, TOWN=town, HOUSE_NAME=district,
            SEN_NAME="S", TOWN_GEOID=f"50001{tid:05}", CNTY="1"),
            geometry=dict(rings=[[[west, 43], [west, 43.1], [west + .1, 43.1],
                                  [west + .1, 43], [west, 43]]])))
    return dict(geometryType="esriGeometryPolygon", spatialReference=dict(wkid=4326), features=features)


def test_vt_maps_dissolve_wards_once_without_allocating_municipal_participation():
    rows, _ = vt_review.vt_results(*vt_fixture())
    boundary = vt_boundary_fixture()
    extra = json.loads(json.dumps(boundary["features"][0]))
    extra["attributes"]["OBJECTID"] = 4
    for point in extra["geometry"]["rings"][0]:
        point[0] += .1
    boundary["features"].append(extra)
    mapped, audit = vt_maps.mapped_splits(rows, boundary)
    assert len(mapped) == 3 and sum(f["properties"]["contest_votes"] for f in mapped) == 39
    first = mapped[0]
    assert first["properties"]["source_object_ids"] == [1, 4]
    assert nd_maps.shape(first["geometry"]).area == pytest.approx(.02)
    assert first["properties"]["reporting_unit_kind"] == "town_legislative_split"
    assert "participation" not in first["properties"] and not audit["withheld_units"]


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_vt_maps_require_the_entire_town_split_set(change):
    rows, _ = vt_review.vt_results(*vt_fixture())
    boundary = vt_boundary_fixture()
    if change == "missing":
        boundary["features"].pop()
    else:
        extra = json.loads(json.dumps(boundary["features"][-1]))
        extra["attributes"].update(OBJECTID=4, HOUSE_NAME="C")
        for point in extra["geometry"]["rings"][0]:
            point[0] += .2
        boundary["features"].append(extra)
    mapped, audit = vt_maps.mapped_splits(rows, boundary)
    assert len(mapped) == 1 and mapped[0]["properties"]["town"] == "FIRST"
    assert not audit["towns"]["SECOND"]["exact"] and len(audit["withheld_units"]) == 2


def test_vt_maps_normalize_district_separators_but_never_infer_town_aliases():
    rows, _ = vt_review.vt_results(*vt_fixture())
    boundary = vt_boundary_fixture()
    rows[0].update(house_district="CHITTENDEN-1", senate_district="CHITTENDEN-CENTRAL_")
    boundary["features"][0]["attributes"].update(
        HOUSE_NAME="Chittenden 1", SEN_NAME="Chittenden Central")
    mapped, _ = vt_maps.mapped_splits(rows, boundary)
    assert len(mapped) == 3
    rows[0]["town"] = "FIRST CITY"
    mapped, audit = vt_maps.mapped_splits(rows, boundary)
    assert len(mapped) == 2 and not audit["towns"]["FIRST CITY"]["exact"]


@pytest.mark.parametrize("unreported", [False, True])
def test_vt_maps_withhold_whole_towns_for_overlapping_reference_units(unreported):
    rows, _ = vt_review.vt_results(*vt_fixture())
    boundary = vt_boundary_fixture()
    if unreported:
        extra = json.loads(json.dumps(boundary["features"][0]))
        extra["attributes"].update(OBJECTID=4, TOWN="UNREPORTED", TOWN_GEOID="5000100003")
        boundary["features"].append(extra)
    else:
        boundary["features"][1]["geometry"] = boundary["features"][0]["geometry"]
    mapped, audit = vt_maps.mapped_splits(rows, boundary)
    assert len(mapped) == (2 if unreported else 0)
    assert audit["overlap_pairs"] and not audit["towns"]["FIRST"]["exact"]
    if not unreported:
        assert not audit["towns"]["SECOND"]["exact"]


def test_vt_maps_reject_overlapping_ward_parts_in_the_same_reporting_split():
    rows, _ = vt_review.vt_results(*vt_fixture())
    boundary = vt_boundary_fixture()
    extra = json.loads(json.dumps(boundary["features"][0]))
    extra["attributes"]["OBJECTID"] = 4
    boundary["features"].append(extra)
    mapped, audit = vt_maps.mapped_splits(rows, boundary)
    assert len(mapped) == 2 and audit["internal_overlaps"]
    assert not audit["towns"]["FIRST"]["exact"]


@pytest.mark.parametrize("change", ["duplicate", "wrong_geoid", "wrong_county", "projection", "truncated"])
def test_vt_maps_reject_incomplete_or_inconsistent_geographic_identity(change):
    rows, _ = vt_review.vt_results(*vt_fixture())
    boundary = vt_boundary_fixture()
    if change == "duplicate":
        boundary["features"].append(boundary["features"][0])
    elif change == "wrong_geoid":
        boundary["features"][0]["attributes"]["TOWN_GEOID"] = "5100100001"
    elif change == "wrong_county":
        boundary["features"][0]["attributes"]["CNTY"] = "3"
    elif change == "projection":
        boundary["spatialReference"]["wkid"] = 3857
    else:
        boundary["exceededTransferLimit"] = True
    with pytest.raises(ValueError):
        vt_maps.mapped_splits(rows, boundary)


def test_vt_maps_reject_reporting_identity_collisions_after_normalization():
    rows, _ = vt_review.vt_results(*vt_fixture())
    rows.append(dict(rows[0], house_district="A_"))
    with pytest.raises(ValueError, match="collide"):
        vt_maps.mapped_splits(rows, vt_boundary_fixture())


def nd_boundary_fixture():
    def part(object_id, west):
        return dict(attributes=dict(OBJECTID=object_id, CountyID=38001, CountyName="Adams",
                                    Precinct="013901", PPartID="0139010" + str(object_id)),
                    geometry=dict(rings=[[[west, 46], [west, 47], [west + 1, 47],
                                          [west + 1, 46], [west, 46]]]))
    return dict(geometryType="esriGeometryPolygon", spatialReference=dict(wkid=4326),
                features=[part(1, -103), part(2, -102)])


def test_nd_maps_dissolve_splits_without_duplicating_votes_or_inventing_turnout():
    rows, stats = nd_review.nd_results(*nd_fixture())
    mapped, audit = nd_maps.mapped_precincts(rows, stats, nd_boundary_fixture())
    assert len(mapped) == 1 and mapped[0]["properties"]["contest_votes"] == 100
    assert nd_maps.shape(mapped[0]["geometry"]).area == pytest.approx(2)
    assert mapped[0]["properties"]["source_object_ids"] == [1, 2]
    assert mapped[0]["properties"]["participation"]["denominator"] is None
    assert audit["counties"]["38001"]["exact"]


def test_nd_maps_withhold_whole_counties_for_wrong_parent_or_reporting_sets():
    rows, stats = nd_review.nd_results(*nd_fixture())
    for field, value in [("CountyID", 30859), ("Precinct", "01390")]:
        boundary = nd_boundary_fixture()
        boundary["features"][0]["attributes"][field] = value
        mapped, audit = nd_maps.mapped_precincts(rows, stats, boundary)
        assert mapped == [] and not audit["counties"]["38001"]["exact"]
    boundary = nd_boundary_fixture()
    boundary["features"].append(boundary["features"][0])
    with pytest.raises(ValueError, match="Duplicate"):
        nd_maps.mapped_precincts(rows, stats, boundary)
    boundary["exceededTransferLimit"] = True
    with pytest.raises(ValueError, match="Incomplete"):
        nd_maps.mapped_precincts(rows, stats, boundary)


def test_nd_native_ring_roles_keep_holes_and_reject_substantive_repairs():
    outer = [[-103, 46], [-103, 48], [-101, 48], [-101, 46], [-103, 46]]
    hole = [[-102.5, 46.5], [-101.5, 46.5], [-101.5, 47.5], [-102.5, 47.5], [-102.5, 46.5]]
    polygon, repair = nd_maps.esri_polygon([outer, hole])
    assert polygon.area == pytest.approx(3) and repair is None
    with pytest.raises(ValueError, match="changes polygon area"):
        nd_maps.esri_polygon([[[-103, 46], [-101, 48], [-103, 48], [-101, 46], [-103, 46]]])


def test_nd_maps_withhold_counties_with_overlapping_reporting_units():
    rows, stats = nd_review.nd_results(*nd_fixture())
    rows.append(dict(rows[0], key="ND|38001|3902", precinct="3902"))
    stats.append(dict(stats[0], key="ND|38001|3902", precinct="3902", precinct_name="013902"))
    boundary = nd_boundary_fixture()
    boundary["features"][1]["attributes"]["Precinct"] = "013902"
    boundary["features"][1]["geometry"] = boundary["features"][0]["geometry"]
    mapped, audit = nd_maps.mapped_precincts(rows, stats, boundary)
    assert mapped == [] and not audit["counties"]["38001"]["exact"]
    assert len(audit["source_cross_precinct_overlaps"]) == 1


def test_nd_maps_mask_ambiguous_strips_without_reallocating_votes():
    rows, stats = nd_review.nd_results(*nd_fixture())
    rows.append(dict(rows[0], key="ND|38001|3902", precinct="3902"))
    stats.append(dict(stats[0], key="ND|38001|3902", precinct="3902", precinct_name="013902"))
    boundary = nd_boundary_fixture()
    boundary["features"][1]["attributes"]["Precinct"] = "013902"
    boundary["features"][1]["geometry"]["rings"] = [
        [[-102.5, 46], [-102.5, 47], [-101.5, 47], [-101.5, 46], [-102.5, 46]]]
    mapped, audit = nd_maps.mapped_precincts(rows, stats, boundary)
    assert len(mapped) == 2 and len(audit["masked_reporting_units"]) == 2
    polygons = [nd_maps.shape(f["geometry"]) for f in mapped]
    assert sum(p.area for p in polygons) == pytest.approx(1)
    assert polygons[0].intersection(polygons[1]).area == 0
    assert [f["properties"]["contest_votes"] for f in mapped] == [100, 100]
    assert all("Counts still describe the entire reporting unit" in f["properties"]["boundary_provenance"]
               for f in mapped)


def nd_fixture():
    choices = [dict(Name=name, PartyID=party, TotalVotes=votes,
                    Votes=[dict(VoteTypeID="1", Votes=votes)])
               for name, party, votes in [("A", "DEM", 70), ("B", "REP", 30), ("write-in", "NON", 0)]]
    precinct = dict(LocationID="3901", LocationName="013901", TotalVotes=100, Choices=choices)
    county = dict(LocationID="38001", LocationName="Adams", TotalVotes=100,
                  Choices=choices, Locations={"3901": precinct})
    house = dict(ContestID="22055", ContestName="Representative in Congress",
                 TotalVotes=100, Choices=choices, TotalPrecincts=1, PrecinctsReporting=1,
                 Locations={"38001": county})
    ballot = dict(LocationID="3901", TotalBallotsCast=110,
                  BallotsCast=[dict(VoteTypeID="1", BallotsCast=110)])
    county_ballot = dict(ballot, LocationID="38001", Locations={"3901": ballot})
    turnout = dict(ballot, TotalPrecincts=1, PrecinctsReporting=1, Locations={"38001": county_ballot})
    source = dict(ElectionData=dict(ElectionID="348", IsOfficial=False),
                  TurnoutData=turnout, ContestData=[house])
    identity = dict(electionID="348", isOfficial=False, turnout=dict(totalBallotsCast=110),
                    response=dict(id="348", name="2026 General Election", date="2026-11-03T00:00:00",
                                  parties={"DEM": {}, "REP": {}, "NON": {}}))
    return json.loads(json.dumps(source)), identity


def test_nd_counts_reconcile_without_relabeling_candidate_votes_or_borrowing_denominators():
    source, identity = nd_fixture()
    rows, participation = nd_review.nd_results(source, identity)
    assert rows[0]["contest_votes"] == 100 and rows[0]["margin_pp"] == 40
    assert participation[0]["ballots"] == 110
    assert participation[0]["denominator"] is None and participation[0]["reported_pct"] is None
    precinct = source["ContestData"][0]["Locations"]["38001"]["Locations"]["3901"]
    precinct["Choices"][0]["TotalVotes"] = precinct["Choices"][0]["Votes"][0]["Votes"] = 71
    precinct["TotalVotes"] = 101
    with pytest.raises(ValueError, match="counts do not reconcile"):
        nd_review.nd_results(source, identity)


def test_nd_explicit_zero_buckets_are_not_missing_counts_and_inconsistent_modes_are_rejected():
    source, _ = nd_fixture()
    house = source["ContestData"][0]
    zero = house["Choices"][-1]
    del zero["TotalVotes"]
    assert nd_review.candidate_totals(house)[("write-in", "NON")] == 0
    del zero["Votes"][0]["Votes"]
    with pytest.raises(ValueError, match="do not substitute zero"):
        nd_review.candidate_totals(house)
    source, identity = nd_fixture()
    source["ContestData"][0]["Choices"][0]["Votes"].append(dict(VoteTypeID="2", Votes=70))
    with pytest.raises(ValueError, match="one explicit All"):
        nd_review.nd_results(source, identity)
    source, identity = nd_fixture()
    identity["response"]["date"] = "2024-11-05T00:00:00"
    with pytest.raises(ValueError, match="election identity"):
        nd_review.nd_results(source, identity)


def test_source_review_accepts_manifest_provenance_without_claiming_mapped_participation(tmp_path, monkeypatch):
    states = tmp_path / "public/voter-participation/data"
    states.mkdir(parents=True)
    (states / "states.geojson").write_text(
        (precinct_coverage.ROOT / "public/voter-participation/data/states.geojson").read_text())
    review = dict(year=2026, state_code="ND", candidate_results="acquired_reconciled",
                  boundaries="reference_crosswalk_pending", join="withheld",
                  validation="counts_passed_map_withheld", publication="full_counts_download_only",
                  participation="acquired_precinct_ballot_counts", next_action="Review polygon splits",
                  source_url="full-results.json", boundary_source="manifest.json",
                  notes="Counts only", complete_download_url="full.zip")
    (tmp_path / "review.json").write_text(json.dumps(review))
    (tmp_path / "public/precinct-results.json").write_text(json.dumps({"source_reviews": ["review.json"]}))
    monkeypatch.setattr(precinct_coverage, "ROOT", tmp_path)
    row = next(r for r in precinct_coverage.build_rows() if r["year"] == 2026 and r["state_code"] == "ND")
    assert row["publication"] == "full_counts_download_only" and row["join"] == "withheld"
    assert row["participation"] == "acquired_precinct_ballot_counts"
    assert row["boundary_source"] == "manifest.json" and row["complete"] == "no"
    review.update(state_code="VT", boundary_source="", sources={"election.json": "election.json"})
    (tmp_path / "review.json").write_text(json.dumps(review))
    row = next(r for r in precinct_coverage.build_rows() if r["year"] == 2026 and r["state_code"] == "VT")
    assert row["boundary_source"] == "" and row["join"] == "withheld"
    review.update(state_code="ID")
    review.pop("sources")
    (tmp_path / "review.json").write_text(json.dumps(review))
    row = next(r for r in precinct_coverage.build_rows() if r["year"] == 2026 and r["state_code"] == "ID")
    assert row["boundary_source"] == "" and row["publication"] == "full_counts_download_only"


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


def test_multiyear_original_downloads_preserve_years_and_do_not_override_validated_map_scope():
    batch = dict(complete_download_url="full.zip", elections={str(year): dict(
        year=year, state_code="HI", original_files=9, original_bytes=1000,
        source_url="official", next_action="Reconcile and obtain boundaries",
        validation="complete_source_bytes_and_native_record_structure_verified")
        for year in (2024, 2022, 2020, 2018)})
    coverage = dict(partial=True, source_url="reviewed-map", next_action="Verify remaining precincts",
                    notes="Reviewed partial map")
    rows = precinct_coverage.build_rows({"coverage": {"2024": {"HI": coverage}}},
                                       published=True, source_batches=[batch])
    hi = {r["year"]: r for r in rows if r["state_code"] == "HI"}
    for year in (2022, 2020, 2018):
        assert hi[year]["candidate_results"] == "acquired_originals_review_pending"
        assert hi[year]["publication"] == "full_originals_download_only"
        assert hi[year]["validation"] == "complete_source_bytes_and_native_record_structure_verified"
        assert hi[year]["participation"] == "not_acquired" and hi[year]["complete"] == "no"
        assert "9 files, 1,000 uncompressed bytes" in hi[year]["notes"]
    assert hi[2024]["publication"] == "published_partial" and hi[2024]["results_source"] == "reviewed-map"
    assert hi[2024]["complete"] == "no"
    assert hi[2016]["publication"] == "not_published"


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
