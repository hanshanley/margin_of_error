import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


spec = importlib.util.spec_from_file_location(
    "nd_long_package", Path(__file__).with_name("package-north-dakota-long-ballot-history.py"))
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)
spec = importlib.util.spec_from_file_location(
    "nd_long_fixtures", Path(__file__).with_name("test-review-north-dakota-long-ballot-history.py"))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def selected():
    return {
        "observations": fixtures.observations(),
        "source_receipts": json.loads(
            (package.ROOT / package.DATA / "selected-observations.json").read_text())["source_receipts"],
        "prior_selected_sha256": package.history.PRIOR_SHA256,
    }


def methods():
    return json.loads((package.ROOT / package.DATA / "methodology-review.json").read_text())


class NorthDakotaLongPackageTests(unittest.TestCase):
    def test_complete_comparison_preserves_native_names_and_unsupported_nulls(self):
        result = package.review(selected(), methods())
        self.assertEqual(len(result["counties"]), 53)
        self.assertEqual(result["statewide"]["reported_count_change_since"]["2018"], -53)
        self.assertIsNone(result["statewide"]["measured_prior_voter_dropoff"])
        self.assertFalse(result["individual_transitions_qualified"])

    def test_scope_and_promoted_claims_fail(self):
        for key, value in (("state_code", "SD"), ("years", [2022, 2024, 2026]),
                           ("individual_transitions_qualified", True),
                           ("demographic_turnout_rates_qualified", True),
                           ("personal_records_included", True)):
            changed = methods()
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                package.review(selected(), changed)

    def test_missing_receipt_wrong_url_and_private_fields_fail(self):
        for mutation in ("missing", "url", "private", "hash", "chain"):
            snapshot = selected()
            receipt = snapshot["source_receipts"]["2016-turnout"]
            if mutation == "missing":
                del snapshot["source_receipts"]["2016-landing"]
            elif mutation == "url":
                receipt["url"] = "https://example.com/"
            elif mutation == "private":
                receipt["response_headers"] = {"Set-Cookie": "not permitted"}
            elif mutation == "hash":
                receipt["sha256"] = "wrong"
            else:
                receipt["declared_by"]["sha256"] = "0" * 64
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                package.review(snapshot, methods())

    def test_csv_preserves_named_and_numeric_unit_fields_without_crosswalk(self):
        snapshot = selected()
        raw = package.unit_csv(snapshot["observations"])
        rows = list(csv.DictReader(io.StringIO(raw.decode())))
        self.assertEqual(len(rows), 318)
        self.assertEqual(rows[0]["native_county_id"], "01")
        self.assertEqual(rows[0]["native_unit_field"], "precinct_label")
        self.assertEqual(rows[0]["native_unit_value"], "Precinct 1 & mail")
        numeric = next(row for row in rows if row["year"] == "2022")
        self.assertEqual(numeric["native_unit_field"], "precinct_id")
        self.assertEqual(numeric["native_unit_value"], "010001")

    def test_deterministic_archive_binds_every_complete_member(self):
        contents = {"selected.json": b'{"all_facts":true}\n', "results.csv": b"native,counts\n"}
        first = package.archive_bytes(contents)
        self.assertEqual(first, package.archive_bytes(dict(reversed(list(contents.items())))))
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            inventory = json.loads(archive.read("checksums.json"))
            self.assertEqual(set(archive.namelist()), {*contents, "checksums.json"})
            for name, raw in contents.items():
                self.assertEqual(archive.read(name), raw)
                self.assertEqual(inventory[name],
                                 {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})

    def test_pinned_input_tampering_fails_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / package.DATA
            data.mkdir(parents=True)
            first = next(iter(package.PINS))
            (data / first).write_text("{}\n")
            with self.assertRaises(ValueError):
                package.package(root)
            self.assertFalse((root / package.PUBLIC).exists())

    def test_missing_field_count_and_relabelled_native_unit_fail(self):
        for mutation in ("unit", "count", "private"):
            snapshot = selected()
            unit = snapshot["observations"][0]["counties"][0]["precincts"][0]
            if mutation == "unit":
                unit["precinct_id"] = unit.pop("precinct_label")
            elif mutation == "count":
                unit["ballots"] = True
            else:
                unit["private_id"] = "not permitted"
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, KeyError)):
                package.review(snapshot, methods())


if __name__ == "__main__":
    unittest.main()
