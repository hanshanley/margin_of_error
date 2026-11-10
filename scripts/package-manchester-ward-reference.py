"""Package every sufficient original, retained city query and native ward-reference decision."""

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ward_reference",ROOT/"scripts/manchester-ward-reference.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
REPRODUCE = """import importlib.util,json
from pathlib import Path
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ward_reference',root/'scripts/manchester-ward-reference.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
print(core.encoded(core.load(root)).decode(),end='')
"""
REPRODUCE_BASE = """import {loadNewHampshireCityExtension} from './scripts/new-hampshire-city-extension.mjs';
process.stdout.write(JSON.stringify(loadNewHampshireCityExtension(),null,2)+'\\n');
"""


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
        raise ValueError("Refuse to replace an immutable ward-reference package")
    data = core.load()
    raw = core.encoded(data)
    inputs = json.loads((version/"inputs.json").read_bytes())
    base = json.loads(gzip.decompress((ROOT/inputs["complete_count_query_path"]).read_bytes()))
    geo = gzip.compress(core.encoded(data["geojson"]),mtime=0)
    if (ROOT/core.PUBLIC/"NH.geojson.gz").read_bytes() != geo:
        raise ValueError("Prepared ward reference differs from complete native queries")
    paths = set(inputs["files"]) | {core.VERSION+"/inputs.json",
        "scripts/manchester-ward-reference.py","scripts/test-manchester-ward-reference.py",
        "scripts/build-manchester-ward-reference-inputs.py","scripts/prepare-manchester-ward-reference.py",
        "scripts/package-manchester-ward-reference.py","scripts/manchester-ward-reference.test.mjs",
        "scripts/check-new-hampshire-city-counts-browser.py",
        "scripts/new-hampshire-city-counts.mjs","scripts/new-hampshire-city-counts.test.mjs",
        "scripts/new-hampshire-city-extension.mjs","scripts/new-hampshire-city-extension.test.mjs",
        "public/scripts/participation-geography.js","public/scripts/provider-county-scopes.js",
        "public/participation-precincts.json",
        core.PUBLIC+"/NH.geojson.gz",core.PUBLIC+"/index.json"}
    members = {name:(ROOT/name).read_bytes() for name in sorted(paths)}
    for name,pin in inputs["files"].items():
        body = members[name]
        if len(body) != pin["bytes"] or core.digest(body) != pin["sha256"]:
            raise ValueError("Changed sufficient original or exact native-source query")
    members["reproduce.py"] = REPRODUCE.encode()
    members["reproduce-base.mjs"] = REPRODUCE_BASE.encode()
    members["requirements.txt"] = b"shapely==2.0.7\n"
    members["queries.json"] = raw
    tables = {
        "all242-retained-native-source-field-queries.csv":data["retained_city_source_queries"],
        "all37-native-ward-reference-dispositions.csv":data["complete_ward_disposition_queries"],
        "all12-native-ward-reference-decisions.csv":data["complete_reference_queries"],
        "all6-native-boundary-overlap-queries.csv":data["native_overlap_queries"],
        "all12-mapped-native-ward-counts.csv":[f["properties"] for f in data["geojson"]["features"]],
        "all4-retained-native-city-source-counts.csv":base["municipalities"],
    }
    for name,rows in tables.items():
        members[name] = csv_bytes(rows)
    members["README.txt"] = """MANCHESTER: NATIVE2026 WARD COUNTS ON CURRENT MUNICIPAL WARD CONTEXT

COMPLETE CONTENTS
All16 complete official PDFs /218 pages /115,942,591 native PDF bytes:
every15 prior city original plus the city-declared complete citywide ward map.
All93 sufficient source/evidence pins, original native projected and geographic
ward geometry, independent native count/IDs, WMS/REST layer declarations,
current clerk declaration facts, all prior242 city-source fields/37 ward rows,
every12 reference decision and six native-overlap decisions, code/tests/results.
Private publisher configurations, compiled app code, acquisition headers,
personal officeholder fields, parcel records and old population proxies are
excluded. This is not a metadata-only package.

COUNT MEANING
All12 literal Manchester ward Total Ballots Cast fields join by city+native
WardNumber and Ward label, not GIS OBJECTID25..36. Their raw sum38,562 is
DERIVED, not a separately printed city parent. Ward7 prints2712 versus
Election Day2694+absentee103=2797. Preserve the85-ballot source conflict.
Federal-only76 is separate and NEVER added. Counts are not repaired or
allocated from city/state values. Every earlier city/ward value remains.
Other25 source wards are TABLE-ONLY; no unqualified geography is inferred.

REFERENCE MEANING
The current official city map declares Wards_2022. Native WMS layer0 is
Wards, but the same service's actual REST Ward polygon layer is3: REST0
is Historic Sites POINTS and was never used as ward geometry. Current clerk
declaration and complete native citywide map identify ward lines effective/
ordainedDecember21,2021; map preparedDecember22,2021. These are current
municipal ward DISPLAY REFERENCE shapes, not newly certified2026 legal
precinct boundaries or a statewide map.

All12 original single-ring polygons are valid without repair. Every3,789
native projected vertex independently matches server geographic output.
Six small NATIVE boundary overlaps remain untouched:0.2868-16.6606 EPSG3857
projected square metres, at most2.65335e-6 of the smaller source ward area.
These are not geodesic ground areas. No clipping, smoothing or implicit
closure/ring-role repair occurs. Source counts are reporting-unit totals;
no person/location or demographic/population allocation is inferred.
All analysis denominators/rates are null. Native source clocks and absences
remain; count election date2026 differs from reference vintage/effective date.

REPRODUCE
Python3.9+ with Shapely2.0.7, and Node22+ for the preserved city calculation.
Extract every member into an empty directory.
  node reproduce-base.mjs > reproduced-base.json
Compare to the decompressed preserved city queries input.
  python reproduce.py > reproduced-queries.json
Compare byte-for-byte to queries.json. Focused source tests:
  python scripts/test-manchester-ward-reference.py
  node --test scripts/new-hampshire-city-counts.test.mjs scripts/new-hampshire-city-extension.test.mjs
  node --test scripts/manchester-ward-reference.test.mjs

manifest.json hashes every other member. The reader verifies all original/
evidence bytes, complete native ID inventory, direct ward counts, geometry,
projection agreement and the recorded overlap decisions. Earlier immutable
full city packages and complete routes remain unchanged.
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
        members=len(members),original_pdfs=16,original_pages=218,original_pdf_bytes=115942591,
        native_ward_count_joins=12,retained_city_source_fields=242,retained_ward_rows=37,
        complete_reference_queries=12,native_overlap_queries=6,source_repairs=False,
        source_geometry_repaired=False,native_federal_only_added=False,analysis_rates_approved=False)
    (version/"queries.json.gz").write_bytes(gzip.compress(raw,mtime=0))
    (version/"summary.json").write_text(json.dumps(data["summary"],indent=2)+"\n")
    (version/"download.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    build(parser.parse_args().output)
