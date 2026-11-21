"""Reproduce dated Connecticut town display layers and their joins."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

import shapefile
from shapely import coverage_is_valid
from shapely.geometry import mapping, shape

BASE = "https://www2.census.gov/geo/tiger/"
SOURCES = {
    "2000-11-07": ("TIGER2008/09_CONNECTICUT/tl_2008_09_cousub00.zip", "00", "COSBIDFP00",
                   "b336cf1ce7a33ede104af093a0f1dba809a9b5994e8f9ee2674f17cb8983816f"),
    "2008-11-04": ("TIGER2008/09_CONNECTICUT/tl_2008_09_cousub.zip", "", "COSBIDFP",
                   "a02f093eedc3b4028a28f3c6d8da138f4379fc84cfee8661a7a082cfec55ae61"),
    "2024-11-05": ("TIGER2024/COUSUB/tl_2024_09_cousub.zip", "", "GEOID",
                   "5d1215b53c40afd93479611828673c4a51c2eb899674d3e1cf05fce9d52eda02"),
}


def build(inputs, output):
    with gzip.open(inputs / "participation-ct-general-town-turnout-archive.csv.gz",
                   "rt", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    output.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for date, (path, suffix, key, digest) in SOURCES.items():
        name = path.rsplit("/", 1)[-1]
        source = inputs / name
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError(f"{date}: source geometry differs")
        features, polygons = [], []
        with shapefile.Reader(str(source)) as layer:
            for entry in layer.iterShapeRecords():
                r = entry.record
                if r[f"STATEFP{suffix}"] != "09":
                    raise ValueError("Non-Connecticut geography in the town layer")
                if r[f"COUSUBFP{suffix}"] == "00000":
                    continue
                polygon = shape(entry.shape.__geo_interface__)
                if not polygon.is_valid or polygon.is_empty or polygon.geom_type not in {"Polygon", "MultiPolygon"}:
                    raise ValueError(f"{date}: invalid town geometry")
                polygons.append(polygon)
                features.append({"type": "Feature", "properties": {
                    "town": r[f"NAME{suffix}"], "id": r[key]},
                    "geometry": mapping(polygon)})
        towns = {f["properties"]["town"] for f in features}
        selected = [r for r in rows if r["election_date"] == date and r["geography_level"] != "state"]
        if (len(towns) != len(features) or len(towns) != 169 or not coverage_is_valid(polygons)
                or towns != {r["reporting_unit"] for r in selected}):
            raise ValueError(f"{date}: town geometry and publication roster do not agree")
        features.sort(key=lambda f: f["properties"]["id"])
        asset = f"town-CT-{date[:4]}.geojson.gz"
        data = {"type": "FeatureCollection", "election_date": date, "state_code": "CT", "features": features}
        body = gzip.compress(json.dumps(data, sort_keys=True, separators=(",", ":")).encode(), mtime=0)
        (output / asset).write_bytes(body)
        receipts[date] = {
            "path": asset, "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body), "source_url": BASE + path, "source_sha256": digest,
            "geometry_count": len(features),
            "qualified_whole_town_rates": sum(r["geography_level"] == "town" and bool(r["checked_as_voted_fraction"])
                                               for r in selected),
        }
    (output / "map-audit.json").write_text(json.dumps(receipts, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
