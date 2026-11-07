import importlib.util
import unittest
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location("choice", Path(__file__).with_name("fit-historical-choice.py"))
choice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(choice)


class ChoiceModelTest(unittest.TestCase):
    def test_native_mappings_preserve_unknowns_and_do_not_turn_party_into_choice(self):
        row = dict(inputstate="37", birthyr="2000", TS_partyreg="NA", TS_p2024_party="6",
                   race="1", hispanic="1")
        features = choice.survey_features(row)
        self.assertEqual(features["state"], "NC")
        self.assertEqual(features["registered_party"], "Unspecified")
        self.assertEqual(features["primary_party"], "REP")
        self.assertEqual(features["race_ethnicity"], "Hispanic")
        self.assertEqual(choice.race_ethnicity("3", "2"), "Hispanic")
        self.assertNotIn("choice", features)
        self.assertEqual(choice.race_ethnicity("1", "NA"), "Ethnicity unspecified")
        self.assertEqual(choice.age_bin("2010"), "Unknown")
        self.assertNotIn("registered_party", choice.predictor_features(features, False))

    def test_weighted_metrics_use_probabilities_and_report_effective_sample(self):
        result = choice.scores(np.array([0, 1]), np.array([[.8, .1, .1], [.2, .7, .1]]), np.array([3., 1.]))
        self.assertAlmostEqual(result["effective_sample_size"], 1.6)
        self.assertAlmostEqual(result["democratic_calibration_error_pp"], -10)
        self.assertAlmostEqual(result["log_loss"], -(3 * np.log(.8) + np.log(.7)) / 4)

    def test_grouped_model_recovers_predictive_signal_without_using_county_as_predictor(self):
        values, targets, groups = [], [], []
        for county in range(10):
            for label, party in enumerate(["DEM", "REP", "Other"]):
                for _ in range(5):
                    values.append(dict(state="NC", age="30-44", race_ethnicity="Unspecified race",
                                       registered_party=party, primary_party="No matched primary"))
                    targets.append(label)
                    groups.append(str(county))
        result = choice.fit_model(values, np.array(targets), np.ones(len(values)), np.array(groups))
        self.assertLess(result["validation"]["log_loss"], .2)
        self.assertGreater(result["state_only_baseline_validation"]["log_loss"], 1.)
        self.assertFalse(any("county" in feature for feature in result["features"]))
        self.assertEqual(result["classes"][0], "Democratic")


if __name__ == "__main__":
    unittest.main()
