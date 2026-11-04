import csv
import importlib.util
import io
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
