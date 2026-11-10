"""Prepare all37 native ward references while preserving every previous public route."""

import gzip
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dover", ROOT / "scripts/dover-ward-reference.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def build():
    public = ROOT / core.PUBLIC
    if public.exists():
        raise ValueError("An existing prepared reference cannot be overwritten")
    data = core.load()
    inputs = json.loads((ROOT / core.VERSION / "inputs.json").read_bytes())
    old_public = "public/participation-precincts/20261110-new-hampshire-ward-reference-03"
    prior = json.loads((ROOT / old_public / "index.json").read_bytes())["state_metadata"]["NH"]
    body = gzip.compress(core.encoded(data["geojson"]), mtime=0)
    metadata = dict(prior,
        source_id=core.SNAPSHOT, boundary_label=core.BOUNDARY, expected_features=37,
        mapped_cities=dict(Manchester=12, Concord=10, Nashua=9, Dover=6),
        boundary_reference_years=dict(prior["boundary_reference_years"], Dover=2022),
        mapped_source_ward_rows=37, held_table_only_ward_rows=0,
        native_vertices_verified=data["summary"]["native_vertices_verified"],
        raw_count_checks_by_city=data["summary"]["raw_count_checks_by_city"],
        complete_download_url=inputs["complete_download_url"], bytes=len(body), sha256=core.digest(body),
        Dover_source_item_id="3d1a8bdf3eaa49e09cf5d9da5b56bf9c", Dover_source_layer_id=11,
        Dover_native_pair_decisions=15, Dover_native_overlap_pairs=0,
        notes="Manchester12, Concord10, Nashua9 and Dover6: all37 held native ward reports now have direct references. "
            "Counts, source disagreements, separate federal-only fields and all prior31 shapes remain unchanged. "
            "Dover uses the independently state-published2022 NHGRANIT ward product, literal district labels, "
            "native3437 and declared inverseESRI108190; not old layer5, FID-as-ward or nativeFIPS-as-county. "
            "All1987 new vertices/cyclic edges and15 native pairs are checked, with no native Dover overlaps. "
            "Six Manchester and fourteen Concord overlaps remain unrepaired. "
            "Four cities only, not statewide/county totals or certified2026 legal precincts; no allocation or analysis rates.")
    pointer_path = ROOT / "public/participation-precincts.json"
    pointer = json.loads(pointer_path.read_bytes())
    old = dict(base_url="/" + old_public.removeprefix("public/") + "/")
    if pointer["additional_sources"].count(old) != 1:
        raise ValueError("Missing or repeated existing NH source")
    others = [row for row in pointer["additional_sources"] if row != old]
    pointer["additional_sources"][pointer["additional_sources"].index(old)] = dict(
        base_url="/" + core.PUBLIC.removeprefix("public/") + "/")
    if [row for row in pointer["additional_sources"]
            if row["base_url"] != "/" + core.PUBLIC.removeprefix("public/") + "/"] != others:
        raise ValueError("Non-NH registry entries changed")
    public.mkdir(parents=True)
    (public / "NH.geojson.gz").write_bytes(body)
    (public / "index.json").write_bytes(core.encoded(dict(year=2026, boundary_date=core.BOUNDARY,
        states=dict(NH="NH.geojson.gz"), state_metadata=dict(NH=metadata))))
    pointer_path.write_bytes(core.encoded(pointer))
    print(json.dumps(dict(status="PASS_prepared37_native_ward_references_NOT_live_acceptance",
        metadata=metadata, prior31_features_and_other_source_registry_entries_preserved=True)))


if __name__ == "__main__":
    build()
