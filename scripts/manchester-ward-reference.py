"""Join literal 2026 ward totals to the current official municipal ward display reference."""

import argparse
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path

from shapely.geometry import Polygon, shape


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/precinct-source-reviews/20261110-manchester-ward-reference-01"
PUBLIC = "public/participation-precincts/20261110-manchester-ward-reference-01"
SNAPSHOT = "manchester-native-ward-reference-20261110-01"
BOUNDARY = ("Current Manchester municipal ward reference (Wards_2022 GIS; lines in effect since "
            "December 21, 2021), not newly certified 2026 precinct boundaries")


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n").encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def review(inputs, counts, geographic, projected, ids, native_count, layer, parent, clerk, native_review):
    if (inputs["source_count_election_date"] != "2026-11-03"
            or inputs["reference_boundary_vintage"] != 2022
            or inputs["certified_legal_precinct_boundaries"] is not False
            or inputs["source_geometry_repaired"] is not False
            or inputs["source_geometry_clipped"] is not False
            or inputs["native_federal_only_added"] is not False
            or clerk["native_current_effective_date"] != "2021-12-21"):
        raise ValueError("Unqualified election, current-reference vintage or source repair")
    if (layer["name"] != "Wards" or layer["description"] != "SDEweb.GISADMIN.Wards_2022"
            or layer["geometryType"] != "esriGeometryPolygon"
            or [row["id"] for row in parent["layers"] if row["name"] == "Wards"] != [3]
            or projected["spatialReference"].get("latestWkid") != 3857):
        raise ValueError("Wrong service layer; WMS/REST ordinals are not interchangeable")
    if (counts["summary"]["source_city_observations"] != 4
            or len(counts["source_queries"]) != 242 or len(counts["ward_rows"]) != 37):
        raise ValueError("Changed complete native city-source scope")
    source = next(row for row in counts["municipalities"] if row["city"] == "Manchester")
    if (source["source_election_date"] != "2026-11-03"
            or source["native_city_parent_printed"] is not False
            or source["native_record"]["federal_only_added_to_total"] is not False):
        raise ValueError("Changed native Manchester election or printed-total definition")
    by_ward = {row["native_ward"]: row for row in counts["ward_rows"] if row["city"] == "Manchester"}
    native_wards = {row["ward"]: row for row in source["native_record"]["wards"]}
    by_projected = {row["attributes"]["WardNumber"]: row for row in projected["features"]}
    features = geographic["features"]
    if (len(features) != native_count["count"] or len(features) != len(ids["objectIds"])
            or len(features) != 12 or set(by_ward) != set(range(1,13))
            or set(native_wards) != set(range(1,13))
            or set(by_projected) != set(range(1,13))):
        raise ValueError("Incomplete ward count, native ID inventory or full original geometry")
    actual_ids, ward_ids, rings, decisions, joined = set(), set(), {}, [], []
    vertex_count = 0
    for feature in features:
        p = feature["properties"]
        if set(p) - {"OBJECTID","Ward_ID","WardNumber","WardName"}:
            raise ValueError("Unrequested personal or population fields in the ward query")
        ward = p["WardNumber"]
        oid = p.get("OBJECTID", feature.get("id"))
        if (type(ward) is not int or ward not in by_ward or ward in ward_ids
                or oid in actual_ids or p["Ward_ID"] != f"Ward {ward}" or p["WardName"] != p["Ward_ID"]):
            raise ValueError("Ambiguous native city ward identity")
        actual_ids.add(oid)
        ward_ids.add(ward)
        local = by_projected[ward]
        if local["attributes"]["OBJECTID"] != oid or local["attributes"]["Ward_ID"] != p["Ward_ID"]:
            raise ValueError("Native projected and geographic Ward IDs differ")
        if (feature["geometry"]["type"] != "Polygon"
                or len(feature["geometry"]["coordinates"]) != 1
                or len(local["geometry"]["rings"]) != 1):
            raise ValueError("Unreviewed ring-role hierarchy; no implicit repairs")
        xy = local["geometry"]["rings"][0]
        ll = feature["geometry"]["coordinates"][0]
        if xy[0] != xy[-1] or ll[0] != ll[-1] or len(xy) != len(ll):
            raise ValueError("Source ring is incomplete or has changed vertices")
        native_polygon, geographic_polygon = Polygon(xy), shape(feature["geometry"])
        if (not native_polygon.is_valid or not geographic_polygon.is_valid
                or native_polygon.is_empty or geographic_polygon.is_empty
                or native_polygon.area <= 0):
            raise ValueError("Invalid native ward polygon; no repair allowed")
        expected = sorted((x/6378137*180/math.pi, math.degrees(math.atan(math.sinh(y/6378137))))
                          for x,y in xy)
        error = max(max(abs(a-b) for a,b in zip(left,right))
                    for left,right in zip(expected,sorted(tuple(point) for point in ll)))
        if error > 1e-10:
            raise ValueError("Source coordinate/projection disagreement")
        vertex_count += len(xy)
        rings[ward] = native_polygon
        row = by_ward[ward]
        native = row["native_record"]
        if (native != native_wards[ward] or row["source_count"] != native["total"] or row["denominator"] is not None
                or row["reported_pct"] is not None or any(
                    type(native[key]) is not int or native[key] < 0
                    for key in ["election_day","absentee","total","federal_only"])):
            raise ValueError("Changed literal ward ballot fields or inferred rates")
        decisions.append(dict(city="Manchester", native_ward_number=ward, native_object_id=oid,
            native_ward_label=p["Ward_ID"], source_total=native["total"],
            geometry_valid_without_repair=True, native_vertices=len(xy),
            maximum_inverse_mercator_error_degrees=error,
            source_component_minus_printed_total=native["election_day"]+native["absentee"]-native["total"],
            source_federal_only_separate=native["federal_only"],
            disposition="current_official_municipal_ward_count_display_not_certified_2026_precinct",
            denominator=None, analysis_rate=None))
        properties = dict(key=f"NH|Manchester|Ward:{ward}", year=2026, state_code="NH",
            county="Manchester", county_fips=None, county_id="additional:NH:city:3345140",
            unit=f"Ward {ward}", unit_key=f"Manchester:Ward:{ward}", unit_kind="municipal_ward",
            reporting_unit_kind="municipal_ward", native_ward_number=ward, native_object_id=oid,
            source_snapshot=SNAPSHOT, match_status="matched_current_municipal_ward_reference",
            ballots=native["total"], denominator=None, reported_pct=None,
            native_record=native, source_url=row["source_url"],
            participation_measure_label="Native Total Ballots Cast",
            source_count_qualified=True, cast_ballot_count_qualified=False,
            unique_voter_count_qualified=False, maps_approved=True,
            source_election_date="2026-11-03", boundary_label=BOUNDARY,
            reference_geometry=dict(native_ward_number=ward, native_ward_label=p["Ward_ID"],
                layer_name="SDEweb.GISADMIN.Wards_2022", rest_layer_id=3,
                boundary_vintage=2022, current_clerk_effective_date="2021-12-21",
                certified_legal_boundaries=False, topology_valid_without_repairs=True,
                single_path_per_polygon=True, native_overlaps_preserved=True),
            quality_flags=row["quality_flags"], geometry_withheld_reason=None,
            rate_withheld_reason="Native counts only; no source electorate denominator or analysis turnout rate.",
            source_update_label=row["native_revision_label"] or "Native clock/timezone not supplied.",
            source_reporting_label="Literal native ward Total Ballots Cast. Election Day, absentee and federal-only "
                "fields remain separate; no federal addition, source repair or city-to-ward allocation.")
        joined.append(dict(type="Feature", properties=properties, geometry=feature["geometry"]))
    if actual_ids != set(ids["objectIds"]):
        raise ValueError("Full source object-ID query differs; not a complete native reference")
    if sum(feature["properties"]["ballots"] for feature in joined) != source["source_count"]:
        raise ValueError("Mapped raw ward totals differ from the preserved derived city count")
    overlaps = []
    for a,b in itertools.combinations(sorted(rings),2):
        area = rings[a].intersection(rings[b]).area
        if area > 0:
            overlaps.append(dict(wards=[a,b], native_projected_square_meters=area,
                overlap_over_smaller_native_ward_area=area/min(rings[a].area,rings[b].area)))
    expected_overlaps = native_review["nonzero_pairwise_overlaps"]
    if (len(overlaps) != len(expected_overlaps) or any(
            row["wards"] != old["wards"] or abs(row["native_projected_square_meters"]
                - old["native_projected_square_meters"]) > 1e-8
            for row,old in zip(overlaps,expected_overlaps))):
        raise ValueError("Unreviewed native boundary overlaps; no clipping or repairs")
    return dict(summary=dict(source_city_observations=4, retained_native_ward_rows=37,
        complete_native_source_fields=242, mapped_city="Manchester", mapped_wards=12,
        mapped_raw_ward_total_sum=sum(f["properties"]["ballots"] for f in joined),
        native_vertices_verified=vertex_count, native_overlap_pairs=len(overlaps),
        source_geometry_repaired=False, source_counts_repaired=False, native_federal_only_added=False,
        rates_approved=False, certified_legal_precinct_boundaries=False),
        complete_reference_queries=decisions, native_overlap_queries=overlaps,
        retained_city_source_queries=counts["source_queries"], retained_ward_source_rows=counts["ward_rows"],
        complete_ward_disposition_queries=[dict(city=row["city"], unit=row["unit"],
            native_source_count=row["source_count"], disposition="mapped_current_official_ward_reference"
            if row["city"] == "Manchester" else "held_table_only_no_qualified_ward_reference")
            for row in counts["ward_rows"]],
        geojson=dict(type="FeatureCollection", features=joined))


def load(root=ROOT):
    inputs = json.loads((root / VERSION / "inputs.json").read_bytes())
    bodies = {}
    for name,pin in inputs["files"].items():
        body = (root/name).read_bytes()
        if len(body) != pin["bytes"] or digest(body) != pin["sha256"]:
            raise ValueError("Changed complete ward input: "+name)
        bodies[name] = body

    def read(name):
        return json.loads(bodies[VERSION+"/"+name])

    counts = json.loads(gzip.decompress(bodies[inputs["complete_count_query_path"]]))
    return review(inputs, counts, read("manchester-wards2022-full-aggregate-original.geojson"),
        read("manchester-wards2022-native-projection-original.json"),
        read("manchester-wards2022-native-ids.json"), read("manchester-wards2022-native-count.json"),
        read("manchester-official-actual-ward-layer.json"), read("manchester-official-mapserver-layers.json"),
        read("manchester-current-ward-lines-safe-declaration.json"),
        read("manchester-native-projection-overlap-check-01.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(encoded(load(args.root)).decode(), end="")
