"""Reconcile DC 2026 plurality results and separate participation against its native map."""

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree


ORIGIN = "https://electionresults.dcboe.org"
SLUG = "2026-General-Election"
SOURCE = ORIGIN + "/election_results/" + SLUG
OFFICE = "CHAIRMAN OF THE COUNCIL OF THE DISTRICT OF COLUMBIA"
HEADERS = ["ElectionDate", "ElectionName", "ContestNumber", "ContestName",
           "PrecinctNumber", "WardNumber", "Candidate", "Party", "Votes"]
NONCANDIDATES = {"OVER VOTES", "UNDER VOTES"}
TOLERANCE = 1e-10
EXTRACTOR = r"""
const fs = require("node:fs"), acorn = require("acorn");
const ast = acorn.parse(fs.readFileSync(0, "utf8"), {ecmaVersion: "latest"});
const filename = "./" + process.argv[1], matches = [];
function walk(node) {
  if (!node || typeof node !== "object") return;
  if (node.type === "Property" && !node.computed && node.key.value === filename)
    matches.push(node.value.value);
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach(walk);
    else if (value && typeof value === "object") walk(value);
  }
}
walk(ast);
const call = ast.body.length === 1 && ast.body[0].expression;
if (!call || call.type !== "CallExpression" || call.callee.name !== "webpackJsonp"
    || matches.length !== 1 || !Number.isInteger(matches[0]))
  throw Error("Ambiguous native reference declaration");
const concat = call.arguments[1], base = concat?.callee?.object;
if (concat?.callee?.property?.name !== "concat" || base?.callee?.name !== "Array"
    || base.arguments.length !== 1 || !Number.isInteger(base.arguments[0].value)
    || concat.arguments.length !== 1 || concat.arguments[0].type !== "ArrayExpression")
  throw Error("Unknown native module inventory");
const fn = concat.arguments[0].elements[matches[0] - base.arguments[0].value];
const statement = fn?.body?.body;
const assignment = statement?.length === 1 && statement[0].expression;
if (fn?.type !== "FunctionExpression" || assignment?.type !== "AssignmentExpression"
    || assignment.operator !== "=" || assignment.left?.object?.name !== fn.params[0]?.name
    || assignment.left?.property?.name !== "exports" || assignment.left.computed)
  throw Error("Reference module is not a literal data export");
function literal(node) {
  if (node.type === "Literal" && !node.regex
      && (node.value === null || ["string", "boolean"].includes(typeof node.value)
          || typeof node.value === "number" && Number.isFinite(node.value))) return node.value;
  if (node.type === "UnaryExpression" && node.operator === "-"
      && node.argument.type === "Literal" && Number.isFinite(node.argument.value)
      && typeof node.argument.value === "number") return -node.argument.value;
  if (node.type === "ArrayExpression" && node.elements.every(Boolean))
    return node.elements.map(literal);
  if (node.type === "ObjectExpression") {
    const result = Object.create(null);
    for (const p of node.properties) {
      const key = p.key?.type === "Identifier" ? p.key.name : p.key?.value;
      if (p.type !== "Property" || p.kind !== "init" || p.method || p.computed
          || typeof key !== "string" || Object.hasOwn(result, key))
        throw Error("Nonliteral or duplicate reference property");
      result[key] = literal(p.value);
    }
    return result;
  }
  throw Error("Executable expression in native reference module");
}
console.log(JSON.stringify({module_id: matches[0], topology: literal(assignment.right)}));
"""


def extract_reference(bundle, filename):
    result = subprocess.run(["node", "-e", EXTRACTOR, filename], input=bundle,
                            capture_output=True, cwd=Path(__file__).resolve().parents[1])
    if result.returncode:
        raise ValueError("Native reference extraction failed: " + result.stderr.decode()[-1500:])
    return json.loads(result.stdout)


