import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location("mevp", Path(__file__).with_name("review-mevp-voter-poll.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    tables = []
    for code, (name, prefix) in module.GROUPS.items():
        tables.append({
            "group_id": code, "source_url": module.ROOT + f"wp-content/uploads/2026/11/{prefix}-Xtabs-Midterm-Election-Voter-Poll-2026.pdf",
            "source_sha256": "a" * 64, "source_bytes": 1000, "source_pages": {"Q10": 3},
            "columns": [name] + module.BANNERS,
            "raw_respondent_bases": [1000, 40, 30, 400, 450, 50, 90, 490, 500],
            "house_choice_pct": {
                "R": [50, 0, 0, 92, 4, 20, 50, 50, 50],
                "D": [48, 100, 100, 7, 95, 70, 48, 48, 48],
                "O": [2, 0, 0, 1, 1, 10, 2, 2, 2],
            },
            "prior_choice_pct_among_previous_voters": {"D": 44, "R": 51, "O": 3, "N": 2},
            "first_november_election_pct": {"2026": 10, "2024": 10, "2022": 10, "earlier": 70},
        })
    return {
        "study_id": "bsp-aarc-mevp-2026", "question_id": "Q10",
        "contest_scope": "respondent_district_house_party_choice",
        "prior_question_universe": "previous_voters_18plus_in_2024",
        "methodology_url": module.ROOT + "methodology/",
        "methods_field_end": "2026-11-03", "pdf_field_end": "2026-11-02", "tables": tables,
    }


class ReviewTest(unittest.TestCase):
    def test_exact_prior_banner_not_outcome_selected_banner_or_raw_ratio(self):
        result = module.review_snapshot(fixture())["groups"][0]
        prior = result["reported_choices_among_current_voters_by_reported_prior"]
        self.assertEqual(prior["R"]["reported_opposite_party_pct"], 7)
        self.assertEqual(prior["R"]["raw_respondents"], 400)
        self.assertEqual(prior["D"]["reported_opposite_party_pct"], 4)
        self.assertEqual(result["raw_unclassified_prior_or_first_november_respondents"], 10)

    def test_conditional_marginal_does_not_create_population_or_dropoff(self):
        row = module.review_snapshot(fixture())["groups"][0]
        for field in ["prior_composition_among_all_current_group_voters",
                      "current_electorate_group_population_share", "switcher_population_count",
                      "original_2024_coalition_switching_pct", "apparent_absence",
                      "demographic_turnout_rate", "share_of_total_swing"]:
            self.assertIsNone(row[field])
        self.assertEqual(row["reported_first_november_2026_pct"], 10)

    def test_rounding_is_preserved(self):
        source = fixture()
        source["tables"][0]["house_choice_pct"]["R"][3] = 93
        prior = module.review_snapshot(source)["groups"][0]["reported_choices_among_current_voters_by_reported_prior"]["R"]
        self.assertEqual(prior["reported_choice_sum_pct"], 101)
        self.assertEqual(prior["current_house_choice_pct"]["R"], 93)
        source["tables"][0]["house_choice_pct"]["R"][3] = 94
        with self.assertRaises(ValueError):
            module.review_snapshot(source)

    def test_zero_prior_base_withholds_without_recovering_from_switcher_banner(self):
        source = fixture()
        source["tables"][0]["raw_respondent_bases"][1] = 0
        source["tables"][0]["raw_respondent_bases"][3] = 0
        for row in source["tables"][0]["house_choice_pct"].values():
            row[1] = 0
            row[3] = 0
        prior = module.review_snapshot(source)["groups"][0]["reported_choices_among_current_voters_by_reported_prior"]
        self.assertIsNone(prior["R"]["reported_opposite_party_pct"])
        self.assertEqual(prior["D"]["reported_opposite_party_pct"], 4)

    def test_universe_contest_and_date_guards(self):
        for key, value in [("prior_question_universe", "all_current_voters"),
                           ("contest_scope", "national_senate"),
                           ("methods_field_end", "2026-11-02")]:
            source = fixture()
            source[key] = value
            with self.assertRaises(ValueError):
                module.review_snapshot(source)

    def test_source_and_banner_guards(self):
        for key, value in [("source_url", "https://example.com/poll.pdf"),
                           ("source_sha256", "z" * 64),
                           ("columns", ["Trump24"] * 9)]:
            source = fixture()
            source["tables"][0][key] = value
            with self.assertRaises(ValueError):
                module.review_snapshot(source)

    def test_missing_duplicate_and_bad_numeric_inputs(self):
        source = fixture()
        source["tables"].pop()
        with self.assertRaises(ValueError):
            module.review_snapshot(source)
        source = fixture()
        source["tables"].append(copy.deepcopy(source["tables"][0]))
        with self.assertRaises(ValueError):
            module.review_snapshot(source)
        for value in [True, -1, 100.0]:
            source = fixture()
            source["tables"][0]["house_choice_pct"]["D"][3] = value
            with self.assertRaises(ValueError):
                module.review_snapshot(source)
        source = fixture()
        source["tables"][0]["raw_respondent_bases"][3:7] = [400, 450, 100, 100]
        with self.assertRaises(ValueError):
            module.review_snapshot(source)


if __name__ == "__main__":
    unittest.main()
