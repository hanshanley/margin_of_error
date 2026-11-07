import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "nd_long_history", Path(__file__).with_name("review-north-dakota-long-ballot-history.py"))
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def page(year=2016):
    blocks = []
    for number in range(1, 54):
        code, name = f"{number:02}", f"County {number}"
        blocks.append(
            '<div class="turnout-county-data-wrapper">'
            f"<a href='/ResultsSW.aspx?type=CTYALL&amp;map=CTY&amp;cty={code}"
            f"&amp;name={name}&amp;eid={review.ELECTION_IDS[year]}'>"
            f"<h1>{name}</h1></a>"
            f'<div id="countyturnout{code}" class="section group">'
            '<div class="county-precinct odd">Precinct 1 &amp; mail</div>'
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
    rows = [review.historical(page(year), year) for year in review.ELECTION_IDS]
    for year in (2022, 2024, 2026):
        row = copy.deepcopy(rows[0])
        row.update(year=year, election_date=review.DATES[year])
        for county in row["counties"]:
            if year == 2026:
                county["native_county_id"] = "100" + county["native_county_id"]
                county["county_identifier_system"] = "current_portal_location_id"
            for precinct in county["precincts"]:
                del precinct["precinct_label"]
                precinct["precinct_id"] = (
                    "1" if year == 2026 else county["native_county_id"] + "0001")
        if year == 2026:
            row.update(
                official=False, source_version="v75",
                source_updated_native="2026-11-05T01:30:08.5674284Z",
                source_clock_timezone="UTC", native_eligible_voters=None,
                native_denominator_definition=None, ballots=477)
            for county in row["counties"]:
                county["ballots"] = 9
                county["precincts"][0]["ballots"] = 9
        rows.append(row)
    return rows


class NorthDakotaLongHistoryTests(unittest.TestCase):
    def test_native_named_units_are_not_invented_numeric_ids_or_crosswalks(self):
        row = review.historical(page(), 2016)
        self.assertEqual(row["counties"][0]["precincts"],
                         [{"precinct_label": "Precinct 1 & mail", "ballots": 10}])
        result = review.compare(observations())
        self.assertEqual(result["statewide"]["reported_count_change_since"]["2016"], -53)
        self.assertEqual(sum(r["reported_count_change_since"]["2016"]
                             for r in result["counties"]), -53)
        self.assertFalse(result["individual_transitions_qualified"])
        self.assertFalse(result["precinct_longitudinal_comparison_qualified"])
        for field in ("measured_prior_voter_dropoff", "new_or_returning_voters",
                      "party_switchers", "demographic_turnout_rate"):
            self.assertIsNone(result["statewide"][field])

    def test_wrong_date_status_year_or_county_election_fails(self):
        for before, after in (
                ("November 8", "November 9"), (">Official<", ">Unofficial<"),
                ("2016 General", "2018 General"),
                (review.ELECTION_IDS[2016], review.ELECTION_IDS[2018]),
                ("name=County 1", "name=Other"), ("cty=01", "cty=02"),
                ("type=CTYALL", "type=LEGALL"),
                ("/ResultsSW.aspx", "https://example.com/ResultsSW.aspx")):
            with self.subTest(before=before), self.assertRaises(ValueError):
                review.historical(page().replace(before, after, 1), 2016)

    def test_missing_duplicate_unpaired_or_negative_units_fail(self):
        for before, after in (
                ('>Precinct 1 &amp; mail</div>', '></div>'),
                ('class="county-cast odd">10', 'class="other">10'),
                ('class="county-cast odd">10', 'class="county-cast odd">-10'),
                ('countyturnout01', 'countyturnout02'),
                ('class="county-cast odd">10', 'class="county-cast odd">1,0')):
            with self.subTest(before=before), self.assertRaises(ValueError):
                review.historical(page().replace(before, after, 1), 2016)
        pair = ('<div class="county-precinct odd">Precinct 1 &amp; mail</div>'
                '<div class="county-cast odd">10</div>')
        with self.assertRaises(ValueError):
            review.historical(page().replace(pair, pair + pair, 1), 2016)

    def test_state_and_complete_reporting_controls_reject_unreconciled_sources(self):
        for before, after in (
                ("Voter Turnout<span>530", "Voter Turnout<span>531"),
                ("Fully<span>53", "Fully<span>52"),
                ("Total Precincts<span>53", "Total Precincts<span>54"),
                ('orange;">0', 'orange;">1')):
            with self.subTest(before=before), self.assertRaises(ValueError):
                review.historical(page().replace(before, after, 1), 2016)
        zero = page().replace('county-cast odd">10', 'county-cast odd">0', 1)
        zero = zero.replace("Voter Turnout<span>530", "Voter Turnout<span>520")
        self.assertEqual(review.historical(zero, 2016)["counties"][0]["ballots"], 0)

    def test_county_local_current_ids_and_distinct_historical_names_are_preserved(self):
        result = review.compare(observations())
        self.assertEqual(len(result["counties"]), 53)
        self.assertEqual(len(result["statewide"]["ballots_by_year"]), 6)
        self.assertEqual(len(result["statewide"]["reported_count_change_since"]), 5)

    def test_changed_year_scope_missing_county_or_promoted_status_fails(self):
        for mutation in ("year", "date", "name", "status", "bool", "missing", "extra"):
            rows = observations()
            if mutation == "year":
                rows[0]["year"] = 2018
            elif mutation == "date":
                rows[0]["election_date"] = review.DATES[2018]
            elif mutation == "name":
                rows[0]["counties"][0]["county_name"] = "Unmatched"
            elif mutation == "status":
                rows[-1]["official"] = True
            elif mutation == "bool":
                rows[0]["counties"][0]["precincts"][0]["ballots"] = True
            elif mutation == "missing":
                rows[0]["counties"].pop()
            else:
                rows[0]["counties"][0]["precincts"][0]["personal_record"] = "no"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                review.compare(rows)

    def test_changed_unit_or_county_controls_fail(self):
        for mutation in ("state", "county", "unit_count", "unit", "parent"):
            rows = observations()
            if mutation == "state":
                rows[0]["ballots"] += 1
            elif mutation == "county":
                rows[0]["counties"][0]["ballots"] += 1
            elif mutation == "unit_count":
                rows[0]["reported_precincts"] += 1
            elif mutation == "unit":
                rows[0]["counties"][0]["precincts"][0]["ballots"] += 1
            else:
                rows[3]["counties"][0]["precincts"][0]["precinct_id"] = "020001"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                review.compare(rows)

    def test_frozen_native_receipt_rejects_changed_bytes_status_and_url(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.html"
            path.write_bytes(b"frozen")
            receipt = {"url": "source", "status": 200, "bytes": 6,
                       "sha256": hashlib.sha256(b"frozen").hexdigest()}
            sidecar = path.with_suffix(".html.receipt.json")
            sidecar.write_text(json.dumps(receipt))
            self.assertEqual(review.frozen(path, "source")[0], "frozen")
            for key, value in (("url", "other"), ("status", 403), ("bytes", 7),
                               ("sha256", "wrong")):
                sidecar.write_text(json.dumps(dict(receipt, **{key: value})))
                with self.assertRaises(ValueError):
                    review.frozen(path, "source")


if __name__ == "__main__":
    unittest.main()
