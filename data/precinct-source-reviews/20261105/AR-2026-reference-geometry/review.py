"""Preserve complete Arkansas official reference geometry without approving election joins."""

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

import pyproj
from pyproj import Transformer
import shapely
from shapely.geometry import shape
from shapely.ops import transform
from shapely.strtree import STRtree
from shapely.validation import explain_validity


LAYER = "https://gis.arkansas.gov/arcgis/rest/services/FEATURESERVICES/Boundaries/FeatureServer/11"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def literal(value):
    require(isinstance(value, str) and value.strip(), "Missing native reference label")
    return " ".join(value.casefold().split())


def geometry_issue(geometry):
    if geometry is None:
        return "native_null_geometry"
    polygon = shape(geometry)
    if polygon.is_empty:
        return "native_empty_geometry"
    if polygon.geom_type not in {"Polygon", "MultiPolygon"}:
        return "native_nonpolygon_geometry"
    if not polygon.is_valid:
        return explain_validity(polygon)
    if polygon.area <= 0:
        return "native_zero_area"
    if not (-95 < polygon.bounds[0] <= polygon.bounds[2] < -89
            and 32 < polygon.bounds[1] <= polygon.bounds[3] < 37):
        return "native_geometry_outside_arkansas_extent"
    return None


def diagnose(rows, features):
    by_id, by_name, ids = defaultdict(list), defaultdict(list), set()
    for feature in features:
        p = feature["properties"]
        oid = p["objectid"]
        require(type(oid) is int and oid not in ids, "Duplicate or invalid native object ID")
        require(p["state_fips"] == "05" and isinstance(p["county_fips"], str)
                and re.fullmatch(r"[0-9]{3}", p["county_fips"]), "Invalid reference county FIPS")
        literal(p["county_name"])
        ids.add(oid)
        county = p["state_fips"] + p["county_fips"]
        by_id[(county, p["precinct_code_1"].strip())].append(feature)
        by_name[(county, literal(p["precinct"]))].append(feature)
    identities, scope, counties = set(), Counter(), {}
    for row in rows:
        identity = (row["county_code"], row["precinct_code"], row["contest_id"])
        require(row["year"] == "2026" and row["state_code"] == "AR"
                and re.fullmatch(r"05[0-9]{3}", row["county_code"]), "Wrong result election or county")
        require(identity not in identities, "Duplicate native county/precinct/contest vector")
        require(counties.setdefault(row["county_code"], literal(row["county"])) == literal(row["county"]),
                "Conflicting native county labels")
        identities.add(identity)
        scope[identity[:2]] += 1
    diagnostics = []
    for row in rows:
        identity = (row["county_code"], row["precinct_code"])
        a = by_id[identity]
        b = by_name[(row["county_code"], literal(row["precinct"]))]
        if len(a) > 1 or len(b) > 1:
            category = "ambiguous_reference_identity"
        elif a and b:
            category = ("exact_id_and_literal_name" if a[0]["properties"]["objectid"]
                        == b[0]["properties"]["objectid"] else "conflicting_id_and_literal_name")
        elif b:
            category = "unique_literal_name_only_unconfirmed"
        elif a:
            category = "id_only_unconfirmed"
        else:
            category = "unmatched"
        candidates = {f["properties"]["objectid"]: f for f in a + b}
        conflicts = [oid for oid, feature in candidates.items()
                     if literal(feature["properties"]["county_name"]) != literal(row["county"])]
        diagnostics.append(dict(county_code=row["county_code"], county=row["county"],
            precinct_code=row["precinct_code"], precinct=row["precinct"],
            contest_id=row["contest_id"], classification=category,
            id_reference_objects=[f["properties"]["objectid"] for f in a],
            name_reference_objects=[f["properties"]["objectid"] for f in b],
            conflicting_county_label_objects=conflicts, house_vectors_for_identity=scope[identity],
            maps_approved=False))
    return diagnostics, by_id, by_name


def audit(rows, features):
    diagnostics, by_id, by_name = diagnose(rows, features)
    invalid, valid, polygons = [], [], []
    for feature in features:
        issue = geometry_issue(feature["geometry"])
        if issue:
            invalid.append(dict(object_id=feature["properties"]["objectid"],
                                properties=feature["properties"], reason=issue))
        else:
            valid.append(feature["properties"]["objectid"])
            polygons.append(shape(feature["geometry"]))
    project = Transformer.from_crs(4326, 5070, always_xy=True).transform
    areas = [transform(project, polygon).area for polygon in polygons]
    tree = STRtree(polygons)
    overlaps, tiny = [], 0
    for index, polygon in enumerate(polygons):
        for raw_other in tree.query(polygon, predicate="intersects"):
            other = int(raw_other)
            if other <= index:
                continue
            intersection = polygon.intersection(polygons[other])
            if intersection.area == 0:
                continue
            area = transform(project, intersection).area
            fraction = area / min(areas[index], areas[other])
            if area > 1 and fraction > 0.0000001:
                overlaps.append(dict(left_object_id=valid[index], right_object_id=valid[other],
                    area_square_meters=area, smaller_precinct_fraction=fraction))
            else:
                tiny += 1
    duplicate = lambda values: [
        dict(county_code=key[0], reference_identifier=key[1],
             object_ids=[f["properties"]["objectid"] for f in value])
        for key, value in sorted(values.items()) if len(value) > 1]
    report = dict(year=2026, state_code="AR", layer=LAYER,
        reference_features=len(features), reference_counties=len({
            f["properties"]["county_fips"] for f in features}),
        native_house_vectors=len(rows), native_precinct_identities=len({
            (row["county_code"], row["precinct_code"]) for row in rows}),
        classifications=dict(Counter(row["classification"] for row in diagnostics)),
        duplicate_reference_codes=duplicate(by_id), duplicate_reference_names=duplicate(by_name),
        invalid_geometry=invalid, material_overlaps=overlaps, subthreshold_overlap_pairs=tiny,
        county_label_conflicts=[row for row in diagnostics if row["conflicting_county_label_objects"]],
        multi_house_scope=[row for row in diagnostics if row["house_vectors_for_identity"] > 1],
        native_edit_dates=dict(sorted(Counter(
            f["properties"]["edit_date"] or "not_reported" for f in features).items())),
        dependencies=dict(shapely=shapely.__version__, pyproj=pyproj.__version__),
        election_day_geometry_certified=False, geometry_repaired=False, maps_approved=False,
        scope="Complete current official reference, not certified election-day geometry. "
              "Numeric ID collisions and unique names alone are not approved crosswalks. "
              "No polygon repair, fuzzy label matching, pooled vote allocation, missing-count "
              "imputation, inferred participation rates or map publication. Material overlaps "
              "exceed both 1 square meter and 0.0000001 of the smaller polygon in EPSG:5070.")
    return report, diagnostics


