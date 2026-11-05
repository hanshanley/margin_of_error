"""Join Arizona 2026 counts to exact Maricopa code/name pairs without repairing shapes."""

import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
from urllib.parse import parse_qs, urlsplit
import zipfile

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform
from shapely.strtree import STRtree


ITEM = "d54dad69d3954287849087b949fb561f"
SERVICE = ("https://services.arcgis.com/ykpntM6e3tHvzKRJ/arcgis/rest/services/"
           "Maricopa_County_Voting_Precincts_%282026_%29/FeatureServer")
SOURCE = "https://app.enhancedvoting.com/cdn/results/Arizona/export-110326GeneralElection.json"
VOTES = ["democratic_votes", "republican_votes", "other_votes"]
POLICY = ("Native-coordinate intersections are projected to EPSG:5070. Both precincts in an "
          "overlap exceeding 1 square meter and 0.0000001 of the smaller precinct are withheld "
          "whole. Invalid/empty/nonpolygon shapes are withheld. No clipping or geometry repair.")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def mapped_precincts(rows, features):
    reporting, reference, seen, codes = {}, {}, set(), set()
    for row in rows:
        require(row["year"] == 2026 and row["state_code"] == "AZ"
                and row["county_code"] == "maricopa" and row["county"] == "Maricopa County"
                and row["native_virtual_precinct"] == "False"
                and re.fullmatch(r"AZ-[1-9]", row["contest_id"]),
                "Unreviewed election, county, virtual unit or House contest")
        require(row["precinct"] not in reporting and row["precinct_code"] not in codes,
                "Duplicate native Maricopa precinct")
        require(all(type(row[field]) is int and row[field] >= 0
                    for field in VOTES + ["total_votes"])
                and sum(row[field] for field in VOTES) == row["total_votes"],
                "Incomplete native candidate vector")
        expected = (100 * (row["democratic_votes"] - row["republican_votes"]) / row["total_votes"]
                    if row["total_votes"] else None)
        require((row["margin_pp"] is None if expected is None else
                 isinstance(row["margin_pp"], (int, float))
                 and not isinstance(row["margin_pp"], bool)
                 and math.isclose(row["margin_pp"], expected, rel_tol=1e-12, abs_tol=1e-12)),
                "Candidate margin differs from complete count vector")
        reporting[row["precinct"]] = row
        codes.add(row["precinct_code"])
    for feature in features:
        p = feature["properties"]
        require(type(p["OBJECTID"]) is int and p["OBJECTID"] not in seen
                and isinstance(p["BdVal"], str) and re.fullmatch(r"[0-9]{4}", p["BdVal"])
                and type(p["PctNum"]) is int and int(p["BdVal"]) == p["PctNum"]
                and isinstance(p["BdName"], str) and bool(p["BdName"]),
                "Duplicate or conflicting reference code/name declaration")
        label = p["BdVal"] + " " + p["BdName"]
        require(label not in reference, "Duplicate literal reference code/name")
        reference[label] = feature
        seen.add(p["OBJECTID"])
    require(bool(reporting) and reporting.keys() == reference.keys(),
            "Complete native/reference code-name sets differ")
    polygons, reasons, correspondence = {}, {}, []
    for label, row in reporting.items():
        feature = reference[label]
        p = feature["properties"]
        require(isinstance(row["precinct_code"], str)
                and re.fullmatch(r"[0-9]+", row["precinct_code"])
                and int(row["precinct_code"]) == p["PctNum"],
                "Media ID conflicts with independent literal reference code/name")
        reasons[label] = []
        if feature["geometry"] is None:
            reasons[label].append("null_reference_geometry")
        else:
            polygon = shape(feature["geometry"])
            if (polygon.is_empty or not polygon.is_valid
                    or polygon.geom_type not in {"Polygon", "MultiPolygon"}):
                reasons[label].append("invalid_empty_or_nonpolygon_reference_geometry")
            else:
                require(-115 < polygon.bounds[0] <= polygon.bounds[2] < -110
                        and 32 < polygon.bounds[1] <= polygon.bounds[3] < 35,
                        "Reference geometry is not geographic Maricopa coordinates")
                polygons[label] = polygon
        correspondence.append(dict(county_code="maricopa", media_precinct_id=row["precinct_code"],
            literal_media_name=label, reference_object_id=p["OBJECTID"],
            reference_BdVal=p["BdVal"], reference_BdName=p["BdName"],
            reference_PctNum=p["PctNum"]))
    labels = sorted(polygons)
    values = [polygons[label] for label in labels]
    project = Transformer.from_crs(4326, 5070, always_xy=True).transform
    areas = [transform(project, polygon).area for polygon in values]
    tree = STRtree(values)
    overlaps = []
    for i, polygon in enumerate(values):
        for raw_j in tree.query(polygon, predicate="intersects"):
            j = int(raw_j)
            if j <= i:
                continue
            intersection = polygon.intersection(values[j])
            if intersection.area == 0:
                continue
            area = transform(project, intersection).area
            fraction = area / min(areas[i], areas[j])
            material = area > 1 and fraction > 0.0000001
            overlaps.append(dict(left=labels[i], right=labels[j], square_meters=area,
                                 smaller_precinct_fraction=fraction, material=material))
            if material:
                for label in [labels[i], labels[j]]:
                    reasons[label].append("material_reference_overlap")
    mapped = []
    for label, row in reporting.items():
        if reasons[label]:
            continue
        p = reference[label]["properties"]
        properties = {field: row[field] for field in
            ["year", "state_code", "county_code", "county", "precinct_code", "precinct",
             "contest_id", "office", "democratic_votes", "republican_votes", "other_votes",
             "margin_pp", "native_reporting_status"]}
        properties.update(key=f'2026-AZ-maricopa-{row["precinct_code"]}-{row["contest_id"]}',
            contest_votes=row["total_votes"], match_status="matched", official_boundary=True,
            boundary_date="Effective January 2, 2026",
            reference_BdVal=p["BdVal"], reference_BdName=p["BdName"],
            reference_PctNum=p["PctNum"], source_object_ids=[p["OBJECTID"]],
            ballot_scope="Unofficial native precinct candidate counts across all five declared voting "
                "modes at the acquired snapshot; candidate votes are not ballots or turnout.",
            boundary_provenance="Maricopa Elections GIS 2026 reference. Exact literal BdVal + space + "
                "BdName equals the native label; numeric PctNum independently agrees with the media ID. "
                "No aliases, padding, UUID substitution or vote allocation. " + POLICY)
        mapped.append(dict(type="Feature", properties=properties,
                           geometry=reference[label]["geometry"]))
    return mapped, dict(year=2026, state_code="AZ", county_code="maricopa",
        source_features=len(features), county_house_vectors=len(rows),
        literal_code_name_correspondence=correspondence,
        overlap_policy=POLICY, overlap_pairs=overlaps,
        withheld_units=[dict(precinct=label, reasons=sorted(set(flags)))
                        for label, flags in sorted(reasons.items()) if flags],
        mapped_units=len(mapped), colored_units=sum(
            feature["properties"]["margin_pp"] is not None for feature in mapped),
        candidate_totals={field: sum(row[field] for row in rows)
                          for field in VOTES + ["total_votes"]},
        all_reference_and_native_names_match=True, participation_joined=False,
        rates_available=False, complete=False)


