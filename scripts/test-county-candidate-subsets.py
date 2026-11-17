import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("county_subsets",
    Path(__file__).with_name("review-county-candidate-subsets.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(dem=12, rep=8, write_ins=4):
    roles = [{"candidate_id": 1, "name": "Dem Candidate", "party": "Democratic", "role": "D"},
             {"candidate_id": 2, "name": "Rep Candidate", "party": "Republican", "role": "R"},
             {"candidate_id": 3, "name": "Write-in", "party": "Nonpartisan", "role": "unallocated_other"}]
    candidates = [{**{k: r[k] for k in ("name", "party", "candidate_id")}, "votes": votes}
                  for r, votes in zip(roles, (dem, rep, write_ins))]
    native = {"country": "US", "province": "ME", "district": "ME-01", "test_data": False,
        "election_type": "House of Representatives", "election_scope": "General", "round": 1,
        "election_date": "2026-11-03T05:00:00.000Z", "last_updated": "2026-11-07T05:36:43.607Z",
        "candidates": candidates, "region_results": {"a": {"name": "Example", "type": "County",
            "fips": "23001", "candidates": [{**c, "votes": 0 if c["party"] == "Nonpartisan" else c["votes"]}
                                        for c in candidates]}}}
    review = {"contract": "participation.county_candidate_subset_review.v1", "year": 2026,
        "state_code": "ME", "state_fips": "23", "office": "U.S. House", "stage": "General",
        "round": 1, "boundary_reference_year": 2026, "freshness": "retained_historical_observation",
        "districts": [{"district": "ME-01", "file": "original.json", "candidate_roles": roles,
            "receipt": {"status": 200, "url": "https://civicapi.org/api/v2/race/1",
                        "acquired_at": "2026-11-07T05:54:18.647980+00:00"}}]}
    reference = {"reference": {"23001": {"GEOID": "23001", "STATEFP": "23", "NAME": "Example",
        "NAMELSAD": "Example County"}}, "geometry": {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"key": "23001", "name": "Example County", "state_code": "ME",
         "boundary_year": 2026}, "geometry": {"type": "Polygon",
             "coordinates": [[[-70, 43], [-69, 43], [-69, 44], [-70, 43]]]}}]}}
    return review, native, reference


def compile_fixture(review, native, reference):
    raw = json.dumps(native).encode()
    receipt = review["districts"][0]["receipt"]
    receipt.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    return module.compile_subset(review, {"original.json": raw}, reference)


class CountySubsetsTest(unittest.TestCase):
    def test_partial_votes_remain_inspectable_without_complete_denominator(self):
        data = compile_fixture(*fixture())
        row = data["rows"][0]
        self.assertEqual((row["democratic_votes"], row["republican_votes"]), (12, 8))
        self.assertEqual(row["margin_bounds_pp"], [100 * 4 / 24, 20.0])
        self.assertIsNone(row["other_votes"])
        self.assertIsNone(row["contest_votes"])
        self.assertIsNone(row["margin_pp"])
        self.assertEqual(data["unlocated_other_votes"], 4)
        self.assertEqual(row["district_fragments"][0]["candidates"][-1]["votes"], 0)
        self.assertFalse(data["swing_qualified"])
        self.assertFalse(data["model_update_qualified"])

    def test_revised_and_decreased_source_counts_and_true_zero(self):
        for dem, rep in ((13, 8), (11, 8), (0, 8), (0, 0), (12, 0)):
            with self.subTest(dem=dem, rep=rep):
                row = compile_fixture(*fixture(dem, rep))["rows"][0]
                self.assertEqual(row["democratic_votes"], dem)
                self.assertEqual(row["republican_votes"], rep)
                self.assertEqual(row["margin_bounds_pp"], module.margin_bounds(dem, rep, 0, 4))

    def test_complete_source_vector_is_explicit_and_never_uses_an_unknown_zero(self):
        data = compile_fixture(*fixture(write_ins=0))
        row = data["rows"][0]
        self.assertTrue(row["complete_vector_qualified"])
        self.assertEqual(row["other_votes"], 0)
        self.assertEqual(row["contest_votes"], 20)
        self.assertEqual(row["margin_pp"], 20)

    def test_missing_candidates_unknowns_and_unreconciled_major_counts_refuse(self):
        changes = (
            lambda n: n["region_results"]["a"]["candidates"].pop(),
            lambda n: n["region_results"]["a"]["candidates"][0].update(votes=None),
            lambda n: n["region_results"]["a"]["candidates"][0].update(votes=True),
            lambda n: n["region_results"]["a"]["candidates"][0].update(votes=11),
            lambda n: n["region_results"]["a"]["candidates"][-1].update(votes=5),
            lambda n: n["candidates"][0].update(candidate_id=99),
            lambda n: n["region_results"]["a"].update(fips="23003"),
            lambda n: n["region_results"].update(b=copy.deepcopy(n["region_results"]["a"])),
        )
        for change in changes:
            review, native, reference = fixture()
            change(native)
            with self.subTest(change=change), self.assertRaises(ValueError):
                compile_fixture(review, native, reference)

    def test_wrong_stage_round_office_election_test_and_clock_refuse(self):
        for key, value in (("round", 2), ("election_scope", "Runoff"), ("province", "NH"),
                           ("election_type", "Senate"), ("election_date", "2024-11-03T00:00:00Z"),
                           ("test_data", True), ("last_updated", "2026-11-08T00:00:00Z")):
            review, native, reference = fixture()
            native[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                compile_fixture(review, native, reference)

    def test_nested_townships_are_retained_but_never_added(self):
        review, native, reference = fixture()
        native["region_results"]["town"] = {**copy.deepcopy(native["region_results"]["a"]), "type": "Township"}
        result = compile_fixture(review, native, reference)
        self.assertEqual(result["rows"][0]["democratic_votes"], 12)
        self.assertEqual(len(result["district_decisions"][0]["ignored_nested_regions"]), 1)

    def test_two_district_fragments_are_summed_once_with_separate_missing_mass(self):
        review, native, reference = fixture()
        raw = json.dumps(native).encode()
        first = review["districts"][0]
        first["receipt"].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        second = copy.deepcopy(first)
        second.update(district="ME-02", file="second.json")
        second["receipt"]["url"] = "https://civicapi.org/api/v2/race/2"
        other = copy.deepcopy(native)
        other["district"] = "ME-02"
        for c in other["candidates"]:
            c["candidate_id"] += 10
        for role in second["candidate_roles"]:
            role["candidate_id"] += 10
        other_raw = json.dumps(other).encode()
        second["receipt"].update(bytes=len(other_raw), sha256=hashlib.sha256(other_raw).hexdigest())
        review["districts"].append(second)
        result = module.compile_subset(review, {"original.json": raw, "second.json": other_raw}, reference)
        row = result["rows"][0]
        self.assertEqual((row["democratic_votes"], row["republican_votes"]), (24, 16))
        self.assertEqual(row["unlocated_other_upper_bound"], 8)
        self.assertEqual(len(row["district_fragments"]), 2)

    def test_checksums_and_missing_originals_refuse(self):
        review, native, reference = fixture()
        with self.assertRaisesRegex(ValueError, "inventory"):
            module.compile_subset(review, {}, reference)
        with self.assertRaisesRegex(ValueError, "checksum"):
            module.compile_subset(review, {"original.json": json.dumps(native).encode()}, reference)


if __name__ == "__main__":
    unittest.main()
