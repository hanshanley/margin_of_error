"""Complete resident release bundles with preserved science and runtime reproduction."""

import gzip
import json
from pathlib import Path
import zipfile

from .context_package import file_pin, write_complete_archive
from .contract import IntakeError, digest, encoded, pin
from .precinct_package import checked_members, reproduce_precinct_package
from .resident import add_precinct_context


def extract_complete(archive, target):
    target = Path(target)
    target.mkdir()
    with zipfile.ZipFile(archive) as source:
        source.extractall(target)
    return target


def reproduce_resident_dataset(root, full=False):
    root = Path(root)
    manifest = checked_members(root)
    science = extract_complete(root / "originals/complete-precinct-analysis.zip", root / "science-extracted")
    checked_members(science)
    if full:
        reproduce_precinct_package(science)
        county = science / "prior-county-extracted"
    else:
        county = extract_complete(science / "originals/complete-county-context.zip", root / "county-extracted")
        checked_members(county)
    base = json.loads((county / "runtime/dataset.json").read_bytes())
    files = {name: (county / "runtime" / name).read_bytes() for name in base["files"]}
    registry = json.loads((science / "references/registry.json").read_bytes())
    contexts, references, crosswalks = {}, {}, {}
    for code in registry["states"]:
        references[code] = json.loads(gzip.decompress((science / "references" / (code + ".geojson.gz")).read_bytes()))
        contexts[code] = json.loads(gzip.decompress(
            (science / "queries" / (code + "-modeled-resident-context.json.gz")).read_bytes()))
        crosswalks[code] = json.loads(gzip.decompress(
            (science / "queries" / (code + "-population-weights.json.gz")).read_bytes()))
    compiled = add_precinct_context(files, contexts, references, crosswalks)
    description = json.loads((root / "runtime/dataset.json").read_bytes())
    if set(compiled) != set(description["files"]):
        raise IntakeError("package_reproduction", "Runtime resident coverage differs")
    for name, body in compiled.items():
        if body != (root / "runtime" / name).read_bytes():
            raise IntakeError("package_reproduction", "Resident runtime differs: " + name)
        if name.startswith("states/"):
            before = json.loads(gzip.decompress(files[name]))["counties"]
            after = json.loads(gzip.decompress(body))["counties"]
            if before != after:
                raise IntakeError("package_reproduction", "An existing native county profile changed")
    version = digest(encoded(dict(files={name: pin(body) for name, body in sorted(compiled.items())},
        contract=description["record_contract"])))
    if version != description["version"]:
        raise IntakeError("package_reproduction", "Content-addressed runtime version differs")
    index = json.loads(compiled["index.json"])
    return dict(status="PASS_complete_resident_runtime_exact_all_counties_and_local_profiles",
        native_counties=index["complete_native_counties"], conditional_profiles=index["modeled_precincts"],
        jurisdictions=len(index["states"]), runtime_files_exact=len(compiled),
        version=version, complete_members_verified=len(manifest["members"]),
        scientific_inputs_reused=not full, full_science_recomputed=full,
        acquisitions=0, source_geometry_repaired=False)


