"""Package all permitted sources and four exact generations of native ward queries."""

import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ward_reference",ROOT/"scripts/nashua-ward-reference.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
old_spec = importlib.util.spec_from_file_location("previous_package",ROOT/"scripts/package-new-hampshire-ward-reference.py")
old_package = importlib.util.module_from_spec(old_spec)
old_spec.loader.exec_module(old_package)
REPRODUCE = """import importlib.util
from pathlib import Path
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ward_reference',root/'scripts/nashua-ward-reference.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
print(core.encoded(core.load(root)).decode(),end='')
"""


def build(output):
    version = ROOT/core.VERSION
    if output.exists() or (version/"queries.json.gz").exists():
        raise ValueError("Refuse to replace an immutable Nashua ward-reference package")
    data = core.load()
    raw = core.encoded(data)
    inputs = json.loads((version/"inputs.json").read_bytes())
    if gzip.compress(core.encoded(data["geojson"]),mtime=0) != (ROOT/core.PUBLIC/"NH.geojson.gz").read_bytes():
        raise ValueError("Prepared public geometry differs from complete queries")
    paths = set(inputs["files"]) | {core.VERSION+"/inputs.json",
        "scripts/nashua-ward-reference.py","scripts/test-nashua-ward-reference.py",
        "scripts/build-nashua-ward-extension-inputs.py","scripts/prepare-nashua-ward-reference.py",
        "scripts/package-nashua-ward-reference.py","scripts/nashua-ward-reference.test.mjs",
        "scripts/new-hampshire-ward-reference.py","scripts/test-new-hampshire-ward-reference.py",
        "scripts/new-hampshire-ward-reference.test.mjs","scripts/package-new-hampshire-ward-reference.py",
        "scripts/manchester-ward-reference.py","scripts/test-manchester-ward-reference.py",
        "scripts/manchester-ward-reference.test.mjs",
        "scripts/new-hampshire-city-counts.mjs","scripts/new-hampshire-city-counts.test.mjs",
        "scripts/new-hampshire-city-extension.mjs","scripts/new-hampshire-city-extension.test.mjs",
        "scripts/check-new-hampshire-city-counts-browser.py",
        "public/scripts/participation-geography.js","public/scripts/provider-county-scopes.js",
        "public/participation-precincts.json",core.PUBLIC+"/NH.geojson.gz",core.PUBLIC+"/index.json"}
    for previous in ["20261110-manchester-ward-reference-01","20261110-new-hampshire-ward-reference-02"]:
        paths.update({"public/participation-precincts/"+previous+"/"+name for name in ["NH.geojson.gz","index.json"]})
    members = {name:(ROOT/name).read_bytes() for name in sorted(paths)}
    for name,pin in inputs["files"].items():
        if len(members[name]) != pin["bytes"] or core.digest(members[name]) != pin["sha256"]:
            raise ValueError("Changed sufficient original or earlier frozen query input")
    members["reproduce.py"] = REPRODUCE.encode()
    members["reproduce-v02.py"] = REPRODUCE.replace("nashua-ward-reference.py","new-hampshire-ward-reference.py").encode()
    members["reproduce-manchester.py"] = REPRODUCE.replace("nashua-ward-reference.py","manchester-ward-reference.py").encode()
    members["reproduce-base.mjs"] = b"import {loadNewHampshireCityExtension} from './scripts/new-hampshire-city-extension.mjs';\nprocess.stdout.write(JSON.stringify(loadNewHampshireCityExtension(),null,2)+'\\n');\n"
    members["requirements.txt"] = b"shapely==2.0.7\npyproj==3.6.1\n"
    members["queries.json"] = raw
    tables = {
        "all242-retained-native-source-field-queries.csv":data["retained_city_source_queries"],
        "all37-native-ward-reference-dispositions.csv":data["complete_ward_disposition_queries"],
        "all31-native-ward-reference-decisions.csv":data["complete_reference_queries"],
        "all31-mapped-native-ward-counts.csv":[f["properties"] for f in data["geojson"]["features"]],
        "all36-Nashua-native-and-geographic-pair-decisions.csv":data["complete_nashua_pairwise_queries"],
        "all45-retained-Concord-pair-decisions.csv":data["complete_concord_pairwise_queries"],
        "all6-retained-Manchester-native-overlap-queries.csv":data["retained_manchester_overlap_queries"],
        "all6-Dover-table-only-native-ward-holds.csv":[r for r in data["complete_ward_disposition_queries"] if r["city"]=="Dover"],
    }
    for name,rows in tables.items():
        members[name] = old_package.csv_bytes(rows)
    members["README.txt"] = """NEW HAMPSHIRE: NATIVE WARD COUNTS IN THREE CITIES

COMPLETE CONTENTS
All17 complete official PDFs /219pages /117,853,795 native PDF bytes, all140
sufficient pins, every earlier242 city-source field/37 ward row/22 mapped
feature, all31 reference decisions,36 Nashua pair decisions, retained45 Concord
pair decisions/six Manchester overlaps, every6 Dover held ward, original
geographic/native geometry, native IDs/counts, safe declarations, exact code/
tests/results and four generations of offline reproduction. No metadata-only
download. Private app configs/compiled publisher code/session headers/keys and
personal/officeholder/population/address/point/parcel feature data are excluded.

NASHUA SOURCE MEANING
Nine literal native ward Total Ballots Cast fields sum to33,849: DERIVED, not
a separately printed city parent. Component sum33,847 is NOT substituted.
Ward3/4/8 component-minus-printed disagreements+1/-2/-1 remain. Ward8's red
amendments selectElectionDay3349/Total3575 whileabsentee225 stays unchanged;
cancelled3264/3489 are not reused. Federal-only92 is separate and NEVER added.
All earlier Manchester/Concord/Dover values remain byte-exact in frozen input
queries. No ballot definition, deduplicated person, state/county allocation,
analysis denominator/rate or new/first-ever eligibility is inferred.

REFERENCE MEANING
Only city-published ADOPTED municipal display context, not newly certified
2026 legal precincts. The independent city-linked NashuaMaps public portal's
adopted2022 app/webmap declares FeatureServerlayer7 WardBoundary(Adopted
December28,2021), with a separate effectiveDecember28,2021 webmap label.
This is NOT proposed wards/pollingpoint6/censusblock22/parcel8. Only native
OBJECTID,Ward,Wardtxt and full geometry were requested. GIS OBJECTIDs are
not ward numbers. All8256 new vertices independently match native3857 to the
unmodified geographic output; all9 closed single-ring polygons are valid.
No native Nashua pair overlap occurs in the complete36 pair decisions.
The current full official city map separately prints effective/revised
OCTOBER2026. Native count clocks, adoption date and map date are not spliced.
The old unavailable NewGIS backend remains an honest failed-product record;
this is an independently declared public product, not an access-denial bypass.

EARLIER REFERENCES AND HOLDS
All22 earlier features are unchanged: Manchester GIS2022/currentlines2021-12-21;
Concord cityapproval2021-11-08, nativeEPSG3437/inverseESRI108190, not a vintage
inferred from serviceName2020 or a default null-offset projection. Six native
Manchester overlap pairs (projectedm²) and14 Concord pairs (projectedUSsurveyft²)
remain unrepaired and are not pooled as a common area measure or geodesic area.
Dover's6 native ward rows remain TABLE-ONLY: no private named-map data or keys,
parcel allocation or unsupported geometry is used.
Every count is a whole source reporting unit, never an area/population allocation.
No repair, clipping, smoothing or implicit ring-role inference is applied.

REPRODUCE
Python3.9-3.12 with pinned requirements, Node22+ for the preserved city source.
Extract every member into an empty directory.
  node reproduce-base.mjs > reproduced-base.json
Compare with the decompressed preserved city query input.
  python reproduce-manchester.py > reproduced-manchester.json
Compare with the decompressed preserved12-ward query input.
  python reproduce-v02.py > reproduced-v02.json
Compare with the decompressed preserved22-ward query input.
  python reproduce.py > reproduced-queries.json
Compare byte-for-byte with queries.json.
  python scripts/test-nashua-ward-reference.py
  python scripts/test-new-hampshire-ward-reference.py
  python scripts/test-manchester-ward-reference.py
  node --test scripts/new-hampshire-city-counts.test.mjs scripts/new-hampshire-city-extension.test.mjs scripts/manchester-ward-reference.test.mjs scripts/new-hampshire-ward-reference.test.mjs scripts/nashua-ward-reference.test.mjs
manifest.json hashes every other member. Previous immutable full releases and
public paths remain unchanged.
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
        mapped_cities=dict(Manchester=12,Concord=10,Nashua=9),retained_city_source_fields=242,
        retained_native_ward_rows=37,complete_reference_decisions=31,
        complete_nashua_pair_decisions=36,table_only_ward_holds=6,
        source_repairs=False,geometry_repairs=False,native_federal_only_added=False,analysis_rates_approved=False)
    (version/"queries.json.gz").write_bytes(gzip.compress(raw,mtime=0))
    (version/"summary.json").write_text(json.dumps(data["summary"],indent=2)+"\n")
    (version/"download.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    build(parser.parse_args().output)
