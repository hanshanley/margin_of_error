import copy
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "current", Path(__file__).with_name("review-ces-2022-current-electorate.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(**changes):
    result = {key: "NA" for key in module.REQUIRED}
    result.update(inputstate="37", TS_state="28", TS_g2022="4", CC22_401="5",
                  presvote20post="1", birthyr="1980", CC22_412="1",
                  HouseCand1Party_post="Republican", vvweight_post="1", commonpostweight="2")
    result.update(changes)
    return result


def control():
    return {state: {"ballots_2022": 100, "presidential_2020": {"D": 60, "R": 30, "O": 10, "total": 100}}
            for state in list(module.FIPS.values()) + ["US50"]}


def nc(rows, spec_index=0):
    result = module.review(iter(rows), control())
    return next(state for state in result["states"] if state["state_code"] == "NC")["specifications"][spec_index]


class CurrentElectorateTests(unittest.TestCase):
    def test_native_matched_state_is_not_fips(self):
        self.assertEqual(nc([row()])["current_query_n"], 1)
        self.assertEqual(nc([row(TS_state="37")])["current_query_n"], 0)
        self.assertEqual(nc([row(TS_state="37")], 1)["current_query_n"], 1)

    def test_nonvoters_and_unknowns_remain_in_current_electorate_denominator(self):
        result = nc([row(), row(presvote20post="6"), row(presvote20post="NA")])
        self.assertEqual(result["current_query_n"], 3)
        self.assertAlmostEqual(result["prior_composition"]["D"]["share_full_current_query_denominator"],
                               Decimal(1) / 3, places=27)
        self.assertEqual(result["prior"]["NO_PRESIDENT"]["n"], 1)
        self.assertEqual(result["prior"]["UNKNOWN"]["n"], 1)
        self.assertIsNone(result["prior_composition"]["NO_PRESIDENT"]["original_2020_presidential_votes"])

    def test_weighted_scaling_switches_and_negative_absence_not_clamped(self):
        result = nc([row(vvweight_post="3"), row(presvote20post="6")])
        prior = result["prior_composition"]["D"]
        self.assertEqual(prior["conditional_scaled_current_people"], 75)
        self.assertEqual(prior["conditional_scaled_opposite_house_choice"], 75)
        self.assertEqual(prior["signed_apparent_absence"], -15)

    def test_birthyear_boundary_and_inconsistent_prior_vote_are_retained(self):
        result = nc([row(birthyr="2003"), row(birthyr="2002"), row(birthyr="2001"),
                     row(birthyr="NA"), row(birthyr="2005")])
        self.assertEqual(result["current_query_n"], 5)
        self.assertEqual({key: value["n"] for key, value in result["prior_by_age"]["D"].items()},
                         {"UNDER_18_IN_2020": 1, "BIRTHDAY_BOUNDARY_2002": 1,
                          "ADULT_IN_2020": 1, "UNKNOWN": 2})

    def test_selfreport_sensitivity_does_not_change_administrative_primary(self):
        source = [row(TS_g2022="7"), row(TS_g2022="NA")]
        self.assertEqual(nc(source)["current_query_n"], 0)
        self.assertEqual(nc(source, 2)["current_query_n"], 2)

    def test_missing_geography_and_weight_have_explicit_dispositions(self):
        result = nc([row(TS_state="NA"), row(vvweight_post="NA"), row(TS_g2022="NA")])
        self.assertEqual([result["dispositions"][key]["n"] for key in
                          ("matched_state_missing", "missing_or_zero_weight", "not_current_query_voter")],
                         [1, 1, 1])

    def test_dc_is_separate_from_national_50_and_inputs_unchanged(self):
        source = [row(), row(inputstate="11", TS_state="8")]
        original = copy.deepcopy(source)
        result = module.review(iter(source), control())
        counts = {state["state_code"]: state["specifications"][0]["current_query_n"]
                  for state in result["states"]}
        self.assertEqual((counts["NC"], counts["DC"], counts["US50"]), (1, 1, 1))
        self.assertEqual(source, original)
        self.assertFalse(result["population_method_validated"])

    def test_literal_candidate_party_and_unknown_responses_not_recoded(self):
        for changes, expected in (({"HouseCand1Party_post": "Independent"}, "O"),
                                  ({"HouseCand1Party_post": "NA"}, "UNKNOWN"),
                                  ({"CC22_412": "11"}, "CONTEST_NONVOTE"),
                                  ({"CC22_412": "12"}, "REPORTED_NONVOTE")):
            self.assertEqual(module.house_choice(row(**changes)), expected)
        for changes in ({"TS_state": "99"}, {"TS_g2022": "0"}, {"presvote20post": "7"},
                        {"vvweight_post": "-1"}, {"vvweight_post": "NaN"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                nc([row(**changes)])


if __name__ == "__main__":
    unittest.main()
