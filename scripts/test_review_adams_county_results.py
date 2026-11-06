import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data/county-source-reviews/20261106-adams-facts-01"
SPEC = importlib.util.spec_from_file_location("adams", ROOT / "scripts/review-adams-county-results.py")
adams = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adams)


class AdamsFactsTests(unittest.TestCase):
    def setUp(self):
        self.facts = json.loads((PACKAGE / "source-records.json").read_text())

    def test_complete_native_participation_is_not_candidate_votes(self):
        adams.validate(self.facts)
        county = self.facts["reports"][0]["pages"][0]["participation"]
        governor = self.facts["reports"][0]["pages"][1]["contests"][0]
        self.assertEqual(adams.counts(county["ballot_count_literals"]), [42660, 32340, 10320, 0])
        self.assertEqual(adams.counts(county["blank_count_literals"]), [5, 1, 4, 0])
        self.assertEqual(adams.counts(governor["accounting"]["Total Votes Cast"])[0], 42477)
        self.assertNotEqual(county["ballot_count_literals"], governor["accounting"]["Total Votes Cast"])

    def test_reporting_does_not_establish_completion(self):
        self.facts["reports"][0]["pages"][0]["reporting"][1]["reported_literal"] = "53"
        with self.assertRaisesRegex(ValueError, "reporting/completion"):
            adams.validate(self.facts)

    def test_missing_blank_or_provisional_is_not_zero(self):
        for field in ("blank_count_literals", "ballot_count_literals"):
            facts = copy.deepcopy(self.facts)
            native = facts["reports"][0]["pages"][0]["participation"]
            if field == "blank_count_literals":
                del native[field]
            else:
                native[field].pop()
            with self.assertRaisesRegex(ValueError, "Incomplete native"):
                adams.validate(facts)

    def test_candidate_and_accounting_corruption_are_rejected(self):
        for key in ("rows", "accounting"):
            facts = copy.deepcopy(self.facts)
            contest = facts["reports"][0]["pages"][1]["contests"][0]
            values = contest[key][0]["count_literals"] if key == "rows" else contest[key]["Undervotes"]
            values[0] = str(adams.integer(values[0]) + 1)
            values[1] = str(adams.integer(values[1]) + 1)
            with self.assertRaisesRegex(ValueError, "accounting does not reconcile"):
                adams.validate(facts)

    def test_missing_or_duplicated_units_and_pages_are_rejected(self):
        for mutation in ("page", "unit"):
            facts = copy.deepcopy(self.facts)
            pages = facts["reports"][1]["pages"]
            if mutation == "page":
                pages.pop()
            else:
                pages[2]["unit"] = pages[0]["unit"]
            with self.assertRaisesRegex(ValueError, "Incomplete|Duplicate"):
                adams.validate(facts)

    def test_literal_candidate_identity_must_reconcile_to_county(self):
        self.facts["reports"][1]["pages"][0]["contests"][0]["rows"][0]["name"] = "Different candidate"
        with self.assertRaisesRegex(ValueError, "candidate identities"):
            adams.validate(self.facts)

    def test_native_time_and_electorate_are_not_replaced(self):
        for mutation in ("timezone", "registration"):
            facts = copy.deepcopy(self.facts)
            page = facts["reports"][0]["pages"][0]
            if mutation == "timezone":
                page["declared_timezone"] = "Eastern"
            else:
                page["participation"]["registered_voters_literal"] = "77,162"
            with self.assertRaisesRegex(ValueError, "status or update|frozen county"):
                adams.validate(facts)

    def test_offline_full_package_reproduces_every_byte(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "facts"
            audit = adams.build(self.facts, output)
            self.assertEqual(audit["table_rows"], {
                "county-participation.csv": 1, "native-unit-participation.csv": 53,
                "county-candidate-results.csv": 13, "native-unit-candidate-results.csv": 530,
                "county-literal-party-totals.csv": 36, "native-contest-accounting.csv": 652,
                "native-reporting-statements.csv": 4, "native-source-pages.csv": 109,
            })
            self.assertEqual({path.name for path in output.iterdir()}, {path.name for path in PACKAGE.iterdir()})
            for path in output.iterdir():
                self.assertEqual(path.read_bytes(), (PACKAGE / path.name).read_bytes(), path.name)


if __name__ == "__main__":
    unittest.main()
