"""Reconcile six ND election ballot snapshots without assuming shared precincts."""

import argparse
import hashlib
import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DATES = {
    2016: "November 8, 2016", 2018: "November 6, 2018",
    2020: "November 3, 2020", 2022: "November 8, 2022",
    2024: "November 5, 2024", 2026: "2026-11-03T00:00:00",
}
ELECTION_IDS = {2016: "NT3DecKycoM.", 2018: "bdXDzl1YpEQ.", 2020: "StuhWbgeuSk."}
PRIOR_SHA256 = "d837369711d2f09a91b6db6bfdef4f518d1f39b737cc4000f65c3a6ae9e8a701"


def one(pattern, text):
    found = re.findall(pattern, text, re.S)
    if len(found) != 1:
        raise ValueError("Missing or ambiguous native field")
    return found[0]


def integer(text):
    if not isinstance(text, str) or not re.fullmatch(
            r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)", text):
        raise ValueError("Missing or invalid native count")
    return int(text.replace(",", ""))


def historical(html, year):
    if year not in ELECTION_IDS:
        raise ValueError("Unsupported older election")
    one(rf"<h1><span>Official</span> {year} General Election Results</h1>", html)
    one(rf"<h2>{DATES[year]}</h2>", html)
    controls = {
        key: integer(one(pattern, html)) for key, pattern in {
            "ballots": r"Voter Turnout<span>([^<]*)</span>",
            "eligible": r"Eligible Voters<span>([^<]*)</span>",
            "fully": r"Precincts Fully<span>([^<]*)</span>",
            "total": r"Total Precincts<span>([^<]*)</span>",
            "partial": r"Precincts Partially<span[^>]*>([^<]*)</span>",
        }.items()
    }
    clock = one(r'<div class="last-updated">\s*Results last updated:\s*([^<]+)</div>', html).strip()
    counties, codes = [], set()
    for block in html.split('<div class="turnout-county-data-wrapper">')[1:]:
        href, raw_name = one(r"<a href='([^']+)'>\s*<h1>([^<]+)</h1>", block)
        name = unescape(raw_name).strip()
        parsed = urlsplit(unescape(href))
        query = parse_qs(parsed.query)
        if (parsed.scheme or parsed.netloc or parsed.path != "/ResultsSW.aspx"
                or set(query) != {"type", "map", "cty", "name", "eid"}
                or query["type"] != ["CTYALL"] or query["map"] != ["CTY"]
                or query["name"] != [name] or query["eid"] != [ELECTION_IDS[year]]
                or len(query["cty"]) != 1 or not name):
            raise ValueError("Wrong election or county link identity")
        code = query["cty"][0]
        if not re.fullmatch(r"\d{2}", code) or code in codes:
            raise ValueError("Duplicate or invalid native county ordinal")
        codes.add(code)
        one(rf'<div id="countyturnout{code}" class="section group"', block)
        cells = re.findall(r'<div class="county-(precinct|cast) (?:odd|even)">([^<]*)</div>', block)
        if not cells or len(cells) % 2:
            raise ValueError("Missing named reporting-unit/ballot pair")
        precincts, labels = [], set()
        for offset in range(0, len(cells), 2):
            (kind, raw_label), (value_kind, value) = cells[offset:offset + 2]
            label = unescape(raw_label).strip()
            if kind != "precinct" or value_kind != "cast" or not label or label in labels:
                raise ValueError("Missing, duplicate or unpaired native reporting-unit label")
            labels.add(label)
            precincts.append({"precinct_label": label, "ballots": integer(value)})
        counties.append({
            "county_name": name, "native_county_id": code,
            "county_identifier_system": "legacy_portal_ordinal_not_FIPS",
            "ballots": sum(row["ballots"] for row in precincts), "precincts": precincts,
        })
    if (codes != {f"{number:02}" for number in range(1, 54)}
            or controls["fully"] != controls["total"] or controls["partial"] != 0
            or sum(len(row["precincts"]) for row in counties) != controls["total"]
            or sum(row["ballots"] for row in counties) != controls["ballots"]):
        raise ValueError("Native unit/county/state controls do not reconcile")
    return {
        "year": year, "election_date": DATES[year], "official": True,
        "source_updated_native": clock, "source_clock_timezone": None,
        "ballots": controls["ballots"], "reported_precincts": controls["total"],
        "native_eligible_voters": controls["eligible"],
        "native_denominator_definition": "Source defines eligible voters as estimated residents aged 18+.",
        "counties": counties,
    }


