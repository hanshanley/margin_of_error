"""Population/housing proxy weights on unchanged approved reference footprints."""

from collections import Counter, defaultdict
from fractions import Fraction

from .contract import IntakeError


def population_weights(features, blocks, state_code, state_fips, chunk_size=20000,
                       point_query_writer=None, reference_holds=None):
    import numpy as np
    import shapely
    from shapely.geometry import shape
    from shapely.strtree import STRtree

    declared_holds = {} if reference_holds is None else reference_holds
    if not isinstance(declared_holds, dict) or any(
            not isinstance(key, str) or not key or not isinstance(reason, str) or not reason
            for key, reason in declared_holds.items()):
        raise IntakeError("crosswalk_scope", "Reference holds require explicit identities and reasons")
    identities, polygons, holds, seen = [], [], [], set()
    for feature in features:
        props = feature["properties"]
        key = props.get("key")
        if not isinstance(key, str) or not key or key in seen or props.get("state_code") != state_code:
            raise IntakeError("crosswalk_identity", "Reference identities are absent, duplicated or in another state")
        seen.add(key)
        if key in declared_holds:
            holds.append(dict(key=key, reason=declared_holds[key]))
            continue
        geometry = shape(feature["geometry"])
        if not geometry.is_valid or geometry.is_empty or geometry.geom_type not in ("Polygon", "MultiPolygon"):
            holds.append(dict(key=key, reason="invalid_or_nonpolygon_native_reference_not_repaired"))
            continue
        if props.get("maps_approved") is False:
            holds.append(dict(key=key, reason="source_reference_not_approved"))
            continue
        identities.append(key)
        polygons.append(geometry)
    if set(declared_holds) - seen:
        raise IntakeError("crosswalk_scope", "A declared hold is outside the complete reference inventory")
    if not polygons:
        raise IntakeError("crosswalk_geometry", "No approved unrepaired reference footprints")
    tree = STRtree(polygons)
    denominators, assigned = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0, 0])
    block_ids, point_counts = set(), Counter()
    totals = [0, 0]
    for offset in range(0, len(blocks), chunk_size):
        batch = blocks[offset:offset+chunk_size]
        for row in batch:
            key = row["GEOID"]
            if key in block_ids or len(key) != 15 or key[:2] != state_fips or row.get("STATE") != state_fips:
                raise IntakeError("crosswalk_identity", "Duplicate or invalid native block identity")
            block_ids.add(key)
            for value in (row["POP100"], row["HU100"]):
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    raise IntakeError("crosswalk_weight", "Unknown/invalid native proxy is not zero")
            if not -180 <= float(row["INTPTLON"]) <= 180 or not -90 <= float(row["INTPTLAT"]) <= 90:
                raise IntakeError("crosswalk_point", "Native internal point is outside geographic bounds")
            denominators[key[:12]][0] += row["POP100"]
            denominators[key[:12]][1] += row["HU100"]
            totals[0] += row["POP100"]
            totals[1] += row["HU100"]
        x = np.asarray([float(row["INTPTLON"]) for row in batch])
        y = np.asarray([float(row["INTPTLAT"]) for row in batch])
        pairs = tree.query(shapely.points(x, y), predicate="intersects")
        multiplicity = Counter(pairs[0].tolist())
        candidates = defaultdict(list)
        if point_query_writer is not None:
            for point_index, polygon_index in zip(*pairs):
                candidates[point_index].append(identities[polygon_index])
        for i, row in enumerate(batch):
            number = multiplicity[i]
            status = "unique_reference" if number == 1 else "ambiguous_reference" if number else "outside_loaded_reference"
            point_counts[status] += 1
            point_counts[status+"_population"] += row["POP100"]
            point_counts[status+"_housing"] += row["HU100"]
            if point_query_writer is not None:
                point_query_writer(dict(census_2020_block=row["GEOID"], status=status,
                    reference_keys=sorted(candidates[i])))
        for point_index, polygon_index in zip(*pairs):
            if multiplicity[point_index] != 1:
                continue
            row = batch[point_index]
            value = assigned[(identities[polygon_index], row["GEOID"][:12])]
            value[0] += row["POP100"]
            value[1] += row["HU100"]
            value[2] += 1
    links = []
    for (key, bg), (population, housing, count) in sorted(assigned.items()):
        total_population, total_housing = denominators[bg]
        links.append(dict(reference_key=key, census_2020_block_group=bg,
            assigned_population=population, assigned_housing_units=housing,
            assigned_blocks=count, block_group_population=total_population,
            block_group_housing_units=total_housing,
            population_fraction=str(Fraction(population, total_population)) if total_population else None,
            housing_proxy_fraction=str(Fraction(housing, total_housing)) if total_housing else None))
    return dict(contract="resident.population_proxy_crosswalk.v1", state_code=state_code,
        weight_year=2020, projection="EPSG:4326", native_coordinate_predicate=True,
        links=links, reference_keys=identities, held_references=holds,
        reference_features=len(features), qualified_reference_features=len(identities),
        source_blocks=len(blocks), complete_population=totals[0], complete_housing_units=totals[1],
        point_decisions=dict(point_counts), source_geometry_repaired=False,
        ambiguous_points_allocated=False, reference_points_are_not_whole_block_intersections=True,
        housing_units_are_not_occupied_households=True,
        ACS_2024_identity_and_variable_qualification_pending=True,
        limitations=[
            "2020 population internal points approximate population distribution within source footprints.",
            "Point membership uses unchanged native geographic-coordinate edges, without projected-chord replacement.",
            "A block can straddle later precinct boundaries; point assignment is a modeling assumption.",
            "Overlapping reference candidates remain unallocated; native shapes are not repaired.",
            "Housing units are an occupied-household weighting proxy, not observed occupied households.",
            "Reference geography is not certified election-time precinct geography.",
            "These weights do not estimate voter demographics, individual characteristics or group turnout."])
