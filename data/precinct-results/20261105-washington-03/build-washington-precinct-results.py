"""Map Washington 2026 only with complete, literal county reporting/CD joins."""

import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import zipfile

import shapefile
from shapely.geometry import mapping
from shapely.ops import unary_union
from shapely.strtree import STRtree

spec = importlib.util.spec_from_file_location(
    "wa_geometry", Path(__file__).with_name("build-north-dakota-precinct-results.py"))
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)
REFERENCE = "https://www.sos.wa.gov/elections/data-research/election-data-and-maps/reports-data-and-statistics/precinct-shapefiles"
PORTAL = "https://results.votewa.gov/results/public/washington/20261103"
BALLOT_SCOPE = "Unofficial native county House reporting-unit counts; not certified all-residential-ballot totals"
TOLERANCE = 1e-10
STRATEGIES = [("precincts", "PrecinctNa"), ("precincts", "PrecinctNu"),
              ("splits", "PrecinctNa"), ("splits", "PrecinctNu"), ("splits", "PPartName")]


def select_references(rows, references):
    reporting = defaultdict(dict)
    if len({row["key"] for row in rows}) != len(rows):
        raise ValueError("Duplicate Washington result key")
    for row in rows:
        key = (row["precinct"], int(row["congressional_district"]))
        if key in reporting[row["county"]]:
            raise ValueError("Ambiguous Washington reporting label/CD")
        reporting[row["county"]][key] = row
    audits, selected = {}, {}
    for county, expected in sorted(reporting.items()):
        attempts, candidates = {}, []
        for package, field in STRATEGIES:
            groups = defaultdict(list)
            for record in references[package]:
                if record["CountyName"] + " County" == county:
                    value = record[field]
                    label = str(value) if value is not None else None
                    groups[(label, record["CD"])].append(record)
            ambiguous = [key for key, records in groups.items()
                         if len({r["St_Code"] for r in records}) != 1
                         or any(not r["St_Code"] for r in records)]
            county_codes = {r["County"] for records in groups.values() for r in records}
            exact = expected.keys() == groups.keys() and not ambiguous and len(county_codes) == 1
            strategy = package + "/" + field
            attempts[strategy] = dict(exact=exact, reporting_only=sorted(expected.keys() - groups.keys()),
                reference_only=sorted(groups.keys() - expected.keys()), ambiguous_source_codes=ambiguous)
            if exact:
                candidates.append((strategy, package, groups))
        signatures = [{key: {r["St_Code"] for r in records} for key, records in groups.items()}
                      for _, _, groups in candidates]
        conflicting_crosswalks = bool(signatures and any(item != signatures[0] for item in signatures[1:]))
        chosen = candidates[0] if candidates and not conflicting_crosswalks else None
        audits[county] = dict(exact=bool(chosen), reporting_rows=len(expected), attempts=attempts,
            strategy=chosen[0] if chosen else None, conflicting_complete_crosswalks=conflicting_crosswalks)
        if chosen:
            selected[county] = (expected, chosen[1], chosen[2])
    return selected, audits