def verified(source, key, receipt):
    body = gzip.decompress((source / "originals" / (key + ".gz")).read_bytes())
    require(receipt["status"] == 200 and len(body) == receipt["bytes"]
            and hashlib.sha256(body).hexdigest() == receipt["sha256"],
            "Invalid original response receipt: " + key)
    return body


def build(source, counts, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing to overwrite an existing review")
    sources = json.loads((source / "sources.json").read_text())
    require({path.name for path in (source / "originals").iterdir()}
            == {key + ".gz" for key in sources}, "Unreceipted or missing original")
    bodies = {key: verified(source, key, value) for key, value in sources.items()}
    metadata = json.loads(bodies["official-layer-metadata"])
    require(metadata["name"] == "ELECTION_PRECINCTS" and metadata["maxRecordCount"] == 200,
            "Unexpected native reference layer")
    catalog = json.loads(bodies["current-official-org-precinct-search"])
    require(catalog["nextStart"] == -1 and any(item.get("url") == LAYER
            for item in catalog["results"]), "Missing complete official catalog declaration")
    before = json.loads(bodies["official-object-ids-before"])["objectIds"]
    after = json.loads(bodies["official-object-ids-after"])["objectIds"]
    require(before and len(set(before)) == len(before) and sorted(before) == sorted(after),
            "Unstable or duplicate native object IDs")
    pages = sorted(key for key in sources if key.startswith("official-precinct-geometry-"))
    require(pages == ["official-precinct-geometry-" + str(i).zfill(5)
                     for i in range(0, len(before), 200)], "Missing native geometry page")
    features = []
    for key in pages:
        page = json.loads(bodies[key])
        offset = int(key.rsplit("-", 1)[1])
        require(page["type"] == "FeatureCollection" and not page.get("exceededTransferLimit")
                and sorted(f["properties"]["objectid"] for f in page["features"])
                == sorted(before)[offset:offset + 200], "Truncated or mismatched native geometry page")
        features.extend(page["features"])
    with counts.open() as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == 2769 and hashlib.sha256(counts.read_bytes()).hexdigest()
            == "6aa855e89d163d172d75ad3e587b8c914103d8bb5ff30b5b13c4f43c0a5da905",
            "Wrong complete reviewed native count table")
    report, diagnostics = audit(rows, features)
    report.update(original_receipts=len(sources), geometry_pages=len(pages),
        complete_object_id_set_verified=True,
        native_count_source_commit="36fb8b109d0044a1d3cc7527a2810cdf70f3dc2d",
        native_count_release="voter-precinct-arkansas-native-counts-20261105",
        native_count_table_sha256=hashlib.sha256(counts.read_bytes()).hexdigest(),
        legacy_notice_redirected=sources["official-2026-searcy-update-notice"]["effective_url"]
            != sources["official-2026-searcy-update-notice"]["url"])
    output.mkdir(parents=True)
    shutil.copytree(source / "originals", output / "native-source/originals")
    shutil.copyfile(source / "sources.json", output / "native-source/sources.json")
    (output / "reference").mkdir()
    shutil.copyfile(counts, output / "reference/precinct-counts.csv")
    shutil.copyfile(__file__, output / "review.py")
    (output / "reference-geometry-review.json").write_text(json.dumps(report, indent=2) + "\n")
    for filename, records in [
        ("reporting-vector-geometry-diagnostic.csv", diagnostics),
        ("all-reference-properties.csv", [feature["properties"] for feature in features]),
    ]:
        with (output / filename).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows({key: json.dumps(value, separators=(",", ":"))
                              if isinstance(value, (list, dict)) else value
                              for key, value in record.items()} for record in records)
    checksums = {}
    for path in sorted(p for p in output.rglob("*") if p.is_file()):
        body = path.read_bytes()
        checksums[str(path.relative_to(output))] = dict(
            bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    (output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as target:
        for path in sorted(p for p in output.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(str(path.relative_to(output)))
            info.external_attr = 0o644 << 16
            target.writestr(info, path.read_bytes())
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--counts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source, args.counts, args.output, args.archive)
    print(json.dumps({key: result[key] for key in [
        "reference_features", "native_house_vectors", "classifications", "maps_approved"]}, indent=2))
