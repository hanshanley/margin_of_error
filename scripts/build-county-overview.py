"""Build a lightweight national display from reviewed 2026 county shapes."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from shapely.geometry import mapping, shape


def build(source, output):
    index = json.loads((source / "index.json").read_bytes())
    checksums = json.loads((source / "checksums.json").read_bytes())
    features, seen = [], set()
    for code, coverage in sorted(index["coverage"].items()):
        raw = (source / coverage["file"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != checksums[coverage["file"]]["sha256"]:
            raise ValueError("Changed reviewed county geometry")
        for feature in json.loads(gzip.decompress(raw))["features"]:
            properties = feature["properties"]
            key = properties["key"]
            if (key in seen or properties["state_code"] != code
                    or properties["boundary_year"] != index["year"]):
                raise ValueError("Duplicate or wrong-year county identity")
            seen.add(key)
            original = shape(feature["geometry"])
            geometry = original.simplify(.015, preserve_topology=True)
            if geometry.is_empty or not geometry.is_valid:
                geometry = original
            if geometry.is_empty or not geometry.is_valid:
                raise ValueError("Invalid county overview geometry")
            features.append({
                "type": "Feature",
                "properties": {key: properties[key] for key in ("key", "name", "state_code", "boundary_year")},
                "geometry": mapping(geometry),
            })
    if len(features) != index["mapped_counties"]:
        raise ValueError("County overview omits reviewed counties")
    data = dict(type="FeatureCollection", year=index["year"],
                geometry_scope="Display-simplified 2026 Census county reference; full shapes remain in the complete download.",
                features=features)
    raw = json.dumps(data, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(gzip.compress(raw, mtime=0))
    print(json.dumps(dict(counties=len(features), states=len(index["coverage"]),
                          bytes=output.stat().st_size,
                          sha256=hashlib.sha256(output.read_bytes()).hexdigest())))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
