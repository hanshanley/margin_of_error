"""Prepare the new two-city ward file while retaining every older public route."""

import gzip
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ward_reference",ROOT/"scripts/new-hampshire-ward-reference.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def build():
    public = ROOT/core.PUBLIC
    if public.exists():
        raise ValueError("Refuse to replace an already prepared reference version")
    data = core.load()
    inputs = json.loads((ROOT/core.VERSION/"inputs.json").read_bytes())
    geo = gzip.compress(core.encoded(data["geojson"]),mtime=0)
    metadata = dict(source_id=core.SNAPSHOT,boundary_label=core.BOUNDARY,
        certified_legal_precinct_boundaries=False,expected_features=22,
        mapped_cities=dict(Manchester=12,Concord=10),
        boundary_reference_years=dict(Manchester=2022,Concord=None),
        current_clerk_dates=dict(Manchester="2021-12-21",Concord="2021-11-08"),
        native_source_ward_rows=37,mapped_source_ward_rows=22,held_table_only_ward_rows=15,
        complete_native_source_fields=242,source_city_observations=4,
        counts_only=True,rates_approved=False,native_federal_only_added=False,
        source_geometry_repaired=False,source_native_overlaps_preserved=True,
        native_overlap_pairs=20,native_vertices_verified=7936,
        raw_count_checks_by_city=dict(Manchester=38562,Concord=19234),
        complete_download_url=inputs["complete_download_url"],bytes=len(geo),sha256=core.digest(geo),
        area_column_label="City",ballot_column_label="Native ward source count",
        notes="Manchester12 and Concord10 native wards only. Other15 New Hampshire ward rows remain in tables. "
            "Source measures remain literal and separate; no statewide parent or rate is inferred. "
            "Manchester Ward7's85-ballot disagreement and separate federal-only76 remain unchanged. "
            "Six Manchester and fourteen Concord native boundary-overlap pairs remain unrepaired. "
            "Concord uses its declared inverse Esri108190 datum operation, not a null-offset approximation. "
            "Current municipal context, not newly certified2026 legal precincts; no clipping or population allocation.")
    index = dict(year=2026,boundary_date=core.BOUNDARY,states=dict(NH="NH.geojson.gz"),
                 state_metadata=dict(NH=metadata))
    pointer_path = ROOT/"public/participation-precincts.json"
    pointer = json.loads(pointer_path.read_bytes())
    old = dict(base_url="/participation-precincts/20261110-manchester-ward-reference-01/")
    if pointer["additional_sources"].count(old) != 1:
        raise ValueError("Missing or repeated existing NH source; no duplicate state registration")
    previous_sources = pointer["additional_sources"][:]
    pointer["additional_sources"][pointer["additional_sources"].index(old)] = dict(
        base_url="/"+core.PUBLIC.removeprefix("public/")+"/")
    if [row for row in previous_sources if row != old] != pointer["additional_sources"][:3]:
        raise ValueError("Earlier non-NH source pointers changed")
    public.mkdir(parents=True)
    (public/"NH.geojson.gz").write_bytes(geo)
    (public/"index.json").write_bytes(core.encoded(index))
    pointer_path.write_bytes(core.encoded(pointer))
    print(json.dumps(dict(metadata=metadata,earlier_public_source_files_and_non_NH_pointers_preserved=True)))


if __name__ == "__main__":
    build()
