"""Preserve all earlier ward queries and join literal Nashua source totals."""

import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon, shape


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/precinct-source-reviews/20261110-new-hampshire-ward-reference-03"
PUBLIC = "public/participation-precincts/20261110-new-hampshire-ward-reference-03"
SNAPSHOT = "new-hampshire-native-ward-reference-20261110-03"
BOUNDARY = "Official municipal ward display references in Manchester, Concord and Nashua, not newly certified 2026 legal precincts"


def encoded(value):
    return (json.dumps(value,ensure_ascii=True,separators=(",",":"))+"\n").encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def review(base,geo,native,count,ids,layer,declaration,independent):
    if (len(base["retained_city_source_queries"]) != 242 or len(base["retained_ward_source_rows"]) != 37
            or len(base["geojson"]["features"]) != 22 or layer["id"] != 7
            or layer["name"] != "Ward Boundary (Adopted December 28, 2021)"
            or layer["geometryType"] != "esriGeometryPolygon"
            or declaration["adopted_source_date"] != "2021-12-28"
            or declaration["effective_source_date"] != "2021-12-28"
            or declaration["certified_legal2026_precinct_boundaries"] is not False
            or native["spatialReference"]["latestWkid"] != 3857):
        raise ValueError("Changed source count scope or actual adopted ward reference role/date")
    rows = {r["native_ward"]:r for r in base["retained_ward_source_rows"] if r["city"] == "Nashua"}
    projected = {f["attributes"]["Ward"]:f for f in native["features"]}
    if (len(geo["features"]) != count["count"] or count["count"] != len(ids["objectIds"])
            or count["count"] != 9 or len(native["features"]) != 9
            or set(rows) != set(range(1,10)) or set(projected) != set(range(1,10))):
        raise ValueError("Incomplete native adopted ward inventory")
    seen,objects,polygons,wgs,queries,features = set(),set(),{},{},[],[]
    for feature in geo["features"]:
        p = feature["properties"]
        if set(p) != {"OBJECTID","Ward","Wardtxt"}:
            raise ValueError("Unrequested personal or population fields")
        ward,oid = p["Ward"],p["OBJECTID"]
        if type(ward) is not int or ward not in rows or ward in seen or oid in objects or p["Wardtxt"] != str(ward):
            raise ValueError("Ambiguous native Ward identity; OBJECTID is not a ward")
        seen.add(ward)
        objects.add(oid)
        original = projected[ward]
        if (original["attributes"] != p or feature["geometry"]["type"] != "Polygon"
                or len(feature["geometry"]["coordinates"]) != 1 or len(original["geometry"]["rings"]) != 1):
            raise ValueError("Changed native identity or unreviewed ring-role hierarchy")
        xy,ll = original["geometry"]["rings"][0],feature["geometry"]["coordinates"][0]
        if len(xy) != len(ll) or xy[0] != xy[-1] or ll[0] != ll[-1]:
            raise ValueError("Changed/unclosed source ring; no repairs")
        polygons[ward],wgs[ward] = Polygon(xy),shape(feature["geometry"])
        if not polygons[ward].is_valid or not wgs[ward].is_valid:
            raise ValueError("Invalid source geometry; no repairs")
        expected = [(x/6378137*180/math.pi,math.degrees(math.atan(math.sinh(y/6378137)))) for x,y in xy]
        error = MultiPoint(expected).hausdorff_distance(MultiPoint(ll))
        if error >= 1e-10:
            raise ValueError("Native geographic/projected coordinate disagreement")
        row,n = rows[ward],rows[ward]["native_record"]
        if (n["ward"] != ward or row["source_count"] != n["total"] or row["denominator"] is not None
                or row["reported_pct"] is not None or any(type(n[k]) is not int or n[k] < 0
                for k in ["election_day","absentee","total","federal_only"])):
            raise ValueError("Changed literal native source total or inferred rate")
        queries.append(dict(city="Nashua",native_ward_number=ward,native_object_id=oid,
            native_ward_text=p["Wardtxt"],source_total=n["total"],native_vertices=len(xy),
            inverse_mercator_error_degrees=error,
            source_component_minus_printed_total=n["election_day"]+n["absentee"]-n["total"],
            source_federal_only_separate=n["federal_only"],denominator=None,analysis_rate=None,
            disposition="adopted_official_municipal_ward_count_display_not_certified_2026_precinct"))
        properties = dict(key=f"NH|Nashua|Ward:{ward}",year=2026,state_code="NH",
            county="Nashua",county_fips=None,county_id="additional:NH:city:3350260",
            unit=f"Ward {ward}",unit_key=row["source_unit_id"],unit_kind="municipal_ward",
            reporting_unit_kind="municipal_ward",native_ward_number=ward,native_object_id=oid,
            source_snapshot=SNAPSHOT,match_status="matched_current_municipal_ward_reference",
            ballots=n["total"],denominator=None,reported_pct=None,native_record=n,
            source_url=row["source_url"],source_count_qualified=True,cast_ballot_count_qualified=False,
            unique_voter_count_qualified=False,maps_approved=True,source_election_date="2026-11-03",
            participation_measure_label="Native Total Ballots Cast",
            boundary_label="City-published adopted Nashua municipal wards (adopted/effective December 28, 2021; current full city map prints October 2026), not newly certified 2026 legal precincts",
            reference_geometry=dict(native_ward_number=ward,native_ward_label=f"Ward {ward}",
                layer_name="Ward Boundary (Adopted December 28, 2021)",rest_layer_id=7,
                boundary_vintage=None,adopted_date="2021-12-28",effective_date="2021-12-28",
                current_map_effective_literal="OCTOBER 2026",current_map_revised_literal="OCTOBER 2026",
                proposed_geometry_used=False,native_projection_epsg=3857,
                certified_legal_boundaries=False,topology_valid_without_repairs=True,
                single_path_per_polygon=True,native_overlaps_preserved=True),
            quality_flags=row["quality_flags"],geometry_withheld_reason=None,
            rate_withheld_reason="Native counts only; no source electorate denominator or analysis turnout rate.",
            source_update_label=row["native_revision_label"] or "Native clock/timezone not supplied.",
            source_reporting_label="Literal native ward Total Ballots Cast; amendments and source component conflicts remain unchanged. Federal-only fields stay separate, never added.")
        features.append(dict(type="Feature",properties=properties,geometry=feature["geometry"]))
    if objects != set(ids["objectIds"]) or sum(f["properties"]["ballots"] for f in features) != 33849:
        raise ValueError("Changed full native IDs or raw derived ward-total sum")
    queries.sort(key=lambda r:r["native_ward_number"])
    if ([(r["native_ward_number"],r["source_component_minus_printed_total"]) for r in queries
            if r["source_component_minus_printed_total"]] != [(3,1),(4,-2),(8,-1)]
            or sum(r["source_federal_only_separate"] for r in queries) != 92):
        raise ValueError("Source native conflicts or separate federal-only accounting changed")
    pairs = [dict(wards=[a,b],native_projected_square_meters=polygons[a].intersection(polygons[b]).area,
        geographic_square_degrees=wgs[a].intersection(wgs[b]).area,
        overlap_over_smaller_native_ward_area=polygons[a].intersection(polygons[b]).area/min(polygons[a].area,polygons[b].area),
        native_overlaps_preserved_not_repaired=True) for a,b in itertools.combinations(sorted(polygons),2)]
    if pairs != independent["complete_pairwise_queries"]:
        raise ValueError("Changed native pair decisions; no clipping or repairs")
    features.sort(key=lambda f:f["properties"]["native_ward_number"])
    summary = dict(base["summary"],mapped_cities=dict(Manchester=12,Concord=10,Nashua=9),
        mapped_wards=31,held_table_only_ward_rows=6,
        raw_count_checks_by_city=dict(Manchester=38562,Concord=19234,Nashua=33849),
        native_vertices_verified=base["summary"]["native_vertices_verified"]+sum(r["native_vertices"] for r in queries))
    return dict(base,summary=summary,
        complete_reference_queries=[*base["complete_reference_queries"],*queries],
        complete_nashua_pairwise_queries=pairs,
        complete_ward_disposition_queries=[dict(city=r["city"],unit=r["unit"],
            native_source_count=r["source_count"],disposition="mapped_current_official_ward_reference"
            if r["city"] in ["Manchester","Concord","Nashua"] else "held_table_only_no_qualified_ward_reference")
            for r in base["retained_ward_source_rows"]],
        geojson=dict(type="FeatureCollection",features=[*base["geojson"]["features"],*features]))


def load(root=ROOT):
    inputs = json.loads((root/VERSION/"inputs.json").read_bytes())
    bodies = {}
    for name,pin in inputs["files"].items():
        body = (root/name).read_bytes()
        if len(body) != pin["bytes"] or digest(body) != pin["sha256"]:
            raise ValueError("Changed sufficient original: "+name)
        bodies[name] = body
    def read(name):
        return json.loads(bodies[VERSION+"/"+name])
    base = json.loads(gzip.decompress(bodies[inputs["previous_ward_query_path"]]))
    return review(base,read("nashua-adopted2021-full-aggregate-original.geojson"),
        read("nashua-adopted2021-native-projection-original.json"),read("nashua-adopted2021-native-count.json"),
        read("nashua-adopted2021-native-ids.json"),read("adopted-ward-layer7-original.json"),
        read("nashua-independent-adopted-ward-safe-declaration.json"),
        read("nashua-all9-adopted-native-ward-reference-review-01.json"))
