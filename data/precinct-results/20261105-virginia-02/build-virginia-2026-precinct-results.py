"""Map only supported Virginia 2026 precincts using the agency's current reference."""

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import zipfile

from shapely.geometry import mapping, shape
from shapely.ops import unary_union


SPEC = importlib.util.spec_from_file_location("virginia_geometry",
    Path(__file__).with_name("review-virginia-2026-reference-geometry.py"))
geometry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(geometry)
require = geometry.require
REFERENCE = "https://www.elections.virginia.gov/casting-a-ballot/redistricting/interactive-map/"
RESULTS = "https://enr.elections.virginia.gov/results/public/virginia/elections/2026-November-General"


def normalized_result(row, raw_id):
    candidates = json.loads(row["candidates"])
    votes = defaultdict(int)
    for candidate in candidates.values():
        value = geometry.native.native_count(candidate["votes"])
        party = candidate["party"]
        if party and party["abbreviation"] in {"D", "R"}:
            expected = {"D": "Democratic", "R": "Republican"}[party["abbreviation"]]
            require(geometry.native.english(party["name"]) == expected,
                    "Unreviewed native candidate party")
            votes[party["abbreviation"]] += value
        else:
            votes["other"] += value
    total = sum(votes.values())
    require(total == int(row["candidate_votes"]), "Changed native precinct candidate total")
    precinct = geometry.precinct_code(raw_id)
    return dict(year=2026, state_code="VA", state="Virginia",
        key="VA:" + row["locality_code"] + ":" + precinct + ":" + row["district"],
        county=row["locality"], county_code=row["locality_code"], precinct=row["precinct"],
        precinct_code=precinct, original_precinct_id=raw_id, precinct_uuid=row["precinct_uuid"],
        congressional_district=int(row["district"]), office="U.S. House",
        democratic_votes=votes["D"], republican_votes=votes["R"], other_votes=votes["other"],
        contest_votes=total, margin_pp=100 * (votes["D"] - votes["R"]) / total if total else None,
        source_url=RESULTS, native_detail_source=row["source"],
        ballot_scope="Unofficial published House counts. " + (
            "Precinct method vectors exhaust the corresponding locality/House summary at this snapshot. "
            if row["precinct_mode_allocation_complete"] == "True" else
            "County method residuals remain unallocated; this precinct vector may omit those modes. ")
            + "Unreported provisional and post-election methods are not final zeroes. "
            "Candidate counts are not turnout.",
        reporting_unit_kind="source_reporting_unit")


def qualify_current_reference(source):
    sources = json.loads((source / "sources.json").read_text())

    def load(key):
        return geometry.native.reports.verified(source, key, sources[key])

    page = load("official-current-boundary-map").decode()
    webmap = json.loads(load("official-linked-webmap-item"))
    data = json.loads(load("official-linked-webmap-data"))
    layer = json.loads(load("official-district-union-layer"))
    url = sources["official-district-union-layer"]["url"].split("?")[0]
    require(sources["official-current-boundary-map"]["url"] == REFERENCE
            and webmap["id"] in page
            and "maps showing the current election district and precinct boundaries" in page
            and webmap["orgId"] == "M3dium4ePYpmdT4B"
            and any(item.get("url") == url for item in data["operationalLayers"]),
            "Unreviewed official current-reference chain")
    edit = datetime.fromtimestamp(layer["editingInfo"]["lastEditDate"] / 1000, timezone.utc).isoformat()
    require("2026-01-01" <= edit[:10] <= "2026-11-03"
            and sources["official-current-boundary-map"]["fetched_at"].startswith("2026-"),
            "Reference is not the agency's pre-election-edited current 2026 snapshot")
    return dict(source_url=REFERENCE, layer_url=url, data_edit_utc=edit,
        scope="Agency's current reference captured during 2026 reporting, with pre-election 2026 "
              "data edits and literal 2026 precinct identities. Not certified election-day shapes.")


