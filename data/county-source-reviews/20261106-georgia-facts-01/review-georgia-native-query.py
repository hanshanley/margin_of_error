"""Reproduce the complete factual Georgia county participation and results query."""

import argparse
from collections import Counter
import csv
from decimal import Decimal, ROUND_HALF_UP
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


INPUT_SHA256 = "c07b3e67b6af696ef94ee546c42410491b037df4b34e60c2877f119759b5f088"
ARCHIVE = "complete-georgia-native-query-01.zip"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n").encode()


def english(values):
    matches = [row["text"] for row in values if row["languageId"] == "en"]
    require(len(matches) == 1, "Nonunique English source label")
    return matches[0]


def percent(numerator, denominator):
    return (Decimal(100) * Decimal(str(numerator)) / Decimal(str(denominator))).quantize(
        Decimal(".01"), rounding=ROUND_HALF_UP)


def mode_summary(groups):
    known = [row["voteCount"] for row in groups if row["voteCount"] is not None]
    require(all(type(value) is int and value >= 0 for value in known), "Invalid native mode count")
    complete = bool(groups) and len(known) == len(groups)
    return dict(known_sum=sum(known), missing_cells=len(groups) - len(known),
                complete=complete, complete_sum=sum(known) if complete else None)


def parse_voters(text):
    matches = re.findall(
        r"^([^\n]+ County)\nVoters: ([\d,]+)\nBallots Cast: ([\d,]+)\nVoter Turnout:([^\n]*)$",
        text, re.MULTILINE)
    rows = {name: dict(voters=int(voters.replace(",", "")), ballots=int(ballots.replace(",", "")),
                       printed_turnout=turnout.strip()) for name, voters, ballots, turnout in matches}
    require(len(matches) == len(rows) == 159, "Incomplete or duplicate native Voters cards")
    root = re.search(
        r"Totals\nVoters\n([\d,]+)\nBallots Cast\n([\d,]+)\nVoter Turnout\n([\d.]+)%\n", text)
    require(root is not None, "Missing printed statewide Voters total")
    clock = re.search(r"^Last Updated ([^\n]+)$", text, re.MULTILINE)
    require(clock is not None, "Missing printed native clock")
    return rows, dict(voters=int(root[1].replace(",", "")), ballots=int(root[2].replace(",", "")),
                      printed_turnout=root[3], source_update_literal=clock[1], printed_timezone="")


