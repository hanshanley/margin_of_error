"""Independently verify missing-only Utah count selection and unchanged references."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def load(root):
    descriptor = json.loads((root / "dataset.json").read_bytes())
    files = {name: (root / name).read_bytes() for name in descriptor["files"]}
    for name, body in files.items():
        if dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest()) != descriptor["files"][name]:
            raise ValueError("Pinned runtime differs: " + name)
    if hashlib.sha256(encoded(dict(files=descriptor["files"],
            contract=descriptor["record_contract"]))).hexdigest() != descriptor["version"]:
        raise ValueError("Runtime content identity differs")
    return descriptor, files, json.loads(files["index.json"])


def scientific(record):
    value = json.loads(json.dumps(record))
    del value["geography"]["join"]
    value["view"].pop("maps_approved", None)
    value["view"].pop("reference_geometry", None)
    return value


def verify(base_counts, base_native, runtime, inputs, commit):
    checks = 0

    def require(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            raise ValueError(message)

    _, old_files, old_index = load(base_counts)
    _, old_native_files, old_native = load(base_native)
    descriptor, files, index = load(runtime / "counts")
    native_descriptor, native_files, native = load(runtime / "native")
    recipe = json.loads((inputs / "extension.json").read_bytes())
    binding_recipe = json.loads((inputs / "recipe.json").read_bytes())
    facts_body = (inputs / "native-facts.json").read_bytes()
    facts = json.loads(facts_body)
    reference_body = (inputs / "reference.json").read_bytes()
    geometry = json.loads(reference_body)
    review = json.loads((inputs / "previous-review.json").read_bytes())
    require(hashlib.sha256(facts_body).hexdigest() == recipe["input_sha256"]
        == binding_recipe["native_facts_sha256"], "Full native facts differ")
    require(hashlib.sha256(reference_body).hexdigest() == review["geometry"]["UT"]["sha256"]
        == binding_recipe["geometry_sha256"], "Accepted geometry bytes changed")
    require(hashlib.sha256((inputs / "previous-review.json").read_bytes()).hexdigest()
        == binding_recipe["previous_review_sha256"], "Accepted identity oracle changed")
    before = json.loads(gzip.decompress(old_files[old_index["states"]["UT"]["file"]]))
    after = json.loads(gzip.decompress(files[index["states"]["UT"]["file"]]))
    prior = {row["id"]: row for row in before["records"]}
    actual = {row["id"]: row for row in after["records"]}
    require(len(actual) == len(after["records"]) == len(prior) + 4, "Source archive inventory differs")
    old_qualified = {row["county_id"]: row for row in review["observations"] if row["state_code"] == "UT"}
    for identity, row in prior.items():
        require(identity in actual, "An old source record was removed")
        if row["view"].get("county_id") in old_qualified and row["count"]["status"] == "reported":
            require(scientific(actual[identity]) == scientific(row), "An accepted scientific field changed")
        else:
            require(actual[identity] == row, "An unselected/held/early/returned record changed")
    reports = {row["key"]: row for row in facts["reports"]}
    replacements = {}
    for source in recipe["sources"]:
        old = prior[source["supersedes"]["id"]]
        report = reports[source["report_key"]]
        require(hashlib.sha256(encoded(old)).hexdigest() == source["supersedes"]["sha256"],
            "The exact superseded source pin differs")
        require(old["count"]["value"] is None and old["count"]["status"] in ("unknown", "withheld"),
            "A reported value or zero was superseded")
        rows = [row for row in after["records"] if row["source"]["id"] == source["id"]]
        require(len(rows) == 1, "Missing or duplicate successor")
        row = rows[0]
        value = int(report["full_summary_statistics"]["Ballots Cast - Total"].replace(",", ""))
        require(row["count"]["value"] == value and row["count"]["status"] == "reported",
            "Explicit native ballot total differs")
        require(row["count"]["literal"] == report["full_summary_statistics"]["Ballots Cast - Total"],
            "Native count literal was repaired")
        require(row["source"]["fields"] == report and row["source"]["input_sha256"] == recipe["input_sha256"],
            "Complete native fields differ")
        require(row["election"] == report["election"] and row["geography"]["id"] == old["geography"]["id"],
            "Successor election or county scope differs")
        require(row["source_clock"]["literal"] == report["source_clock"]["literal"]
            and row["source_clock"]["timezone"] is None, "Clock/timezone was substituted")
        require(row["denominator"] is None and row["view"]["reported_pct"] is None
            and row["reporting_status"]["complete"] is None, "A new fraction or counting completion was inferred")
        require(row["measure"]["kind"] == "ballots_cast"
            and row["view"]["participation_measure_kind"] == "source_defined_participation_count",
            "Native ballot total mislabeled as candidate votes or a derived component sum")
        require(len(source["count_columns"]) == 1 and len(source["selected_labels"]) == 2,
            "Native count/corroboration selection differs")
        for label in source["selected_labels"]:
            selected = [item for item in report["rows"] if item["label"] == label]
            require(len(selected) == 1 and int(selected[0]["count_literals"][0].replace(",", "")) == value,
                "Independent selected total differs")
        replacements[old["id"]] = row["id"]
    for mode, frame in before["views"].items():
        expected = json.loads(json.dumps(frame))
        if mode in binding_recipe["modes"]:
            expected["counties"] = [replacements.get(identity, identity) for identity in expected["counties"]]
        require(after["views"][mode] == expected, "Other source modes or frame order changed")
    selected = [actual[key] for key in after["views"]["official"]["counties"]]
    require(len(selected) == 29 and sum(row["count"]["value"] is not None for row in selected) == 23,
        "Current county coverage differs")
    require(sum(row["view"].get("reported_pct") is not None for row in selected)
        == sum(prior[key]["view"].get("reported_pct") is not None for key in before["views"]["official"]["counties"]),
        "An old rate was lost or a new rate was promoted")
    shapes = {feature["properties"]["key"]: feature for feature in geometry["features"]}
    require(len(shapes) == len(geometry["features"]) == 29, "Reference inventory differs")
    qualifier_keys = ["state_code", "county_id", "county", "geography_level", "county_fips",
        "reference_municipality_key", "source_administration_id", "source_mode", "denominator_basis",
        "participation_measure_kind", "participation_measure_literal", "participation_measure_label",
        "cast_ballot_count_qualified", "unique_voter_count_qualified"]
    for mode in binding_recipe["modes"]:
        binding = native["county_bindings"]["UT"][mode]
        require(binding["sha256"] == binding_recipe["geometry_sha256"]
            and binding["features"] == 29 and len(binding["rows"]) == 29, "Binding inventory differs")
        for match, row in zip(binding["rows"], selected):
            feature = shapes[match["feature_key"]]
            p = feature["properties"]
            require(p["state_code"] == "UT" and p["boundary_year"] == 2024
                and p["name"].upper() == row["geography"]["name"].upper(), "Reference state/name/vintage differs")
            require(match["county_id"] == row["view"]["county_id"]
                and match["qualifier"] == {key: row["view"].get(key) for key in qualifier_keys},
                "Bound source scope differs")
            if row["count"]["value"] is None:
                require(row["view"]["maps_approved"] is False
                    and row["geography"]["join"]["status"] != "approved", "An unknown count was approved")
            else:
                reference = row["view"]["reference_geometry"]
                require(row["geography"]["join"]["feature_key"] == p["key"]
                    and reference["sha256"] == binding["sha256"]
                    and f"/{commit}/" in reference["url"] and reference["boundary_year"] == 2024,
                    "Qualified source/reference identity differs")
    for code, modes in old_native["county_bindings"].items():
        for mode, binding in modes.items():
            require(native["county_bindings"][code][mode] == binding, "An old native mode binding changed")
    for name, body in old_files.items():
        if name not in ("index.json", old_index["states"]["UT"]["file"]):
            require(files[name] == body, "Another state/current snapshot changed")
    for name, body in old_native_files.items():
        if name != "index.json":
            require(native_files[name] == body, "Another native layer/table changed")
    return dict(status="passed_independent_utah_count_successor_verification", checks=checks,
        original_utah_records=len(prior), retained_utah_records=len(prior), new_observations=4,
        selected_counties=29, qualified_counts=23, unresolved_counts=6, geometry_unchanged=True,
        old_rates_and_early_mail_frames_preserved=True, new_analysis_rates=0,
        counts_version=descriptor["version"], native_version=native_descriptor["version"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base-counts", "base-native", "runtime", "inputs", "proof"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    if args.proof.exists():
        raise ValueError("Use a fresh independent receipt")
    result = verify(args.base_counts, args.base_native, args.runtime, args.inputs, args.commit)
    args.proof.write_bytes(encoded(result))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
