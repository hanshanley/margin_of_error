import copy
import gzip
import importlib.util
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch


here = Path(__file__).parent
spec = importlib.util.spec_from_file_location("columbia", here / "review-columbia-county-native-query.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
source = here / "source-records.json.gz"
if not source.exists():
    source = here / "clinton-columbia-clearfield-primary-20261106-01/columbia-complete-reviewed-source-input-01.json"
body = source.read_bytes()
FACTS = json.loads(gzip.decompress(body) if source.suffix == ".gz" else body)


class CompleteColumbiaQuery(unittest.TestCase):
    def test_complete_native_query(self):
        tables = module.review(FACTS)
        self.assertEqual(len(tables["native-mail-cell-review.csv"]), 105)
        self.assertEqual(len(tables["county-candidate-results.csv"]), 10)
        self.assertEqual(len(tables["county-contest-accounting.csv"]), 3)
        self.assertEqual(tables["county-participation.csv"][0]["ballots_cast"], 22583)
        self.assertEqual(tables["native-mail-ballot-styles.csv"][0]["native_label"], "")
        self.assertEqual(tables["native-source-pages.csv"][1]["source_update_literal"], "")
        self.assertEqual(tables["native-source-pages.csv"][0]["declared_timezone"], "EST")
        self.assertTrue(any(row["rapidocr_literals"] != row["apple_vision_literals"]
                            for row in tables["native-mail-cell-review.csv"]))

    def test_paired_text_change_cannot_relabel_source_candidate(self):
        facts = copy.deepcopy(FACTS)
        facts["native_layout"] = {key: value.replace("RACHEL WALLACE", "ANOTHER CANDIDATE")
                                  for key, value in facts["native_layout"].items()}
        with self.assertRaisesRegex(ValueError, "Changed complete independently reviewed source query"):
            module.review(facts)

    def test_semantic_fail_closed_guards_beyond_snapshot_pin(self):
        mutations = (
            ("missing category", lambda value: value["mail_sections"]["registration_parties"].pop()),
            ("changed cell", lambda value: value["mail_sections"]["application_types"][0]["values"].__setitem__(4, 8)),
            ("changed repeated total", lambda value: value["mail_totals"]["ballot_styles"].__setitem__(4, 3773)),
            ("relabeled registration party", lambda value: value["mail_sections"]["registration_parties"][5].__setitem__("native_label", "REPUBLICAN")),
            ("invented ballot style", lambda value: value["mail_sections"]["ballot_styles"][0].__setitem__("native_label", "All")),
            ("omitted mail column", lambda value: value["mail_sections"]["ballot_styles"][0]["values"].pop()),
            ("changed receipt", lambda value: value["source_receipts"][1].__setitem__("sha256", "0" * 64)),
            ("unauthorized map", lambda value: value.__setitem__("maps_approved", True)),
            ("invented mail time", lambda value: value["native_mail_headers"].__setitem__("native_update_time_literal", "22:23:41")),
            ("changed electorate filter", lambda value: value["native_mail_headers"].__setitem__("source_filter", "")),
        )
        with patch.object(module, "REVIEWED_INPUT_SHA256", ""):
            for name, mutate in mutations:
                with self.subTest(name=name):
                    facts = copy.deepcopy(FACTS)
                    mutate(facts)
                    with self.assertRaises((ValueError, IndexError)):
                        module.review(facts)

    def test_native_summary_guards_beyond_snapshot_pin(self):
        mutations = (
            ("candidate sum as ballots", r"Total Ballots 22,583", "Total Ballots 22,422"),
            ("candidate arithmetic", r"10,354", "10,355"),
            ("missing source timezone", r"10:37:16 PM EST", "10:37:16 PM"),
            ("false zero write-in", r"33\s+0\.15%", "0 0.15%"),
            ("wrong registration denominator", r"40,797", "40,897"),
            ("removed candidate", r"Write-in\s+33\s+0\.15%", ""),
        )
        with patch.object(module, "REVIEWED_INPUT_SHA256", ""):
            for name, pattern, replacement in mutations:
                with self.subTest(name=name):
                    facts = copy.deepcopy(FACTS)
                    for engine in facts["native_layout"]:
                        text, count = re.subn(pattern, replacement, facts["native_layout"][engine])
                        self.assertEqual(count, 1)
                        facts["native_layout"][engine] = text
                    with self.assertRaises((ValueError, IndexError)):
                        module.review(facts)

    def test_no_single_ocr_engine_is_claimed_to_support_every_cell(self):
        facts = copy.deepcopy(FACTS)
        facts["ocr"]["rapidocr"]["results"] = []
        with patch.object(module, "REVIEWED_INPUT_SHA256", ""):
            with self.assertRaisesRegex(ValueError, "No independent OCR evidence"):
                module.review(facts)
        facts = copy.deepcopy(FACTS)
        facts["ocr"]["apple_vision"][0]["lines"] = []
        with patch.object(module, "REVIEWED_INPUT_SHA256", ""):
            with self.assertRaisesRegex(ValueError, "No independent OCR evidence"):
                module.review(facts)


if __name__ == "__main__":
    unittest.main()
