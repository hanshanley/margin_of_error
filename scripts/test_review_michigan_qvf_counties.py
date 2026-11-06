import copy
import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mi_qvf", HERE / "review-michigan-qvf-counties.py")
mi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mi)
spec_acquire = importlib.util.spec_from_file_location(
    "mi_acquire", HERE / "acquire-michigan-qvf-counties.py")
acquire = importlib.util.module_from_spec(spec_acquire)
spec_acquire.loader.exec_module(acquire)


class MichiganQvfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = [
            HERE / "native-facts.json",
            HERE.parent / "data/county-source-reviews/20261106-michigan-qvf-facts-01/native-facts.json",
        ]
        cls.facts = json.loads(next(path for path in paths if path.is_file()).read_text())

    def changed(self):
        return copy.deepcopy(self.facts)

    def reseal(self, evidence, value):
        body = mi.encoded(value)
        evidence.update(text=body.decode(), bytes=len(body), sha256=mi.sha(body))

    def test_complete_native_query_preserves_scope_without_approving_ballots_or_rates(self):
        outputs = mi.review(self.facts)
        audit = json.loads(outputs["audit.json"])
        rows = list(csv.DictReader(io.StringIO(outputs["county-participation.csv"].decode())))
        total = sum(int(row["native_qvf_recorded_total"]) for row in rows)
        self.assertEqual(audit["complete_native_county_total_sum"], total)
        self.assertEqual(audit["unallocated_statewide_minus_native_county_total"],
                         audit["statewide_native_qvf_total"] - total)
        self.assertTrue(any(row["all_native_modes_numeric"] == "true" for row in rows))
        for row in rows:
            self.assertEqual(row["native_county_active_registration_denominator"], "")
            self.assertEqual(row["tabulator_ballots"], "")
            self.assertEqual(row["generic_registration_fraction"], "")
            self.assertEqual(row["maps_approved"], "false")
            self.assertEqual(row["rates_approved"], "false")

    def test_native_discrepancy_is_preserved_without_rebalancing(self):
        facts = self.changed()
        selected = next(row for row in facts["counties"] if row["county"] == "Alger")
        response = mi.unpack(selected["response"])
        row = response["results"][0]["result"]["data"]["dsr"]["DS"][0]["PH"][0]["DM7"][0]
        index = next(i for i, column in enumerate(row["S"]) if column["N"] == "M13")
        changed_total = mi.number(row["C"][index]) + 7
        row["C"][index] = str(changed_total)
        self.reseal(selected["response"], response)
        selected["rendered_native_fields"][mi.FIELDS[6]] = format(changed_total, ",")
        outputs = mi.review(facts)
        audit = json.loads(outputs["audit.json"])
        rows = list(csv.DictReader(io.StringIO(outputs["county-participation.csv"].decode())))
        alger = next(row for row in rows if row["native_county_name"] == "Alger")
        self.assertEqual(int(alger["native_qvf_recorded_total"]), changed_total)
        self.assertEqual(alger["all_numeric_modes_reconcile"], "false")
        self.assertFalse(audit["native_county_totals_match_statewide"])
        self.assertEqual(alger["tabulator_ballots"], "")

    def test_unavailable_election_day_is_not_zero_or_a_complete_total(self):
        outputs = mi.review(self.facts)
        rows = list(csv.DictReader(io.StringIO(outputs["county-participation.csv"].decode())))
        alcona = next(row for row in rows if row["native_county_name"] == "Alcona")
        self.assertTrue(alcona["native_qvf_recorded_total"])
        self.assertEqual(alcona["qvf_election_day"], "")
        self.assertEqual(alcona["all_native_modes_numeric"], "false")
        self.assertEqual(alcona["all_numeric_modes_reconcile"], "")
        self.assertIn("No data available", alcona["native_election_day_literal"])
        self.assertTrue(alcona["native_active_registered_turnout_literal"])
        self.assertEqual(alcona["generic_registration_fraction"], "")
        gladwin = next(row for row in rows if row["native_county_name"] == "Gladwin")
        self.assertEqual(gladwin["native_election_day_status"], "source_suppressed_less_than_10")
        self.assertEqual(gladwin["qvf_election_day"], "")
        self.assertEqual(gladwin["all_numeric_modes_reconcile"], "")

    def test_zero_and_unavailable_remain_distinct(self):
        self.assertEqual(mi.number("0L"), 0)
        self.assertEqual(mi.number(0), 0)
        self.assertIsNone(mi.number("'No data available'"))
        self.assertIsNone(mi.number("'Less than 10'"))
        with self.assertRaises(ValueError):
            mi.number(False)

    def test_exact_value_not_rendered_by_source_cannot_be_published(self):
        facts = self.changed()
        selected = facts["counties"][0]
        selected["rendered_native_fields"][mi.FIELDS[5]] = "Less than 10"
        with self.assertRaisesRegex(ValueError, "rendered numerical facts disagree"):
            mi.review(facts)

    def test_changed_entire_response_is_rejected(self):
        facts = self.changed()
        facts["counties"][0]["response"]["text"] += " "
        with self.assertRaisesRegex(ValueError, "Changed entire native evidence"):
            mi.review(facts)

    def test_one_wrong_measure_county_is_rejected_even_with_valid_checksums(self):
        facts = self.changed()
        evidence = facts["counties"][0]["request"]
        request = mi.unpack(evidence)
        for item in mi.tree(request):
            clause = item.get("In", {})
            if any(expression.get("Column", {}).get("Property") == "COUNTY_NAME"
                   for expression in clause.get("Expressions", [])):
                clause["Values"][0][0]["Literal"]["Value"] = "'Alger'"
                break
        self.reseal(evidence, request)
        with self.assertRaisesRegex(ValueError, "single-county scope"):
            mi.review(facts)

    def test_one_wrong_measure_election_is_rejected(self):
        facts = self.changed()
        evidence = facts["counties"][0]["request"]
        body = evidence["text"].replace(mi.ELECTION, "2024 General Election", 1).encode()
        evidence.update(text=body.decode(), bytes=len(body), sha256=mi.sha(body))
        with self.assertRaisesRegex(ValueError, "election"):
            mi.review(facts)

    def test_missing_county_and_mixed_clocks_are_rejected(self):
        facts = self.changed()
        facts["counties"].pop()
        with self.assertRaisesRegex(ValueError, "county scope"):
            mi.review(facts)
        facts = self.changed()
        facts["counties"][0]["native_clock_literal"] += " UTC"
        with self.assertRaisesRegex(ValueError, "refresh clocks"):
            mi.review(facts)

    def test_delayed_statewide_response_cannot_be_a_county(self):
        facts = self.changed()
        facts["counties"][0].update(copy.deepcopy(facts["statewide"]))
        with self.assertRaisesRegex(ValueError, "single-county scope"):
            mi.review(facts)

    def test_native_collector_skips_delayed_statewide_card_but_requires_exact_county(self):
        selected = self.facts["counties"][0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = []
            for sequence, evidence in enumerate((self.facts["statewide"], selected), 1):
                record = dict(sequence=sequence, phase="county:" + selected["county"], status=200)
                for source_key, key in (("request", "native_request"), ("response", "response")):
                    body = evidence[source_key]["text"].encode()
                    name = "%d-%s.json" % (sequence, key)
                    (root / name).write_bytes(body)
                    record[key] = dict(file=name, bytes=len(body), sha256=mi.sha(body))
                records.append(record)
            result = acquire.matching_card(root, records, selected["county"], 1)
            self.assertEqual(result["evidence"]["sequence"], 2)
            with self.assertRaisesRegex(ValueError, "exactly one"):
                acquire.matching_card(root, records, selected["county"], 3)


if __name__ == "__main__":
    unittest.main()
