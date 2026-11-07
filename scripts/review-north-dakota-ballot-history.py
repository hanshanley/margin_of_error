"""Reconcile official ND ballot histories without identifying individual transitions."""

import argparse
import gzip
import hashlib
import importlib.util
import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


HISTORICAL_URLS = {
    2022: "https://results.sos.nd.gov/VoterTurnoutDetails.aspx?eid=vxUYQ0lrpP4.",
    2024: "https://results.sos.nd.gov/VoterTurnoutDetails.aspx",
}
DATES = {2022: "November 8, 2022", 2024: "November 5, 2024"}


def integer(text):
    if not isinstance(text, str) or not re.fullmatch(r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)", text):
        raise ValueError("Missing or invalid native ballot count")
    return int(text.replace(",", ""))


def one(pattern, text):
    matches = re.findall(pattern, text, re.S)
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous native turnout field")
    return matches[0]


def historical(html, year):
    if year not in DATES:
        raise ValueError("Unsupported historical election")
    one(rf"<h1><span>Official</span> {year} General Election Results</h1>", html)
    one(rf"<h2>{DATES[year]}</h2>", html)
    ballots = integer(one(r"Voter Turnout<span>([^<]*)</span>", html))
    eligible = integer(one(r"Eligible Voters<span>([^<]*)</span>", html))
    fully = integer(one(r"Precincts Fully<span>([^<]*)</span>", html))
    total = integer(one(r"Total Precincts<span>([^<]*)</span>", html))
    partial = integer(one(r'Precincts Partially<span[^>]*>([^<]*)</span>', html))
    clock = one(r'<div class="last-updated">\s*Results last updated:\s*([^<]+)</div>', html).strip()
    counties, codes, precinct_ids = [], set(), set()
    blocks = html.split('<div class="turnout-county-data-wrapper">')[1:]
    for block in blocks:
        href, raw_name = one(r"<a href='([^']+)'>\s*<h1>([^<]+)</h1>", block)
        name = unescape(raw_name).strip()
        url = urlsplit(unescape(href))
        query = parse_qs(url.query)
        if (url.path != "/ResultsSW.aspx" or query.get("type") != ["CTYALL"]
                or query.get("map") != ["CTY"] or query.get("name") != [name]
                or len(query.get("cty", [])) != 1):
            raise ValueError("Historical county identity is not explicit")
        code = query["cty"][0]
        if code in codes or not re.fullmatch(r"\d{2}", code):
            raise ValueError("Duplicate or invalid historical county code")
        codes.add(code)
        one(rf'<div id="countyturnout{code}" class="section group"', block)
        cells = re.findall(r'<div class="county-(precinct|cast) (?:odd|even)">([^<]*)</div>', block)
        if not cells or len(cells) % 2:
            raise ValueError("Missing native precinct/ballot pair")
        precincts = []
        for offset in range(0, len(cells), 2):
            (kind, precinct), (value_kind, value) = cells[offset:offset + 2]
            if (kind != "precinct" or value_kind != "cast"
                    or not re.fullmatch(r"\d{6}", precinct) or not precinct.startswith(code)
                    or precinct in precinct_ids):
                raise ValueError("Duplicate, misplaced or invalid historical precinct")
            precinct_ids.add(precinct)
            precincts.append({"precinct_id": precinct, "ballots": integer(value)})
        counties.append({
            "county_name": name,
            "native_county_id": code,
            "county_identifier_system": "legacy_portal_ordinal_not_FIPS",
            "ballots": sum(row["ballots"] for row in precincts),
            "precincts": precincts,
        })
    if (codes != {f"{number:02}" for number in range(1, 54)}
            or partial != 0 or fully != total or len(precinct_ids) != total
            or sum(row["ballots"] for row in counties) != ballots):
        raise ValueError("Historical precinct/county/state controls do not reconcile")
    return {
        "year": year, "election_date": DATES[year], "official": True,
        "source_updated_native": clock, "source_clock_timezone": None,
        "ballots": ballots, "reported_precincts": total,
        "native_eligible_voters": eligible,
        "native_denominator_definition": "Source defines eligible voters as estimated residents aged 18+.",
        "counties": counties,
    }