def participation(records):
    primary = records["primary"]
    cards, root = parse_voters(records["voters"]["text"])
    rows, seen = [], set()
    media_counties = {row["name"]: row for row in records["media"]["localResults"]}
    require(len(media_counties) == len(records["media"]["localResults"]) == 159, "Duplicate media counties")
    for row in primary["complete_county_native_records"]:
        child, registration, election = (row[key] for key in
            ("native_child_locality", "native_registration", "native_locality_election"))
        name, identity = english(child["name"]), child["id"].casefold()
        require(identity not in seen, "Duplicate native county identity")
        seen.add(identity)
        require(identity == registration["id"].casefold() == election["jurisdictionId"].casefold(),
                "Nonbijective county UUID join")
        require(child["name"] == registration["localityName"], "Different registration county identity")
        require(name in cards and name in media_counties, "Missing independent native county label")
        ballots, voters = election["ballotsCast"], election["totalVoters"]
        require(all(type(value) in (int, float) and int(value) == value and value >= 0 for value in (ballots, voters)),
                "Invalid native participation")
        require(cards[name]["ballots"] == ballots and cards[name]["voters"] == voters == registration["total"],
                "Rendered participation disagrees with native county records")
        require(election["electionDate"] == "2026-11-03", "Changed county election")
        printed = cards[name]["printed_turnout"]
        if voters:
            require(ballots <= voters and child["turnoutPercent"] is not None, "Unusable positive-denominator fraction")
            require(printed == str(percent(ballots, voters)) + "%", "Printed county rate disagrees")
            require(percent(child["turnoutPercent"], 1) == percent(ballots, voters), "Native fraction disagrees")
        else:
            require(child["turnoutPercent"] is None and printed == "", "Invented zero-denominator turnout")
        rows.append(dict(year=2026, state_code="GA", county=name, native_uuid=child["id"],
            native_media_county_id=media_counties[name]["id"], source_fips="",
            native_ballots_cast=ballots, native_total_voters=voters,
            native_registration_total=registration["total"], native_active_voters=registration["activeVoters"],
            native_inactive_voters=registration["inactiveVoters"], native_fraction=child["turnoutPercent"],
            native_printed_turnout=printed, usable_native_fraction=voters > 0,
            native_is_official_results=election["isOfficialResults"],
            native_as_of=election["asOf"], native_last_updated=election["lastUpdated"],
            native_publish_date=election["publishDate"], counting_complete=False, maps_approved=False,
            native_reporting_json=json.dumps(dict(group=election["groupReportingStatus"],
                                                  precinct=election["precinctReportingStatus"]), separators=(",", ":"))))
    require(len(seen) == len(rows) == len(cards) == 159, "Incomplete county participation query")
    require(root["ballots"] == sum(row["native_ballots_cast"] for row in rows) == 4210155,
            "Printed statewide ballots disagree with counties")
    require(root["voters"] == sum(row["native_total_voters"] for row in rows)
            == primary["election"]["totalVoters"] == 7516484, "Statewide registration disagreement")
    require(root["printed_turnout"] == str(percent(root["ballots"], root["voters"])), "Printed statewide rate disagrees")
    require(primary["election"]["ballotsCast"] == 0, "Original conflicting API root field was overwritten")
    require(sorted(row["county"] for row in rows if not row["usable_native_fraction"])
            == ["Jeff Davis County", "Screven County"], "Changed native missing-denominator inventory")
    return rows, root


