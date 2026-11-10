"""Complete conditional resident packages, retaining originals and every decision."""

import gzip
import json
from pathlib import Path
import sqlite3
import zipfile

from .acs_context import TABLES
from .arcgis import aggregate_query
from .context_package import file_pin, reproduce_county_package, write_complete_archive
from .contract import IntakeError, encoded, pin
from .crosswalk import population_weights
from .precinct_context import estimate_context
from .resident import compressed
from .small_area import block_group_rows


def checked_members(root):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_bytes())
    for name, declaration in manifest["members"].items():
        if file_pin(root / name) != declaration:
            raise IntakeError("package_integrity", "Changed complete-package member: " + name)
    return manifest


def verify_native_index(source_store, database):
    connection = sqlite3.connect("file:" + str(Path(database).resolve()) + "?mode=ro", uri=True)
    counts = {}
    try:
        for table in TABLES:
            receipt = json.loads((Path(source_store) / (table + "-receipt.json")).read_bytes())
            source = Path(source_store) / "objects" / receipt["sha256"]
            if file_pin(source) != {key: receipt[key] for key in ("bytes", "sha256")}:
                raise IntakeError("context_original_integrity", "Native source changed: " + table)
            count = 0
            for geoid, pairs in block_group_rows(source, table):
                row = connection.execute(
                    "SELECT native_pairs FROM cells WHERE geoid=? AND table_id=?", (geoid, table)).fetchone()
                if row is None or json.loads(row[0]) != pairs:
                    raise IntakeError("context_index_integrity", "Native index differs from original ACS cells")
                count += 1
            if count != connection.execute("SELECT COUNT(*) FROM cells WHERE table_id=?", (table,)).fetchone()[0]:
                raise IntakeError("context_index_integrity", "Native index has unmatched identities")
            counts[table] = count
    finally:
        connection.close()
    return counts


def reproduce_precinct_package(root):
    root = Path(root)
    manifest = checked_members(root)
    prior = root / "prior-county-extracted"
    prior.mkdir()
    with zipfile.ZipFile(root / "originals/complete-county-context.zip") as archive:
        archive.extractall(prior)
    county = reproduce_county_package(prior)
    database = root / "queries/native-block-group-cells.sqlite3"
    native_counts = verify_native_index(prior / "source-store", database)
    registry = json.loads((root / "references/registry.json").read_bytes())
    results = {}
    for code, declaration in sorted(registry["states"].items()):
        state_root = root / "originals/blocks" / declaration["state_fips"]
        expected_blocks = json.loads((state_root / "complete-query.json").read_bytes())
        records, _ = aggregate_query(expected_blocks["acquisition"]["source"], state_root)
        if records != expected_blocks["records"]:
            raise IntakeError("package_reproduction", "Native counted block pages differ")
        raw_reference = (root / "references" / (code + ".geojson.gz")).read_bytes()
        if pin(raw_reference) != {key: declaration[key] for key in ("bytes", "sha256")}:
            raise IntakeError("context_reference", "Pinned unrepaired reference differs")
        points = root / ("reproduced-" + code + "-complete-point-decisions.jsonl.gz")
        with points.open("xb") as target, gzip.GzipFile(
                fileobj=target, mode="wb", mtime=0, filename="") as stream:
            def write_point(row):
                stream.write(encoded(row))
            crosswalk = population_weights(json.loads(gzip.decompress(raw_reference))["features"],
                records, code, declaration["state_fips"], point_query_writer=write_point)
        crosswalk["complete_point_query"] = dict(file=code + "-complete-point-decisions.jsonl.gz", **file_pin(points))
        crosswalk["source_reference"] = {key: value for key, value in declaration.items() if key != "file"}
        crosswalk["source_block_query"] = file_pin(state_root / "complete-query.json")
        expected_crosswalk = root / "queries" / (code + "-population-weights.json.gz")
        if compressed(encoded(crosswalk)) != expected_crosswalk.read_bytes():
            raise IntakeError("package_reproduction", "Complete source weights differ: " + code)
        if points.read_bytes() != (root / "queries" / crosswalk["complete_point_query"]["file"]).read_bytes():
            raise IntakeError("package_reproduction", "Full point query differs: " + code)
        context = estimate_context(crosswalk, database)
        context["source_reference"] = crosswalk["source_reference"]
        context["source_native_block_group_database"] = registry["native_block_group_database"]
        if compressed(encoded(context)) != (root / "queries" / (code + "-modeled-resident-context.json.gz")).read_bytes():
            raise IntakeError("package_reproduction", "Conditional resident profiles differ: " + code)
        results[code] = dict(records=len(context["records"]), blocks=len(records),
            held_references=len(crosswalk["held_references"]), all_weight_and_profile_bytes_exact=True)
    return dict(status="PASS_complete_precinct_context_native_inputs_all_points_and_profiles",
        states=results, county_reproduction=county, native_block_groups_per_table=native_counts,
        members_verified=len(manifest["members"]), acquisition_requests=0,
        source_geometry_repaired=False, source_geometry_reacquired=False)


