"""Prepare pinned missing-only Utah count and contextual-reference recipes."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("counts", "facts", "reference", "previous-review", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--fact-source-commit", required=True)
    args = parser.parse_args()
    if args.output.exists() or len(args.fact_source_commit) != 40:
        raise ValueError("Use a fresh recipe output and exact factual-source commit")
    index = json.loads((args.counts / "index.json").read_bytes())
    shard = json.loads(gzip.decompress((args.counts / index["states"]["UT"]["file"]).read_bytes()))
    by_id = {row["id"]: row for row in shard["records"]}
    selected = {by_id[key]["geography"]["name"]: by_id[key] for key in shard["views"]["official"]["counties"]}
    facts_body, reference_body = args.facts.read_bytes(), args.reference.read_bytes()
    review_body = args.previous_review.read_bytes()
    facts, geometry, review = map(json.loads, (facts_body, reference_body, review_body))
    if sha(reference_body) != review["geometry"]["UT"]["sha256"] or len(geometry["features"]) != 29:
        raise ValueError("Do not replace, repair or simplify the accepted contextual reference")
    modes = ["available", "official", "uf_vep", "uf_vap"]
    if any(shard["views"][mode]["counties"] != shard["views"]["official"]["counties"] for mode in modes):
        raise ValueError("Selected county source frames differ")
    tag = "participation-utah-count-successors-20261111-01"
    complete = f"https://github.com/hanshanley/margin_of_error/releases/download/{tag}/complete-analysis.zip"
    source_path = "data/participation-count-successors/20261111-ut-01/native-facts.json"
    sources = []
    for report in facts["reports"]:
        old = selected[report["geography"]["name"]]
        if old["count"]["value"] is not None or old["count"]["status"] not in ("unknown", "withheld"):
            raise ValueError("A reported old value, including zero, cannot be replaced by this increment")
        notes = [
            "Native Ballots Cast - Total independently corroborated; not candidate selections, processing counts or unique people.",
            f"Native registered total {report['full_summary_statistics']['Registered Voters - Total']} and printed "
            f"turnout {report['full_summary_statistics']['Voter Turnout - Total']} are retained in full facts, "
            "not promoted to an analysis denominator or turnout rate.",
            f"Native precinct completeness: {report['full_summary_statistics']['Precincts Complete']}; "
            f"partially reported: {report['full_summary_statistics']['Precincts Partially Reported']}. "
            "The local OFFICIAL label does not certify state counting completion. Timezone not supplied.",
        ]
        if report["geography"]["name"] == "Kane County":
            notes.append("The G25 workbook filename and explicit November 3, 2026 worksheet header remain literal.")
        if report["geography"]["name"] == "Cache County":
            notes.append("The separate denied workbook remains unavailable; this explicit summary ballot statistic is the source.")
        sources.append(dict(
            id="native-utah-total-20261110-" + report["key"].removeprefix("UT-"),
            report_key=report["key"], election=report["election"],
            geography={**report["geography"], "view_id": old["view"]["county_id"]},
            measure=dict(id="native-20261110-total-ballots", kind="ballots_cast",
                mode="all_methods", literal="Native Ballots Cast - Total", unit="source_reported_count"),
            selected_labels=[row["label"] for row in report["rows"]],
            count_columns=report["columns"], bindings=modes,
            participation_measure_kind="source_defined_participation_count",
            supersedes=dict(id=old["id"], sha256=sha(canonical(old) + b"\n")),
            notes=notes))
    extension = dict(contract="participation.count_extension.v1", id="utah-native-total-successors-20261111-01",
        input_sha256=sha(facts_body), facts_url=f"https://raw.githubusercontent.com/hanshanley/margin_of_error/"
            f"{args.fact_source_commit}/{source_path}", complete_download_url=complete, sources=sources)
    prior = [row for row in review["observations"] if row["state_code"] == "UT"]
    binding = dict(contract="participation.county_binding_extension.v1",
        id="utah-partial-county-successors-20261111-01", state_code="UT",
        native_state_literal="Utah", modes=modes, allow_held_source_rows=True,
        boundary_year=review["geometry"]["UT"]["boundary_year"], expected_counties=29,
        expected_retained=len(prior), expected_new=len(sources),
        expected_held=29 - len(prior) - len(sources),
        geometry_sha256=sha(reference_body),
        geometry_canonical_sha256=review["geometry"]["UT"]["canonical_sha256"],
        previous_review_sha256=sha(review_body), native_facts_sha256=sha(facts_body),
        reference_repository_path="data/participation-county-bindings/20261111-ut-01/reference.json",
        new_source_ids=[source["id"] for source in sources], complete_download_url=complete)
    args.output.mkdir(parents=True)
    for name, body in {"native-facts.json": facts_body, "reference.json": reference_body,
            "previous-review.json": review_body, "extension.json": encoded(extension),
            "recipe.json": encoded(binding)}.items():
        (args.output / name).write_bytes(body)
    print(json.dumps(dict(status="prepared_explicit_missing_only_successors",
        sources=len(sources), old_counted=len(prior), remaining_holds=binding["expected_held"],
        reference_year=binding["boundary_year"], reference_unchanged=True)))


if __name__ == "__main__":
    main()