def package_resident_dataset(runtime_root, science_root, native_intake_archive, native_proof, output):
    runtime, science, output = Path(runtime_root), Path(science_root), Path(output)
    if output.exists():
        raise IntakeError("immutable_package", "Refuse to replace an existing resident dataset packet")
    science_summary = json.loads((science / "packet-summary.json").read_bytes())
    science_archive = science / "complete-analysis.zip"
    if file_pin(science_archive) != {key: science_summary[key] for key in ("bytes", "sha256")}:
        raise IntakeError("package_integrity", "Accepted complete scientific packet changed")
    for attempt in (1, 2):
        proof = json.loads((science / f"offline-reproduction-{attempt:02d}.json").read_bytes())
        if not proof.get("status", "").startswith("PASS") or proof["archive_sha256"] != science_summary["sha256"]:
            raise IntakeError("package_verification", "Both exact scientific reproductions are required")
    native_proof = json.loads(Path(native_proof).read_bytes())
    if not native_proof.get("status", "").startswith("PASS") or file_pin(native_intake_archive) != {
            key: native_proof["complete_download"][key] for key in ("bytes", "sha256")}:
        raise IntakeError("package_verification", "Complete verified direct-intake demonstration is required")
    native_proof.pop("directory", None)
    description = json.loads((runtime / "dataset.json").read_bytes())
    paths = {
        "originals/complete-precinct-analysis.zip": science_archive,
        "originals/complete-native-intake-pilot.zip": Path(native_intake_archive),
        "runtime/dataset.json": runtime / "dataset.json",
        "checks/scientific-reproduction-01.json": science / "offline-reproduction-01.json",
        "checks/scientific-reproduction-02.json": science / "offline-reproduction-02.json",
        "checks/independent-native-points.json": science / "independent-verification.json",
    }
    for name, expected in description["files"].items():
        path = runtime / name
        if file_pin(path) != expected:
            raise IntakeError("context_dataset_integrity", "Frozen resident runtime changed")
        paths["runtime/" + name] = path
    source = Path(__file__).parent
    for path in source.glob("*.py"):
        paths["code/participation_intake/" + path.name] = path
    for path in source.parent.glob("test-participation-*.py"):
        paths["tests/" + path.name] = path
    for path in source.parent.glob("requirements-participation-*.txt"):
        paths[path.name] = path
    paths["requirements.txt"] = source.parent / "requirements-participation-intake.txt"
    bodies = {
        "checks/native-intake-verification.json": encoded(native_proof),
        "README.txt": (
            "COMPLETE RESIDENT DATASET AND INTAKE DEMONSTRATION\n\n"
            "Contains the entire accepted precinct scientific ZIP, including the\n"
            "entire county ZIP and every sufficient original, point query, weight,\n"
            "profile, reference and common analysis routine. Neither earlier ZIP\n"
            "is reduced or replaced by metadata. All runtime shards and the exact\n"
            "compiler source are included, plus the complete native Minnesota\n"
            "direct-intake packet, schema/code and tests. No acquisition headers.\n\n"
            "Fast exact runtime reproduction from accepted scientific inputs:\n"
            "python reproduce.py\n"
            "Full resident raw-input reproduction, including every native ACS\n"
            "block-group cell, counted block page and point/profile calculation:\n"
            "python reproduce.py --full\n"
            "Both run without acquisition. The native count demonstration also\n"
            "has its own complete original/code/query reproduction in its ZIP.\n\n"
            "Context describes residents, not voter composition or group turnout.\n"
            "Conditional proxies retain their 2020/2024/reference-vintage and\n"
            "uniform-composition assumptions; no median averaging or new MOEs.\n"
        ).encode(),
        "reproduce.py": (
            "import argparse,json,pathlib,sys\n"
            "root=pathlib.Path(__file__).resolve().parent\n"
            "sys.path.insert(0,str(root/'code'))\n"
            "from participation_intake.dataset_package import reproduce_resident_dataset\n"
            "parser=argparse.ArgumentParser()\n"
            "parser.add_argument('--full',action='store_true')\n"
            "args=parser.parse_args()\n"
            "print(json.dumps(reproduce_resident_dataset(root,args.full),sort_keys=True))\n"
        ).encode(),
    }
    manifest = dict(contract="geographic.resident_dataset_package.v1",
        dataset_version=description["version"], resident_context_not_voter_data=True,
        scientific_packet_pin=file_pin(science_archive),
        members={**{name: file_pin(path) for name, path in paths.items()},
            **{name: pin(body) for name, body in bodies.items()}})
    bodies["manifest.json"] = encoded(manifest)
    write_complete_archive(output, paths, bodies)
    return dict(status="complete_resident_dataset_packet_prepared_not_yet_reproduced_or_published",
        **file_pin(output), members=len(manifest["members"]) + 1,
        version=description["version"], full_prior_science_preserved=True, metadata_only=False)