def mapped_precincts(rows, references, readers):
    selected, audits = select_references(rows, references)
    mapped, repairs = [], []
    for county, (expected, package, groups) in selected.items():
        features, invalid = [], []
        for key, records in groups.items():
            polygons = []
            for record in records:
                native = readers[package].shape(record["_index"])
                stops = list(native.parts) + [len(native.points)]
                rings = [list(native.points[first:last]) for first, last in zip(stops, stops[1:])]
                try:
                    polygon, repair = geometry.esri_polygon(rings)
                    polygons.append(polygon)
                    if repair:
                        repairs.append(dict(county=county, source_record=record["_index"], **repair))
                except ValueError as error:
                    invalid.append(dict(source_record=record["_index"], reason=str(error)))
            if invalid:
                continue
            polygon = unary_union(polygons)
            if polygon.is_empty or not polygon.is_valid or polygon.geom_type not in {"Polygon", "MultiPolygon"}:
                invalid.append(dict(precinct=key[0], reason="Invalid dissolved reporting-unit geometry"))
                continue
            row = expected[key]
            properties = dict(row, match_status="matched", official_boundary=True,
                ballot_scope=BALLOT_SCOPE, reporting_unit_kind="source_reporting_unit", source_url=PORTAL,
                boundary_date="October 15, 2026 / 2026 General",
                source_object_ids=[package + ":" + str(r["_index"]) for r in records],
                reference_state_precinct_ids=sorted({r["St_Code"] for r in records}),
                reference_county_codes=sorted({r["County"] for r in records}),
                reference_join=audits[county]["strategy"],
                boundary_provenance="Official Washington 2026 General reference; complete county literal "
                    "reporting-name or explicit precinct-number and congressional-district sets match. "
                    "Only parts of the same St_Code and reporting/CD identity are dissolved. "
                    "No aliases, padding, ID-prefix decoding or vote allocation. Whole counties with "
                    "invalid geometry are withheld. Candidate counts are not turnout.")
            features.append((dict(type="Feature", properties=properties, geometry=mapping(polygon)), polygon))
        audits[county]["invalid_geometry"] = invalid
        if invalid:
            audits[county]["exact"] = False
        else:
            mapped.extend(features)
    polygons = [polygon for _, polygon in mapped]
    tree = STRtree(polygons)
    overlaps, masks = [], defaultdict(list)
    for i, polygon in enumerate(polygons):
        for j in tree.query(polygon, predicate="intersects"):
            if j <= i:
                continue
            area = polygon.intersection(polygons[j]).area
            if area > TOLERANCE:
                left, right = mapped[i][0]["properties"], mapped[j][0]["properties"]
                overlaps.append(dict(left=left["key"], right=right["key"], area_degrees_squared=area))
                intersection = polygon.intersection(polygons[j])
                masks[i].append(intersection)
                masks[j].append(intersection)
    withheld, masked_units, mask_features = set(), [], []
    for i, intersections in masks.items():
        ambiguous = unary_union(intersections)
        polygon = polygons[i].difference(ambiguous)
        properties = mapped[i][0]["properties"]
        record = dict(key=properties["key"], area_degrees_squared=ambiguous.area,
                      fraction_of_reference_geometry=ambiguous.area / polygons[i].area)
        masked_units.append(record)
        mask_features.append(dict(type="Feature", properties=record, geometry=mapping(ambiguous)))
        if polygon.is_empty:
            withheld.add(properties["county"])
            continue
        if not polygon.is_valid or polygon.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Invalid Washington overlap-masked reporting-unit geometry")
        mapped[i][0]["geometry"] = mapping(polygon)
        mapped[i] = (mapped[i][0], polygon)
        properties["geometry_scope"] = "Reference geometry with overlapping strips withheld"
        properties["boundary_provenance"] += (
            " Ambiguous strips shared with another reference reporting unit are excluded from both, "
            "never assigned to either precinct. Counts still describe the entire reporting unit. "
            "The complete original boundaries and excluded-area audit remain in the full download.")
    for county in withheld:
        audits[county].update(exact=False, geometry_withheld="Reporting unit completely overlaps another")
    features = [feature for feature, _ in mapped if feature["properties"]["county"] not in withheld]
    remaining = [polygon for feature, polygon in mapped if feature["properties"]["county"] not in withheld]
    tree = STRtree(remaining)
    for i, polygon in enumerate(remaining):
        for j in tree.query(polygon, predicate="intersects"):
            if j > i and polygon.intersection(remaining[j]).area > TOLERANCE:
                raise ValueError("Washington reference overlap remains after excluding ambiguous strips")
    return features, dict(counties=audits, topology_repairs=repairs, all_reference_overlap_pairs=overlaps,
        mapped_cross_precinct_overlaps=0, masked_reporting_units=masked_units,
        ambiguity_mask=dict(type="FeatureCollection", features=mask_features),
        overlap_tolerance_degrees_squared=TOLERANCE, coordinate_grid_degrees=geometry.GRID,
        mapped_units=len(features), reporting_units=len(rows),
        withheld_units=sorted({r["key"] for r in rows} - {f["properties"]["key"] for f in features}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-directory", required=True, type=Path)
    parser.add_argument("--boundaries-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable Washington mapped snapshot")
    for name, item in json.loads((args.review_directory / "checksums.json").read_bytes()).items():
        raw = (args.review_directory / name).read_bytes()
        if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("Washington immutable count review changed")
    count_audit = json.loads((args.review_directory / "audit.json").read_bytes())
    rows = json.loads(gzip.decompress((args.review_directory / "results.json.gz").read_bytes()))
    if (count_audit["state_code"] != "WA" or count_audit["year"] != 2026
            or len(rows) != count_audit["house_reporting_rows"]
            or any(row["margin_pp"] != (
                100 * (row["democratic_votes"] - row["republican_votes"]) / row["contest_votes"]
                if row["contest_votes"] else None) for row in rows)
            or any(sum(row[field] for row in rows) != total for field, total in count_audit["candidate_totals"].items())):
        raise ValueError("Washington normalized count inventory changed")
    inputs = json.loads(gzip.decompress((args.review_directory / "inputs.json.gz").read_bytes()))
    references, readers = {}, {}
    for package in ["precincts", "splits"]:
        name = "official-statewide-2026-general-" + package + ".zip"
        raw = (args.boundaries_cache / name).read_bytes()
        item = inputs["official-discovery"][name]
        if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("Washington official reference original changed")
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if archive.testzip() is not None:
                raise ValueError("Washington boundary ZIP fails CRC")
            prefix = "Statewide_" + ("Precincts" if package == "precincts" else "Splits") + "_2026General"
            projection = archive.read(prefix + ".prj").decode()
            if not projection.startswith('GEOGCS["GCS_WGS_1984"') or "PROJCS" in projection:
                raise ValueError("Washington boundary CRS is not native WGS84 geographic")
            readers[package] = shapefile.Reader(shp=io.BytesIO(archive.read(prefix + ".shp")),
                shx=io.BytesIO(archive.read(prefix + ".shx")), dbf=io.BytesIO(archive.read(prefix + ".dbf")))
            references[package] = [dict(record.as_dict(), _index=i)
                                   for i, record in enumerate(readers[package].records())]
            if len(references[package]) != (8119 if package == "precincts" else 13774):
                raise ValueError("Incomplete Washington original reference inventory")
    features, audit = mapped_precincts(rows, references, readers)
    if not features:
        raise ValueError("No verified Washington precinct geometry")
    args.output.mkdir(parents=True)

    def save(name, value):
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(value, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
        path.write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)

    shutil.copytree(args.review_directory, args.output / "count-review")
    shutil.copyfile(args.review_directory / "results.json.gz", args.output / "results.json.gz")
    csv_rows = [dict(row, ballot_scope=BALLOT_SCOPE, reporting_unit_kind="source_reporting_unit", source_url=PORTAL)
                for row in rows]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, list(csv_rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(csv_rows)
    (args.output / "results.csv.gz").write_bytes(gzip.compress(stream.getvalue().encode(), mtime=0))
    for name in [Path(__file__).name, "build-north-dakota-precinct-results.py",
                 "review-north-dakota-precinct-results.py", "build-precinct-results.py"]:
        shutil.copyfile(Path(__file__).with_name(name), args.output / name)
    save("2026/WA.geojson.gz", dict(type="FeatureCollection", features=features))
    audit.update(candidate_totals=count_audit["candidate_totals"], source_review_counties=36)
    save("2026/WA-ambiguous-reference-areas.geojson.gz", audit.pop("ambiguity_mask"))
    save("audit.json", audit)
    notes = (f"{len(rows)} House rows reconcile across 36 counties; {len(features)} precinct reporting units "
        "map using complete literal county name/precinct name or explicit precinct number/CD sets from "
        "the official October 15, 2026 General reference. Only matching source parts are dissolved. "
        "No prefixes, aliases, vote allocation or borrowed shapes. Counties with invalid "
        "geometry or incomplete identity sets are withheld. Ambiguous overlapping strips are excluded "
        "from both precincts, never assigned to either; counts describe the complete reporting unit. "
        "King has duplicate House labels; Jefferson "
        "and Walla Walla have unresolved ballot accounting. All 39 county APIs, 78 Excel originals, both "
        "complete native boundary ZIPs, unmatched rows and scoped audits remain in the full download. "
        "These unofficial candidate margins are not turnout or demographic participation.")
    coverage = dict(file="2026/WA.geojson.gz", source_url=count_audit["source_url"],
        boundary_source=REFERENCE, partial=True, features=len(features),
        colored=sum(f["properties"]["margin_pp"] is not None for f in features),
        office="U.S. House", boundary_date="October 15, 2026 / 2026 General", notes=notes,
        next_action="Resolve remaining complete reporting/reference identity sets and geometry conflicts "
                    "with authoritative crosswalks. Resolve three withheld counties' count-source issues. "
                    "Audit separate native ballot/registration definitions before participation claims.")
    save("index.json", dict(coverage={"2026": {"WA": coverage}}, result_rows=len(rows),
        complete_download=args.archive.name, participation_rows=0,
        metric="Candidate margins, not turnout or demographic participation.",
        attribution="Washington Secretary of State and county election offices"))
    save("checksums.json", {p.relative_to(args.output).as_posix(): dict(bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(args.output.rglob("*")) if p.is_file()})
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                item = zipfile.ZipInfo(path.relative_to(args.output).as_posix(), (2026, 11, 5, 0, 0, 0))
                item.external_attr = 0o100644 << 16
                archive.writestr(item, path.read_bytes())
    print(json.dumps(dict(mapped=len(features), colored=coverage["colored"],
        mapped_counties=sum(c["exact"] for c in audit["counties"].values()),
        overlap_pairs=len(audit["all_reference_overlap_pairs"]),
        archive_bytes=args.archive.stat().st_size,
        archive_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest()), indent=2))


if __name__ == "__main__":
    main()