def media_audit(records):
    media, primary = records["media"], records["primary"]
    api = {(english(row["name"]), row["contestType"]): row for row in primary["complete_native_contest_vectors"]}
    roots = {(row["name"], row["contestType"]): row for row in media["results"]["ballotItems"]}
    require(len(api) == len(roots) == 273 and api.keys() == roots.keys(), "Incomplete root contest query")
    require(media["electionDate"] == primary["election"]["electionDate"] == "2026-11-03", "Changed media election")
    matched = 0
    for identity, contest in api.items():
        other = roots[identity]
        require(english(contest["voteFor"]) == f"Vote for {other['voteFor']}", "Different vote-for scope")
        choices = {row["nativeId"]: row for row in contest["summaryResults"]["ballotOptions"]}
        exported = {row["id"]: row for row in other["ballotOptions"]}
        require(len(choices) == len(contest["summaryResults"]["ballotOptions"])
                and len(exported) == len(other["ballotOptions"]) and choices.keys() == exported.keys(),
                "Incomplete or duplicate root choice identity")
        require(sum(row["voteCount"] for row in choices.values()) == contest["voteTotal"], "Root native total disagrees")
        for key, choice in choices.items():
            native = exported[key]
            require((english(choice["name"]), choice["voteCount"],
                     english(choice["party"]["name"]) if choice["party"] else None)
                    == (native["name"], native["voteCount"], native["politicalParty"]),
                    "Root choice/party/count representation disagrees")
            groups = {english(row["groupName"]): row["voteCount"] for row in choice["groupResults"]}
            other_groups = {row["groupName"]: row["voteCount"] for row in native["groupResults"]}
            require(len(groups) == len(choice["groupResults"]) and len(other_groups) == len(native["groupResults"])
                    and groups == other_groups and sum(groups.values()) == native["voteCount"], "Root mode disagreement")
            matched += 1
    require(matched == 457, "Incomplete root choices")
    root_by_id = {row["id"]: row for row in roots.values()}
    require(len(root_by_id) == 273, "Duplicate root native contest ID")
    exceptions = {key: [] for key in ("contest_title_aliases", "unresolved_contest_scopes", "literal_party_differences",
        "choice_label_aliases", "unresolved_choice_labels", "incomplete_modes", "mode_residuals", "precinct_residuals",
        "root_minus_approved_county_residuals")}
    totals, counts = Counter(), Counter()
    for county in media["localResults"]:
        identities = set()
        for contest in county["ballotItems"]:
            require(contest["id"] not in identities, "Duplicate county contest ID")
            identities.add(contest["id"])
            counts["county_contests"] += 1
            expected = root_by_id.get(contest["id"])
            approved = expected is not None
            scope = dict(county=county["name"], native_media_county_id=county["id"],
                         contest_id=contest["id"], native_county_contest=contest["name"])
            if expected:
                require((contest["contestType"], contest["voteFor"]) == (expected["contestType"], expected["voteFor"]),
                        "Different native contest/vote-for scope")
                if contest["name"] != expected["name"]:
                    alias = (contest["name"].split("/", 1)[0].strip() == expected["name"] or
                             contest["id"] in ("SQ1", "SQ2", "SQ3") and "Proposed " + contest["name"] == expected["name"])
                    exceptions["contest_title_aliases" if alias else "unresolved_contest_scopes"].append(
                        dict(**scope, native_root_contest=expected["name"]))
                    approved = bool(alias)
            choices = set()
            for choice in contest["ballotOptions"]:
                require(choice["id"] not in choices, "Duplicate native county choice ID")
                choices.add(choice["id"])
                counts["county_choices"] += 1
                total = choice["voteCount"]
                require(type(total) is int and total >= 0, "Invalid native choice total")
                key = dict(**scope, choice_id=choice["id"], native_choice=choice["name"])
                mode = mode_summary(choice["groupResults"])
                counts["missing_mode_cells"] += mode["missing_cells"]
                if not mode["complete"]:
                    exceptions["incomplete_modes"].append(dict(**key, native_choice_votes=total,
                        native_groups=choice["groupResults"], known_group_sum=mode["known_sum"]))
                elif mode["complete_sum"] != total:
                    exceptions["mode_residuals"].append(dict(**key, native_choice_votes=total, mode_sum=mode["complete_sum"]))
                precincts = choice["precinctResults"]
                if precincts is not None:
                    require(all(type(row["voteCount"]) is int and row["voteCount"] >= 0 for row in precincts),
                            "Missing or invalid precinct choice count")
                    counts["precinct_choice_records"] += len(precincts)
                    subtotal = sum(row["voteCount"] for row in precincts)
                    if subtotal != total:
                        exceptions["precinct_residuals"].append(dict(**key, native_choice_votes=total,
                            native_precinct_sum=subtotal, unclassified_difference=total-subtotal))
                if approved:
                    other = next((row for row in expected["ballotOptions"] if row["id"] == choice["id"]), None)
                    require(other is not None, "Unknown root choice native ID")
                    if choice["politicalParty"] != other["politicalParty"]:
                        require(choice["politicalParty"] == "" or
                                choice["politicalParty"].casefold() == other["politicalParty"].casefold(),
                                "Unresolved substantive party mismatch")
                        exceptions["literal_party_differences"].append(dict(**key,
                            native_county_party=choice["politicalParty"], native_root_party=other["politicalParty"]))
                    if choice["name"] != other["name"]:
                        alias = re.sub(r"\s+", "", choice["name"]).casefold() == re.sub(r"\s+", "", other["name"]).casefold()
                        exceptions["choice_label_aliases" if alias else "unresolved_choice_labels"].append(
                            dict(**key, native_root_choice=other["name"], native_votes=total))
                        if not alias:
                            continue
                    totals[(contest["id"], choice["id"])] += total
    for contest in roots.values():
        for choice in contest["ballotOptions"]:
            subtotal = totals[(contest["id"], choice["id"])]
            if subtotal != choice["voteCount"]:
                exceptions["root_minus_approved_county_residuals"].append(dict(
                    contest_id=contest["id"], contest=contest["name"], choice_id=choice["id"],
                    native_root_votes=choice["voteCount"], approved_county_sum=subtotal,
                    unclassified_difference=choice["voteCount"]-subtotal))
    return dict(root_contests=273, root_choice_vectors=matched, **counts,
                exception_counts={key: len(rows) for key, rows in exceptions.items()}, exceptions=exceptions)


