"""Check newly reported statistics, observed zeros and unchanged native coordinates."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mn_complete", ROOT / "scripts/minnesota-complete-native.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
SOURCE = ROOT / core.VERSION


class MinnesotaCompleteNativeTests(unittest.TestCase):
    def test_complete_source_preserves_zeroes_conflicts_and_withheld_precinct_rates(self):
        data = core.load()
        units, counties = data["all4105_native_precinct_decisions"], data["complete_county_decisions"]
        newly_reported = [row for row in units if row["newly_reported"]]
        self.assertEqual(len(newly_reported), 26)
        self.assertTrue(all(row["reported_statistics"] and row["total_number_voted"] is not None for row in units))
        zeros = [row for row in units if row["total_number_voted"] == 0]
        self.assertEqual(len(zeros), 32)
        self.assertTrue(all(row["reported_statistics"] for row in zeros))
        self.assertTrue(all(row["precinct_analysis_rate"] is None for row in units))
        for row in counties:
            allowed = row["complete_registration_frame"] > 0 and not row["native_component_conflicts"] \
                and not row["native_electorate_excesses"]
            self.assertEqual(row["registration_fraction"] is not None, allowed)
        self.assertEqual(sum(row["registration_fraction"] is None for row in counties), 14)
        self.assertFalse(data["summary"]["reference_coordinates_changed"])
        self.assertIsNone(data["summary"]["independently_printed_state_count"])

    def test_missing_native_statistics_cannot_be_promoted_to_reported_zero(self):
        body = (SOURCE / "originals/pctstats.txt").read_bytes()
        lines = body.decode("utf-8-sig").splitlines()
        cells = lines[0].split(";")
        cells[4] = "0"
        lines[0] = ";".join(cells)
        with self.assertRaisesRegex(ValueError, "explicitly reported"):
            core.native(("\n".join(lines) + "\n").encode())

    def test_duplicate_identity_and_unsafe_count_rejected(self):
        body = (SOURCE / "originals/pctstats.txt").read_bytes()
        lines = body.decode("utf-8-sig").splitlines()
        broken = list(lines)
        broken[1] = broken[0]
        with self.assertRaisesRegex(ValueError, "Duplicated"):
            core.native(("\n".join(broken) + "\n").encode())
        cells = lines[0].split(";")
        cells[11] = "9007199254740992"
        lines[0] = ";".join(cells)
        with self.assertRaisesRegex(ValueError, "safe count"):
            core.native(("\n".join(lines) + "\n").encode())


if __name__ == "__main__":
    unittest.main()
