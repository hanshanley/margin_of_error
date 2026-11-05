"""Reconcile Vermont reporting splits without calling municipal turnout precinct data."""

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile


spec = importlib.util.spec_from_file_location("precinct_results", Path(__file__).with_name("build-precinct-results.py"))
results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(results)
GUID = "68d61e96-1d28-4210-8c1d-8e90512ae105"
STATIC = "https://static.electionresults.vermont.gov/"
STAMP = "20261104211117"
TABS = dict(federal="full-results", stateWide="stateWide", senate="senate",
            house="house", county="county", town="town", turnOut="turnOut")
HOUSE_URL = f"{STATIC}elections/{GUID}-f-{STAMP}.json"
APP_SOURCE = dict(url="https://electionresults.vermont.gov/chunk-3WQ2LQCO.js", bytes=3608924,
                  sha256="6d7af6eacc27e1f9b3c191e8a6a9deb19b4ac856ac3aa2227cc876f595526ada")
EXTRA_FIELDS = ["town_id", "town", "house_district", "senate_district", "county_name",
                "reported_contest_total", "overvotes", "blank_votes"]


def count(value):
    if type(value) is not int or value < 0:
        raise ValueError("Missing or invalid VT count; do not substitute zero")
    return value


def candidate_counts(node):
    candidates = {}
    for candidate in node["rc"] + node["wc"]:
        identity = count(candidate["cid"])
        if identity in candidates or not candidate["cn"]:
            raise ValueError("Duplicate or unnamed VT candidate")
        candidates[identity] = candidate
        count(candidate["vc"])
    if (node["vf"] != 1 or sum(c["vc"] for c in candidates.values())
            + count(node["sv"]) + count(node["bv"]) != count(node["sc"])):
        raise ValueError("VT candidate, blank, overvote and contest totals do not reconcile")
    return candidates


