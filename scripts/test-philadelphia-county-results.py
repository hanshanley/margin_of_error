import csv
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "philadelphia", ROOT / "scripts/review-philadelphia-county-results.py")
PHILADELPHIA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PHILADELPHIA)


def fixture():
    header = (
        '<div id="pnlTestBanner" style="display:none">Testing in Progress</div>'
        '<h1>Unofficial 2026 General Election Results November 3, 2026</h1>'
        '<div id="pnlTurnoutReg">Total Ballots Cast<span>10</span>'
        'Registered Voters<span>20</span></div>'
        '<div id="pnlTurnoutInv">Ballots Cast by Mail:<span>4</span>'
        'Ballots Cast at Polling Place:<span>6</span>'
        'Ballots Cast by Provisional:<span>0</span></div>'
        '<div id="turnoutgraph"><div class="dough-percent">50.00%</div></div>'
        '<div id="pnlPrecinctReg"><span>2</span><span>2</span></div>'
        '<div>Results Last Updated 11/5/2026 5:21:56 PM EST</div>'
    )
    raw = {name: header.encode() for name in PHILADELPHIA.SOURCE_URLS}
    raw["official-election-home.html"] = b'<a href="/resources-data/election-result/">Current</a>'
    raw["official-current-election-index.html"] = b'<a href="https://vote.phila.gov/results/">Results</a>'
    raw["official-results-redirect.html"] = b'<iframe src="https://philadelphiaresults.azurewebsites.us"></iframe>'
    divisions = ""
    for code in ["01-01", "01-02"]:
        cells = "".join('<div class="county-cast">{}</div>'.format(n) for n in [10, 5, 3, 2, 0])
        divisions += '<div><div class="county-precinct">{}</div>{}</div>'.format(code, cells)
    raw["county-participation.html"] = (
        header + '<div id="countyturnout01">' + divisions + '</div>').encode()
    normal = [("A NAME DEM", "DEM", "Democratic", (1, 1, 0)),
              ("B NAME REP", "REP", "Republican", (1, 0, 0)),
              ("Write-In", "NON", "Nonpartisan", (0, 0, 0))]
    house = [normal[0], ("DENNIS MAHONEY TIP", "IND", "Independent", (1, 0, 0)), normal[2]]
    contests = [
        ("statewide-results.html", "GOVERNOR  AND LIEUTENANT GOVERNOR", ["01-01", "01-02"], normal, True),
        ("congress-results.html", "REPRESENTATIVE IN CONGRESS 2ND DISTRICT", ["01-01", "01-02"], house, True),
        ("state-senate-results.html", "SENATOR IN THE GENERAL ASSEMBLY 2ND DISTRICT", ["01-01"], [normal[0], normal[2]], False),
        ("state-house-results.html", "REPRESENTATIVE IN THE GENERAL ASSEMBLY 10TH DISTRICT", ["01-01"], [normal[0], normal[2]], False),
        ("state-house-results-page2.html", "REPRESENTATIVE IN THE GENERAL ASSEMBLY 197TH DISTRICT", ["01-02"], [normal[0], normal[2]], False),
        ("ballot-question-results.html", "QUESTION #1", ["01-01", "01-02"], [
            ("YES", "NON", "Nonpartisan", (2, 1, 0)), ("NO", "NON", "Nonpartisan", (1, 0, 0))], False),
    ]
    records = []
    for filename, title, units, candidates, special in contests:
        title += " (VOTE FOR 1)"
        total = sum(sum(c[3]) * len(units) for c in candidates)
        html = '<div class="wrapper-border"><div class="display-results-box-a"><h1>{}</h1></div>'.format(title)
        for literal, party, label, methods in candidates:
            votes = sum(methods) * len(units)
            html += (
                '<div><div class="display-results-box-d"><h1>{}</h1><h2 class="{}">{}</h2></div>'
                '<div class="display-results-box-f"><h1>{}</h1></div></div>'
            ).format(literal, party, label, votes)
            for unit in units + (["2nd Congressional"] if special else []):
                counts = (0, 0, 0) if unit == "2nd Congressional" else methods
                values = [title, party, literal, unit, "11/5/2026 7:15:35 PM", "1",
                          str(sum(counts)), str(Decimal(votes) / total), "{0}/{0}".format(len(units)),
                          *map(str, counts)]
                records.append(['="{}"'.format(v) for v in values] + [""])
        html += (
            '<div class="display-results-box-total"><h2>{0}</h2></div>'
            '<div class="precinct-fully">Divisions Reported: {1} / {1}</div></div>'
        ).format(total, len(units))
        raw[filename] = (header + html).encode()
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(PHILADELPHIA.CSV_FIELDS)
    writer.writerows(records)
    raw["native-county-export.bin"] = stream.getvalue().encode()
    return raw


