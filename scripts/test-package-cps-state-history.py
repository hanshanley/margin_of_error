"""Native-cell, suppression, completeness and offline reproduction checks."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cps_state", ROOT / "scripts/package-cps-state-history.py")
cps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cps)


class StateHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.summary, cls.display, cls.inputs = cps.review()
        cls.lookup = {(r["state"], r["group"], r["year"]): r for r in cls.rows}

    def test_native_values_and_both_presidential_midterm_years(self):
        self.assertEqual(len(self.rows), 3328)
        self.assertEqual(self.summary["duplicate_overall_controls_verified"], 208)
        self.assertEqual({r["state"] for r in self.rows}, set(cps.STATES))
        for year, expected in zip(cps.YEARS, (53.4, 66.8, 52.2, 65.3)):
            self.assertEqual(self.lookup[cps.STATES[0], "Total", year]["display_reported_voting_pct"],
                             expected)
        row = self.lookup["Alabama", "Total", 2024]
        self.assertEqual((row["display_reported_voting_pct"], row["display_native_moe90_pp"]),
                         (58.7, 4.5))
        self.assertNotEqual(row["display_reported_voting_pct"],
                            100 * row["reported_voters_thousands"] / row["adult_citizens_thousands"])

    def test_native_suppression_is_never_recovered_from_counts(self):
        suppressed = [r for r in self.rows if r["display_status"] == cps.STATUSES[1]]
        self.assertTrue(suppressed)
        for row in suppressed:
            self.assertEqual(row["voted_citizen_pct"], "B")
            self.assertIsNone(row["display_reported_voting_pct"])
            self.assertIsNone(row["display_native_moe90_pp"])
        native = copy.deepcopy(self.lookup["Alabama", "Total", 2024])
        for base, expected in ((75, cps.STATUSES[2]), (74, cps.STATUSES[2]),
                               ("-", cps.STATUSES[2]), (76, cps.STATUSES[0])):
            native["adult_citizens_thousands"] = base
            self.assertEqual(cps.disposition(native)[0], expected)
        native["voted_citizen_pct"] = "-"
        self.assertEqual(cps.disposition(native), (cps.STATUSES[3], None, None))
        native["voted_citizen_pct"] = "B"
        with self.assertRaisesRegex(ValueError, "Inconsistent native B"):
            cps.disposition(native)

    def test_display_reconciles_every_state_group_year_and_preserves_overlap(self):
        display = self.display
        self.assertEqual(len(display["values"]), 52)
        self.assertIn("White alone or in combination", display["groups"])
        self.assertNotIn("education", display["groups"])
        for state_index, state in enumerate(display["states"]):
            for group_index, group in enumerate(display["groups"]):
                for year_index, year in enumerate(display["years"]):
                    row = self.lookup[state, group, year]
                    actual = display["values"][state_index][group_index][year_index]
                    expected = ([row["display_reported_voting_pct"], row["display_native_moe90_pp"]]
                                if row["display_status"] == cps.STATUSES[0]
                                else [-cps.STATUSES.index(row["display_status"])])
                    self.assertEqual(actual, expected)

    def test_changed_native_bytes_refused_before_any_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / cps.DATA, root / cps.DATA,
                            ignore=shutil.ignore_patterns("output"))
            path = next((root / cps.DATA).glob("*.xlsx"))
            path.write_bytes(path.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "Frozen workbook changed"):
                cps.package(root)
            self.assertFalse((root / cps.DATA / "output").exists())

    def test_complete_deterministic_archive_reproduces_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in cps.CODE:
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, root / name)
            shutil.copytree(ROOT / cps.DATA, root / cps.DATA,
                            ignore=shutil.ignore_patterns("output"))
            first = cps.package(root)
            self.assertEqual(first, cps.package(root))
            path = root / cps.DATA / "output/complete-analysis.zip"
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), first["sha256"])
            with zipfile.ZipFile(path) as archive:
                inventory = json.loads(archive.read("checksums.json"))
                self.assertEqual(set(archive.namelist()), {*inventory, "checksums.json"})
                self.assertEqual(sum(name.endswith(".xlsx") for name in inventory), 8)
                self.assertEqual(sum(name.endswith(".html") for name in inventory), 4)
                self.assertEqual(len(archive.read("results/observations.csv").splitlines()), 3329)
                for name, expected in inventory.items():
                    raw = archive.read(name)
                    self.assertEqual({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
                                     expected)
            output = root / cps.DATA / "output/display.json"
            output.write_text("{}")
            with self.assertRaisesRegex(ValueError, "Frozen output"):
                cps.package(root)

    def test_changed_catalog_and_manifest_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / cps.DATA, root / cps.DATA,
                            ignore=shutil.ignore_patterns("output"))
            path = root / cps.DATA / "catalog-2018.html"
            path.write_text("<a href='guessed-source.xlsx'>wrong</a>")
            with self.assertRaisesRegex(ValueError, "Frozen declared-link catalog"):
                cps.review(root)
            path = root / cps.DATA / "sources.json"
            path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "Frozen source manifest"):
                cps.review(root)


if __name__ == "__main__":
    unittest.main()