def reference_capture(source):
    receipts = json.loads((source / "sources.json").read_text())
    originals = {}
    for key, receipt in receipts.items():
        path = Path(receipt["file"])
        require(path.parts[0] == "originals" and ".." not in path.parts,
                "Unreviewed original path")
        raw = gzip.decompress((source / path).read_bytes())
        require(len(raw) == receipt["bytes"]
                and hashlib.sha256(raw).hexdigest() == receipt["sha256"],
                "Reference original receipt mismatch")
        originals[key] = raw
    def data(key, endpoint):
        require(receipts[key]["status"] == 200
                and receipts[key]["url"].split("?")[0] == endpoint,
                "Reference identity or HTTP receipt mismatch")
        return json.loads(originals[key])
    service = data("service", SERVICE)
    layer = data("layer", SERVICE + "/0")
    after_layer = data("layer-after", SERVICE + "/0")
    item = data("item", "https://www.arcgis.com/sharing/rest/content/items/" + ITEM)
    require(service["serviceItemId"] == layer["serviceItemId"] == item["id"] == ITEM
            and layer["name"] == "VotingPrecincts2026"
            and layer["geometryType"] == "esriGeometryPolygon"
            and item["owner"] == "MaricopaElectionsGIS" and item["access"] == "public"
            and "effective for use on Jan 2, 2026" in item["description"]
            and "October 1, 2025" in item["description"]
            and layer["editingInfo"] == after_layer["editingInfo"],
            "Unreviewed official 2026 reference vintage or unstable edit version")
    before = data("object-ids-before", SERVICE + "/0/query")
    after = data("object-ids-after", SERVICE + "/0/query")
    ids = before["objectIds"]
    require(ids and all(type(value) is int for value in ids)
            and len(ids) == len(set(ids)) and len(after["objectIds"]) == len(ids)
            and set(after["objectIds"]) == set(ids),
            "Unstable or duplicate reference ID inventory")
    features, seen = [], set()
    for key in sorted(k for k in receipts if k.startswith("features-")):
        page = data(key, SERVICE + "/0/query")
        query = parse_qs(urlsplit(receipts[key]["url"]).query)
        expected = [int(value) for value in query["objectIds"][0].split(",")]
        actual = [f["properties"][layer["objectIdField"]] for f in page["features"]]
        require(page["type"] == "FeatureCollection" and not page.get("exceededTransferLimit")
                and not page.get("properties", {}).get("exceededTransferLimit")
                and query["outFields"] == ["*"] and query["outSR"] == ["4326"]
                and query["returnGeometry"] == ["true"] and query["f"] == ["geojson"]
                and len(actual) == len(set(actual)) == len(expected)
                and set(actual) == set(expected) and not seen.intersection(actual),
                "Incomplete or conflicting bounded reference page")
        seen.update(actual)
        features.extend(page["features"])
    declared = re.search(r"there are ([0-9]+) voting precincts", item["description"])
    require(seen == set(ids) and declared and len(features) == int(declared.group(1)),
            "Reference pages do not cover the complete declared precinct inventory")
    return features, receipts, layer["editingInfo"]


