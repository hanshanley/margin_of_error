"""Estimate resident context for a registry of held approved display references."""

import argparse
import gzip
import json
from pathlib import Path

from participation_intake.context_package import file_pin
from participation_intake.contract import IntakeError, encoded, pin
from participation_intake.crosswalk import population_weights
from participation_intake.precinct_context import estimate_context
from participation_intake.resident import compressed


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--references", type=Path, required=True)
parser.add_argument("--site-root", type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument("--blocks-root", type=Path, required=True)
parser.add_argument("--database", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
registry = json.loads(args.references.read_bytes())
if registry.get("contract") != "resident.approved_reference_registry.v1":
    raise IntakeError("context_registry", "Unknown reference registry")
if file_pin(args.database) != registry["native_block_group_database"]:
    raise IntakeError("context_database", "Qualified native source cells changed")
args.output.mkdir(parents=True, exist_ok=False)
summaries = {}
for code, declaration in sorted(registry["states"].items()):
    reference = args.site_root / declaration["file"]
    body = reference.read_bytes()
    if pin(body) != {key: declaration[key] for key in ("bytes", "sha256")}:
        raise IntakeError("context_reference", "Held approved reference changed: " + code)
    if not declaration.get("approval_evidence"):
        raise IntakeError("context_reference", "A checksum is not reference approval")
    features = json.loads(gzip.decompress(body))["features"]
    if len(features) != declaration["expected_features"]:
        raise IntakeError("context_reference", "Held approved reference coverage changed")
    blocks = json.loads((args.blocks_root / declaration["state_fips"] / "complete-query.json").read_bytes())
    points_path = args.output / (code + "-complete-point-decisions.jsonl.gz")
    with points_path.open("xb") as target, gzip.GzipFile(
            fileobj=target, mode="wb", mtime=0, filename="") as stream:
        def write_point(row):
            stream.write(encoded(row))
        crosswalk = population_weights(features, blocks["records"], code, declaration["state_fips"],
            point_query_writer=write_point)
    crosswalk["complete_point_query"] = dict(file=points_path.name, **file_pin(points_path))
    crosswalk["source_reference"] = {key: value for key, value in declaration.items() if key != "file"}
    crosswalk["source_block_query"] = file_pin(
        args.blocks_root / declaration["state_fips"] / "complete-query.json")
    crosswalk_path = args.output / (code + "-population-weights.json.gz")
    crosswalk_path.write_bytes(compressed(encoded(crosswalk)))
    result = estimate_context(crosswalk, args.database)
    result["source_reference"] = crosswalk["source_reference"]
    result["source_native_block_group_database"] = registry["native_block_group_database"]
    context_path = args.output / (code + "-modeled-resident-context.json.gz")
    context_path.write_bytes(compressed(encoded(result)))
    summary = dict(
        status="computed_conditional_resident_context_not_yet_independently_verified_or_live",
        records=len(result["records"]), reference_features=len(features),
        held_reference_features=len(crosswalk["held_references"]),
        population_estimates=sum(row["resident_population"]["estimate"] is not None for row in result["records"]),
        income_bands=sum(row["modeled_income_median_band"] is not None for row in result["records"]),
        missing_BG_holds=sum(bool(row["missing_2024_block_groups"]) for row in result["records"]),
        complete_population=crosswalk["complete_population"],
        complete_housing_units=crosswalk["complete_housing_units"],
        point_decisions=crosswalk["point_decisions"], source_geometry_repaired=False,
        counts_allocated=False, original_acquisitions=0,
        crosswalk=pin(crosswalk_path.read_bytes()), context=pin(context_path.read_bytes()))
    (args.output / (code + "-summary.json")).write_bytes(encoded(summary))
    summaries[code] = summary
    print(json.dumps(dict(state=code, **summary)), flush=True)
(args.output / "summary.json").write_bytes(encoded(dict(
    status="computed_conditional_reference_context_not_yet_published",
    states=summaries, reference_registry=registry, whole_project_complete=False)))
