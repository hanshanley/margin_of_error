import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/county-source-reviews/20261105-dauphin-reviewed-01/originals"
spec = importlib.util.spec_from_file_location(
    "dauphin", Path(__file__).with_name("review-dauphin-county-results.py"))
reviewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reviewer)


class DauphinCountyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw, cls.receipts = reviewer.load_originals(SOURCE)
        cls.tables, cls.audit = reviewer.review(cls.raw, cls.receipts)

    def test_complete_native_counts_and_literal_parties(self):
        self.assertEqual(self.audit["table_rows"], {
            "county-candidate-results.csv": 23, "county-contest-totals.csv": 8,
            "county-contest-party-totals.csv": 23, "county-participation.csv": 1,
            "native-precinct-candidate-counts.csv": 1597,
            "native-municipality-candidate-counts.csv": 460,
            "native-contest-reporting.csv": 8})
        house = {r["party_literal"]: r["votes"] for r in self.tables["county-candidate-results.csv"]
                 if r["office"] == "us_house"}
        self.assertEqual(house, {"DEM": 68655, "REP": 45507, "NONPARTISAN": 479})
        self.assertEqual(self.audit["geographic_explicit_zeroes"], {"precinct": 128, "municipality": 39})
        participation = self.tables["county-participation.csv"][0]
        self.assertEqual(participation["house_candidate_votes"], 114641)
        self.assertIsNone(participation["ballots_cast"])
        self.assertIsNone(participation["turnout_percent"])

    def test_absent_party_and_commented_mail_are_not_zeroes(self):
        for district in ["104", "105"]:
            self.assertNotIn("REP", {r["party_literal"] for r in self.tables["county-candidate-results.csv"]
                                    if r["office"] == "state_house" and r["district_literal"] == district})
        self.assertTrue(all(r["mail_ballots"] is None and r["provisional_ballots"] is None
                            for r in self.tables["native-contest-reporting.csv"]))

    def changed_detail(self, edit, filename="native-detail-01.html"):
        raw = dict(self.raw)
        soup = BeautifulSoup(raw[filename], "html.parser")
        edit(soup)
        raw[filename] = str(soup).encode()
        return raw

    def test_precinct_and_municipality_must_reconcile_independently(self):
        for selector in ["table.my_tab", "table.tab2"]:
            with self.subTest(selector=selector):
                def edit(soup):
                    grid = soup.select_one(selector).find("table")
                    grid.find_all("tr", recursive=False)[1].find_all("td", recursive=False)[1].string = "999999"
                with self.assertRaisesRegex(ValueError, "geographic candidate sums"):
                    reviewer.review(self.changed_detail(edit), self.receipts)

    def test_duplicate_native_precinct_is_rejected(self):
        def edit(soup):
            rows = soup.select_one("table.my_tab").find("table").find_all("tr", recursive=False)
            rows[2].find("td").string = reviewer.text(rows[1].find("td"))
        with self.assertRaisesRegex(ValueError, "duplicate native geography"):
            reviewer.review(self.changed_detail(edit), self.receipts)

    def test_changed_candidate_header_is_rejected(self):
        def edit(soup):
            soup.select_one("table.my_tab").find("table").find("tr").find_all("td")[1].string = "OTHER"
        with self.assertRaisesRegex(ValueError, "candidate columns disagree"):
            reviewer.review(self.changed_detail(edit), self.receipts)

    def test_different_snapshot_minute_is_rejected(self):
        raw = dict(self.raw)
        raw["native-detail-01.html"] = raw["native-detail-01.html"].replace(
            b"11/03/2026 10:41 PM", b"11/03/2026 10:40 PM")
        with self.assertRaisesRegex(ValueError, "detail timestamp"):
            reviewer.review(raw, self.receipts)

    def test_wrong_election_is_rejected(self):
        raw = dict(self.raw)
        raw["native-report-01.html"] = raw["native-report-01.html"].replace(
            b'type="hidden" value="42"', b'type="hidden" value="41"')
        with self.assertRaisesRegex(ValueError, "Wrong election"):
            reviewer.review(raw, self.receipts)

    def test_matching_hash_does_not_permit_unscreened_credential(self):
        import hashlib
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "originals"
            shutil.copytree(SOURCE, target)
            path = target / "native-report-01.html"
            path.write_bytes(path.read_bytes() + b"\n<!-- " + b"AI" + b"za" + b"x" * 35 + b" -->")
            receipts = copy.deepcopy(self.receipts)
            receipt = next(r for r in receipts if r["file"] == path.name)
            receipt["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            receipt["bytes"] = path.stat().st_size
            receipt["screening"] = dict(original_sha256=receipt["sha256"],
                                       original_bytes=receipt["bytes"], replacements=0)
            (target / "receipts.json").write_text(json.dumps(receipts))
            with self.assertRaisesRegex(ValueError, "Unredacted public service key"):
                reviewer.load_originals(target)


if __name__ == "__main__":
    unittest.main()
