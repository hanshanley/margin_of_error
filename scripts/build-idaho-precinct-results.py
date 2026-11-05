"""Map Idaho 2026 returns only where complete county identities and geometry agree."""

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
import re
import shutil
import zipfile

from shapely.geometry import mapping
from shapely.strtree import STRtree

spec = importlib.util.spec_from_file_location(
    "id_geometry", Path(__file__).with_name("build-north-dakota-precinct-results.py"))
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)
ITEM = "0b4fbe4f3104487da8bc5087f9321705"
SERVICE = ("https://services1.arcgis.com/CNPdEkvnGl65jCX8/arcgis/rest/services/"
           "Idaho_Voting_Precincts_Precinct_Boundaries_-_Master_Data_-_DO_NOT_SHARE_view/FeatureServer")
OFFICIAL = "https://voteidaho.gov/data-and-dashboards/"
ELECTION_MS = int(datetime(2026, 11, 3, tzinfo=timezone.utc).timestamp() * 1000)
TOLERANCE = 1e-10


def precinct_identity(label):
    if not isinstance(label, str) or not label.strip():
        raise ValueError("Missing Idaho precinct name")
    tokens = re.findall(r"[a-z]+|[0-9]+", label.casefold().replace("'", ""))
    if not tokens:
        raise ValueError("Empty Idaho textual precinct identity")
    return tuple(int(token) if token.isdigit() else token for token in tokens)


