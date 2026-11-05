"""Reconcile native Arizona counts; never turn candidate votes into participation."""

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


COUNTIES = {
    "01": "Apache County", "02": "Cochise County", "03": "Coconino County",
    "04": "Gila County", "05": "Graham County", "06": "Greenlee County",
    "07": "La Paz County", "maricopa": "Maricopa County", "09": "Mohave County",
    "10": "Navajo County", "pima": "Pima County", "12": "Pinal County",
    "13": "Santa Cruz County", "14": "Yavapai County", "15": "Yuma County",
}
MODES = {"Election Day", "Early Voting", "Provisional", "Early A.R.S. 16-579", "Late Early*"}
HOUSE = {f"AZ-{n}": f"U.S. Representative in Congress - District No. {n}" for n in range(1, 10)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def count(value):
    require(type(value) is int and value >= 0, "Missing or invalid native integer count")
    return value


def english(values):
    matches = [entry["text"] for entry in values if entry.get("languageId") == "en"]
    require(len(matches) == 1 and isinstance(matches[0], str) and matches[0],
            "Missing or ambiguous source-declared English label")
    return matches[0]


def indexed(nodes, key="id"):
    result = {}
    for node in nodes:
        identity = node.get(key)
        require(isinstance(identity, str) and identity and identity not in result,
                "Missing or duplicate native identity")
        result[identity] = node
    require(result, "Missing native collection")
    return result


def mode_vector(node):
    modes = indexed(node["groupResults"], "groupName")
    require(set(modes) == MODES, "Incomplete or unknown native voting modes")
    for group in modes.values():
        count(group.get("voteCount"))
        require(type(group.get("isFromVirtualPrecinct")) is bool,
                "Missing native virtual-mode flag")
    require(sum(group["voteCount"] for group in modes.values()) == count(node.get("voteCount")),
            "Native candidate/mode count residual")
    return {name: dict(votes=group["voteCount"], virtual=group["isFromVirtualPrecinct"])
            for name, group in sorted(modes.items())}


def contest_options(contest):
    require(contest["type"] == "State" and contest["contestType"] in {"Candidate", "BallotMeasure"}
            and contest["rankedChoiceResults"] is None
            and type(contest["voteFor"]) is int and contest["voteFor"] > 0
            and isinstance(contest["name"], str) and contest["name"],
            "Unreviewed native contest scope or ranked-choice format")
    options = indexed(contest["ballotOptions"])
    for option in options.values():
        require(isinstance(option.get("name"), str) and option["name"]
                and (option.get("politicalParty") is None
                     or isinstance(option["politicalParty"], str) and option["politicalParty"]),
                "Missing literal option identity or invalid party")
        mode_vector(option)
    return options


def review_native(data, party_aliases):
    require(data["electionDate"] == "2026-11-03" and data["electionName"] == "2026 General Election"
            and data["results"]["name"] == "Arizona"
            and data["results"]["id"] == "01000000-0496-9e5d-0291-08dbda35db79",
            "Wrong native Arizona general-election identity")
    counties = indexed(data["localResults"])
    require({key: node["name"] for key, node in counties.items()} == COUNTIES,
            "Incomplete or conflicting native county inventory; native codes are not FIPS")
    statewide = indexed(data["results"]["ballotItems"])
    require({key: statewide[key]["name"] for key in HOUSE if key in statewide} == HOUSE,
            "Missing or conflicting native House inventory")
    parents = {key: contest_options(contest) for key, contest in statewide.items()}
    totals, mode_totals = Counter(), Counter()
    all_rows, house_rows, descriptions, scopes = [], [], [], []
    identities, house_identities = {}, Counter()

    def row(level, county_id, precinct_id, precinct, contest, option, parent, virtual=None, status=None):
        require(option["name"] == parent["name"], "Conflicting literal native option name")
        canonical_party = parent["politicalParty"]
        native_party = option["politicalParty"]
        canonical_group = canonical_party if canonical_party in {"Democratic", "Republican"} else "Other"
        local_group = party_aliases.get(native_party, "Other")
        require(local_group == canonical_group, "Conflicting native Democratic/Republican party identity")
        modes = mode_vector(option)
        record = dict(year=2026, state_code="AZ", level=level, county_code=county_id,
            county=COUNTIES.get(county_id), precinct_code=precinct_id, precinct=precinct,
            contest_id=contest["id"], office=contest["name"], contest_type=contest["contestType"],
            vote_for=contest["voteFor"], option_id=option["id"], option_name=option["name"],
            native_party=native_party, state_declared_party=canonical_party,
            votes=count(option.get("voteCount")), native_virtual_precinct=virtual,
            native_reporting_status=status,
            voting_modes=json.dumps(modes, separators=(",", ":"), ensure_ascii=True))
        all_rows.append(record)
        return record

    for key, contest in statewide.items():
        for option in parents[key].values():
            require(option["precinctResults"] is None, "Unexpected statewide precinct duplication")
            row("state", None, None, None, contest, option, option)
    for county_id, county in counties.items():
        for key, contest in indexed(county["ballotItems"]).items():
            require(key in statewide and contest["name"] == statewide[key]["name"]
                    and contest["voteFor"] == statewide[key]["voteFor"]
                    and contest["contestType"] == statewide[key]["contestType"],
                    "Unmatched native county contest")
            options = contest_options(contest)
            require(set(options) == set(parents[key]), "Incomplete native county option inventory")
            leaf_inventory, candidate_vectors = None, {}
            for option_id, option in options.items():
                parent = parents[key][option_id]
                row("county", county_id, None, None, contest, option, parent)
                if option["politicalParty"] != parent["politicalParty"]:
                    descriptions.append(dict(county_code=county_id, contest_id=key, option_id=option_id,
                        native_party=option["politicalParty"], state_party=parent["politicalParty"]))
                totals[key, option_id] += option["voteCount"]
                for mode, value in mode_vector(option).items():
                    mode_totals[key, option_id, mode] += value["votes"]
                leaves = indexed(option["precinctResults"])
                require(leaf_inventory is None or set(leaves) == leaf_inventory,
                        "Incomplete native precinct candidate inventory")
                leaf_inventory = set(leaves)
                leaf_modes = {identity: mode_vector(leaf) for identity, leaf in leaves.items()}
                require(sum(count(leaf.get("voteCount")) for leaf in leaves.values()) == option["voteCount"],
                        "Native precinct/county candidate residual")
                for mode, value in mode_vector(option).items():
                    require(sum(values[mode]["votes"] for values in leaf_modes.values())
                            == value["votes"], "Native precinct/county mode residual")
                for precinct_id, leaf in leaves.items():
                    require(type(leaf.get("isVirtual")) is bool
                            and isinstance(leaf.get("name"), str) and leaf["name"]
                            and isinstance(leaf.get("reportingStatus"), str) and leaf["reportingStatus"],
                            "Missing native precinct scope or status")
                    identity = (county_id, precinct_id)
                    description = (leaf["name"], leaf["isVirtual"])
                    require(identity not in identities or identities[identity] == description,
                            "Conflicting county-qualified precinct identity")
                    identities[identity] = description
                    record = row("precinct", county_id, precinct_id, leaf["name"], contest,
                                 dict(option, voteCount=leaf["voteCount"], groupResults=leaf["groupResults"]),
                                 parent, leaf["isVirtual"], leaf["reportingStatus"])
                    candidate_vectors.setdefault(precinct_id, []).append(record)
            scopes.append(dict(county_code=county_id, contest_id=key, precincts=len(candidate_vectors),
                               precincts_reporting=contest["precinctsReporting"],
                               precincts_participating=contest["precinctsParticipating"]))
            if key in HOUSE:
                for precinct_id, vector in candidate_vectors.items():
                    require(len({record["native_reporting_status"] for record in vector}) == 1,
                            "Conflicting native precinct reporting status")
                    by_party = Counter()
                    for record in vector:
                        party = record["state_declared_party"]
                        by_party[party if party in {"Democratic", "Republican"} else "Other"] += record["votes"]
                    total = sum(by_party.values())
                    house_identities[county_id, precinct_id] += 1
                    house_rows.append(dict(year=2026, state_code="AZ", county_code=county_id,
                        county=county["name"], precinct_code=precinct_id, precinct=vector[0]["precinct"],
                        contest_id=key, office=contest["name"], total_votes=total,
                        democratic_votes=by_party["Democratic"], republican_votes=by_party["Republican"],
                        other_votes=by_party["Other"],
                        margin_pp=100 * (by_party["Democratic"] - by_party["Republican"]) / total if total else None,
                        native_virtual_precinct=vector[0]["native_virtual_precinct"],
                        native_reporting_status=vector[0]["native_reporting_status"],
                        candidates=json.dumps(vector, separators=(",", ":"), ensure_ascii=True),
                        maps_approved=False, turnout_rate=None))
    for key, options in parents.items():
        for option_id, option in options.items():
            require(totals[key, option_id] == option["voteCount"], "Native county/state candidate residual")
            require(all(mode_totals[key, option_id, mode] == value["votes"]
                        for mode, value in mode_vector(option).items()),
                    "Native county/state mode residual")
    require(set(house_identities) == set(identities), "Native House coverage omits observed precinct identities")
    return house_rows, all_rows, dict(
        year=2026, state_code="AZ", complete="no", maps_approved=False, rates_available=False,
        native_created_at=data["createdAt"], native_counties=len(counties),
        statewide_contests=len(statewide), county_contests=len(scopes),
        precinct_house_vectors=len(house_rows), native_precinct_identities=len(identities),
        precinct_option_rows=sum(record["level"] == "precinct" for record in all_rows),
        all_native_option_rows=len(all_rows), all_candidate_and_mode_scopes_reconcile=True,
        virtual_precincts=sum(value[1] for value in identities.values()),
        split_house_identities=[dict(county_code=key[0], precinct_code=key[1], house_scopes=value)
                                for key, value in sorted(house_identities.items()) if value > 1],
        native_party_description_differences=descriptions, county_contest_scopes=scopes,
        native_ids_are_not_fips=True, candidate_counts_are_not_ballots=True)


def api_count(value):
    require(type(value) in {int, float} and value >= 0 and int(value) == value,
            "Missing or nonintegral native API count")
    return int(value)


def uuid_key(value):
    require(isinstance(value, str) and re.fullmatch(
        r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value),
        "Invalid source-declared UUID")
    return value.lower()


def uuid_index(nodes):
    result = {}
    for node in nodes:
        key = uuid_key(node["id"])
        require(key not in result, "Duplicate source-declared UUID")
        result[key] = node
    require(result, "Missing native UUID collection")
    return result


def api_identity(api):
    election = api["election"]
    require(election["electionDate"] == "2026-11-03" and election["isPrimary"] is False
            and election["isProduction"] is True and election["isOfficialResults"] is False
            and english(election["name"]) == "2026 General Election"
            and uuid_key(election["jurisdictionId"]) == uuid_key(api["jurisdiction"]["id"]),
            "Wrong native API election or production identity")


def party_aliases(api):
    aliases = {}
    for party in api["election"]["parties"]:
        name = english(party["name"])
        if name in {"Democratic", "Republican"}:
            for label in [name, party["abbreviation"]]:
                require(label and (label not in aliases or aliases[label] == name),
                        "Conflicting source-declared party abbreviation")
                aliases[label] = name
    require(set(aliases.values()) == {"Democratic", "Republican"}, "Missing native major-party declaration")
    return aliases


def compare_scope(native, api, county_code=None):
    expected = indexed(native)
    observed = {}
    for contest in api:
        label = english(contest["name"])
        require(label not in observed, "Ambiguous literal API contest name")
        observed[label] = contest
    require(set(observed) == {contest["name"] for contest in expected.values()},
            "Full export/API contest inventory conflict")
    correspondence = []
    for contest in expected.values():
        other = observed[contest["name"]]
        key_field = "name" if county_code else "id"
        options = indexed(contest["ballotOptions"], key_field)
        entries = other["summaryResults"]["ballotOptions"]
        indexed(entries, "nativeId")
        choices = indexed([dict(entry, literal_name=english(entry["name"])) for entry in entries],
                          "literal_name" if county_code else "nativeId")
        require(set(choices) == set(options), "Full export/API option identity conflict")
        require(count(other["voteTotal"]) == sum(option["voteCount"] for option in options.values()),
                "Full export/API contest count residual")
        for key, option in options.items():
            choice = choices[key]
            require(english(choice["name"]) == option["name"]
                    and count(choice.get("voteCount")) == option["voteCount"],
                    "Full export/API literal candidate or count conflict")
            modes = {}
            for mode in choice["groupResults"]:
                name = english(mode["groupName"])
                require(name not in modes, "Duplicate native API voting mode")
                modes[name] = count(mode.get("voteCount"))
            require(modes == {key: value["votes"] for key, value in mode_vector(option).items()},
                    "Full export/API voting-mode count conflict")
            uuid_key(choice["id"])
            correspondence.append(dict(county_code=county_code, contest_id=contest["id"],
                option_name=option["name"], media_option_id=option["id"],
                api_native_option_id=choice["nativeId"], api_option_uuid=choice["id"],
                comparison="unique literal county/contest/option names and equal count/modes"
                    if county_code else "exact declared native option ID and equal literal name/count/modes",
                certifies_shared_id_namespace=False if county_code else True))
    return correspondence


def review_api(data, root, local_apis):
    api_identity(root)
    require(english(root["jurisdiction"]["name"]) == "Arizona"
            and root["jurisdiction"]["id"] == data["results"]["id"]
            and root["jurisdiction"]["mediaExportPath"] == "Arizona/export-110326GeneralElection.json",
            "Native application does not declare the actual acquired media export")
    comparisons = compare_scope(data["results"]["ballotItems"], root["ballotItems"])
    children = uuid_index(root["jurisdiction"]["childLocalities"])
    declarations = uuid_index(root["localityElections"])
    declarations = {uuid_key(node["jurisdictionId"]): node for node in declarations.values()}
    require(len(declarations) == len(children), "Duplicate native county election scope")
    registrations = uuid_index(root["voterRegistration"])
    require(set(children) == set(declarations) == set(registrations),
            "Native county declaration/registration inventory conflict")
    by_name = {english(node["name"]): (key, node) for key, node in children.items()}
    require(len(by_name) == len(children) and set(by_name) == set(COUNTIES.values())
            and set(local_apis) == set(by_name), "Incomplete literal county API inventory")
    participation, county_rows = [], []
    raw_counties = indexed(data["localResults"])
    for code, name in COUNTIES.items():
        key, child = by_name[name]
        api = local_apis[name]
        api_identity(api)
        require(uuid_key(api["jurisdiction"]["id"]) == key
                and english(api["jurisdiction"]["name"]) == name
                and english(registrations[key]["localityName"]) == name,
                "Conflicting native API county identity")
        comparisons.extend(compare_scope(raw_counties[code]["ballotItems"], api["ballotItems"], code))
        declaration = declarations[key]
        ballots = api_count(api["election"]["ballotsCast"])
        registered = api_count(api["election"]["totalVoters"])
        require(ballots == api_count(declaration["ballotsCast"])
                and registered == api_count(declaration["totalVoters"])
                == count(registrations[key]["total"]), "Native county/API participation conflict")
        precincts = uuid_index(api["precincts"])
        turnout = uuid_index(api["voterTurnout"])
        require(set(turnout) <= set(precincts), "Unmatched native participation UUID")
        observed_ballots, observed_registered = [], []
        for identity, precinct in precincts.items():
            label = english(precinct["name"])
            require(type(precinct["isVirtual"]) is bool, "Missing native precinct virtual flag")
            node = turnout.get(identity)
            if node is not None:
                require(node["precinctName"] == label, "Native precinct/turnout label conflict")
                cast = api_count(node["ballotsCast"])
                native_turnout = api_count(node["voterTurnout"])
                voters = count(node["voterRegistration"])
                require(native_turnout == cast, "Native turnout count differs from ballots; not a rate")
                observed_ballots.append(cast)
                observed_registered.append(voters)
            else:
                cast = voters = native_turnout = None
            participation.append(dict(year=2026, state_code="AZ", county_code=code, county=name,
                native_county_uuid=api["jurisdiction"]["id"], precinct_code=precinct["id"],
                precinct=label, ballots=cast, registered_voters=voters,
                native_voter_turnout_count=native_turnout,
                native_virtual_precinct=precinct["isVirtual"],
                native_reporting_status=precinct["reportingStatus"],
                native_observation_present=node is not None, turnout_rate=None,
                quality="Native administrative counts; no inferred rate, candidate-ID or geometry join."))
        require(sum(observed_ballots) == ballots and sum(observed_registered) == registered,
                "Native precinct/county ballot or registration residual")
        county_rows.append(dict(year=2026, state_code="AZ", county_code=code, county=name,
            native_county_uuid=api["jurisdiction"]["id"], ballots=ballots, registered_voters=registered,
            native_active_voters=count(registrations[key]["activeVoters"]),
            native_inactive_voters=count(registrations[key]["inactiveVoters"]),
            native_reported_fraction=child["turnoutPercent"], turnout_rate=None))
    require(sum(row["registered_voters"] for row in county_rows)
            == api_count(root["election"]["totalVoters"]), "Native county/state registration residual")
    return participation, county_rows, dict(
        native_publish_version=root["election"]["publishVersionId"],
        full_file_api_candidate_cells=len(comparisons), all_api_candidate_and_mode_scopes_match=True,
        api_option_correspondence=comparisons,
        native_api_precincts=len(participation),
        native_participation_observations=sum(row["native_observation_present"] for row in participation),
        missing_participation_rows=[row for row in participation if not row["native_observation_present"]],
        observed_county_ballot_sum=sum(row["ballots"] for row in county_rows),
        native_county_registration_sum=sum(row["registered_voters"] for row in county_rows),
        native_state_ballot_field=api_count(root["election"]["ballotsCast"]),
        native_state_ballot_field_matches_counties=api_count(root["election"]["ballotsCast"])
            == sum(row["ballots"] for row in county_rows),
        native_registration_components_match_totals=all(
            row["native_active_voters"] + row["native_inactive_voters"] == row["registered_voters"]
            for row in county_rows),
        all_observed_precinct_county_participation_scopes_reconcile=True,
        candidate_and_participation_id_namespaces_not_joined=True, rates_approved=False)


def build(source, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing to overwrite an existing package")
    sources = json.loads((source / "sources.json").read_text())
    require({path.stem for path in (source / "originals").glob("*.gz")} == set(sources),
            "Missing or unreceipted acquisition original")
    payloads = {}
    for key, receipt in sources.items():
        path = source / receipt["file"]
        require(path == source / "originals" / (key + ".gz"), "Unexpected original source path")
        body = gzip.decompress(path.read_bytes())
        require(len(body) == receipt["bytes"]
                and hashlib.sha256(body).hexdigest() == receipt["sha256"],
                "Native original receipt conflict")
        if key == "official-full-election-json" or key.startswith("native-public-response-"):
            require(receipt["status"] == 200, "Native data original not successfully acquired")
            payloads[key] = body
    data = json.loads(payloads["official-full-election-json"])
    versions, apis = {}, {}
    for key, body in payloads.items():
        url = sources[key]["url"]
        if not url.endswith("/data"):
            continue
        require(url not in versions or versions[url] == body, "Native app changed between county captures")
        versions[url] = body
        api = json.loads(body)
        name = english(api["jurisdiction"]["name"])
        require(name not in apis or apis[name] == api, "Conflicting native locality snapshots")
        apis[name] = api
    root = apis.pop("Arizona")
    require(sources["official-full-election-json"]["url"]
            == "https://app.enhancedvoting.com/cdn/results/" + root["jurisdiction"]["mediaExportPath"],
            "Acquired media URL differs from actual native application declaration")
    house, all_rows, audit = review_native(data, party_aliases(root))
    participation, counties, api_audit = review_api(data, root, apis)
    comparisons = api_audit.pop("api_option_correspondence")
    api_audit["api_option_correspondence_table"] = "api-option-correspondence.csv"
    audit["api_review"] = api_audit
    require((audit["native_counties"], audit["statewide_contests"], audit["county_contests"],
             len(house), audit["precinct_option_rows"], len(participation))
            == (15, 99, 415, 1762, 143533, 1763), "Native snapshot scope changed; review before publication")
    output.mkdir(parents=True)
    originals = output / "native-source/originals"
    originals.mkdir(parents=True)
    for key in payloads:
        shutil.copyfile(source / sources[key]["file"], originals / (key + ".gz"))
    (output / "native-source/sources.json").write_text(json.dumps(
        {key: sources[key] for key in payloads}, indent=2) + "\n")
    context = dict(
        official_platform_declaration="https://azsos.gov/news/1077",
        official_press_declaration="https://azsos.gov/press",
        native_application_declares_media_export=True,
        nonredistributed_frontend_and_blocked_response_receipts={
            key: receipt for key, receipt in sources.items() if key not in payloads},
        original_count=len(payloads), geometry_approved=False,
        limitation="Direct SOS press request is HTTP403. Full factual native media/API originals "
                   "are acquired; no blocked HTML, frontend document or third-party map is redistributed.")
    if (source / "acquisition-context.json").exists():
        context = json.loads((source / "acquisition-context.json").read_text())
        require(context["original_count"] == len(payloads)
                and context["native_application_declares_media_export"] is True,
                "Portable acquisition context conflicts with actual originals")
    (output / "native-source/acquisition-context.json").write_text(json.dumps(context, indent=2) + "\n")
    shutil.copyfile(Path(__file__), output / "review.py")
    for name, records in [("precinct-counts.csv", house),
                          ("precinct-participation.csv", participation),
                          ("county-participation.csv", counties),
                          ("api-option-correspondence.csv", comparisons),
                          ("all-native-option-counts.csv.gz", all_rows)]:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
        raw = stream.getvalue().encode()
        (output / name).write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)
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
                      if key not in {"county_contest_scopes", "native_party_description_differences"}},
                     indent=2))
