"""Check historical age-bin, suppression, source and complete-download contracts."""

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cps_older", ROOT / "scripts/package-cps-older-history.py")
cps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cps)


class OlderStateHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.summary, cls.display, cls.inputs = cps.review()
        cls.lookup = {(r["state"], r["group"], r["year"]): r for r in cls.rows}
        cls.shared = cps.shared(ROOT)

    def tree(self, root):
        for name in cps.CODE:
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, root / name)
        shutil.copytree(ROOT / cps.DATA, root / cps.DATA, ignore=shutil.ignore_patterns("output"))

    def test_native_percentages_not_ratios_of_rounded_counts(self):
        for year, expected in zip(cps.YEARS, (45.5, 61.8, 41.9, 61.4)):
            row = self.lookup[self.shared.STATES[0], "Total", year]
            self.assertEqual(row["display_reported_voting_pct"], expected)
            self.assertNotEqual(expected, 100 * row["reported_voters_thousands"]
                                / row["adult_citizens_thousands"])
        self.assertEqual(len(self.rows), 3328)
        self.assertEqual(self.summary["duplicate_overall_controls_verified"], 208)

    def test_2010_age_bins_not_split_or_imputed(self):
        for state in self.shared.STATES:
            for group in ("25 to 44", "65 to 74", "75+"):
                self.assertIn((state, group, 2010), self.lookup)
                self.assertNotIn((state, group, 2012), self.lookup)
            for group in ("25 to 34", "35 to 44", "65+"):
                self.assertNotIn((state, group, 2010), self.lookup)
                self.assertIn((state, group, 2012), self.lookup)
        missing = 0
        for si, state in enumerate(self.display["states"]):
            for gi, group in enumerate(self.display["groups"]):
                for yi, year in enumerate(self.display["years"]):
                    actual = self.display["values"][si][gi][yi]
                    row = self.lookup.get((state, group, year))
                    if row is None:
                        self.assertEqual(actual, [-4])
                        missing += 1
                    elif row["display_status"] == "published":
                        self.assertEqual(actual, [row["display_reported_voting_pct"],
                                                  row["display_native_moe90_pp"]])
                    else:
                        self.assertEqual(actual, [-cps.STATUSES.index(row["display_status"])])
        self.assertEqual(missing, 624)

    def test_native_suppression_spelling_and_2016_population_threshold(self):
        suppressed = [r for r in self.rows if r["display_status"] == "native_B_not_published"]
        self.assertEqual({r["voted_citizen_pct"] for r in suppressed}, {"B", "(B)"})
        for row in suppressed:
            self.assertEqual(row["voted_citizen_pct"], row["voted_citizen_moe90_pp"])
            self.assertIsNone(row["display_reported_voting_pct"])
        native = copy.deepcopy(self.lookup["Alabama", "Total", 2016])
        native["adult_citizens_thousands"] = 90
        self.assertEqual(cps.disposition(native, 2016)[0], cps.STATUSES[2])
        self.assertEqual(cps.disposition(native, 2014)[0], cps.STATUSES[0])
        native["adult_citizens_thousands"] = 100
        self.assertEqual(cps.disposition(native, 2016)[0], cps.STATUSES[2])
        native["adult_citizens_thousands"] = 101
        self.assertEqual(cps.disposition(native, 2016)[0], cps.STATUSES[0])
        native["voted_citizen_pct"] = "(B)"
        with self.assertRaisesRegex(ValueError, "Inconsistent native suppression"):
            cps.disposition(native, 2016)
        native["voted_citizen_moe90_pp"] = "(B)"
        self.assertEqual(cps.disposition(native, 2016), (cps.STATUSES[1], None, None))
        native["voted_citizen_pct"] = "-"
        native["voted_citizen_moe90_pp"] = 0.1
        self.assertEqual(cps.disposition(native, 2016), (cps.STATUSES[3], None, None))

    def test_native_source_or_manifest_tamper_refused_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.tree(root)
            filename = root / cps.DATA / "2010-table4b.xls"
            filename.write_bytes(filename.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "Frozen source receipt mismatch"):
                cps.package(root)
            self.assertFalse((root / cps.DATA / "output").exists())
            (root / cps.DATA / "sources.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Frozen source manifest changed"):
                cps.review(root)

    def test_catalog_and_shared_reader_tamper_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.tree(root)
            filename = root / cps.DATA / "catalog-2010.html"
            filename.write_text("changed")
            with self.assertRaisesRegex(ValueError, "Frozen source receipt mismatch"):
                cps.review(root)
            (root / cps.SHARED).write_text("changed")
            with self.assertRaisesRegex(ValueError, "Frozen shared reader changed"):
                cps.review(root)

    def test_complete_reproducible_archive_and_existing_output_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.tree(root)
            result = cps.package(root)
            self.assertEqual(result, cps.package(root))
            filename = root / cps.DATA / "output/complete-analysis.zip"
            with zipfile.ZipFile(filename) as archive:
                inventory = json.loads(archive.read("checksums.json"))
                self.assertEqual(set(archive.namelist()), {*inventory, "checksums.json"})
                self.assertEqual(sum(name.endswith((".xls", ".xlsx")) for name in inventory), 8)
                self.assertEqual(sum(name.endswith(".html") for name in inventory), 4)
                self.assertEqual(len(archive.read("results/observations.csv").splitlines()), 3329)
                self.assertIn("scripts/requirements-cps-older-history.txt", inventory)
                for name, expected in inventory.items():
                    raw = archive.read(name)
                    self.assertEqual({"bytes": len(raw), "sha256": self.shared.digest(raw)}, expected)
            (root / cps.DATA / "output/display.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Frozen output changed"):
                cps.package(root)


if __name__ == "__main__":
    unittest.main()
