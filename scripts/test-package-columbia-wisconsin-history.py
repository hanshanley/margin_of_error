"""Focused preservation and malformed-input tests for the Columbia factual package."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "columbia_history", Path(__file__).with_name("package-columbia-wisconsin-history.py"))
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class ColumbiaHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = PACKAGE.ROOT / PACKAGE.DATA
        cls.snapshot = json.loads((root / "selected-observations.json").read_bytes())
        cls.methods = json.loads((root / "methodology-review.json").read_bytes())

    def test_complete_native_rows_and_unclassified_gaps(self):
        result, ballots, answers = PACKAGE.review(self.snapshot, self.methods)
        self.assertEqual((len(ballots), len(answers)), (76, 2647))
        self.assertEqual(result["reported_ballot_count_change_2026_minus_2024"], -7725)
        self.assertEqual([x["unclassified_ballot_minus_contest_votes"] for x in result["contest_context"]],
                         [127, 1744, 325])
        self.assertTrue(all(x is None for x in result["unsupported_estimates"].values()))
        self.assertTrue(any("Shanahan" in x["native_answer"] for x in answers))

    def test_missing_duplicate_and_malformed_native_values(self):
        mutations = (
            lambda x: x["elections"].pop(),
            lambda x: x["elections"][0]["observations"][0]["units"].pop(),
            lambda x: x["elections"][0]["observations"][0]["units"].__setitem__(
                1, copy.deepcopy(x["elections"][0]["observations"][0]["units"][0])),
            lambda x: x["elections"][0]["observations"][0]["units"][0].update(ballots=True),
            lambda x: x["elections"][0]["observations"][0]["units"][0].update(ballots=-1),
            lambda x: x["elections"][0]["observations"][0]["units"][0]["contests"][
                PACKAGE.PRESIDENT]["answers"][0].update(votes=234),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                wrong = copy.deepcopy(self.snapshot)
                mutate(wrong)
                with self.assertRaises(ValueError):
                    PACKAGE.review(wrong, self.methods)

    def test_scope_clock_status_and_receipt_changes_refused(self):
        mutations = (
            lambda x: x["elections"][0]["scope"].update(county_fips="55025"),
            lambda x: x["elections"][0]["observations"][0].update(source_report_clock_literal="synchronized"),
            lambda x: x["elections"][1]["observations"][0].update(status="CERTIFIED"),
            lambda x: x["elections"][0]["source_receipts"].pop(),
            lambda x: x["elections"][0]["source_receipts"][0]["headers"].update({"Set-Cookie": "private"}),
            lambda x: x["elections"][0]["observations"][0]["units"][0].update(person_id="private"),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                wrong = copy.deepcopy(self.snapshot)
                mutate(wrong)
                with self.assertRaises(ValueError):
                    PACKAGE.review(wrong, self.methods)

    def test_partial_county_and_lost_literal_candidates_refused(self):
        for remove in (True, False):
            wrong = copy.deepcopy(self.snapshot)
            contest = wrong["elections"][0]["observations"][0]["units"][0]["contests"][PACKAGE.HOUSE]
            if remove:
                contest["answers"].pop()
            else:
                contest["native_reporting_units"] = {"reported": 37, "total": 37}
            with self.assertRaises(ValueError):
                PACKAGE.review(wrong, self.methods)

    def test_used_source_links_with_unused_provisional_declaration(self):
        receipts = self.snapshot["elections"][1]["source_receipts"]
        self.assertEqual(len(receipts[0]["declared_report_links"]), 3)
        self.assertEqual(receipts[0]["declared_report_links"][2]["text"],
                         "Outstanding Provisional Ballots Report")
        PACKAGE.review(self.snapshot, self.methods)
        mutations = (
            lambda x: x[0]["declared_report_links"].pop(0),
            lambda x: x[0]["declared_report_links"].__setitem__(
                1, copy.deepcopy(x[0]["declared_report_links"][0])),
            lambda x: x[1]["declared_link"].update(url="https://www.co.columbia.wi.us/columbiacounty/changed"),
            lambda x: x[1].update(declared_link=copy.deepcopy(x[0]["declared_report_links"][1])),
            lambda x: x[0]["declared_report_links"][0].update(session="private"),
        )
        for mutate in mutations:
            wrong = copy.deepcopy(self.snapshot)
            mutate(wrong["elections"][1]["source_receipts"])
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                PACKAGE.review(wrong, self.methods)

    def test_unsupported_claims_refused(self):
        for key in PACKAGE.UNSUPPORTED:
            wrong = copy.deepcopy(self.methods)
            wrong[key] = True
            with self.subTest(claim=key), self.assertRaises(ValueError):
                PACKAGE.review(self.snapshot, wrong)

    def test_changed_source_and_frozen_outputs_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / PACKAGE.DATA
            data.mkdir(parents=True)
            for name in PACKAGE.PINS:
                (data / name).write_bytes((PACKAGE.ROOT / PACKAGE.DATA / name).read_bytes())
            changed = data / "selected-observations.json"
            changed.write_bytes(changed.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "Reviewed source changed"):
                PACKAGE.package(root, root / "output")
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            (out / "history.json").write_bytes(b"older complete version\n")
            with self.assertRaisesRegex(ValueError, "Frozen output changed"):
                PACKAGE.package(PACKAGE.ROOT, out)
            self.assertEqual((out / "history.json").read_bytes(), b"older complete version\n")


if __name__ == "__main__":
    unittest.main()
