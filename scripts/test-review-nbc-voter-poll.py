import copy
import importlib.util
import json
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "review", Path(__file__).with_name("review-nbc-voter-poll.py"))
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def fixture():
    answers = [
        ("Kamala Harris (Dem)", 49, 97, 2),
        ("Donald Trump (Rep)", 44, 7, 91),
        ("Other", 2, 57, 30),
        ("Did not vote", 4, 70, 25),
    ]
    poll = {"pollName": "National Presidential", "candidates": [
        {"party": "gop", "colorHex": "#bb0000"},
        {"party": "dem", "colorHex": "#0000bb"},
    ], "polls": [{"question": review.QUESTION, "answers": [
        {"label": label, "percent": f"{share}%", "values": [
            {"color": "#bb0000", "value": r},
            {"color": "#0000bb", "value": d},
        ]} for label, share, d, r in answers]}]}
    return {"electionSeason": "2026", "electionType": "general",
            "currentUrlPath": "/politics/2026-elections/exit-polls",
            "nationalExitPollData": [{"code": 0, "title": "All Voters", "polls": poll}]}


def run(props):
    return review.review_page(('<script id="__NEXT_DATA__">'
        + json.dumps({"props": {"pageProps": props}}) + "</script>").encode())


class ReviewTests(unittest.TestCase):
    def test_joint_arithmetic_uses_party_colors_and_retains_rounding(self):
        result = run(fixture())
        row = result["groups"][0]
        self.assertEqual(row["reported_composition_sum_pct"], 99)
        self.assertEqual(row["joint_question_rows"]["R"][
            "current_choice_pct_within_prior_choice"]["D"], 7)
        self.assertEqual(row[
            "arithmetic_from_rounded_percentages_per_100_current_group_voters"], {
                "reported_trump_to_dem": 3.08, "reported_harris_to_rep": 0.98,
                "net_reported_switching_toward_dem": 2.1})
        self.assertIsNone(row["dropoff_estimate"])
        self.assertIsNone(row["share_of_total_swing"])
        self.assertIsNone(row["design_confidence_interval"])

    def test_missing_joint_question_is_withheld_not_rebuilt_from_marginals(self):
        props = fixture()
        props["nationalExitPollData"][0]["polls"]["polls"][0]["question"] = "Age"
        result = run(props)
        row = result["groups"][0]
        self.assertEqual(row["status"], "withheld_missing_joint_question")
        self.assertNotIn("joint_question_rows", row)
        self.assertFalse(result["qualification"]["complete_selected_question_tables"])

    def test_wrong_election_and_ambiguous_values_fail_closed(self):
        props = fixture()
        props["electionSeason"] = "2024"
        with self.assertRaisesRegex(ValueError, "Wrong election"):
            run(props)
        props = fixture()
        answer = props["nationalExitPollData"][0]["polls"]["polls"][0]["answers"][0]
        answer["values"][1]["color"] = "#bb0000"
        with self.assertRaisesRegex(ValueError, "Duplicate current"):
            run(props)

    def test_overlapping_views_are_kept_separate(self):
        props = fixture()
        second = copy.deepcopy(props["nationalExitPollData"][0])
        second.update(code=53, title="18-29 voters")
        props["nationalExitPollData"].append(second)
        self.assertEqual(len(run(props)["groups"]), 2)

    def test_empty_source_is_not_successful_evidence(self):
        props = fixture()
        props["nationalExitPollData"] = []
        with self.assertRaisesRegex(ValueError, "No source views"):
            run(props)

    def test_selected_snapshot_reproduces_without_whole_copyrighted_page(self):
        props = fixture()
        props["nationalExitPollData"][0]["polls"]["polls"].append({
            "question": "Unselected question", "answers": []})
        raw = ('<script id="__NEXT_DATA__">' + json.dumps(
            {"props": {"pageProps": props}}) + "</script>").encode()
        snapshot = review.snapshot_page(raw)
        self.assertNotIn("Unselected question", json.dumps(snapshot))
        self.assertEqual(review.review_snapshot(snapshot), review.review_page(raw))


if __name__ == "__main__":
    unittest.main()
