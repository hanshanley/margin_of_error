import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "berks", ROOT / "scripts/review-berks-county-results.py")
BERKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BERKS)
ORIGINALS = ROOT / "data/county-source-reviews/20261105-berks-reviewed-01/originals"


class BerksReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_raw, cls.original_receipts = BERKS.load_originals(ORIGINALS)

    def setUp(self):
        self.raw = dict(self.original_raw)
        self.receipts = copy.deepcopy(self.original_receipts)

    def mutate(self, name, update):
        data = json.loads(self.raw[name])
        update(data)
        self.raw[name] = json.dumps(data).encode()

    def change_candidate(self, prefix, predicate, delta):
        for name in sorted(n for n in self.raw if n.startswith(prefix)):
            data = json.loads(self.raw[name])
            for feature in data["features"]:
                row = feature["attributes"]
                if predicate(row):
                    row["numvotes"] += delta
                    self.raw[name] = json.dumps(data).encode()
                    return
        self.fail("Synthetic candidate target not found")

    def test_complete_native_counts_parties_nulls_and_overlaps(self):
        tables, audit = BERKS.review(self.raw, self.receipts)
        self.assertEqual(len(tables["county-candidate-results.csv"]), 45)
        self.assertEqual(len(tables["native-precinct-candidate-counts.csv"]), 2216)
        self.assertEqual(audit["candidate_explicit_zeroes"], 332)
        participation = tables["county-participation.csv"][0]
        self.assertEqual((participation["ballots_cast"], participation["registered_voters"]),
                         (143855, 275941))
        self.assertIsNone(participation["eligible_population_turnout"])
        methods = {r["native_field"]: r for r in tables["county-voting-method-counts.csv"]}
        self.assertIsNone(methods["earlyvote"]["count"])
        self.assertEqual(methods["earlyvote"]["null_units"], 202)
        self.assertEqual(methods["earlyvote"]["explicit_zero_units"], 0)
        self.assertEqual(methods["provisional"]["absent_units"], 202)
        self.assertEqual(methods["mail"]["count"], 27931)
        self.assertEqual(methods["electionday"]["count"], 115924)
        self.assertEqual(set(audit["congressional_scope_overlaps"]), {"4310", "7001"})
        self.assertEqual({r["party_literal"] for r in tables["county-candidate-results.csv"]},
                         {"Democratic", "Republican", "Libertarian", "Green", "Write-in"})
        self.assertNotEqual(audit["participation_record_edit_ms"],
                            audit["candidate_record_edit_ms"])
        self.assertFalse(audit["maps_approved"])

    def test_missing_full_query_batch_rejected(self):
        self.raw.pop("results-table-post-records-003.json")
        with self.assertRaisesRegex(ValueError, "Missing or duplicated full native records"):
            BERKS.review(self.raw, self.receipts)

    def test_consistent_local_candidate_change_still_needs_native_aggregate(self):
        target = lambda r: (r["contest"] == "Governor and Lieutenant Governor"
                            and r["candidate"] == "Josh Shapiro")
        for prefix in ("raw-native-post-records-", "results-table-post-records-"):
            self.change_candidate(prefix, target, 1)
        with self.assertRaisesRegex(ValueError, "native server aggregates"):
            BERKS.review(self.raw, self.receipts)

    def test_null_early_voting_cannot_be_coerced_to_zero(self):
        self.mutate("turnout-post-records-001.json",
                    lambda d: d["features"][0]["attributes"].update(earlyvote=0))
        with self.assertRaisesRegex(ValueError, "Participation or observed-method"):
            BERKS.review(self.raw, self.receipts)

    def test_observed_methods_must_match_native_ballots(self):
        self.mutate("turnout-post-records-001.json",
                    lambda d: d["features"][0]["attributes"].update(mail=99999))
        with self.assertRaisesRegex(ValueError, "Participation or observed-method"):
            BERKS.review(self.raw, self.receipts)

    def test_changed_source_during_capture_rejected(self):
        self.mutate("raw-native-layer-after.json",
                    lambda d: d["editingInfo"].update(lastEditDate=0))
        with self.assertRaisesRegex(ValueError, "Source changed during capture"):
            BERKS.review(self.raw, self.receipts)

    def test_wrong_election_rejected(self):
        self.mutate("dashboard-item.json", lambda d: d.update(
            title="County Of Berks: 2024 General Election Results Master Dashboard"))
        with self.assertRaisesRegex(ValueError, "election identity"):
            BERKS.review(self.raw, self.receipts)

    def test_split_congress_scope_cannot_double_count_ballots(self):
        contest = "Representative in Congress 4th District"
        target = lambda r: (r["contest"] == contest and r["jurisdictionname"] == "4310"
                            and r["party"] == "Write-in")
        for prefix in ("raw-native-post-records-", "results-table-post-records-"):
            self.change_candidate(prefix, target, 15)

        def update(data):
            for feature in data["features"]:
                row = feature["attributes"]
                if row["contest"] == contest and row["party"] == "Write-in":
                    row["native_votes"] += 15
        self.mutate("native-candidate-aggregates.json", update)
        with self.assertRaisesRegex(ValueError, "Congress overlap"):
            BERKS.review(self.raw, self.receipts)

    def test_winner_view_is_not_a_substitute_for_full_results(self):
        self.mutate("joined-results-post-records-001.json",
                    lambda d: d["features"][0]["attributes"].update(numvotes=0))
        with self.assertRaisesRegex(ValueError, "Winner-only view"):
            BERKS.review(self.raw, self.receipts)

    def test_winner_candidate_identity_must_match_its_own_votes(self):
        name = "joined-results-post-records-001.json"
        winner = json.loads(self.raw[name])["features"][0]["attributes"]
        other = next(
            feature["attributes"]
            for path in sorted(n for n in self.raw if n.startswith("raw-native-post-records-"))
            for feature in json.loads(self.raw[path])["features"]
            if feature["attributes"]["contest"] == winner["contest"]
            and feature["attributes"]["jurisdictionname"] == winner["jurisdictionname"]
            and feature["attributes"]["numvotes"] != winner["numvotes"])
        self.mutate(name, lambda d: d["features"][0]["attributes"].update(
            candidate=other["candidate"], party=other["party"]))
        with self.assertRaisesRegex(ValueError, "Winner-only view"):
            BERKS.review(self.raw, self.receipts)

    def test_credentials_rejected_even_with_updated_receipt_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "originals"
            shutil.copytree(ORIGINALS, folder)
            name = "official-results-index.html"
            body = (folder / name).read_bytes() + b"AI" + b"za" + b"x" * 35
            (folder / name).write_bytes(body)
            receipts = json.loads((folder / "receipts.json").read_bytes())
            for receipt in receipts:
                if receipt["file"] == name:
                    digest = hashlib.sha256(body).hexdigest()
                    receipt.update(bytes=len(body), sha256=digest, screening={
                        "original_bytes": len(body), "original_sha256": digest, "replacements": 0})
            (folder / "receipts.json").write_text(json.dumps(receipts))
            with self.assertRaisesRegex(ValueError, "Unredacted public service key"):
                BERKS.load_originals(folder)


if __name__ == "__main__":
    unittest.main()