def topology_features(topology):
    if (topology.get("type") != "Topology" or set(topology.get("objects", {})) != {"precinct_octo"}
            or topology["objects"]["precinct_octo"].get("type") != "GeometryCollection"):
        raise ValueError("Wrong DC precinct topology object")
    transform = topology["transform"]
    scale, translate = transform["scale"], transform["translate"]
    if (len(scale) != 2 or len(translate) != 2
            or any(type(v) not in {int, float} or not math.isfinite(v) for v in scale + translate)
            or any(v <= 0 for v in scale)):
        raise ValueError("Invalid native topology transform")
    arcs = []
    for arc in topology["arcs"]:
        x, y, decoded = 0, 0, []
        for point in arc:
            if len(point) != 2 or any(type(v) is not int for v in point):
                raise ValueError("Invalid quantized native arc")
            x, y = x + point[0], y + point[1]
            decoded.append([x * scale[0] + translate[0], y * scale[1] + translate[1]])
        if len(decoded) < 2:
            raise ValueError("Empty native topology arc")
        arcs.append(decoded)

    def ring(indices):
        result = []
        for index in indices:
            if type(index) is not int or not 0 <= (index if index >= 0 else ~index) < len(arcs):
                raise ValueError("Invalid native topology arc identity")
            arc = arcs[index] if index >= 0 else arcs[~index][::-1]
            if result and result[-1] != arc[0]:
                raise ValueError("Discontinuous native topology ring")
            result.extend(arc if not result else arc[1:])
        if len(result) < 4 or result[0] != result[-1]:
            raise ValueError("Unclosed native topology ring")
        return result

    features = []
    for g in topology["objects"]["precinct_octo"]["geometries"]:
        if g["type"] not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Nonpolygonal native reference")
        coordinates = ([ring(r) for r in g["arcs"]] if g["type"] == "Polygon"
                       else [[ring(r) for r in polygon] for polygon in g["arcs"]])
        features.append(dict(type="Feature", properties=g["properties"],
                             geometry=dict(type=g["type"], coordinates=coordinates)))
    return features


def integer(value):
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value):
        return int(value)
    raise ValueError("Missing, negative or noninteger DC count")


def contest_counts(record):
    if (record["ContestNumber"] != 6 or record["OfficeName"] != OFFICE
            or record["IsRCV"] is not False):
        raise ValueError("Wrong DC plurality contest; RCV first ranks are not a winner")
    counts = {}
    for c in record["ElectionData"]:
        if c["Contestant"] in counts:
            raise ValueError("Duplicate native DC contestant")
        counts[c["Contestant"]] = integer(c["Votes"])
    return counts


