"""Publish direct county candidate counts without inventing unlocated write-ins."""

import argparse
from collections import Counter
import csv
from datetime import datetime
from fractions import Fraction
import gzip
import hashlib
import io
import json
from pathlib import Path
import re

CONTRACT = "participation.county_candidate_subsets.v1"
MAX_INTEGER = 9007199254740991


def require(condition, message):
    if not condition:
        raise ValueError(message)


def count(value):
    require(type(value) is int and 0 <= value <= MAX_INTEGER, "Unknown or invalid candidate count")
    return value


def clock(value):
    require(isinstance(value, str) and value.endswith("Z"), "Missing explicit UTC source clock")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def vector(candidates):
    require(isinstance(candidates, list) and bool(candidates), "Missing candidate inventory")
    result = {}
    for candidate in candidates:
        name, party = candidate.get("name"), candidate.get("party")
        require(isinstance(name, str) and bool(name.strip()) and isinstance(party, str)
                and bool(party.strip()), "Missing literal candidate identity")
        require((name, party) not in result, "Duplicate candidate identity")
        result[name, party] = count(candidate.get("votes"))
    return result


def margin_bounds(dem, rep, located_other, unlocated):
    total = dem + rep + located_other
    require(total + unlocated <= MAX_INTEGER, "Candidate total exceeds safe integer range")
    if not total:
        return None
    return sorted(float(Fraction(100 * (dem - rep), denominator))
                  for denominator in (total, total + unlocated))


