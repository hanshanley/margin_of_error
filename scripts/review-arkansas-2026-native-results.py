"""Reconcile complete native Arkansas exports without filling omitted counts."""

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import zipfile


ELECTION = "11b07106-031e-4d7c-911a-d01fb473d6dd"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def count(value):
    require(type(value) is int and value >= 0, "Invalid native count")
    return value


def optional_count(node, field):
    return count(node[field]) if field in node else None


def vector(node, modes):
    require(node.get("Choices") and not node.get("WriteinChoices"),
            "Unreviewed empty candidates or separate named write-ins")
    result = {}
    for candidate in node["Choices"]:
        identity = candidate["ChoiceID"]
        require(identity and identity not in result, "Duplicate native candidate identity")
        observed_modes = {}
        for mode in candidate["Votes"]:
            key = mode["VoteTypeID"]
            require(key in modes and key not in observed_modes, "Duplicate or unknown vote mode")
            observed_modes[key] = count(mode["Votes"])
        require(set(observed_modes) == set(modes), "Incomplete native voting modes")
        total = optional_count(candidate, "TotalVotes")
        require((total is not None and sum(observed_modes.values()) == total)
                or (total is None and not any(observed_modes.values())),
                "Native candidate/mode total conflict")
        result[identity] = dict(name=candidate["Name"], party_id=candidate["PartyID"],
                                votes=total, modes=observed_modes)
    total = optional_count(node, "TotalVotes")
    values = [candidate["votes"] for candidate in result.values()]
    require((total is None and all(value is None for value in values))
            or (total is not None and sum(v for v in values if v is not None) == total),
            "Native candidate/contest total conflict")
    return result


def residuals(parent, children):
    require(children and all(set(child) == set(parent) for child in children),
            "Incomplete native child candidate identities")
    residual = {}
    for identity, candidate in parent.items():
        require(all((child[identity]["name"], child[identity]["party_id"])
                    == (candidate["name"], candidate["party_id"]) for child in children),
                "Conflicting native candidate description")
        expected = candidate["votes"]
        actual = sum(child[identity]["votes"] for child in children
                     if child[identity]["votes"] is not None)
        residual[identity] = dict(total=None if expected is None else expected - actual,
            modes={mode: votes - sum(child[identity]["modes"][mode] for child in children)
                   for mode, votes in candidate["modes"].items()})
    return residual


def complete(residual):
    return all(value["total"] in (None, 0) and not any(value["modes"].values())
               for value in residual.values())


def csv_signature(contest, county, node, candidate, modes):
    # Native CSV serializes omitted numeric totals as zero; retain that distinction elsewhere.
    by_mode = {mode["VoteTypeID"]: count(mode["Votes"]) for mode in candidate["Votes"]}
    name = node["LocationName"]
    if node is not county:
        name = county["LocationName"] + " - " + name
    return (contest["ContestID"], contest["ContestName"], node["LocationID"], name,
            candidate["ChoiceID"], candidate["Name"], candidate["PartyID"],
            str(optional_count(candidate, "TotalVotes") or 0),
            str(optional_count(node, "TotalVotes") or 0),
            *(str(by_mode[mode]) for mode in modes))


def compare_csv(data, text, modes):
    expected = Counter()
    omitted = 0
    for contest in data["ContestData"]:
        for county in contest["Locations"].values():
            for node in [county, *county.get("Locations", {}).values()]:
                require(not node.get("WriteinChoices"), "Review separately named write-ins")
                for candidate in node["Choices"]:
                    expected[csv_signature(contest, county, node, candidate, modes)] += 1
                    omitted += "TotalVotes" not in candidate
    columns = ["Contest ID", "Contest Name", "Location ID", "Location Name", "Candidate ID",
               "Candidate Name", "Party ID", "Candidate Votes", "Total Votes", *modes.values()]
    reader = csv.DictReader(io.StringIO(text))
    require(reader.fieldnames and set(columns) <= set(reader.fieldnames),
            "Incomplete native CSV header")
    actual = Counter(tuple(row[column] for column in columns) for row in reader)
    require(actual == expected, "Native full CSV/JSON candidate or mode conflict")
    return dict(candidate_cells=sum(actual.values()), csv_json_match=True,
                json_omitted_candidate_totals=omitted,
                csv_zero_serialization_does_not_fill_json=True)


