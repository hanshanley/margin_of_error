import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "registration_entry", Path(__file__).with_name("package-registration-entry.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DATA = Path(__file__).resolve().parents[1] / module.DATA


class RegistrationEntryTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((DATA / "selected-aggregates.json").read_bytes())

    def test_denominators_are_selected_cohort_and_date_group_not_all_voters(self):
        result = module.review(self.source)
        for row in result["rows"]:
            self.assertAlmostEqual(row["post_registration_share_of_accepted_pct"],
                                   100 * row["post_2024_registration"] / row["accepted_cohort"])
            self.assertAlmostEqual(row["positive_history_share_of_post_registration_pct"],
                                   100 * row["positive_2024_nc_history"] / row["post_2024_registration"])
        for key in ("first_time_voters", "nationally_new_voters", "all_mode_turnout", "turnout_rates",
                    "candidate_choice", "persuasion", "measured_staying_home",
                    "statewide_or_national_estimates"):
            self.assertIsNone(result[key])

    def test_scope_and_private_field_promotions_fail(self):
        for field, value in (("accepted_status", "COUNTED"), ("state", "US"),
                             ("history_search", "county_only"), ("registration_field", "first_registration"),
                             ("registration_after_exclusive", "2024-11-04")):
            source = copy.deepcopy(self.source)
            source["scope"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                module.review(source)
        for target in ("root", "row", "source", "provenance"):
            source = copy.deepcopy(self.source)
            destinations = {"root": source, "row": source["rows"][0], "source": source["sources"][0],
                            "provenance": source["private_provenance"]["WAKE"]}
            destinations[target]["individual_records"] = []
            with self.subTest(target=target), self.assertRaises(ValueError):
                module.review(source)

    def test_small_negative_boolean_inconsistent_or_duplicate_counts_fail(self):
        for edit in ("small", "negative", "boolean", "partition", "denominator", "duplicate"):
            source = copy.deepcopy(self.source)
            row = source["rows"][0]
            if edit == "duplicate":
                source["rows"][1] = copy.deepcopy(row)
            elif edit == "denominator":
                row["accepted_cohort"] = row["post_2024_registration"] - 1
            else:
                row["positive_2024_nc_history"] = {
                    "small": 999, "negative": -1, "boolean": True,
                    "partition": row["positive_2024_nc_history"] + 1}[edit]
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                module.review(source)

    def test_private_selection_excludes_other_cohorts_dates_and_incomplete_history(self):
        template = {
            "cohort_membership_2026": "Accepted 2026 MAIL", "historical_search_complete": True,
            "registration_period": "Registration after 2024 election",
            "prior_2024_history": "Positive 2024 NC history", "records": 2000,
        }
        cells = [template, {**template, "records": 3000,
                           "prior_2024_history":
                               "No 2024 NC history found; national participation unresolved"},
                 {**template, "records": 4000, "registration_period": "Unknown registration date"},
                 {**template, "records": 5000,
                  "cohort_membership_2026": "Not in selected early/mail cohort"}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def save(rows):
                raw = module.encoded(rows)
                (root / "joint-cells.json").write_bytes(raw)
                (root / "audit.json").write_bytes(module.encoded({
                    "county": "WAKE", "joint_cells_sha256": hashlib.sha256(raw).hexdigest(),
                    "accepted_cohort": {"unambiguous_records": 9000}}))

            save(cells)
            row = module.select_private(root)
            self.assertEqual(row, {"county": "WAKE", "accepted_cohort": 9000,
                                  "post_2024_registration": 5000, "positive_2024_nc_history": 2000,
                                  "no_2024_nc_history_found": 3000})
            save([{**template, "historical_search_complete": False}, *cells[1:]])
            with self.assertRaises(ValueError):
                module.select_private(root)
            save(cells)
            (root / "joint-cells.json").write_bytes(module.encoded(cells[:-1]))
            with self.assertRaises(ValueError):
                module.select_private(root)

    def test_missing_source_receipt_or_unqualified_scope_cannot_be_packaged(self):
        source = copy.deepcopy(self.source)
        source["sources"].pop()
        with self.assertRaises(ValueError):
            module.review(source)
        source = copy.deepcopy(self.source)
        source["limitations"] = []
        with self.assertRaises(ValueError):
            module.review(source)


if __name__ == "__main__":
    unittest.main()
