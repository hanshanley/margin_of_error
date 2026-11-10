import argparse
import datetime
import hashlib
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request
import zipfile

from pyproj import CRS, Transformer
import shapefile
from shapely.geometry import shape


parser = argparse.ArgumentParser()
parser.add_argument("--acquire", action="store_true")
parser.add_argument("--root", type=Path)
parser.add_argument("--prior-root", type=Path)
parser.add_argument("--output", type=Path)
parser.add_argument("--native-review", type=Path)
parser.add_argument("--geometry-server-receipt", type=Path)
args = parser.parse_args()
FILES = Path(__file__).resolve().parent
ROOT = args.root or FILES / "somerville-independent-remaining-boundary-leads-01"
ORIGINALS = args.prior_root or FILES / "massachusetts-independent-city-sources-20261110-01"
OUTPUT = args.output or ROOT
native_review = json.loads((args.native_review or ROOT / "native-only-review.json").read_bytes())
assert native_review["summary"]["native_valid_shapes"] == 32
server = json.loads((args.geometry_server_receipt or ORIGINALS /
    "geometry-discovery-01/massgis-declared-geometry-server.safe-receipt.json").read_bytes())
BASE = server["source"].split("?")[0]
with zipfile.ZipFile(ROOT / "city-declared-precinct-original.zip") as archive:
    wkt = archive.read("Precincts.prj").decode()
    reader = shapefile.Reader(shp=io.BytesIO(archive.read("Precincts.shp")),
                              shx=io.BytesIO(archive.read("Precincts.shx")),
                              dbf=io.BytesIO(archive.read("Precincts.dbf")))
    native_shapes = list(reader.iterShapeRecords())
    bounds = reader.bbox
sr = dict(wkt=wkt)
geometries = []
for native in native_shapes:
    parts = list(native.shape.parts) + [len(native.shape.points)]
    geometries.append(dict(rings=[native.shape.points[start:end]
                                  for start, end in zip(parts, parts[1:])]))


def acquire(name, method, parameters):
    request_path = ROOT / (name+"-request.json")
    response_path = ROOT / (name+"-response.json")
    receipt_path = ROOT / (name+"-receipt.json")
    if args.acquire:
        assert not any(path.exists() for path in [request_path, response_path, receipt_path])
        request_path.write_text(json.dumps(parameters, indent=2)+"\n")
        encoded = urllib.parse.urlencode(parameters).encode()
        endpoint = BASE + "/" + method
        request = (urllib.request.Request(endpoint, data=encoded) if method == "project" else
                   urllib.request.Request(endpoint + "?" + encoded.decode()))
        with urllib.request.urlopen(request, timeout=90) as response:
            assert response.status == 200
            body = response.read(2000001)
            assert len(body) <= 2000000
        response_path.write_bytes(body)
        receipt_path.write_text(json.dumps(dict(
            source=endpoint, method=request.get_method(), status=200, bytes=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            request_sha256=hashlib.sha256(request_path.read_bytes()).hexdigest(),
            retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            public_original_coordinates_only=True), indent=2)+"\n")
    assert json.loads(request_path.read_bytes()) == parameters
    receipt = json.loads(receipt_path.read_bytes())
    body = response_path.read_bytes()
    assert receipt["status"] == 200 and receipt["sha256"] == hashlib.sha256(body).hexdigest()
    assert receipt["request_sha256"] == hashlib.sha256(request_path.read_bytes()).hexdigest()
    result = json.loads(body)
    assert "error" not in result, result
    return result


declaration = acquire("exact-wkt-transformations", "findTransformations", dict(
    f="json", inSR=json.dumps(sr), outSR=4326, numOfResults=3,
    extentOfInterest=json.dumps(dict(xmin=bounds[0], ymin=bounds[1],
                                    xmax=bounds[2], ymax=bounds[3], spatialReference=sr))))
operation = declaration["transformations"][0]
assert operation["geoTransforms"] == [
    dict(wkid=108190, latestWkid=108190, transformForward=False,
         name="WGS_1984_(ITRF00)_To_NAD_1983")]
projected = acquire("all32-exact-wkt-geographic", "project", dict(
    f="json", inSR=json.dumps(sr), outSR=4326,
    transformation=json.dumps(operation), transformForward="true",
    geometries=json.dumps(dict(geometryType="esriGeometryPolygon", geometries=geometries))))
