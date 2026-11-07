import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "nd_history", Path(__file__).with_name("review-north-dakota-ballot-history.py"))
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def page(year=2024):
    blocks = []
    for number in range(1, 54):
        code, name = f"{number:02}", f"County {number}"
        blocks.append(
            '<div class="turnout-county-data-wrapper">'
            f"<a href='/ResultsSW.aspx?type=CTYALL&amp;map=CTY&amp;cty={code}&amp;name={name}'>"
            f"<h1>{name}</h1></a>"
            f'<div id="countyturnout{code}" class="section group">'
            f'<div class="county-precinct odd">{code}0001</div>'
            '<div class="county-cast odd">10</div></div></div>')
    return (
        f"<h1><span>Official</span> {year} General Election Results</h1>"
        f"<h2>{review.DATES[year]}</h2>"
        '<div class="last-updated">Results last updated: native clock</div>'
        "Voter Turnout<span>530</span>Eligible Voters<span>1,000</span>"
        "Precincts Fully<span>53</span>Total Precincts<span>53</span>"
        'Precincts Partially<span style="color: orange;">0</span>'
        + "".join(blocks))


def observations():
    older, prior = review.historical(page(2022), 2022), review.historical(page(), 2024)
    current = copy.deepcopy(prior)
    current.update(year=2026, official=False, ballots=477)
    for row in current["counties"]:
        row["ballots"] = 9
    return [older, prior, current]


class NorthDakotaHistoryTests(unittest.TestCase):
    def test_complete_native_rows_keep_ordinal_ids_and_missing_transitions(self):
        historical = review.historical(page(), 2024)
        self.assertEqual(historical["ballots"], 530)
        self.assertEqual(historical["native_eligible_voters"], 1000)
        self.assertEqual(historical["counties"][0]["native_county_id"], "01")
        self.assertEqual(historical["counties"][0]["county_identifier_system"],
                         "legacy_portal_ordinal_not_FIPS")
        result = review.compare(observations())
        self.assertFalse(result["current_snapshot_official"])
        self.assertFalse(result["precinct_longitudinal_comparison_qualified"])
        self.assertEqual(result["statewide"]["reported_ballot_count_change_since_2024"], -53)
        self.assertEqual(sum(row["reported_ballot_count_change_since_2024"]
                             for row in result["counties"]), -53)
        for key in ("measured_prior_voter_dropoff", "new_or_returning_voters",
                    "party_switchers", "demographic_turnout_rate"):
            self.assertIsNone(result["statewide"][key])

    def test_wrong_year_date_and_certification_fail(self):
        for text in (page(2022), page().replace("November 5", "November 4"),
                     page().replace(">Official<", ">Unofficial<")):
            with self.assertRaises(ValueError):
                review.historical(text, 2024)

    def test_missing_duplicate_and_wrong_parent_precinct_fail(self):
        for text in (page().replace('>010001</div>', '>020001</div>'),
                     page().replace('>010001</div>', '></div>'),
                     page().replace('class="county-cast odd">10', 'class="other">10', 1),
                     page().replace('countyturnout01', 'countyturnout02'),
                     page().replace('cty=01', 'cty=02', 1)):
            with self.assertRaises(ValueError):
                review.historical(text, 2024)

    def test_wrong_county_query_or_name_fails(self):
        for before, after in (("type=CTYALL", "type=LEGALL"), ("name=County 1", "name=Other"),
                              ("<h1>County 1</h1>", "<h1>Other</h1>")):
            with self.assertRaises(ValueError):
                review.historical(page().replace(before, after, 1), 2024)

    def test_invalid_missing_or_inconsistent_ballot_controls_fail(self):
        for before, after in (("Voter Turnout<span>530", "Voter Turnout<span>531"),
                              ("Fully<span>53", "Fully<span>52"),
                              ("Total Precincts<span>53", "Total Precincts<span>54"),
                              ('orange;">0', 'orange;">1'),
                              ('county-cast odd">10', 'county-cast odd">-10'),
                              ('county-cast odd">10', 'county-cast odd">1,0'),
                              ('county-cast odd">10', 'county-cast odd">')):
            with self.assertRaises(ValueError):
                review.historical(page().replace(before, after, 1), 2024)

    def test_zero_is_valid_but_missing_is_not_zero(self):
        text = page().replace('county-cast odd">10', 'county-cast odd">0', 1)
        text = text.replace("Voter Turnout<span>530", "Voter Turnout<span>520")
        self.assertEqual(review.historical(text, 2024)["counties"][0]["ballots"], 0)
        for value in ("", "NaN", "1.5", "-1", "1,23", " 10", "01"):
            with self.assertRaises(ValueError):
                review.integer(value)

    def test_county_mismatch_duplicate_and_changed_controls_fail(self):
        for mutation in ("name", "duplicate", "ballots", "year"):
            rows = observations()
            if mutation == "name":
                rows[2]["counties"][0]["county_name"] = "Unmatched"
            elif mutation == "duplicate":
                rows[2]["counties"][0]["county_name"] = rows[2]["counties"][1]["county_name"]
            elif mutation == "ballots":
                rows[2]["ballots"] += 1
            else:
                rows[2]["year"] = 2024
            with self.assertRaises(ValueError):
                review.compare(rows)

    def test_native_receipt_rejects_changed_bytes_url_and_length(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.html"
            path.write_bytes(b"frozen")
            receipt = {"url": "source", "bytes": 6,
                       "sha256": hashlib.sha256(b"frozen").hexdigest()}
            self.assertEqual(review.frozen(path, receipt, "source"), b"frozen")
            for key, value in (("url", "other"), ("bytes", 7), ("sha256", "wrong")):
                changed = dict(receipt, **{key: value})
                with self.assertRaises(ValueError):
                    review.frozen(path, changed, "source")
            path.write_bytes(b"change")
            with self.assertRaises(ValueError):
                review.frozen(path, receipt, "source")


if __name__ == "__main__":
    unittest.main()
