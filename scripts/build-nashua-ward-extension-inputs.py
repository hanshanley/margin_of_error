"""Freeze the independently city-published adopted Nashua ward reference."""

import argparse
import hashlib
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/precinct-source-reviews/20261110-new-hampshire-ward-reference-03"
PRIOR = "data/precinct-source-reviews/20261110-new-hampshire-ward-reference-02"


def build(source):
    target = ROOT/VERSION
    if target.exists():
        raise ValueError("Refuse to replace an immutable Nashua ward input version")
    previous = json.loads((ROOT/PRIOR/"inputs.json").read_bytes())
    files = dict(previous["files"])
    target.mkdir(parents=True)

    def pin(body):
        return dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest())

    def save(name,body):
        path = target/name
        path.write_bytes(body)
        files[path.relative_to(ROOT).as_posix()] = pin(body)

    for name in ["inputs.json","queries.json.gz"]:
        path = PRIOR+"/"+name
        files[path] = pin((ROOT/path).read_bytes())
    names = ["adopted-ward-service-parent-original.json",
        "adopted-ward-service-parent-original.json.safe-receipt.json",
        "adopted-ward-layer7-original.json","adopted-ward-layer7.safe-receipt.json",
        "nashua-all9-adopted-native-ward-reference-review-01.json"]
    for name in ["native-count.json","native-ids.json","full-aggregate-original.geojson","native-projection-original.json"]:
        names.extend(["nashua-adopted2021-"+name,"nashua-adopted2021-"+name+".safe-receipt.json"])
    for name in names:
        if ".private." in name or name.endswith((".html",".js")):
            raise ValueError("Private app code cannot be copied")
        save(name,(source/name).read_bytes())
    parent = source.parent
    declaration = parent/"nashua-ward-declaration.private.html"
    text = BeautifulSoup(declaration.read_bytes(),"html.parser").get_text(" ",strip=True)
    if not re.search(r"December\s+28,\s+2021",text):
        raise ValueError("Missing native current clerk ward-date declaration")
    webmap = json.loads((source/"adopted2022-webmap.private.json").read_bytes())
    service = "https://services1.arcgis.com/WwJAqA4K2ienzdKW/arcgis/rest/services/Nashua_Wards_2022_WFL1/FeatureServer"
    ward = next(row for row in webmap["operationalLayers"] if row.get("url") == service+"/7")
    if ward["title"] != "Ward Boundary (Effective December 28, 2021)":
        raise ValueError("Proposed or unqualified ward source role")
    safe = dict(city="Nashua",current_clerk_source="https://nashuanh.gov/205/Where-Do-I-Vote",
        native_clerk_date="2021-12-28",private_clerk_html_sha256=pin(declaration.read_bytes())["sha256"],
        independent_city_declaring_page="https://www.nashuanh.gov/155/GIS",
        city_linked_public_org="WwJAqA4K2ienzdKW",
        adopted_public_app="d52ed8ae4a3240b798d6645548309feb",
        adopted_public_webmap="b3e0f610170a417996404eb0486d9e63",
        actual_declared_ward_layer=service+"/7",native_webmap_ward_label=ward["title"],
        adopted_source_date="2021-12-28",effective_source_date="2021-12-28",
        current_full_map_effective_literal="OCTOBER 2026",current_full_map_revised_literal="OCTOBER 2026",
        not_proposed_point6_block22_or_parcel8=True,
        old_query_backend_unavailable_not_an_access_denial=True,
        private_app_or_compiled_code_copied=False,private_keys_used=False,
        certified_legal2026_precinct_boundaries=False)
    save("nashua-independent-adopted-ward-safe-declaration.json",(json.dumps(safe,indent=2)+"\n").encode())
    inputs = dict(version=VERSION,files=files,previous_ward_query_path=PRIOR+"/queries.json.gz",
        source_count_election_date="2026-11-03",retained_city_source_fields=242,retained_native_ward_rows=37,
        mapped_cities=dict(Manchester=12,Concord=10,Nashua=9),held_table_only_ward_rows=6,
        source_counts_repaired=False,source_geometry_repaired=False,source_geometry_clipped=False,
        native_federal_only_added=False,analysis_denominator=None,analysis_rate=None,
        certified_legal_precinct_boundaries=False,
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-new-hampshire-native-ward-reference-20261110-03/complete-analysis.zip")
    (target/"inputs.json").write_text(json.dumps(inputs,indent=2)+"\n")
    print(json.dumps(dict(sufficient_input_files=len(files),mapped_native_wards=31,
        retained_city_source_fields=242,retained_native_ward_rows=37,held_table_only_ward_rows=6,
        previous_all124_inputs_preserved=True,no_private_app_code_or_personal_features_copied=True)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    build(parser.parse_args().source)
