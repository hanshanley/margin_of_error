import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


spec = importlib.util.spec_from_file_location("fulton", Path(__file__).with_name("review-fulton-county-results.py"))
fulton = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fulton)


def report_text(label, participants=1, registrations=2):
    source = f"""{label}    Official Results
FULTON COUNTY, PENNSYLVANIA
GENERAL ELECTION, NOVEMBER 3, 2026
Registered Voters
{participants} of {registrations} = 50.00%
Precincts Reporting
{13 if label == "Cumulative Results" else 0} of {13 if label == "Cumulative Results" else 1} = {100 if label == "Cumulative Results" else 0}.00%
Run Date 11/03/2026
Run Time 9:04 PM
"""
    if label != "Cumulative Results":
        source += f"{participants} of {registrations} registered voters = 50.00%\n"
    for office in fulton.OFFICES:
        vote_for = "the candidates of ONE Party" if office == fulton.OFFICES[0] else "One"
        source += f"""
{office} - (Vote for {vote_for})
Choice Party Mail Election Day Voting Provisional Total
FIRST LAST RUNNING MATE NATIVE 0 0.00% {participants} 100.00% 0 0.00% {participants} 100.00%
Cast Votes: 0 0.00% {participants} 100.00% 0 0.00% {participants} 100.00%
Undervotes: 0 0 0 0
Overvotes: 0 0 0 0
"""
    return source + "*** End of report ***"


def fixture():
    return {"schema": "fulton-2026-complete-numerical-facts-v1", "reports": [
        fulton.parse_report(report_text("Cumulative Results", 13, 26), "Cumulative Results", "county.pdf"),
        *(fulton.parse_report(report_text(unit), unit, f"{unit}.pdf") for unit in fulton.UNITS),
    ]}


class FultonReviewTest(unittest.TestCase):
    def test_complete_native_fields_and_ticket_names(self):
        facts = fulton.validate(fixture())
        county, unit = facts["reports"][:2]
        self.assertEqual(county["accounted_ballots_by_mode"], [0, 13, 0, 13])
        self.assertEqual(unit["statements"][1], ["0", "1", "0.00%"])
        self.assertEqual(unit["native_status_literal"], "Official Results")
        self.assertIsNone(unit["declared_timezone"])
        self.assertEqual(unit["contests"][0]["candidates"][0]["name"], "FIRST LAST RUNNING MATE")
        self.assertEqual(unit["contests"][0]["candidates"][0]["party_literal"], "NATIVE")

    def test_rejects_wrong_election_or_native_report_identity(self):
        for source in (report_text("Ayr Township").replace("2026", "2024"),
                       report_text("Belfast Township"),
                       report_text("Ayr Township").replace("Run Time", "Unknown Time"),
                       report_text("Ayr Township").replace("Official Results", "Other status")):
            with self.assertRaises(ValueError):
                fulton.parse_report(source, "Ayr Township", "source.pdf")

    def test_rejects_unparsed_rows_and_incomplete_contests(self):
        for source in (report_text("Ayr Township").replace("Cast Votes:", "Unexpected row:"),
                       report_text("Ayr Township").replace("Undervotes: 0 0 0 0", "Undervotes: 0 0"),
                       report_text("Ayr Township").replace(fulton.OFFICES[-1], "Different office")):
            with self.assertRaises(ValueError):
                fulton.parse_report(source, "Ayr Township", "source.pdf")

    def test_rejects_missing_or_duplicated_municipal_reports(self):
        facts = fixture()
        for reports in (facts["reports"][:-1], [*facts["reports"][:-1], facts["reports"][1]]):
            with self.assertRaisesRegex(ValueError, "source report"):
                fulton.validate({**facts, "reports": reports})

    def test_preserves_blanks_as_errors_and_requires_accounting(self):
        for value in ("", "-1", "1.5"):
            facts = fixture()
            facts["reports"][1]["contests"][0]["candidates"][0]["count_literals"][0] = value
            with self.assertRaises(ValueError):
                fulton.validate(facts)
        facts = fixture()
        facts["reports"][1]["contests"][0]["accounting"]["undervotes"] = ["0", "1", "0", "1"]
        with self.assertRaisesRegex(ValueError, "ballot accounting"):
            fulton.validate(facts)

    def test_rejects_printed_fraction_counter_or_literal_party_changes(self):
        facts = fixture()
        facts["reports"][1]["statements"][0][2] = "99.99%"
        with self.assertRaisesRegex(ValueError, "printed fraction"):
            fulton.validate(facts)
        facts = fixture()
        facts["reports"][1]["statements"][1] = ["1", "1", "100.00%"]
        with self.assertRaisesRegex(ValueError, "reporting counters"):
            fulton.validate(facts)
        facts = fixture()
        facts["reports"][1]["contests"][0]["candidates"][0]["party_literal"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "candidate inventory"):
            fulton.validate(facts)

    def test_candidate_votes_are_not_participation(self):
        facts = fixture()
        for report in facts["reports"]:
            contest = report["contests"][1]
            old_cast = copy.deepcopy(contest["accounting"]["cast"]["count_literals"])
            contest["candidates"][0].update(count_literals=["0"] * 4, percent_literals=["0.00%"] * 4)
            contest["accounting"]["cast"] = {"count_literals": ["0"] * 4, "percent_literals": ["0.00%"] * 4}
            contest["accounting"]["undervotes"] = old_cast
        self.assertEqual(fulton.validate(facts)["reports"][0]["accounted_ballots_by_mode"][-1], 13)

    def test_complete_facts_archive_reproduces_without_private_presentations(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first", Path(directory) / "second"
            audit = fulton.build(fixture(), first)
            fulton.build(json.loads((first / "source-records.json").read_text()), second)
            archive = "complete-fulton-2026-numerical-facts-01.zip"
            self.assertEqual((first / archive).read_bytes(), (second / archive).read_bytes())
            self.assertEqual(len(audit["table_rows"]), 8)
            self.assertFalse(audit["maps_approved"])
            with zipfile.ZipFile(first / archive) as package:
                self.assertEqual(len(package.namelist()), 12)
                self.assertFalse(any(name.endswith((".html", ".pdf")) for name in package.namelist()))
                self.assertEqual(len(set(package.namelist())), len(package.namelist()))


if __name__ == "__main__":
    unittest.main()
