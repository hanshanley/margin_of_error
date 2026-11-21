"""Reproduce the dated Massachusetts county reference from the retained TIGER ZIP."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import runpy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.original.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if (args.original.name != "tl_2026_us_county.zip"
            or digest != "b527c9ba7aeb8f17ef118f026eae5e5a938aa1d00b873bc32342d0dce59321c0"):
        raise ValueError("Massachusetts county reference source pin differs")
    key_names = {f"25{code:03d}": name for code, name in zip(range(1, 28, 2), (
        "Barnstable", "Berkshire", "Bristol", "Dukes", "Essex", "Franklin", "Hampden", "Hampshire",
        "Middlesex", "Nantucket", "Norfolk", "Plymouth", "Suffolk", "Worcester"), strict=True)}
    namespace = runpy.run_path(str(Path(__file__).with_name("review-house-county-results.py")))
    collection, excluded = namespace["county_geometries"](
        args.original.parent, [{"geography": key, "state_code": "MA"} for key in key_names])
    if excluded or set(collection) != {"MA"}:
        raise ValueError("Incomplete valid Massachusetts county geometry")
    layer = collection["MA"]
    layer["boundary_vintage"] = 2026
    layer["features"].sort(key=lambda feature: feature["properties"]["key"])
    for feature in layer["features"]:
        p = feature["properties"]
        if p["name"] != key_names.pop(p["key"]) + " County":
            raise ValueError("Massachusetts county name differs from its FIPS")
        p["level"] = "county"
    if key_names:
        raise ValueError("Missing Massachusetts county geometry")
    body = (json.dumps(layer, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    compressed = bytearray(gzip.compress(body, mtime=0))
    compressed[9] = 3
    with args.output.open("xb") as stream:
        stream.write(compressed)
    print(len(compressed), hashlib.sha256(compressed).hexdigest())


if __name__ == "__main__":
    main()
