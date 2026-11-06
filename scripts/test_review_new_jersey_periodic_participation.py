import copy
import csv
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data/county-source-reviews/20261106-nj-participation-facts-01"
SPEC = importlib.util.spec_from_file_location(
    "nj", ROOT / "scripts/review-new-jersey-periodic-participation.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


class NewJerseyParticipationTests(unittest.TestCase):
    def setUp(self):
        self.facts = json.loads(gzip.decompress((PACKAGE / "source-records.json.gz").read_bytes()))

    def table(self, name):
        with (PACKAGE / name).open() as source:
            return list(csv.DictReader(source))

    def report(self, county):
        return next(row for row in self.facts["reports"] if row["county"] == county)

    def test_complete_county_query_preserves_two_withheld_records(self):
        REVIEW.validate(self.facts)
        rows = self.table("county-participation.csv")
        self.assertEqual(tuple(row["county"] for row in rows), REVIEW.COUNTIES)
        self.assertEqual(sum(bool(row["reported_participation_subtotal"]) for row in rows), 19)
        withheld = [row for row in rows if row["withheld_reason"]]
        self.assertEqual([row["county"] for row in withheld], ["Essex", "Hudson"])
        self.assertTrue(all(row["reported_participation_subtotal"] == "" for row in withheld))
        self.assertTrue(all(row["early_voting_votes_cast"] == "" for row in withheld))
        self.assertEqual(len(self.table("native-aggregate-participation.csv")), 65)
        self.assertEqual(len(self.facts["source_receipts"]), 23)

    def test_subtotals_never_add_issued_received_pending_or_provisional_counts(self):
        atlantic = next(row for row in self.table("county-participation.csv") if row["county"] == "Atlantic")
        self.assertEqual(atlantic["reported_participation_subtotal"], "94292")
        self.assertEqual(atlantic["mail_ballots_tallied"], "15305")
        self.assertEqual(atlantic["registered_voters"], "")
        self.assertEqual(atlantic["provisional_ballots_counted"], "")
        self.assertEqual(atlantic["native_participation_measure_literal"], "")
        self.assertIn("Derived", atlantic["participation_measure_label"])
        for row in self.table("county-participation.csv"):
            if not row["withheld_reason"]:
                self.assertEqual(int(row["reported_participation_subtotal"]),
                    sum(int(row[field]) for field in
                        ("early_voting_votes_cast", "election_day_votes_cast", "mail_ballots_tallied")))

    def test_cape_may_uses_actual_attached_ballot_summary_and_registration(self):
        row = next(row for row in self.table("county-participation.csv") if row["county"] == "Cape May")
        self.assertEqual(row["reported_participation_subtotal"], "41278")
        self.assertEqual(row["registered_voters"], "76899")
        self.assertEqual(row["native_printed_turnout"], "53.68%")
        self.assertEqual(row["native_participation_measure_literal"], "Ballots Cast - Total")
        self.assertEqual(row["provisional_ballots_counted"], "0")
        native = json.loads(row["native_county_count_literals_json"])
        self.assertEqual(native[-1], "347")
        self.assertNotEqual(int(native[-1]), int(row["provisional_ballots_counted"]))
        congressional = next(row for row in self.report("Cape May")["aggregates"]
                             if row["label_literal"] == "Congressional TOTALS")
        self.assertEqual(congressional["count_literals"][3:], [
            "133", "0", "24033", "10498", "7963", "7567", "396", "347"])

    def test_conflicting_subtotals_and_missing_observations_stay_distinct(self):
        essex = self.report("Essex")
        self.assertIsNone(REVIEW.select(essex))
        alternatives = [row for row in essex["aggregates"] if row["label_literal"].endswith("TOTALS")]
        self.assertEqual([REVIEW.mode_counts(row)[1] for row in alternatives], [133271, 137294])
        hudson = self.report("Hudson")
        self.assertIsNone(REVIEW.select(hudson))
        self.assertEqual(hudson["aggregates"][0]["count_literals"][2], "")
        self.assertEqual(hudson["aggregates"][1]["count_literals"][2], "0")
        self.assertIsNone(REVIEW.number(""))
        self.assertEqual(REVIEW.number("0"), 0)
        self.assertEqual(REVIEW.number("-637"), -637)

    def test_union_overseas_scope_and_hunterdon_agreement_are_checked(self):
        union = self.report("Union")
        self.assertEqual(REVIEW.mode_counts(REVIEW.select(union)), (42998, 103766, 29592))
        without_note = copy.deepcopy(union)
        without_note["notes"] = []
        with self.assertRaisesRegex(ValueError, "overseas scope"):
            REVIEW.select(without_note)
        changed = copy.deepcopy(self.report("Hunterdon"))
        row = next(row for row in changed["aggregates"] if row["label_literal"] == "Municipality TOTALS")
        row["count_literals"][8] = "13531"
        with self.assertRaisesRegex(ValueError, "aggregates disagree"):
            REVIEW.select(changed)

    def test_current_pages_exclude_old_snapshots_and_preserve_scanned_source(self):
        morris = self.report("Morris")
        self.assertEqual(morris["selected_periodic_pages"], [1, 2])
        self.assertEqual([row["source_page"] for row in morris["excluded_appended_pages"]], [3, 4, 5, 6])
        self.assertEqual(REVIEW.mode_counts(REVIEW.select(morris)), (43773, 122015, 33352))
        self.assertIn("PRIMARY", morris["excluded_appended_pages"][0]["header_literal"])
        bergen = self.report("Bergen")
        self.assertIn("visually reviewed", bergen["extraction"])
        self.assertEqual(len(bergen["aggregates"]), 5)
        self.assertEqual(REVIEW.mode_counts(REVIEW.select(bergen)), (60373, 200273, 58857))
        self.assertEqual(bergen["aggregates"][-1]["count_literals"][0], "20")
        self.assertEqual(bergen["aggregates"][0]["count_literals"][0], "23")

    def test_rejects_lost_counts_changed_provenance_and_out_of_scope_pages(self):
        for mutate in (
            lambda facts: facts["reports"].pop(),
            lambda facts: facts["reports"][0]["aggregates"].pop(),
            lambda facts: facts["reports"][0]["aggregates"][0]["count_literals"].pop(),
            lambda facts: facts["reports"][0]["aggregates"][0].update(source_page=3),
            lambda facts: facts["reports"][0].update(declared_timezone="Eastern"),
            lambda facts: facts["source_receipts"]["atlantic-periodic-report.pdf"].update(status=404),
            lambda facts: facts["source_receipts"]["atlantic-periodic-report.pdf"].update(sha256="0" * 64),
        ):
            changed = copy.deepcopy(self.facts)
            mutate(changed)
            with self.assertRaises(ValueError):
                REVIEW.validate(changed)

    def test_every_output_and_zip_member_reproduces_without_dependencies(self):
        with tempfile.TemporaryDirectory(prefix="nj-county-query-") as directory:
            output = Path(directory) / "reproduced"
            subprocess.run([sys.executable, "-S", str(PACKAGE / "review-new-jersey-periodic-participation.py"),
                            "--facts", str(PACKAGE / "source-records.json.gz"), "--output", str(output)],
                           check=True, stdout=subprocess.DEVNULL)
            self.assertEqual({p.name for p in output.iterdir()}, {p.name for p in PACKAGE.iterdir()})
            for path in PACKAGE.iterdir():
                self.assertEqual((output / path.name).read_bytes(), path.read_bytes(), path.name)
            with zipfile.ZipFile(output / "complete-new-jersey-2026-participation-query-01.zip") as archive:
                self.assertIsNone(archive.testzip())
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (output / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