def compare_api(data, identity, turnout, federal):
    for snapshot in [turnout, federal]:
        require(snapshot["electionID"] == ELECTION
                and snapshot["versionID"] == identity["versionID"]
                and snapshot["isOfficial"] is False, "Native API version or election conflict")
    for native, observed in [(data["TurnoutData"], turnout["response"]),
            *((data["TurnoutData"]["Locations"][key], node)
              for key, node in turnout["response"]["locations"].items())]:
        for field in ["TotalBallotsCast", "RegisteredVoters", "TotalPrecincts"]:
            require(count(native[field]) == count(observed[field[0].lower() + field[1:]]),
                    "Native full-file/API ballot or registration conflict")
    require(set(data["TurnoutData"]["Locations"]) == set(turnout["response"]["locations"]),
            "Native full-file/API county scope conflict")
    full_contests = {contest["ContestID"]: contest for contest in data["ContestData"]}
    cells = 0
    for contest_id, observed in federal["response"]["contests"].items():
        require(contest_id in full_contests and observed["contestID"] == contest_id,
                "Unknown native federal contest")
        native = full_contests[contest_id]
        require(set(native["Locations"]) == set(observed["locations"]),
                "Native full-file/API federal county scope conflict")
        for full, api in [(native, observed),
                *((native["Locations"][key], node) for key, node in observed["locations"].items())]:
            require(count(full["TotalVotes"]) == count(api["totalVotes"]),
                    "Native full-file/API contest total conflict")
            choices = api["choices"]
            if isinstance(choices, dict):
                choices = list(choices.values())
            expected = {choice["ChoiceID"]: choice for choice in full["Choices"]}
            require(len(choices) == len(expected)
                    and {choice["choiceID"] for choice in choices} == set(expected),
                    "Native full-file/API candidate identity conflict")
            for choice in choices:
                original = expected[choice["choiceID"]]
                require(original["PartyID"] == choice["partyID"]
                        and count(choice["totalVotes"]) == (optional_count(original, "TotalVotes") or 0),
                        "Native full-file/API candidate count conflict")
                cells += 1
    require(len(federal["response"]["contests"]) == 5, "Incomplete native federal API scope")
    return dict(version=identity["versionID"],
                county_ballot_scopes=len(turnout["response"]["locations"]),
                federal_contests=5, federal_summary_candidate_cells=cells,
                full_file_api_counts_match=True)


