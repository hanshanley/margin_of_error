"""Test preservation of denominator, native-bin and withholding boundaries."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


spec = importlib.util.spec_from_file_location(
    "unified", Path(__file__).with_name("package-cps-unified-history.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class UnifiedHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.displays, cls.members = module.read_sources(module.ROOT)
        cls.rows, cls.display, cls.summary = module.join(cls.displays)
        cls.index = {(r["geography"], r["group"], r["year"]): r for r in cls.rows}

    def row(self, state, group, year):
        return self.index[state, group, year]

    def test_denominators_and_native_values_are_not_spliced(self):
        adult = self.row("United States (including D.C.)", "Total", 2004)
        citizen = self.row("United States (including D.C.)", "Total", 2024)
        self.assertEqual(adult["denominator"], "all_adults_18_plus")
        self.assertEqual(adult["reported_voting_pct"], 58.3)
        self.assertEqual(citizen["denominator"], "citizen_adults_18_plus")
        self.assertEqual(citizen["reported_voting_pct"], 65.3)
        self.assertEqual(self.row("Alabama", "Total", 2022)["election_type"], "midterm")

    def test_unlabeled_national_blocks_are_not_assigned(self):
        national = "United States (including D.C.)"
        self.assertEqual(self.row(national, "Total", 2006)["status"], "not_supplied")
        self.assertEqual(self.row(national, "Male", 2008)["status"], "not_supplied")
        overall = self.row(national, "Total", 2008)
        self.assertEqual(overall["status"], "published_native_rate")
        source = self.displays["early"][int(overall["source_display_pointer"].split("/")[1])]
        self.assertEqual((source["role"], source["geography"]), ("age", "UNITED STATES"))

    def test_exact_native_age_bins_are_not_merged_or_split(self):
        self.assertEqual(self.row("Alabama", "25 to 34", 2010)["status"], "not_supplied")
        self.assertEqual(self.row("Alabama", "25 to 44", 2010)["status"], "published_native_rate")
        self.assertEqual(self.row("Alabama", "25 to 44", 2012)["status"], "not_supplied")
        self.assertEqual(self.row("Alabama", "65+", 2010)["status"], "not_supplied")
        self.assertEqual(self.row("Alabama", "65 to 74", 2010)["status"], "published_native_rate")
        self.assertEqual(self.row("Alabama", "18 to 24", 2006)["status"], "not_supplied")

    def test_conflicts_and_out_of_range_rows_remain_withheld(self):
        for state in ("Florida", "Georgia", "Hawaii"):
            row = self.row(state, "Total", 2008)
            self.assertEqual(row["status"], "withheld_conflicting_same_year_total")
            self.assertIsNone(row["reported_voting_pct"])
        row = self.row("South Dakota", "White alone or in combination", 2008)
        self.assertEqual(row["status"], "withheld_native_out_of_range_metric")
        self.assertIsNone(row["reported_voting_pct"])
        self.assertNotIn("Non-Hispanic White", self.display["groups"])

    def test_every_populated_value_matches_its_exact_source_pointer(self):
        for row in self.rows:
            pointer = row["source_display_pointer"]
            if pointer is None:
                self.assertEqual(row["status"], "not_supplied")
                continue
            value = self.displays[row["source_package"]]
            for part in pointer.strip("/").split("/"):
                value = value[int(part)] if isinstance(value, list) else value[part]
            if isinstance(value, dict):
                self.assertEqual(row["status"], value["status"])
                self.assertEqual(row["reported_voting_pct"], value["rate_pct"])
                self.assertEqual(row["native_moe90_pp"], value["native_moe90_pp"])
            elif len(value) == 2:
                self.assertEqual([row["reported_voting_pct"], row["native_moe90_pp"]], value)
            else:
                self.assertEqual(row["status"], module.NUMERIC_STATUSES[value[0]])

    def test_changed_source_shape_or_denominator_is_refused(self):
        for change in ("duplicate", "denominator", "states"):
            data = copy.deepcopy(self.displays)
            if change == "duplicate":
                data["early"][1] = data["early"][0]
            elif change == "denominator":
                data["early"][0]["display"]["denominator"] = "citizen_adults_18_plus"
            else:
                data["older"]["states"][1] = "Unknown"
            with self.assertRaises(ValueError):
                module.join(data)

    def test_changed_frozen_source_hash_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / next(iter(self.members))
            path.parent.mkdir(parents=True)
            path.write_bytes(b"{}")
            with self.assertRaisesRegex(ValueError, "Changed frozen input"):
                module.read_sources(root)

    def test_complete_archive_reproduces_offline_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            receipt = module.package(output=first)
            archive_path = first / "complete-analysis.zip"
            with zipfile.ZipFile(archive_path) as archive:
                inventory = json.loads(archive.read("checksums.json"))
                self.assertEqual(set(archive.namelist()), {*inventory, "checksums.json"})
                for name, metadata in inventory.items():
                    raw = archive.read(name)
                    self.assertEqual(len(raw), metadata["bytes"])
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), metadata["sha256"])
                self.assertEqual(sum(name.endswith("/complete-analysis.zip") for name in inventory), 3)
                archive.extractall(root / "isolated")
            reproduced = module.package(root=root / "isolated", output=root / "second")
            self.assertEqual(receipt, reproduced)
            self.assertEqual(archive_path.read_bytes(), (root / "second/complete-analysis.zip").read_bytes())
            (first / "display.json").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Frozen output changed"):
                module.package(output=first)


if __name__ == "__main__":
    unittest.main()
