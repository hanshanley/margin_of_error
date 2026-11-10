"""Focused failures for native county scope, source substitution and PDF extraction."""

import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nevada", ROOT / "scripts/nevada-native-counties.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
DIRECTORY = ROOT / core.VERSION


def facts(county):
    return json.loads((DIRECTORY / "originals" /
        (county.lower().replace(" ", "-") + "-complete-numerical-facts.json")).read_bytes())


class NevadaNativeCountyTests(unittest.TestCase):
    def test_complete_reconstruction_keeps_unknowns_and_distinct_clocks(self):
        data = core.load()
        unknown = [row for row in data["county_decisions"] if not row["observed"]]
        self.assertEqual(len(unknown), 13)
        self.assertTrue(all(row["source_count"] is None and row["registered"] is None for row in unknown))
        self.assertTrue(all(row["analysis_rate"] is None for row in data["county_decisions"]))
        self.assertIsNone(data["summary"]["state_ballots"])
        self.assertEqual(len({row["source_clock_literal"] for row in data["native_observations"]}), 4)
        self.assertEqual(len(data["native_counting_groups"]), 19)

    def test_candidate_table_cannot_replace_clark_participation(self):
        native = facts("Clark")
        native["all_tables"] = native["all_tables"][1:]
        with self.assertRaisesRegex(ValueError, "participation"):
            core.parse_clark(native)

    def test_explicit_zero_modes_survive_and_bad_component_is_rejected(self):
        native = facts("Clark")
        row = core.parse_clark(native)
        self.assertEqual([mode["source_count"] for mode in row["source_modes"][-2:]], [0, 0])
        broken = copy.deepcopy(native)
        broken["all_tables"][0][1][1] = "220,022"
        with self.assertRaises(ValueError):
            core.parse_clark(broken)

    def test_independent_pdf_whitespace_is_accepted_but_count_disagreement_is_not(self):
        native = facts("Churchill")
        parsed = core.parse_pdf("Churchill", native)
        self.assertEqual(parsed["source_count"], 9685)
        native["independent_first_page_text"] = native["independent_first_page_text"].replace("9,685", "9,684")
        with self.assertRaisesRegex(ValueError, "Independent"):
            core.parse_pdf("Churchill", native)

    def test_native_general_election_identity_is_required(self):
        native = facts("White Pine")
        native["page_texts"][0] = native["page_texts"][0].replace("2026 General Election", "2024 General Election")
        with self.assertRaisesRegex(ValueError, "Wrong county"):
            core.parse_pdf("White Pine", native)

    def test_contest_specific_zero_register_is_not_a_county_denominator(self):
        parsed = core.parse_pdf("Churchill", facts("Churchill"))
        conflict = [row for row in parsed["all_native_contest_times_cast"] if row["native_registered"] == 0]
        self.assertTrue(conflict)
        self.assertEqual(conflict[0]["native_times_cast"], 1)
        self.assertEqual(conflict[0]["native_percent_literal"], "N/A")
        self.assertEqual(parsed["registered"], 17211)
        self.assertEqual(parsed["source_count"], 9685)


if __name__ == "__main__":
    unittest.main()
