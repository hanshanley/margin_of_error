"""Reconcile native Rhode Island House counts without inventing residential geography or turnout."""

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
from uuid import UUID
import zipfile


SOURCE = "https://electionresults.ri.gov/results/public/rhodeisland/elections/2026StatewideGeneralElection"
API = "https://electionresults.ri.gov/results/public/api/elections/rhodeisland/2026StatewideGeneralElection/data"
MEDIA = "https://electionresults.ri.gov/cdn/results/RhodeIsland/export-2026StatewideGeneralElection.json"
RELEASE = ("https://github.com/hanshanley/margin_of_error/releases/download/"
           "voter-precinct-rhode-island-20261105/complete-rhode-island-2026-source-review.zip")
CONTESTS = {str(i + 1): f"Representative in Congress District {i}" for i in (1, 2)}
MODES = {"Election Day", "Early Voting", "Mail Ballots"}


def count(value):
    if (type(value) not in (int, float) or value < 0
            or type(value) is float and not math.isfinite(value) or value != int(value)):
        raise ValueError("Missing or invalid Rhode Island count, not zero")
    return int(value)


def english(values):
    names = [v["text"] for v in values if v["languageId"] == "en"]
    if len(names) != 1 or not names[0]:
        raise ValueError("Ambiguous Rhode Island English identity")
    return names[0]


def keyed(rows, field="id"):
    result = {}
    for row in rows:
        key = row[field]
        if not isinstance(key, str) or not key or key in result:
            raise ValueError("Duplicate or missing Rhode Island source identity")
        result[key] = row
    return result


def modes(rows, public=False):
    values = {}
    for row in rows:
        name = english(row["groupName"]) if public else row["groupName"]
        if name in values or name not in MODES:
            raise ValueError("Duplicate or unknown Rhode Island voting mode")
        if not public and type(row["isFromVirtualPrecinct"]) is not bool:
            raise ValueError("Missing Rhode Island native virtual-mode flag")
        values[name] = count(row["voteCount"])
    if set(values) != MODES:
        raise ValueError("Missing Rhode Island voting mode")
    return values