def review(data, identity):
    election = identity["response"]
    require(identity["electionID"] == election["id"] == data["ElectionData"]["ElectionID"] == ELECTION
            and election["date"] == "2026-11-03T00:00:00"
            and election["name"] == "2026 General Election & Judical Runoff"
            and data["ElectionData"]["IsOfficial"] is identity["isOfficial"] is False,
            "Wrong native general-election identity")
    require(len({contest["ContestID"] for contest in data["ContestData"]})
            == len(data["ContestData"]), "Duplicate native contest identity")
    parties = election["parties"]
    modes = {key: value["description"] for key, value in election["voteTypes"].items()
             if value["description"] in {"Absentee", "Early Voting", "Election Day"}}
    require(set(modes.values()) == {"Absentee", "Early Voting", "Election Day"}
            and len(modes) == 3, "Unreviewed native vote modes")
    turnout = data["TurnoutData"]
    require(count(turnout["TotalBallotsCast"]) == count(identity["turnout"]["totalBallotsCast"])
            and set(turnout["Locations"]) == set(election["locations"]),
            "Native election/turnout scope conflict")
    participation, county_ballots, all_precincts = [], [], set()
    for county_id, county in turnout["Locations"].items():
        native = election["locations"][county_id]
        require(re.fullmatch(r"05[0-9]{3}", county_id)
                and native["locationID"] == county["LocationID"] == county_id
                and set(county["Locations"]) == set(native["locations"]),
                "Native turnout county or precinct identity conflict")
        observed = []
        for precinct_id, node in county["Locations"].items():
            label = native["locations"][precinct_id]
            require(node["LocationID"] == label["locationID"] == precinct_id,
                    "Native turnout leaf identity conflict")
            identity_key = (county_id, precinct_id)
            require(identity_key not in all_precincts, "Duplicate county-qualified precinct")
            all_precincts.add(identity_key)
            ballots = optional_count(node, "TotalBallotsCast")
            bucket = node["BallotsCast"]
            require(len(bucket) == 1
                    and election["voteTypes"][bucket[0]["VoteTypeID"]]["description"] == "TV - Total Votes"
                    and (ballots == count(bucket[0]["BallotsCast"]) if ballots is not None
                         else count(bucket[0]["BallotsCast"]) == 0),
                    "Native turnout bucket conflict")
            if ballots is not None:
                observed.append(ballots)
            participation.append(dict(year=2026, state_code="AR", county_code=county_id,
                county=native["locationName"], precinct_code=precinct_id,
                precinct=label["locationName"], ballots=ballots,
                registered_voters=optional_count(node, "RegisteredVoters"),
                native_reported_pct=node.get("VotePercent"), turnout_rate=None,
                missing_total_preserved=ballots is None,
                quality="Unofficial native counts; electorate definition unreviewed; no inferred rate."))
        total = count(county["TotalBallotsCast"])
        require(sum(observed) == total, "Native precinct/county ballot residual")
        county_ballots.append(total)
    require(sum(county_ballots) == count(turnout["TotalBallotsCast"])
            and len(all_precincts) == count(turnout["TotalPrecincts"]),
            "Native county/state ballot or precinct-count conflict")
    rows, scopes, house = [], [], []
    selected = [c for c in data["ContestData"]
                if re.fullmatch(r"U\.S\. Congress District 0[1-4]", c["ContestName"])]
    require(len(selected) == 4 and len({c["ContestName"] for c in selected}) == 4,
            "Missing or duplicate native House contests")
    for contest in selected:
        parent = vector(contest, modes)
        counties = []
        for county_id, county in contest["Locations"].items():
            require(county_id in election["locations"] and county["LocationID"] == county_id
                    and county["LocationName"] == election["locations"][county_id]["locationName"],
                    "Native House county identity conflict")
            county_vector = vector(county, modes)
            counties.append(county_vector)
            precinct_vectors = []
            for precinct_id, node in county["Locations"].items():
                require((county_id, precinct_id) in all_precincts
                        and node["LocationID"] == precinct_id
                        and node["LocationName"]
                        == election["locations"][county_id]["locations"][precinct_id]["locationName"],
                        "Unmatched native House precinct identity")
                candidates = vector(node, modes)
                precinct_vectors.append(candidates)
                totals = {}
                for party_name in ["Democratic", "Republican", "Other"]:
                    group = []
                    for candidate in candidates.values():
                        require(candidate["party_id"] in parties, "Unknown native party")
                        party = parties[candidate["party_id"]]["partyName"]
                        if party not in {"Democratic", "Republican"}:
                            party = "Other"
                        if party == party_name:
                            group.append(candidate["votes"])
                    totals[party_name] = (None if any(v is None for v in group)
                                          else sum(group))
                total = optional_count(node, "TotalVotes")
                fully_observed = total is not None and all(v["votes"] is not None
                                                           for v in candidates.values())
                rows.append(dict(year=2026, state_code="AR", county_code=county_id,
                    county=county["LocationName"], precinct_code=precinct_id,
                    precinct=node["LocationName"], contest_id=contest["ContestID"],
                    office=contest["ContestName"], total_votes=total,
                    democratic_votes=totals["Democratic"], republican_votes=totals["Republican"],
                    other_votes=totals["Other"],
                    margin_pp=100 * (totals["Democratic"] - totals["Republican"]) / total
                    if fully_observed and total else None,
                    candidates=json.dumps(candidates, separators=(",", ":"), ensure_ascii=True),
                    maps_approved=False, turnout_rate=None,
                    quality="Native reporting-unit vector; no geometry or residential allocation approved."))
            residual = residuals(county_vector, precinct_vectors)
            require(complete(residual), "Native precinct/county candidate or mode residual")
            scopes.append(dict(contest_id=contest["ContestID"], county_code=county_id,
                               precinct_vectors=len(precinct_vectors), residuals=residual))
        require(complete(residuals(parent, counties)), "Native county/state candidate or mode residual")
        house.append(dict(contest_id=contest["ContestID"], office=contest["ContestName"],
                          total_votes=count(contest["TotalVotes"]), candidates=parent))
    return rows, participation, dict(year=2026, state_code="AR", complete="no",
        maps_approved=False, rates_available=False, unofficial=True,
        all_native_contests=len(data["ContestData"]), native_counties=len(county_ballots),
        precinct_house_vectors=len(rows), native_precinct_identities=len(all_precincts),
        observed_house_vectors=sum(row["total_votes"] is not None for row in rows),
        omitted_house_vector_totals=sum(row["total_votes"] is None for row in rows),
        turnout_observations=len(participation),
        omitted_native_ballot_totals=sum(row["ballots"] is None for row in participation),
        native_ballots=count(turnout["TotalBallotsCast"]),
        all_house_candidate_and_mode_scopes_reconcile=True,
        all_observed_ballot_scopes_reconcile=True, house=house, county_house_scopes=scopes), modes


