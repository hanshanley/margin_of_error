"""Join native geographic ballot counts to the unrepaired valid app-reference subset."""

import argparse
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import re

from shapely.geometry import MultiPolygon, Polygon
from shapely.strtree import STRtree


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/precinct-source-reviews/20261110-alaska-native-display-01"
PUBLIC = "public/participation-precincts/20261110-alaska-native-display-01"
SNAPSHOT = "alaska-native-display-20261110-01"
SOURCE = "https://www.elections.alaska.gov/enr/26GENR/"
BOUNDARY = "Official 2026 Alaska app reference, valid unrepaired subset; not certified legal boundaries"
DOWNLOAD = ("https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-alaska-native-display-20261110-01/complete-analysis.zip")
RATE_HOLD = ("Geographic House units omit separately pooled absentee, early and question ballots; "
             "no pooled or overseas allocation and no full-election precinct turnout rate.")


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n").encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def decode_single_path_groups(row):
    coordinates, text = [], [row["number"] + "\n"]
    for polygon_index, group in enumerate(row["coords"]):
        if len(group) != 1:
            raise ValueError("Multiple native paths require separate ring-role qualification")
        tokens = group[0].split()
        if len(tokens) < 8 or len(tokens) % 2:
            raise ValueError("Incomplete native path")
        if any(not re.fullmatch(r"-?(?:\d+(?:\.\d{1,3})?|\.\d{1,3})", t) for t in tokens):
            raise ValueError("Unqualified native coordinate precision")
        values = [int(Decimal(t) * 1000) for t in tokens]
        x = y = 0
        path, integers = [], []
        text.append(f"{polygon_index}/0\n")
        for i in range(0, len(values), 2):
            x += values[i]
            y += values[i + 1]
            if not (-180000 <= x <= 180000 and -90000 <= y <= 90000):
                raise ValueError("Coordinates outside longitude/latitude range")
            integers.append((x, y))
            path.append([x / 1000, y / 1000])
            text.append(f"{x},{y};")
        text.append("\n")
        if integers[0] != integers[-1]:
            raise ValueError("Unclosed source ring; no implicit closure allowed")
        if any(abs(a[0] - b[0]) > 180000 for a, b in zip(integers, integers[1:])):
            raise ValueError("Unqualified antimeridian source jump")
        coordinates.append([path])
    shape = MultiPolygon([Polygon(p[0]) for p in coordinates])
    if shape.is_empty or not shape.is_valid or shape.area <= 0:
        raise ValueError("Invalid source geometry; no repair allowed")
    return coordinates, shape, digest("".join(text).encode())


