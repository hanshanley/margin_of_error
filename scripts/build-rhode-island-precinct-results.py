"""Map Rhode Island 2026 counts only where complete town sets match the attributed decade reference."""

import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import zipfile

from shapely.geometry import mapping
from shapely.strtree import STRtree


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


review = module("review-rhode-island-precinct-results")
geometry = module("build-north-dakota-precinct-results")
SERVICE = ("https://services2.arcgis.com/S8zZg9pg23JUEexQ/ArcGIS/rest/services/"
           "BND_Voting_Precincts_2022/FeatureServer")
ITEM = "9104ca2e5e9b4cdb9985e8935ef2514d"
ATTRIBUTION = ("RIGIS; Election Data Services Inc; each Rhode Island city and town Board of "
               "Canvassers; Rhode Island Department of State Elections Division")
TOLERANCE = 1e-10


def mapped_precincts(rows, boundary):
    if (boundary.get("exceededTransferLimit") or boundary.get("geometryType") != "esriGeometryPolygon"
            or boundary.get("spatialReference", {}).get("wkid") != 4326):
        raise ValueError("Incomplete or incorrectly projected Rhode Island boundaries")
    reporting, excluded, problems = defaultdict(dict), [], defaultdict(list)
    seen_rows = set()
    for row in rows:
        if (row["key"] in seen_rows or row["state_code"] != "RI" or row["year"] != 2026
                or row["source_contest_id"] not in review.CONTESTS):
            raise ValueError("Duplicate or wrong Rhode Island result identity")
        seen_rows.add(row["key"])
        town = row["locality"]
        if town == "Federal" or re.search(r"\bLIMITED\b", row["precinct"], re.I):
            excluded.append(row["key"])
            continue
        reporting[town]
        match = re.search(r"\((.+) ([0-9]{4})\)$", row["precinct"])
        if (not match or match[1] != town.upper() or row["source_is_virtual"] is not False):
            problems[town].append("unverified_native_label_or_virtual_scope")
            continue
        code = match[2]
        if code in reporting[town]:
            raise ValueError("Ambiguous Rhode Island town/precinct identity across House contests")
        reporting[town][code] = row
    reference, polygons, attributes, repairs, seen = defaultdict(dict), {}, {}, [], set()
    for feature in boundary["features"]:
        p = feature["attributes"]
        oid, town, code = p["OBJECTID"], p["TOWN"], p["DISTRICT"]
        if type(oid) is not int or oid in seen or town not in reporting:
            raise ValueError("Duplicate or unknown Rhode Island reference identity")
        seen.add(oid)
        if code in reference[town]:
            raise ValueError("Duplicate Rhode Island reference precinct")
        reference[town][code] = p
        attributes[oid] = p
        if (not isinstance(code, str) or not re.fullmatch(r"[0-9]{4}", code)
                or type(p["Congress"]) is not int or p["Congress"] not in {1, 2}
                or p["DISTRICTN"] != int(code)):
            problems[town].append("unassigned_or_inconsistent_reference_identity")
        try:
            polygon, repair = geometry.esri_polygon(feature["geometry"]["rings"])
        except ValueError as error:
            problems[town].append("invalid_reference_geometry: " + str(error))
            continue
        polygons[oid] = polygon
        if repair:
            repairs.append(dict(object_id=oid, **repair))
    ids, values = list(polygons), list(polygons.values())
    tree, overlaps = STRtree(values), []
    for i, polygon in enumerate(values):
        for j in tree.query(polygon, predicate="intersects"):
            if j <= i:
                continue
            area = polygon.intersection(values[j]).area
            if area > TOLERANCE:
                left, right = attributes[ids[i]], attributes[ids[j]]
                overlaps.append(dict(left=ids[i], right=ids[j], area_degrees_squared=area))
                for town in (left["TOWN"], right["TOWN"]):
                    problems[town].append("overlapping_reference_geometry")
    mapped, audits = [], {}
    for town, expected in sorted(reporting.items()):
        actual = reference[town]
        reasons = set(problems[town])
        if expected.keys() != actual.keys():
            reasons.add("different_complete_town_reporting_reference_sets")
        conflicts = [expected[k]["key"] for k in expected.keys() & actual.keys()
                     if actual[k]["Congress"] != int(expected[k]["source_contest_id"]) - 1]
        if conflicts:
            reasons.add("conflicting_explicit_congressional_district")
        audits[town] = dict(exact=not reasons, reasons=sorted(reasons),
            reporting_units=len(expected), reference_units=len(actual),
            reporting_only=sorted(expected.keys() - actual.keys()),
            boundary_only=sorted(actual.keys() - expected.keys()),
            congressional_conflicts=sorted(conflicts))
        if reasons:
            continue
        for code, row in expected.items():
            p = actual[code]
            margin = (100 * (row["democratic_votes"] - row["republican_votes"]) / row["contest_votes"]
                      if row["contest_votes"] else None)
            properties = dict(row, county=town, precinct_code=code, match_status="matched",
                margin_pp=margin, source_object_ids=[p["OBJECTID"]], official_boundary=True,
                congressional_district=str(p["Congress"]), reference_precinct=code,
                ballot_scope="Native Election Day, Early Voting and Mail Ballots candidate counts. "
                    "Federal and limited-only reporting units are retained separately, never allocated. "
                    "Candidate votes are not ballots cast, turnout or demographic participation.",
                boundary_date="2022-2032 RIGIS reference; not a new 2026 survey",
                quality_flags="decade_reference;precinct_rates_withheld",
                boundary_provenance=ATTRIBUTION + ". The source explicitly recommends this "
                    "2022-redistricting reference for 2022-2032 elections and warns of possible "
                    "later changes. Complete town precinct sets and explicit House districts match "
                    "the literal 2026 result labels. Federal/limited-only units are withheld, not "
                    "allocated. Inconsistent towns and unassigned reference areas remain state-colored. "
                    "No boundary stability, certified geography, precinct turnout or demographics inferred.")
            mapped.append(dict(type="Feature", properties=properties,
                               geometry=mapping(polygons[p["OBJECTID"]])))
    return mapped, dict(towns=audits, source_features=len(seen), topology_repairs=repairs,
        all_reference_overlap_pairs=overlaps, overlap_tolerance_degrees_squared=TOLERANCE,
        coordinate_grid_degrees=geometry.GRID, excluded_reporting_units=excluded,
        withheld_units=sorted(seen_rows - {f["properties"]["key"] for f in mapped}),
        mapped_units=len(mapped), reporting_units=len(rows), rates_available=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("review-directory", "boundaries-cache", "output", "archive"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable Rhode Island mapped snapshot")
    count_root = args.review_directory
    for name, receipt in json.loads((count_root / "checksums.json").read_bytes()).items():
        raw = (count_root / name).read_bytes()
        if len(raw) != receipt["bytes"] or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed Rhode Island immutable count review: " + name)
    count_sources = json.loads((count_root / "sources.json").read_bytes())
    parent_name = next(n for n, r in count_sources.items() if r["url"] == review.API)
    original = lambda n: json.loads(gzip.decompress((count_root / "originals" / (n + ".gz")).read_bytes()))
    rows, statistics, reconciliation = review.review(original("official-media-export.json"), original(parent_name))
    csv_output = io.StringIO(newline="")
    writer = csv.DictWriter(csv_output, list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    audit = json.loads((count_root / "audit.json").read_bytes())
    if (gzip.decompress((count_root / "results.csv.gz").read_bytes()).decode() != csv_output.getvalue()
            or original(parent_name)["election"]["electionDate"] != "2026-11-03"
            or json.loads(gzip.decompress((count_root / "participation.json.gz").read_bytes())) != statistics
            or audit["reconciliation"] != reconciliation or audit["rates_available"] != 0):
        raise ValueError("Rhode Island count review differs from independently reconciled originals")
    cache, sources, originals = args.boundaries_cache, {}, {}
    names = ["service.json", "layer.json", "item.json", "ids.json"]
    ids = json.loads((cache / "ids.json").read_bytes())["objectIds"]
    if not ids or len(ids) != len(set(ids)) or any(type(i) is not int for i in ids):
        raise ValueError("Incomplete or duplicate Rhode Island reference ID response")
    for start in range(0, len(ids), 150):
        names += [f"features-{start}.json", f"geographic-features-{start}.json"]
    for name in names:
        raw = (cache / name).read_bytes()
        receipt = json.loads((cache / (name + ".source.json")).read_bytes())
        expected = ("https://www.arcgis.com/sharing/rest/content/items/" + ITEM if name == "item.json"
                    else SERVICE if name == "service.json" else SERVICE + "/0" if name == "layer.json"
                    else SERVICE + "/0/query")
        if (receipt["url"].split("?")[0] != expected or len(raw) != receipt["bytes"]
                or hashlib.sha256(raw).hexdigest() != receipt["sha256"]):
            raise ValueError("Rhode Island reference receipt mismatch: " + name)
        sources[name], originals[name] = receipt, raw
    item, layer = json.loads(originals["item.json"]), json.loads(originals["layer.json"])
    if (item["id"] != ITEM or item["owner"] != "URIEDC_RIGIS" or item["access"] != "public"
            or item["url"].casefold() != SERVICE.casefold() or layer["serviceItemId"] != ITEM
            or "2022 though 2032" not in layer["description"]
            or "Please acknowledge both RIGIS and the primary producer(s)" not in item["licenseInfo"]):
        raise ValueError("Wrong Rhode Island decade reference identity, scope or terms")
    exports = []
    for prefix, crs in [("features-", 102730), ("geographic-features-", 4326)]:
        features = []
        for start in range(0, len(ids), 150):
            part = json.loads(originals[f"{prefix}{start}.json"])
            if (part.get("exceededTransferLimit") or part["geometryType"] != "esriGeometryPolygon"
                    or part["spatialReference"]["wkid"] != crs):
                raise ValueError("Incomplete or wrongly projected Rhode Island reference")
            features.extend(part["features"])
        if sorted(f["attributes"]["OBJECTID"] for f in features) != sorted(ids):
            raise ValueError("Rhode Island reference export/ID sets differ")
        exports.append(features)
    if ({f["attributes"]["OBJECTID"]: f["attributes"] for f in exports[0]}
            != {f["attributes"]["OBJECTID"]: f["attributes"] for f in exports[1]}):
        raise ValueError("Rhode Island native/geographic reference identities differ")
    mapped, audit = mapped_precincts(rows, dict(geometryType="esriGeometryPolygon",
        spatialReference=dict(wkid=4326), features=exports[1]))
    if not mapped:
        raise ValueError("No verified Rhode Island precinct geometry")
    args.output.mkdir(parents=True)

    def save(name, value):
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        path.write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)

    shutil.copytree(count_root, args.output / "count-review")
    for name in ["results.csv.gz", "participation.json.gz"]:
        shutil.copyfile(count_root / name, args.output / name)
    (args.output / "originals").mkdir()
    for name, raw in originals.items():
        (args.output / "originals" / (name + ".gz")).write_bytes(gzip.compress(raw, mtime=0))
    save("2026/RI.geojson.gz", dict(type="FeatureCollection", features=mapped))
    save("audit.json", audit)
    save("sources.json", sources)
    notes = (f"{len(mapped)} native House units map only where complete town precinct sets and explicit "
        "congressional districts match the literal 2026 labels. " + ATTRIBUTION + ". "
        "The 2022-redistricting reference is explicitly recommended for 2022-2032 elections, not a "
        "newly surveyed or certified 2026 boundary snapshot. Entire inconsistent towns are withheld. "
        "Federal and limited-only votes remain in all complete source/result tables, never allocated "
        "to polygons. Missing areas retain state result colors. Separate locality ballot/registration "
        "observations are not precinct denominators; all precinct rates remain withheld. Complete "
        "native/geographic original features, attribution/terms, count originals and audits included.")
    coverage = dict(file="2026/RI.geojson.gz", source_url=review.SOURCE,
        boundary_source=SERVICE + "/0", partial=True, features=len(mapped),
        colored=sum(f["properties"]["margin_pp"] is not None for f in mapped),
        office="U.S. House", boundary_date="2022-2032 RIGIS election reference", notes=notes,
        next_action="Resolve all withheld town/reference differences, verify subsequent local boundary "
            "changes, retain Federal/limited-only scope and obtain actual precinct participation denominators.")
    save("index.json", dict(coverage={"2026": {"RI": coverage}}, result_rows=len(rows),
        participation_rows=len(statistics), complete_download=args.archive.name,
        metric="Candidate margins are not participation; locality counts never become precinct rates.",
        attribution=ATTRIBUTION, boundary_item="https://www.arcgis.com/home/item.html?id=" + ITEM))
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
    print(json.dumps(dict(mapped=len(mapped), exact_towns=sum(t["exact"] for t in audit["towns"].values()),
        colored=coverage["colored"], overlap_pairs=len(audit["all_reference_overlap_pairs"]),
        archive_bytes=args.archive.stat().st_size), indent=2))


if __name__ == "__main__":
    main()