def validate(records, check_pinned=True):
    if check_pinned:
        require(hashlib.sha256(json_bytes(records)).hexdigest() == INPUT_SHA256, "Changed complete factual input")
    rows, root = participation(records)
    audit = media_audit(records)
    receipt = records["voters"]["receipt"]
    require(receipt["sha256"] == hashlib.sha256(records["voters"]["text"].encode()).hexdigest()
            and receipt["bytes"] == len(records["voters"]["text"].encode()), "Changed rendered Voters evidence")
    require(audit["county_contests"] == 3894 and audit["county_choices"] == 7067
            and audit["precinct_choice_records"] == 102214, "Incomplete native county/precinct query")
    return rows, root, audit


def csv_bytes(rows):
    require(bool(rows), "Empty native query export")
    target = io.StringIO(newline="")
    writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return target.getvalue().encode()


def tables(records, participation_rows, root):
    candidates, contests, modes, precincts, parties, accounting, statuses = [], [], [], [], [], [], []
    for county in [records["media"]["results"], *records["media"]["localResults"]]:
        statewide = county is records["media"]["results"]
        base = dict(year=2026, state_code="GA", scope="statewide" if statewide else "county",
                    native_locality_name=county["name"], native_locality_id=county["id"], source_fips="")
        statuses.extend(dict(**base, native_group=row["groupName"], native_status=row["status"])
                        for row in county["reportingStatuses"])
        for contest in county["ballotItems"]:
            scope = dict(**base, native_contest_id=contest["id"], native_contest=contest["name"],
                         native_contest_type=contest["contestType"], native_vote_for=contest["voteFor"])
            contests.append(dict(**scope, derived_choice_sum=sum(row["voteCount"] for row in contest["ballotOptions"]),
                native_ballot_order=contest["ballotOrder"], native_precincts_participating=contest["precinctsParticipating"],
                native_precincts_reporting=contest["precinctsReporting"],
                native_ranked_choice_results_json=json.dumps(contest["rankedChoiceResults"], separators=(",", ":"))))
            literal_parties = Counter()
            for choice in contest["ballotOptions"]:
                identity = dict(**scope, native_choice_id=choice["id"], native_choice=choice["name"],
                                native_party=choice["politicalParty"])
                candidates.append(dict(**identity, native_votes=choice["voteCount"], native_ballot_order=choice["ballotOrder"]))
                literal_parties[choice["politicalParty"]] += choice["voteCount"]
                modes.extend(dict(**identity, native_group=row["groupName"], native_votes=row["voteCount"],
                                  native_is_from_virtual_precinct=row["isFromVirtualPrecinct"])
                             for row in choice["groupResults"])
                native_precincts = choice["precinctResults"]
                for precinct in native_precincts or []:
                    precincts.append(dict(**identity, native_precinct_id=precinct["id"],
                        native_precinct=precinct["name"], native_is_virtual=precinct["isVirtual"],
                        native_votes=precinct["voteCount"], native_reporting_status=precinct["reportingStatus"],
                        native_group_results_json=json.dumps(precinct["groupResults"], separators=(",", ":"))))
                mode = mode_summary(choice["groupResults"])
                subtotal = sum(row["voteCount"] for row in native_precincts) if native_precincts is not None else None
                accounting.append(dict(**identity, native_choice_votes=choice["voteCount"],
                    known_mode_sum=mode["known_sum"], missing_mode_cells=mode["missing_cells"],
                    complete_mode_sum=mode["complete_sum"], derived_precinct_sum=subtotal,
                    unclassified_choice_minus_precinct_sum=choice["voteCount"]-subtotal if subtotal is not None else None))
            parties.extend(dict(**scope, native_party=party, native_choice_vote_sum=votes,
                                measure="choice_votes_not_party_participation_no_missing_party_inference")
                           for party, votes in literal_parties.items())
    return {
        "county-participation.csv": participation_rows,
        "statewide-participation.csv": [dict(**root, original_conflicting_api_root_ballots=0,
            statewide_is_official_results=records["primary"]["election"]["isOfficialResults"],
            missing_county_registration_denominators=2, counting_complete=False, rate_comparable_to_cvap=False)],
        "candidate-results.csv": candidates, "native-contests.csv": contests,
        "candidate-mode-results.csv": modes, "precinct-choice-results.csv.gz": precincts,
        "literal-party-totals.csv": parties, "choice-accounting.csv": accounting,
        "native-reporting-statuses.csv": statuses,
        "source-receipts.csv": [dict(representation=name, receipt_json=json.dumps(receipt, separators=(",", ":")))
            for name, receipt in (("primary_API", records["primary"]["source_receipt"]),
                                  ("media_export", records["media_receipt"]),
                                  ("rendered_Voters", records["voters"]["receipt"]))],
    }


