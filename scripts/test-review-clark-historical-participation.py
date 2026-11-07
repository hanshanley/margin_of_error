import copy
import gzip
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "clark_participation", Path(__file__).with_name("review-clark-historical-participation.py"))
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def native(code="1000", registration="10", total="6", day="1", early="2", mail="3"):
    return (
        '"Precinct","Tally Type","Registration","Turnout","Total Votes","Candidate"\n'
        f'"{code}","Totals",{registration},{total},0,"*"\n'
        f'"{code}","Election Day",{registration},{day},0,"*"\n'
        f'"{code}","Early Vote",{registration},{early},0,"*"\n'
        f'"{code}","Mail",{registration},{mail},0,"*"\n'
        '"Totals", "Tally Type", "# Voters", "Voters/Turnout"\n'
        f'"Election Day","{day}","0.0%"\n'
        f'"Early Vote","{early}","0.0%"\n'
        f'"Mail","{mail}","0.0%"\n'
    ).encode()


class ClarkParticipationTests(unittest.TestCase):
    def test_native_counts_not_candidate_votes_or_repeated_registration(self):
        result = review.statement(native())
        self.assertEqual(result["native_turnout"], 6)
        self.assertEqual(result["summed_native_registration_once_per_unit"], 10)
        self.assertEqual(result["units"][0]["native_turnout_by_mode"],
                         {"Election Day": 1, "Early Vote": 2, "Mail": 3})
        self.assertIsNone(result["qualified_turnout_rate"])
        self.assertIsNone(result["units"][0]["qualified_turnout_rate"])
        self.assertEqual(result["native_footer"]["Mail"]["native_percentage_unused"], "0.0%")
        for value in (b'"0"', b'"*****"', b'"999"', b'""'):
            self.assertEqual(review.statement(native().replace(b'"*"', value)), result)

    def test_native_zero_and_turnout_exceeding_registration_are_retained_without_rates(self):
        result = review.statement(native(registration="0"))
        self.assertEqual(result["native_turnout"], 6)
        self.assertEqual(result["turnout_exceeds_registration_units"], 1)
        self.assertIsNone(result["qualified_turnout_rate"])
        self.assertEqual(review.statement(native(total="0", day="0", early="0", mail="0"))[
            "native_turnout"], 0)

    def test_invalid_missing_and_non_ascii_registration_or_turnout_fail(self):
        for value in ("", "-1", "1.5", "01", '" 6"', "NaN", "True", "\u0666"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review.statement(native(total=value))
            with self.subTest(registration=value), self.assertRaises(ValueError):
                review.statement(native(registration=value))

    def test_duplicate_misordered_and_missing_modes_or_units_fail(self):
        text = native()
        rows = text.splitlines(keepends=True)
        bad = [
            b"".join(rows[:5] + rows[1:5] + rows[5:]),
            b"".join(rows[:2] + rows[3:]),
            b"".join(rows[:2] + [rows[3], rows[2]] + rows[4:]),
            text.replace(b'"1000","Mail"', b'"1001","Mail"'),
            native(code="100"),
            text.replace(b'"1000","Mail",10', b'"1000","Mail",11'),
        ]
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                review.statement(raw)

    def test_changed_header_footer_or_control_counts_fail(self):
        text = native()
        for before, after in (
            (b'"Turnout"', b'"Votes"'),
            (b'"Total Votes"', b'"Other"'),
            (b'"Totals", "Tally Type"', b'"Wrong", "Tally Type"'),
            (b'"Mail","3","0.0%"', b'"Mail","4","0.0%"'),
            (b'"Mail","3","0.0%"', b'"Mail","3","missing"'),
            (b'"1000","Totals",10,6', b'"1000","Totals",10,7'),
            (b'"1000","Mail",10,3,0,"*"', b'"1000","Mail",10,3,0'),
        ):
            with self.subTest(before=before), self.assertRaises(ValueError):
                review.statement(text.replace(before, after))
        with self.assertRaises(ValueError):
            review.statement(text + b'"Totals", "Tally Type", "# Voters", "Voters/Turnout"\n')

    def test_contest_specific_absence_and_shared_differences_are_not_pooled_or_allocated(self):
        president = review.statement(native())
        extra = copy.deepcopy(president["units"][0])
        extra["native_precinct_id"] = "9996"
        president["units"].append(extra)
        president["native_turnout"] += 6
        senate = review.statement(native())
        result = review.contest_scope(president, senate)
        self.assertEqual(result["president_only_units"], [extra])
        self.assertEqual(result["president_minus_senate_native_turnout"], 6)
        self.assertEqual(result["shared_native_reporting_units"], 1)
        self.assertFalse(result["same_electorate_qualified"])
        senate["units"][0]["native_turnout_by_mode"]["Mail"] += 1
        self.assertEqual(review.contest_scope(president, senate)[
            "shared_units_with_different_participation_fields"], ["1000"])

    def test_receipt_rejects_changed_native_bytes_scope_and_failed_http(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "originals").mkdir()
            path = root / "originals" / "native.txt.gz"
            raw = native()
            path.write_bytes(gzip.compress(raw))
            receipt = {"url": "https://example.test/native.txt",
                       "resolved_url": "https://example.test/native.txt",
                       "status": 200, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            self.assertEqual(review.frozen(root, "native.txt", receipt, receipt["url"]), raw)
            for key, value in (("url", "other"), ("resolved_url", "other"), ("status", 403),
                               ("method", "POST"), ("bytes", 1), ("sha256", "wrong")):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    review.frozen(root, "native.txt", dict(receipt, **{key: value}), receipt["url"])
            path.write_bytes(gzip.compress(raw + b"changed"))
            with self.assertRaises(ValueError):
                review.frozen(root, "native.txt", receipt, receipt["url"])
            (root / "sources.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "complete reviewed Clark source manifest"):
                review.review(root)


if __name__ == "__main__":
    unittest.main()
