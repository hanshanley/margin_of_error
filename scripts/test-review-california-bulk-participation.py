import collections
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/review-california-bulk-participation.py"
SPEC = importlib.util.spec_from_file_location("california_review", SCRIPT)
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)
FACTS = ROOT / "data/county-source-reviews/20261106-california-facts-01"


class CaliforniaReviewTests(unittest.TestCase):
    def setUp(self):
        self.inputs = {name: (FACTS / name).read_bytes() for name in REVIEW.BASE_NAMES}

    def change_json(self, name, predicate, mutate):
        rows = REVIEW.records(self.inputs[name])
        selected = 0
        for row in rows:
            value = json.loads(row["native_record_json"])
            if predicate(row, value):
                mutate(value)
                row["native_record_json"] = REVIEW.encoded(value)
                selected += 1
        self.assertEqual(selected, 1)
        self.inputs[name] = REVIEW.table(rows)

    def change_text(self, name, predicate, mutate):
        rows = REVIEW.records(self.inputs["native-text-records.csv"])
        restored, selected = bytearray(), 0
        for row in rows:
            if row["source_file"] != name:
                continue
            value = json.loads(row["native_fields_json"])
            if predicate(value):
                mutate(value)
                row["native_fields_json"] = REVIEW.encoded(value)
                selected += 1
            literal = "[" + "|".join(value) + "]" + json.loads(row["native_line_ending_json"])
            restored.extend(literal.encode(row["decoding"].replace("-sig", "")))
        self.assertEqual(selected, 1)
        self.inputs["native-text-records.csv"] = REVIEW.table(rows)
        sources = REVIEW.records(self.inputs["sources.csv"])
        for source in sources:
            if source["source_file"] == name:
                source["bytes"] = str(len(restored))
                source["sha256"] = REVIEW.hashlib.sha256(restored).hexdigest()
        self.inputs["sources.csv"] = REVIEW.table(sources)

    def test_complete_query_reproduces_every_file_and_zip_offline(self):
        outputs = REVIEW.package(self.inputs, SCRIPT.read_bytes())
        self.assertEqual(set(outputs), {path.name for path in FACTS.iterdir()})
        for name, body in outputs.items():
            with self.subTest(file=name):
                self.assertEqual(body, (FACTS / name).read_bytes())

    def test_contest_and_party_conservation_keeps_aggregate_scopes_separate(self):
        outputs = REVIEW.reconcile(self.inputs)
        choices = REVIEW.records(outputs["contest-choices.csv"])
        sums, party_sums = collections.Counter(), collections.Counter()
        for row in choices:
            key = row["native_contest_code"], row["native_county_code"]
            sums[key] += int(row["votes"])
            if row["party_not_applicable"] == "false":
                party_sums[key + (row["party_literal"],)] += int(row["votes"])
            else:
                self.assertEqual(row["party_literal"], "")
        for row in REVIEW.records(outputs["contest-totals.csv"]):
            key = row["native_contest_code"], row["native_county_code"]
            self.assertEqual(sums[key], int(row["contest_votes"]))
            self.assertEqual(row["geography_level"] == "county", row["native_county_code"] != "59")
        for row in REVIEW.records(outputs["party-totals.csv"]):
            key = row["native_contest_code"], row["native_county_code"], row["party_literal"]
            self.assertEqual(party_sums.pop(key), int(row["candidate_votes"]))
            self.assertEqual(row["geography_level"] == "county", row["native_county_code"] != "59")
        self.assertFalse(party_sums)

    def test_candidate_substitution_cannot_replace_native_participation(self):
        self.change_json("native-reporting-status.csv", lambda _, row: row["county"] == 1,
                         lambda row: row.update(voterTurnout="309715"))
        with self.assertRaisesRegex(ValueError, "JSON/native participation mismatch"):
            REVIEW.reconcile(self.inputs)

    def test_coherent_county_changes_still_require_statewide_conservation(self):
        self.change_json("native-reporting-status.csv", lambda _, row: row["county"] == 1,
                         lambda row: row.update(voterTurnout="314952"))
        self.change_text("V26GG.txt", lambda row: row[0] == "A" and row[3] == "1",
                         lambda row: row.__setitem__(10, "314952"))
        with self.assertRaisesRegex(ValueError, "County/statewide participation conservation"):
            REVIEW.reconcile(self.inputs)

    def test_paired_native_rate_changes_do_not_bypass_fraction_arithmetic(self):
        self.change_json("native-reporting-status.csv", lambda _, row: row["county"] == 1,
                         lambda row: row.update(voterTurnoutPercentage="33.0"))
        self.change_text("V26GG.txt", lambda row: row[0] == "A" and row[3] == "1",
                         lambda row: row.__setitem__(12, "33.0"))
        with self.assertRaisesRegex(ValueError, "percentage arithmetic mismatch"):
            REVIEW.reconcile(self.inputs)

    def test_changed_candidate_votes_require_independent_native_agreement(self):
        def mutate(row):
            row["candidates"][0]["Votes"] = "245,343"
        self.change_json("native-contest-reports.csv",
                         lambda source, row: source["archive_member"] == "governor.json"
                         and row["raceTitle"] == "Governor - Alameda County Results", mutate)
        with self.assertRaisesRegex(ValueError, "candidate or contest reconciliation"):
            REVIEW.reconcile(self.inputs)

    def test_losing_one_county_or_one_contest_is_not_partial_success(self):
        for name in ("native-reporting-status.csv", "native-contest-reports.csv"):
            with self.subTest(file=name):
                original = self.inputs[name]
                self.inputs[name] = REVIEW.table(REVIEW.records(original)[1:])
                with self.assertRaises(ValueError):
                    REVIEW.reconcile(self.inputs)
                self.inputs[name] = original

    def test_party_code_conflicts_are_not_silently_normalized(self):
        self.change_text("C26GG.txt", lambda row: row[0] == "C"
                         and row[3] == "020000000000" and row[4] == "3654",
                         lambda row: row.__setitem__(9, "02"))
        with self.assertRaisesRegex(ValueError, "Conflicting literal party/code"):
            REVIEW.reconcile(self.inputs)

    def test_coherent_contest_sources_cannot_exceed_native_participation(self):
        def mutate_json(row):
            row["candidates"][0].update(Votes="450,000", Percent="90.0")
            row["candidates"][1].update(Votes="50,000", Percent="10.0")
        self.change_json("native-contest-reports.csv",
                         lambda source, row: source["archive_member"] == "governor.json"
                         and row["raceTitle"] == "Governor - Alameda County Results", mutate_json)
        def mutate_text(row):
            row[9], row[11], row[13], row[15] = "450000", "90.0", "50000", "10.0"
        self.change_text("V26GG.txt", lambda row: row[0] == "V"
                         and row[3:5] == ["020000000000", "1"], mutate_text)
        with self.assertRaisesRegex(ValueError, "exceeds native reported participation"):
            REVIEW.reconcile(self.inputs)

    def test_native_candidate_names_remain_covered_by_original_byte_receipts(self):
        rows = REVIEW.records(self.inputs["native-text-records.csv"])
        selected = next(row for row in rows if row["source_file"] == "C26GG.txt"
                        and json.loads(row["native_fields_json"])[0] == "C")
        fields = json.loads(selected["native_fields_json"])
        fields[10] += " changed"
        selected["native_fields_json"] = REVIEW.encoded(fields)
        self.inputs["native-text-records.csv"] = REVIEW.table(rows)
        with self.assertRaisesRegex(ValueError, "Entire native text source reconstruction"):
            REVIEW.reconcile(self.inputs)


if __name__ == "__main__":
    unittest.main()
