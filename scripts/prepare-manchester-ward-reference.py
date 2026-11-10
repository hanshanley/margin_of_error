"""Prepare the exact ward display file and append its source without replacing any earlier route."""

import gzip
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ward_reference", ROOT/"scripts/manchester-ward-reference.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def build():
    public = ROOT/core.PUBLIC
    if public.exists():
        raise ValueError("Refuse to replace an already prepared ward-reference version")
    data = core.load()
    inputs = json.loads((ROOT/core.VERSION/"inputs.json").read_bytes())
    geo = gzip.compress(core.encoded(data["geojson"]),mtime=0)
    metadata = dict(source_id=core.SNAPSHOT, boundary_label=core.BOUNDARY,
        reference_scope=inputs["reference_scope"], boundary_reference_year=2022,
        current_clerk_effective_date="2021-12-21", certified_legal_precinct_boundaries=False,
        expected_features=12, source_city="Manchester", native_source_ward_rows=37,
        mapped_source_ward_rows=12, held_table_only_ward_rows=25,
        complete_native_source_fields=242, source_city_observations=4,
        counts_only=True, rates_approved=False, native_federal_only_added=False,
        source_geometry_repaired=False, source_native_overlaps_preserved=True,
        native_overlap_pairs=6, native_vertices_verified=3789,
        mapped_raw_ward_total_sum=38562,
        complete_download_url=inputs["complete_download_url"], bytes=len(geo),sha256=core.digest(geo),
        area_column_label="City",ballot_column_label="Native ward Total Ballots Cast",
        notes="Manchester only: twelve raw ward totals on current official municipal ward context. "
            "The other25 native ward rows remain in tables. Ward7's85-ballot source disagreement is retained; "
            "federal-only76 is separate and never added. Six small native boundary overlaps "
            "(0.2868-16.6606 projected square metres) remain unrepaired. Not certified2026 legal precincts "
            "or a statewide native ward/precinct map; no analysis rates or population allocation.")
    index = dict(year=2026,boundary_date=core.BOUNDARY,states=dict(NH="NH.geojson.gz"),
                 state_metadata=dict(NH=metadata))
    pointer_path = ROOT/"public/participation-precincts.json"
    pointer = json.loads(pointer_path.read_bytes())
    entry = dict(base_url="/"+core.PUBLIC.removeprefix("public/")+"/")
    if entry in pointer["additional_sources"]:
        raise ValueError("Ward source is already registered; no repeated preparation")
    pointer["additional_sources"].append(entry)
    public.mkdir(parents=True)
    (public/"NH.geojson.gz").write_bytes(geo)
    (public/"index.json").write_bytes(core.encoded(index))
    pointer_path.write_bytes(core.encoded(pointer))
    print(json.dumps(dict(metadata=metadata,earlier_source_routes_preserved=True)))


if __name__ == "__main__":
    build()
