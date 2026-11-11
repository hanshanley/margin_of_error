"""Independent scalar verification of reference-only county binding updates."""

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path


def digest(body):
    return hashlib.sha256(body).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def verify(base_counts, base_native, runtime, inputs):
    checks = 0

    def require(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            raise ValueError(message)

    recipe = json.loads((inputs / "recipe.json").read_bytes())
    code = recipe["state_code"]
    geometry_body = (inputs / "reference.json").read_bytes()
    require(digest(geometry_body) == recipe["geometry_sha256"], "Reference bytes changed")
    geometry = json.loads(geometry_body)
    review_body = (inputs / "previous-review.json").read_bytes()
    require(digest(review_body) == recipe["previous_review_sha256"], "Prior qualification input changed")
    review = json.loads(review_body)
    facts_body = (inputs / "native-facts.json").read_bytes()
    require(digest(facts_body) == recipe["native_facts_sha256"], "Native county facts changed")
    facts = json.loads(facts_body)
    features = {row["properties"]["key"]: row for row in geometry["features"]}
    require(len(features) == len(geometry["features"]) == recipe["expected_counties"], "Incomplete reference")
    for feature in features.values():
        p = feature["properties"]
        require(p["state_code"] == code and p["boundary_year"] == recipe["boundary_year"], "Reference scope differs")
    old_count_index = json.loads((base_counts / "index.json").read_bytes())
    count_index = json.loads((runtime / "counts/index.json").read_bytes())
    path = old_count_index["states"][code]["file"]
    old = json.loads(gzip.decompress((base_counts / path).read_bytes()))
    new = json.loads(gzip.decompress((runtime / "counts" / path).read_bytes()))
    require(old["views"] == new["views"], "Source mode selections changed")
    require(len(old["records"]) == len(new["records"]), "Source observations changed")
    selected = set(old["views"][recipe["modes"][0]]["counties"])
    old_joins = {row["county_id"]: row for row in review["observations"] if row["state_code"] == code}
    old_by_id = {row["id"]: row for row in old["records"]}
    retained, added = 0, 0
    for row in new["records"]:
        before = old_by_id[row["id"]]
        comparable = copy.deepcopy(row)
        if row["id"] in selected:
            comparable["geography"]["join"] = before["geography"]["join"]
            for key in ("maps_approved", "reference_geometry"):
                if key in before["view"]:
                    comparable["view"][key] = before["view"][key]
                else:
                    comparable["view"].pop(key, None)
            join, view = row["geography"]["join"], row["view"]
            require(join["status"] == "approved" and join["reference_id"] == recipe["geometry_sha256"],
                "Unqualified reference hash")
            feature = features[join["feature_key"]]["properties"]
            require(view["geography_level"] == "county" and row["geography"]["level"] == "county"
                and feature["name"].removesuffix(" County").upper() == view["county"].upper(), "County identity differs")
            require(view["reference_geometry"]["sha256"] == recipe["geometry_sha256"]
                and view["reference_geometry"]["boundary_year"] == recipe["boundary_year"]
                and view["maps_approved"] is True, "View reference qualifier differs")
            prior = old_joins.get(view["county_id"])
            if prior:
                require(digest(canonical(before["view"])) == prior["source_record_sha256"]
                    and prior["contextual_geoid"] == join["feature_key"], "Old source-record-hash oracle differs")
                retained += 1
            else:
                require(row["source"]["id"] in recipe["new_source_ids"], "Unregistered new geographic qualification")
                reports = [report for report in facts["reports"]
                    if report["geography"]["state_code"] == code and report["geography"]["name"] == view["county"]]
                require(len(reports) == 1 and reports[0] == row["source"]["fields"]
                    and reports[0]["geography"]["level"] == "county", "Whole native county source differs")
                require(row["denominator"] is None and view["reported_pct"] is None
                    and row["reporting_status"]["complete"] is None, "A new rate or completion was inferred")
                added += 1
        require(comparable == before, "A source number, clock, field, conflict or other observation changed")
    require(retained == recipe["expected_retained"] and added == recipe["expected_new"], "Wrong qualification footprint")
    old_native_index = json.loads((base_native / "index.json").read_bytes())
    native_index = json.loads((runtime / "native/index.json").read_bytes())
    comparable_native = copy.deepcopy(native_index)
    qualifier_keys = ["state_code", "county_id", "county", "geography_level", "county_fips",
        "reference_municipality_key", "source_administration_id", "source_mode", "denominator_basis",
        "participation_measure_kind", "participation_measure_literal", "participation_measure_label",
        "cast_ballot_count_qualified", "unique_voter_count_qualified"]
    new_by_id = {row["id"]: row for row in new["records"]}
    for mode in recipe["modes"]:
        binding = native_index["county_bindings"][code][mode]
        require(binding["sha256"] == recipe["geometry_sha256"]
            and binding["features"] == len(features) and len(binding["rows"]) == len(selected),
            "Native binding inventory differs")
        for bound in binding["rows"]:
            row = next(new_by_id[key] for key in new["views"][mode]["counties"]
                if new_by_id[key]["view"]["county_id"] == bound["county_id"])
            require(bound["qualifier"] == {key: row["view"].get(key) for key in qualifier_keys}
                and bound["feature_key"] == row["geography"]["join"]["feature_key"], "Native qualifier differs")
        del comparable_native["county_bindings"][code][mode]
    comparable_native["county_frame_checks"] -= len(recipe["modes"])
    comparable_native.pop("extensions")
    if "extensions" in old_native_index:
        comparable_native["extensions"] = old_native_index["extensions"]
    require(comparable_native == old_native_index, "An old native layer, mode, table or reference changed")
    count_comparable = copy.deepcopy(count_index)
    count_comparable["states"][code] = old_count_index["states"][code]
    count_comparable["extensions"] = old_count_index["extensions"]
    require(count_comparable == old_count_index, "Unrelated count metadata changed")
    unchanged = {}
    for family, baseline in (("counts", base_counts), ("native", base_native)):
        description = json.loads((runtime / family / "dataset.json").read_bytes())
        old_description = json.loads((baseline / "dataset.json").read_bytes())
        require(set(description["files"]) == set(old_description["files"]), "Runtime file inventory changed")
        identical = 0
        for name, expected in description["files"].items():
            body = (runtime / family / name).read_bytes()
            require(dict(bytes=len(body), sha256=digest(body)) == expected, "Runtime hash differs")
            if body == (baseline / name).read_bytes():
                identical += 1
            else:
                require(name in (["index.json", path] if family == "counts" else ["index.json"]),
                    "Unrelated runtime bytes changed")
        unchanged[family] = identical
    require(unchanged == dict(counts=51, native=29), "Incremental footprint differs")
    return dict(status="passed_independent_county_binding_extension", checks=checks,
        qualified_contextual_counties=retained + added, retained_identities=retained,
        newly_qualified_identities=added, unchanged_runtime_files=unchanged,
        all_source_observations_preserved_except_explicit_reference_metadata=True,
        all_source_counts_rates_clocks_and_conflicts_unchanged=True, geometry_changed=False,
        new_rates_or_precinct_allocations=False, source_reductions_repeated=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base-counts", "base-native", "runtime", "inputs", "proof"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.base_counts, args.base_native, args.runtime, args.inputs)
    if args.proof.exists():
        raise ValueError("Use a fresh independent receipt")
    args.proof.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
