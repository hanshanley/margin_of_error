"""Audit complete Virginia current-reference fragments and withhold unsupported joins."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re

from pyproj import Transformer
from shapely import is_valid_reason
from shapely.geometry import shape
from shapely.ops import transform, unary_union
from shapely.strtree import STRtree


SPEC = importlib.util.spec_from_file_location("virginia_localities",
    Path(__file__).with_name("review-virginia-2026-locality-results.py"))
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)
require = native.require


def precinct_code(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9]{3,4}", value.strip()),
            "Unreviewed native numeric precinct code")
    return value.strip().zfill(4)


def literal_label(value):
    return " ".join(value.casefold().split())


def fragment_issue(geometry):
    if geometry is None:
        return "native_null_geometry"
    polygon = shape(geometry)
    if polygon.is_empty:
        return "native_empty_geometry"
    if polygon.geom_type not in {"Polygon", "MultiPolygon"}:
        return "native_nonpolygon_geometry"
    if not polygon.is_valid:
        return is_valid_reason(polygon)
    return None


def literal_names_match(results, aliases):
    return bool({literal_label(re.sub(r"^[0-9]+\s*-\s*", "", value)) for value in results}
                & {literal_label(value) for value in aliases})


def audit(package):
    checksums = json.loads((package / "checksums.json").read_text())
    for filename, receipt in checksums.items():
        body = (package / filename).read_bytes()
        require(len(body) == receipt["bytes"]
                and hashlib.sha256(body).hexdigest() == receipt["sha256"],
                "Source package checksum conflict")
    source = package / "current-reference-geometry"
    sources = native.verify_capture(source)
    capture = native.geometry_capture(source, sources)
    groups, attributes, invalid, blank = defaultdict(list), defaultdict(list), [], []
    for key in sorted(k for k in sources if k.startswith("district-union-features-")):
        page = json.loads(native.reports.verified(source, key, sources[key]))
        for feature in page["features"]:
            properties = feature["properties"]
            county, precinct = properties["CountyFIPS"], properties["PrcnctNum"]
            if not county or not precinct:
                blank.append(properties)
                continue
            require(re.fullmatch(r"[0-9]{3}", county), "Unreviewed native county code")
            identity = (county, precinct_code(precinct))
            require(properties["PrcnctFIPS"] == identity[1].zfill(6)
                    and properties["GEOID"] == "51" + county + properties["PrcnctFIPS"],
                    "Conflicting native geometry identifiers")
            attributes[identity].append(properties)
            groups[identity]
            issue = fragment_issue(feature["geometry"])
            if issue:
                invalid.append(dict(identity=identity, object_id=properties["OBJECTID"], reason=issue))
            else:
                groups[identity].append(shape(feature["geometry"]))
    bad = {tuple(row["identity"]) for row in invalid}
    dissolved = {}
    for identity, polygons in groups.items():
        if identity in bad:
            continue
        polygon = unary_union(polygons)
        if polygon.is_valid and not polygon.is_empty:
            dissolved[identity] = polygon
        else:
            bad.add(identity)
    identities = sorted(dissolved)
    shapes = [dissolved[key] for key in identities]
    tree = STRtree(shapes)
    project = Transformer.from_crs(4326, 5070, always_xy=True).transform
    overlaps, tiny = [], 0
    areas = [transform(project, polygon).area for polygon in shapes]
    for index, polygon in enumerate(shapes):
        for raw_other in tree.query(polygon, predicate="intersects"):
            other = int(raw_other)
            if other <= index:
                continue
            intersection = polygon.intersection(shapes[other])
            if intersection.area == 0:
                continue
            area = transform(project, intersection).area
            fraction = area / min(areas[index], areas[other])
            if area > 1 and fraction > 0.0000001:
                overlaps.append(dict(left=identities[index], right=identities[other],
                                     area_square_meters=area, smaller_precinct_fraction=fraction))
            else:
                tiny += 1
    overlapping = {tuple(row[side]) for row in overlaps for side in ["left", "right"]}
    official_ids, format_changes, canonical_names = {}, {}, {}
    with (package / "earlier-report-review/precinct-counts.csv").open() as stream:
        for row in csv.DictReader(stream):
            identity = (row["locality_code"], row["precinct"])
            raw = row["precinct_id"]
            require(official_ids.setdefault(identity, raw) == raw, "Conflicting original precinct IDs")
            canonical = (row["locality_code"], precinct_code(raw))
            require(canonical_names.setdefault(canonical, row["precinct"]) == row["precinct"],
                    "Ambiguous normalized precinct identity")
            if raw != canonical[1]:
                format_changes[canonical] = dict(locality_code=canonical[0], raw=raw,
                                                  canonical=canonical[1])
    roots = package / "native-locality-source"
    root_sources = native.verify_capture(roots)
    metadata = {}
    for key in sorted(k for k in root_sources if k.startswith("locality-")):
        locality = key.split("-")[1]
        data = json.loads(native.reports.verified(roots, key, root_sources[key]))
        for precinct in data["precincts"]:
            identity = (locality, precinct["id"])
            require(identity not in metadata, "Duplicate native precinct UUID")
            metadata[identity] = precinct
    result_groups = defaultdict(list)
    with (package / "precinct-counts.csv").open() as stream:
        for row in csv.DictReader(stream):
            code = row["locality_code"]
            result_groups[(code, precinct_code(official_ids[(code, row["precinct"])]))].append(row)
    label_counts, label_conflicts, eligibility = Counter(), [], []
    for identity, units in sorted(result_groups.items()):
        names = {row["precinct"] for row in units}
        aliases = {a[field] for a in attributes.get(identity, [])
                   for field in ["PrcnctName", "PrcNmeLong"] if a[field]}
        literal_match = literal_names_match(names, aliases)
        generic = aliases and all(re.fullmatch(
            r"precinct\s*0*" + str(int(identity[1])), literal_label(n)) for n in aliases)
        classification = ("literal_name_match_ignoring_case_and_whitespace" if literal_match
                          else "generic_number_only_reference_label" if generic
                          else "unmatched_or_conflicting_literal_label")
        label_counts[classification] += 1
        if not literal_match:
            label_conflicts.append(dict(identity=identity, results=sorted(names),
                                        reference=sorted(aliases), classification=classification))
        flags = []
        if identity not in groups:
            flags.append("missing_reference_identity")
        if identity in bad:
            flags.append("null_invalid_or_empty_native_fragment")
        if identity in overlapping:
            flags.append("material_reference_overlap")
        if not literal_match:
            flags.append("unreviewed_literal_label")
        if not all(row["precinct_mode_allocation_complete"] == "True" for row in units):
            flags.append("incomplete_locality_house_mode_scope")
        if len(units) != 1:
            flags.append("multiple_house_district_parts")
        require(all((row["locality_code"], row["precinct_uuid"]) in metadata for row in units),
                "Unmatched native precinct UUID")
        if any(metadata[(row["locality_code"], row["precinct_uuid"])]["isVirtual"] is not False
               for row in units):
            flags.append("virtual_or_unreported_native_unit_type")
        eligibility.append(dict(identity=identity, flags=flags,
            supported_candidate_subset=not flags, election_day_geometry_certified=False))
    return dict(year=2026, state_code="VA", input_checksums_sha256=hashlib.sha256(
        (package / "checksums.json").read_bytes()).hexdigest(),
        complete_reference_capture=capture, blank_identity_fragments=len(blank),
        invalid_fragments=invalid, invalid_identities=sorted(bad),
        valid_dissolved_identities=len(dissolved), material_overlaps=overlaps,
        materially_overlapping_identities=len(overlapping), subthreshold_overlap_pairs=tiny,
        result_precincts=len(result_groups), canonical_exact_id_matches=len(set(result_groups) & set(groups)),
        geometry_only=sorted(set(groups) - set(result_groups)),
        source_id_format_changes=[format_changes[k] for k in sorted(format_changes)],
        label_classifications=dict(label_counts), label_conflicts=label_conflicts,
        precinct_eligibility=eligibility,
        supported_candidate_subset=sum(row["supported_candidate_subset"] for row in eligibility),
        geometry_approved=False, maps_approved=False,
        scope="Current official reference, not certified election-day shapes. Any invalid fragment "
              "withholds its entire identity. Material overlaps exceed both 1 square meter and "
              "0.0000001 of the smaller precinct in EPSG:5070. No shape repair, fuzzy labels, "
              "county-mode allocation, cross-district allocation or turnout-rate inference.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Refusing immutable audit overwrite")
    result = audit(args.source)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {
        "invalid_fragments", "material_overlaps", "precinct_eligibility", "label_conflicts"}}, indent=2))
