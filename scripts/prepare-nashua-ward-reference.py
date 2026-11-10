"""Prepare the three-city ward reference without removing any prior public route."""

import gzip
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ward_reference",ROOT/"scripts/nashua-ward-reference.py")
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
        certified_legal_precinct_boundaries=False,expected_features=31,
        mapped_cities=dict(Manchester=12,Concord=10,Nashua=9),
        boundary_reference_years=dict(Manchester=2022,Concord=None,Nashua=None),
        current_clerk_dates=dict(Manchester="2021-12-21",Concord="2021-11-08",Nashua="2021-12-28"),
        native_source_ward_rows=37,mapped_source_ward_rows=31,held_table_only_ward_rows=6,
        complete_native_source_fields=242,source_city_observations=4,
        counts_only=True,rates_approved=False,native_federal_only_added=False,
        source_geometry_repaired=False,source_native_overlaps_preserved=True,
        native_overlap_pairs=20,native_vertices_verified=16192,
        raw_count_checks_by_city=dict(Manchester=38562,Concord=19234,Nashua=33849),
        complete_download_url=inputs["complete_download_url"],bytes=len(geo),sha256=core.digest(geo),
        area_column_label="City",ballot_column_label="Native ward source count",
        notes="Manchester12, Concord10 and Nashua9 native wards only; other6 Dover ward rows remain in tables. "
            "All source values and literal measures remain separate; no statewide parent or rate is inferred. "
            "Manchester Ward7's85-ballot disagreement/federal-only76 and Nashua Ward3/4/8 source disagreements "
            "+1/-2/-1/federal-only92 stay unchanged; federal-only counts are never added. "
            "Six Manchester and fourteen Concord native overlap pairs remain unrepaired; Nashua has no native pair overlaps. "
            "The public Nashua layer is adopted/effective December28,2021, not proposed wards, polling points, "
            "census blocks or parcels. Its current full map prints October2026; source clocks are distinct. "
            "Municipal reference context, not newly certified2026 legal precincts; no clipping or population allocation.")
    index = dict(year=2026,boundary_date=core.BOUNDARY,states=dict(NH="NH.geojson.gz"),
                 state_metadata=dict(NH=metadata))
    pointer_path = ROOT/"public/participation-precincts.json"
    pointer = json.loads(pointer_path.read_bytes())
    old = dict(base_url="/participation-precincts/20261110-new-hampshire-ward-reference-02/")
    if pointer["additional_sources"].count(old) != 1:
        raise ValueError("Missing or repeated existing NH source")
    before = pointer["additional_sources"][:]
    pointer["additional_sources"][pointer["additional_sources"].index(old)] = dict(
        base_url="/"+core.PUBLIC.removeprefix("public/")+"/")
    if [row for row in before if row != old] != pointer["additional_sources"][:3]:
        raise ValueError("Earlier non-NH pointers changed")
    public.mkdir(parents=True)
    (public/"NH.geojson.gz").write_bytes(geo)
    (public/"index.json").write_bytes(core.encoded(index))
    pointer_path.write_bytes(core.encoded(pointer))
    print(json.dumps(dict(metadata=metadata,earlier_public_source_files_and_non_NH_pointers_preserved=True)))


if __name__ == "__main__":
    build()
