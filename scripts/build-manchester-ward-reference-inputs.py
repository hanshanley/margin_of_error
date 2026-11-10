"""Freeze complete held count inputs and only permitted aggregate ward-reference originals."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/precinct-source-reviews/20261110-manchester-ward-reference-01"
PRIOR = "data/county-source-reviews/20261110-new-hampshire-cities-02"


def build(source):
    target = ROOT / VERSION
    if target.exists():
        raise ValueError("Refuse to replace an immutable ward-reference input version")
    prior = json.loads((ROOT / PRIOR / "inputs.json").read_bytes())
    files = dict(prior["files"])
    target.mkdir(parents=True)

    def receipt(body):
        return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())

    for name in ["inputs.json", "queries.json.gz"]:
        path = PRIOR + "/" + name
        files[path] = receipt((ROOT / path).read_bytes())
    sources = [
        "manchester-wards2022-full-aggregate-original.geojson",
        "manchester-wards2022-native-projection-original.json",
        "manchester-wards2022-native-count.json",
        "manchester-wards2022-native-ids.json",
        "manchester-official-actual-ward-layer.json",
        "manchester-official-mapserver-layers.json",
        "manchester-declared-wards-wms-capabilities.xml",
        "manchester-declared-citywide-ward-map-original.pdf",
        "manchester-current-ward-lines-safe-declaration.json",
        "manchester-native-projection-overlap-check-01.json",
        "manchester-all-native-vertices-reference-check-01.json",
        "manchester-all12-native-ward-count-join-review-01.json",
        "manchester-wards2022-independent-geography-review-01.json",
    ]
    for name in sources:
        body = (source / name).read_bytes()
        path = target / name
        shutil.copyfile(source / name, path)
        files[path.relative_to(ROOT).as_posix()] = receipt(body)
        acquired = source / (name + ".receipt.json")
        if acquired.exists():
            native = json.loads(acquired.read_bytes())
            if native["status"] != 200 or receipt(body) != {key:native[key] for key in ["bytes","sha256"]}:
                raise ValueError("Changed native aggregate ward original")
            path = target / acquired.name
            shutil.copyfile(acquired, path)
            files[path.relative_to(ROOT).as_posix()] = receipt(acquired.read_bytes())
    inputs = dict(version=VERSION, files=files,
        complete_count_query_path=PRIOR + "/queries.json.gz",
        source_count_election_date="2026-11-03", reference_layer_name="SDEweb.GISADMIN.Wards_2022",
        reference_boundary_vintage=2022, current_clerk_effective_date="2021-12-21",
        source_geometry_repaired=False, source_geometry_clipped=False,
        source_native_overlaps_preserved=True, certified_legal_precinct_boundaries=False,
        source_count_field="Total Ballots Cast", native_federal_only_added=False,
        count_denominator=None, analysis_rate=None, retained_source_city_profiles=4,
        retained_source_ward_rows=37, mapped_city="Manchester", mapped_wards=12,
        reference_scope="current_official_municipal_ward_display_reference_not_certified_2026_precincts",
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-manchester-native-ward-reference-20261110-01/complete-analysis.zip")
    (target / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    print(json.dumps(dict(sufficient_input_files=len(files), retained_native_city_sources=4,
        retained_native_ward_rows=37, native_reference_wards=12,
        old_count_originals_unchanged=True, private_publisher_configuration_copied=False,
        personal_official_or_parcel_fields_copied=False)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    build(parser.parse_args().source)
