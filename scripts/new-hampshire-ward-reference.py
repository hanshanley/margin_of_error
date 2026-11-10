"""Extend the preserved ward-count queries with current Concord municipal context."""

import gzip
import hashlib
import itertools
import json
from pathlib import Path

from pyproj import Transformer, network
from shapely.geometry import MultiPoint, Polygon, shape


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/precinct-source-reviews/20261110-new-hampshire-ward-reference-02"
PUBLIC = "public/participation-precincts/20261110-new-hampshire-ward-reference-02"
SNAPSHOT = "new-hampshire-native-ward-reference-20261110-02"
BOUNDARY = "Current official Manchester and Concord municipal ward display references, not newly certified 2026 legal precincts"


def encoded(value):
    return (json.dumps(value,ensure_ascii=True,separators=(",",":"))+"\n").encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def review(base,geo,native,count,ids,layer,declaration,operation,transformations,independent):
    if (len(base["retained_city_source_queries"]) != 242 or len(base["retained_ward_source_rows"]) != 37
            or len(base["geojson"]["features"]) != 12
            or layer["id"] != 53 or layer["name"] != "Voting Wards"
            or layer["geometryType"] != "esriGeometryPolygon"
            or declaration["current_city_viewer_approval_date"] != "2021-11-08"
            or declaration["certified_legal2026_precinct_boundaries"] is not False
            or native["spatialReference"]["latestWkid"] != 3437):
        raise ValueError("Changed source count scope, actual ward layer or current-reference qualification")
    if transformations["transformations"][0]["geoTransforms"] != [
            dict(wkid=108190,latestWkid=108190,transformForward=False,name="WGS_1984_(ITRF00)_To_NAD_1983")]:
        raise ValueError("Unknown native datum operation; no default null-offset substitution")
    if operation["authority"] != "ESRI" or operation["code"] != 108190 or operation["direction"] != "inverse":
        raise ValueError("Changed native inverse datum operation")
    network.set_network_enabled(False)
    inverse_projection = Transformer.from_crs(3437,4269,always_xy=True)
    datum = Transformer.from_pipeline(operation["pipeline"])
    ward_rows = {row["native_ward"]:row for row in base["retained_ward_source_rows"] if row["city"] == "Concord"}
    projected = {row["attributes"]["Ward"]:row for row in native["features"]}
    if (len(geo["features"]) != count["count"] or count["count"] != len(ids["objectIds"])
            or count["count"] != 10 or len(native["features"]) != 10
            or set(ward_rows) != set(range(1,11)) or set(projected) != set(range(1,11))):
        raise ValueError("Incomplete native Concord ward inventory")
    seen,objects,polygons,wgs,queries,features = set(),set(),{},{},[],[]
    for feature in geo["features"]:
        p = feature["properties"]
        if set(p) != {"OBJECTID","Ward"}:
            raise ValueError("Unrequested population or personal fields")
        ward,oid = p["Ward"],p["OBJECTID"]
        if type(ward) is not int or ward not in ward_rows or ward in seen or oid in objects:
            raise ValueError("Ambiguous native Ward identity; OBJECTID is not a ward")
        seen.add(ward)
        objects.add(oid)
        source = projected[ward]
        if (source["attributes"] != p or feature["geometry"]["type"] != "Polygon"
                or len(feature["geometry"]["coordinates"]) != 1 or len(source["geometry"]["rings"]) != 1):
            raise ValueError("Changed source identity or unreviewed ring-role hierarchy")
        xy,ll = source["geometry"]["rings"][0],feature["geometry"]["coordinates"][0]
        if len(xy) != len(ll) or xy[0] != xy[-1] or ll[0] != ll[-1]:
            raise ValueError("Changed or unclosed source ring; no repairs")
        polygons[ward],wgs[ward] = Polygon(xy),shape(feature["geometry"])
        if not polygons[ward].is_valid or not wgs[ward].is_valid:
            raise ValueError("Invalid native geometry; no repairs")
        transformed = []
        for x,y in xy:
            lon,lat = inverse_projection.transform(x,y)
            outlat,outlon = datum.transform(lat,lon,direction="INVERSE")
            transformed.append((outlon,outlat))
        error = MultiPoint(transformed).hausdorff_distance(MultiPoint(ll))
        if error >= 1e-9:
            raise ValueError("Native coordinate/declared datum disagreement")
        row = ward_rows[ward]
        total = sum(cell["count"] for cell in row["native_record"]["total_cast_columns"])
        if (type(row["source_count"]) is not int or row["source_count"] < 0 or row["source_count"] != total
                or row["native_record"]["printed_ward_subtotal"] not in (None,total)
                or row["denominator"] is not None or row["reported_pct"] is not None):
            raise ValueError("Changed source Total Cast, school splits, printed subtotal or inferred rate")
        queries.append(dict(city="Concord",native_ward_number=ward,native_object_id=oid,
            source_total=total,native_vertices=len(xy),independent_projection_error_degrees=error,
            disposition="current_official_municipal_ward_count_display_not_certified_2026_precinct",
            denominator=None,analysis_rate=None))
        properties = dict(key=f"NH|Concord|Ward:{ward}",year=2026,state_code="NH",
            county="Concord",county_fips=None,county_id="additional:NH:city:3314200",
            unit=f"Ward {ward}",unit_key=row["source_unit_id"],unit_kind="municipal_ward",
            reporting_unit_kind="municipal_ward",native_ward_number=ward,native_object_id=oid,
            source_snapshot=SNAPSHOT,match_status="matched_current_municipal_ward_reference",
            ballots=total,denominator=None,reported_pct=None,native_record=row["native_record"],
            source_url=row["source_url"],source_count_qualified=True,cast_ballot_count_qualified=False,
            unique_voter_count_qualified=False,maps_approved=True,source_election_date="2026-11-03",
            participation_measure_label="Native Total Cast",
            boundary_label="Current city-declared Concord Voting Wards reference (city approval November 8, 2021); GIS service name PubWebGIS2020 is not a boundary vintage or certified 2026 legal precincts",
            reference_geometry=dict(native_ward_number=ward,native_ward_label=f"Ward {ward}",
                layer_name="Voting Wards",rest_layer_id=53,boundary_vintage=None,
                current_clerk_approval_date="2021-11-08",native_projection_epsg=3437,
                native_datum_operation=dict(wkid=108190,forward=False),
                certified_legal_boundaries=False,topology_valid_without_repairs=True,
                single_path_per_polygon=True,native_overlaps_preserved=True),
            quality_flags=row["quality_flags"],geometry_withheld_reason=None,
            rate_withheld_reason="Native Total Cast only. Opening, Election Day and closing registers and printed percentages remain source diagnostics, not analysis denominators or rates.",
            source_update_label="Native clock/timezone not supplied.",
            source_reporting_label="Native school-district cells and separately printed ward subtotals remain unchanged. No city-to-ward allocation, source repair or inferred rate.")
        features.append(dict(type="Feature",properties=properties,geometry=feature["geometry"]))
    if objects != set(ids["objectIds"]) or sum(f["properties"]["ballots"] for f in features) != 19234:
        raise ValueError("Full native IDs or raw ward counts differ from printed Concord city parent")
    pairs = [dict(wards=[a,b],native_projected_US_survey_feet_squared=polygons[a].intersection(polygons[b]).area,
        geographic_square_degrees=wgs[a].intersection(wgs[b]).area,no_source_repairs_or_clipping=True)
        for a,b in itertools.combinations(sorted(polygons),2)]
    if pairs != independent["complete_pairwise_queries"]:
        raise ValueError("Changed native/reference overlap decisions; no clipping or repairs")
    features.sort(key=lambda f:f["properties"]["native_ward_number"])
    return dict(summary=dict(source_city_observations=4,retained_native_ward_rows=37,
        complete_native_source_fields=242,mapped_cities=dict(Manchester=12,Concord=10),
        mapped_wards=22,held_table_only_ward_rows=15,
        raw_count_checks_by_city=dict(Manchester=38562,Concord=19234),
        native_vertices_verified=base["summary"]["native_vertices_verified"]+sum(q["native_vertices"] for q in queries),
        native_overlap_pairs=6+sum(q["native_projected_US_survey_feet_squared"]>0 for q in pairs),
        source_geometry_repaired=False,source_counts_repaired=False,native_federal_only_added=False,
        rates_approved=False,certified_legal_precinct_boundaries=False),
        complete_reference_queries=[*base["complete_reference_queries"],*queries],
        retained_manchester_overlap_queries=base["native_overlap_queries"],
        complete_concord_pairwise_queries=pairs,
        retained_city_source_queries=base["retained_city_source_queries"],
        retained_ward_source_rows=base["retained_ward_source_rows"],
        complete_ward_disposition_queries=[dict(city=row["city"],unit=row["unit"],
            native_source_count=row["source_count"],disposition="mapped_current_official_ward_reference"
            if row["city"] in ["Manchester","Concord"] else "held_table_only_no_qualified_ward_reference")
            for row in base["retained_ward_source_rows"]],
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
    return review(base,read("concord-full-aggregate-original.geojson"),
        read("concord-native-projection-original.json"),read("concord-native-count.json"),
        read("concord-native-ids.json"),read("concord-actual-ward-layer-original.json"),
        read("concord-current-ward-safe-declaration.json"),
        read("concord-esri108190-independent-projection-operation.json"),
        read("concord-native-datum-transformations-original.json"),
        read("concord-all10-native-ward-reference-review-01.json"))