def build(source, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing to overwrite an existing package")
    sources = json.loads((source / "sources.json").read_text())
    require({p.stem for p in (source / "originals").glob("*.gz")} == set(sources),
            "Missing or unreceipted original")
    payloads = {}
    for key, receipt in sources.items():
        body = gzip.decompress((source / "originals" / (key + ".gz")).read_bytes())
        require(len(body) == receipt["bytes"]
                and hashlib.sha256(body).hexdigest() == receipt["sha256"],
                "Native original receipt conflict")
        payloads[key] = body
    identities = [json.loads(body) for key, body in payloads.items()
                  if "/Election/GetElectionInfo?" in sources[key]["url"]]
    require(len(identities) == 1, "Missing or ambiguous native election identity response")
    data = json.loads(payloads["official-full-election-json"])
    rows, participation, audit, modes = review(data, identities[0])
    turnout = [json.loads(body) for key, body in payloads.items()
               if "/Turnout/GetTurnout?" in sources[key]["url"]]
    federal = [json.loads(body) for key, body in payloads.items()
               if "/Contest/GetContestResults?" in sources[key]["url"]]
    require(len(turnout) == len(federal) == 1, "Missing or ambiguous independent API snapshots")
    audit["api_review"] = compare_api(data, identities[0], turnout[0], federal[0])
    audit["csv_review"] = compare_csv(data, payloads["official-full-election-csv"].decode("utf-8-sig"), modes)
    require(audit["native_counties"] == 75 and audit["native_precinct_identities"] == 2768
            and audit["precinct_house_vectors"] == 2769
            and audit["csv_review"]["candidate_cells"] == 106922,
            "Native snapshot scope changed; review before publication")
    output.mkdir(parents=True)
    # Keep factual originals and agency declarations, not the app's frontend document/configuration.
    selected = {key: receipt for key, receipt in sources.items()
                if key == "official-election-results-index" or key.startswith("official-full-election-")
                or "/Election/" in receipt["url"] or "/Turnout/" in receipt["url"]
                or "/Contest/" in receipt["url"] or "gis.tally-enr.com/" in receipt["url"]}
    originals = output / "native-source/originals"
    originals.mkdir(parents=True)
    for key in selected:
        shutil.copyfile(source / "originals" / (key + ".gz"), originals / (key + ".gz"))
    (output / "native-source/sources.json").write_text(json.dumps(selected, indent=2) + "\n")
    shutil.copyfile(Path(__file__), output / Path(__file__).name)
    for name, records in [("precinct-counts.csv", rows), ("precinct-participation.csv", participation)]:
        with (output / name).open("w") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    (output / "counts-review.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "checksums.json").write_text(json.dumps({
        path.relative_to(output).as_posix(): dict(bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(output.rglob("*")) if path.is_file()
    }, separators=(",", ":")) + "\n")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as target:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                member = zipfile.ZipInfo(path.relative_to(output).as_posix())
                member.external_attr = 0o644 << 16
                target.writestr(member, path.read_bytes())
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["source", "output", "archive"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source, args.output, args.archive)
    print(json.dumps({key: value for key, value in result.items()
                      if key not in {"house", "county_house_scopes"}}, indent=2))