def compile_subset(review, originals, reference):
    require(review.get("contract") == "participation.county_candidate_subset_review.v1",
            "Unreviewed candidate-subset rule")
    year, code, state_fips = (review.get(key) for key in ("year", "state_code", "state_fips"))
    require(type(year) is int and re.fullmatch(r"[A-Z]{2}", code or "")
            and re.fullmatch(r"\d{2}", state_fips or ""), "Invalid election/state identity")
    require(review.get("office") == "U.S. House" and review.get("stage") == "General"
            and review.get("round") == 1 and review.get("boundary_reference_year") == year,
            "Unsupported office, stage, round or boundary frame")
    require(review.get("freshness") == "retained_historical_observation",
            "Retained evidence cannot be represented as a fresh collection")
    records, geometry = reference.get("reference", {}), reference.get("geometry", {})
    require(records and all(re.fullmatch(r"\d{5}", key) and key.startswith(state_fips)
            and row.get("GEOID") == key and row.get("STATEFP") == state_fips
            for key, row in records.items()), "Invalid native county reference")
    features = geometry.get("features", [])
    require(geometry.get("type") == "FeatureCollection" and len(features) == len(records)
            and {feature["properties"]["key"] for feature in features} == set(records),
            "County geometry inventory differs from the native reference")
    for feature in features:
        p = feature.get("properties", {})
        require(p.get("state_code") == code and p.get("boundary_year") == year
                and p.get("name") == records[p["key"]]["NAMELSAD"]
                and feature.get("geometry", {}).get("type") in ("Polygon", "MultiPolygon"),
                "County reference identity or vintage changed")
    grouped, decisions, districts = {}, [], set()
    declared = review.get("districts")
    require(isinstance(declared, list) and bool(declared)
            and {entry["file"] for entry in declared} == set(originals),
            "Original inventory differs from the reviewed district inventory")
    for entry in declared:
        raw = originals[entry["file"]]
        receipt = entry.get("receipt", {})
        require(receipt.get("status") == 200 and receipt.get("bytes") == len(raw)
                and receipt.get("sha256") == hashlib.sha256(raw).hexdigest()
                and re.fullmatch(r"https://civicapi\.org/api/v2/race/\d+", receipt.get("url", "")),
                "Original URL, size, status or checksum differs")
        native = json.loads(raw)
        district = entry.get("district")
        require(district not in districts and re.fullmatch(code + r"-\d{2}", district or ""),
                "Duplicate or invalid district identity")
        districts.add(district)
        require(native.get("country") == "US" and native.get("province") == code
                and native.get("district") == district and native.get("test_data") is False
                and native.get("election_type") == "House of Representatives"
                and native.get("election_scope") == "General" and native.get("round") == 1
                and str(native.get("election_date", "")).startswith(str(year) + "-11-03T"),
                "Source election, office, geography, stage or round changed")
        require(clock(native.get("last_updated")) <= datetime.fromisoformat(receipt["acquired_at"]),
                "Source clock follows its receipt")
        expected = vector(native.get("candidates"))
        roles = entry.get("candidate_roles", [])
        require(len(roles) == len(expected) and len({r.get("candidate_id") for r in roles}) == len(roles)
                and {(r["name"], r["party"]) for r in roles} == set(expected)
                and {r["role"] for r in roles} <= {"D", "R", "unallocated_other"}
                and sum(r["role"] == "D" for r in roles) == 1
                and sum(r["role"] == "R" for r in roles) == 1, "Candidate coverage or reviewed roles changed")
        for r in roles:
            require(any(c.get("candidate_id") == r["candidate_id"] and c.get("name") == r["name"]
                        and c.get("party") == r["party"] for c in native["candidates"]),
                    "Stable provider candidate identity changed")
            require((r["role"] == "D" and r["party"] == "Democratic")
                    or (r["role"] == "R" and r["party"] == "Republican")
                    or (r["role"] == "unallocated_other" and r["party"] == "Nonpartisan"
                        and r["name"] == "Write-in"), "Unsupported candidate role or aggregate")
        totals, fragments, seen, ignored = Counter({key: 0 for key in expected}), [], set(), []
        regions = native.get("region_results")
        require(isinstance(regions, dict), "Missing direct county regions")
        for source_key, region in regions.items():
            if region.get("type") in ("Town", "Township", "House District", "State"):
                ignored.append({"source_key": source_key, "native_type": region["type"]})
                continue
            require(region.get("type") == "County", "Unreviewed non-county or unlocated source region")
            key = region.get("fips")
            require(key in records and key not in seen and region.get("name") == records[key]["NAME"],
                    "Missing, duplicate or mismatched native county identity")
            seen.add(key)
            votes = vector(region.get("candidates"))
            require(set(votes) == set(expected), "Missing or unexpected county candidate")
            totals.update(votes)
            fragments.append({"geography": key, "source_key": source_key, "district": district,
                "source_url": receipt["url"], "source_sha256": receipt["sha256"],
                "source_updated_at": native["last_updated"], "source_round": 1,
                "candidates": region["candidates"]})
        require(bool(fragments), "No direct county candidate counts")
        residuals = []
        for r in roles:
            identity = r["name"], r["party"]
            missing = expected[identity] - totals[identity]
            require(missing >= 0 and (r["role"] == "unallocated_other" or missing == 0),
                    "Major-party vectors do not reconcile or county counts exceed the district")
            residuals.append({**r, "district_votes": expected[identity],
                              "located_county_votes": totals[identity], "unlocated_votes": missing})
        missing_other = sum(r["unlocated_votes"] for r in residuals)
        for fragment in fragments:
            fragment["unlocated_other_upper_bound"] = missing_other
            grouped.setdefault(fragment["geography"], []).append(fragment)
        decisions.append({"district": district, "source_url": receipt["url"],
            "source_sha256": receipt["sha256"], "source_updated_at": native["last_updated"],
            "candidate_decisions": residuals, "ignored_nested_regions": ignored,
            "complete_vector_qualified": missing_other == 0, "source_round": 1})
    require(set(grouped) == set(records), "District inventory does not cover every state county")
    rows = []
    for key, fragments in sorted(grouped.items()):
        by_party = Counter()
        for fragment in fragments:
            for candidate in fragment["candidates"]:
                by_party[candidate["party"]] += candidate["votes"]
        dem, rep = by_party["Democratic"], by_party["Republican"]
        located_other = sum(by_party.values()) - dem - rep
        upper = sum(f["unlocated_other_upper_bound"] for f in fragments)
        bounds = margin_bounds(dem, rep, located_other, upper)
        rows.append({"geography": key, "geography_name": records[key]["NAMELSAD"],
            "state_code": code, "year": year, "level": "county", "office": "U.S. House",
            "stage": "General", "source_round": 1, "democratic_votes": dem, "republican_votes": rep,
            "located_other_votes": located_other, "other_votes": None if upper else located_other,
            "known_candidate_votes": dem + rep + located_other, "contest_votes": None if upper else dem + rep + located_other,
            "unlocated_other_upper_bound": upper, "margin_bounds_pp": bounds,
            "margin_pp": bounds[0] if bounds and not upper else None,
            "complete_vector_qualified": upper == 0,
            "freshness": "retained_historical_observation", "district_fragments": fragments})
    result = {"contract": CONTRACT, "year": year, "state_code": code, "state_fips": state_fips,
        "office": "U.S. House", "stage": "General", "source_round": 1,
        "boundary_reference_year": year, "freshness": "retained_historical_observation",
        "complete_state_vector_qualified": all(r["complete_vector_qualified"] for r in rows),
        "participation_qualified": False, "swing_qualified": False, "model_update_qualified": False,
        "rows": rows, "geometry": geometry, "district_decisions": decisions,
        "unlocated_other_votes": sum(c["unlocated_votes"] for d in decisions for c in d["candidate_decisions"]),
        "interpretation": (
            "Direct recorded candidate counts in a retained round-1 source observation, not latest/final "
            "RCV results, ballots or turnout. Missing nonmajor votes remain unallocated. All-candidate "
            "margin bounds allow zero through the district's full unlocated mass in each affected county. "
            "These are marginal accounting bounds, not simultaneously attainable allocations or confidence "
            "intervals. A color uses the bound nearest zero, never an exact county margin. No swing or model "
            "eligibility is granted; the existing complete-result hold remains.")}
    return result


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def outputs(folder):
    review = json.loads((folder / "review.json").read_bytes())
    ref = (folder / review["reference_file"]).read_bytes()
    require(hashlib.sha256(ref).hexdigest() == review["reference_sha256"], "Reference checksum differs")
    result = compile_subset(review, {e["file"]: (folder / e["file"]).read_bytes()
                                    for e in review["districts"]}, json.loads(gzip.decompress(ref)))
    raw = bytearray(gzip.compress(encode(result), mtime=0))
    raw[9] = 3
    csv_body = io.StringIO(newline="")
    fields = [key for key in result["rows"][0] if key not in ("district_fragments", "margin_bounds_pp")]
    writer = csv.DictWriter(csv_body, fieldnames=fields + ["margin_lower_pp", "margin_upper_pp",
        "source_updated_at", "source_urls"], lineterminator="\n")
    writer.writeheader()
    for row in result["rows"]:
        bounds = row["margin_bounds_pp"]
        writer.writerow({**{key: row[key] for key in fields},
            "margin_lower_pp": bounds[0] if bounds else None, "margin_upper_pp": bounds[1] if bounds else None,
            "source_updated_at": "|".join(sorted({f["source_updated_at"] for f in row["district_fragments"]})),
            "source_urls": "|".join(sorted({f["source_url"] for f in row["district_fragments"]}))})
    return {"county-subsets.json.gz": bytes(raw), "county-results.csv": csv_body.getvalue().encode(),
            "decisions.json": encode({key: value for key, value in result.items() if key not in ("rows", "geometry")})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bodies = outputs(args.inputs)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, body in bodies.items():
        path = args.output / name
        require(not path.exists() or path.read_bytes() == body, "Refusing to overwrite a different output")
        if not path.exists():
            path.write_bytes(body)
    print(json.dumps({"outputs": {name: hashlib.sha256(body).hexdigest() for name, body in bodies.items()}}))


if __name__ == "__main__":
    main()