def compare(observations):
    if sorted(row["year"] for row in observations) != list(DATES):
        raise ValueError("Require one observation for each of the six general elections")
    indexed = {}
    for observation in observations:
        year = observation["year"]
        keys = {"year", "election_date", "official", "source_updated_native",
                "source_clock_timezone", "ballots", "reported_precincts",
                "native_eligible_voters", "native_denominator_definition", "counties"}
        if year == 2026:
            keys.add("source_version")
            identity_ok = (
                observation["official"] is False and observation["source_version"] == "v75"
                and observation["source_updated_native"] == "2026-11-05T01:30:08.5674284Z"
                and observation["source_clock_timezone"] == "UTC"
                and observation["native_eligible_voters"] is None
                and observation["native_denominator_definition"] is None)
        else:
            identity_ok = (
                observation["official"] is True and observation["source_clock_timezone"] is None
                and type(observation["native_eligible_voters"]) is int
                and observation["native_eligible_voters"] > 0
                and observation["native_denominator_definition"] ==
                "Source defines eligible voters as estimated residents aged 18+.")
        if (set(observation) != keys or not identity_ok
                or observation["election_date"] != DATES[year]
                or not isinstance(observation["source_updated_native"], str)
                or not observation["source_updated_native"].strip()
                or type(observation["ballots"]) is not int or observation["ballots"] < 0
                or type(observation["reported_precincts"]) is not int):
            raise ValueError("Election scope, source clock, status or denominator changed")
        counties, codes, unit_count = {}, set(), 0
        for county in observation["counties"]:
            code, name = county["native_county_id"], county["county_name"]
            system = ("current_portal_location_id" if year == 2026
                      else "legacy_portal_ordinal_not_FIPS")
            if (set(county) != {"county_name", "native_county_id", "county_identifier_system",
                               "ballots", "precincts"}
                    or not isinstance(name, str) or not name or name != name.strip()
                    or name in counties or not isinstance(code, str) or code in codes
                    or not re.fullmatch(r"\d{5}" if year == 2026 else r"\d{2}", code)
                    or county["county_identifier_system"] != system or not county["precincts"]
                    or type(county["ballots"]) is not int or county["ballots"] < 0):
                raise ValueError("Duplicate, missing or invalid county identity")
            codes.add(code)
            unit_key = "precinct_label" if year in ELECTION_IDS else "precinct_id"
            units, total = set(), 0
            for unit in county["precincts"]:
                identity, value = unit[unit_key], unit["ballots"]
                if (set(unit) != {unit_key, "ballots"} or not isinstance(identity, str)
                        or not identity or identity != identity.strip() or identity in units
                        or type(value) is not int or value < 0
                        or (unit_key == "precinct_id" and not re.fullmatch(r"\d+", identity))
                        or (year in (2022, 2024)
                            and (len(identity) != 6 or not identity.startswith(code)))):
                    raise ValueError("Missing, duplicate, malformed or misplaced native unit")
                units.add(identity)
                total += value
                unit_count += 1
            if total != county["ballots"]:
                raise ValueError("Complete unit observations do not equal county sum")
            counties[name] = county
        if (len(counties) != 53 or sum(row["ballots"] for row in counties.values())
                != observation["ballots"] or unit_count != observation["reported_precincts"]
                or (year != 2026 and codes != {f"{number:02}" for number in range(1, 54)})):
            raise ValueError("Complete county/state/reporting-unit controls changed")
        indexed[year] = counties
    names = set(indexed[2026])
    if any(set(rows) != names for rows in indexed.values()):
        raise ValueError("County names differ; no inferred crosswalk or allocation")

    def counts(values):
        return {
            "ballots_by_year": {str(year): values[year] for year in DATES},
            "reported_count_change_since": {
                str(year): values[2026] - values[year] for year in DATES if year != 2026
            },
            "measured_prior_voter_dropoff": None, "new_or_returning_voters": None,
            "party_switchers": None, "demographic_turnout_rate": None,
        }

    return {
        "status": "observed_ballot_count_change_not_linked_turnout", "state_code": "ND",
        "county_matching": "exact_source_names_not_fixed_people_or_precinct_boundaries",
        "precinct_longitudinal_comparison_qualified": False,
        "individual_transitions_qualified": False, "demographic_turnout_rates_qualified": False,
        "statewide": counts({row["year"]: row["ballots"] for row in observations}),
        "counties": [
            {"county_name": name,
             **counts({year: indexed[year][name]["ballots"] for year in DATES})}
            for name in sorted(names)
        ],
        "source_observations": [
            {key: value for key, value in row.items() if key != "counties"}
            for row in sorted(observations, key=lambda row: row["year"])
        ],
        "limitations": [
            "2026 is the frozen unofficial reported count, not final turnout.",
            "County totals are derived native reporting-unit sums, not independent county controls.",
            "2016/2018/2020 preserve named native units; names do not establish numeric precinct IDs.",
            "County names are matched, not fixed people, precinct boundaries or historical demographics.",
            "Count changes do not identify staying home, returning voters or candidate switching.",
            "Native estimated adult residents are not registration or fixed-cohort denominators.",
        ],
    }


