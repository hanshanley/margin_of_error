"""Preserve reconciled 2026 North Dakota counts without inventing a boundary crosswalk."""

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path

import requests

spec = importlib.util.spec_from_file_location("precinct_results", Path(__file__).with_name("build-precinct-results.py"))
results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(results)
PORTAL = "https://resultsnd.sos.nd.gov"
API = "https://api.resultsnd.sos.nd.gov"
SOURCES = {
    "election.json": API + "/Election/GetElectionInfo?cId=north-dakota",
    "configuration.json": API + "/Election/GetElectionConfig?cId=north-dakota&electionID=348",
    "turnout.json": API + "/Turnout/GetTurnout?cId=north-dakota&electionID=348",
    "manifest.json": PORTAL + "/gis/states/north-dakota/manifest.json",
    "counties.json": PORTAL + "/gis/states/north-dakota/counties.json",
    "38001-precincts.json": PORTAL + "/gis/states/north-dakota/counties-precincts/38001-precincts.json",
    "full-results.json": PORTAL + "/results/north-dakota/348/FullDataFile.json",
}


def count(value):
    if type(value) is not int or value < 0:
        raise ValueError("Missing or invalid ND count; do not substitute zero")
    return value


def total_with_bucket(node, field, bucket, bucket_field):
    values = node.get(bucket)
    if not isinstance(values, list) or len(values) != 1 or values[0].get("VoteTypeID") != "1":
        raise ValueError("ND requires one explicit All vote bucket")
    value = count(values[0].get(bucket_field))
    if field in node:
        if count(node[field]) != value:
            raise ValueError("ND total and All bucket do not reconcile")
    elif value != 0:
        raise ValueError("Missing positive ND total")
    return value


def candidate_totals(node):
    if not node.get("Choices") or node.get("WriteinChoices"):
        raise ValueError("Review missing ND candidates or separately named write-ins")
    totals = {}
    for candidate in node["Choices"]:
        name = " ".join(candidate["Name"].split())
        key = (name, candidate["PartyID"])
        if not name or key in totals:
            raise ValueError("Duplicate or unnamed ND candidate")
        totals[key] = total_with_bucket(candidate, "TotalVotes", "Votes", "Votes")
    total = sum(totals.values())
    if ("TotalVotes" in node and count(node["TotalVotes"]) != total) or (
            "TotalVotes" not in node and total != 0):
        raise ValueError("ND candidate and contest totals do not reconcile")
    return totals


def reconcile(parent, children):
    if not children or any(set(child) != set(parent) for child in children):
        raise ValueError("ND candidate identities do not reconcile")
    if any(sum(child[key] for child in children) != value for key, value in parent.items()):
        raise ValueError("ND candidate counts do not reconcile")


