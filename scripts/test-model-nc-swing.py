import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

spec = importlib.util.spec_from_file_location("model", Path(__file__).with_name("model-nc-swing.py"))
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


class ConditionalModelTest(unittest.TestCase):
    def test_conflicting_source_ages_become_unknown_without_dropping_history_or_mutating_inputs(self):
        baseline = dict(records=1, baseline_2024_voted_county=True,
                        prior_2024_history="Positive 2024 NC history", age_2024="Under 18 in 2024",
                        age_2018="Under 18", age_2022="Under 18", age_2026="18-29")
        earlier = dict(records=2, baseline_2024_voted_county=False, prior_2020_history=True,
                       age_2018="Under 18", age_2022="Under 18", age_2024="18-29", age_2026="18-29")
        original = json.dumps([baseline, earlier], sort_keys=True)
        resolved, audit = model.reconcile_source_ages([baseline, earlier])
        self.assertEqual(json.dumps([baseline, earlier], sort_keys=True), original)
        self.assertEqual(audit["conflicting_source_records"], 3)
        self.assertEqual(audit["conflicting_source_cells"], 2)
        self.assertEqual(audit["baseline_2024_records_retained"], 1)
        for before, after in zip([baseline, earlier], resolved):
            self.assertEqual({key: value for key, value in before.items() if not key.startswith("age_")},
                             {key: value for key, value in after.items() if not key.startswith("age_")})
            self.assertTrue(all(after[f"age_{year}"] == "Unknown" for year in (2018, 2022, 2024, 2026)))

    def test_newly_adult_and_nonconflicting_history_keep_source_ages(self):
        entrant = dict(records=3, baseline_2024_voted_county=False, age_2024="Under 18 in 2024",
                       age_2026="18-29", primary_2024="DEM")
        ordinary = dict(records=4, prior_2020_history=True, age_2018="Under 18",
                        age_2022="18-29", age_2024="18-29", age_2026="18-29")
        rows = [entrant, ordinary]
        resolved, audit = model.reconcile_source_ages(rows)
        self.assertIsNone(audit)
        self.assertEqual(resolved, rows)

    def test_explicit_county_requires_its_hash_bound_cells_and_population_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cells = [
                dict(records=60, baseline_2024_voted_county=True,
                     cohort_membership_2026="Accepted 2026 EARLY VOTING"),
                dict(records=40, baseline_2024_voted_county=True,
                     cohort_membership_2026="Not in selected early/mail cohort"),
            ]
            cells_path = root / "cells.json"
            cells_path.write_text(json.dumps(cells))
            audit = dict(state_code="NC", county="WAKE", aggregate_cells=2,
                         joint_cells_sha256=hashlib.sha256(cells_path.read_bytes()).hexdigest(),
                         history=dict(baseline_county_2024_unique_identifiers=100),
                         accepted_cohort=dict(unambiguous_records=60))
            audit_path = root / "audit.json"
            audit_path.write_text(json.dumps(audit))
            candidates = [
                dict(county=county, year=year, contest=contest, method="Total Votes",
                     party_literal=party, votes=count)
                for county in ["WAKE", "DURHAM"]
                for year, contest in [(2024, "US PRESIDENT"), (2026, "US SENATE")]
                for party, count in [("DEM", 40), ("REP", 30), ("OTHER", 1)]
            ]
            for name, value in [
                ("model.json", {}),
                ("candidates.json", candidates),
                ("participation.json", dict(state="North Carolina", election_date="2026-11-03",
                                            reporting=[dict(county="WAKE", ballots_cast=80)])),
            ]:
                (root / name).write_text(json.dumps(value))

            def run(**kwargs):
                return model.run(cells_path, root / "model.json", root / "candidates.json",
                                 root / "participation.json", root / "output", **kwargs)

            with self.assertRaisesRegex(ValueError, "hash-bound linkage audit"):
                run(county="WAKE")
            with patch.object(model, "historical_turnout", side_effect=RuntimeError("WAKE_FIT_STARTED")):
                with self.assertRaisesRegex(RuntimeError, "WAKE_FIT_STARTED"):
                    run(county="WAKE", linkage_audit=audit_path)
            for changed in [
                dict(county="DURHAM"), dict(joint_cells_sha256="changed"),
                dict(aggregate_cells=3),
                dict(history=dict(baseline_county_2024_unique_identifiers=99)),
                dict(accepted_cohort=dict(unambiguous_records=59)),
            ]:
                audit_path.write_text(json.dumps({**audit, **changed}))
                with self.assertRaisesRegex(ValueError, "County linkage audit"):
                    run(county="WAKE", linkage_audit=audit_path)
            audit_path.write_text(json.dumps(audit))
            (root / "participation.json").write_text(json.dumps(dict(
                state="North Carolina", election_date="2026-11-03",
                reporting=[dict(county="DURHAM", ballots_cast=80)])))
            with self.assertRaisesRegex(ValueError, "county participation scope"):
                run(county="WAKE", linkage_audit=audit_path)

    def test_county_run_exports_every_scenarios_group_activity_and_sensitivity_extrema(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cells = [
                dict(records=count, baseline_2024_voted_county=True,
                     cohort_membership_2026=membership, registration_status_2026="ACTIVE",
                     age_2024="30-44", age_2026="30-44", race="W", ethnicity="NL", gender=gender,
                     registered_party_2026=party, primary_2024="No matched primary",
                     prior_2024_history="Positive 2024 NC history")
                for count, membership, gender, party in [
                    (60, "Accepted 2026 EARLY VOTING", "F", "DEM"),
                    (40, "Not in selected early/mail cohort", "M", "REP")]
            ]
            cells[0]["age_2024"] = "Under 18 in 2024"
            (root / "cells.json").write_text(json.dumps(cells))
            audit = dict(state_code="NC", county="WAKE", aggregate_cells=2,
                         joint_cells_sha256=hashlib.sha256((root / "cells.json").read_bytes()).hexdigest(),
                         history=dict(baseline_county_2024_unique_identifiers=100),
                         accepted_cohort=dict(unambiguous_records=60))
            candidates = [
                dict(county="WAKE", year=year, contest=contest, method="Total Votes",
                     party_literal=party, votes=count)
                for year, contest in [(2024, "US PRESIDENT"), (2026, "US SENATE")]
                for party, count in [("DEM", 40), ("REP", 30), ("OTHER", 1)]
            ]
            for name, value in [
                ("audit.json", audit), ("candidates.json", candidates),
                ("model.json", dict(models=[dict(model=name) for name in [
                    "registered-party-and-primary", "registration", "primary", "demographics"]])),
                ("participation.json", dict(state="North Carolina", election_date="2026-11-03",
                                            reporting=[dict(county="WAKE", ballots_cast=80)])),
            ]:
                (root / name).write_text(json.dumps(value))
            with patch.object(model, "historical_turnout", return_value=(np.array([.8, .6]), {})), \
                    patch.object(model, "predict_choice", side_effect=lambda *args, **kwargs: np.array(
                        [[.9, .09, .01], [.1, .89, .01]])), patch("builtins.print"):
                model.run(root / "cells.json", root / "model.json", root / "candidates.json",
                          root / "participation.json", root / "output",
                          county="WAKE", linkage_audit=root / "audit.json")
            result = json.loads((root / "output" / "conditional-transitions.json").read_text())
            self.assertEqual(len(result["scenarios"]), 86)
            self.assertEqual(result["source_age_handling"]["baseline_2024_records_retained"], 60)
            self.assertEqual(json.loads((root / "cells.json").read_text()), cells)
            for scenario in result["scenarios"]:
                unknown = next(row for row in scenario["demographics"]
                               if row["dimension"] == "age_2024" and row["group"] == "Unknown")
                self.assertAlmostEqual(unknown["modeled_2024_county_participants"], 60)
                self.assertFalse(any(row["dimension"] == "age_2024" and row["group"] == "Under 18 in 2024"
                                     for row in scenario["demographics"]))
            for ranges in result["demographic_sensitivity_range_margin_pp"]:
                groups = [next(group for group in scenario["demographics"]
                               if (group["dimension"], group["group"]) == (ranges["dimension"], ranges["group"]))
                          for scenario in result["scenarios"]]
                for key in ["modeled_2024_county_participants", "modeled_2026_participants"]:
                    self.assertEqual(ranges[key], dict(minimum=min(group[key] for group in groups),
                                                       maximum=max(group[key] for group in groups)))
                for key, extrema in ranges["modeled_cohort_counts"].items():
                    values = [group["modeled_cohort_counts"][key] for group in groups]
                    self.assertEqual(extrema, dict(minimum=min(values), maximum=max(values)))
                for party, flows in ranges["modeled_prior_choice_transitions"].items():
                    for key, extrema in flows.items():
                        values = [group["modeled_prior_choice_transitions"][party][key] for group in groups]
                        self.assertEqual(extrema, dict(minimum=min(values), maximum=max(values)))
            overall = next(group for group in result["demographic_sensitivity_range_margin_pp"]
                           if group["dimension"] == "overall")
            switchers = overall["modeled_cohort_counts"]["republican_to_democratic"]
            self.assertGreater(switchers["maximum"], switchers["minimum"])

    def test_choice_calibration_preserves_each_cohort_and_handles_zero_other(self):
        priors = np.array([[.9, .09, .01], [.1, .89, .01]])
        weights = np.array([50., 50.])
        target = np.array([70., 30., 0.])
        fitted = model.calibrate(priors, weights, target)
        np.testing.assert_allclose(fitted.sum(axis=1), 1)
        np.testing.assert_allclose(weights @ fitted, target, atol=1e-4)
        self.assertGreater(fitted[0, 0], fitted[1, 0])
        with self.assertRaises(ValueError):
            model.calibrate(priors, weights, np.array([70., 40., 0.]))
        for invalid_weights, invalid_target in [(np.array([np.nan, 50.]), target),
                                                (weights, np.array([70., 31., -1.]))]:
            with self.assertRaises(ValueError):
                model.calibrate(priors, invalid_weights, invalid_target)

    def test_prior_turnout_encoding_matches_across_years_and_preserves_unknowns(self):
        row = dict(race="W", ethnicity="NL", registered_party_2026="DEM", primary_2024="DEM",
                   age_2022="45-64", age_2026="45-64", prior_2020_history=True,
                   prior_2024_history="Positive 2024 NC history", historical_search_complete=True)
        self.assertEqual(model.turnout_features(row, 2022, 2020),
                         model.turnout_features(row, 2026, 2024))
        row["prior_2024_history"] = "No 2024 NC history found; national participation unresolved"
        self.assertEqual(model.turnout_features(row, 2026, 2024)["prior_general"], "False")
        row["historical_search_complete"] = False
        self.assertEqual(model.turnout_features(row, 2026, 2024)["prior_general"], "None")

    def test_identical_observations_can_hide_distinct_switching_and_dropoff(self):
        pure_dropoff = np.zeros((1, 6, 6))
        pure_dropoff[0, 0, 0], pure_dropoff[0, 1, 1], pure_dropoff[0, 1, 4] = 50, 40, 10
        switching = np.zeros((1, 6, 6))
        switching[0, 0, 0], switching[0, 0, 4] = 40, 10
        switching[0, 1, 0], switching[0, 1, 1] = 10, 40
        _, first = model.accounting(pure_dropoff)
        _, second = model.accounting(switching)
        self.assertEqual(first["before"], second["before"])
        self.assertEqual(first["after"], second["after"])
        self.assertEqual(first["swing_margin_pp"], second["swing_margin_pp"])
        self.assertEqual(first["gross_major_party_switchers"], 0)
        self.assertEqual(second["gross_major_party_switchers"], 10)
        self.assertNotEqual(first["margin_pp_contributions"], second["margin_pp_contributions"])

    def test_pure_dropoff_receives_the_entire_percentage_point_swing(self):
        flows = np.zeros((1, 6, 6))
        flows[0, 0, 0], flows[0, 1, 1], flows[0, 1, 4] = 50, 40, 10
        _, result = model.accounting(flows)
        self.assertAlmostEqual(result["swing_margin_pp"], 100 / 9)
        self.assertAlmostEqual(result["margin_pp_contributions"]["dropoff"], 100 / 9)
        self.assertAlmostEqual(result["signed_share_of_swing_pct"]["dropoff"], 100)

    def test_switching_factor_two_and_additive_demographic_contributions(self):
        flows = np.zeros((2, 6, 6))
        flows[0, 0, 0], flows[0, 1, 0], flows[0, 1, 1] = 50, 10, 40
        flows[1, 0, 0], flows[1, 0, 4], flows[1, 1, 1] = 40, 10, 50
        contributions, result = model.accounting(flows)
        self.assertEqual(result["gross_major_party_switchers"], 10)
        self.assertGreater(result["signed_share_of_swing_pct"]["switching"], 100)
        self.assertLess(result["signed_share_of_swing_pct"]["dropoff"], 0)
        self.assertAlmostEqual(contributions.sum(), result["swing_margin_pp"])

    def test_zero_swing_does_not_have_component_percentages(self):
        flows = np.zeros((1, 6, 6))
        flows[0, 0, 0], flows[0, 1, 1] = 50, 50
        _, result = model.accounting(flows)
        self.assertTrue(all(value is None for value in result["signed_share_of_swing_pct"].values()))

    def test_early_absence_is_a_probability_not_a_nonvoter_label(self):
        rows = [
            dict(records=40, cohort_membership_2026="Accepted 2026 EARLY VOTING",
                 baseline_2024_voted_county=True, registration_status_2026="ACTIVE",
                 race="W", ethnicity="NL", registered_party_2026="DEM", primary_2024="DEM"),
            dict(records=60, cohort_membership_2026="Not in selected early/mail cohort",
                 baseline_2024_voted_county=True, registration_status_2026="ACTIVE",
                 race="W", ethnicity="NL", registered_party_2026="REP", primary_2024="REP"),
        ]
        membership, exits = model.late_membership(rows, np.array([.7, .7]), 70, 1., 0.)
        self.assertEqual(membership[0], 1)
        self.assertAlmostEqual(membership[1], .5)
        self.assertEqual(exits.sum(), 0)
        with self.assertRaises(ValueError):
            model.late_membership(rows, np.array([.7, .7]), 30, 1., 0.)

    def test_complete_transition_model_reconciles_votes_ballots_and_all_group_partitions(self):
        rows = []
        for count, party, early, old in [(20, "DEM", True, True), (40, "DEM", False, True),
                                         (40, "REP", False, True), (20, "UNA", False, False)]:
            rows.append(dict(records=count, registered_party_2026=party, primary_2024="No matched primary",
                             cohort_membership_2026="Accepted 2026 EARLY VOTING" if early else "Not in selected early/mail cohort",
                             baseline_2024_voted_county=old, registration_status_2026="ACTIVE",
                             age_2024="30-44", age_2026="30-44", race="W", ethnicity="NL", gender="F",
                             prior_2024_history="Positive 2024 NC history" if old else "Unresolved"))
        prior = np.array([[.9, .09, .01], [.9, .09, .01], [.1, .89, .01], [.5, .49, .01]])
        result = model.scenario(rows, prior, prior, np.array([.8, .8, .6, .3]),
                                np.array([55., 44., 1.]), np.array([50., 25., 1.]), 100, 80)
        np.testing.assert_allclose([result["before"][key] for key in ["D", "R", "O"]], [55, 44, 1], atol=1e-4)
        np.testing.assert_allclose([result["after"][key] for key in ["D", "R", "O", "B"]], [50, 25, 1, 4], atol=1e-4)
        for dimension in {row["dimension"] for row in result["demographics"]}:
            groups = [row for row in result["demographics"] if row["dimension"] == dimension]
            self.assertAlmostEqual(sum(row["modeled_2026_participants"] for row in groups), 80)
            self.assertAlmostEqual(sum(sum(row["margin_pp_contributions"].values()) for row in groups),
                                   result["swing_margin_pp"])
        self.assertEqual(next(row["group"] for row in result["demographics"] if row["dimension"] == "administrative_gender"),
                         "FEMALE")
        counts = result["modeled_cohort_counts"]
        self.assertTrue(all("modeled_prior_choice_transitions" not in group for group in result["demographics"]))
        self.assertAlmostEqual(counts["repeat_2024_county_participants"] +
                               counts["participants_without_2024_county_participation"], 80)
        self.assertAlmostEqual(counts["repeat_2024_county_participants"] +
                               counts["prior_county_participants_now_nonvoting"] +
                               counts["prior_county_participants_eligibility_residence_exit"], 100)
        rows[-1]["age_2024"] = "Under 18 in 2024"
        younger = model.scenario(rows, prior, prior, np.array([.8, .8, .6, .3]),
                                 np.array([55., 44., 1.]), np.array([50., 25., 1.]), 100, 80)
        self.assertAlmostEqual(younger["before"]["N"], 0)
        self.assertAlmostEqual(younger["before"]["X"], 20)
        self.assertGreater(younger["modeled_cohort_counts"]["participants_newly_adult_since_2024"], 0)
        rows[-1]["gender"] = "M"
        with_activity = model.scenario(
            rows, prior, prior, np.array([.8, .8, .6, .3]), np.array([55., 44., 1.]),
            np.array([50., 25., 1.]), 100, 80, group_participation=True)
        for key in ["before", "after", "modeled_cohort_counts", "margin_pp_contributions"]:
            self.assertEqual(with_activity[key], younger[key])
        for dimension in {group["dimension"] for group in with_activity["demographics"]}:
            groups = [group for group in with_activity["demographics"] if group["dimension"] == dimension]
            self.assertAlmostEqual(sum(group["modeled_2024_county_participants"] for group in groups), 100)
            for key, value in with_activity["modeled_cohort_counts"].items():
                self.assertAlmostEqual(sum(group["modeled_cohort_counts"][key] for group in groups), value)
            for party in ["D", "R"]:
                flows = [group["modeled_prior_choice_transitions"][party] for group in groups]
                self.assertAlmostEqual(sum(row["original_2024_county_presidential_voters"] for row in flows),
                                       with_activity["before"][party])
                for row in flows:
                    self.assertAlmostEqual(sum(row[state] for state in model.STATES),
                                           row["original_2024_county_presidential_voters"])
        entrants = next(group for group in with_activity["demographics"]
                        if group["dimension"] == "administrative_gender" and group["group"] == "MALE")
        self.assertEqual(entrants["modeled_2024_county_participants"], 0)
        self.assertGreater(entrants["modeled_cohort_counts"]["participants_newly_adult_since_2024"], 0)
        self.assertIsNone(entrants["group_turnout_rate_pct"])
        self.assertIsNone(entrants["measured_staying_home_count"])
        self.assertTrue(all(value == 0 for row in entrants["modeled_prior_choice_transitions"].values()
                            for value in row.values()))


if __name__ == "__main__":
    unittest.main()