def build(review, expected_audit, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing immutable mapped snapshot overwrite")
    audit = geometry.audit(review)
    require(json.loads(json.dumps(audit)) == json.loads(expected_audit.read_text()),
            "Portable geometry audit changed")
    reference = qualify_current_reference(review / "current-reference-geometry")
    selected = {tuple(row["identity"]) for row in audit["precinct_eligibility"]
                if row["supported_candidate_subset"]}
    require(selected, "No supported precinct subset")
    originals = {}
    with (review / "earlier-report-review/precinct-counts.csv").open() as stream:
        for row in csv.DictReader(stream):
            originals[(row["locality_code"], row["precinct"])] = row["precinct_id"]
    with (review / "precinct-counts.csv").open() as stream:
        rows = [normalized_result(row, originals[(row["locality_code"], row["precinct"])])
                for row in csv.DictReader(stream)]
    require(len({row["key"] for row in rows}) == len(rows), "Duplicate normalized result identity")
    turnout = {}
    with (review / "precinct-turnout.csv").open() as stream:
        for row in csv.DictReader(stream):
            turnout[(row["locality_code"], row["precinct_uuid"])] = row
    polygons, object_ids = defaultdict(list), defaultdict(list)
    source = review / "current-reference-geometry"
    sources = json.loads((source / "sources.json").read_text())
    for key in sorted(k for k in sources if k.startswith("district-union-features-")):
        page = json.loads(geometry.native.reports.verified(source, key, sources[key]))
        for feature in page["features"]:
            p = feature["properties"]
            if not p["CountyFIPS"] or not p["PrcnctNum"]:
                continue
            identity = (p["CountyFIPS"], geometry.precinct_code(p["PrcnctNum"]))
            if identity in selected:
                require(geometry.fragment_issue(feature["geometry"]) is None,
                        "Unsupported selected fragment")
                polygons[identity].append(shape(feature["geometry"]))
                object_ids[identity].append(p["OBJECTID"])
    features, mapped_keys = [], set()
    for row in rows:
        identity = (row["county_code"], row["precinct_code"])
        if identity not in selected:
            continue
        require(identity not in mapped_keys, "Multiple selected House parts")
        mapped_keys.add(identity)
        polygon = unary_union(polygons[identity])
        require(polygon.is_valid and not polygon.is_empty, "Invalid selected dissolved precinct")
        stats = turnout[(row["county_code"], row["precinct_uuid"])]
        ballots = int(stats["ballots_cast"])
        flags = ["literal_native_counts_not_final_all_mode_turnout"]
        if row["contest_votes"] > ballots:
            flags.append("candidate_votes_exceed_native_reported_ballots")
        p = dict(row, match_status="matched", official_boundary=True,
            boundary_date="2026 official current reference; data edit " + reference["data_edit_utc"],
            boundary_provenance=reference["scope"] + " Only matching native fragments are dissolved. "
                "Numeric codes retain documented formatting differences; labels match literally "
                "ignoring case/whitespace. Null/invalid shapes, material overlaps, unmatched labels, "
                "virtual units, multi-district precincts and incomplete county/method scopes are withheld.",
            source_object_ids=sorted(object_ids[identity]),
            participation=dict(measure="reported_ballots_and_registration", ballots=ballots,
                registered=int(stats["registered_voters"]), reported_pct=None,
                basis="Separate native locality voterTurnout observation; no candidate-vote substitution.",
                quality="; ".join(flags)))
        features.append(dict(type="Feature", properties=p, geometry=mapping(polygon)))
    require(mapped_keys == selected, "Incomplete supported precinct mapping")
    output.mkdir(parents=True)

    def save(name, value):
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(value, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
        path.write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)

    shutil.copytree(review, output / "count-review")
    shutil.copyfile(expected_audit, output / "reference-geometry-audit.json")
    for name in [Path(__file__).name, "review-virginia-2026-reference-geometry.py",
                 "review-virginia-2026-locality-results.py", "review-virginia-2026-native-results.py"]:
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    save("results.json.gz", rows)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (output / "results.csv.gz").write_bytes(gzip.compress(stream.getvalue().encode(), mtime=0))
    save("participation.json.gz", [dict(row, year=int(row["year"]),
        voter_turnout=int(row["voter_turnout"]), ballots_cast=int(row["ballots_cast"]),
        registered_voters=int(row["registered_voters"]), turnout_rate=None)
        for row in turnout.values()])
    save("2026/VA.geojson.gz", dict(type="FeatureCollection", features=features))
    save("audit.json", dict(mapped_units=len(features), reporting_vectors=len(rows),
        supported_identity_set=sorted(selected), current_reference=reference,
        input_count_review_checksums_sha256=audit["input_checksums_sha256"],
        mapped_candidate_votes=sum(f["properties"]["contest_votes"] for f in features),
        all_native_counts_unchanged=True, rates_available=False, election_day_geometry_certified=False,
        geometry_audit_file="reference-geometry-audit.json",
        excluded_precincts=sum(bool(row["flags"]) for row in audit["precinct_eligibility"])))
    notes = ("Only " + str(len(features)) + " supported precincts are mapped, not all Virginia. "
        "Each has literal 2026 source IDs/names, valid nonoverlapping current-reference shapes, one "
        "nonvirtual House reporting unit and method vectors that exhaust its locality/House summary. "
        "Other precincts, missing county early/mail allocations and unreported methods are not repaired. "
        "The official current reference was edited September 22, 2026 and captured during reporting, "
        "not certified as election-day geometry. All 357 original-response files, all earlier full "
        "reports/demographics, unlocated method vectors, original boundaries and all exclusions remain "
        "in the complete download. Separate native ballot/registration observations have no inferred rates.")
    coverage = dict(file="2026/VA.geojson.gz", source_url=RESULTS, boundary_source=REFERENCE,
        partial=True, features=len(features),
        colored=sum(f["properties"]["margin_pp"] is not None for f in features),
        office="U.S. House", boundary_date="2026 current reference, not certified election-day shapes",
        notes=notes, next_action="Resolve withheld literal labels, invalid/null shapes, overlapping "
            "boundaries, split-district units and county early/mail allocations using authoritative "
            "sources. Never allocate votes or substitute candidate counts for participation.")
    save("index.json", dict(coverage={"2026": {"VA": coverage}}, result_rows=len(rows),
        participation_rows=len(turnout), complete_download=archive.name,
        metric="Candidate margins, not turnout or demographic participation.",
        attribution="Virginia Department of Elections; public current precinct reference and native ENR"))
    save("checksums.json", {p.relative_to(output).as_posix(): dict(bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(output.rglob("*")) if p.is_file()})
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as target:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                item = zipfile.ZipInfo(path.relative_to(output).as_posix(), (2026, 11, 5, 0, 0, 0))
                item.external_attr = 0o644 << 16
                target.writestr(item, path.read_bytes())
    return dict(mapped=len(features), colored=coverage["colored"], archive_bytes=archive.stat().st_size,
                archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["review", "geometry-audit", "output", "archive"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.review, args.geometry_audit, args.output, args.archive), indent=2))
