import importlib.util
import contextlib
import csv
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


spec = importlib.util.spec_from_file_location("cohort", Path(__file__).with_name("review-nc-demographic-cohort.py"))
cohort = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cohort)


def row(**overrides):
    values = dict(county_desc="DURHAM", ncid="test-1", election_dt="11/03/2026",
                  ballot_req_type="ONE-STOP", ballot_rtn_status="ACCEPTED",
                  race="UNKNOWN", ethnicity="UNKNOWN", gender="UNDESIGNATED", age="29",
                  voter_party_code="UNA")
    values.update(overrides)
    return values


class CohortTest(unittest.TestCase):
    def test_complete_native_archive_review_exports_only_aggregates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipts = []
            history = dict(ncid="test-1", election_lbl="11/05/2024",
                           election_desc="11/05/2024 GENERAL", voted_county_desc="DURHAM")
            for name, record, delimiter, encoding in [
                ("absentee.zip", dict(row(), voter_first_name="PRIVATE_MARKER"), ",", "latin-1"),
                ("history-durham.zip", history, "\t", "utf-16"),
            ]:
                content = io.StringIO()
                writer = csv.DictWriter(content, fieldnames=list(record), delimiter=delimiter)
                writer.writeheader()
                writer.writerow(record)
                with zipfile.ZipFile(root / name, "w") as archive:
                    archive.writestr("native.txt", content.getvalue().encode(encoding))
                data = (root / name).read_bytes()
                receipts.append(dict(file=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
            (root / "receipts.json").write_text(json.dumps(receipts))
            with contextlib.redirect_stdout(io.StringIO()):
                cohort.review(root, root / "review")
            public = "".join(path.read_text() for path in (root / "review").iterdir())
            self.assertNotIn("PRIVATE_MARKER", public)
            self.assertNotIn("test-1", public)
            self.assertFalse(json.loads((root / "review/audit.json").read_text())["persuasion_estimates_released"])
            with self.assertRaises(ValueError):
                cohort.review(root, root / "review")
            (root / "absentee.zip").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                cohort.review(root, root / "another-review")

    def test_age_bins_and_unknowns(self):
        self.assertEqual([cohort.age_group(value) for value in ["17", "18", "29", "30", "45", "65", "121", ""]],
                         ["Unknown", "18-29", "18-29", "30-44", "45-64", "65+", "Unknown", "Unknown"])

    def test_missing_history_is_unresolved_not_nonvoting(self):
        records, audit = cohort.aggregate_cohort([row(), row(ncid="test-2")], {"test-1"})
        overall = next(record for record in records if record["dimension"] == "overall")
        self.assertEqual(overall["positive_2024_history_matches"], 1)
        self.assertEqual(overall["history_unresolved"], 1)
        self.assertIsNone(overall["swing_margin_pp"])
        self.assertTrue(audit["membership_unique"])

    def test_requested_rejected_and_nonpilot_history_never_become_positive_cohort_matches(self):
        records, audit = cohort.aggregate_cohort([
            row(ballot_rtn_status="REQUESTED"), row(ballot_rtn_status="REJECTED"),
            row(county_desc="WAKE"),
        ], {"test-1"})
        self.assertEqual(audit["accepted_records"], 1)
        self.assertTrue(all(record["positive_2024_history_matches"] is None for record in records))

    def test_duplicate_and_missing_identifiers_withhold_unique_membership(self):
        _, audit = cohort.aggregate_cohort([row(), row(), row(ncid="")], set())
        self.assertFalse(audit["membership_unique"])
        self.assertEqual(audit["duplicate_accepted_identifier_records"], 1)
        self.assertEqual(audit["accepted_records_missing_identifier"], 1)

    def test_wrong_election_and_missing_fields_fail(self):
        with self.assertRaises(ValueError):
            cohort.aggregate_cohort([row(election_dt="11/05/2024")], set())
        with self.assertRaises(ValueError):
            cohort.aggregate_cohort([{}], set())

    def test_history_uses_general_turnout_not_primary_party_as_vote_choice(self):
        base = dict(ncid="test-1", election_lbl="03/05/2024", election_desc="PRIMARY", voted_county_desc="DURHAM")
        general = dict(base, election_lbl="11/05/2024", election_desc="GENERAL")
        participants, audit = cohort.historical_participants([base, general, general])
        self.assertEqual(participants, {"test-1"})
        self.assertEqual(audit["duplicate_2024_history_records"], 1)


if __name__ == "__main__":
    unittest.main()