def vt_results(source, metadata, turnout):
    identity = metadata["electionDetails"]
    if (identity["electionId"] != 7100 or identity["electionGuid"] != GUID
            or identity["electionName"] != "2026 GENERAL ELECTION"
            or identity["electionDate"] != "2026-11-03T00:00:00"
            or identity["isGeneralElection"] is not True):
        raise ValueError("Incorrect VT election identity")
    if len(source["d"]) != 1 or source["d"][0]["pid"] != 0:
        raise ValueError("Review VT party reporting scope")
    offices = source["d"][0]["o"]
    if (len(offices) != 1 or offices[0]["oid"] != 4
            or offices[0]["on"] != "REPRESENTATIVE TO CONGRESS" or offices[0]["vf"] != 1):
        raise ValueError("Incorrect VT House contest")
    office = offices[0]
    towns = {town["townId"]: town["townName"] for town in metadata["towns"]}
    crosswalk = {(r["townId"], r["repDistrict"], r["senateDistrict"]): r
                 for r in metadata["townDistricts"]}
    if len(towns) != len(metadata["towns"]) or len(crosswalk) != len(metadata["townDistricts"]):
        raise ValueError("Duplicate VT town or legislative-split identity")
    statewide = [r for r in office["cs"] if r["tid"] == 0]
    if len(statewide) != 1:
        raise ValueError("Missing or duplicate VT statewide rollup")
    parent = candidate_counts(statewide[0])
    regular_ids = {c["cid"] for c in statewide[0]["rc"]}
    observed, rows, town_contests = set(), [], defaultdict(list)
    totals = Counter()
    compact = {}
    for detail in office["cd"]:
        key = (detail["tn"], detail["repd"], detail["send"])
        if key in compact:
            raise ValueError("Duplicate VT compact display row")
        compact[key] = detail
    for node in office["cs"]:
        if node["tid"] == 0:
            continue
        key = (node["tid"], node["repd"], node["send"])
        if key in observed or key not in crosswalk or towns.get(node["tid"]) != node["tn"]:
            raise ValueError("VT reporting-unit identity does not match election metadata")
        observed.add(key)
        reference = crosswalk[key]
        if reference["townName"] != node["tn"]:
            raise ValueError("Incorrect VT town crosswalk")
        votes = candidate_counts(node)
        if {c["cid"] for c in node["rc"]} != regular_ids:
            raise ValueError("Missing or different VT regular candidate set")
        for cid, candidate in votes.items():
            if (cid not in parent or candidate["cn"] != parent[cid]["cn"]
                    or candidate["pn"] != parent[cid]["pn"]):
                raise ValueError("VT candidate identity differs from statewide rollup")
            totals[cid] += candidate["vc"]
        display_key = (node["tn"], node["repd"], node["send"])
        detail = compact.pop(display_key, None)
        if detail is None:
            raise ValueError("Missing VT compact display row")
        top = [office[f"cid{i}"] for i in [1, 2, 3]]
        if (any(count(detail[f"vc{i}"]) != votes[cid]["vc"] for i, cid in enumerate(top, 1))
                or count(detail["ovc"]) != node["sc"] - sum(votes[cid]["vc"] for cid in top)):
            raise ValueError("VT detailed and compact candidate counts do not reconcile")
        dem, rep = [sum(c["vc"] for c in votes.values() if c["pn"] == party)
                    for party in ["DEMOCRATIC", "REPUBLICAN"]]
        other = sum(c["vc"] for c in votes.values()) - dem - rep
        row = results.result(2026, "VT", str(reference["countyId"]),
            f'{node["tid"]}:{node["repd"]}:{node["send"]}', "U.S. House", dem, rep, other,
            "Official town/House-district/Senate-district reporting split; not a verified polling precinct.",
            HOUSE_URL, kind="town_legislative_split")
        row.update(town_id=node["tid"], town=node["tn"], county_name=reference["countyName"],
                   house_district=node["repd"], senate_district=node["send"],
                   reported_contest_total=node["sc"], overvotes=node["sv"], blank_votes=node["bv"])
        rows.append(row)
        town_contests[node["tid"]].append(row)
    if observed != set(crosswalk) or compact:
        raise ValueError("Incomplete or extra VT reporting-unit scope")
    if any(totals[cid] != candidate["vc"] for cid, candidate in parent.items()):
        raise ValueError("VT split and statewide candidate totals do not reconcile")
    for source_field, normalized in [("sc", "reported_contest_total"), ("sv", "overvotes"), ("bv", "blank_votes")]:
        if sum(r[normalized] for r in rows) != statewide[0][source_field]:
            raise ValueError("VT split and statewide contest accounting do not reconcile")
    statistics, seen = [], set()
    for node in turnout["d"]:
        tid = node["tid"]
        if tid in seen or towns.get(tid) != node["tn"] or tid not in town_contests:
            raise ValueError("VT municipal turnout identity does not match election metadata")
        seen.add(tid)
        registered, ballots = count(node["tvr"]), count(node["tvc"])
        districts, reported = count(node["tdis"]), count(node["tdisr"])
        if node["hl"]:
            raise ValueError("Review nested VT municipal turnout records before normalizing")
        flags = []
        contest_total = sum(r["reported_contest_total"] for r in town_contests[tid])
        if contest_total != ballots:
            flags.append("house_contest_total_differs_from_municipal_votes_cast")
        if districts == 0 or reported != districts or districts != len(town_contests[tid]):
            flags.append("incomplete_or_different_district_scope")
        if registered == 0 or ballots > registered:
            flags.append("missing_or_inconsistent_registration_denominator")
        statistics.append(dict(year=2026, state_code="VT", town_id=tid, town=node["tn"],
            reporting_unit_kind="municipality", registered_voters=registered,
            ballots=ballots, reported_house_contest_total=contest_total,
            districts=districts, districts_reporting=reported,
            registered_turnout_pct=100 * ballots / registered if not flags else None,
            denominator="source_reported_registered_voters_active_inactive_definition_unspecified",
            provisional=not identity["isOfficial"], quality_flags=flags,
            uninterpreted_source_tabs=count(node["tabs"]),
            source_url=f"{STATIC}elections/{GUID}-turnout-{STAMP}.json"))
    if seen != set(towns) or set(town_contests) != set(towns):
        raise ValueError("Incomplete VT municipal turnout scope")
    return rows, statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an existing VT review or complete archive")
    manifest = json.loads((args.source_cache / "sources.json").read_text())
    metadata = json.loads((args.source_cache / "election.json").read_bytes())
    expected = {"election.json": f"{STATIC}elections/{GUID}.json",
                "elections.json": f"{STATIC}elections/elections.json"}
    for tab, prefix in TABS.items():
        config = metadata[tab]
        if config["isEnable"] is not True:
            raise ValueError("Missing advertised VT results tab")
        expected[f"{prefix}-{STAMP}.json"] = STATIC + config["path"].replace("\\", "/")
    originals = {}
    for name, url in expected.items():
        raw = (args.source_cache / name).read_bytes()
        receipt = manifest[name]
        if (receipt["url"] != url or receipt["bytes"] != len(raw)
                or receipt["sha256"] != hashlib.sha256(raw).hexdigest()):
            raise ValueError("VT cached original changed: " + name)
        json.loads(raw)
        originals[name] = raw
    rows, statistics = vt_results(json.loads(originals[f"full-results-{STAMP}.json"]),
                                 metadata, json.loads(originals[f"turnOut-{STAMP}.json"]))
    if len(rows) != 283 or len(statistics) != 247:
        raise ValueError("VT reporting scope changed; review before publishing")
    args.output.mkdir(parents=True)
    (args.output / "originals").mkdir()
    for name, raw in originals.items():
        (args.output / "originals" / (name + ".gz")).write_bytes(gzip.compress(raw, mtime=0))
    text = io.StringIO()
    writer = csv.DictWriter(text, results.CSV_FIELDS + EXTRA_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (args.output / "results.csv.gz").write_bytes(gzip.compress(text.getvalue().encode(), mtime=0))
    (args.output / "municipal-participation.json.gz").write_bytes(gzip.compress(
        json.dumps(statistics, separators=(",", ":")).encode(), mtime=0))
    (args.output / "original-source-checksums.json").write_text(json.dumps(
        {name: manifest[name] for name in originals}, indent=2) + "\n")
    definitions = dict(source=APP_SOURCE,
        note="Field meanings verified against the normally served public app; copyrighted app code is not redistributed.",
        fields=dict(tvr="Registered Voters", tvc="Votes Cast", tdisr="Districts Reporting",
                    tdis="Total districts", tabs="Uninterpreted; retained only as a raw source value."),
        compact_other_counts="The compact display's ovc includes blank votes and overvotes; never use it as other-candidate votes.",
        registration_scope="Municipal source-reported registrations; active/inactive definition unspecified.",
        boundary_scope="No geography acquired or crosswalk validated; legislative splits are not verified polling precincts.")
    (args.output / "field-definitions.json").write_text(json.dumps(definitions, indent=2) + "\n")
    audit = dict(year=2026, state_code="VT", candidate_results="acquired_reconciled",
        boundaries="not_reviewed", join="withheld", validation="counts_passed_map_withheld",
        publication="full_counts_download_only", participation="acquired_municipal_counts_and_provisional_rates",
        complete="no", source_url=HOUSE_URL, sources={name: manifest[name]["url"] for name in originals},
        boundary_source="", reporting_units=len(rows), municipalities=len(statistics),
        reporting_unit_kind="town_legislative_split", county_id_namespace="Source countyId; not county FIPS.",
        source_updated=metadata["lastUpdatedDate"], official=metadata["electionDetails"]["isOfficial"],
        original_files=len(originals), original_bytes=sum(len(raw) for raw in originals.values()),
        candidate_totals={field: sum(row[field] for row in rows) for field in
                          ["democratic_votes", "republican_votes", "other_votes", "contest_votes"]},
        reported_contest_total=sum(r["reported_contest_total"] for r in rows),
        overvotes=sum(r["overvotes"] for r in rows), blank_votes=sum(r["blank_votes"] for r in rows),
        municipal_ballots=sum(r["ballots"] for r in statistics),
        municipal_registrations=sum(r["registered_voters"] for r in statistics),
        municipal_rates_withheld=sum(r["registered_turnout_pct"] is None for r in statistics),
        municipal_quality_flag_counts=dict(Counter(flag for r in statistics for flag in r["quality_flags"])),
        municipal_discrepancies=[r for r in statistics if r["quality_flags"]],
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-precinct-vermont-20261105/complete-vermont-2026-source-review.zip",
        notes="All 283 town/House-district/Senate-district reporting splits match the election metadata "
              "and reconcile every candidate, named write-in, blank and overvote to the statewide House rollup. "
              "The compact display's other column includes blanks/overvotes and is not used as candidate votes. "
              "These are not established polling precincts; no map or precinct turnout is published. "
              "Separate 247-town registration/ballot counts retain five House-accounting discrepancies "
              "and Colchester's different district count; all six affected municipal rates are withheld, not repaired. "
              "Remaining rates are provisional municipal "
              "registered-voter fractions, not citizen/resident turnout or demographic estimates. "
              "All nine complete original JSON feeds are retained, including all six enabled office tabs and turnout. "
              "Only the federal House counts and municipal turnout are normalized; other offices remain unreviewed. "
              "The generic SOS information page returned 403; the normal public results portal was accessible.",
        next_action="Acquire official 2026 town/legislative-split or polling geography with an explicit identity crosswalk; "
                    "do not map split counts onto whole towns. Resolve Colchester's district scope, five municipal ballot discrepancies and "
                    "registration definitions; reconcile the remaining preserved office tabs.")
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
