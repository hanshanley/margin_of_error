import copy
import importlib.util
import json
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "review", Path(__file__).with_name("review-cnn-voter-poll.py"))
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def fixture():
    entry = {"raceTypeCode": "SG", "stateAbbr": "NC", "subsetNumber": 0,
             "subsetTitle": "Main", "url": "exit-poll/2026-SG-NC.json", "isDisabled": False}
    candidates = [{"candidateId": 2, "partyAbbreviation": "R", "partyName": "Republican"},
                  {"candidateId": 1, "partyAbbreviation": "D", "partyName": "Democratic"}]
    data = {
        "ecKey": "2026-SG-NC", "electionDate": "2026-11-03",
        "electionType": "G", "raceType": "S", "jurisdictionType": "SW",
        "state": {"abbreviation": "NC"}, "subset": {"sub": 0, "longName": "Main"},
        "titles": {"raceTitle": {"title": "Senate"}}, "hasData": True,
        "respondents": 4000, "timestamp": "2026-11-04T00:00:00Z",
        "exitPollEmbargo": {"exitPollsReleased": True},
        "raceEmbargo": {"exitPollsReleased": True}, "candidates": candidates,
        "questions": [{"mxId": 10003, "question": "2024 presidential vote ",
                       "onDigital": True, "answers": [{
                           "answer": label, "totalPercentage": share,
                           "candidateAnswers": [{"candidateId": 2, "percentage": r},
                                                {"candidateId": 1, "percentage": d}],
                       } for label, share, d, r in [
                           ("Harris", 49, 97, 2), ("Trump", 44, 7, 91),
                           ("Another candidate", 2, 57, 30), ("Did not vote", 4, 70, 25)]]}],
    }
    return entry, data


def run(entry, data):
    return review.review_source(review.select_source(json.dumps(data).encode(), entry))