def review(shapes, counts, native, topology, independent, facts):
    expected_contract = {
        "region_identifier_field": "number", "region_polygons_field": "coords",
        "one_polygon_per_coords_outer_group": True, "one_closed_path_per_inner_string": True,
        "coordinate_pair_order": "longitude latitude", "coordinate_accumulator_reset_each_path": True,
        "first_pair_from_zero_is_absolute_position": True, "subsequent_pairs_are_deltas": True,
        "native_rendering_constructor": "google.maps.Polygon",
        "native_paths_input": "all decoded paths within one polygon group",
    }
    if facts["contract"] != expected_contract or facts["publisher_entry_url"] != SOURCE:
        raise ValueError("Unqualified native display contract")
    if (native["name"] != "Alaska 2026 General Election" or native["certified"] is not False
            or native["updated"] != "11/04/2026 2:11 PM"
            or native["contestNames"].count("U.S. Representative") != 1):
        raise ValueError("Changed native election or clock")
    contest = native["contestNames"].index("U.S. Representative")
    native_by_id = {r["number"]: r for r in native["precincts"]}
    shape_by_id = {r["number"]: r for r in shapes}
    topo = {r["native_precinct_id"]: r for r in topology["queries"]}
    hashes = {r["native_precinct_id"]: r for r in independent["queries"]}
    ids = set(native_by_id)
    if (len(ids) != 402 or len(native["precincts"]) != 402 or len(shapes) != 402
            or len(topology["queries"]) != 402 or len(independent["queries"]) != 402
            or set(shape_by_id) != ids or set(topo) != ids or set(hashes) != ids):
        raise ValueError("Incomplete or duplicate native shape/count/review identities")
    if (len(counts) != 523 or len({r["key"] for r in counts}) != 523
            or Counter(r["reporting_unit_kind"] for r in counts) != {
                "geographic_precinct": 402, "pooled_district_absentee": 40,
                "pooled_district_early_voting": 40, "pooled_district_question": 40,
                "federal_overseas": 1}):
        raise ValueError("Incomplete geographic/pooled/federal source-unit query")
    if any(r["year"] != 2026 or r["state_code"] != "AK" or r["reported_pct"] is not None
           or type(r["ballots"]) is not int or r["ballots"] < 0
           or type(r["registered"]) is not int or r["registered"] < 0 for r in counts):
        raise ValueError("Unqualified native counts or inferred rates")
    total = next(r for r in native["totals"] if r["n"] == contest)
    if (sum(r["ballots"] for r in counts) != total["b"]
            or sum(r["registered"] for r in counts) != total["v"]
            or total["b"] != 215906 or total["v"] != 605433):
        raise ValueError("Full source-unit ballot/registration parent disagreement")
    geographic = [r for r in counts if r["reporting_unit_kind"] == "geographic_precinct"]
    if len({r["source_precinct_id"] for r in geographic}) != 402 or {
            r["source_precinct_id"] for r in geographic} != ids:
        raise ValueError("Geographic count identities differ")
    features, decisions, selected_shapes = [], [], []
    for count in geographic:
        identity = count["source_precinct_id"]
        unit = native_by_id[identity]
        records = [r for r in unit["contests"] if r["n"] == contest]
        if len(records) != 1:
            raise ValueError("Missing or duplicate native House reporting unit")
        record = records[0]
        if (type(record["b"]) is not int or type(record["v"]) is not int
                or count["ballots"] != record["b"] or count["registered"] != record["v"]
                or count["precinct"] != identity + " " + unit["name"]):
            raise ValueError("Literal native ballot/registration/identity disagreement")
        decision = dict(topo[identity])
        approved = decision["topology_valid_without_repairs"]
        decision.update(map_approved=approved, count_key=count["key"],
            ballots=count["ballots"], registered=count["registered"],
            reported_pct=None, denominator=None,
            disposition="mapped_valid_single_path_native_app_reference" if approved
            else "held_source_topology_not_repaired")
        decisions.append(decision)
        if not approved:
            continue
        coordinates, shape, coordinate_hash = decode_single_path_groups(shape_by_id[identity])
        if (coordinate_hash != hashes[identity]["exact_millidegree_coordinate_sha256"]
                or hashes[identity]["unclosed_source_rings"] != 0):
            raise ValueError("Independent coordinate hash disagreement")
        selected_shapes.append(shape)
        p = dict(key=count["key"], year=2026, state_code="AK", county="Alaska",
            county_fips=None, unit=count["precinct"], source_sequence=count["source_sequence"],
            native_precinct_id=identity, reporting_unit_kind="geographic_precinct",
            source_snapshot=SNAPSHOT, match_status="matched", ballots=record["b"],
            denominator=None, reported_pct=None, geometry_withheld_reason=None,
            count_scope="native_geographic_house_unit_excludes_pooled_modes",
            native_record=dict(number=identity, name=unit["name"], contest="U.S. Representative",
                b=record["b"], v=record["v"]),
            reference_geometry=dict(native_precinct_id=identity,
                source_selected_election_app=2026, certified_legal_boundaries=False,
                topology_valid_without_repairs=True, single_path_per_polygon=True,
                exact_millidegree_coordinate_sha256=coordinate_hash),
            quality_flags=count["quality_flags"], source_url=SOURCE, boundary_label=BOUNDARY,
            rate_withheld_reason=RATE_HOLD,
            source_update_label="Native updated: " + native["updated"] + "; timezone not supplied.",
            source_reporting_label="Unofficial native House geographic-unit b ballots. "
                "Separately pooled and federal-overseas ballots are not assigned to this shape.")
        features.append(dict(type="Feature", properties=p,
            geometry=dict(type="MultiPolygon", coordinates=coordinates)))
    if len(features) != 81:
        raise ValueError("Changed valid unrepaired native display subset")
    tree = STRtree(selected_shapes)
    for i, shape in enumerate(selected_shapes):
        for j in tree.query(shape):
            if j > i and shape.intersection(selected_shapes[j]).area > 0:
                raise ValueError("Native geographic units overlap; no clipping or allocation")
    return dict(summary=dict(source_units=523, geographic_units=402, pooled_units=120,
        federal_overseas_units=1, map_features=81, geometry_holds=321, rates_approved=0,
        source_ballots=total["b"], mapped_geographic_ballots=sum(f["properties"]["ballots"] for f in features),
        source_geometry_repaired=False, counts_allocated=False, certified_legal_boundaries=False,
        native_source_updated=native["updated"], timezone=None),
        complete_shape_queries=decisions, complete_count_queries=counts,
        geojson=dict(type="FeatureCollection", features=features))


def load(root=ROOT):
    inputs = json.loads((root / VERSION / "inputs.json").read_bytes())
    bodies = {}
    for name, receipt in inputs["files"].items():
        body = (root / name).read_bytes()
        if len(body) != receipt["bytes"] or digest(body) != receipt["sha256"]:
            raise ValueError("Changed sufficient Alaska input: " + name)
        bodies[name] = body
    def read(name):
        body = bodies[VERSION + "/" + name]
        return json.loads(gzip.decompress(body) if name.endswith(".gz") else body)
    receipts = read("original-source-receipts.json")
    if len(receipts) != 6:
        raise ValueError("Incomplete original Alaska source receipts")
    for name, receipt in receipts.items():
        raw = gzip.decompress(bodies[VERSION + "/originals/" + name + ".gz"])
        if len(raw) != receipt["bytes"] or digest(raw) != receipt["sha256"]:
            raise ValueError("Original source receipt disagreement: " + name)
    return review(read("originals/official-precinct-shapes.json.gz"),
        read("qualified-source-count-queries.json.gz"), read("originals/precincts-original.json.gz"),
        read("held-topology-queries.json"), read("independent-integer-coordinates.json"),
        read("native-display-format-facts.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(encoded(load(args.root)).decode(), end="")
