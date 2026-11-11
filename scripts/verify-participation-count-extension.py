"""Independently verify all old bytes/records and new native-count arithmetic."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import zipfile


def verify(base_archive, output, facts, recipe):
    checks = 0

    def require(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            raise ValueError(message)

    with zipfile.ZipFile(base_archive) as archive:
        descriptor = json.loads(archive.read("runtime/dataset.json"))
        base = {name: archive.read("runtime/" + name) for name in descriptor["files"]}
    new = {name: (output / name).read_bytes() for name in descriptor["files"]}
    untouched = [name for name in base if base[name] == new[name]]
    require(len(untouched) == len(base) - 2, "Unexpected runtime changes outside one state/index")
    require(set(base) - set(untouched) == {"index.json", "states/NJ.json.gz"}, "Wrong incremental footprint")
    old_index, index = json.loads(base["index.json"]), json.loads(new["index.json"])
    for code in old_index["states"]:
        if code != "NJ":
            require(old_index["states"][code] == index["states"][code], "Untouched state declaration changed")
            require(old_index["coverage"][code] == index["coverage"][code], "Untouched state coverage changed")
    old, shard = (json.loads(gzip.decompress(data)) for data in (base["states/NJ.json.gz"], new["states/NJ.json.gz"]))
    require(shard["records"][:len(old["records"])] == old["records"], "Prior native observations were changed")
    additions = shard["records"][len(old["records"]):]
    require(len(additions) == len(recipe["sources"]) == 2, "Incomplete or excessive new count query")
    for record, source in zip(additions, recipe["sources"]):
        report = next(row for row in facts["reports"] if row["key"] == source["report_key"])
        columns = report["columns"]
        rows = {row["label"]: row["count_literals"] for row in report["rows"]}
        require(len(rows) == len(report["rows"]), "Duplicate native table row")

        def number(literal):
            return int(literal.replace(",", "")) if literal else None

        selected = [[number(rows[label][columns.index(field)]) for field in source["count_columns"]]
            for label in source["selected_labels"]]
        require(all(value is not None for row in selected for value in row)
            and all(row == selected[0] for row in selected), "Native selected observations disagree")
        for field in source["count_columns"]:
            i = columns.index(field)
            districts = [values for label, values in rows.items() if label.startswith("Congressional District ")]
            municipal = [values for label, values in rows.items() if label != report["geography"]["name"] + " County"
                and "TOTALS" not in label and not label.startswith("Congressional District ")]
            expected = number(rows[source["selected_labels"][0]][i])
            require(len(districts) == 3 and all(values[i] for values in districts)
                and sum(number(values[i]) for values in districts) == expected, "Native district sum differs")
            require(all(values[i] for values in municipal)
                and sum(number(values[i]) for values in municipal) == expected, "Native municipality sum differs")
        value = sum(selected[0])
        require(record["count"]["value"] == record["view"]["ballots"] == value, "Derived source subtotal differs")
        require(record["source"]["fields"] == report, "Complete native query not retained")
        require(record["denominator"] is None and record["view"]["reported_pct"] is None,
            "A new denominator or rate was inferred")
        require(record["reporting_status"]["complete"] is None and record["view"]["maps_approved"] is False,
            "Reporting completeness or geography was promoted")
        require(record["source_clock"]["literal"] == report["source_clock"]["literal"]
            and record["source_clock"]["timezone"] is None, "Native clock changed or timezone invented")
        require(record["geography"]["join"]["status"] == "unreviewed", "A new geographic join was approved")
        if report["key"] == "essex":
            require(any(row["field"] == "mail_ballots_to_be_processed" and row["values"] == [11740, 1990]
                and not row["repaired"] and not row["affects_selected_count"]
                for row in record["quality"]["conflicts"]), "Unrelated processing conflict was repaired or lost")
        if report["key"] == "hudson":
            require(record["view"]["native_record"]["provisional_ballots_counted"] == "1200"
                and value == 213051, "Counted provisional ballots were silently added")
    for mode in ("available", "official", "uf_vep", "uf_vap"):
        require(shard["views"][mode]["counties"][:19] == old["views"][mode]["counties"]
            and len(shard["views"][mode]["counties"]) == 21, "Qualified county bindings differ")
    for mode in ("in_person_early", "mail_returned"):
        require(shard["views"][mode] == old["views"][mode], "Early or returned frames were substituted")
    final = json.loads((output / "dataset.json").read_bytes())
    for name, body in new.items():
        require(final["files"][name] == dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest()),
            "Runtime file checksum differs")
    return dict(status="passed_independent_incremental_count_verification", checks=checks,
        new_county_observations=2, all_county_selections=21, prior_state_observations_preserved=len(old["records"]),
        unchanged_runtime_files=len(untouched), unaffected_state_shards=50,
        new_counts={row["geography"]["name"]: row["count"]["value"] for row in additions},
        state_population_or_turnout_total_derived=False, new_registration_rates=False,
        new_reference_or_geometry_approvals=False, conflicts_and_unknowns_preserved=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base-archive", "runtime", "facts", "recipe", "proof"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.base_archive, args.runtime, json.loads(args.facts.read_bytes()),
        json.loads(args.recipe.read_bytes()))
    if args.proof.exists():
        raise ValueError("Do not replace an accepted verification receipt")
    args.proof.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