def package_precinct_context(results_root, site_root, blocks_root, database, county_packet,
                             county_verification, verification, verifier, output):
    results, site, blocks = Path(results_root), Path(site_root), Path(blocks_root)
    output, database, county_packet = Path(output), Path(database), Path(county_packet)
    if output.exists():
        raise IntakeError("immutable_package", "Refuse to replace an existing precinct package")
    summary = json.loads((results / "summary.json").read_bytes())
    registry = summary["reference_registry"]
    proof = json.loads(Path(verification).read_bytes())
    if not registry.get("states") or not proof.get("status", "").startswith("PASS") or proof["records"] != sum(
            state["records"] for state in summary["states"].values()):
        raise IntakeError("context_verification", "Full native-point acceptance is required")
    if file_pin(database) != registry["native_block_group_database"]:
        raise IntakeError("context_database", "Qualified native source index changed")
    county_proof = json.loads(Path(county_verification).read_bytes())
    county_pin = county_proof.get("assets", {}).get("complete-analysis.zip", {})
    if not county_proof.get("immutable") or not county_pin.get("verified_anonymously") or file_pin(
            county_packet) != {key: county_pin.get(key) for key in ("bytes", "sha256")}:
        raise IntakeError("context_original_integrity", "Accepted complete county input differs")
    paths = {
        "originals/complete-county-context.zip": county_packet,
        "queries/native-block-group-cells.sqlite3": database,
        "queries/summary.json": results / "summary.json",
        "checks/independent-verification.json": Path(verification),
        "checks/verify-native-points.py": Path(verifier),
        "references/county-science-verification.json": Path(county_verification),
    }
    for code, declaration in registry["states"].items():
        if file_pin(site / declaration["file"]) != {
                key: declaration[key] for key in ("bytes", "sha256")}:
            raise IntakeError("context_reference", "Pinned unrepaired reference changed")
        accepted = summary["states"][code]
        for suffix, key in (("population-weights.json.gz", "crosswalk"),
                            ("modeled-resident-context.json.gz", "context")):
            if file_pin(results / (code + "-" + suffix)) != accepted[key]:
                raise IntakeError("context_query_integrity", "Accepted conditional queries changed")
        crosswalk = json.loads(gzip.decompress((results / (code + "-population-weights.json.gz")).read_bytes()))
        if file_pin(results / crosswalk["complete_point_query"]["file"]) != {
                key: crosswalk["complete_point_query"][key] for key in ("bytes", "sha256")}:
            raise IntakeError("context_query_integrity", "Complete point decisions changed")
        paths["references/" + code + ".geojson.gz"] = site / declaration["file"]
        index_file = declaration["approval_evidence"].get("index_file")
        if index_file:
            paths["references/" + code + "-source-index.json"] = site / index_file
        for suffix in ("population-weights.json.gz", "complete-point-decisions.jsonl.gz",
                       "modeled-resident-context.json.gz", "summary.json"):
            paths["queries/" + code + "-" + suffix] = results / (code + "-" + suffix)
        state_root = blocks / declaration["state_fips"]
        complete = state_root / "complete-query.json"
        if file_pin(complete) != crosswalk["source_block_query"]:
            raise IntakeError("context_original_integrity", "Accepted complete block query changed")
        acquisition = json.loads(complete.read_bytes())["acquisition"]
        if acquisition["status"] != "complete_public_aggregate_query":
            raise IntakeError("context_original_integrity", "Incomplete native block query")
        prefix = "originals/blocks/" + declaration["state_fips"] + "/"
        paths[prefix + "complete-query.json"] = complete
        available = {}
        for path in state_root.glob("*-receipt.json"):
            receipt = json.loads(path.read_bytes())
            available[(receipt["url"], receipt["sha256"])] = path
        for receipt in acquisition["receipts"]:
            if any("header" in key.lower() or "cookie" in key.lower() for key in receipt):
                raise IntakeError("context_receipt", "Acquisition headers are not public")
            original = state_root / "objects" / receipt["sha256"]
            if file_pin(original) != {key: receipt[key] for key in ("bytes", "sha256")}:
                raise IntakeError("context_original_integrity", "Complete native block original changed")
            paths[prefix + "objects/" + receipt["sha256"]] = original
            receipt_path = available[(receipt["url"], receipt["sha256"])]
            paths[prefix + receipt_path.name] = receipt_path
    source = Path(__file__).parent
    for path in source.glob("*.py"):
        paths["code/participation_intake/" + path.name] = path
    for path in source.parent.glob("test-participation-*.py"):
        paths["tests/" + path.name] = path
    for path in source.parent.glob("requirements-participation-*.txt"):
        paths[path.name] = path
    paths["requirements.txt"] = source.parent / "requirements-participation-intake.txt"
    bodies = {
        "references/registry.json": encoded(registry),
        "README.txt": (
            "COMPLETE CONDITIONAL LOCAL RESIDENT CONTEXT\n\n"
            "Includes the entire accepted complete county packet with all five full\n"
            "ACS originals and Gazetteer, every selected Census block count/page\n"
            "original and full query, the full qualified factual block-group index,\n"
            "unchanged reference geometry, every block decision/weight/profile,\n"
            "independent checks and maintained common code/tests/toolchain pins.\n"
            "No acquisition headers, respondent files or compiled publisher apps.\n\n"
            "Install the pinned requirements-participation-context.txt if needed.\n"
            "Extract, then run: python reproduce.py\n"
            "Reproduction validates all members, the entire prior county packet,\n"
            "every block-group cell against all five full ACS originals, native\n"
            "block pages/count controls and exact complete point/weight/profile\n"
            "bytes. No acquisition or geometry repair. The prior county ZIP is\n"
            "included in full, not replaced by a pointer or a sample.\n\n"
            "2020 population and housing-unit proxies approximate distribution.\n"
            "2020/2024 block-group code equivalence and within-group composition\n"
            "are assumptions, not geographic certification. Housing units are not\n"
            "occupied households. Income medians are intervals from weighted bins,\n"
            "never averaged medians. No new MOE/CI, voter profile or group turnout.\n"
        ).encode(),
        "reproduce.py": (
            "import json,pathlib,sys\n"
            "root=pathlib.Path(__file__).resolve().parent\n"
            "sys.path.insert(0,str(root/'code'))\n"
            "from participation_intake.precinct_package import reproduce_precinct_package\n"
            "print(json.dumps(reproduce_precinct_package(root),sort_keys=True))\n"
        ).encode(),
    }
    manifest = dict(contract="geographic.conditional_resident_context_package.v1",
        reference_families=len(registry["states"]), records=proof["records"],
        complete_point_decisions=proof["point_decisions"],
        members={**{name: file_pin(path) for name, path in paths.items()},
            **{name: pin(body) for name, body in bodies.items()}})
    bodies["manifest.json"] = encoded(manifest)
    write_complete_archive(output, paths, bodies)
    return dict(status="complete_precinct_packet_prepared_not_yet_reproduced_or_published",
        **file_pin(output), members=len(manifest["members"]) + 1,
        records=proof["records"], complete_point_decisions=proof["point_decisions"],
        prior_county_packet_preserved_in_full=True, metadata_only=False)
