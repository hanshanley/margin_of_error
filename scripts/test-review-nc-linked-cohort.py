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

spec = importlib.util.spec_from_file_location("linked", Path(__file__).with_name("review-nc-linked-cohort.py"))
linked = importlib.util.module_from_spec(spec)
spec.loader.exec_module(linked)


class LinkedCohortTest(unittest.TestCase):
    def test_explicit_county_review_binds_private_cells_to_its_own_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registration = dict(county_desc="WAKE", ncid="PRIVATE1", birth_year="1980",
                                race_code="W", ethnic_code="NL", party_cd="UNA", gender_code="F",
                                registr_dt="01/01/2000", voter_status_desc="ACTIVE")
            accepted = dict(county_desc="WAKE", ncid="PRIVATE1", election_dt="11/03/2026",
                            ballot_rtn_status="ACCEPTED", ballot_req_type="MAIL", race="WHITE",
                            ethnicity="NOT HISPANIC or NOT LATINO", gender="FEMALE", age="46",
                            voter_party_code="UNA", voter_first_name="PRIVATE_MARKER")
            history = dict(ncid="PRIVATE1", election_lbl="11/05/2024", election_desc="GENERAL",
                           voted_county_desc="WAKE", voting_method="IN-PERSON", voted_party_cd="")
            receipts = []
            for name, record, delimiter in [
                ("registration-wake.zip", registration, "\t"),
                ("history-statewide.zip", history, "\t"), ("absentee.zip", accepted, ","),
            ]:
                content = io.StringIO()
                writer = csv.DictWriter(content, fieldnames=list(record), delimiter=delimiter)
                writer.writeheader()
                writer.writerow(record)
                path = root / name
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr("native.txt", content.getvalue().encode("utf-16"))
                receipt = dict(file=name, bytes=path.stat().st_size,
                               sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                receipts.append(receipt)
                Path(f"{path}.receipt.json").write_text(json.dumps(receipt))
            (root / "receipts.json").write_text(json.dumps(receipts))
            output = root / "review"
            with contextlib.redirect_stdout(io.StringIO()):
                linked.review(root, root, output, county="WAKE",
                              registration=root / "registration-wake.zip")
            audit = json.loads((output / "audit.json").read_text())
            cells = json.loads((output / "joint-cells.json").read_text())
            self.assertEqual(audit["county"], "WAKE")
            self.assertEqual(audit["joint_cells_sha256"],
                             hashlib.sha256((output / "joint-cells.json").read_bytes()).hexdigest())
            self.assertEqual(audit["history"]["baseline_county_2024_unique_identifiers"], 1)
            self.assertEqual(sum(cell["records"] for cell in cells), 1)
            self.assertTrue(cells[0]["baseline_2024_voted_county"])
            self.assertEqual(cells[0]["prior_2024_voted_counties"], "WAKE")
            self.assertNotIn("PRIVATE", "".join(path.read_text() for path in output.iterdir()))
            with self.assertRaisesRegex(ValueError, "target county"):
                linked.review(root, root, root / "wrong-county", county="DURHAM",
                              registration=root / "registration-wake.zip")
            (root / "registration-wake.zip").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Changed native source"):
                linked.review(root, root, root / "changed-source", county="WAKE",
                              registration=root / "registration-wake.zip")

    def test_other_county_requires_explicit_registration_not_durham_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "explicit registration"):
                linked.review(root, root, root / "review", county="WAKE")
            with self.assertRaisesRegex(ValueError, "uppercase source county"):
                linked.review(root, root, root / "review", county="Wake")

    def test_registration_date_is_not_first_vote_and_preserves_unknowns(self):
        self.assertEqual(linked.registration_period("11/05/2024"), "Registered by 2024 election")
        self.assertEqual(linked.registration_period("11/06/2024"), "Registration after 2024 election")
        self.assertEqual(linked.registration_period("11/04/2026"), "Registration after 2026 election")
        self.assertEqual(linked.registration_period("xx/xx/xxxx"), "Unknown registration date")
        self.assertEqual(linked.registration_period("##/##/####"), "Unknown registration date")
        with self.assertRaises(ValueError):
            linked.registration_period("not-a-date")

    def test_repeated_id_is_excluded_not_arbitrarily_selected(self):
        rows = [dict(county_desc="DURHAM", ncid="PRIVATE1", field="a"),
                dict(county_desc="DURHAM", ncid="PRIVATE1", field="b"),
                dict(county_desc="DURHAM", ncid="PRIVATE2", field="c")]
        records, audit = linked.unique_records(rows, ["field"], "DURHAM")
        self.assertEqual(set(records), {"PRIVATE2"})
        self.assertEqual(audit["ambiguous_identifiers_excluded"], 1)

    def test_statewide_history_finds_movers_and_uses_actual_voted_county(self):
        rows = [
            ("PRIVATE1", "11/05/2024", "GENERAL", "WAKE", "ONE-STOP", ""),
            ("PRIVATE2", "11/05/2024", "GENERAL", "DURHAM", "IN-PERSON", ""),
            ("PRIVATE1", "03/05/2024", "PRIMARY", "WAKE", "ONE-STOP", "REP"),
        ]
        history, baseline, audit = linked.linked_history(rows, {"PRIVATE1"}, "DURHAM")
        self.assertIn(2024, history["PRIVATE1"]["general"])
        self.assertEqual(history["PRIVATE1"]["primary_2024"], {"REP"})
        self.assertEqual(baseline, {"PRIVATE2"})
        self.assertEqual(audit["baseline_county_2024_unique_identifiers"], 1)

    def test_baseline_orphan_history_remains_unknown_not_false(self):
        rows = [
            ("PRIVATE1", "11/08/2022", "GENERAL", "DURHAM", "IN-PERSON", ""),
            ("PRIVATE1", "03/05/2024", "PRIMARY", "DURHAM", "IN-PERSON", "REP"),
            ("PRIVATE1", "11/05/2024", "GENERAL", "DURHAM", "IN-PERSON", ""),
        ]
        history, baseline, _ = linked.linked_history(rows, set(), "DURHAM")
        cell = linked.aggregate_linkage({}, {}, history, baseline)[0]
        self.assertIsNone(cell["prior_2022_history"])
        self.assertIsNone(cell["positive_2026_history"])
        self.assertFalse(cell["historical_search_complete"])
        self.assertEqual(cell["primary_2024"], "History coverage incomplete")
        self.assertEqual(cell["prior_2024_history"], "Positive 2024 NC history")

    def test_aggregate_export_never_calls_early_absence_nonvoting_or_emits_ids(self):
        registrations = {"PRIVATE1": dict(birth_year="2006", registr_dt="01/01/2025"),
                         "PRIVATE2": dict(birth_year="1970", registr_dt="01/01/2000")}
        accepted = {"PRIVATE1": dict(ballot_req_type="EARLY VOTING", race="WHITE")}
        history = {"PRIVATE2": {"general": {2024: {("DURHAM", "IN-PERSON")}}}}
        cells = linked.aggregate_linkage(registrations, accepted, history, {"PRIVATE2"})
        self.assertEqual(sum(row["records"] for row in cells), 2)
        self.assertNotIn("PRIVATE", json.dumps(cells))
        new = next(row for row in cells if row["cohort_membership_2026"].startswith("Accepted"))
        self.assertEqual(new["age_2024"], "18-29")
        self.assertIn("national participation unresolved", new["prior_2024_history"])
        old = next(row for row in cells if row["baseline_2024_voted_county"])
        self.assertEqual(old["cohort_membership_2026"], "Not in selected early/mail cohort")
        self.assertFalse(old["positive_2026_history"])

    def test_wrong_election_is_rejected(self):
        with self.assertRaises(ValueError):
            linked.unique_records([dict(county_desc="DURHAM", ncid="x", election_dt="11/05/2024",
                                         ballot_rtn_status="ACCEPTED")], [], "DURHAM", accepted=True)

    def test_registered_noncohort_nonbaseline_pool_is_not_dropped(self):
        registration = {"PRIVATE": dict(birth_year="1980", registr_dt="01/01/2018",
                                        voter_status_desc="ACTIVE")}
        cell = linked.aggregate_linkage(registration, {}, {}, set())[0]
        self.assertEqual(cell["records"], 1)
        self.assertFalse(cell["baseline_2024_voted_county"])
        self.assertEqual(cell["age_2022"], "30-44")
        self.assertFalse(cell["registration_by_2016"])
        self.assertTrue(cell["registration_by_2020"])

    def test_masked_and_known_dates_sort_reproducibly_without_comparing_null_to_boolean(self):
        registration = {
            "PRIVATE1": dict(birth_year="1980", registr_dt="01/01/2000", voter_status_desc="ACTIVE"),
            "PRIVATE2": dict(birth_year="1980", registr_dt="##/##/####", voter_status_desc="ACTIVE"),
        }
        cells = linked.aggregate_linkage(registration, {}, {}, set())
        self.assertEqual(len(cells), 2)
        self.assertEqual(sum(row["records"] for row in cells), 2)
        self.assertEqual(cells, linked.aggregate_linkage(dict(reversed(list(registration.items()))), {}, {}, set()))


if __name__ == "__main__":
    unittest.main()
