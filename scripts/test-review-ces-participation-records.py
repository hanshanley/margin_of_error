import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "participation", Path(__file__).with_name("review-ces-participation-records.py"))
participation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(participation)


def respondent(**changes):
    return {
        "TS_g2024": "2", "TS_voterstatus": "1", "vvweight": "1", "commonweight": "1",
        "inputstate": "37", "TS_state": "NC", "gender4": "1",
        "race": "1", "hispanic": "2", "educ": "5", "birthyr": "1996",
    } | changes


def frame(output, scope="NC", frame_index=0):
    return next(row for row in output["scopes"] if row["survey_scope"] == scope)["frames"][
        participation.FRAMES[frame_index]]


class ParticipationRecordsTests(unittest.TestCase):
    def test_unmatched_remains_unknown_not_nonvote(self):
        output = participation.review([
            respondent(commonweight="2", vvweight="3"),
            respondent(TS_g2024="7", commonweight="1", vvweight="2"),
            respondent(TS_g2024="NA", TS_voterstatus="NA", TS_state="NA", vvweight="NA", commonweight="7"),
        ])
        adult, registered = (frame(output, frame_index=i)["overall"] for i in (0, 1))
        self.assertEqual(adult["record_compatible_participation_fraction"], [0.2, 0.9])
        self.assertEqual(adult["record_categories"]["unmatched"]["respondents"], 1)
        self.assertEqual(registered["record_compatible_participation_fraction"], [0.6, 0.6])
        self.assertEqual((adult["sum_weight"], registered["sum_weight"]), (10, 5))
        self.assertIsNone(adult["eligible_population_turnout_rate"])

    def test_matched_missing_history_is_not_explicit_nonvote(self):
        output = participation.review([respondent(), respondent(TS_g2024="NA", vvweight="3")])
        registered = frame(output, frame_index=1)["overall"]
        self.assertEqual(registered["record_compatible_participation_fraction"], [0.25, 1])
        self.assertEqual(registered["record_categories"]["matched_missing_history"]["respondents"], 1)

    def test_all_recorded_methods_and_explicit_nonvote(self):
        output = participation.review([respondent(TS_g2024=str(i)) for i in range(1, 8)])
        total = frame(output)["overall"]
        self.assertEqual(total["record_categories"]["recorded_vote"]["respondents"], 6)
        self.assertEqual(total["record_compatible_participation_fraction"], [6 / 7, 6 / 7])
        self.assertEqual(total["effective_sample_size_not_design_precision"], 7)

    def test_native_unknown_demographics_and_partitions_remain(self):
        output = participation.review([respondent(), respondent(gender4="NA", race="NA", hispanic="NA")])
        result = frame(output)
        genders = {row["group"]: row for row in result["partitions"]["gender_2024"]}
        self.assertEqual(genders["Unknown gender"]["respondents"], 1)
        for rows in result["partitions"].values():
            self.assertEqual(sum(row["respondents"] for row in rows), 2)
            self.assertEqual(sum(row["sum_weight"] for row in rows), 2)

    def test_dc_and_absent_state_are_not_allocated_or_zeroed(self):
        output = participation.review([respondent(), respondent(inputstate="11", TS_state="DC", commonweight="3")])
        self.assertEqual(frame(output, "US50")["overall"]["sum_weight"], 1)
        self.assertEqual(frame(output, "US51")["overall"]["sum_weight"], 4)
        self.assertEqual(frame(output, "DC")["overall"]["sum_weight"], 3)
        self.assertFalse(frame(output, "UT")["available"])
        self.assertIsNone(frame(output, "UT")["overall"])
        self.assertEqual(len(output["scopes"]), 53)

    def test_state_mismatch_stays_in_accounting(self):
        output = participation.review([respondent(TS_state="SC", commonweight="3")])
        total = frame(output)["overall"]
        self.assertEqual(total["validation_state_mismatch_respondents"], 1)
        self.assertEqual(total["validation_state_mismatch_weight"], 3)
        self.assertEqual(total["respondents"], 1)

    def test_matched_missing_state_is_preserved_not_disagreement(self):
        output = participation.review([respondent(TS_state="NA", commonweight="3", vvweight="2")])
        for index, expected_weight in ((0, 3), (1, 2)):
            total = frame(output, frame_index=index)["overall"]
            self.assertEqual(total["validation_state_missing_respondents"], 1)
            self.assertEqual(total["validation_state_missing_weight"], expected_weight)
            self.assertEqual(total["validation_state_mismatch_respondents"], 0)
            self.assertEqual(total["recorded_vote_weight_fraction"], 1)

    def test_candidate_choice_and_post_weight_are_not_used(self):
        rows = [respondent(), respondent(TS_g2024="7")]
        changed = copy.deepcopy(rows)
        for row in changed:
            row.update(CC24_410="invalid", TS_partyreg="invalid", vvweight_post="nan")
        self.assertEqual(participation.review(rows), participation.review(changed))

    def test_inconsistent_codes_and_weights_fail_closed(self):
        for changes in (
            {"TS_g2024": "-1"}, {"TS_voterstatus": "2"}, {"vvweight": "NA"},
            {"TS_state": "XX"}, {"inputstate": "99"},
            {"TS_voterstatus": "NA"}, {"commonweight": "nan"}, {"commonweight": "0"},
            {"vvweight": "inf"}, {"vvweight": "-1"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                participation.review([respondent(**changes)])


if __name__ == "__main__":
    unittest.main()
