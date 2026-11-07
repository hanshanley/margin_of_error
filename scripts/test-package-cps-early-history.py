"""Check denominator boundaries, native anomalies and complete offline reproduction."""

import copy
import csv
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cps_early", ROOT / "scripts/package-cps-early-history.py")
cps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cps)


class EarlyStateHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.summary, cls.display, cls.inputs = cps.review()
        cls.lookup = {(r["year"], r["role"], r["geography"], r["native_group"]): r for r in cls.rows}
        cls.states = {name.upper() for name in cps.shared(ROOT).NAMES}

    def tree(self, root):
        for name in cps.CODE:
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, root / name)
        shutil.copytree(ROOT / cps.DATA, root / cps.DATA, ignore=shutil.ignore_patterns("output"))

    def test_denominators_are_native_not_rounded_count_ratios(self):
        for row in self.rows:
            if row["year"] == 2004:
                self.assertEqual(row["display"]["denominator"], "all_adults_18_plus")
                self.assertNotIn("voted_citizens_pct", row["native"])
            else:
                self.assertEqual(row["display"]["denominator"], "citizen_adults_18_plus")
            if row["display"]["status"] == "published_native_rate":
                prefix = "voted_adults" if row["year"] == 2004 else "voted_citizens"
                self.assertEqual(row["display"]["rate_pct"], row["native"][prefix + "_pct"])
                self.assertEqual(row["display"]["native_moe90_pp"], row["native"][prefix + "_moe90_pp"])
            else:
                self.assertIsNone(row["display"]["rate_pct"])
                self.assertIsNone(row["display"]["native_moe90_pp"])
        row = self.lookup[2004, "sex_race", "UNITED STATES", ".Total"]
        self.assertNotEqual(row["display"]["rate_pct"],
                            100 * row["native"]["voted_thousands"] / row["native"]["adults_thousands"])
        exported = list(csv.DictReader(io.StringIO(cps.csv_bytes(self.rows).decode())))
        for native, csv_row in zip(self.rows, exported):
            if native["year"] == 2004:
                self.assertEqual(csv_row["voted_citizens_pct"], "")
                self.assertEqual(csv_row["voted_citizens_moe90_pp"], "")
            for key, value in native["native"].items():
                self.assertEqual(csv_row[key], str(value))

    def test_actual_age_schemes_not_imputed_or_merged(self):
        def groups(year, geography):
            return tuple(r["native_group"] for r in self.rows
                         if r["year"] == year and r["role"] == "age" and r["geography"] == geography)
        self.assertEqual(groups(2004, "UNITED STATES"), cps.AGE_OLD)
        self.assertEqual(groups(2008, "UNITED STATES"), cps.AGE_US)
        for state in self.states:
            self.assertEqual(groups(2006, state), ())
            self.assertEqual(groups(2004, state), cps.AGE_OLD)
            self.assertEqual(groups(2008, state),
                             cps.AGE_COLLAPSED if state in cps.COLLAPSED_STATES else cps.AGE_OLD)
        small = self.lookup[2008, "age", "ALASKA", ".18 to 44"]
        self.assertEqual(small["native_geography"], "ALASKA 2")
        notes = next(d["notes"] for d in self.summary["native_definitions"]
                     if d["year"] == 2008 and d["role"] == "age")
        self.assertTrue(any("Month xx, 2009" in n["literal"] for n in notes))
        self.assertTrue(any("Table 4b utilizes a collapsed" in n["literal"] for n in notes))

    def test_unlabeled_blocks_and_ambiguous_extra_label_not_repaired(self):
        blank = [r for r in self.rows if r["geography"] == "UNLABELED_FIRST_BLOCK"]
        self.assertEqual(len(blank), 22)
        for row in blank:
            self.assertIsNone(row["native_geography"])
            self.assertEqual(row["display"]["status"], "withheld_unlabeled_native_geography")
        extra = self.lookup[2004, "sex_race", "ARIZONA", ".Non-Hispanic White"]
        white = self.lookup[2004, "sex_race", "ARIZONA", ".White alone"]
        distinct = self.lookup[2004, "sex_race", "ARIZONA", "..White non-Hispanic alone"]
        self.assertEqual(extra["native"], white["native"])
        self.assertNotEqual(extra["native"], distinct["native"])
        self.assertEqual(extra["display"]["status"], "withheld_conflicting_extra_native_label")
        self.assertEqual(white["display"]["status"], "published_native_rate")

    def test_conflicting_controls_preserve_and_withhold_both_source_rates(self):
        for (year, state), differences in cps.CONFLICTS.items():
            left = self.lookup[year, "sex_race", state, ".Total"]
            right = self.lookup[year, "age", state, ".Total"]
            self.assertEqual([left["native"]["voted_citizens_pct"],
                              right["native"]["voted_citizens_pct"]],
                             differences["voted_citizens_pct"])
            for row in (left, right):
                self.assertEqual(row["display"]["status"], "withheld_conflicting_same_year_total")
        repaired = copy.deepcopy(self.rows)
        next(r for r in repaired if r["year"] == 2008 and r["role"] == "age"
             and r["geography"] == "FLORIDA" and r["native_group"] == ".Total"
             )["native"]["voted_citizens_pct"] = 63.8
        with self.assertRaisesRegex(ValueError, "Unreviewed conflicting"):
            cps.qualify(repaired, self.states)

    def test_suppressed_rates_and_numeric_margins_stay_separate(self):
        found = {}
        for row in self.rows:
            for key in row["native_suppression_pair_anomalies"]:
                margin = key.removesuffix("_pct") + "_moe90_pp"
                self.assertEqual(row["native"][key], "(B)")
                found[row["file"], row["source_row"], key] = row["native"][margin]
                if key == "voted_citizens_pct":
                    self.assertIsNone(row["display"]["rate_pct"])
        self.assertEqual(found, cps.PAIR_EXCEPTIONS)
        invalid = self.lookup[2008, "sex_race", "SOUTH DAKOTA", ".White alone or in combination"]
        self.assertEqual(invalid["native"]["registered_citizens_pct"], 423)
        self.assertEqual(invalid["display"]["status"], "withheld_native_out_of_range_metric")
        small = [r for r in self.rows
                 if r["display"]["status"] == "withheld_small_rounded_population_base"]
        self.assertEqual(len(small), 1)
        self.assertLessEqual(small[0]["native"]["adult_citizens_thousands"], 75)

    def test_changed_sources_manifest_or_shared_reference_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.tree(root)
            filename = root / cps.DATA / "2008-table4b.xls"
            original = filename.read_bytes()
            filename.write_bytes(original + b"changed")
            with self.assertRaisesRegex(ValueError, "Source byte/receipt mismatch"):
                cps.package(root)
            self.assertFalse((root / cps.DATA / "output").exists())
            filename.write_bytes(original)
            manifest = root / cps.DATA / "sources.json"
            original_manifest = manifest.read_bytes()
            manifest.write_text("{}")
            with self.assertRaisesRegex(ValueError, "Frozen source manifest changed"):
                cps.review(root)
            manifest.write_bytes(original_manifest)
            (root / cps.SHARED).write_text("changed")
            with self.assertRaisesRegex(ValueError, "Frozen state-name reference changed"):
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
                self.assertEqual(sum(name.endswith(".xls") for name in inventory), 5)
                self.assertEqual(sum(name.endswith(".html") for name in inventory), 3)
                self.assertEqual(json.loads(archive.read("results/observations.json")), self.rows)
                self.assertEqual(len(list(csv.DictReader(io.StringIO(
                    archive.read("results/observations.csv").decode())))), 2375)
                self.assertTrue(set(cps.CODE) <= set(inventory))
                for name, expected in inventory.items():
                    raw = archive.read(name)
                    self.assertEqual({"bytes": len(raw), "sha256": cps.sha(raw)}, expected)
            (root / cps.DATA / "output/display.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Frozen output changed"):
                cps.package(root)


if __name__ == "__main__":
    unittest.main()
