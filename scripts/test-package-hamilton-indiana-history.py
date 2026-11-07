"""Focused preservation, scope, arithmetic and completeness checks."""

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hamilton_history", ROOT / "scripts/package-hamilton-indiana-history.py")
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads((ROOT / history.DATA / "selected-observations.json").read_bytes())
        self.methods = json.loads((ROOT / history.DATA / "methodology-review.json").read_bytes())

    def test_complete_comparisons_preserve_unclassified_counts_and_other_parties(self):
        result = history.review(self.snapshot, self.methods)
        self.assertEqual([row["reported_count_change"] for row in result["reported_count_comparisons"]],
                         [-45184, 20428, -48927])
        self.assertEqual([row["unclassified_reported_count_gap"] for row in result["contests"]], [1964, 8550, 3587])
        self.assertEqual({row["party"] for row in result["contests"][0]["candidates"]}, {"D", "R", "L", "WTP", None})
        self.assertEqual(len(result["native_total_cell_discrepancies"]), 10)
        self.assertTrue(all(value is None for value in result["unsupported_estimates"].values()))
        current = result["contests"][-1]
        self.assertAlmostEqual(current["two_party_margin_pp"], 100 * (81500 - 65570) / (81500 + 65570))
        self.assertNotEqual(current["candidate_total"], current["reported_public_count"])

    def test_partial_or_duplicate_units_and_invalid_counts_are_rejected(self):
        for mutation in ("missing", "duplicate", "boolean", "negative", "mode", "candidate"):
            with self.subTest(mutation=mutation):
                source = copy.deepcopy(self.snapshot)
                row = source["observations"][0]["precincts"][0]
                if mutation == "missing":
                    source["contests"][0]["precincts"].pop()
                elif mutation == "duplicate":
                    source["observations"][0]["precincts"][1]["precinct_id"] = row["precinct_id"]
                elif mutation == "boolean":
                    row["registered_voters"] = True
                elif mutation == "negative":
                    row["election_day"] = -1
                elif mutation == "mode":
                    row["paper_absentee"] += 1
                else:
                    source["contests"][0]["precincts"][0]["candidate_votes"]["Write-In"] += 1
                with self.assertRaises(ValueError):
                    history.review(source, self.methods)

    def test_silent_native_error_repairs_imputed_year_and_population_substitution_refused(self):
        for mutation in ("repair", "year", "population", "party"):
            source = copy.deepcopy(self.snapshot)
            if mutation == "repair":
                source["observations"][1]["native_controls"][0]["total_votes_cast"] = 130376
            elif mutation == "year":
                source["observations"][0]["native_footer_date_literal"] = "Friday, November 13, 2020"
            elif mutation == "population":
                source["contests"][0]["summary_controls"]["public_count"] = 197767
            else:
                source["contests"][1]["candidates"][3]["party"] = "R"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                history.review(source, self.methods)

    def test_private_fields_headers_and_unsupported_claims_refused(self):
        for mutation in ("record", "cookie", "claim", "county"):
            source, methods = copy.deepcopy(self.snapshot), copy.deepcopy(self.methods)
            if mutation == "record":
                source["observations"][0]["precincts"][0]["voter_id"] = "private"
            elif mutation == "cookie":
                next(iter(source["source_receipts"].values()))["headers"]["Set-Cookie"] = "private"
            elif mutation == "claim":
                methods["individual_transitions_qualified"] = True
            else:
                source["scope"]["state_code"] = "OH"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                history.review(source, methods)

    def test_deterministic_complete_archive_and_frozen_output_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in [*(f"{history.DATA}/{name}" for name in history.PINS), *history.CODE]:
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / path, root / path)
            first = history.package(root)
            self.assertEqual(first, history.package(root))
            raw = (root / history.PUBLIC / "complete-analysis.zip").read_bytes()
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                inventory = json.loads(archive.read("checksums.json"))
                self.assertEqual(set(archive.namelist()), {*inventory, "checksums.json"})
                self.assertEqual(first["members"], len(inventory) + 1)
                for name, expected in inventory.items():
                    member = archive.read(name)
                    self.assertEqual(expected, {"bytes": len(member), "sha256": hashlib.sha256(member).hexdigest()})
                self.assertEqual(len(archive.read("results/precinct-participation.csv").splitlines()), 893)
                self.assertEqual(len(archive.read("results/native-controls.csv").splitlines()), 25)
                self.assertTrue(all(not name.endswith((".html", ".pdf")) for name in archive.namelist()))
            (root / history.PUBLIC / "history.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Frozen output"):
                history.package(root)

    def test_changed_reviewed_input_refused_before_any_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / history.DATA / "selected-observations.json"
            path.parent.mkdir(parents=True)
            path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "Reviewed input changed"):
                history.package(root)
            self.assertFalse((root / history.PUBLIC).exists())


if __name__ == "__main__":
    unittest.main()
