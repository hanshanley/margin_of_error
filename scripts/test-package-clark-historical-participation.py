import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile


spec = importlib.util.spec_from_file_location(
    "package_clark", Path(__file__).with_name("package-clark-historical-participation.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ROOT = Path(__file__).resolve().parents[1]


class ClarkPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        paths = [*module.CODE, f"{module.DATA}/pdf-source-consistency.json",
                 f"{module.SOURCE}/sources.json", f"{module.SOURCE}/checksums.json"]
        paths.extend(f"{module.SOURCE}/originals/{key}.gz"
                     for report in module.history.REPORTS for key in report[2:])
        for name in paths:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def test_complete_native_inputs_every_precinct_mode_and_exact_reproduction(self):
        metadata = module.package(self.root)
        out = self.root / module.PUBLIC
        raw = (out / metadata["file"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), metadata["sha256"])
        self.assertEqual(len(raw), metadata["bytes"])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(len(archive.namelist()), metadata["members"])
            inventory = json.loads(archive.read("checksums.json"))
            self.assertEqual(set(inventory), set(archive.namelist()) - {"checksums.json"})
            for name, expected in inventory.items():
                member = archive.read(name)
                self.assertEqual(expected, {"bytes": len(member),
                                            "sha256": hashlib.sha256(member).hexdigest()})
            selected = [name for name in inventory if "/originals/" in name]
            self.assertEqual(len(selected), 8)
            result = json.loads(archive.read("results/native-counts.json"))
            rows = list(csv.DictReader(io.StringIO(
                archive.read("results/precinct-participation.csv").decode())))
            units = [(report, unit) for report in result["observations"] for unit in report["units"]]
            self.assertEqual(len(rows), len(units))
            for row, (report, unit) in zip(rows, units):
                self.assertEqual(row["native_precinct_id"], unit["native_precinct_id"])
                self.assertEqual(int(row["native_registration_once"]), unit["native_registration"])
                self.assertEqual(int(row["native_turnout"]), unit["native_turnout"])
                self.assertEqual(int(row["year"]), report["year"])
                self.assertEqual(row["native_contest"], report["native_contest"])
                for column, mode in zip(("election_day", "early_vote", "mail"), module.history.MODES):
                    self.assertEqual(int(row[column]), unit["native_turnout_by_mode"][mode])
                self.assertEqual(row["qualified_turnout_rate"], "")
                self.assertEqual(row["turnout_exceeds_registration"],
                                 str(unit["turnout_exceeds_registration"]).lower())
            self.assertEqual(archive.read(f"{module.PUBLIC}/summary.json"),
                             (out / "summary.json").read_bytes())
        self.assertEqual(module.package(self.root), metadata)
        self.assertEqual((out / metadata["file"]).read_bytes(), raw)

    def test_descriptive_summary_retains_contest_difference_and_withheld_outcomes(self):
        module.package(self.root)
        result = json.loads((self.root / module.PUBLIC / "summary.json").read_bytes())
        difference = result["same_year_contest_scope"]
        self.assertFalse(difference["same_electorate_qualified"])
        self.assertEqual(difference["president_minus_senate_native_turnout"], 40)
        for field in ("precinct_maps_qualified", "cross_year_precinct_comparisons_qualified",
                      "all_county_ballot_universe_independently_qualified"):
            self.assertFalse(result[field])
        for field in ("measured_prior_voter_dropoff", "new_or_returning_voters",
                      "party_switchers", "demographic_turnout_rate"):
            self.assertIsNone(result[field])
        for row in result["observations"]:
            self.assertIsNone(row["qualified_turnout_rate"])
            self.assertNotIn("units", row)
            self.assertGreater(row["turnout_exceeds_registration_units"], 0)
        self.assertFalse(result["independent_pdf_check"]["fresh_pdf_check_rerun_by_packager"])

    def test_changed_proof_reviewer_or_compressed_source_fails_before_output(self):
        for name, message in (
            (f"{module.DATA}/pdf-source-consistency.json", "receipt"),
            (module.CODE[0], "implementation"),
            (f"{module.SOURCE}/originals/2020/154.txt.gz", "inventory"),
        ):
            path = self.root / name
            original = path.read_bytes()
            changed = bytearray(original)
            if name.endswith(".gz"):
                changed[4] ^= 1
            else:
                changed.extend(b"\n")
            path.write_bytes(changed)
            with self.subTest(name=name), self.assertRaises((ValueError, EOFError)):
                module.package(self.root)
            self.assertFalse((self.root / module.PUBLIC).exists(), message)
            path.write_bytes(original)

    def test_missing_original_or_changed_source_manifest_is_not_metadata_only_fallback(self):
        original = self.root / module.SOURCE / "originals/2024/081.pdf.gz"
        original.unlink()
        with self.assertRaises(FileNotFoundError):
            module.package(self.root)
        self.assertFalse((self.root / module.PUBLIC).exists())
        manifest = self.root / module.SOURCE / "sources.json"
        manifest.write_text("{}")
        with self.assertRaisesRegex(ValueError, "complete reviewed Clark source manifest"):
            module.package(self.root)

    def test_frozen_output_conflict_does_not_partially_rewrite_other_outputs(self):
        out = self.root / module.PUBLIC
        out.mkdir(parents=True)
        (out / "download.json").write_bytes(b"already frozen\n")
        with self.assertRaisesRegex(ValueError, "Frozen Clark output"):
            module.package(self.root)
        self.assertEqual((out / "download.json").read_bytes(), b"already frozen\n")
        self.assertEqual([path.name for path in out.iterdir()], ["download.json"])


if __name__ == "__main__":
    unittest.main()
