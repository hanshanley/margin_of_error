"""Join all six direct Dover ward references without changing prior source counts."""

import gzip
import hashlib
import itertools
import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import Polygon, shape


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/precinct-source-reviews/20261110-new-hampshire-ward-reference-04"
PUBLIC = "public/participation-precincts/20261110-new-hampshire-ward-reference-04"
SNAPSHOT = "new-hampshire-native-ward-reference-20261110-04"
BOUNDARY = "Official municipal ward display references in four New Hampshire cities, not certified 2026 legal precincts"


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":"))+"\n").encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def review(base, geo, native, count, ids, layer, declaration, independent, transformations):
    if (len(base["retained_city_source_queries"]) != 242 or len(base["retained_ward_source_rows"]) != 37
            or len(base["geojson"]["features"]) != 31 or layer["id"] != 11
            or layer["name"] != "NHPolitDists_VW_2022" or layer["geometryType"] != "esriGeometryPolygon"
            or declaration["source_owner"] != "NHGRANIT" or declaration["source_reference_vintage"] != 2022
            or declaration["source_item_id"] != "3d1a8bdf3eaa49e09cf5d9da5b56bf9c"
            or declaration["actual_ward_layer_id"] != 11
            or declaration["certified_legal2026_precinct_boundaries"] is not False
            or native["spatialReference"] != dict(wkid=102710, latestWkid=3437)
            or transformations["transformations"][0]["geoTransforms"] != [
                dict(wkid=108190, latestWkid=108190, transformForward=False,
                     name="WGS_1984_(ITRF00)_To_NAD_1983")]):
        raise ValueError("Changed source scope, actual2022 ward role or declared datum operation")
    rows = {row["native_ward"]: row for row in base["retained_ward_source_rows"] if row["city"] == "Dover"}
    projected = {feature["attributes"]["fid"]: feature for feature in native["features"]}
    if (set(rows) != set(range(1, 7)) or count["count"] != 6 or len(ids["objectIds"]) != 6
            or len(projected) != 6 or len(geo["features"]) != 6
            or set(projected) != set(ids["objectIds"])):
        raise ValueError("Incomplete native Dover inventory")
    checks = {row["native_ward"]: row for row in independent["all_native_reference_decisions"]}
    inverse = Transformer.from_crs(3437, 4269, always_xy=True)
    datum = Transformer.from_pipeline("ESRI:108190")
    wrong = Transformer.from_crs(3437, 4326, always_xy=True)
    features, queries, polygons, seen = [], [], {}, set()
    for feature in geo["features"]:
        p = feature["properties"]
        if set(p) != {"fid", "name", "county", "fips", "district"}:
            raise ValueError("Unrequested population, address or personal fields")
        ward = next((ward for ward in range(1, 7) if p["district"] == f"Dover Ward {ward}"), None)
        if ward is None or ward in seen or p["name"] != "Dover" or p["county"] != "Strafford" or p["fips"] != 17010:
            raise ValueError("Ambiguous native district identity; FID and nativeFIPS are not ward/county IDs")
        seen.add(ward)
        original = projected.get(p["fid"])
        if (original is None or original["attributes"] != p or feature["geometry"]["type"] != "Polygon"
                or len(feature["geometry"]["coordinates"]) != 1 or len(original["geometry"]["rings"]) != 1):
            raise ValueError("Changed original identity or ring roles")
        xy, ll = original["geometry"]["rings"][0], feature["geometry"]["coordinates"][0]
        if len(xy) != len(ll) or xy[0] != xy[-1] or ll[0] != ll[-1]:
            raise ValueError("Unclosed source ring; no repairs")
        polygon, geographic = Polygon(xy), shape(feature["geometry"])
        if not polygon.is_valid or not geographic.is_valid:
            raise ValueError("Invalid source geometry; no repairs")
        check = checks[ward]
        start, direction = check["server_ring_start"], check["server_ring_direction"]
        if direction not in [-1, 1] or type(start) is not int or not 0 <= start < len(ll)-1:
            raise ValueError("Invalid independent cyclic adjacency check")
        error, default_error = 0, 0
        for index, (x, y) in enumerate(xy[:-1]):
            actual = ll[(start+direction*index) % (len(ll)-1)]
            lon, lat = inverse.transform(x, y)
            expected_lat, expected_lon = datum.transform(lat, lon, direction="INVERSE")
            error = max(error, abs(expected_lon-actual[0]), abs(expected_lat-actual[1]))
            default_lon, default_lat = wrong.transform(x, y)
            default_error = max(default_error, abs(default_lon-actual[0]), abs(default_lat-actual[1]))
        if (error > 1e-9 or default_error <= 1e-9 or check["maximum_projection_error_degrees"] != error
                or check["cyclic_vertex_adjacency_preserved"] is not True
                or check["source_count_join_qualified"] is not True):
            raise ValueError("Changed native vertices/edges or substituted null-offset datum")
        row = rows[ward]
        n = row["native_record"]
        if (n["ballots"]["ward"] != ward or n["registrations"]["ward"] != ward
                or row["source_count"] != n["ballots"]["total"]
                or n["ballots"]["registered"] != n["registrations"]["registered"]
                or row["denominator"] is not None or row["reported_pct"] is not None
                or check["native_count"] != row["source_count"]):
            raise ValueError("Changed native count, register or inferred rate")
        polygons[ward] = polygon
        queries.append(dict(city="Dover", native_ward_number=ward, native_object_id=p["fid"],
            native_district=p["district"], native_fips=p["fips"], source_total=row["source_count"],
            native_vertices=len(xy), projection_error_degrees=error,
            rejected_null_offset_error_degrees=default_error, cyclic_vertex_adjacency_verified=True,
            native_projected_area_units="US_survey_feet_squared_NOT_geodesic",
            denominator=None, analysis_rate=None, disposition="direct_state2022_municipal_reference_not_certified2026"))
        properties = dict(
            key=f"NH|Dover|Ward:{ward}", year=2026, state_code="NH", county="Dover", county_fips=None,
            county_id="additional:NH:city:3318820", unit=f"Ward {ward}", unit_key=row["source_unit_id"],
            unit_kind="municipal_ward", reporting_unit_kind="municipal_ward", native_ward_number=ward,
            native_object_id=p["fid"], native_district=p["district"], source_snapshot=SNAPSHOT,
            match_status="matched_current_municipal_ward_reference", ballots=row["source_count"],
            denominator=None, reported_pct=None, native_record=n, source_url=row["source_url"],
            source_count_qualified=True, cast_ballot_count_qualified=False, unique_voter_count_qualified=False,
            maps_approved=True, source_election_date="2026-11-03",
            participation_measure_label="Native Total Ballots Cast",
            boundary_label="NHGRANIT state-published2022 Dover voting wards; municipal display context, not certified2026 legal precincts",
            reference_geometry=dict(native_ward_number=ward, native_ward_label=p["district"],
                layer_name="NHPolitDists_VW_2022", rest_layer_id=11, boundary_vintage=2022,
                source_item_id=declaration["source_item_id"], source_owner="NHGRANIT",
                native_projection_epsg=3437, native_datum_operation=dict(authority="ESRI", code=108190, direction="inverse"),
                native_fips=17010, native_fips_is_not_a_county_id=True,
                certified_legal_boundaries=False, topology_valid_without_repairs=True,
                single_path_per_polygon=True, cyclic_vertex_adjacency_verified=True,
                source_geometry_clipped=False, native_overlaps_preserved=True),
            quality_flags=row["quality_flags"], geometry_withheld_reason=None,
            rate_withheld_reason="Native counts only; no qualified unique-person count or analysis turnout rate.",
            source_update_label="Native election November3,2026; checklist verifiedOctober26,2026; source clock/timezone not supplied.",
            source_reporting_label="Literal native ward Total Ballots Cast and source registers remain separate. Registration affiliations are not ballot choices or group-participation numerators; printed percentages are not promoted to analysis rates.")
        features.append(dict(type="Feature", properties=properties, geometry=feature["geometry"]))
    if sum(feature["properties"]["ballots"] for feature in features) != 15941:
        raise ValueError("Ward source counts differ from printed native city parent")
    pairs = [dict(left_native_ward=a, right_native_ward=b,
        native_overlap_area=polygons[a].intersection(polygons[b]).area,
        positive_native_overlap=polygons[a].intersection(polygons[b]).area > 0,
        native_projected_area_units="US_survey_feet_squared_NOT_geodesic", source_geometry_repaired=False)
        for a, b in itertools.combinations(sorted(polygons), 2)]
    if pairs != independent["all_native_pair_decisions"]:
        raise ValueError("Changed native pair decisions; no clipping or repairs")
    features.sort(key=lambda feature: feature["properties"]["native_ward_number"])
    queries.sort(key=lambda row: row["native_ward_number"])
    return dict(base,
        summary=dict(base["summary"], mapped_cities=dict(Manchester=12, Concord=10, Nashua=9, Dover=6),
            mapped_wards=37, held_table_only_ward_rows=0,
            raw_count_checks_by_city=dict(Manchester=38562, Concord=19234, Nashua=33849, Dover=15941),
            native_vertices_verified=base["summary"]["native_vertices_verified"]+1987),
        complete_reference_queries=[*base["complete_reference_queries"], *queries],
        complete_dover_pairwise_queries=pairs,
        complete_ward_disposition_queries=[dict(city=row["city"], unit=row["unit"],
            native_source_count=row["source_count"], disposition="mapped_current_official_ward_reference")
            for row in base["retained_ward_source_rows"]],
        geojson=dict(type="FeatureCollection", features=[*base["geojson"]["features"], *features]))


def load(root=ROOT):
    inputs = json.loads((root / VERSION / "inputs.json").read_bytes())
    bodies = {}
    for name, pin in inputs["files"].items():
        body = (root / name).read_bytes()
        if len(body) != pin["bytes"] or digest(body) != pin["sha256"]:
            raise ValueError("Changed sufficient original: " + name)
        bodies[name] = body
    def read(name):
        return json.loads(bodies[VERSION+"/"+name])
    return review(json.loads(gzip.decompress(bodies[inputs["previous_ward_query_path"]])),
        read("granit-dover2022-full-geographic-original.geojson"),
        read("granit-dover2022-full-native-projected-original.json"),
        read("granit-dover2022-native-count.json"), read("granit-dover2022-native-ids.json"),
        read("granit-2022-voting-ward-layer11.json"), read("dover-granit-safe-source-declaration.json"),
        read("complete-native-ward-reference-review.json"),
        read("granit-declared-3437-4326-transformations.json"))
