"""Reconcile Virginia's native locality/precinct modes without allocating residual votes."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import zipfile


SPEC = importlib.util.spec_from_file_location("virginia_reports",
    Path(__file__).with_name("review-virginia-2026-native-results.py"))
reports = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reports)
require, english, MODES = reports.require, reports.english, reports.MODES


def native_count(value):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and value >= 0 and value == int(value), "Missing or invalid native count")
    return int(value)


def option_vector(options):
    result = {}
    for option in options:
        identity = option["nativeId"]
        require(identity and identity not in result, "Duplicate native candidate identity")
        modes, group_ids = {}, set()
        for group in option["groupResults"]:
            name = english(group["groupName"])
            require(name not in modes and group["groupId"] not in group_ids,
                    "Duplicate native voting method")
            group_ids.add(group["groupId"])
            modes[name] = native_count(group["voteCount"])
        require(set(modes) == set(MODES), "Missing or unreviewed native voting method")
        votes = native_count(option["voteCount"])
        require(sum(modes.values()) == votes, "Native candidate/method total conflict")
        result[identity] = dict(votes=votes, modes=modes, name=english(option["name"]),
            party=option["party"], is_write_in=option["isWriteIn"])
    require(result, "Empty native candidate vector")
    return result


def review_scope(item):
    summary = option_vector(item["summaryResults"]["ballotOptions"])
    require(sum(o["votes"] for o in summary.values()) == native_count(item["voteTotal"]),
            "Native summary total conflict")
    require(item["breakdownResultCount"] == len(item["breakdownResults"]),
            "Incomplete native breakdown")
    totals = {identity: {mode: 0 for mode in MODES} for identity in summary}
    seen, units = set(), []
    for row in item["breakdownResults"]:
        identity = row["precinct"]["id"]
        require(identity not in seen and row["parentBallotItemId"] == item["id"],
                "Duplicate or wrong-contest precinct")
        seen.add(identity)
        vector = option_vector(row["ballotOptions"])
        require(set(vector) == set(summary), "Incomplete precinct candidate identities")
        require(sum(o["votes"] for o in vector.values()) == native_count(row["voteTotal"]),
                "Native precinct total conflict")
        for candidate, option in vector.items():
            require(all(option[field] == summary[candidate][field]
                        for field in ["name", "party", "is_write_in"]),
                    "Conflicting native candidate description")
            for mode in MODES:
                totals[candidate][mode] += option["modes"][mode]
        units.append(dict(precinct=row["precinct"], candidates=vector,
                          candidate_votes=native_count(row["voteTotal"])))
    residuals = {mode: {candidate: option["modes"][mode] - totals[candidate][mode]
        for candidate, option in summary.items()} for mode in MODES}
    return dict(summary=summary, mode_residuals=residuals,
        precinct_mode_allocation_complete=all(v == 0 for vector in residuals.values()
                                               for v in vector.values()),
        negative_residual_conflict=any(v < 0 for vector in residuals.values()
                                      for v in vector.values())), units


def validate_identity(data, child=None):
    election = data["election"]
    require(election["electionDate"] == "2026-11-03"
            and english(election["name"]) == "2026 November General"
            and election["isProduction"] is True
            and election["isOfficialResults"] is False, "Wrong native election identity")
    if child:
        require(data["jurisdiction"]["id"].lower() == child["id"].lower()
                and data["jurisdiction"]["shortName"] == child["shortName"],
                "Wrong native locality identity")


def house_name(item):
    name = english(item["name"])
    return name if re.fullmatch(
        r"Member, House of Representatives \(\d+(?:st|nd|rd|th) District\)", name) else None


def verify_capture(source):
    sources = json.loads((source / "sources.json").read_text())
    require({p.stem for p in (source / "originals").glob("*.gz")} == set(sources),
            "Unreceipted or missing HTTP original")
    for key, receipt in sources.items():
        reports.verified(source, key, receipt)
    return sources


def geometry_capture(source, sources):
    def load(key):
        return json.loads(reports.verified(source, key, sources[key]))
    ids = load("district-union-objectids")["objectIds"]
    require(len(ids) == len(set(ids)) and ids, "Invalid native geometry ID set")
    seen, pairs, missing = set(), set(), 0
    for key in sorted(k for k in sources if k.startswith("district-union-features-")):
        data = load(key)
        require(data["type"] == "FeatureCollection" and not data.get("exceededTransferLimit"),
                "Truncated geometry page")
        for feature in data["features"]:
            properties = feature["properties"]
            require(properties["OBJECTID"] not in seen, "Duplicate geometry feature")
            seen.add(properties["OBJECTID"])
            pair = (properties["CountyFIPS"], properties["PrcnctNum"])
            pairs.add(pair)
            missing += not all(pair)
    require(seen == set(ids), "Incomplete native geometry")
    item = load("district-union-service-item")
    require(item["access"] == "public" and item["orgId"] == "M3dium4ePYpmdT4B",
            "Unreviewed geometry publisher")
    return dict(native_fragments=len(ids), distinct_attribute_pairs=len(pairs),
        blank_identity_fragments=missing, all_native_object_ids_present_exactly_once=True,
        approval="Current official reference only; no join, shape audit or election-day certification.",
        geometry_approved=False)


def build_review(source, earlier, geometry, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing immutable review overwrite")
    sources = verify_capture(source)
    geometry_sources = verify_capture(geometry)

    def load(key):
        return json.loads(reports.verified(source, key, sources[key]))

    for filename, receipt in json.loads((earlier / "checksums.json").read_text()).items():
        body = (earlier / filename).read_bytes()
        require(len(body) == receipt["bytes"]
                and hashlib.sha256(body).hexdigest() == receipt["sha256"],
                "Earlier immutable review checksum conflict")
    with (earlier / "precinct-counts.csv").open() as stream:
        original_candidates = {}
        for row in csv.DictReader(stream):
            for candidate in json.loads(row["candidates"]):
                key = (row["locality_code"], row["precinct"], row["district"], candidate["id"])
                require(key not in original_candidates, "Duplicate earlier candidate identity")
                original_candidates[key] = candidate["votes"]
    with (earlier / "precinct-turnout.csv").open() as stream:
        original_turnout = {(r["locality_code"], r["precinct"]): r for r in csv.DictReader(stream)}
    parent = load("parent-state")
    validate_identity(parent)
    children = parent["jurisdiction"]["childLocalities"]
    require(len(children) == len({c["id"] for c in children}) == 133
            and len({c["mapFeatureId"] for c in children}) == 133, "Incomplete native localities")
    expected = {house_name(i): {o["nativeId"]: native_count(o["voteCount"])
        for o in i["summaryResults"]["ballotOptions"]} for i in parent["ballotItems"] if house_name(i)}
    require(len(expected) == 11, "Incomplete parent House vectors")
    actual, method_gaps = defaultdict(Counter), Counter()
    county_rows, precinct_rows, turnout_rows, scope_rows, versions = [], [], [], [], []
    used_details, seen_candidates, seen_turnout = set(), set(), set()
    for child in children:
        code = child["mapFeatureId"]
        data = load("locality-" + code)
        validate_identity(data, child)
        precinct_names = {}
        for row in data["voterTurnout"]:
            require(row["id"] not in precinct_names, "Duplicate native turnout identity")
            precinct_names[row["id"]] = row["precinctName"]
            key = (code, row["precinctName"])
            require(key in original_turnout and key not in seen_turnout,
                    "Unmatched native turnout identity")
            seen_turnout.add(key)
            registration = native_count(row["voterRegistration"])
            require(registration == int(original_turnout[key]["TotalRegisteredVoters"]),
                    "Native precinct registration conflict")
            turnout_rows.append(dict(year=2026, state_code="VA", locality_code=code,
                locality=english(child["name"]), precinct_uuid=row["id"],
                precinct=row["precinctName"], voter_turnout=native_count(row["voterTurnout"]),
                ballots_cast=native_count(row["ballotsCast"]), registered_voters=registration,
                earlier_csv_total_vote_turnout=original_turnout[key]["TotalVoteTurnout"],
                turnout_rate=None, scope="Literal native counts; county mode coverage not allocated.",
                source="locality-" + code))
        require(len(data["precincts"]) == len(precinct_names), "Native precinct/turnout scope conflict")
        for item in data["ballotItems"]:
            name = house_name(item)
            if not name:
                continue
            require(name in expected and data["election"]["includePrecinctResults"]
                    and not data["election"]["precinctResultsProtected"]
                    and item["hasBreakdownResults"], "Unreviewed or protected native detail")
            key = "house-" + code + "-" + item["id"]
            detail = load(key)
            used_details.add(key)
            validate_identity(detail, child)
            full = detail["ballotItemWithBreakdown"]
            require(full["id"] == item["id"] and house_name(full) == name,
                    "Wrong native House detail")
            review, units = review_scope(full)
            root_vector = option_vector(item["summaryResults"]["ballotOptions"])
            require(root_vector == review["summary"], "Locality root/detail candidate conflict")
            require(set(root_vector) == set(expected[name]), "Locality/parent candidate identity conflict")
            actual[name].update({candidate: option["votes"] for candidate, option in root_vector.items()})
            district = re.search(r"\((\d+)", name).group(1)
            common = dict(year=2026, state_code="VA", locality_code=code,
                locality=english(child["name"]), district=district, office=name,
                precinct_mode_allocation_complete=review["precinct_mode_allocation_complete"],
                maps_approved=False, source=key)
            county_rows.append(dict(**common, candidate_votes=native_count(full["voteTotal"]),
                candidates=json.dumps(root_vector, separators=(",", ":"), ensure_ascii=True),
                mode_residuals=json.dumps(review["mode_residuals"], separators=(",", ":")),
                reporting_status=json.dumps(data["election"]["groupReportingStatus"],
                                             separators=(",", ":"), ensure_ascii=True)))
            scope_rows.append({**common, **review})
            for mode, vector in review["mode_residuals"].items():
                method_gaps[mode] += any(v != 0 for v in vector.values())
            for unit in units:
                precinct = unit["precinct"]
                require(precinct["id"] in precinct_names, "Unmatched native precinct UUID")
                label = precinct_names[precinct["id"]]
                for candidate, option in unit["candidates"].items():
                    identity = (code, label, district, candidate)
                    require(identity not in seen_candidates and identity in original_candidates,
                            "Duplicate or unmatched earlier precinct candidate")
                    seen_candidates.add(identity)
                    require(option["votes"] == original_candidates[identity],
                            "Earlier CSV/native precinct count conflict")
                precinct_rows.append(dict(**common, precinct_uuid=precinct["id"],
                    precinct=label, native_breakdown_label=english(precinct["name"]),
                    candidate_votes=unit["candidate_votes"],
                    candidates=json.dumps(unit["candidates"], separators=(",", ":"), ensure_ascii=True),
                    ballots=None, turnout_rate=None))
        versions.append(dict(locality_code=code, as_of=data["election"]["asOf"],
            publish_version=data["election"]["publishVersionId"],
            ballots_cast=native_count(data["election"]["ballotsCast"])))
    require({k: dict(v) for k, v in actual.items()} == expected,
            "Locality/state candidate vector conflict")
    require(seen_candidates == set(original_candidates), "Incomplete earlier candidate reconciliation")
    require(seen_turnout == set(original_turnout), "Incomplete native turnout reconciliation")
    require(used_details == {k for k in sources if k.startswith("house-")},
            "Unreviewed native House detail original")
    result = dict(year=2026, state_code="VA", original_files=len(sources),
        localities=len(children), house_details=len(used_details), precinct_vectors=len(precinct_rows),
        candidate_cells=len(seen_candidates), all_earlier_csv_candidate_cells_match=True,
        all_locality_candidate_vectors_match_parent=True,
        native_turnout_rows=len(turnout_rows),
        native_precinct_turnout=sum(r["voter_turnout"] for r in turnout_rows),
        native_locality_ballots=sum(r["ballots_cast"] for r in versions),
        incomplete_locality_house_scopes=sum(not r["precinct_mode_allocation_complete"] for r in scope_rows),
        method_scope_gaps=dict(method_gaps), geometry=geometry_capture(geometry, geometry_sources),
        maps_approved=False, rates_available=False,
        scope="Unofficial published counts, not final turnout. Each positive or negative county/method "
              "residual stays unallocated. Unreported modes and old blank CSV totals are not repaired.",
        locality_versions=versions)
    output.mkdir(parents=True)
    shutil.copytree(source, output / "native-locality-source")
    shutil.copytree(earlier, output / "earlier-report-review")
    shutil.copytree(geometry, output / "current-reference-geometry")
    for name in [Path(__file__).name, "review-virginia-2026-native-results.py"]:
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    for name, value in [("counts-review.json", result), ("locality-house-scope-review.json", scope_rows)]:
        (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n")
    for name, rows in [("precinct-counts.csv", precinct_rows), ("precinct-turnout.csv", turnout_rows),
                       ("locality-house-counts.csv", county_rows)]:
        with (output / name).open("w") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (output / "checksums.json").write_text(json.dumps({
        path.relative_to(output).as_posix(): dict(bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(output.rglob("*")) if path.is_file()
    }, separators=(",", ":")))
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as target:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                member = zipfile.ZipInfo(path.relative_to(output).as_posix())
                member.external_attr = 0o644 << 16
                target.writestr(member, path.read_bytes())
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["source", "earlier", "geometry", "output", "archive"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = build_review(args.source, args.earlier, args.geometry, args.output, args.archive)
    print(json.dumps({k: v for k, v in result.items() if k != "locality_versions"}, indent=2))
