"""Independently verify complete reference scopes, native points and resident cells."""

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import gzip
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from shapely.geometry import Point, shape
from shapely.strtree import STRtree


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--results", type=Path, required=True)
parser.add_argument("--site-root", type=Path)
parser.add_argument("--blocks-root", type=Path, required=True)
parser.add_argument("--database", type=Path, required=True)
parser.add_argument("--references-root", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
assert args.site_root or args.references_root
assert not args.output.exists()
registry = json.loads((args.results / "summary.json").read_bytes())["reference_registry"]
tables = {"B19001": 17, "B03002": 21, "B15003": 25, "B01001": 49}
connection = sqlite3.connect("file:" + str(args.database.resolve()) + "?mode=ro", uri=True)
checks, summaries = 0, {}


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def checked_body(path, declaration):
    body = path.read_bytes()
    assert len(body) == declaration["bytes"]
    assert hashlib.sha256(body).hexdigest() == declaration["sha256"]
    return body


def check(actual, value):
    global checks
    assert actual is None if value is None else actual is not None and math.isclose(
        actual, float(value), rel_tol=1e-12, abs_tol=1e-10), (actual, value)
    checks += 1


def percent(value, total):
    return 100 * value / total if value is not None and total is not None and total > 0 else None


for code, declaration in sorted(registry["states"].items()):
    crosswalk = load(args.results / (code + "-population-weights.json.gz"))
    result = load(args.results / (code + "-modeled-resident-context.json.gz"))
    reference = args.references_root / (code + ".geojson.gz") if args.references_root else args.site_root / declaration["file"]
    features = json.loads(gzip.decompress(checked_body(reference, declaration)))["features"]
    declared_holds = declaration.get("reference_holds", {})
    audit_pin = declaration["approval_evidence"].get("source_scope_audit")
    if audit_pin:
        audit_path = args.references_root / (code + "-source-scope-audit.json") if args.references_root else args.site_root / audit_pin["file"]
        audit = json.loads(checked_body(audit_path, audit_pin))
        clipped = {row["key"] for row in audit["masked_reporting_units"]}
        repaired = {row["object_id"] for row in audit["topology_repairs"]}
        assert clipped == {f["properties"]["key"] for f in features
            if f["properties"].get("geometry_scope") == "Reference geometry with overlapping strips withheld"}
        expected_holds = {}
        for feature in features:
            p, reasons = feature["properties"], []
            if p["key"] in clipped:
                reasons.append("display_excludes_part_of_whole_source_unit")
            if set(p["source_object_ids"]) & repaired:
                reasons.append("previous_source_topology_repair_not_newly_approved_for_resident_context")
            if reasons:
                expected_holds[p["key"]] = ";".join(reasons)
        assert declared_holds == expected_holds
    else:
        assert not declared_holds
    polygons, keys, held = [], [], set()
    for feature in features:
        props = feature["properties"]
        if props["key"] in declared_holds:
            held.add(props["key"])
            continue
        geometry = shape(feature["geometry"])
        if geometry.is_valid and not geometry.is_empty and geometry.geom_type in ("Polygon", "MultiPolygon") and props.get("maps_approved") is not False:
            polygons.append(geometry)
            keys.append(props["key"])
        else:
            held.add(props["key"])
    assert held == {row["key"] for row in crosswalk["held_references"]}
    held_reasons = {row["key"]: row["reason"] for row in crosswalk["held_references"]}
    assert all(held_reasons[key] == reason for key, reason in declared_holds.items())
    assert set(keys) == set(crosswalk["reference_keys"])
    assert len(features) == crosswalk["reference_features"] == len(keys) + len(held)
    tree = STRtree(polygons)
    blocks = json.loads((args.blocks_root / declaration["state_fips"] / "complete-query.json").read_bytes())["records"]
    source = {row["GEOID"]: row for row in blocks}
    assert len(source) == len(blocks) == crosswalk["source_blocks"]
    denominators = defaultdict(lambda: [0, 0])
    assigned = defaultdict(lambda: [0, 0, 0])
    decisions, seen = Counter(), set()
    for row in blocks:
        denominators[row["GEOID"][:12]][0] += row["POP100"]
        denominators[row["GEOID"][:12]][1] += row["HU100"]
    point_path = args.results / crosswalk["complete_point_query"]["file"]
    checked_body(point_path, crosswalk["complete_point_query"])
    with gzip.open(point_path, "rt") as stream:
        for line in stream:
            decision = json.loads(line)
            identity = decision["census_2020_block"]
            assert identity not in seen and identity in source
            seen.add(identity)
            row = source[identity]
            point = Point(float(row["INTPTLON"]), float(row["INTPTLAT"]))
            candidates = sorted(keys[i] for i in tree.query(point) if polygons[i].covers(point))
            assert candidates == decision["reference_keys"], (code, identity, candidates, decision)
            status = "unique_reference" if len(candidates) == 1 else "ambiguous_reference" if candidates else "outside_loaded_reference"
            assert decision["status"] == status
            decisions[status] += 1
            decisions[status + "_population"] += row["POP100"]
            decisions[status + "_housing"] += row["HU100"]
            if len(candidates) == 1:
                total = assigned[(candidates[0], identity[:12])]
                total[0] += row["POP100"]
                total[1] += row["HU100"]
                total[2] += 1
            checks += 3
    assert seen == set(source) and dict(decisions) == crosswalk["point_decisions"]
    actual_links = {(link["reference_key"], link["census_2020_block_group"]): link for link in crosswalk["links"]}
    assert set(actual_links) == set(assigned)
    weights = defaultdict(list)
    for (key, bg), (population, housing, count) in assigned.items():
        actual = actual_links[(key, bg)]
        assert [actual["assigned_population"], actual["assigned_housing_units"], actual["assigned_blocks"]] == [population, housing, count]
        assert [actual["block_group_population"], actual["block_group_housing_units"]] == denominators[bg]
        fractions = [Fraction(value, total) if total else None for value, total in zip((population, housing), denominators[bg])]
        for field, fraction in zip(("population_fraction", "housing_proxy_fraction"), fractions):
            assert actual[field] == (str(fraction) if fraction is not None else None)
            checks += 1
        weights[key].append((bg, *fractions))
    native = defaultdict(dict)
    for geoid, table, literals in connection.execute(
        "SELECT geoid,table_id,native_pairs FROM cells WHERE geoid LIKE ?", (declaration["state_fips"] + "%",)):
        native[geoid][table] = [int(pair[0]) if pair[0].isdigit() else None for pair in json.loads(literals)]
    rows = {row["geography"]["reference_key"]: row for row in result["records"]}
    assert len(rows) == len(result["records"]) and set(rows) == set(keys)
    for key, row in rows.items():
        missing = {bg for bg, _, _ in weights[key] if set(native[bg]) != set(tables) | {"B19013"}}
        assert set(row["missing_2024_block_groups"]) == missing
        cells = {}
        for table, count in tables.items():
            usable = [(bg, housing if table == "B19001" else population)
                for bg, population, housing in weights[key]
                if (housing if table == "B19001" else population) not in (None, Fraction(0))]
            cells[table] = []
            for i in range(count):
                parts = [] if missing else [(native[bg][table][i], fraction) for bg, fraction in usable]
                value = sum((number * fraction for number, fraction in parts), Fraction(0)) if parts and all(
                    number is not None for number, _ in parts) else None
                assert row["exact_weighted_source_cells"][table][f"{i+1:03d}"] == (str(value) if value is not None else None)
                cells[table].append(value)
                checks += 1
        population = cells["B03002"][0]
        check(row["resident_population"]["estimate"], population)
        for group, i in zip(row["race_ethnicity"]["groups"], [2, 3, 4, 5, 6, 7, 8, 11]):
            check(group["estimate"], cells["B03002"][i])
            check(group["percent"], percent(cells["B03002"][i], population))
            assert group["margin_of_error"] is None and group["percentage_moe"] is None
        age = cells["B01001"]
        for group, indices in zip(row["age"]["groups"], [
            [*range(2, 6), *range(26, 30)], [*range(6, 19), *range(30, 43)], [*range(19, 25), *range(43, 49)],
        ]):
            value = sum(age[i] for i in indices) if all(age[i] is not None for i in indices) else None
            check(group["estimate"], value)
            check(group["percent"], percent(value, age[0]))
            assert group["derived_moe"] is None
        education = cells["B15003"]
        bachelors = sum(education[21:]) if all(v is not None for v in education[21:]) else None
        check(row["education"]["bachelors_or_higher"], bachelors)
        check(row["education"]["bachelors_or_higher_pct"], percent(bachelors, education[0]))
        income, band = cells["B19001"], row["modeled_income_median_band"]
        for i, value in enumerate(income[1:], 2):
            check(row["household_income_distribution"]["bins"][f"{i:03d}"]["estimate"], value)
        if any(value is None for value in income[1:]) or sum(income[1:]) <= 0:
            assert band is None
        else:
            bounds = [0, 10000, 15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000, 60000,
                75000, 100000, 125000, 150000, 200000, None]
            cumulative = [sum(income[1:i+2]) for i in range(16)]
            half = sum(income[1:]) / 2
            assert band["lower_bound"] == bounds[next(i for i, value in enumerate(cumulative) if value >= half)]
            assert band["upper_bound"] == bounds[next(i for i, value in enumerate(cumulative) if value > half) + 1]
        assert row["median_household_income"]["estimate"] is None and row["income_medians_averaged"] is False
        assert row["voter_participation_rate"] is None and row["resident_composition_is_not_voter_composition"]
        assert row["source_geometry_repaired"] is False and row["conflicts"] == []
    summaries[code] = dict(records=len(rows), held_reference_features=len(held), complete_point_decisions=len(seen),
        population_estimates=sum(row["resident_population"]["estimate"] is not None for row in rows.values()),
        income_bands=sum(row["modeled_income_median_band"] is not None for row in rows.values()),
        declared_scope_holds=len(declared_holds), point_decisions=dict(decisions))
    print(json.dumps(dict(state=code, status="PASS_independent_native_point_membership_and_exact_weighted_cells",
        **summaries[code])), flush=True)
connection.close()
proof = dict(status="PASS_all_native_points_full_reference_decisions_and_exact_resident_arithmetic",
    checks=checks, states=summaries, reference_families=len(summaries),
    records=sum(value["records"] for value in summaries.values()),
    point_decisions=sum(value["complete_point_decisions"] for value in summaries.values()),
    source_geometry_repaired=False, certified_election_boundaries=False,
    source_block_group_code_equivalence_is_assumption=True,
    published_or_live=False, whole_project_complete=False)
args.output.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps({key: value for key, value in proof.items() if key != "states"}))
