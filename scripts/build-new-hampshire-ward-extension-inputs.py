"""Freeze the qualified Concord extension and honest held-geometry decisions."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/precinct-source-reviews/20261110-new-hampshire-ward-reference-02"
PRIOR = "data/precinct-source-reviews/20261110-manchester-ward-reference-01"


def build(source):
    target = ROOT/VERSION
    if target.exists():
        raise ValueError("Refuse to replace an immutable ward-extension input version")
    prior = json.loads((ROOT/PRIOR/"inputs.json").read_bytes())
    files = dict(prior["files"])
    target.mkdir(parents=True)

    def pin(body):
        return dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest())

    def save(name,body):
        path = target/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(body)
        files[path.relative_to(ROOT).as_posix()] = pin(body)

    for name in ["inputs.json","queries.json.gz"]:
        path = PRIOR+"/"+name
        files[path] = pin((ROOT/path).read_bytes())
    names = [
        "concord-declared-parent-service-original.json","concord-declared-parent-service.safe-receipt.json",
        "concord-actual-ward-layer-original.json","concord-actual-ward-layer.safe-receipt.json",
        "concord-native-datum-transformations-original.json",
        "concord-esri108190-independent-projection-operation.json",
        "concord-all10-native-ward-reference-review-01.json",
        "nashua-declared-parent-service-original.json","nashua-declared-parent-service.safe-receipt.json",
        "nashua-actual-ward-layer-original.json","nashua-actual-ward-layer.safe-receipt.json",
        "nashua-current-declared-citywide-ward-map-original.pdf",
        "nashua-current-declared-citywide-ward-map.safe-receipt.json",
        "dover-public-ward-portal.safe-receipt.json",
    ]
    for name in names:
        if ".private." in name or name.endswith((".html",".js")):
            raise ValueError("Private app code is not a sufficient public input")
        save(name,(source/name).read_bytes())
    for city,names in [
        ("concord",["native-count.json","native-ids.json","full-aggregate-original.geojson","native-projection-original.json"]),
        ("nashua",["native-count.json","native-ids.json"]),
    ]:
        for name in names:
            for suffix in ["",".safe-receipt.json"]:
                path = city+"-"+name+suffix
                save(path,(source/"native-ward-originals"/path).read_bytes())
    save("nashua-full-aggregate-original.geojson.safe-receipt.json",
         (source/"native-ward-originals/nashua-full-aggregate-original.geojson.safe-receipt.json").read_bytes())
    text = BeautifulSoup((source/"concord-ward-declaration.private.html").read_bytes(),"html.parser").get_text(" ",strip=True)
    if "approved by City Council on November 8, 2021" not in text:
        raise ValueError("Missing actual city ward approval declaration")
    safe_declaration = dict(city="Concord",
        source_url="https://www.concordnh.gov/897/Interactive-GIS-Viewer",
        original_private_html_sha256=pin((source/"concord-ward-declaration.private.html").read_bytes())["sha256"],
        current_city_viewer_approval_date="2021-11-08",declared_voting_wards=10,
        actual_declared_viewer="https://gis.concordnh.gov/arcgis/publicwebgis/",
        source_geometry_year_not_inferred_from_service_name=True,
        complete_public_original_geometry_supplied=True,
        certified_legal2026_precinct_boundaries=False,
        private_publisher_configuration_or_compiled_app_code_copied=False)
    save("concord-current-ward-safe-declaration.json",(json.dumps(safe_declaration,indent=2)+"\n").encode())
    error = json.loads((source/"native-ward-originals/nashua-native-count.json").read_bytes())
    if error != dict(status="error",messages=["Could not access any server machines. Please contact your system administrator."]):
        raise ValueError("Changed source-specific Nashua backend failure")
    held = dict(nashua=dict(native_ward_rows=9,disposition="held_no_qualified_reference",
        reason="Declared ArcGIS query backend unavailable; metadata is not geometry. Complete current map PDF is a separate reference, not a feature join.",
        native_map_effective_literal="OCTOBER 2026",native_map_revised_literal="OCTOBER 2026",
        source_geometry_year_not_inferred_from_2022_service_name=True),
        dover=dict(native_ward_rows=6,disposition="held_no_qualified_reference",
        reason="Held city-linked MapGeo uses an opaque named map; parcel-ward lookup is not ward geometry. Independently city-linked public portal ward search has zero items.",
        no_private_keys_or_compiled_app_code_used=True,no_parcel_geometry_allocated=True))
    save("remaining15-native-ward-geometry-holds.json",(json.dumps(held,indent=2)+"\n").encode())
    inputs = dict(version=VERSION,files=files,previous_ward_query_path=PRIOR+"/queries.json.gz",
        source_count_election_date="2026-11-03",retained_city_source_fields=242,retained_native_ward_rows=37,
        mapped_cities=dict(Manchester=12,Concord=10),held_table_only_ward_rows=15,
        source_counts_repaired=False,source_geometry_repaired=False,source_geometry_clipped=False,
        native_federal_only_added=False,analysis_denominator=None,analysis_rate=None,
        certified_legal_precinct_boundaries=False,
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-new-hampshire-native-ward-reference-20261110-02/complete-analysis.zip")
    (target/"inputs.json").write_text(json.dumps(inputs,indent=2)+"\n")
    print(json.dumps(dict(sufficient_input_files=len(files),mapped_native_wards=22,
        retained_city_source_fields=242,retained_native_ward_rows=37,held_table_only_ward_rows=15,
        all_prior_inputs_preserved=True,no_private_app_code_or_personal_features_copied=True)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    build(parser.parse_args().source)