def review_counts(raw, info, inventory, citywide, xml_raw, summary, precinct_map):
    ids = inventory["PrecinctNumberList"]
    if (info["ElectionName"] != "General Election" or info["ElectionCode"] != "G"
            or info["ElectionDate"] != "2026-11-03T00:00:00"
            or info["ElectionResultsTypeName"] != "Election Night Unofficial Results"
            or info["PrecintsJsonMap"] != "OCTO_VotingPrecinct_2019.json"
            or len(ids) != len(set(ids)) or any(type(p) is not int or p < 1 for p in ids)
            or len(ids) != info["TotalPrecincts"] or not 0 <= info["PrecinctsCounted"] <= len(ids)):
        raise ValueError("Wrong election or incomplete DC native precinct inventory")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    if reader.fieldnames != HEADERS:
        raise ValueError("Changed DC native CSV columns")
    data = defaultdict(dict)
    wards, seen, original_rows = {}, set(), 0
    for r in reader:
        if (set(r) != set(HEADERS) or any(v is None for v in r.values())
                or r["ElectionDate"] != "11/3/2026 12:00:00 AM"
                or r["ElectionName"] != "General Election"):
            raise ValueError("Malformed or wrong-election DC CSV row")
        pid, ward = integer(r["PrecinctNumber"]), integer(r["WardNumber"])
        key = (r["ContestNumber"], pid, r["Candidate"], r["Party"])
        if pid not in ids or ward not in range(1, 9) or key in seen or (
                pid in wards and wards[pid] != ward):
            raise ValueError("Unknown, duplicated or conflicting DC precinct row")
        seen.add(key)
        wards[pid] = ward
        value = integer(r["Votes"])
        original_rows += 1
        cid = r["ContestNumber"]
        if cid not in {"-2", "-1", "6"}:
            continue
        if cid in {"-2", "-1"}:
            expected = "REGISTERED VOTERS - TOTAL" if cid == "-2" else "BALLOTS CAST - TOTAL"
            if r["ContestName"] != expected or r["Candidate"] or r["Party"] != "CITYWIDE":
                raise ValueError("Invalid DC participation record identity")
            identity = cid
        else:
            if r["ContestName"] != OFFICE:
                raise ValueError("Wrong DC Council-chair contest identity")
            identity = r["Candidate"]
        if identity in data[pid]:
            raise ValueError("Duplicate DC precinct count identity")
        data[pid][identity] = (value, r["Party"])
    chairs = [r for r in citywide if r["ContestNumber"] == 6]
    if len(chairs) != 1:
        raise ValueError("Missing or ambiguous DC Council-chair aggregate")
    totals = contest_counts(chairs[0])
    candidate_parties = {c["Contestant"]: c["PartyCode"] for c in chairs[0]["ElectionData"]
                        if c["Contestant"] not in NONCANDIDATES}
    if Counter(candidate_parties.values()) != Counter({"DEM": 1, "REP": 1, "NPN": 1}):
        raise ValueError("Changed DC Council-chair candidate identities")
    if any(type(r["PrecinctNumber"]) is not int for r in precinct_map["wardPrecinctResults"]):
        raise ValueError("Invalid native DC precinct-map identity")
    native = {r["PrecinctNumber"]: r for r in precinct_map["wardPrecinctResults"]}
    if (len(native) != len(precinct_map["wardPrecinctResults"]) or set(native) != set(ids)
            or len(precinct_map["cityWideResults"]) != 1
            or contest_counts(precinct_map["cityWideResults"][0]) != totals or set(data) != set(ids)):
        raise ValueError("Incomplete or inconsistent DC precinct-map count inventory")
    rows, statistics, summed, accounting = [], [], Counter(), []
    for pid in sorted(ids):
        values = data[pid]
        if set(values) != set(totals) | {"-2", "-1"}:
            raise ValueError("Incomplete native DC precinct candidate/participation counts")
        if {c: values[c][0] for c in totals} != contest_counts(native[pid]):
            raise ValueError("DC CSV/independent native precinct counts differ")
        candidates = []
        for name, party in candidate_parties.items():
            if values[name][1] != party:
                raise ValueError("DC candidate party identity differs")
            candidates.append(dict(name=name, party=party, votes=values[name][0]))
        if any(values[name][1] for name in NONCANDIDATES):
            raise ValueError("Over/under votes cannot become party candidate votes")
        dem = sum(c["votes"] for c in candidates if c["party"] == "DEM")
        rep = sum(c["votes"] for c in candidates if c["party"] == "REP")
        total = sum(c["votes"] for c in candidates)
        ballots, registered = values["-1"][0], values["-2"][0]
        flags = []
        if registered < 20:
            flags.append("small_or_missing_registration")
        if ballots > registered or total > ballots:
            flags.append("inconsistent_source_counts")
        difference = ballots - total - sum(values[c][0] for c in NONCANDIDATES)
        if difference:
            accounting.append(dict(precinct=pid, ballots_minus_contest_accounting=difference))
        key = f"DC|11001|{pid}|6"
        statistics.append(dict(key=key, year=2026, state_code="DC", precinct=str(pid),
            measure="reported_ballots_and_registration", ballots=ballots, registered=registered,
            reported_pct=None if flags else 100 * ballots / registered,
            basis="Election-night reported ballots / source-registered voters, not final turnout "
                "or a citizen/resident denominator. Registration reference date not independently verified.",
            quality="; ".join(["Provisional November 3 snapshot; outstanding ballots remain",
                              *flags, *(["Separate local-contest accounting differs; no repair or allocation"]
                                         if difference else [])])))
        rows.append(dict(key=key, year=2026, state_code="DC", county="District of Columbia",
            county_code="11001", precinct=f"Precinct {pid}", precinct_code=str(pid), ward=wards[pid],
            source_contest_id="6", source_office=OFFICE, office="D.C. Council chair",
            democratic_votes=dem, republican_votes=rep, other_votes=total - dem - rep,
            contest_votes=total, overvotes=values["OVER VOTES"][0], undervotes=values["UNDER VOTES"][0],
            candidate_counts=json.dumps(candidates, separators=(",", ":"), sort_keys=True),
            margin_pp=100 * (dem - rep) / total if total else None, source_url=SOURCE,
            source_reporting_status=info["ElectionResultsTypeName"],
            source_updated_at=info["LastUpdated"]))
        summed.update({c: values[c][0] for c in totals})
    if dict(summed) != totals:
        raise ValueError("DC precinct candidate counts do not reconcile citywide")
    xml = ET.fromstring(xml_raw)
    if (xml.tag != "XmlExportViewModel" or xml.findtext("ElectionName") != "General Election"
            or xml.findtext("ElectionDate") != "2026-11-03T00:00:00"):
        raise ValueError("Wrong DC XML election identity")
    for name, expected in [(OFFICE, totals),
                           ("REGISTERED VOTERS - TOTAL", {"": sum(s["registered"] for s in statistics)}),
                           ("BALLOTS CAST - TOTAL", {"": sum(s["ballots"] for s in statistics)})]:
        contests = [c for c in xml.findall("ContestList/ContestDataExportViewModel")
                    if c.findtext("ContestName") == name]
        if len(contests) != 1:
            raise ValueError("Missing or ambiguous DC XML aggregate")
        entries = contests[0].findall("ElectionData/ElectionDataExportViewModel")
        counts = {c.findtext("Candidate", ""): integer(c.findtext("Votes")) for c in entries}
        if len(counts) != len(entries) or counts != expected:
            raise ValueError("DC CSV/XML aggregate reconciliation failed")
    if (summary["SummaryType"] != "c" or summary["WardNumber"] is not None
            or summary["PrecinctNumber"] is not None or summary["Party"] is not None
            or integer(summary["RegisteredVoters"]) != sum(s["registered"] for s in statistics)
            or integer(summary["TotalBallotsCast"]) != sum(s["ballots"] for s in statistics)
            or sum(integer(summary[k]) for k in
                   ["ElectionDayVoters", "EarlyVotes", "AbsenteeSpecialBallotVotes"])
            != summary["TotalBallotsCast"]):
        raise ValueError("DC independently reported participation aggregate differs")
    return rows, statistics, dict(original_csv_rows=original_rows, reporting_units=len(ids),
        candidate_totals=totals, registered=summary["RegisteredVoters"], ballots=summary["TotalBallotsCast"],
        separate_contest_accounting_differences=accounting,
        provisional_reported_fractions=sum(s["reported_pct"] is not None for s in statistics),
        final_turnout_rates=0, demographic_rates=0, rcv_first_rank_contests_not_mapped=True)


