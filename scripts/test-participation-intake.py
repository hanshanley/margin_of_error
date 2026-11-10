"""Contract, direct adapter, incremental-cache and complete-package behavior."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
import zipfile

from participation_intake.contract import IntakeError, encoded, pin, validate
from participation_intake.engine import Store, run


SPEC = dict(id="fixture-native", adapter="csv", classification="public_aggregate", primary_input="counts",
    inputs={"counts": {"url": "https://elections.example.gov/participation.csv"}},
    election=dict(id="US-2026-general", year=2026, date="2026-11-03", type="general", qualification="native"),
    geography=dict(state_code="MN", level="precinct"),
    measure=dict(id="total-number-voted", literal="Total Number Voted", kind="voters_reported",
        mode="all_methods", unit="source_reported_people"),
    columns=dict(geography_id="id", geography_name="name", count="voted", reported="reported",
        denominator=["registered_7am", "registered_day"], components=["roster", "absentee"]),
    denominator=dict(literal="7AM plus Election Day registrations", basis="native_7am_plus_election_day"),
    rate_levels=["county"], aggregate_parents=True, source_clock=dict(literal=None, timezone=None),
    reporting_status="Unofficial Results")
BODY = (b"id,name,reported,voted,registered_7am,registered_day,roster,absentee\n"
        b"01,P1,1,0,10,0,0,0\n02,P2,0,0,20,0,0,0\n")
GEOMETRY = encoded(dict(type="FeatureCollection", features=[
    dict(type="Feature", properties=dict(key=key), geometry=dict(type="Polygon", coordinates=[]))
    for key in ("P1", "P2", "C1")]))
REFERENCES = dict(
    assets={"approved": dict(url="https://data.example.gov/approved.geojson", **pin(GEOMETRY),
        key_path="properties.key", approval_evidence="existing-native-reference-review")},
    identities={key: dict(id="MN|" + key, name=name, parent_id="MN|county1",
        reference_id="approved", feature_key=name, evidence="explicit-native-IDs")
        for key, name in (("01", "P1"), ("02", "P2"))},
    parents={"MN|county1": dict(name="County1", state_code="MN", level="county", parent_id=None,
        reference_id="approved", feature_key="C1", evidence="explicit-parent-reference")})


class ParticipationIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.input = self.root / "source.csv"
        self.input.write_bytes(BODY)
        self.store = Store(self.root / "store")

    def tearDown(self):
        self.store.db.close()
        self.temporary.cleanup()

    def intake(self, spec=None, references=None):
        return run(spec or SPEC, self.store, supplied={"counts": self.input},
            references=references or REFERENCES, geometry_inputs={"approved": GEOMETRY})

    def test_native_zero_and_unknown_stay_distinct_and_parent_remains_partial(self):
        result = self.intake()
        self.assertEqual(result["status"], "awaiting_publication")
        rows = json.loads((Path(result["directory"]) / "queries.json").read_bytes())
        self.assertEqual(rows[0]["count"]["value"], 0)
        self.assertEqual(rows[0]["count"]["status"], "reported")
        self.assertIsNone(rows[1]["count"]["value"])
        self.assertIsNone(rows[2]["count"]["value"])
        self.assertFalse(rows[2]["reporting_status"]["complete"])
        self.assertIsNone(rows[0]["source_clock"]["literal"])
        self.assertIsNone(rows[0]["source_clock"]["timezone"])

    def test_unchanged_inputs_skip_parsing_and_changed_data_reuses_geometry(self):
        first = self.intake()
        second = self.intake()
        self.assertFalse(first["no_op"])
        self.assertTrue(second["no_op"])
        self.assertEqual(second["parsed_inputs"], 0)
        self.input.write_bytes(BODY.replace(b"02,P2,0,0", b"02,P2,1,0"))
        changed = self.intake()
        self.assertFalse(changed["no_op"])
        self.assertEqual(changed["geometry_parses"], 0)
        self.assertNotEqual(first["recipe"], changed["recipe"])

    def test_conflicts_are_retained_without_count_repair_or_rate(self):
        self.input.write_bytes(BODY.replace(b"01,P1,1,0", b"01,P1,1,2").replace(b"02,P2,0", b"02,P2,1"))
        result = self.intake()
        rows = json.loads((Path(result["directory"]) / "queries.json").read_bytes())
        self.assertEqual(rows[0]["count"]["value"], 2)
        self.assertEqual(rows[0]["quality"]["conflicts"][0]["residual"], 2)
        self.assertFalse(rows[2]["denominator"]["qualified"])
        self.assertFalse(result["source_counts_repaired"])

    def test_candidate_count_field_and_wrong_geographic_join_are_rejected(self):
        spec = copy.deepcopy(SPEC)
        spec["columns"]["count"] = "candidate_votes"
        rejected = self.intake(spec)
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["errors"][0]["code"], "candidate_vote_substitution")
        refs = copy.deepcopy(REFERENCES)
        refs["identities"]["01"]["feature_key"] = "NOT-A-REAL-KEY"
        joined = self.intake(references=refs)
        self.assertEqual(joined["status"], "rejected")
        self.assertEqual(joined["errors"][0]["code"], "geographic_join")

    def test_person_records_are_quarantined_never_packaged(self):
        self.input.write_bytes(BODY.replace(b"id,name", b"voter_id,name"))
        rejected = self.intake()
        self.assertEqual(rejected["errors"][0]["code"], "private_record_input")
        self.assertTrue(rejected["raw_inputs_quarantined_not_packaged"])
        self.assertFalse((Path(rejected["directory"]) / "complete-analysis.zip").exists())
        repeated = self.intake()
        self.assertTrue(repeated["no_op"])
        self.assertIsNone(repeated["complete_download"])

    def test_complete_download_contains_actual_originals_queries_code_and_exact_reproduction(self):
        result = self.intake()
        archive = Path(result["directory"]) / "complete-analysis.zip"
        destination = self.root / "replay"
        with zipfile.ZipFile(archive) as package:
            self.assertEqual(package.read("originals/counts"), BODY)
            self.assertEqual(package.read("references/approved"), GEOMETRY)
            self.assertIn("code/participation_intake/adapters.py", package.namelist())
            package.extractall(destination)
        reproduced = subprocess.check_output([sys.executable, "-I", "-S", str(destination / "reproduce.py")])
        self.assertEqual(reproduced, (destination / "queries.json").read_bytes())

    def test_json_adapter_uses_same_contract_and_preserves_every_native_field(self):
        spec = copy.deepcopy(SPEC)
        spec["adapter"], spec["aggregate_parents"] = "json", False
        spec["format"] = dict(items_path="results")
        row = dict(id="01", name="P1", reported="1", voted=0, registered_7am=10,
                   registered_day=0, roster=0, absentee=0, native_status="not certified")
        self.input.write_bytes(encoded(dict(results=[row])))
        result = self.intake(spec)
        parsed = json.loads((Path(result["directory"]) / "queries.json").read_bytes())[0]
        self.assertEqual(parsed["contract"], "participation.observation.v1")
        self.assertEqual(parsed["source"]["fields"], row)
        self.assertEqual(parsed["count"]["value"], 0)

    def test_unsafe_count_and_inferred_timezone_fail_closed(self):
        self.input.write_bytes(BODY.replace(b"01,P1,1,0", b"01,P1,1,9007199254740992"))
        result = self.intake()
        self.assertEqual(result["errors"][0]["code"], "unsafe_count")
        self.input.write_bytes(BODY)
        result = self.intake()
        row = json.loads((Path(result["directory"]) / "queries.json").read_bytes())[0]
        row["source_clock"]["timezone"] = "UTC"
        with self.assertRaisesRegex(IntakeError, "inferred timezone"):
            validate(row)

    def test_malformed_nested_contracts_reject_cleanly(self):
        result = self.intake()
        valid = json.loads((Path(result["directory"]) / "queries.json").read_bytes())[0]
        for key, value in [("quality", {}), ("source", {"id": None}),
                           ("geography", {"id": []}), ("denominator", []),
                           ("source_clock", "not a native clock")]:
            with self.subTest(key=key):
                row = copy.deepcopy(valid)
                row[key] = value
                with self.assertRaises(IntakeError):
                    validate(row)
        row = copy.deepcopy(valid)
        row["denominator"]["value"] = "10"
        with self.assertRaises(IntakeError):
            validate(row)

    def test_access_denial_stops_route_and_retains_attempt_without_retry(self):
        url = SPEC["inputs"]["counts"]["url"]
        opener = mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError(url, 403, "Denied", {}, None)
        with mock.patch("participation_intake.engine.urllib.request.build_opener", return_value=opener):
            rejected = run(SPEC, self.store)
            stopped = run(SPEC, self.store)
        self.assertEqual(opener.open.call_count, 1)
        self.assertEqual(rejected["errors"][0]["code"], "source_access")
        self.assertEqual(stopped["errors"][0]["code"], "source_stopped")
        attempts = list((self.store.root / "attempts").glob("*.json"))
        self.assertEqual(len(attempts), 1)
        self.assertTrue(json.loads(attempts[0].read_bytes())["acquisition_incomplete"])

    def test_conditional_304_reuses_verified_original(self):
        description = SPEC["inputs"]["counts"]
        self.store.object(BODY)
        self.store.db.execute("INSERT INTO inputs VALUES(?,?,?,?,?)",
            (description["url"], pin(BODY)["sha256"], '"native-v1"', "Tue, 10 Nov 2026 08:08:00 GMT", None))
        opener = mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError(description["url"], 304, "Unchanged", {}, None)
        with mock.patch("participation_intake.engine.urllib.request.build_opener", return_value=opener):
            body, receipt = self.store.acquire(description)
        self.assertEqual(body, BODY)
        self.assertEqual(receipt["status"], 304)
        self.assertEqual(dict(opener.open.call_args[0][0].header_items())["If-none-match"], '"native-v1"')

    def test_clock_html_publishes_all_facts_but_no_application_code(self):
        page = self.root / "page.html"
        page.write_text("<html><script>compiledPublisherApp=999999</script>"
            "<style>compiledStyle1234</style><p>Last Updated: native-clock</p>"
            "<table><tr><td>First total</td><td>123</td></tr>"
            "<tr><td>Second total</td><td>456</td></tr></table></html>")
        spec = copy.deepcopy(SPEC)
        spec["inputs"]["page"] = dict(url="https://elections.example.gov/clock", publication="factual_html")
        spec["source_clock"] = dict(input="page", html=True, pattern="Last Updated: (native-clock)", timezone=None)
        result = run(spec, self.store, supplied={"counts": self.input, "page": page},
            references=REFERENCES, geometry_inputs={"approved": GEOMETRY})
        destination = self.root / "html-replay"
        with zipfile.ZipFile(Path(result["directory"]) / "complete-analysis.zip") as archive:
            facts = archive.read("originals/page")
            self.assertNotIn(b"compiledPublisher", facts)
            self.assertNotIn(b"compiledStyle", facts)
            self.assertIn(b"First total", facts)
            self.assertIn(b"Second total", facts)
            self.assertIn(b"123", facts)
            self.assertIn(b"456", facts)
            archive.extractall(destination)
        reproduced = subprocess.check_output([sys.executable, "-I", "-S", str(destination / "reproduce.py")])
        self.assertEqual(reproduced, (destination / "queries.json").read_bytes())

    def test_pdf_adapter_uses_same_contract_and_preserves_a_reported_zero(self):
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
            DictionaryObject({NameObject("/F1"): font})})
        content = DecodedStreamObject()
        content.set_data(b"BT /F1 12 Tf 40 700 Td (2026 General Election) Tj "
                         b"0 -20 Td (01 P1 0 10 0 0 0 1) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(content)
        with self.input.open("wb") as target:
            writer.write(target)
        spec = copy.deepcopy(SPEC)
        spec.update(adapter="pdf", aggregate_parents=False)
        spec["format"] = dict(election_pattern=r"2026 General Election",
            row_pattern=r"^(?P<id>01)\s+(?P<name>P1)\s+(?P<voted>\d+)\s+"
                r"(?P<registered_7am>\d+)\s+(?P<registered_day>\d+)\s+"
                r"(?P<roster>\d+)\s+(?P<absentee>\d+)\s+(?P<reported>[01])$")
        result = self.intake(spec)
        self.assertEqual(result["status"], "awaiting_publication")
        row = json.loads((Path(result["directory"]) / "queries.json").read_bytes())[0]
        self.assertEqual(row["count"], dict(value=0, status="reported", literal="0"))
        self.assertEqual(row["measure"]["literal"], "Total Number Voted")
        self.assertIsNone(row["source_clock"]["timezone"])

    def test_empty_malformed_and_ambiguous_source_rows_are_rejected(self):
        for body in [b"id,name,reported,voted,registered_7am,registered_day,roster,absentee\n",
                     BODY.replace(b"01,P1,1", b"01,P1,2"), BODY.replace(b"01,P1", b"01,P1,EXTRA")]:
            with self.subTest(body=body):
                self.input.write_bytes(body)
                result = self.intake()
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(result["errors"][0]["code"], "source_schema")
        spec = copy.deepcopy(SPEC)
        spec["adapter"] = "json"
        self.input.write_bytes(b'{"truncated":')
        self.assertEqual(self.intake(spec)["errors"][0]["code"], "source_schema")

    def test_rejected_candidate_and_geographic_join_reports_reproduce_truthfully(self):
        cases = []
        spec = copy.deepcopy(SPEC)
        spec["columns"]["count"] = "candidate_votes"
        cases.append(self.intake(spec))
        refs = copy.deepcopy(REFERENCES)
        refs["identities"]["01"]["feature_key"] = "wrong-key"
        cases.append(self.intake(references=refs))
        for index, result in enumerate(cases):
            with self.subTest(index=index):
                destination = self.root / ("rejected-replay-" + str(index))
                with zipfile.ZipFile(Path(result["directory"]) / "complete-analysis.zip") as archive:
                    archive.extractall(destination)
                reproduced = subprocess.check_output(
                    [sys.executable, "-I", "-S", str(destination / "reproduce.py")])
                self.assertEqual(reproduced, b"[]\n")


if __name__ == "__main__":
    unittest.main()