def reproduce(folder):
    records = json.loads(gzip.decompress((folder / "source-records.json.gz").read_bytes()))
    rows, root, audit = validate(records)
    exported = {}
    for name, values in tables(records, rows, root).items():
        body = csv_bytes(values)
        exported[name] = gzip.compress(body, compresslevel=9, mtime=0) if name.endswith(".gz") else body
    audit.update(status="complete_factual_source_query_not_explorer_approval", native_counties=159,
        usable_native_county_fractions=157, missing_county_fractions=2, printed_statewide_totals=root,
        qualifications=[
            "Rendered Voters and API/media are representations of the same official backend, not independent institutions.",
            "The original API root ballotsCast=0 remains conflicting, not actual zero; native Voters separately prints 4,210,155.",
            "Screven and Jeff Davis retain zero denominators and missing native fractions/printed rates, never zero turnout.",
            "Native totalVoters and active/inactive fields remain literal; no active-plus-inactive decomposition is inferred.",
            "Native registered-voter fractions are not CVAP or demographic-group turnout; two county denominators are missing.",
            "Native county media IDs are not FIPS; no native FIPS, 2026 boundary applicability or map approval is inferred.",
            "Wilkinson alone retains its true native official flag; the root remains unofficial; reporting is not certification.",
            "All native party strings, including missing and case variants, survive; no missing county party is filled from root.",
            "Literal-party totals are within one native contest/scope only, never party participation or pooled voters.",
            "All 372 null mode cells remain missing; known-mode sums are partial and never used as complete mode sums.",
            "Only explicit bilingual/Proposed contest wording and case/whitespace choice aliases are used, with both labels retained.",
            "Unresolved party/stage contest scopes are quarantined; residuals remain unclassified, not inferred undervotes.",
            "All 102,214 native precinct choice records and their nested mode groups survive, without precinct map allocation.",
            "Both complete factual queries, native clocks/statuses, county participation and full download data are preserved.",
            "Source HTML, scripts, browser traffic, application configuration and access-denied bodies are not redistributed."])
    exported["audit.json"] = (json.dumps(audit, indent=2, ensure_ascii=True) + "\n").encode()
    exported.update({name: (folder / name).read_bytes() for name in
        ("source-records.json.gz", "review-georgia-native-query.py", "test-georgia-native-query.py")})
    exported["checksums.json"] = (json.dumps([
        dict(file=name, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        for name, body in sorted(exported.items())], indent=2) + "\n").encode()
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, body in sorted(exported.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, body, compresslevel=9)
    exported[ARCHIVE] = target.getvalue()
    return exported


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    folder = Path(__file__).parent
    outputs = reproduce(folder)
    for name, body in outputs.items():
        if args.write:
            (folder / name).write_bytes(body)
        require((folder / name).read_bytes() == body, "Changed complete output: " + name)
    print(f"All {len(outputs)} entire Georgia files reproduce, including the complete archive.")