class PhiladelphiaReviewTests(unittest.TestCase):
    def setUp(self):
        self.raw = fixture()

    def mutate_export(self, update):
        rows = list(csv.reader(io.StringIO(self.raw["native-county-export.bin"].decode())))
        update(rows)
        stream = io.StringIO(newline="")
        csv.writer(stream).writerows(rows)
        self.raw["native-county-export.bin"] = stream.getvalue().encode()

    def test_complete_scopes_methods_literal_party_difference_and_no_publication(self):
        tables, audit = PHILADELPHIA.review(self.raw)
        county = tables["county-participation.csv"][0]
        self.assertEqual((county["ballots_cast"], county["registered_voters"]), (10, 20))
        self.assertEqual(county["house_ballot_residual_unclassified"], 4)
        different = [r for r in tables["native-party-label-comparison.csv"] if r["literal_party_codes_differ"]]
        self.assertEqual(len(different), 1)
        self.assertEqual((different[0]["export_party_code"],
                          different[0]["displayed_candidate_party_suffix_literal"]), ("IND", "TIP"))
        self.assertEqual(len(tables["native-division-participation.csv"]), 2)
        self.assertEqual(audit["special_zero_rows"], 6)
        self.assertFalse(audit["publication_approved"])
        self.assertFalse(audit["new_maps_approved"])
        self.assertFalse(any(r["office"] == "ballot_question" for r in tables["county-contest-party-totals.csv"]))
        self.assertFalse(any(r["export_party_code"] == "REP" and r["office"] == "state_house"
                             for r in tables["county-contest-party-totals.csv"]))

    def test_visible_test_banner_rejected(self):
        self.raw["official-results-index.html"] = self.raw["official-results-index.html"].replace(
            b'display:none', b'display:block')
        with self.assertRaisesRegex(ValueError, "test banner"):
            PHILADELPHIA.review(self.raw)

    def test_missing_native_explicit_zero_rejected(self):
        def drop(rows):
            index = next(i for i, row in enumerate(rows[1:], 1) if
                         row[6] == '="0"' and row[3] == '="01-01"')
            rows.pop(index)
        self.mutate_export(drop)
        with self.assertRaisesRegex(ValueError, "Incomplete native option inventory"):
            PHILADELPHIA.review(self.raw)

    def test_candidate_methods_must_match_votes(self):
        self.mutate_export(lambda rows: rows[1].__setitem__(9, '="999"'))
        with self.assertRaisesRegex(ValueError, "methods do not equal"):
            PHILADELPHIA.review(self.raw)

    def test_nonzero_special_unit_cannot_be_a_division(self):
        def change(rows):
            row = next(r for r in rows[1:] if r[3] == '="2nd Congressional"')
            row[6] = row[9] = '="1"'
        self.mutate_export(change)
        with self.assertRaisesRegex(ValueError, "nonzero special-unit"):
            PHILADELPHIA.review(self.raw)

    def test_division_participation_must_reconcile_to_county(self):
        soup = BeautifulSoup(self.raw["county-participation.html"], "html.parser")
        soup.select_one("#countyturnout01 .county-cast").string = "11"
        self.raw["county-participation.html"] = str(soup).encode()
        with self.assertRaisesRegex(ValueError, "Division participation differs"):
            PHILADELPHIA.review(self.raw)

    def test_missing_paginated_original_rejected(self):
        self.raw.pop("state-house-results-page2.html")
        with self.assertRaisesRegex(ValueError, "Incomplete acquired original inventory"):
            PHILADELPHIA.review(self.raw)

    def test_extra_trailing_csv_payload_rejected(self):
        self.mutate_export(lambda rows: rows[1].append("unexpected"))
        with self.assertRaisesRegex(ValueError, "trailing native export"):
            PHILADELPHIA.review(self.raw)

    def test_private_package_reproduces_without_real_city_html_fixtures(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "originals"
            folder.mkdir()
            receipts = []
            for name, body in self.raw.items():
                (folder / name).write_bytes(body)
                receipts.append(dict(path=name, requested_url=PHILADELPHIA.SOURCE_URLS[name],
                    final_url=PHILADELPHIA.SOURCE_URLS[name], status=200, bytes=len(body),
                    sha256=hashlib.sha256(body).hexdigest()))
            controls = {
                "native-county-export.bin": dict(submit_name="ctl00$MainContent$LinkButton1",
                    submit_value="Philadelphia", command_argument="Philadelphia|04"),
                "state-house-results-page2.html": dict(submit_name="ctl00$MainContent$btnNext", submit_value="Next Page"),
            }
            for r in receipts:
                if r["path"] in controls:
                    r.update(method="POST", form_control=controls[r["path"]])
            (folder / "receipts.json").write_text(json.dumps(receipts))
            for name in ["first", "second"]:
                PHILADELPHIA.reproduce(folder, Path(temporary) / name)
            archive = "private-philadelphia-2026-native-review-01.zip"
            self.assertEqual((Path(temporary) / "first" / archive).read_bytes(),
                             (Path(temporary) / "second" / archive).read_bytes())


if __name__ == "__main__":
    unittest.main()
