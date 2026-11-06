"""Synthetic, offline regression tests for Centre's native-source review."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile


SPEC = importlib.util.spec_from_file_location(
    "centre_review", Path(__file__).with_name("review-centre-county-results.py"))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def district(i):
    return "state_house_77" if i <= 34 else "state_house_82" if i <= 66 else "state_house_171"


def option_values(office, option):
    if option.startswith("DEM "):
        return (3, 2, 1, 0)
    if option.startswith("REP "):
        return (1, 1, 0, 0)
    if option == "Write-In Totals" and office == "governor_lieutenant_governor":
        return (1, 1, 0, 0)
    return (0, 0, 0, 0)


def contest(office, count=1, county=False):
    heading = next(k for k, v in M.HEADINGS.items() if v == office)
    rows = {k: tuple(v * count for v in option_values(office, k)) for k in M.FIELDS[office]}
    rows["Not Assigned"] = rows["Write-In Totals"]
    if office == "governor_lieutenant_governor":
        rows["Write-In: ASD"] = (0, 0, 0, 0)
    rows["Total Votes Cast"] = M.total([rows[k] for k in M.FIELDS[office]])
    rows["Contest Totals"] = tuple(v * count for v in (5, 4, 1, 0))
    lines = ["Vote For 1", heading]
    lines.extend(k + " " + " ".join(map(str, v)) for k, v in rows.items())
    if county:
        lines.append(f"Precincts Reporting {count} of {count}")
    return "\n".join(lines)


def fixture():
    header = ("Centre County\nUNOFFICIAL RESULTS\n2026 General Gubernatorial Election\n"
              "Electionware County\nNovember 3, 2026\n")
    reporting = ("Election Day Precincts Reporting 87 of 87 87 0 0\n"
                 "Precincts Complete 0 of 87 0 0 0\n"
                 "Precincts Partially Reported 87 of 87 87 0 0\n"
                 "Absentee/ Early Precincts Reporting 86 of 87 0 86 0\n")
    def participation(n):
        return (f"Registered Voters - Total {10*n}\n{5*n}Ballots Cast - Total {4*n} {n} 0\n"
                "0Ballots Cast - Blank 0 0 0\nVoter Turnout - Total 50.00%\n")
    precinct_pages, observations = [], []
    for i in range(1, 88):
        label = f"{i} SYNTHETIC PRECINCT {i}"
        active = ["governor_lieutenant_governor", "us_house", district(i)]
        precinct_pages.append(label + "\n" + header + participation(1)
            + "\n".join(contest(o) for o in active)
            + f"\nPrecinct Summary - 11/04/2026 12:40AM  87Page {i} of")
        for pos, method in enumerate(M.METHODS, 1):
            row = dict(ObjectId=len(observations) + 1, PRECINCT_CODE=100+i,
                       PRECINCT_NAME=label, VotingType=method,
                       REGISTERED_VOTERS_TOTAL=10 if pos == 1 else None,
                       BALLOTS_CAST_TOTAL=(4, 1, 0)[pos-1],
                       BALLOTS_CAST_BLANK=240 if i == 1 and pos == 3 else 0)
            for office, fields in M.FIELDS.items():
                for option, field in fields.items():
                    row[field] = option_values(office, option)[pos] if office in active else 0
            observations.append(dict(attributes=row))
    county_pages = [
        header + reporting + participation(87)
        + "\n".join(contest(o, n, True) for o, n in [
            ("governor_lieutenant_governor", 87), ("us_house", 87), ("state_house_77", 34)])
        + "\nElection Summary - 11/04/2026 12:40AM  2Page 1 of",
        header + "\n".join(contest(o, n, True) for o, n in [
            ("state_house_82", 32), ("state_house_171", 21)])
        + "\nElection Summary - 11/04/2026 12:40AM  2Page 2 of",
    ]
    html = ('<html><title>Synthetic source fixture</title>'
        '<a href="https://experience.arcgis.com/experience/637f95443bd04cb4a891b0f2de161129">Dashboard</a>'
        '<a href="/DocumentCenter/View/44859/precinctsummary">Precinct PDF</a>'
        '<a href="/DocumentCenter/View/44860/electionsummary">County PDF</a>'
        '<p>Updated: 11/4/2026 at 12:44 am</p>'
        + "".join(f'<a href="/synthetic/{i}">{i} - Synthetic Precinct {i}</a>' for i in range(1, 88))
        + '<p>[REDACTED_PUBLIC_SERVICE_KEY] [REDACTED_PUBLIC_SERVICE_KEY]</p></html>')
    raw = {name: b"" if name in M.FAILED else b"{}" for name in M.FILES}
    raw.update({
        "official-results-browser.html": html.encode(),
        "official-precinct-summary-browser.pdf": b"%PDF-synthetic-precinct",
        "official-election-summary-browser.pdf": b"%PDF-synthetic-county",
        "precinct-stats-layer.json": json.dumps(dict(
            objectIdField="ObjectId", fields=[{"name": k} for k in observations[0]["attributes"]],
            editingInfo=dict(lastEditDate=1793770978424, dataLastEditDate=1792006443679))).encode(),
        "precinct-stats-all.json": json.dumps(dict(features=observations)).encode(),
        "precinct-stats-ids.json": json.dumps(dict(objectIds=list(range(1, 262)))).encode(),
        "precinct-stats-count.json": b'{"count":261}',
        "item-55b9957d0d6a4052adcaaecae1907fa5.json": b'{"error":{"code":400}}',
    })
    raw["precinct-stats-layer-after.json"] = raw["precinct-stats-layer.json"]
    return raw, precinct_pages, county_pages


def reader(precinct_pages, county_pages):
    def read(stream):
        pages = precinct_pages if stream.getvalue() == b"%PDF-synthetic-precinct" else county_pages
        return SimpleNamespace(pages=[
            SimpleNamespace(extract_text=lambda text=text: text) for text in pages])
    return read


def source_url(name):
    if name.startswith("official-"):
        if "precinct-summary" in name:
            return "https://centrecountypa.gov/DocumentCenter/View/44859/precinctsummary"
        if "election-summary" in name:
            return "https://centrecountypa.gov/DocumentCenter/View/44860/electionsummary"
        return M.INDEX.replace("https://", "https://www.") if "www" in name else M.INDEX
    if name.startswith("precinct-stats-"):
        return M.LAYER + ("" if name in {"precinct-stats-layer.json", "precinct-stats-layer-after.json"} else "/query")
    item = name[5:-5] if name.startswith("item-") else "637f95443bd04cb4a891b0f2de161129"
    return "https://www.arcgis.com/sharing/rest/content/items/" + item + (
        "/data" if name == "declared-experience-data.json" else "")


def write_originals(folder, raw):
    folder.mkdir()
    receipts = []
    for name in sorted(raw):
        body = raw[name]
        (folder / name).write_bytes(body)
        screening = dict(original_bytes=len(body), original_sha256=hashlib.sha256(body).hexdigest(),
                         replacements=0, service_key_replacements=0, telemetry_key_replacements=0,
                         removed_value_bytes=0)
        if name == "official-results-browser.html":
            screening.update(replacements=2, service_key_replacements=1, telemetry_key_replacements=1,
                             removed_value_bytes=69, original_bytes=len(body)+69-58)
        receipts.append(dict(path=name, requested_url=source_url(name), final_url=source_url(name),
            status=404 if name in M.FAILED else 200, bytes=len(body),
            sha256=hashlib.sha256(body).hexdigest(), screening=screening))
    (folder / "receipts.json").write_text(json.dumps(receipts))


class CentreTests(unittest.TestCase):
    def setUp(self):
        self.raw, self.precinct, self.county = fixture()

    def run_review(self):
        with patch.object(M, "PdfReader", side_effect=reader(self.precinct, self.county)):
            return M.review(self.raw)

    def mutate_api(self, mutate):
        data = json.loads(self.raw["precinct-stats-all.json"])
        mutate(data)
        self.raw["precinct-stats-all.json"] = json.dumps(data).encode()

    def test_complete_scopes_crosswalk_and_native_conflict(self):
        tables, audit = self.run_review()
        self.assertEqual(audit["native_precincts"], 87)
        self.assertEqual(audit["api_precinct_codes_differ_from_report_ids"], 87)
        self.assertEqual(audit["state_house_precinct_scopes"],
                         dict(state_house_77=34, state_house_82=32, state_house_171=21))
        self.assertEqual(audit["county_participation"]["ballots"], 435)
        self.assertEqual(audit["county_participation"]["house_ballot_residual_unclassified"], 87)
        self.assertEqual(audit["conflicting_api_blank_total"], 240)
        self.assertFalse(audit["county_ballot_methods"][2]["api_blank_accounting_usable"])
        self.assertIsNone(tables["native-api-observations.csv"][1]["REGISTERED_VOTERS_TOTAL"])
        self.assertEqual(len(tables["native-precinct-option-results.csv"]), 870)
        self.assertEqual(sum(r["votes"] for r in tables["county-contest-option-results.csv"]
                             if r["office"] == "governor_lieutenant_governor"), 435)
        self.assertFalse(audit["publication_approved"])

    def test_printed_rate_is_preserved_separately_from_calculated_rate(self):
        self.precinct[0] = self.precinct[0].replace("50.00%", "50.01%")
        tables, audit = self.run_review()
        self.assertEqual(audit["native_printed_rate_difference_rows"], 1)
        row = tables["native-printed-rate-differences.csv"][0]
        self.assertEqual((row["native_rate_literal"], row["calculated_rate"],
                          row["difference_percentage_points"]), ("50.01%", "50.00%", "0.01"))

    def test_truncated_export_or_duplicate_object_id_fails(self):
        for mode in ["limit", "duplicate"]:
            with self.subTest(mode=mode):
                original = self.raw["precinct-stats-all.json"]
                def mutate(d):
                    if mode == "limit":
                        d["exceededTransferLimit"] = True
                    else:
                        d["features"][0]["attributes"]["ObjectId"] = 2
                self.mutate_api(mutate)
                with self.assertRaises(ValueError):
                    self.run_review()
                self.raw["precinct-stats-all.json"] = original

    def test_missing_precinct_method_fails(self):
        self.mutate_api(lambda d: d["features"].pop())
        with self.assertRaisesRegex(ValueError, "object inventory"):
            self.run_review()

    def test_null_registration_must_not_be_replaced_with_zero(self):
        self.mutate_api(lambda d: d["features"][1]["attributes"].update(REGISTERED_VOTERS_TOTAL=0))
        with self.assertRaisesRegex(ValueError, "registration null/zero"):
            self.run_review()

    def test_out_of_scope_zero_must_not_become_a_positive_candidate(self):
        self.mutate_api(lambda d: d["features"][0]["attributes"].update(DEM_PAUL_TAKAC=1))
        with self.assertRaisesRegex(ValueError, "district scopes"):
            self.run_review()

    def test_candidate_method_mismatch_fails(self):
        self.mutate_api(lambda d: d["features"][0]["attributes"].update(DEM_RAY_BILGER=1))
        with self.assertRaisesRegex(ValueError, "option counts"):
            self.run_review()

    def test_unreviewed_mail_blank_difference_fails(self):
        self.mutate_api(lambda d: d["features"][1]["attributes"].update(BALLOTS_CAST_BLANK=1))
        with self.assertRaisesRegex(ValueError, "blank-ballot discrepancy"):
            self.run_review()

    def test_missing_pdf_page_or_option_fails(self):
        self.precinct.pop()
        with self.assertRaisesRegex(ValueError, "page inventory"):
            self.run_review()
        self.raw, self.precinct, self.county = fixture()
        self.precinct[0] = self.precinct[0].replace("LIB KEN KRAWCHUK / JOHN 0 0 0 0\n", "")
        with self.assertRaisesRegex(ValueError, "option or annotation inventory"):
            self.run_review()

    def test_layer_edit_during_acquisition_fails(self):
        changed = json.loads(self.raw["precinct-stats-layer-after.json"])
        changed["editingInfo"]["lastEditDate"] += 1
        self.raw["precinct-stats-layer-after.json"] = json.dumps(changed).encode()
        with self.assertRaisesRegex(ValueError, "changed during acquisition"):
            self.run_review()

    def test_original_integrity_and_unredacted_key_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "originals"
            write_originals(folder, self.raw)
            M.load_originals(folder)
            (folder / "precinct-stats-all.json").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "receipt mismatch"):
                M.load_originals(folder)
        for key in [b"AI" + b"za" + b"x" * 35,
                    b"license" + b"Key: 'synthetic-telemetry-value'"]:
            with self.subTest(key_kind="telemetry" if b"Key:" in key else "service"):
                raw = copy.deepcopy(self.raw)
                raw["official-results-browser.html"] += key
                with tempfile.TemporaryDirectory() as tmp:
                    folder = Path(tmp) / "originals"
                    write_originals(folder, raw)
                    with self.assertRaisesRegex(ValueError, "Unredacted public service key"):
                        M.load_originals(folder)

    def test_private_package_is_deterministic_and_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            originals = root / "originals"
            write_originals(originals, self.raw)
            with patch.object(M, "PdfReader", side_effect=reader(self.precinct, self.county)):
                for name in ["first", "second"]:
                    M.reproduce(originals, root / name)
            archive = "private-centre-2026-native-review-01.zip"
            self.assertEqual((root / "first" / archive).read_bytes(), (root / "second" / archive).read_bytes())
            with zipfile.ZipFile(root / "first" / archive) as package:
                self.assertEqual(len(package.namelist()), len(set(package.namelist())))
                checksums = json.loads(package.read("checksums.json"))
                for name, receipt in checksums.items():
                    body = package.read(name)
                    self.assertEqual((len(body), hashlib.sha256(body).hexdigest()),
                                     (receipt["bytes"], receipt["sha256"]))
                self.assertIn("native-api-observations.csv", checksums)
                self.assertIn("originals/official-precinct-summary-browser.pdf", checksums)

    def test_complete_public_facts_equal_private_tables_without_templates(self):
        private_tables, private_audit = self.run_review()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            originals, factual = root / "private", root / "facts"
            write_originals(originals, self.raw)
            with patch.object(M, "PdfReader", side_effect=reader(self.precinct, self.county)):
                M.export_fact_sources(originals, factual)
            public_tables, public_audit = M.review(M.load_originals(factual))
            self.assertEqual(private_tables, public_tables)
            self.assertEqual(private_audit["native_reporting_qualifications"],
                             public_audit["native_reporting_qualifications"])
            self.assertTrue(public_audit["publication_approved"])
            self.assertFalse(public_audit["new_maps_approved"])
            facts = json.loads((factual / M.FACT_FILE).read_bytes())
            self.assertEqual(len(facts["source_capture_receipts"]), 16)
            self.assertFalse(facts["presentation_templates_included"])
            manifest = json.loads((factual / "receipts.json").read_bytes())
            derived = next(r for r in manifest["files"] if r["path"] == M.FACT_FILE)
            self.assertNotIn("status", derived)
            for name in ["first", "second"]:
                M.reproduce(factual, root / name, public_facts=True)
            archive = "complete-centre-2026-native-facts-01.zip"
            self.assertEqual((root / "first" / archive).read_bytes(), (root / "second" / archive).read_bytes())
            with zipfile.ZipFile(root / "first" / archive) as package:
                self.assertFalse(any(n.endswith((".html", ".pdf")) for n in package.namelist()))
                self.assertIn("source-data/precinct-stats-all.json", package.namelist())
                self.assertEqual(sum(n.endswith(".csv") for n in package.namelist()), 13)

    def test_public_facts_still_enforce_native_zero_option_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            originals, factual = root / "private", root / "facts"
            write_originals(originals, self.raw)
            with patch.object(M, "PdfReader", side_effect=reader(self.precinct, self.county)):
                M.export_fact_sources(originals, factual)
            raw = M.load_originals(factual)
            facts = json.loads(raw[M.FACT_FILE])
            del facts["precinct"]["units"][0]["contests"][0]["rows"]["LIB KEN KRAWCHUK / JOHN"]
            raw[M.FACT_FILE] = json.dumps(facts).encode()
            with self.assertRaisesRegex(ValueError, "option or annotation inventory"):
                M.review(raw)

    def test_public_profile_cannot_package_private_presentation_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            originals = Path(tmp) / "private"
            write_originals(originals, self.raw)
            with self.assertRaisesRegex(ValueError, "Output profile"):
                M.reproduce(originals, Path(tmp) / "public", public_facts=True)

    def test_fact_sources_reject_an_added_presentation_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            originals, factual = root / "private", root / "facts"
            write_originals(originals, self.raw)
            with patch.object(M, "PdfReader", side_effect=reader(self.precinct, self.county)):
                M.export_fact_sources(originals, factual)
            (factual / "unexpected.html").write_text("<p>unexpected template</p>")
            with self.assertRaisesRegex(ValueError, "source inventory"):
                M.load_originals(factual)


if __name__ == "__main__":
    unittest.main()