def nd_results(source, identity):
    election = identity["response"]
    if (str(source["ElectionData"]["ElectionID"]) != "348"
            or str(identity["electionID"]) != "348" or str(election["id"]) != "348"
            or election["name"] != "2026 General Election"
            or not election["date"].startswith("2026-11-03T")
            or source["ElectionData"]["IsOfficial"] != identity["isOfficial"]):
        raise ValueError("Incorrect ND election identity")
    contests = [node for node in source["ContestData"]
                if node["ContestName"] == "Representative in Congress"]
    if len(contests) != 1 or str(contests[0]["ContestID"]) != "22055":
        raise ValueError("Incorrect or duplicate ND House contest")
    house = contests[0]
    statewide = candidate_totals(house)
    if {party for _, party in statewide} - set(election["parties"]):
        raise ValueError("Unknown ND party")
    turnout = source["TurnoutData"]
    if set(house["Locations"]) != set(turnout["Locations"]):
        raise ValueError("ND candidate/turnout county identities do not reconcile")
    if turnout["TotalBallotsCast"] != identity["turnout"]["totalBallotsCast"]:
        raise ValueError("ND full-file and election-info ballots do not reconcile")
    rows, participation, counties, county_ballots = [], [], [], []
    for county_id, county in house["Locations"].items():
        if county["LocationID"] != county_id or not county_id.startswith("38") or len(county_id) != 5:
            raise ValueError("Incorrect ND parent county identity")
        county_votes = candidate_totals(county)
        county_turnout = turnout["Locations"][county_id]
        if county_turnout["LocationID"] != county_id or (
                set(county["Locations"]) != set(county_turnout["Locations"])):
            raise ValueError("ND precinct candidate/turnout identities do not reconcile")
        precinct_votes, precinct_ballots = [], []
        for precinct_id, precinct in county["Locations"].items():
            if precinct["LocationID"] != precinct_id:
                raise ValueError("Incorrect ND precinct identity")
            votes = candidate_totals(precinct)
            precinct_votes.append(votes)
            ballot_node = county_turnout["Locations"][precinct_id]
            if ballot_node["LocationID"] != precinct_id:
                raise ValueError("Incorrect ND ballot precinct identity")
            ballots = total_with_bucket(ballot_node, "TotalBallotsCast", "BallotsCast", "BallotsCast")
            precinct_ballots.append(ballots)
            totals = [sum(value for (_, party), value in votes.items() if party == code)
                      for code in ["DEM", "REP"]]
            other = sum(value for (_, party), value in votes.items() if party not in {"DEM", "REP"})
            row = results.result(2026, "ND", county_id, precinct_id, "U.S. House",
                *totals, other, "Official unofficial House reporting-unit counts; not participation.",
                SOURCES["full-results.json"])
            rows.append(row)
            participation.append(dict(year=2026, state_code="ND", key=row["key"], county=county_id,
                county_name=county["LocationName"], precinct=precinct_id,
                precinct_name=precinct["LocationName"], ballots=ballots, denominator=None,
                reported_pct=None, candidate_votes_exceed_ballots=row["contest_votes"] > ballots,
                quality="No precinct electorate denominator. Do not reuse county/state voting-age estimates."))
        reconcile(county_votes, precinct_votes)
        county_total = total_with_bucket(county_turnout, "TotalBallotsCast", "BallotsCast", "BallotsCast")
        if sum(precinct_ballots) != county_total:
            raise ValueError("ND precinct/county ballots do not reconcile")
        counties.append(county_votes)
        county_ballots.append(county_total)
    reconcile(statewide, counties)
    if sum(county_ballots) != total_with_bucket(turnout, "TotalBallotsCast", "BallotsCast", "BallotsCast"):
        raise ValueError("ND county/state ballots do not reconcile")
    if (len(rows) != house["TotalPrecincts"] or len(rows) != turnout["TotalPrecincts"]
            or house["PrecinctsReporting"] != len(rows) or turnout["PrecinctsReporting"] != len(rows)):
        raise ValueError("Incomplete ND precinct reporting")
    return rows, participation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an existing ND review or complete archive")
    args.source_cache.mkdir(parents=True, exist_ok=True)
    manifest_path = args.source_cache / "sources.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    captures = {}
    for name, url in SOURCES.items():
        path = args.source_cache / name
        if not path.exists():
            response = requests.get(url, timeout=(15, 120))
            response.raise_for_status()
            response.json()
            path.write_bytes(response.content)
            manifest[name] = dict(url=url, bytes=len(response.content),
                                 sha256=hashlib.sha256(response.content).hexdigest())
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        raw = path.read_bytes()
        if (manifest[name]["url"] != url or manifest[name]["bytes"] != len(raw)
                or manifest[name]["sha256"] != hashlib.sha256(raw).hexdigest()):
            raise ValueError("ND cached original changed: " + name)
        captures[name] = raw
    decoded = {name: json.loads(raw) for name, raw in captures.items()}
    rows, participation = nd_results(decoded["full-results.json"], decoded["election.json"])
    if len(rows) != 358 or len({row["county"] for row in rows}) != 53:
        raise ValueError("ND reporting scope changed; review before publishing")
    if decoded["turnout.json"]["electionID"] != "348" or (
            decoded["turnout.json"]["versionID"] != decoded["election.json"]["versionID"]):
        raise ValueError("ND API source versions differ")
    sample = decoded["38001-precincts.json"]["features"]
    shape_ids = {feature["properties"]["boundary_id"] for feature in sample}
    sample_rows = {row["precinct"] for row in rows if row["county"] == "38001"}
    if shape_ids & sample_rows or len(sample) != 5 or len(sample_rows) != 1:
        raise ValueError("ND sampled boundary identities changed; review classification")
    args.output.mkdir(parents=True)
    originals = args.output / "originals"
    originals.mkdir()
    for name, raw in captures.items():
        (originals / (name + ".gz")).write_bytes(gzip.compress(raw, mtime=0))
    text = io.StringIO()
    writer = csv.DictWriter(text, results.CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (args.output / "results.csv.gz").write_bytes(gzip.compress(text.getvalue().encode(), mtime=0))
    (args.output / "participation.json.gz").write_bytes(gzip.compress(
        json.dumps(participation, separators=(",", ":")).encode(), mtime=0))
    (args.output / "original-source-checksums.json").write_text(json.dumps(
        {name: manifest[name] for name in SOURCES}, indent=2) + "\n")
    audit = dict(year=2026, state_code="ND", candidate_results="acquired_reconciled",
        boundaries="reference_crosswalk_pending", join="withheld", validation="counts_passed_map_withheld",
        publication="full_counts_download_only", participation="acquired_precinct_ballot_counts",
        complete="no", reporting_units=len(rows), counties=53,
        source_url=SOURCES["full-results.json"], sources=SOURCES,
        boundary_source=SOURCES["manifest.json"], boundary_sample_county="38001",
        boundary_features=len(sample), boundary_sample_reporting_units=len(sample_rows),
        boundary_vintage=decoded["manifest.json"]["generated_at"],
        election_version=decoded["election.json"]["versionID"],
        source_updated=decoded["election.json"]["lastUpdated"],
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-precinct-north-dakota-20261105/complete-north-dakota-precinct-source-review.zip",
        candidate_totals={field: sum(row[field] for row in rows) for field in
                          ["democratic_votes", "republican_votes", "other_votes", "contest_votes"]},
        ballots=sum(row["ballots"] for row in participation), rates_withheld=len(participation),
        candidate_ballot_discrepancies=sum(row["candidate_votes_exceed_ballots"] for row in participation),
        notes="All 358 House candidate and ballot rows reconcile to all 53 counties and statewide totals. "
              "Candidate totals are not turnout. Separate precinct ballot counts have no electorate denominator; "
              "all rates are withheld. The official explanatory page defines eligible voters as estimated residents "
              "age 18+, despite the API's registeredVoters field name. The official current-portal GIS manifest is "
              "dated March 2026, but its sampled Adams County file has five split polygons with UUID boundary IDs "
              "for one reporting unit. Only this county was sampled; no statewide boundary review or documented "
              "split-to-reporting-unit crosswalk is claimed. No geometry is mapped and no counts are allocated. "
              "The complete ZIP includes the full all-contest original JSON, normalized House and ballot rows, "
              "the original API captures, GIS manifest, county reference and sampled split boundaries.",
        next_action="Acquire all county-sharded precinct geometry and an official split/reporting-unit crosswalk; "
                    "validate correct-election reporting scopes and polygon unions before mapping. "
                    "Seek precinct electorate denominators separately.")
    (args.output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    checksums = {str(path.relative_to(args.output)): dict(bytes=path.stat().st_size,
                 sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in sorted(args.output.rglob("*")) if path.is_file()}
    (args.output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(args.output)))
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