def build(review, boundaries, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing immutable snapshot overwrite")
    for name, receipt in json.loads((review / "checksums.json").read_text()).items():
        raw = (review / name).read_bytes()
        require(len(raw) == receipt["bytes"]
                and hashlib.sha256(raw).hexdigest() == receipt["sha256"],
                "Immutable count-review checksum mismatch")
    counts = json.loads((review / "counts-review.json").read_text())
    require(counts["year"] == 2026 and counts["state_code"] == "AZ"
            and counts["all_candidate_and_mode_scopes_reconcile"] is True,
            "Unreviewed native candidate/mode scopes")
    all_rows = list(csv.DictReader((review / "precinct-counts.csv").open()))
    require(len(all_rows) == counts["precinct_house_vectors"], "Incomplete native House table")
    rows = [row for row in all_rows if row["county_code"] == "maricopa"]
    for row in rows:
        for field in VOTES + ["total_votes", "year"]:
            require(bool(re.fullmatch(r"[0-9]+", row[field])), "Missing or noninteger native count")
            row[field] = int(row[field])
        row["margin_pp"] = float(row["margin_pp"]) if row["margin_pp"] else None
    features, receipts, edit = reference_capture(boundaries)
    mapped, audit = mapped_precincts(rows, features)
    require(bool(mapped), "No supported Maricopa map units")
    output.mkdir(parents=True)

    def save(name, value):
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        path.write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)

    shutil.copytree(review, output / "count-review")
    (output / "reference-source/originals").mkdir(parents=True)
    for receipt in receipts.values():
        shutil.copyfile(boundaries / receipt["file"], output / "reference-source" / receipt["file"])
    shutil.copyfile(boundaries / "sources.json", output / "reference-source/sources.json")
    shutil.copyfile(__file__, output / "review.py")
    (output / "results.csv.gz").write_bytes(gzip.compress(
        (review / "precinct-counts.csv").read_bytes(), mtime=0))
    audit.update(native_created_at=counts["native_created_at"], reference_editing_info=edit,
                 statewide_house_vectors=len(all_rows), maps_approved=True)
    save("audit.json", audit)
    save("2026/AZ.geojson.gz", dict(type="FeatureCollection", features=mapped))
    notes = (f"Maricopa County only: {audit['mapped_units']} verified 2026 reference shapes, "
        f"{audit['colored_units']} with positive candidate counts. Exact literal code/name pairs and "
        "independent numeric IDs agree for the entire 956-unit county inventory. "
        f"{len(audit['withheld_units'])} whole precincts are withheld for reference geometry defects. "
        "Explicit zero-vote units remain uncolored; missing is never zero-filled. "
        "Unofficial House candidate margins, not ballots, turnout or demographic participation. "
        "All 15 counties' original counts and separate unjoined participation remain in the full ZIP. "
        + POLICY)
    save("index.json", dict(coverage={"2026": {"AZ": dict(file="2026/AZ.geojson.gz",
        source_url=SOURCE, boundary_source=SERVICE + "/0", partial=True, features=len(mapped),
        colored=audit["colored_units"], office="U.S. House",
        boundary_date="Effective January 2, 2026", notes=notes,
        next_action="Acquire correct-election reference/crosswalks for the other 14 counties; resolve "
            "Maricopa overlap defects and separate registration-definition discrepancies.")}},
        result_rows=len(all_rows), complete_download=archive.name,
        metric="Candidate margins are not participation; no participation or rates joined.",
        attribution="Arizona Secretary of State; Maricopa County Elections GIS"))
    checksums = {}
    for path in sorted(output.rglob("*")):
        if path.is_file():
            raw = path.read_bytes()
            checksums[path.relative_to(output).as_posix()] = dict(
                bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    save("checksums.json", checksums)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as target:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                entry = zipfile.ZipInfo(path.relative_to(output).as_posix(), date_time=(2026, 11, 5, 0, 0, 0))
                entry.external_attr = 0o100644 << 16
                target.writestr(entry, path.read_bytes())
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-directory", required=True, type=Path)
    parser.add_argument("--boundaries-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    audit = build(args.review_directory, args.boundaries_cache, args.output, args.archive)
    print(json.dumps({key: value for key, value in audit.items()
                      if key not in {"literal_code_name_correspondence", "overlap_pairs"}}, indent=2))
