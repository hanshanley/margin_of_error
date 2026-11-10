"""Package all permitted originals, previous queries, 22 ward joins and every hold."""

import argparse
import csv
import gzip
import importlib.util
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ward_reference",ROOT/"scripts/new-hampshire-ward-reference.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
REPRODUCE = """import importlib.util
from pathlib import Path
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ward_reference',root/'scripts/new-hampshire-ward-reference.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
print(core.encoded(core.load(root)).decode(),end='')
"""
REPRODUCE_PREVIOUS = REPRODUCE.replace("new-hampshire-ward-reference.py","manchester-ward-reference.py")


def csv_bytes(rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    out = io.StringIO()
    writer = csv.DictWriter(out,fields,lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key:json.dumps(value,separators=(",",":")) if isinstance(value,(list,dict))
                         else value for key,value in row.items()})
    return out.getvalue().encode()


def build(output):
    version = ROOT/core.VERSION
    if output.exists() or (version/"queries.json.gz").exists():
        raise ValueError("Refuse to replace an immutable ward-extension package")
    data = core.load()
    raw = core.encoded(data)
    inputs = json.loads((version/"inputs.json").read_bytes())
    if gzip.compress(core.encoded(data["geojson"]),mtime=0) != (ROOT/core.PUBLIC/"NH.geojson.gz").read_bytes():
        raise ValueError("Prepared public geometry differs from complete queries")
    paths = set(inputs["files"]) | {core.VERSION+"/inputs.json",
        "scripts/new-hampshire-ward-reference.py","scripts/test-new-hampshire-ward-reference.py",
        "scripts/build-new-hampshire-ward-extension-inputs.py","scripts/prepare-new-hampshire-ward-reference.py",
        "scripts/package-new-hampshire-ward-reference.py","scripts/new-hampshire-ward-reference.test.mjs",
        "scripts/manchester-ward-reference.py","scripts/test-manchester-ward-reference.py",
        "scripts/manchester-ward-reference.test.mjs",
        "scripts/new-hampshire-city-counts.mjs","scripts/new-hampshire-city-counts.test.mjs",
        "scripts/new-hampshire-city-extension.mjs","scripts/new-hampshire-city-extension.test.mjs",
        "scripts/check-new-hampshire-city-counts-browser.py",
        "public/scripts/participation-geography.js","public/scripts/provider-county-scopes.js",
        "public/participation-precincts.json",core.PUBLIC+"/NH.geojson.gz",core.PUBLIC+"/index.json",
        "public/participation-precincts/20261110-manchester-ward-reference-01/NH.geojson.gz",
        "public/participation-precincts/20261110-manchester-ward-reference-01/index.json"}
    members = {name:(ROOT/name).read_bytes() for name in sorted(paths)}
    for name,pin in inputs["files"].items():
        if len(members[name]) != pin["bytes"] or core.digest(members[name]) != pin["sha256"]:
            raise ValueError("Changed sufficient original or earlier frozen numerical input")
    members["reproduce.py"] = REPRODUCE.encode()
    members["reproduce-previous.py"] = REPRODUCE_PREVIOUS.encode()
    members["reproduce-base.mjs"] = b"import {loadNewHampshireCityExtension} from './scripts/new-hampshire-city-extension.mjs';\nprocess.stdout.write(JSON.stringify(loadNewHampshireCityExtension(),null,2)+'\\n');\n"
    members["requirements.txt"] = b"shapely==2.0.7\npyproj==3.6.1\n"
    members["queries.json"] = raw
    tables = {
        "all242-retained-native-source-field-queries.csv":data["retained_city_source_queries"],
        "all37-native-ward-reference-dispositions.csv":data["complete_ward_disposition_queries"],
        "all22-native-ward-reference-decisions.csv":data["complete_reference_queries"],
        "all45-Concord-native-and-geographic-pair-decisions.csv":data["complete_concord_pairwise_queries"],
        "all6-retained-Manchester-native-overlap-queries.csv":data["retained_manchester_overlap_queries"],
        "all22-mapped-native-ward-counts.csv":[f["properties"] for f in data["geojson"]["features"]],
        "all15-table-only-native-ward-holds.csv":[r for r in data["complete_ward_disposition_queries"] if r["city"] not in ["Manchester","Concord"]],
    }
    for name,rows in tables.items():
        members[name] = csv_bytes(rows)
    members["README.txt"] = """NEW HAMPSHIRE: NATIVE WARD COUNTS IN TWO CITIES

COMPLETE CONTENTS
All17 complete official PDFs /219pages /117,853,795 native PDF bytes, all124
sufficient pins, every earlier242 city-source field and37 ward row, original
Manchester and Concord geographic/native geometry, native counts/IDs, safe
city declarations, exact datum-operation metadata, every22 reference decision,
all45 Concord pair decisions, retained6 Manchester overlaps, every15 held
ward disposition, complete numerical results, code/tests and offline reproduction.
Private app configuration, compiled publisher code, acquisition session headers,
personal/officeholder/parcel/population feature attributes are excluded.
This is not a metadata-only package.

COUNT MEANING
Manchester12 source ward totals remain exactly as previously published:
38,562 is a DERIVED sum, not a separately printed city parent. Ward7 prints
2712 despite2694 Election Day+103absentee=2797. Preserve the85 disagreement;
separate federal-only76 is NEVER added.
Concord10 ward Total Cast values sum to the separately printed city19234.
Wards1/2 retain native school-district components and separately printed ward
subtotals; other ward values stay literal. Opening/ED/closing registers and
printed percentages remain source diagnostics, NOT analysis rates.
No city/state values or population estimates are allocated to wards.
Every earlier Nashua/Dover source value remains. Their15 wards are TABLE-ONLY.

REFERENCE MEANING
Current official municipal DISPLAY REFERENCES, not newly certified2026 legal
precincts. Manchester uses Wards_2022/current lines effective2021-12-21.
Concord's city declaration approves the current viewer's10 voting wards on
2021-11-08; its service NAME PubWebGIS2020 is NOT an inferred boundary vintage.
Native REST Ward layer53 is separate from all parcel/population layers.
All7936 vertices are independently checked. Concord native EPSG3437 uses
US survey feet. Server-declared datum operation is inverseESRI108190.
The installed library's default null-offset operation is wrong for this
source; the declared inverse operation reproduces it within1e-9degrees.
That is coordinate reproduction agreement, NOT a ground-accuracy guarantee.
No grid/network download, geometry repair, clipping, smoothing or implicit
ring-role inference occurs.
All22 original single-ring shapes are valid without repair. Six Manchester
and14 Concord NATIVE overlap pairs remain unchanged. Concord native overlap
areas are projected USsurveyfeet squared, NOT square metres or geodesic ground
areas. Different coordinate/source frames are never pooled as one area measure.
No rates, deduplicated people, legal-boundary certification or statewide ward
completeness is inferred.

HOLDS
Nashua's declared query backend returned a native server-unavailable error,
not usable features; full current map PDF prints effective/revisedOCTOBER2026,
not a year inferred from its2022 service name. Dover's held city-linked app
uses an opaque named map; its parcel-ward lookup is not ward geometry. The
separately city-linked public portal ward search has zero items. No keys,
private named-map data, parcel allocation or unsupported boundaries are used.

REPRODUCE
Python3.9-3.12 with the pinned requirements, Node22+ for the preserved city
calculation. Extract every member into an empty directory.
  node reproduce-base.mjs > reproduced-base.json
Compare with the decompressed preserved city query input.
  python reproduce-previous.py > reproduced-previous.json
Compare with the decompressed preserved Manchester ward-query input.
  python reproduce.py > reproduced-queries.json
Compare byte-for-byte with queries.json.
  python scripts/test-new-hampshire-ward-reference.py
  python scripts/test-manchester-ward-reference.py
  node --test scripts/new-hampshire-city-counts.test.mjs scripts/new-hampshire-city-extension.test.mjs scripts/manchester-ward-reference.test.mjs scripts/new-hampshire-ward-reference.test.mjs
manifest.json hashes every other member. Previous immutable full packages and
public routes are preserved, not replaced by this version.
""".encode()
    members["manifest.json"] = (json.dumps(dict(summary=data["summary"],files={
        name:dict(bytes=len(body),sha256=core.digest(body)) for name,body in sorted(members.items())}),
        indent=2)+"\n").encode()
    output.mkdir(parents=True)
    for name in ["queries.json",*tables,"requirements.txt","README.txt","manifest.json"]:
        (output/name).write_bytes(members[name])
    with zipfile.ZipFile(output/"complete-analysis.zip","x",compression=zipfile.ZIP_DEFLATED) as archive:
        for name,body in sorted(members.items()):
            archive.writestr(name,body)
    body = (output/"complete-analysis.zip").read_bytes()
    receipt = dict(url=inputs["complete_download_url"],bytes=len(body),sha256=core.digest(body),
        members=len(members),original_pdfs=17,original_pages=219,original_pdf_bytes=117853795,
        mapped_cities=dict(Manchester=12,Concord=10),retained_city_source_fields=242,
        retained_native_ward_rows=37,complete_reference_decisions=22,
        complete_concord_pair_decisions=45,table_only_ward_holds=15,
        source_repairs=False,geometry_repairs=False,native_federal_only_added=False,analysis_rates_approved=False)
    (version/"queries.json.gz").write_bytes(gzip.compress(raw,mtime=0))
    (version/"summary.json").write_text(json.dumps(data["summary"],indent=2)+"\n")
    (version/"download.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    build(parser.parse_args().output)