def compare(observations):
    if sorted(row["year"] for row in observations) != [2022, 2024, 2026]:
        raise ValueError("Require one observation for each general election")
    indexed = {}
    for observation in observations:
        year = observation["year"]
        rows = observation["counties"]
        named = {row["county_name"]: row for row in rows}
        if (len(rows) != 53 or len(named) != 53
                or any(not name or name != name.strip() for name in named)
                or any(type(row["ballots"]) is not int or row["ballots"] < 0 for row in rows)
                or type(observation["ballots"]) is not int
                or sum(row["ballots"] for row in rows) != observation["ballots"]):
            raise ValueError("Duplicate county or inconsistent ballot control")
        indexed[year] = named
    names = set(indexed[2026])
    if any(set(indexed[year]) != names for year in (2022, 2024)):
        raise ValueError("County names differ; do not silently crosswalk or allocate")

    def changes(counts):
        return {
            "ballots_by_year": {str(year): counts[year] for year in (2022, 2024, 2026)},
            "reported_ballot_count_change_since_2024": counts[2026] - counts[2024],
            "reported_ballot_count_change_since_2022": counts[2026] - counts[2022],
            "measured_prior_voter_dropoff": None,
            "new_or_returning_voters": None,
            "party_switchers": None,
            "demographic_turnout_rate": None,
        }

    counties = [
        {"county_name": name,
         "current_native_county_id": indexed[2026][name]["native_county_id"],
         **changes({year: indexed[year][name]["ballots"] for year in indexed})}
        for name in sorted(names)
    ]
    return {
        "status": "observed_ballot_count_change_not_linked_turnout",
        "state_code": "ND",
        "current_snapshot_official": next(row["official"] for row in observations if row["year"] == 2026),
        "county_matching": "exact_source_names_not_fixed_people_or_precinct_boundaries",
        "precinct_longitudinal_comparison_qualified": False,
        "limitations": [
            "2026 is the frozen reported-count snapshot, not an estimate of final turnout.",
            "Historical county totals are sums of their native precinct rows, not independent county controls.",
            "Ballot-count changes do not identify individual dropoff, returning voters or candidate switching.",
            "No geographic overlay, precinct crosswalk or current group denominator is established.",
        ],
        "statewide": changes({row["year"]: row["ballots"] for row in observations}),
        "counties": counties,
        "observations": sorted(observations, key=lambda row: row["year"]),
    }


def frozen(path, receipt, url):
    raw = path.read_bytes()
    if (receipt["url"] != url or receipt["bytes"] != len(raw)
            or receipt["sha256"] != hashlib.sha256(raw).hexdigest()):
        raise ValueError("Frozen native source does not match its receipt")
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-cache", type=Path, required=True)
    parser.add_argument("--current-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    if args.output.exists() or repository in args.output.resolve().parents:
        raise ValueError("Require a new private output outside the repository")
    observations = []
    receipts = {}
    for year, url in HISTORICAL_URLS.items():
        path = args.historical_cache / f"turnout-{year}.html"
        receipt = json.loads(path.with_suffix(".html.receipt.json").read_text())
        observations.append(historical(frozen(path, receipt, url).decode("utf-8-sig"), year))
        receipts[str(year)] = receipt
    spec = importlib.util.spec_from_file_location(
        "nd_results_review", Path(__file__).with_name("review-north-dakota-precinct-results.py"))
    reviewer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reviewer)
    manifest = json.loads((args.current_source / "sources.json").read_text())
    native = {}
    for name in ("election.json", "full-results.json"):
        raw = gzip.decompress((args.current_source / "originals" / (name + ".gz")).read_bytes())
        receipt = manifest[name]
        if (receipt["url"] != reviewer.SOURCES[name] or receipt["bytes"] != len(raw)
                or receipt["sha256"] != hashlib.sha256(raw).hexdigest()):
            raise ValueError("Current frozen ND source does not match its receipt")
        native[name] = json.loads(raw)
        receipts[name] = receipt
    identity, source = native["election.json"], native["full-results.json"]
    _, participation = reviewer.nd_results(source, identity)
    county_rows = {}
    for row in participation:
        county = county_rows.setdefault(row["county"], {
            "native_county_id": row["county"], "county_name": row["county_name"],
            "county_identifier_system": "current_portal_location_id",
            "ballots": 0, "precincts": [],
        })
        county["ballots"] += row["ballots"]
        county["precincts"].append({"precinct_id": row["precinct"], "ballots": row["ballots"]})
    observations.append({
        "year": 2026, "election_date": identity["response"]["date"],
        "official": identity["isOfficial"], "source_updated_native": identity["lastUpdated"],
        "source_clock_timezone": "UTC", "source_version": identity["versionID"],
        "ballots": identity["turnout"]["totalBallotsCast"],
        "reported_precincts": len(participation),
        "native_eligible_voters": None, "native_denominator_definition": None,
        "counties": list(county_rows.values()),
    })
    result = compare(observations)
    archive_path = args.historical_cache / "archive.html"
    archive_receipt = json.loads(archive_path.with_suffix(".html.receipt.json").read_text())
    frozen(archive_path, archive_receipt, "https://www.sos.nd.gov/elections/election-results")
    receipts["terminology_and_archive"] = archive_receipt
    result["source_receipts"] = receipts
    with args.output.open("x") as target:
        target.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"counties": len(result["counties"]), **result["statewide"]}))


if __name__ == "__main__":
    main()
