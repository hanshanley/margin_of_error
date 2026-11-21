"""Reproduce the 2024 Hawaii election reporting areas from pinned county shapes."""

import gzip
import hashlib
import json
from pathlib import Path
import sys

from shapely.geometry import mapping, shape

SOURCE_SHA = "1b519be669ad7f217ca6d082449b4cae7f179499ee02ad80ab53d3db27e520ee"
COUNTIES = {"15001": "Hawaii", "15003": "Honolulu", "15005": "Kalawao", "15007": "Kauai", "15009": "Maui"}
AREAS = {"15001": "County of Hawaii", "15003": "City & County of Honolulu",
         "15007": "County of Kauai", "15009": "County of Maui"}


def build(source, output):
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError("Unexpected Hawaii 2024 geography")
    features = json.loads(gzip.decompress(raw))["features"]
    counties = {}
    for feature in features:
        p = feature["properties"]
        key = p["key"]
        if (key in counties or p != {"key": key, "name": COUNTIES.get(key), "state_code": "HI",
                                    "boundary_year": 2024, "level": "county"}):
            raise ValueError("Unexpected dated Hawaii county identity")
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Invalid Hawaii county geometry")
        counties[key] = geometry
    if counties.keys() != COUNTIES.keys():
        raise ValueError("Incomplete Hawaii county inventory")
    combined = counties["15009"].union(counties["15005"])
    if not combined.is_valid or combined.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError("Invalid combined Maui election reporting area")
    result = []
    for key, name in AREAS.items():
        members = ["15009", "15005"] if key == "15009" else [key]
        geometry = combined if key == "15009" else counties[key]
        result.append({"type": "Feature", "properties": {
            "key": key, "name": name, "state_code": "HI", "boundary_year": 2024, "level": "county",
            "source_counties": members}, "geometry": mapping(geometry)})
    body = json.dumps({"type": "FeatureCollection", "boundary_vintage": 2024, "source_sha256": SOURCE_SHA,
                       "features": result}, separators=(",", ":"), sort_keys=True).encode()
    with output.open("wb") as stream, gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as encoded:
        encoded.write(body)


if __name__ == "__main__":
    build(*map(Path, sys.argv[1:]))
