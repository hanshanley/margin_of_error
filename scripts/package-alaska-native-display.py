"""Package all selected/held Alaska queries, sufficient originals and independent code."""

import argparse
import csv
import gzip
import importlib.util
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("alaska_display", ROOT / "scripts/alaska-native-display.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
REPRODUCE = """import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('display', Path(__file__).parent / 'scripts/alaska-native-display.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
print(core.encoded(core.load()).decode(), end='')
"""


def csv_bytes(rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    out = io.StringIO()
    writer = csv.DictWriter(out, fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, separators=(",", ":")) if isinstance(v, (dict, list)) else v
                         for k, v in row.items()})
    return out.getvalue().encode()


def build(output=None):
    version, public = ROOT / core.VERSION, ROOT / core.PUBLIC
    if (output is not None and output.exists()) or (version / "queries.json.gz").exists():
        raise ValueError("Refuse to replace an immutable Alaska supplement")
    data = core.load()
    geo = gzip.compress(core.encoded(data["geojson"]), mtime=0)
    metadata = dict(source_id=core.SNAPSHOT, boundary_label=core.BOUNDARY,
        notes="81 of 402 native geographic units; 321 source-topology holds. "
            "All 523 count records remain downloadable, including 120 pooled district and one "
            "federal-overseas unit. Geographic House b ballots omit those pooled modes; "
            "no allocation, geometry repair, legal-boundary certification or turnout rate.",
        complete_download_url=core.DOWNLOAD, sha256=core.digest(geo), bytes=len(geo),
        expected_features=81, native_source_rows=523, native_geographic_rows=402,
        geometry_holds=321, counts_only=True, rates_approved=False,
        area_column_label="Source area", ballot_column_label="Native geographic-unit ballots")
    index = dict(year=2026, boundary_date=core.BOUNDARY, states=dict(AK="AK.geojson.gz"),
        state_metadata=dict(AK=metadata))
    expected = {"AK.geojson.gz": geo, "index.json": core.encoded(index)}
    if public.exists():
        if {p.name for p in public.iterdir()} != set(expected) or any(
                (public / name).read_bytes() != body for name, body in expected.items()):
            raise ValueError("Changed prepared Alaska reference")
    else:
        public.mkdir(parents=True)
        for name, body in expected.items():
            (public / name).write_bytes(body)
    if output is None:
        print(json.dumps(data["summary"]))
        return
    inputs = json.loads((version / "inputs.json").read_bytes())
    paths = set(inputs["files"]) | {core.VERSION + "/inputs.json",
        "scripts/alaska-native-display.py", "scripts/test-alaska-native-display.py",
        "scripts/alaska-native-display.test.mjs", "scripts/build-alaska-native-display-inputs.py",
        "scripts/package-alaska-native-display.py", "scripts/review-alaska-precinct-results.py",
        "scripts/check-alaska-native-display-browser.py",
        "public/scripts/participation-geography.js", "public/scripts/provider-county-scopes.js"}
    members = {name: (ROOT / name).read_bytes() for name in sorted(paths)}
    members[core.PUBLIC + "/AK.geojson.gz"] = geo
    members[core.PUBLIC + "/index.json"] = core.encoded(index)
    members["reproduce.py"] = REPRODUCE.encode()
    members["queries.json"] = core.encoded(data)
    tables = {
        "all402-native-shape-decisions.csv": data["complete_shape_queries"],
        "all523-source-count-queries.csv": data["complete_count_queries"],
        "all81-mapped-geographic-counts.csv": [f["properties"] for f in data["geojson"]["features"]],
    }
    for name, rows in tables.items():
        members[name] = csv_bytes(rows)
    members["README.txt"] = """ALASKA: PARTIAL NATIVE GEOGRAPHIC BALLOT-COUNT DISPLAY

Complete contents
All 402 native shape decisions, all 523 previously qualified source count
queries, all 81 mapped native geographic counts and exact unrepaired geometry.
All six complete official originals are retained: statewide/precinct JSON,
20,046-row all-contest CSV, source summary PDF, district and precinct shapes.
The prior count audit, safe source receipts, complete 402-row topology and
independent coordinate-hash reviews, factual format contract, our independent
implementation, focused tests and results are included. Publisher compiled
app code, HTML, API credentials and acquisition session headers are excluded.

Measure and geographic hierarchy
These are literal native House geographic-unit "b" ballot counts, not candidate
selections. All 523 source records sum to 215,906 native ballots; 402 geographic
units remain distinct from 120 pooled district units and one federal-overseas
unit. Only 81 geographic units/38,672 ballots have approved display shapes.
Pooled absentee/early/question and overseas ballots are never assigned to
residential precincts. Native registrations, source zeros and accounting flags
remain literal; ALL analysis denominators and turnout rates remain null.
Source count clock: 11/04/2026 2:11 PM, timezone unspecified, unofficial.
This is neither full-election precinct turnout nor demographic participation.

Reference, not certified legal boundaries
The official 26GENR app publishes this 402-ID reference alongside the native
2026 election counts. Its format contract defines each outer coords group as
one polygon and each string as a longitude/latitude delta path, reset from zero.
Our independent exact-millidegree decoder agrees with the separate coordinate
hash reader. All 81 approved features have ONE closed path per polygon, valid
unrepaired positive-area geometry and no interior overlaps with one another.
There is no inference of hole roles: the 321 other native shapes retain their
source topology holds. No clipping, simplification, repair, alternate locator
geometry or certified 2026 legal-boundary claim. Source possession and matching
IDs alone do not qualify the held shapes.

Reproduce offline (Python 3.9+, Shapely 2.x; Node 22+ for browser guards)
With existing Shapely available, extract ALL members to an empty directory:
  python3 reproduce.py > reproduced-queries.json
Compare byte-for-byte with queries.json, then run:
  python3 scripts/test-alaska-native-display.py
  node --test scripts/alaska-native-display.test.mjs

The original qualified 523-row count query is a sufficient pinned input for
this new display join; candidate CSV reduction is not repeated by reproduce.py.
The original full count-review implementation is also included. manifest.json
hashes every other member. Empty CSV fields correspond to JSON null values;
native originals preserve their literal cells. Older releases are unchanged.
""".encode()
    members["manifest.json"] = (json.dumps(dict(summary=data["summary"], files={
        name: dict(bytes=len(body), sha256=core.digest(body))
        for name, body in sorted(members.items())}), indent=2) + "\n").encode()
    output.mkdir(parents=True)
    for name in ["queries.json", *tables, "README.txt", "manifest.json"]:
        (output / name).write_bytes(members[name])
    (output / "AK.geojson.gz").write_bytes(geo)
    with zipfile.ZipFile(output / "complete-analysis.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(members.items()):
            archive.writestr(name, body)
    body = (output / "complete-analysis.zip").read_bytes()
    receipt = dict(url=core.DOWNLOAD, bytes=len(body), sha256=core.digest(body), members=len(members),
        complete_shape_queries=402, complete_count_queries=523, map_features=81, geometry_holds=321)
    (version / "queries.json.gz").write_bytes(gzip.compress(core.encoded(data), mtime=0))
    (version / "summary.json").write_text(json.dumps(data["summary"], indent=2) + "\n")
    (version / "download.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--prepare-reference", action="store_true")
    build(parser.parse_args().output)
