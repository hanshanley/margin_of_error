import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location("house", Path(__file__).with_name("export-historical-house-counties.py"))
house = importlib.util.module_from_spec(spec)
spec.loader.exec_module(house)


def candidate(**changes):
    return dict(dict(year="2024", office="house", state_po="NY", state_fips="36",
        county_fips="36001", district="20", stage="general", candidate="A",
        party="Democratic", party_group="DEM", votes="10", source="native", quality_flag=""), **changes)


def run(rows, qa=None, origins=None):
    summaries, sources = {}, {}
    for row in rows:
        key = house.historical.key(row)
        summary = summaries.setdefault(key, dict(year=row["year"], office=row["office"], state_po=row["state_po"],
            county_fips=row["county_fips"], dem_votes=0, rep_votes=0, other_votes=0, total_votes=0, quality_flag=""))
        summary[{"DEM": "dem_votes", "REP": "rep_votes", "OTHER": "other_votes"}[row["party_group"]]] += int(row["votes"])
        summary["total_votes"] += int(row["votes"])
        source = sources.setdefault(house.source_key(row), {**{field: row[field] for field in house.SOURCE_FIELDS},
            "origin": (origins or {}).get(row["source"], "medsl"), "n_rows": 0, "license_status": "cc0_verified"})
        source["n_rows"] += 1
    for row in summaries.values():
        for field in ["dem_votes", "rep_votes", "other_votes", "total_votes"]:
            row[field] = str(row[field])
    for row in sources.values():
        row["n_rows"] = str(row["n_rows"])
    return house.build_tables(rows, list(summaries.values()), list(sources.values()), qa or [])


def test_fusion_lines_zeroes_and_literal_identity_flags_survive_without_false_state_totals():
    rows = [candidate(), candidate(party="Working Families", votes="3", quality_flag="surname_only"),
            candidate(candidate="Independent", party="Independent", party_group="OTHER", votes="0")]
    tables, audit = run(rows)
    assert tables["reviewed-candidate-party-lines.csv"] == rows
    assert {(r["party"], r["votes"]) for r in tables["reviewed-county-party-totals.csv"]} == {
        ("Democratic", 10), ("Working Families", 3), ("Independent", 0)}
    assert all(not r["fully_complete"] and r["scope"] == "sum_of_reviewed_counties_not_certified_state_total"
               for r in tables["reviewed-state-party-sums.csv"])
    assert audit["native_quality_flags"]["surname_only"] == 1
    coverage = tables["state-coverage.csv"]
    assert len(coverage) == 153 and all(not row["fully_complete"] and not row["map_approved"] for row in coverage)
    assert next(row for row in coverage if (row["year"], row["state_code"]) == ("2024", "AK"))[
        "status"] == "outside_selected_source_origin_or_missing"


def test_qa_exclusion_removes_entire_county_from_both_aggregates_but_keeps_all_raw_lines():
    good, bad = candidate(), candidate(county_fips="36005", candidate="B", votes="20")
    tables, audit = run([good, bad], [dict(sample="HE/SE", year="2024", cty_fips="36005", test="T2")])
    assert tables["source-candidate-party-lines.csv"] == [good, bad]
    assert tables["withheld-candidate-party-lines.csv"] == [bad]
    assert tables["reviewed-candidate-party-lines.csv"] == [good]
    assert tables["reviewed-state-party-sums.csv"][0]["votes"] == 10
    assert audit["reviewed_counties"] == 1


def test_nj_2022_is_withheld_even_without_a_machine_qa_record():
    row = candidate(year="2022", state_po="NJ", state_fips="34", county_fips="34033")
    tables, _ = run([row])
    assert tables["withheld-candidate-party-lines.csv"] == [row]
    assert not tables["reviewed-candidate-party-lines.csv"]
    assert not tables["reviewed-state-party-sums.csv"]
    assert "district_totals_repeated" in tables["county-review.csv"][0]["withheld_reasons"]


def test_yazoo_prose_only_exception_and_zero_padded_machine_fips_are_not_lost():
    yazoo = candidate(year="2022", state_po="MS", state_fips="28", county_fips="28163")
    alabama = candidate(state_po="AL", state_fips="01", county_fips="01001")
    tables, _ = run([yazoo, alabama], [dict(sample="HE", year="2024", cty_fips="1001", test="T1")])
    assert tables["withheld-candidate-party-lines.csv"] == [yazoo, alabama]
    assert not tables["reviewed-candidate-party-lines.csv"]


def test_office_origin_year_and_qa_office_are_scoped_independently():
    rows = [candidate(), candidate(office="senate", candidate="Senator"),
            candidate(year="2018", candidate="Earlier"),
            candidate(source="replacement", county_fips="36003", candidate="Official replacement")]
    tables, _ = run(rows, [dict(sample="SE", year="2024", cty_fips="36001", test="T1")],
                    {"replacement": "sos_file"})
    assert tables["source-candidate-party-lines.csv"] == [rows[0]]
    assert tables["reviewed-candidate-party-lines.csv"] == [rows[0]]
    assert not tables["withheld-candidate-party-lines.csv"]


def test_mixed_origin_partial_county_vector_is_withheld_instead_of_summed_as_complete():
    rows = [candidate(), candidate(source="replacement", party="Republican", party_group="REP", votes="8")]
    tables, _ = run(rows, origins={"replacement": "sos_file"})
    assert tables["source-candidate-party-lines.csv"] == [rows[0]]
    assert tables["withheld-candidate-party-lines.csv"] == [rows[0]]
    assert not tables["reviewed-county-party-totals.csv"]
    assert "candidate_summary_disagreement" in tables["county-review.csv"][0]["withheld_reasons"]


def test_2020_qa_exclusion_does_not_remove_other_years_or_other_counties():
    rows = [candidate(year="2020", state_po="MD", state_fips="24", county_fips="24027"),
            candidate(year="2024", state_po="MD", state_fips="24", county_fips="24027"),
            candidate(year="2020", state_po="MD", state_fips="24", county_fips="24001")]
    tables, audit = run(rows, [dict(sample="HE", year="2020", cty_fips="24027", test="T1")])
    assert tables["withheld-candidate-party-lines.csv"] == [rows[0]]
    assert tables["reviewed-candidate-party-lines.csv"] == rows[1:]
    scope = next(row for row in audit["years"] if row["year"] == "2020")
    assert scope["reviewed_counties"] == scope["withheld_counties"] == 1