def frozen(path, url):
    raw = path.read_bytes()
    receipt = json.loads(path.with_suffix(".html.receipt.json").read_text())
    if (receipt["url"] != url or receipt["status"] != 200 or receipt["bytes"] != len(raw)
            or receipt["sha256"] != hashlib.sha256(raw).hexdigest()):
        raise ValueError("Native source does not match frozen acquisition receipt")
    return raw.decode("utf-8-sig"), receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--prior-selected", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or ROOT in args.output.resolve().parents:
        raise ValueError("Require a new private output outside the repository")
    raw = args.prior_selected.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PRIOR_SHA256:
        raise ValueError("Previously qualified selected observations changed")
    prior = json.loads(raw)
    observations = prior["observations"]
    receipts = dict(prior["source_receipts"])
    for year, election_id in ELECTION_IDS.items():
        base = f"https://results.sos.nd.gov/Default.aspx?map=Cty&eid={election_id}"
        turnout_url = f"https://results.sos.nd.gov/VoterTurnoutDetails.aspx?eid={election_id}"
        landing, landing_receipt = frozen(args.cache / f"election-{year}.html", base)
        html, receipt = frozen(args.cache / f"turnout-{year}.html", turnout_url)
        if turnout_url.split("/", 3)[-1] not in unescape(landing):
            raise ValueError("Turnout page is not declared by frozen election landing")
        if (receipt["declared_by"]["url"] != base
                or receipt["declared_by"]["sha256"] != landing_receipt["sha256"]
                or landing_receipt["declared_by"]["url"] !=
                "https://www.sos.nd.gov/elections/election-results"
                or landing_receipt["declared_by"]["sha256"] !=
                prior["source_receipts"]["terminology_and_archive"]["sha256"]):
            raise ValueError("Declared-link chain does not match frozen archive")
        observations.append(historical(html, year))
        for kind, native in (("landing", landing_receipt), ("turnout", receipt)):
            receipts[f"{year}-{kind}"] = {
                key: value for key, value in native.items()
                if key in {"url", "final_url", "status", "bytes", "sha256", "acquired_at", "declared_by"}
            }
    result = compare(observations)
    result.update(observations=sorted(observations, key=lambda row: row["year"]),
                  source_receipts=receipts, prior_selected_sha256=PRIOR_SHA256)
    with args.output.open("x") as target:
        args.output.chmod(0o600)
        target.write(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"counties": len(result["counties"]), **result["statewide"]}))


if __name__ == "__main__":
    main()
