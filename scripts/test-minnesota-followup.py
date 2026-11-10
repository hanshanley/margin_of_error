import csv
import importlib.util
import io
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mn_followup", ROOT / "scripts/minnesota-followup.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
SOURCE = ROOT / core.VERSION
INPUTS = json.loads((SOURCE / "inputs.json").read_bytes())
BODIES = {name: (SOURCE / name).read_bytes() for name in INPUTS["files"]}


class MinnesotaFollowup(unittest.TestCase):
    def test_all_new_complete_counts_and_partial_subtotals_are_distinct(self):
        data = core.load()
        self.assertEqual(data["summary"]["complete_counties"], 84)
        self.assertEqual(data["summary"]["qualified_registration_fractions"],
                         sum(row["registration_fraction_eligible"] for row in data["complete_county_decisions"]))
        self.assertEqual(len(data["all4105_native_precinct_decisions"]), 4105)
        self.assertEqual({row["county"] for row in data["complete_county_decisions"]
                          if not row["all_statistics_reported"]}, {"Fillmore", "Hubbard", "Wright"})
        self.assertTrue(all(row["complete_total_number_voted"] is None
                            for row in data["complete_county_decisions"] if not row["all_statistics_reported"]))
        self.assertIsNone(data["summary"]["exact_statewide_total_number_voted"])
        self.assertEqual(data["summary"]["reported_total_number_voted_subtotal"], 2827091)
        self.assertEqual(data["summary"]["separate_official_page_estimated_voters"], 2852528)
        self.assertEqual(sum(row["newly_complete"] for row in data["complete87_previous_current_comparisons"]), 9)

    def test_missing_native_statistics_are_not_observed_zeros(self):
        data = core.load()
        unreported = [row for row in data["all4105_native_precinct_decisions"] if not row["reported_statistics"]]
        self.assertEqual(len(unreported), 26)
        self.assertTrue(all(row["total_number_voted"] is None and not row["precinct_geometry_approved"]
                            for row in unreported))
        rows = list(csv.reader(io.StringIO(BODIES["originals/pctstats.txt"].decode()), delimiter=";"))
        row = next(row for row in rows if row[4] == "0")
        row[4] = "1"
        stream = io.StringIO(newline="")
        csv.writer(stream, delimiter=";", lineterminator="\n").writerows(rows)
        with self.assertRaises(ValueError):
            core.review(dict(BODIES, **{"originals/pctstats.txt": stream.getvalue().encode()}))

    def test_duplicate_native_precinct_and_wrong_estimate_are_rejected(self):
        rows = list(csv.reader(io.StringIO(BODIES["originals/pctstats.txt"].decode()), delimiter=";"))
        rows[1] = rows[0]
        stream = io.StringIO(newline="")
        csv.writer(stream, delimiter=";", lineterminator="\n").writerows(rows)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            core.review(dict(BODIES, **{"originals/pctstats.txt": stream.getvalue().encode()}))
        observation = json.loads(BODIES["current-official-web-observation.json"])
        observation["official_values"]["estimated_voters"] = 2827091
        with self.assertRaisesRegex(ValueError, "Estimated Voters"):
            core.review(dict(BODIES, **{"current-official-web-observation.json": core.encoded(observation)}))

    def test_native_county_ids_do_not_become_fips_and_conflicts_keep_counts(self):
        data = core.load()
        becker = next(row for row in data["complete_county_decisions"] if row["county"] == "Becker")
        self.assertEqual(becker["native_county_id"], "03")
        self.assertEqual(becker["county_fips"], "27005")
        benton = next(row for row in data["complete_county_decisions"] if row["county"] == "Benton")
        self.assertEqual(benton["complete_total_number_voted"], 18773)
        self.assertGreater(benton["native_component_conflicts"], 0)
        self.assertIsNone(benton["registration_fraction"])


if __name__ == "__main__":
    unittest.main()