def mapped_precincts(rows, participation, boundary):
    if (boundary.get("exceededTransferLimit") or boundary.get("geometryType") != "esriGeometryPolygon"
            or boundary.get("spatialReference", {}).get("wkid") != 4326):
        raise ValueError("Incomplete or incorrectly projected Idaho boundaries")
    statistics = {r["key"]: r for r in participation}
    if len(statistics) != len(participation) or set(statistics) != {r["key"] for r in rows}:
        raise ValueError("Idaho result/participation identities differ")
    reporting, excluded = defaultdict(dict), []
    for row in rows:
        if not row["county"].endswith(" County"):
            raise ValueError("Unknown Idaho county-name convention")
        county = row["county"][:-7]
        reporting[county]
        if row["reporting_unit_kind"] == "pooled_absentee_or_early_unit":
            excluded.append(row["key"])
            continue
        key = precinct_identity(row["precinct"])
        if key in reporting[county]:
            raise ValueError("Idaho reporting identities collide after punctuation/padding normalization")
        reporting[county][key] = row
    reference, polygons, attributes, repairs = defaultdict(dict), {}, {}, []
    invalid, inactive, seen = defaultdict(list), [], set()
    for feature in boundary["features"]:
        p = feature["attributes"]
        oid, county = p["OBJECTID"], p["COUNTY"]
        if (type(oid) is not int or oid in seen or county not in reporting
                or p["ACTIVE"] not in {"Y", "N"}
                or type(p["DATE_ACT"]) is not int or type(p["DATE_INACT"]) is not int
                or p["DATE_ACT"] >= p["DATE_INACT"]):
            raise ValueError("Duplicate or unknown Idaho boundary identity/activity interval")
        seen.add(oid)
        if not p["DATE_ACT"] <= ELECTION_MS < p["DATE_INACT"]:
            inactive.append(oid)
            continue
        key = precinct_identity(p["PCNCT_NME"])
        if key in reference[county] or str(p["CONGR_DIST"]) not in {"1", "2"}:
            raise ValueError("Ambiguous Idaho reference precinct or congressional district")
        reference[county][key] = p
        attributes[oid] = p
        try:
            polygon, repair = geometry.esri_polygon(feature["geometry"]["rings"])
        except ValueError as error:
            invalid[county].append(dict(object_id=oid, reason=str(error)))
            continue
        polygons[oid] = polygon
        if repair:
            repairs.append(dict(object_id=oid, **repair))
    ids, values = list(polygons), list(polygons.values())
    tree, overlaps, conflicts = STRtree(values), [], set(invalid)
    for i, polygon in enumerate(values):
        for j in tree.query(polygon, predicate="intersects"):
            if j <= i:
                continue
            area = polygon.intersection(values[j]).area
            if area > TOLERANCE:
                left, right = attributes[ids[i]], attributes[ids[j]]
                overlaps.append(dict(left=ids[i], right=ids[j], left_county=left["COUNTY"],
                    right_county=right["COUNTY"], area_degrees_squared=area))
                conflicts.update([left["COUNTY"], right["COUNTY"]])
    audits, mapped = {}, []
    for county, expected in sorted(reporting.items()):
        actual = reference[county]
        reasons = []
        if expected.keys() != actual.keys():
            reasons.append("different_complete_county_reporting_reference_sets")
        district_conflicts = [expected[k]["key"] for k in expected.keys() & actual.keys()
                              if str(actual[k]["CONGR_DIST"]) != expected[k]["congressional_district"]]
        if district_conflicts:
            reasons.append("different_explicit_congressional_district")
        if county in conflicts:
            reasons.append("invalid_or_overlapping_reference_geometry")
        audits[county] = dict(exact=not reasons, reasons=reasons, reporting_units=len(expected),
            reference_units=len(actual),
            reporting_only=sorted(expected[k]["precinct"] for k in expected.keys() - actual.keys()),
            boundary_only=sorted(actual[k]["PCNCT_NME"] for k in actual.keys() - expected.keys()),
            district_conflicts=sorted(district_conflicts), invalid_geometry=invalid.get(county, []))
        if reasons:
            continue
        for key, row in expected.items():
            p = actual[key]
            statistics_row = statistics[row["key"]]
            properties = dict(row, match_status="matched", official_boundary=True,
                reference_precinct_name=p["PCNCT_NME"], reference_state_precinct_id=p["STATE_PR_ID"],
                reference_county_precinct_id=p["CNTY_PR_ID"], source_object_ids=[p["OBJECTID"]],
                boundary_date="2026 primary/general-election reference",
                boundary_provenance="Official Idaho Secretary of State 2026 reference. Complete county "
                    "sets match by precinct name after case, punctuation and numeric-padding normalization; "
                    "token order and spelling are unchanged. Explicit congressional districts also agree. "
                    "No ID decoding, aliases, pooled-ballot allocation, boundary clipping or borrowed geography. "
                    "Whole counties with conflicting geometry or reporting scope are withheld.",
                participation=dict(statistics_row, measure="reported_ballots_and_registration",
                    quality="; ".join(statistics_row["quality_flags"]) or "Provisional source-defined fraction"))
            mapped.append(dict(type="Feature", properties=properties,
                               geometry=mapping(polygons[p["OBJECTID"]])))
    return mapped, dict(counties=audits, source_features=len(seen), inactive_features=inactive,
        topology_repairs=repairs, all_reference_overlap_pairs=overlaps,
        overlap_tolerance_degrees_squared=TOLERANCE, coordinate_grid_degrees=geometry.GRID,
        mapped_units=len(mapped), reporting_units=len(rows), excluded_pooled_reporting_units=excluded,
        withheld_units=sorted({r["key"] for r in rows} - {f["properties"]["key"] for f in mapped}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-directory", required=True, type=Path)
    parser.add_argument("--boundaries-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable Idaho mapped snapshot")
    for name, receipt in json.loads((args.review_directory / "checksums.json").read_text()).items():
        raw = (args.review_directory / name).read_bytes()
        if len(raw) != receipt["bytes"] or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError("Idaho original count review changed: " + name)
    rows = list(csv.DictReader(io.StringIO(gzip.decompress(
        (args.review_directory / "results.csv.gz").read_bytes()).decode())))
    for row in rows:
        for field in ["year", "democratic_votes", "republican_votes", "other_votes", "contest_votes",
                      "reported_ballots", "overvotes", "undervotes"]:
            row[field] = int(row[field])
        row["margin_pp"] = float(row["margin_pp"]) if row["margin_pp"] else None
    statistics = json.loads(gzip.decompress((args.review_directory / "participation.json.gz").read_bytes()))
    count_audit = json.loads((args.review_directory / "audit.json").read_text())
    if (count_audit["state_code"] != "ID" or count_audit["year"] != 2026
            or len(rows) != count_audit["reporting_units"] or len({r["key"] for r in rows}) != len(rows)
            or any(sum(row[field] for row in rows) != total
                   for field, total in count_audit["candidate_totals"].items())):
        raise ValueError("Idaho normalized counts differ from the immutable count review")
    names = ["item.json", "service.json", "layer.json", "count.json",
             "native-features.json", "geographic-esri-features.json", "features.geojson"]
    receipts = json.loads((args.boundaries_cache / "sources.json").read_text())
    originals = {}
    for name in names:
        raw, receipt = (args.boundaries_cache / name).read_bytes(), receipts[name]
        expected = ("https://www.arcgis.com/sharing/rest/content/items/" + ITEM if name == "item.json"
                    else SERVICE if name == "service.json" else SERVICE + "/0" if name == "layer.json"
                    else SERVICE + "/0/query")
        if (receipt["url"].split("?")[0] != expected or len(raw) != receipt["bytes"]
                or hashlib.sha256(raw).hexdigest() != receipt["sha256"]):
            raise ValueError("Idaho 2026 boundary receipt mismatch: " + name)
        originals[name] = raw
    item, service, layer, count, native, geographic, geojson = [json.loads(originals[n]) for n in names]
    if (item["id"] != ITEM or item["url"] != SERVICE or item["owner"] != "State_of_Idaho"
            or item["access"] != "public" or item["contentStatus"] != "public_authoritative"
            or "Data goes back to the 2026 election year." not in item["description"]
            or service["spatialReference"]["wkid"] != native["spatialReference"]["wkid"]):
        raise ValueError("Incorrect Idaho public authoritative 2026 geography")
    identity_sets = []
    for data, key in [(native, "attributes"), (geographic, "attributes"), (geojson, "properties")]:
        identities = {f[key]["OBJECTID"]: f[key] for f in data["features"]}
        if (len(identities) != len(data["features"]) or len(identities) != count["count"]
                or data.get("exceededTransferLimit") or data.get("properties", {}).get("exceededTransferLimit")):
            raise ValueError("Incomplete or duplicate Idaho reference exports")
        identity_sets.append(identities)
    if identity_sets[0] != identity_sets[1] or identity_sets[0] != identity_sets[2]:
        raise ValueError("Idaho projected/geographic/GeoJSON identities disagree")
    mapped, audit = mapped_precincts(rows, statistics, geographic)
    if not mapped:
        raise ValueError("No verified Idaho precinct geometry")
    args.output.mkdir(parents=True)

    def save(name, value):
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        path.write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)

    shutil.copytree(args.review_directory, args.output / "count-review")
    for name in ["results.csv.gz", "participation.json.gz"]:
        shutil.copyfile(args.review_directory / name, args.output / name)
    (args.output / "originals").mkdir()
    for name, raw in originals.items():
        (args.output / "originals" / (name + ".gz")).write_bytes(gzip.compress(raw, mtime=0))
    save("2026/ID.geojson.gz", dict(type="FeatureCollection", features=mapped))
    audit.update(candidate_totals=count_audit["candidate_totals"],
                 boundary_last_edit=layer["editingInfo"]["lastEditDate"])
    save("audit.json", audit)
    save("sources.json", {name: receipts[name] for name in names})
    notes = (f"All {len(rows)} House reporting-unit returns reconcile to complete county summaries and both "
        f"district candidate APIs. {len(mapped)} units map by unique complete county precinct-name sets and "
        "explicit congressional district to the official 2026 Idaho SOS reference. Only case, punctuation "
        "and numeric padding are normalized; no token reordering, aliases, ID decoding or vote allocation. "
        "Counties with inconsistent scope or any reference overlap above the audited tolerance are withheld. "
        "Separately reported absentee/early units remain unmapped; no pooled votes are allocated. "
        "Candidate votes are not turnout. Separate unofficial ballots/registration and all provisional "
        "fractions and withholding flags remain in the full download. These are source reporting units "
        "joined to reference precincts, not proof of complete residential all-ballot returns or demographic "
        "participation. Every original result workbook/PDF/API, every native and geographic GIS feature, "
        "unmatched return and county/geometry audit is retained.")
    coverage = dict(file="2026/ID.geojson.gz", source_url=count_audit["source_url"],
        boundary_source=SERVICE + "/0", partial=True, features=len(mapped),
        colored=sum(f["properties"]["margin_pp"] is not None for f in mapped),
        office="U.S. House", boundary_date="2026 primary/general-election reference", notes=notes,
        next_action="Obtain official county reporting-unit crosswalks, resolve reference overlap slivers and "
            "separately reported pooled-ballot scope. Resolve Twin Falls registration and other source "
            "ballot disagreements before enabling withheld rates. No ID-only matching or vote allocation.")
    save("index.json", dict(coverage={"2026": {"ID": coverage}}, result_rows=len(rows),
        participation_rows=len(statistics), complete_download=args.archive.name,
        metric="Candidate margins are not participation; source-defined provisional fractions remain separate.",
        attribution="Idaho Secretary of State; county election clerks; Idaho Office of Information Technology Services",
        source_documentation=OFFICIAL, boundary_item=f"https://www.arcgis.com/home/item.html?id={ITEM}"))
    save("checksums.json", {str(path.relative_to(args.output)): dict(bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(args.output.rglob("*")) if path.is_file()})
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(args.output)))
    print(json.dumps(dict(mapped=len(mapped), colored=coverage["colored"],
        exact_counties=sum(c["exact"] for c in audit["counties"].values()),
        overlap_pairs=len(audit["all_reference_overlap_pairs"]),
        archive_bytes=args.archive.stat().st_size), indent=2))


if __name__ == "__main__":
    main()