def review(media, parent):
    election = parent["election"]
    if (media["electionDate"] != "2026-11-03" or election["electionDate"] != "2026-11-03"
            or media["electionName"] != "Statewide General Election"
            or english(election["name"]) != media["electionName"]
            or media["results"]["name"] != "Rhode Island"
            or english(parent["jurisdiction"]["name"]) != "Rhode Island"):
        raise ValueError("Wrong Rhode Island election identity")
    state = keyed(media["results"]["ballotItems"])
    if {k for k, c in state.items() if c["name"].startswith("Representative in Congress")} != set(CONTESTS):
        raise ValueError("Unknown Rhode Island native House scope")
    public_house = [b for b in parent["ballotItems"]
                    if english(b["name"]).startswith("Representative in Congress")]
    public = {english(b["name"]): b for b in public_house}
    if len(public_house) != 2 or set(public) != set(CONTESTS.values()):
        raise ValueError("Missing or duplicate Rhode Island public House contest")
    localities = keyed(media["localResults"])
    api_localities = {str(UUID(r["jurisdictionId"])): r for r in parent["localityElections"]}
    children = {str(UUID(r["id"])): r for r in parent["jurisdiction"]["childLocalities"]}
    if (len(api_localities) != len(parent["localityElections"])
            or len(children) != len(parent["jurisdiction"]["childLocalities"])
            or set(api_localities) != set(children)
            or {str(UUID(k)) for k in localities} != set(children)):
        raise ValueError("Missing or duplicate Rhode Island locality")
    expected, sums, results, facts, scope = {}, Counter(), [], {}, []
    for identity, title in CONTESTS.items():
        contest = state.get(identity)
        if (not contest or contest["name"] != title or contest["contestType"] != "Candidate"
                or contest["voteFor"] != 1 or title not in public):
            raise ValueError("Missing or wrong Rhode Island House contest")
        candidates = keyed(contest["ballotOptions"])
        independent = keyed(public[title]["summaryResults"]["ballotOptions"], "nativeId")
        if set(candidates) != set(independent):
            raise ValueError("Rhode Island public/media candidate sets differ")
        for cid, c in candidates.items():
            p = independent[cid]
            party_names = (p.get("party") or {}).get("name")
            if (english(p["name"]) != c["name"]
                    or (english(party_names) if party_names else None) != c["politicalParty"]
                    or count(p["voteCount"]) != count(c["voteCount"])
                    or modes(c["groupResults"]) != modes(p["groupResults"], public=True)
                    or sum(modes(c["groupResults"]).values()) != count(c["voteCount"])):
                raise ValueError("Rhode Island independent candidate identity/count/mode mismatch")
        expected[identity] = candidates
    statistics = []
    for lid, locality in localities.items():
        api = api_localities[str(UUID(lid))]
        if english(children[str(UUID(lid))]["name"]) != locality["name"]:
            raise ValueError("Rhode Island locality names differ")
        statistics.append(dict(source_locality_id=lid, locality=locality["name"],
            source_updated=api["asOf"], ballots=count(api["ballotsCast"]),
            registered=count(api["totalVoters"]), reported_pct=None,
            basis="Uncertified source locality counts; not precinct or demographic participation rates."))
        local_contests = keyed(locality["ballotItems"])
        if not set(local_contests) & set(CONTESTS):
            raise ValueError("Rhode Island locality missing House records")
        for identity, contest in local_contests.items():
            if identity not in CONTESTS:
                if contest["name"].startswith("Representative in Congress"):
                    raise ValueError("Unknown Rhode Island local House scope")
                continue
            if (contest["name"] != CONTESTS[identity] or contest["voteFor"] != 1
                    or contest["contestType"] != "Candidate"):
                raise ValueError("Wrong Rhode Island local House identity")
            candidates = keyed(contest["ballotOptions"])
            if set(candidates) != set(expected[identity]):
                raise ValueError("Missing Rhode Island local candidate")
            units, local_sums = {}, Counter()
            for cid, candidate in candidates.items():
                reference = expected[identity][cid]
                if any(candidate[f] != reference[f] for f in ("name", "politicalParty")):
                    raise ValueError("Rhode Island local candidate identity differs")
                precincts = keyed(candidate["precinctResults"])
                if not precincts:
                    raise ValueError("Missing Rhode Island native candidate units")
                if units and set(precincts) != set(units):
                    raise ValueError("Missing Rhode Island native candidate unit")
                for pid, p in precincts.items():
                    if type(p["isVirtual"]) is not bool or not p["name"]:
                        raise ValueError("Missing Rhode Island unit scope")
                    fact = (p["name"], p["isVirtual"], p["reportingStatus"])
                    if pid in units and units[pid]["facts"] != fact:
                        raise ValueError("Conflicting Rhode Island repeated unit facts")
                    key = (lid, pid)
                    if key in facts and facts[key][:2] != fact[:2]:
                        raise ValueError("Conflicting Rhode Island cross-contest unit identity")
                    facts[key] = fact
                    values = modes(p["groupResults"])
                    if sum(values.values()) != count(p["voteCount"]):
                        raise ValueError("Rhode Island native candidate modes disagree")
                    record = dict(source_candidate_id=cid, name=candidate["name"],
                        party=candidate["politicalParty"], votes=count(p["voteCount"]),
                        modes=values, source_group_results=p["groupResults"])
                    units.setdefault(pid, dict(facts=fact, candidates=[]))["candidates"].append(record)
                    for mode, value in values.items():
                        local_sums[(cid, mode)] += value
                        sums[(identity, cid, mode)] += value
                values = modes(candidate["groupResults"])
                if (sum(values.values()) != count(candidate["voteCount"])
                        or any(local_sums[(cid, m)] != n for m, n in values.items())):
                    raise ValueError("Rhode Island native/local candidate-mode totals differ")
            if len(units) != count(contest["precinctsParticipating"]):
                scope.append(dict(locality=locality["name"], contest_id=identity,
                    declared_precincts=contest["precinctsParticipating"], native_units=len(units)))
            for pid, unit in units.items():
                label, virtual, reporting = unit["facts"]
                kind = ("federal_reporting_unit" if locality["name"] == "Federal" else
                        "limited_only_office" if "LIMITED ONLY" in label.upper() else
                        "native_reporting_unit_geography_unverified")
                votes = unit["candidates"]
                totals = {p: sum(c["votes"] for c in votes if c["party"] == p)
                          for p in ("DEMOCRAT", "REPUBLICAN")}
                total = sum(c["votes"] for c in votes)
                results.append(dict(key=f"RI|{lid}|{identity}|{pid}", year=2026, state_code="RI",
                    locality=locality["name"], source_locality_id=lid, source_unit_id=pid,
                    precinct=label, source_contest_id=identity, source_office=CONTESTS[identity],
                    office="U.S. House", reporting_unit_kind=kind, source_is_virtual=virtual,
                    source_reporting_status=reporting, democratic_votes=totals["DEMOCRAT"],
                    republican_votes=totals["REPUBLICAN"],
                    other_votes=total - sum(totals.values()), contest_votes=total,
                    candidate_counts=json.dumps(votes, separators=(",", ":"), sort_keys=True),
                    source_url=MEDIA, quality_flags="geography_unverified;precinct_rates_withheld"))
    for identity, candidates in expected.items():
        for cid, candidate in candidates.items():
            if any(sums[(identity, cid, m)] != v for m, v in modes(candidate["groupResults"]).items()):
                raise ValueError("Rhode Island complete native/state candidate-mode totals differ")
    return results, statistics, dict(unique_native_units=len(facts),
        candidate_totals={f"{identity}|{cid}|{c['name']}": c["voteCount"]
                          for identity, candidates in expected.items() for cid, c in candidates.items()},
        source_unit_kinds=dict(Counter(r["reporting_unit_kind"] for r in results)),
        native_vs_declared_precinct_counts=scope,
        parent_ballots=count(election["ballotsCast"]), parent_registered=count(election["totalVoters"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cache", "output", "archive"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable Rhode Island review")
    receipts = {r["file"]: r for r in json.loads((args.cache / "public-response-receipts.json").read_bytes())}
    for name in ("official-general-results.html", "official-results-main.js", "official-media-export.json"):
        receipts[name] = json.loads((args.cache / (name.rsplit(".", 1)[0] + ".source.json")).read_bytes())
    parent_name = next(name for name, receipt in receipts.items() if receipt["url"] == API)
    originals = {}
    for name, receipt in receipts.items():
        if Path(name).name != name or not receipt["url"].startswith("https://electionresults.ri.gov/"):
            raise ValueError("Wrong Rhode Island original source")
        raw = (args.cache / name).read_bytes()
        if len(raw) != receipt["bytes"] or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed Rhode Island original")
        originals[name] = raw
    if receipts["official-media-export.json"]["url"] != MEDIA:
        raise ValueError("Wrong Rhode Island native export")
    parent = json.loads(originals[parent_name])
    results, statistics, reconciliation = review(json.loads(originals["official-media-export.json"]), parent)
    args.output.mkdir(parents=True)
    def save(name, value):
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        (args.output / name).write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)
    (args.output / "originals").mkdir()
    for name, raw in originals.items():
        (args.output / "originals" / (name + ".gz")).write_bytes(gzip.compress(raw, mtime=0))
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, list(results[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(results)
    (args.output / "results.csv.gz").write_bytes(gzip.compress(out.getvalue().encode(), mtime=0))
    save("participation.json.gz", statistics)
    save("sources.json", receipts)
    save("audit.json", dict(year=2026, state_code="RI", complete="no",
        source_election_date="2026-11-03", source_updated=parent["election"]["asOf"],
        source_certified=parent["election"]["isOfficialResults"],
        reporting_units=reconciliation["unique_native_units"], result_rows=len(results),
        candidate_results="acquired_reconciled", participation="acquired_locality_counts_rates_withheld",
        boundaries="exact_year_reference_pending", join="withheld",
        validation="native_and_independent_api_candidate_mode_totals_passed",
        publication="full_counts_download_only", source_url=SOURCE,
        complete_download_url=RELEASE, reconciliation=reconciliation, rates_available=0,
        next_action="Review Federal and limited-only allocation, obtain authoritative 2026 geographic "
                    "references and validate unique joins; review local participation separately.",
        notes="Complete native export and separate public API preserved. Native isVirtual=false is not "
              "residential geography. Federal/limited-only units, declared-count differences and zero "
              "parent ballots retained. House votes are not ballots or demographic participation. "
              "All rates and geometry withheld. " + str(reconciliation["unique_native_units"]) + " native units."))
    save("checksums.json", {str(p.relative_to(args.output)): dict(bytes=p.stat().st_size,
         sha256=hashlib.sha256(p.read_bytes()).hexdigest())
         for p in sorted(args.output.rglob("*")) if p.is_file()})
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(str(path.relative_to(args.output)), date_time=(2026, 11, 5, 0, 0, 0))
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())
    print(json.dumps(dict(result_rows=len(results), reconciliation=reconciliation,
        archive_bytes=args.archive.stat().st_size,
        archive_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest()), indent=2))


if __name__ == "__main__":
    main()
