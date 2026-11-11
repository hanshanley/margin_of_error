"""Publishable county context compiled from frozen native ACS output."""

import gzip
import io
import json
from pathlib import Path
import re

from .contract import IntakeError, encoded, pin
from .acs_context import STATE_FIPS


def compressed(body):
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, filename="") as stream:
        stream.write(body)
    return buffer.getvalue()


def name_key(name):
    return re.sub(r"[^A-Z0-9]", "", re.sub(
        r"\b(COUNTY|PARISH|BOROUGH|CENSUS AREA)\b", "", name.upper()))


def compile_counties(native, identities, geometries):
    labels = {row["GEOID"]: row for row in identities if row["GEOID"][:2] in STATE_FIPS}
    if len(labels) != sum(row["GEOID"][:2] in STATE_FIPS for row in identities):
        raise IntakeError("context_geography", "Duplicate Census identity")
    keys = [row["geography"]["census_geoid"] for row in native["records"]]
    if len(set(keys)) != len(keys) or set(keys) != set(labels):
        raise IntakeError("context_geography", "Complete ACS and Gazetteer county identities differ")
    counties, references = {}, {}
    for code, collection in geometries.items():
        features = collection["features"]
        keys = [row["properties"]["key"] for row in features]
        expected = {key for key, row in labels.items() if row["USPS"] == code}
        if len(set(keys)) != len(keys) or set(keys) != expected:
            raise IntakeError("context_geography", "Loaded county reference identities differ: " + code)
        if any(row["properties"]["state_code"] != code or
                row["properties"]["boundary_year"] != 2024 for row in features):
            raise IntakeError("context_geography", "County context reference is not its declared vintage")
        references[code] = {row["properties"]["key"]: row["properties"] for row in features}
    if set(geometries) != {row["USPS"] for row in labels.values()}:
        raise IntakeError("context_geography", "A state is missing its approved county reference")
    for row in native["records"]:
        geoid = row["geography"]["census_geoid"]
        label = labels[geoid]
        code = label["USPS"]
        view = {key: value for key, value in row.items() if key != "native_tables"}
        aliases = references[code][geoid].get("aliases", [])
        view.update(name=label["NAME"], state_code=code, context_status="direct_native_county_ACS",
            name_keys=sorted({name_key(value) for value in [label["NAME"], *aliases]}),
            map_join=dict(status="approved_context_identity", reference_year=2024,
                feature_key=geoid, certified_election_boundary=False))
        counties.setdefault(code, []).append(view)
    common = dict(contract=native["contract"], source_period=native["source_period"],
        income_dollar_year=native["income_dollar_year"], resident_context_not_voter_data=True,
        historical_electorates_not_inferred=True)
    files, states = {}, {}
    for code, rows in sorted(counties.items()):
        filename = f"states/{code}.json.gz"
        body = compressed(encoded(dict(**common, state_code=code,
            counties=sorted(rows, key=lambda row: row["geography"]["census_geoid"]), precincts=[])))
        files[filename] = body
        states[code] = dict(file=filename, **pin(body), counties=len(rows), precincts=0,
            direct_counties=len(rows), modeled_precincts=0)
    files["index.json"] = encoded(dict(**common, states=states,
        complete_native_counties=len(labels), source_is_election_data=False,
        county_reference_vintage=2024, precinct_context_status="awaiting_qualified_weighted_crosswalk",
        limitations=native["limitations"]))
    return files


def build_county_files(native_path, identities_path, geometry_root):
    native = json.loads(gzip.decompress(Path(native_path).read_bytes()))
    identities = json.loads(gzip.decompress(Path(identities_path).read_bytes()))
    root = Path(geometry_root)
    pointer = json.loads((root / "latest.json").read_bytes())
    base = root / pointer["snapshot_id"]
    declarations = {row["path"]: row for row in pointer["files"]}
    geometries = {}
    for code in sorted({row["USPS"] for row in identities if row["GEOID"][:2] in STATE_FIPS}):
        name = f"geometry/county-{code}.geojson"
        body = (base / name).read_bytes()
        if pin(body) != {key: declarations[name][key] for key in ("bytes", "sha256")}:
            raise IntakeError("geometry_hash", "The held approved county reference differs")
        geometries[code] = json.loads(body)
    files = compile_counties(native, identities, geometries)
    return files, dict(native_query=pin(Path(native_path).read_bytes()),
        county_identity_original=pin(Path(identities_path).read_bytes()),
        approved_geometry={f"geometry/county-{code}.geojson":
            pin((base / f"geometry/county-{code}.geojson").read_bytes()) for code in geometries},
        original_reacquisitions=0, geometry_repreparations=0, count_reductions_repeated=0)


def add_precinct_context(files, contexts, references, crosswalks):
    files = dict(files)
    index = json.loads(files["index.json"])
    if set(contexts) != set(references) or set(contexts) != set(crosswalks):
        raise IntakeError("context_coverage", "Every modeled source needs its full reference and hold inventory")
    for code, context in sorted(contexts.items()):
        if code not in index["states"] or context["state_code"] != code or context["source_period"] != index["source_period"]:
            raise IntakeError("context_geography", "Conditional context belongs to another state or source period")
        declaration = index["states"][code]
        data = json.loads(gzip.decompress(files[declaration["file"]]))
        features = references[code]["features"]
        properties = {feature["properties"]["key"]: feature["properties"] for feature in features}
        keys = [row["geography"]["reference_key"] for row in context["records"]]
        held = crosswalks[code]["held_references"]
        held_keys = {row["key"] for row in held}
        if len(properties) != len(features) or len(set(keys)) != len(keys) or set(keys) & held_keys or set(
                keys) | held_keys != set(properties):
            raise IntakeError("context_geography", "Full conditional reference decisions differ")
        profiles = []
        for row in context["records"]:
            key = row["geography"]["reference_key"]
            props = properties[key]
            if row["geography"]["state_code"] != code or props["state_code"] != code or row.get(
                    "resident_composition_is_not_voter_composition") is not True:
                raise IntakeError("context_geography", "Unqualified conditional reference identity")
            view = {name: value for name, value in row.items()
                if name not in ("exact_weighted_source_cells", "source_block_groups")}
            view.update(name=props.get("unit") or props.get("precinct") or key,
                source_area=props.get("county"), state_code=code,
                source_block_group_count=len(row["source_block_groups"]))
            profiles.append(view)
        data.update(precincts=profiles, precinct_source=context["source_reference"],
            precinct_reference_holds=held, weight_year=context["weight_year"],
            conditional_context_limitations=context["limitations"])
        body = compressed(encoded(data))
        files[declaration["file"]] = body
        declaration.update(**pin(body), precincts=len(profiles), modeled_precincts=len(profiles),
            held_reference_features=len(held), reference_features=len(features),
            population_profiles=sum(row["resident_population"]["estimate"] is not None for row in profiles),
            income_profiles=sum(row["modeled_income_median_band"] is not None for row in profiles))
    index.update(precinct_context_status="conditional_local_reference_profiles",
        modeled_precincts=sum(value["precincts"] for value in index["states"].values()),
        precinct_reference_families=sum(value.get("reference_features", 0) > 0
            for value in index["states"].values()),
        resident_context_not_voter_data=True, income_medians_averaged=False)
    files["index.json"] = encoded(index)
    return files
