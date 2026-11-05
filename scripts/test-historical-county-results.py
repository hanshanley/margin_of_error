import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("historical", Path(__file__).with_name("review-historical-county-results.py"))
historical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(historical)


def candidate(votes="10"):
    return dict(year="2024", office="house", state_po="NY", state_fips="36",
                county_fips="36001", district="20", stage="general", candidate="Candidate A",
                party="Democratic", party_group="DEM", votes=votes, source="native",
                quality_flag="")


def summary(dem="10", rep="0", other="0", total="10"):
    return dict(year="2024", office="house", state_po="NY", county_fips="36001",
                dem_votes=dem, rep_votes=rep, other_votes=other, total_votes=total, quality_flag="")


def test_fusion_lines_and_explicit_zero_other_party_remain_distinct():
    rows = [candidate(), {**candidate("3"), "party": "Working Families"},
            {**candidate("0"), "candidate": "Independent", "party": "Independent", "party_group": "OTHER"}]
    report, parties, accepted, audit = historical.reconcile(rows, [summary(dem="13", total="13")])
    assert audit["accepted_integer_counties"] == 1
    assert {(r["party"], r["votes"]) for r in parties} == {
        ("Democratic", 10), ("Working Families", 3), ("Independent", 0)}
    assert accepted == rows and report[0]["integer_counts_accepted"]


@pytest.mark.parametrize("votes", ["10.25", "", "-1"])
def test_invalid_vote_literal_withholds_entire_county_vector_without_rounding_or_zero_fill(votes):
    report, parties, accepted, audit = historical.reconcile([candidate(votes)], [summary()])
    assert not parties and not accepted
    assert audit["literal_vote_exceptions"][0]["votes"] == votes
    assert "noninteger_or_missing_votes" in report[0]["withheld_reasons"]


def test_summary_disagreement_is_withheld():
    report, parties, accepted, audit = historical.reconcile([candidate()], [summary(dem="11", total="11")])
    assert audit["arithmetic_matched_summaries"] == 0
    assert not parties and not accepted
    assert report[0]["withheld_reasons"] == "candidate_summary_disagreement"


def test_runoff_cannot_be_added_to_same_district_general_but_other_district_final_is_retained():
    general, runoff = candidate(), {**candidate(), "stage": "runoff"}
    report, parties, _, _ = historical.reconcile([general, runoff], [summary(dem="20", total="20")])
    assert "overlapping_general_and_runoff" in report[0]["withheld_reasons"] and not parties
    runoff["district"] = "21"
    report, parties, _, _ = historical.reconcile([general, runoff], [summary(dem="20", total="20")])
    assert report[0]["source_stages"] == "general;runoff"
    assert parties[0]["votes"] == 20


def test_duplicate_literal_party_line_is_not_silently_double_counted():
    report, parties, _, _ = historical.reconcile([candidate(), candidate()], [summary(dem="20", total="20")])
    assert report[0]["withheld_reasons"] == "duplicate_candidate_party_line" and not parties


def test_candidate_and_summary_scope_must_match():
    with pytest.raises(ValueError, match="identities differ"):
        historical.reconcile([candidate()], [])


def test_county_ledger_preserves_named_gaps_missingness_and_distinct_map_approval():
    report, _, _, _ = historical.reconcile([candidate()], [summary()])
    rows = historical.coverage(report,
        [dict(year="2024", office="house", state="NEW YORK")], [],
        {"coverage": {"NY": {"counties": 1}}}, {"NEW YORK": "NY"})
    ledger = {(row["year"], row["office"], row["state_code"]): row for row in rows}
    old = ledger[(2024, "house", "NY")]
    assert old["source_gap_records"] == 1 and old["integer_accepted_counties"] == 1
    assert old["county_candidate_maps"] == 0 and not old["fully_complete"]
    assert ledger[(2024, "house", "AK")]["source_counties"] == ""
    current = ledger[(2026, "house", "NY")]
    assert current["county_candidate_maps"] == 1 and not current["fully_complete"]
    assert ledger[(2026, "president", "NY")]["status"] == "no_regular_presidential_election"