assert len(projected["geometries"]) == len(native_shapes) == 32
definitions = json.loads((ORIGINALS /
    "geometry-discovery-01/massgis-independent-declared-datum-operations.json").read_bytes())
inverse_projection = Transformer.from_crs(CRS.from_wkt(wkt), 4269, always_xy=True)
datum = Transformer.from_pipeline(definitions["operations"]["108190"]["pipeline"])
default = Transformer.from_crs(CRS.from_wkt(wkt), 4326, always_xy=True)
features, decisions = [], []
for native, source, result in zip(native_shapes, geometries, projected["geometries"]):
    assert len(source["rings"]) == len(result["rings"])
    errors, default_errors, alignments = [], [], []
    for original_ring, geographic_ring in zip(source["rings"], result["rings"]):
        assert len(original_ring) == len(geographic_ring)
        assert original_ring[0] == original_ring[-1]
        assert geographic_ring[0] == geographic_ring[-1]
        expected, defaults = [], []
        for x, y in original_ring[:-1]:
            lon, lat = inverse_projection.transform(x, y)
            expected_lat, expected_lon = datum.transform(lat, lon, direction="INVERSE")
            expected.append((expected_lon, expected_lat))
            defaults.append(default.transform(x, y))
        actual = geographic_ring[:-1]
        candidates = []
        for start, point in enumerate(actual):
            if max(abs(a-b) for a, b in zip(expected[0], point)) > 1e-9:
                continue
            for direction in [1, -1]:
                aligned = [actual[(start+direction*i) % len(actual)] for i in range(len(actual))]
                candidate_errors = [max(abs(a-b) for a, b in zip(left, right))
                                    for left, right in zip(expected, aligned)]
                candidates.append((max(candidate_errors), start, direction, aligned, candidate_errors))
        assert candidates, "Missing native vertex; do not repair or relax tolerance"
        error, start, direction, aligned, candidate_errors = min(candidates, key=lambda row: row[0])
        assert error <= 1e-9, "Changed vertex adjacency; arbitrary sorting is not sufficient"
        errors.extend(candidate_errors+[candidate_errors[0]])
        null_errors = [max(abs(a-b) for a, b in zip(left, right))
                       for left, right in zip(defaults, aligned)]
        default_errors.extend(null_errors+[null_errors[0]])
        alignments.append(dict(cyclic_start_offset=start, direction=direction))
    assert max(errors) <= 1e-9 and max(default_errors) > 1e-9
    label = native.record.as_dict()["Precinct"]
    assert len(source["rings"]) == len(result["rings"]) == 1
    geographic = dict(type="Polygon", coordinates=result["rings"])
    assert shape(geographic).is_valid
    features.append(dict(type="Feature", properties=dict(native_label=label),
                         geometry=geographic))
    decisions.append(dict(
        native_label=label, checked_vertices=len(errors),
        maximum_error_degrees=max(errors),
        rejected_default_error_degrees=max(default_errors),
        geographic_valid=True, cyclic_vertex_adjacency_preserved=True,
        server_ring_alignments=alignments))
summary = dict(
    status="PASS_32_native_city_references_independent_geographic_check_NOT_website_acceptance",
    source_shapes=32, checked_vertices=sum(row["checked_vertices"] for row in decisions),
    maximum_error_degrees=max(row["maximum_error_degrees"] for row in decisions),
    strict_tolerance_degrees=1e-9, exact_original_wkt_preserved=True,
    declared_datum_operation=dict(authority="ESRI", code=108190, direction="inverse"),
    default_null_offset_and_inexact_EPSG_alias_rejected=True,
    four_prior_holds_have_direct_native_city_shapes=True,
    original_labels_and_duplicate_native_ids_retained=True,
    no_clipping_allocation_source_repair_or_rates=True,
    published_release_changed=False, maps_approved=False)
for name, value in [
    ("verified32-city-display-reference.geojson", dict(type="FeatureCollection", features=features)),
    ("geographic-review.json", dict(summary=summary, all_decisions=decisions)),
]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / name
    assert not path.exists()
    path.write_text(json.dumps(value, indent=2)+"\n")
print(json.dumps(summary))
