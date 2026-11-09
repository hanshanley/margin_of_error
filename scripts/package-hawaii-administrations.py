"""Package every Hawaii reporting-area and Census-county decision with sufficient originals and offline code."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261109-hawaii-administrations-01"
REPRODUCE = """import { loadHawaiiAdministrations } from './scripts/hawaii-administrations.mjs';
process.stdout.write(JSON.stringify(loadHawaiiAdministrations(), null, 2) + '\\n');
"""
REPRODUCE_GEOMETRY = """import gzip,json
from pathlib import Path
from shapely.geometry import shape,mapping
from shapely.ops import unary_union
version=Path('data/county-source-reviews/20261109-hawaii-administrations-01')
inputs=json.loads((version/'inputs.json').read_bytes())
original=json.loads(gzip.decompress(Path(inputs['original_reference']['path']).read_bytes()))
features={r['properties']['key']:r for r in original['features']}
grid=json.loads((version/'native-administration-grid.json').read_bytes())
derived=[]
for row in grid:
    components=row['component_county_fips']
    combined=unary_union([shape(features[key]['geometry']) for key in components])
    assert combined.is_valid
    derived.append(dict(type='Feature',properties=dict(key=row['source_administration_id'],
        name=row['administration'],state_code='HI',boundary_year=2026,
        source_administration_id=row['source_administration_id'],component_county_fips=components,
        geography_scope='Derived election administration from full 2026 Census components; not precincts'),
        geometry=mapping(combined)))
print(json.dumps(dict(type='FeatureCollection',features=derived),indent=2))
"""


def build(output):
    if output.exists() or (ROOT / VERSION / "queries.json.gz").exists():
        raise ValueError("Refuse to replace an immutable Hawaii query package")
    raw = subprocess.check_output(["node", "--input-type=module", "-e", REPRODUCE], cwd=ROOT)
    queries = json.loads(raw)
    inputs = json.loads((ROOT / VERSION / "inputs.json").read_bytes())
    paths = set(inputs["files"]) | {VERSION + "/inputs.json",
        "scripts/hawaii-administrations.mjs", "scripts/hawaii-administrations.test.mjs",
        "scripts/build-hawaii-administration-inputs.py", "scripts/package-hawaii-administrations.py",
        "public/scripts/participation-geography.js"}
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    for name, receipt in inputs["files"].items():
        body = members[name]
        if len(body) != receipt["bytes"] or hashlib.sha256(body).hexdigest() != receipt["sha256"]:
            raise ValueError("Changed sufficient Hawaii numerical input")
    members["reproduce.mjs"] = REPRODUCE.encode()
    members["reproduce-geometry.py"] = REPRODUCE_GEOMETRY.encode()
    members["queries.json"] = raw
    table = io.StringIO()
    fields = ["year", "state_code", "source_administration_id", "county", "county_fips",
        "source_count", "component_county_fips", "denominator", "reported_pct",
        "participation_measure_label", "source_update_label", "source_url", "disposition",
        "cast_ballot_count_qualified", "unique_voter_count_qualified"]
    writer = csv.DictWriter(table, fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in [*queries["administrations"], *queries["Census_county_decisions"]]:
        writer.writerow(dict(row, component_county_fips=json.dumps(row.get("component_county_fips"),
            separators=(",", ":"))))
    members["complete-administration-and-county-queries.csv"] = table.getvalue().encode()
    members["README.txt"] = (
        "Hawaii2026: complete four native election-administration decisions plus five Census-county decisions\n"
        "Native TOTAL TURNOUT:Honolulu228487/Hawaii62453/Kauai24635/Maui(includingKalawao)50324.\n"
        "Native source counts, registrations, mail/in-person fields, printed sections and separateNov4\n"
        "REPORT3clocks survive. No timezone inferred. TOTAL TURNOUT is NOT certified cast ballots or unique people.\n"
        "Maui includesKalawao for elections; the official counting manual scope/page/URL is recorded.\n"
        "Four reporting-area shapes use full2026Census components. Maui15009+Kalawao15005 are grouped by\n"
        "unary_union, with no buffer,make_valid,clipping or count allocation. Administration IDs are NOTFIPS.\n"
        "All five original county polygons and membership are preserved. Three single-component Census\n"
        "counts are qualified; separate Maui/Kalawao counts stayNULL. Never paint50324 onto both counties.\n"
        "All analysis denominators/rates withheld. These are derived reporting areas, NOT certified precincts.\n"
        "The original state summary365897 and496unit total365903 survive. Four separate county snapshots\n"
        "sum365899 for diagnostics only, not a researcher statewide total or common-cutoff claim.\n"
        "Includes sufficient original PDFs/fullmedia/source-unit records/full original+derived geometry,\n"
        "all queries/holds/scope facts/code/tests/results. No metadata-only download, session headers,\n"
        "compiled publisher appcode, private contacts or nonnumerical publisher prose.\n"
        "Extract every member into an empty directory; Node22+ needs no network or installed packages:\n"
        "  node reproduce.mjs > reproduced-queries.json\n"
        "Compare byte-for-byte to queries.json. Then:\n"
        "  node --test scripts/hawaii-administrations.test.mjs\n"
        "Optional exact geometry regeneration uses Python3.9+ with already-installedShapely2.0.7:\n"
        "  python3 reproduce-geometry.py > reproduced-geometry.json\n"
        "Compare to decompressed public/participation-county-administrations/20261109-hawaii-01/HI.geojson.gz.\n"
        "All earlier immutable analyses, frozen readers and496native unit observations remain unchanged.\n"
    ).encode()
    manifest = dict(summary=queries["summary"], diagnostics=queries["diagnostics"], files={
        name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        for name, body in sorted(members.items())})
    members["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output.mkdir(parents=True)
    for name in ["queries.json", "complete-administration-and-county-queries.csv", "README.txt", "manifest.json"]:
        (output / name).write_bytes(members[name])
    archive = output / "complete-analysis.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as target:
        for name, body in sorted(members.items()):
            target.writestr(name, body)
    receipt = dict(url=inputs["complete_download_url"], bytes=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), members=len(members),
        native_administrations=4, Census_county_decisions=5, analysis_rates_approved=False)
    (ROOT / VERSION / "queries.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    (ROOT / VERSION / "summary.json").write_text(json.dumps(queries["summary"], indent=2) + "\n")
    (ROOT / VERSION / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)