def mapped_precincts(rows, statistics, features):
    expected = {r["precinct_code"]: r for r in rows}
    stats = {s["key"]: s for s in statistics}
    if len(expected) != len(rows) or len(stats) != len(statistics) or set(stats) != {r["key"] for r in rows}:
        raise ValueError("Duplicate or differing DC result/participation identities")
    polygons, seen_ids = {}, set()
    for f in features:
        p = f["properties"]
        match = re.fullmatch(r"Precinct ([1-9][0-9]*)", p["NAME"])
        if (not match or match[1] not in expected or match[1] in polygons
                or type(p["OBJECTID"]) is not int or p["OBJECTID"] in seen_ids):
            raise ValueError("Unknown or duplicate DC native reference identity")
        polygon = shape(f["geometry"])
        if (polygon.is_empty or not polygon.is_valid or polygon.geom_type not in {"Polygon", "MultiPolygon"}
                or polygon.area <= 0 or not all(math.isfinite(v) for v in polygon.bounds)
                or not (-77.2 < polygon.bounds[0] <= polygon.bounds[2] < -76.8
                        and 38.7 < polygon.bounds[1] <= polygon.bounds[3] < 39.1)):
            raise ValueError("Invalid or wrongly projected DC reference geometry")
        polygons[match[1]] = (polygon, p)
        seen_ids.add(p["OBJECTID"])
    if set(polygons) != set(expected):
        raise ValueError("Complete DC reporting/reference sets differ")
    values = [value[0] for value in polygons.values()]
    codes = list(polygons)
    tree = STRtree(values)
    overlaps, masks = [], defaultdict(list)
    for i, polygon in enumerate(values):
        for j in tree.query(polygon, predicate="intersects"):
            if j <= i:
                continue
            intersection = polygon.intersection(values[j])
            if intersection.area > TOLERANCE:
                overlaps.append(dict(left=codes[i], right=codes[j],
                                     area_degrees_squared=intersection.area))
                masks[codes[i]].append(intersection)
                masks[codes[j]].append(intersection)
    mapped, masked, withheld, mask_features = [], [], [], []
    for code, row in expected.items():
        polygon, native = polygons[code]
        if code in masks:
            ambiguous = unary_union(masks[code])
            record = dict(key=row["key"], area_degrees_squared=ambiguous.area,
                          fraction_of_reference_geometry=ambiguous.area / polygon.area)
            masked.append(record)
            mask_features.append(dict(type="Feature", properties=record, geometry=mapping(ambiguous)))
            polygon = polygon.difference(ambiguous)
            if polygon.is_empty:
                withheld.append(code)
                continue
            if not polygon.is_valid or polygon.geom_type not in {"Polygon", "MultiPolygon"}:
                raise ValueError("Invalid DC overlap-masked reporting-unit geometry")
        properties = dict(row, participation=stats[row["key"]], match_status="matched",
            official_boundary=True, source_object_ids=[native["OBJECTID"]],
            boundary_date="2019-named reference explicitly selected by the 2026 official app",
            boundary_provenance="DCBOE 2026 election metadata explicitly selects "
                "OCTO_VotingPrecinct_2019.json, embedded in its native statistics bundle. "
                "Complete native precinct sets match; no newly surveyed or certified 2026 geography "
                "or cross-election boundary stability claimed.",
            ballot_scope="Election-night Council-chair plurality counts, not RCV first ranks. "
                "Separate provisional ballots and registered voters are not candidate votes, "
                "final turnout or demographic participation.",
            quality_flags="provisional;official_app_reference_not_new_survey")
        if code in masks:
            properties["geometry_scope"] = "Reference geometry with overlapping strips withheld"
            properties["boundary_provenance"] += (
                " Ambiguous strips shared with another reference precinct are excluded from both. "
                "Counts still describe the entire precinct, never an allocation to clipped areas. "
                "The full original reference and excluded-area mask remain downloadable.")
        mapped.append(dict(type="Feature", properties=properties, geometry=mapping(polygon)))
    output_polygons = [shape(f["geometry"]) for f in mapped]
    tree = STRtree(output_polygons)
    for i, polygon in enumerate(output_polygons):
        for j in tree.query(polygon, predicate="intersects"):
            if j > i and polygon.intersection(output_polygons[j]).area > TOLERANCE:
                raise ValueError("DC reference overlap remains after ambiguous-strip withholding")
    return mapped, dict(mapped_units=len(mapped), reference_features=len(features),
        all_reference_overlap_pairs=overlaps, mapped_cross_precinct_overlaps=0,
        overlap_tolerance_degrees_squared=TOLERANCE,
        topology_repairs=[], masked_reporting_units=masked, withheld_units=withheld,
        ambiguity_mask=dict(type="FeatureCollection", features=mask_features))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["cache-root", "output", "archive"]:
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable DC snapshot")
    sources, originals, urls = {}, {}, {}
    for p in sorted(args.cache_root.glob("official-*")):
        if p.name.endswith(".receipt.json") or not p.is_file():
            continue
        raw = p.read_bytes()
        receipt = json.loads(p.with_name(p.name + ".receipt.json").read_bytes())
        if (receipt["status"] != 200 or receipt["bytes"] != len(raw)
                or receipt["sha256"] != hashlib.sha256(raw).hexdigest()
                or not receipt["url"].startswith((ORIGIN + "/", "https://dcboe.org/"))
                or receipt["url"] in urls):
            raise ValueError("Changed, duplicate or wrong-origin DC original: " + p.name)
        sources[p.name], originals[p.name], urls[receipt["url"]] = receipt, raw, p.name

    def raw(path):
        return originals[urls[ORIGIN + path]]

    def native(path):
        return json.loads(raw(path))

    info = native("/electionResults/getElectionInfo/" + SLUG)
    if not originals[urls[info["PdfLink"]]].startswith(b"%PDF-"):
        raise ValueError("Missing or invalid complete declared DC PDF original")
    rows, statistics, audit = review_counts(
        originals[urls[info["CsvLink"]]], info, native("/cityWide/getWardPrecinct/" + SLUG),
        native("/cityWide/getCityWide/" + SLUG), originals[urls[info["XmlLink"]]],
        native("/cityWide/getVoterSummaryInfo/" + SLUG),
        native("/mapStats/getMapDetails/" + SLUG + "/6/false"))
    bundle_name = next(n for n, s in sources.items()
                       if re.fullmatch(ORIGIN + r"/static/js/0\.[a-z0-9]+\.chunk\.js", s["url"]))
    extracted = extract_reference(originals[bundle_name], info["PrecintsJsonMap"])
    mapped, geometry_audit = mapped_precincts(rows, statistics, topology_features(extracted["topology"]))
    audit.update(geometry_audit, original_files=len(originals),
                 original_bytes=sum(map(len, originals.values())),
                 reference_module_id=extracted["module_id"],
                 reference_filename=info["PrecintsJsonMap"], reference_bundle=bundle_name)
    notes = ("DC Council-chair plurality margins, not the RCV delegate contest or a federal House "
        "result. Complete precinct candidate rows reconcile with native per-precinct JSON and "
        "citywide JSON/XML. Separate ballots/registration reconcile independently; displayed "
        "fractions are provisional election-night shares, not final turnout or demographic rates. "
        "Local-contest accounting differences remain in the audit, never repaired or allocated. "
        "The official 2026 app explicitly selects its 2019-named embedded precinct reference; "
        "this is not newly surveyed/certified 2026 geography or a cross-election stability claim. "
        "Three source-boundary overlaps affect five precincts: ambiguous strips are withheld "
        "from both precincts, not assigned. Counts still describe whole precincts, never clipped-area "
        "allocations. Full original boundaries and the excluded-area mask are downloadable. "
        "All complete originals, including every CSV contest, XML/PDF and native reference bundle, "
        "are retained with receipts. Outstanding ballots and source/reference review remain.")
    args.output.mkdir(parents=True)

    def save(name, value):
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        path.write_bytes(gzip.compress(body, mtime=0) if name.endswith(".gz") else body)

    for name, body in originals.items():
        p = args.output / "originals" / (name + ".gz")
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(gzip.compress(body, mtime=0))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (args.output / "results.csv.gz").write_bytes(gzip.compress(stream.getvalue().encode(), mtime=0))
    save("participation.json.gz", statistics)
    save("reference-topology.json.gz", extracted["topology"])
    save("2026/DC.geojson.gz", dict(type="FeatureCollection", features=mapped))
    save("2026/DC-ambiguous-reference-areas.geojson.gz", audit.pop("ambiguity_mask"))
    save("audit.json", audit)
    save("sources.json", sources)
    save("index.json", dict(coverage={"2026": {"DC": dict(file="2026/DC.geojson.gz",
        source_url=SOURCE, boundary_source=sources[bundle_name]["url"], partial=True,
        features=len(mapped), colored=sum(f["properties"]["contest_votes"] > 0 for f in mapped),
        office="D.C. Council chair", notes=notes,
        boundary_date="2019-named reference selected by the official 2026 app",
        participation="acquired_precinct_counts_and_registration",
        next_action="Review outstanding ballots and updated certification; verify reference changes "
            "and all native contest-accounting differences; acquire group-specific denominators.")}},
        result_rows=len(rows), participation_rows=len(statistics),
        complete_download=args.archive.name, metric=notes))
    save("checksums.json", {str(p.relative_to(args.output)): dict(bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(args.output.rglob("*")) if p.is_file()})
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for p in sorted(args.output.rglob("*")):
            if p.is_file():
                item = zipfile.ZipInfo(str(p.relative_to(args.output)), (2026, 11, 5, 0, 0, 0))
                item.external_attr = 0o100644 << 16
                archive.writestr(item, p.read_bytes())
    print(json.dumps(dict(output=str(args.output), archive=str(args.archive),
                          archive_bytes=args.archive.stat().st_size,
                          archive_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest(), **audit)))


if __name__ == "__main__":
    main()
