import copy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("utah_query", HERE / "review-counties.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
INPUT = json.loads((HERE / "source-qualification.json").read_text())


class UtahQueryTest(unittest.TestCase):
    def test_latest_counted_totals_do_not_add_davis_snapshots(self):
        result = module.review(INPUT)
        counties = {row["native_county"]: row for row in result["counties"]}
        self.assertEqual(len(counties), 29)
        self.assertEqual(counties["Davis County"]["ballots_counted"], 115308)
        self.assertEqual(counties["Davis County"]["source_ordinal"], 26)
        self.assertEqual(len([row for row in result["receipts"] if row["native_county"] == "Davis County"]), 2)
        changed = copy.deepcopy(INPUT)
        next(row for row in changed["reports"] if row["source_ordinal"] == 6)["latest_selection"] = True
        with self.assertRaisesRegex(ValueError, "Multiple latest"):
            module.review(changed)

    def test_received_processed_scanned_daily_and_credit_stay_withheld(self):
        result = module.review(INPUT)
        counties = {row["native_county"]: row for row in result["counties"]}
        for name in ("Cache", "Garfield", "Iron", "Kane", "Millard", "San Juan"):
            self.assertIsNone(counties[name + " County"]["ballots_counted"])
        for ordinal, invalid_count in ((10, 2060), (11, 4049), (14, 3391), (16, 17611), (18, 41680), (22, 5596)):
            changed = copy.deepcopy(INPUT)
            next(row for row in changed["reports"] if row["source_ordinal"] == ordinal)["fields"]["ballots_counted"] = invalid_count
            with self.assertRaisesRegex(ValueError, "not counted totals"):
                module.review(changed)

    def test_missing_reports_and_dash_are_not_backend_zeros(self):
        result = module.review(INPUT)
        missing = [row for row in result["counties"] if row["source_scope_review"] == "missing_declared_report"]
        self.assertEqual([row["native_county"] for row in missing],
                         ["Daggett County", "Morgan County", "Piute County", "Wasatch County"])
        self.assertTrue(all(row["ballots_counted"] is None for row in missing))
        weber = next(row for row in result["observations"] if row["native_county"] == "Weber County"
                     and row["scope"] == "fields" and row["field"] == "incurable_ballots")
        self.assertIsNone(weber["value"])
        self.assertEqual(weber["value_state"], "missing")

    def test_same_report_denominators_are_not_registration_pdf_substitutes(self):
        rows = {row["native_county"]: row for row in module.review(INPUT)["counties"]}
        self.assertEqual(rows["Salt Lake County"]["registered_voters"], 604694)
        self.assertEqual(rows["Wayne County"]["registered_voters"], 1827)
        self.assertIsNone(rows["Box Elder County"]["registered_voters"])
        self.assertEqual(rows["Wayne County"]["ballots_counted"], 1109)

    def test_literal_clocks_and_tabulation_discrepancies_are_not_repaired(self):
        result = module.review(INPUT)
        rows = {row["native_county"]: row for row in result["counties"]}
        self.assertEqual(rows["Uintah County"]["source_updated_literal"], "11/03/2026 11:18 a.m.")
        self.assertIsNone(rows["Wayne County"]["source_updated_literal"])
        self.assertTrue(all(row["source_timezone_literal"] is None for row in rows.values()))
        reconciliation = {row["field"]: row["value"] for row in result["observations"]
                          if row["native_county"] == "Wayne County" and row["scope"] == "reconciliation"}
        self.assertEqual(reconciliation["tabulated_ballots"], 1109)
        self.assertEqual(reconciliation["voters_given_credit"], 1209)
        self.assertEqual(reconciliation["native_difference"], 100)

    def test_all_registration_rows_preserve_native_arithmetic_and_absences(self):
        result = module.review(INPUT)
        self.assertEqual(len(result["registrations"]), 228)
        self.assertEqual(sum(row["active_registered_voters"] for row in result["registrations"]), 1784255)
        republican = next(row for row in result["state_registrations"] if row["party_literal"] == "Republican")
        self.assertEqual(republican["active"] + republican["inactive"] - republican["total"], 1)
        self.assertFalse(any(row["county_literal"] == "Piute" and row["party_literal"] == "Green"
                             for row in result["registrations"]))
        changed = copy.deepcopy(INPUT)
        changed["registration_review"]["native_rows"].append(
            dict(county_literal="Piute", party_literal="Green", active_registered_voters=0))
        with self.assertRaisesRegex(ValueError, "registration rows"):
            module.review(changed)

    def test_native_scope_and_supersession_fail_closed(self):
        changed = copy.deepcopy(INPUT)
        next(row for row in changed["reports"] if row["source_ordinal"] == 6)["superseded_for_latest_selection_by_ordinal"] = 25
        with self.assertRaisesRegex(ValueError, "superseded"):
            module.review(changed)
        changed = copy.deepcopy(INPUT)
        changed["map_approved"] = True
        with self.assertRaisesRegex(ValueError, "not geographic"):
            module.review(changed)

    def test_complete_archive_reproduces_offline_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "original"
            module.build(original)
            with zipfile.ZipFile(original / "complete-query.zip") as archive:
                self.assertEqual(len(archive.namelist()), 12)
                self.assertNotIn("complete-query.zip", archive.namelist())
                archive.extractall(root / "extracted")
            manifest = json.loads((root / "extracted/checksums.json").read_text())
            for entry in manifest["files"]:
                body = (root / "extracted" / entry["path"]).read_bytes()
                self.assertEqual(len(body), entry["bytes"])
                self.assertEqual(hashlib.sha256(body).hexdigest(), entry["sha256"])
            subprocess.run([sys.executable, "-B", "-I", str(root / "extracted/review-counties.py"),
                            "--output", str(root / "reproduced")], check=True, stdout=subprocess.DEVNULL)
            self.assertEqual({path.name for path in original.iterdir()},
                             {path.name for path in (root / "reproduced").iterdir()})
            for path in original.iterdir():
                self.assertEqual(path.read_bytes(), (root / "reproduced" / path.name).read_bytes(), path.name)
            with zipfile.ZipFile(original / "complete-query.zip") as archive:
                rows = list(csv.DictReader(io.StringIO(archive.read("county-participation.csv").decode())))
                self.assertEqual(len(rows), 29)
                self.assertEqual(sum(bool(row["ballots_counted"]) for row in rows), 19)
                statistics = list(csv.DictReader(io.StringIO(archive.read("source-native-observations.csv").decode())))
                self.assertEqual(len(statistics), len(module.review(INPUT)["observations"]))

    def test_refuses_to_mutate_existing_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "overwrite"):
                module.build(temporary)


if __name__ == "__main__":
    unittest.main()