class ReviewTests(unittest.TestCase):
    def test_candidate_ids_not_array_positions_and_no_population_claim(self):
        entry, data = fixture()
        result = run(entry, data)
        self.assertEqual(result["reported_composition_sum_pct"], 99)
        self.assertEqual(result["arithmetic_from_rounded_percentages_per_100_current_group_voters"], {
            "reported_trump_to_dem": 3.08, "reported_harris_to_rep": 0.98,
            "gross_reported_major_party_switchers": 4.06,
            "net_reported_switching_toward_dem": 2.1})
        self.assertIsNone(result["dropoff_estimate"])
        self.assertIsNone(result["share_of_total_swing"])
        self.assertIsNone(result["design_confidence_interval"])

    def test_suppression_is_not_zero_or_recovered_from_other_conditionals(self):
        entry, data = fixture()
        data["questions"][0]["answers"][1]["candidateAnswers"][1].update(
            percentage=-1, vPercentage=8)
        result = run(entry, data)
        self.assertEqual(result["status"], "withheld_suppressed_switching_cell")
        self.assertIsNone(result["joint_question_rows"]["R"]["current_choice_pct_within_prior_choice"]["D"])
        data["questions"][0]["answers"][1]["candidateAnswers"][1]["percentage"] = 7
        data["questions"][0]["answers"][2]["candidateAnswers"][1]["percentage"] = -1
        self.assertEqual(run(entry, data)["status"], "published_joint_question_reviewed")

    def test_independents_and_multiple_same_party_candidates_are_not_forced_to_dem(self):
        entry, data = fixture()
        data["candidates"][1].update(partyAbbreviation="I", partyName="Independent", bopPartyId="DEM")
        self.assertEqual(run(entry, data)["status"], "withheld_nonunique_literal_dem_rep_comparison")
        entry, data = fixture()
        data["candidates"].append({"candidateId": 3, "partyAbbreviation": "R", "partyName": "Republican"})
        self.assertEqual(run(entry, data)["status"], "withheld_nonunique_literal_dem_rep_comparison")

    def test_wrong_state_contest_subgroup_and_incomplete_rows_fail_closed(self):
        for field, value in [("ecKey", "2026-GG-NC"), ("electionDate", "2024-11-05")]:
            entry, data = fixture()
            data[field] = value
            with self.assertRaisesRegex(ValueError, "mismatch"):
                run(entry, data)
        entry, data = fixture()
        data["subset"]["sub"] = 53
        with self.assertRaisesRegex(ValueError, "mismatch"):
            run(entry, data)
        entry, data = fixture()
        data["questions"][0]["answers"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            run(entry, data)

    def test_unpublished_or_embargoed_tables_are_not_reconstructed(self):
        entry, data = fixture()
        data["questions"][0]["onDigital"] = False
        self.assertEqual(run(entry, data)["status"], "withheld_missing_published_joint_question")
        data["questions"][0]["onDigital"] = True
        data["raceEmbargo"]["exitPollsReleased"] = False
        self.assertEqual(run(entry, data)["status"], "withheld_not_released_or_no_data")
        self.assertEqual(review.select_source(json.dumps(data).encode(), entry)[
            "selected_native_data"]["questions"], [])

    def test_incomplete_configuration_and_metadata_only_success_fail_closed(self):
        entry, data = fixture()
        selected = review.select_source(json.dumps(data).encode(), entry)
        other = dict(entry, stateAbbr="VA", url="exit-poll/2026-SG-VA.json")
        with self.assertRaisesRegex(ValueError, "inventory"):
            review.review_snapshot({"sources": [selected],
                                    "selected_configuration": {"SG": [entry, other]}})
        with self.assertRaisesRegex(ValueError, "Missing selected data"):
            review.review_snapshot({"sources": [{"configuration_entry": entry,
                                                 "status": "published_joint_question_reviewed"}]})

    def test_composition_shortfall_is_retained_and_not_renormalized(self):
        entry, data = fixture()
        data["questions"][0]["answers"][0]["totalPercentage"] = 47
        result = run(entry, data)
        self.assertEqual(result["status"], "withheld_unreconciled_prior_composition")
        self.assertEqual(result["reported_composition_sum_pct"], 97)
        self.assertEqual(result["reported_composition_difference_from_100_pct"], 3)
        self.assertEqual(result["joint_question_rows"]["D"]["prior_choice_share_pct"], 47)
        self.assertNotIn("arithmetic_from_rounded_percentages_per_100_current_group_voters", result)
        data["questions"][0]["answers"][0]["totalPercentage"] = 60
        with self.assertRaisesRegex(ValueError, "exceeds"):
            run(entry, data)

    def test_snapshot_reproduction_keeps_overlaps_distinct_and_all_jurisdictions(self):
        entry, data = fixture()
        first = review.select_source(json.dumps(data).encode(), entry)
        entry, data = copy.deepcopy(entry), copy.deepcopy(data)
        entry.update(subsetNumber=53, subsetTitle="18-29", url="exit-poll/2026-SG-NC-53.json")
        data.update(ecKey="2026-SG-NC-53", subset={"sub": 53, "longName": "18-29"})
        second = review.select_source(json.dumps(data).encode(), entry)
        snapshot = {"sources": [first, second]}
        result = review.review_snapshot(snapshot)
        self.assertEqual(result, review.review_snapshot(json.loads(json.dumps(snapshot))))
        self.assertEqual(len(result["tables"]), 2)
        nc = next(r for r in result["jurisdictions"] if r["state_code"] == "NC")
        va = next(r for r in result["jurisdictions"] if r["state_code"] == "VA")
        self.assertEqual(nc["reviewed_joint_tables"], 2)
        self.assertEqual(va["reviewed_joint_tables"], 0)
        self.assertFalse(va["population_decomposition_available"])
        self.assertEqual(len(result["jurisdictions"]), 51)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            review.review_snapshot({"sources": [first, first]})


if __name__ == "__main__":
    unittest.main()
