"""Normalize the official 2026 app's selected Monroe reference without repairing geometry."""

import gzip
import hashlib
import json

from shapely.geometry import MultiPolygon, Polygon, mapping


SNAPSHOT = "indiana-monroe-native-20261109-01"
PUBLIC = "public/participation-precincts/20261109-indiana-monroe-01"
BOUNDARY = "Official Monroe 2026 app's selected current precinct reference; not certified 2026 legal boundaries"
DOWNLOAD = ("https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-county-indiana-voter-statistics-20261109-01/complete-analysis.zip")
GEO_SHA = "05063b53d4dbb2fa4ed95410e0517bbe2d928190aa7571b0fc42cfe0a8d7b5ce"


def encoded(value):
    return (json.dumps(value, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def source_polygon(raw):
    rings = raw["rings"]
    if not rings or any(len(ring) < 4 or ring[0] != ring[-1] for ring in rings):
        raise ValueError("Unclosed source ring; no geometry repair allowed")
    shapes = [Polygon(ring) for ring in rings]
    if any(not shape.is_valid or shape.is_empty or shape.area <= 0 for shape in shapes):
        raise ValueError("Invalid source ring; no geometry repair allowed")
    containers = [[j for j, other in enumerate(shapes)
                   if i != j and other.area > shape.area and other.covers(shape)]
                  for i, shape in enumerate(shapes)]
    pieces = []
    for i, ring in enumerate(rings):
        if len(containers[i]) % 2:
            continue
        holes = [rings[j] for j in range(len(rings))
                 if len(containers[j]) == len(containers[i]) + 1 and i in containers[j]]
        pieces.append(Polygon(ring, holes))
    result = pieces[0] if len(pieces) == 1 else MultiPolygon(pieces)
    if not result.is_valid or result.is_empty:
        raise ValueError("Invalid source polygon; no geometry repair allowed")
    if not (-87 < result.bounds[0] < result.bounds[2] < -86
            and 38 < result.bounds[1] < result.bounds[3] < 40):
        raise ValueError("Source coordinates are outside Monroe County's longitude/latitude region")
    return result


def build_monroe(count_bytes, geometry_bytes, source_url):
    if hashlib.sha256(geometry_bytes).hexdigest() != GEO_SHA:
        raise ValueError("Changed app-selected Monroe polygon snapshot")
    source = json.loads(count_bytes)
    polygons = json.loads(geometry_bytes)
    if polygons["spatialReference"]["wkid"] != 4326:
        raise ValueError("Monroe selected reference must retain its source longitude/latitude query")
    rows = [feature["attributes"] for feature in source["features"]]
    identities = [row["Precinct_ID"] for row in rows]
    by_id = {feature["attributes"]["Precinct_ID"]: feature for feature in polygons["features"]}
    if len(rows) != 103 or len(set(identities)) != 103 or len(by_id) != 103 or set(identities) != set(by_id):
        raise ValueError("Incomplete or unmatched native Monroe participation/reference identities")
    for row in rows:
        if (type(row["Ballots_Cast"]) is not int or row["Ballots_Cast"] < 0
                or row["Precinct_Reporting"] != "Partially Reporting"
                or not row["Precinct"]):
            raise ValueError("Changed native Monroe participation fields or reporting status")
    if sum(row["Ballots_Cast"] for row in rows) != 42766:
        raise ValueError("Monroe rows disagree with the publisher-defined county indicator")
    qualified, invalid = {}, {}
    for identity, feature in by_id.items():
        try:
            qualified[identity] = source_polygon(feature["geometry"])
        except ValueError as error:
            invalid[str(identity)] = str(error)
    federal = next(row for row in rows if row["Precinct_ID"] == 51)
    if (federal["Precinct"] != "Bloom Federal 20" or federal["Registered_Voters"] != 0
            or federal["Ballots_Cast"] != 241 or 51 not in qualified
            or any(not qualified[51].intersects(shape)
                   for identity, shape in qualified.items() if identity != 51)):
        raise ValueError("Changed source-assigned federal reporting-unit carrier")
    carriers = {51: "Federal reporting-unit carrier overlaps every other source unit; no distinct precinct assignment."}
    overlapping = set()
    overlaps = []
    for left, a in qualified.items():
        for right, b in qualified.items():
            if left in carriers or right in carriers or left >= right or not a.intersects(b):
                continue
            area = a.intersection(b).area
            if area > 1e-10:
                overlapping.update((left, right))
                overlaps.append(dict(left=left, right=right, square_degrees=area))
    features, units = [], []
    for native in rows:
        identity = native["Precinct_ID"]
        withheld = carriers.get(identity) or invalid.get(str(identity)) or (
            "Source precinct-split polygons overlap; no clipping or count allocation."
            if identity in overlapping else None)
        props = dict(year=2026, state_code="IN", county="Monroe County", county_fips="18105",
            county_id="additional:IN:18105", key=f"IN|18105|{identity}",
            unit_key=str(identity), unit=native["Precinct"], native_precinct_id=identity,
            ballots=native["Ballots_Cast"], denominator=None, reported_pct=None,
            native_record=native, source_snapshot=SNAPSHOT,
            source_url=source_url, boundary_label=BOUNDARY,
            match_status="withheld_source_geometry" if withheld else "matched",
            geometry_withheld_reason=withheld,
            rate_withheld_reason="Native electorate definitions are unqualified; no analysis rate.",
            source_update_label="Native count source clock and timezone not supplied; acquisition/edit times are not substitutes.",
            source_reporting_label="Native Precinct_Reporting=Partially Reporting. Whole source-unit ballots, not clipped-area allocations. "
                "The official general-election app contains conflicting copied primary-election instructions; its selected 2026 general source is retained.")
        units.append(props)
        if identity in qualified and not withheld:
            features.append(dict(type="Feature", properties=props, geometry=mapping(qualified[identity])))
    if not features:
        raise ValueError("No qualified Monroe reference polygons; counts must remain table-only")
    raw = gzip.compress(encoded(dict(type="FeatureCollection", features=features)), mtime=0)
    metadata = dict(source_id=SNAPSHOT, boundary_label=BOUNDARY,
        notes=f"Monroe County only: {len(features)} mapped source units of 103 native count records. All source rows are Partially Reporting. "
            "The federal carrier and overlapping split references remain table-only; no geometry repairs or count allocations. "
            "No statewide Indiana precinct coverage, completion, certified geography, rates or demographic allocation.",
        complete_download_url=DOWNLOAD, sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw), expected_features=len(features), native_source_rows=103,
        county_fips="18105", counts_only=True, rates_approved=False)
    index = dict(year=2026, boundary_date=BOUNDARY, states={"IN": "IN.geojson.gz"},
        state_metadata={"IN": metadata})
    audit = dict(source_snapshot=SNAPSHOT, original_count_rows=103, source_polygon_ids=103,
        mapped_polygons=len(features), invalid_source_geometry=invalid,
        overlap_pairs=overlaps, withheld_overlap_ids=sorted(overlapping),
        withheld_carrier_ids=sorted(carriers), carrier_reasons=carriers,
        geometry_repaired=False, counts_allocated_to_clips=False,
        publisher_count_indicator_reproduced=42766, analysis_rates_approved=False)
    return {
        "monroe-original-counts.json": count_bytes,
        "monroe-selected-polygons.json": geometry_bytes,
        "monroe-reporting-units.json.gz": gzip.compress(encoded(units), mtime=0),
        "monroe-reference-review.json": (json.dumps(audit, indent=2) + "\n").encode(),
    }, {f"{PUBLIC}/IN.geojson.gz": raw, f"{PUBLIC}/index.json": encoded(index)}, audit
