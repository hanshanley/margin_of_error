"""Join the July 2026 NM precinct release to the saved election-night participation rows."""

import argparse
import gzip
import hashlib
import io
import json
import re
import shutil
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import shapefile


BOUNDARY_URL = (
    "https://gstore.unm.edu/apps/rgis/datasets/297dcb42-ac88-4026-abda-f1e614e79e8a/"
    "New_Mexico_Voting_Precinct_20260717_FGDC.original.zip"
)
METADATA_URL = (
    "https://gstore.unm.edu/apps/rgis/datasets/297dcb42-ac88-4026-abda-f1e614e79e8a/"
    "metadata/FGDC-STD-001-1998.html"
)


def precinct_number(label, county):
    pattern = r"(?:(?:PCT|PREC|PRECINCT)\s+)?(\d+)"
    if county == "Hidalgo":
        pattern += r"(?:\s*-\s*[A-Z /]+)?"
    match = re.fullmatch(pattern, label.strip(), re.I)
    return str(int(match.group(1))) if match else None


def join_precincts(features, rows, counties):
    shapes, reporting = defaultdict(list), defaultdict(list)
    for feature in features:
        shapes[feature["properties"]["county"]].append(feature)
    for row in rows:
        if row["state_code"] == "NM":
            reporting[row["county"]].append(row)
    county_rows = {row["county"]: row for row in counties if row["state_code"] == "NM"}
    audit = []
    for county in sorted(set(shapes) | set(reporting)):
        polygons, observations = shapes[county], reporting[county]
        shape_keys = [feature["properties"]["precinct"] for feature in polygons]
        row_keys = [precinct_number(row["unit"], county) for row in observations]
        reconciles = bool(county_rows.get(county, {}).get("rows_reconcile"))
        matched = bool(polygons) and reconciles and (
            None not in row_keys
            and len(shape_keys) == len(set(shape_keys))
            and len(row_keys) == len(set(row_keys))
            and set(shape_keys) == set(row_keys)
            and all(row["unit_kind"] == "precinct" for row in observations)
            and all(row["county_id"] == county_rows[county]["county_id"] for row in observations)
        )
        by_key = dict(zip(row_keys, observations)) if matched else {}
        colored = 0
        for feature in polygons:
            p = feature["properties"]
            row = by_key.get(p["precinct"])
            rate = row["reported_pct"] if row and row["denominator"] >= 25 else None
            colored += rate is not None
            p.update({
                "unit_key": row["unit_key"] if row else None,
                "county_id": row["county_id"] if row else None,
                "unit": row["unit"] if row else "Precinct " + p["precinct"],
                "ballots": row["ballots"] if row else None,
                "denominator": row["denominator"] if row else None,
                "denominator_basis": row["denominator_basis"] if row else None,
                "reported_pct": rate,
                "source_url": row["source_url"] if row else None,
                "source_update_label": row["source_update_label"] if row else None,
                "match_status": "county_precinct_set_mismatch" if not matched
                    else "matched" if rate is not None else "rate_withheld",
            })
        audit.append({
            "county": county, "boundary_precincts": len(polygons), "reporting_rows": len(observations),
            "exact_precinct_set": matched, "colored_precincts": colored,
            "boundary_only_ids": sorted(set(shape_keys) - set(row_keys)),
            "reporting_only_ids": sorted(str(key) for key in set(row_keys) - set(shape_keys)),
            "unparsed_labels": [row["unit"] for row, key in zip(observations, row_keys) if key is None],
        })
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundaries", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--research", type=Path, default=Path("../voter-participation"))
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new immutable output directory")
    sys.path.insert(0, str(args.research.resolve()))
    from scripts.build import simplify

    pointer = json.loads(Path("public/participation-current/latest.json").read_text())
    reporting_path = Path("public/participation-current") / pointer["snapshot_id"] / "local.json"
    reporting = json.loads(reporting_path.read_text())
    features = []
    with zipfile.ZipFile(args.boundaries) as archive:
        stem = next(name[:-4] for name in archive.namelist() if name.endswith(".shp"))
        reader = shapefile.Reader(**{
            ext: io.BytesIO(archive.read(stem + "." + ext)) for ext in ["shp", "shx", "dbf"]
        })
        for record in reader.iterShapeRecords():
            p = record.record.as_dict()
            if p["STATE"] != "35" or p["GEOCODE"] != p["STATE"] + p["COUNTY_FIP"] + p["VTD"]:
                raise ValueError("Invalid source precinct geography identity")
            number = str(int(p["VTD_NUM"]))
            geometry = record.shape.__geo_interface__
            polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
            simplified = []
            for polygon in polygons:
                rings = []
                for ring in polygon:
                    points = simplify(ring, .0001)
                    if len(points) < 4:
                        points = ring
                    rings.append([[round(x, 6), round(y, 6)] for x, y, *rest in points])
                simplified.append(rings)
            features.append({
                "type": "Feature",
                "properties": {"key": "35" + p["COUNTY_FIP"] + number.zfill(6),
                               "source_geocode": p["GEOCODE"], "source_vtd": p["VTD"],
                               "county_fips": "35" + p["COUNTY_FIP"],
                               "state_code": "NM", "county": p["COUNTY_NAM"],
                               "precinct": number, "boundary_date": "2026-07-17"},
                "geometry": {"type": "MultiPolygon", "coordinates": simplified},
            })
    audit = join_precincts(features, reporting["precincts"], reporting["counties"])
    args.output.mkdir(parents=True)

    def save(name, value, compressed=False):
        content = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        (args.output / name).write_bytes(gzip.compress(content, mtime=0) if compressed else content)

    save("NM.geojson.gz", {"type": "FeatureCollection", "features": features}, True)
    save("audit.json", audit)
    originals = args.output / "originals"
    originals.mkdir()
    shutil.copyfile(args.boundaries, originals / "NM-precincts-20260717.zip")
    shutil.copyfile(args.metadata, originals / "NM-precincts-20260717-metadata.html")
    save("index.json", {
        "year": 2026, "election_date": "2026-11-03", "boundary_date": "2026-07-17",
        "states": {"NM": "NM.geojson.gz"}, "boundary_features": len(features),
        "matched_counties": sum(row["exact_precinct_set"] for row in audit),
        "matched_precincts": sum(row["boundary_precincts"] for row in audit if row["exact_precinct_set"]),
        "colored_precincts": sum(row["colored_precincts"] for row in audit),
        "unmatched_counties": [row["county"] for row in audit if not row["exact_precinct_set"]],
        "boundary_source": BOUNDARY_URL, "boundary_metadata": METADATA_URL,
        "reporting_snapshot": pointer["snapshot_id"],
        "reporting_sha256": hashlib.sha256(reporting_path.read_bytes()).hexdigest(),
        "minimum_electorate": 25,
        "precinct_number_field": "VTD_NUM (Voting District Number)",
        "limitations": [
            "July 2026 reference boundaries, not certified election-night geography.",
            "County + explicit precinct number join; complete unique county precinct sets must match.",
            "Uses VTD_NUM: eight updated Sandoval shapes retain older Census VTD/GEOCODE values.",
            "A matching ID does not establish unchanged precinct boundaries or electorate across elections.",
            "Entire mismatched counties remain neutral; no county rates are allocated to precincts.",
            "Eligible Voters is the portal's electorate definition, not an assumed citizen or registered population.",
            "Unofficial captured counts, not final turnout; missing rates and electorates under 25 are withheld.",
        ],
    })
    save("checksums.json", {
        str(path.relative_to(args.output)): {
            "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
        } for path in sorted(args.output.rglob("*")) if path.is_file()
    })
    print(json.dumps(json.loads((args.output / "index.json").read_text()), indent=2))


if __name__ == "__main__":
    main()
