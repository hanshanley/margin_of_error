"""Complete, deterministic county-context packages using held public originals."""

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile

from .acs_context import TABLES, build_county_context
from .contract import IntakeError, digest, encoded, pin
from .resident import compile_counties


def file_pin(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return dict(bytes=Path(path).stat().st_size, sha256=checksum.hexdigest())


def gazetteer_identities(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != 1 or not names[0].endswith(".txt"):
            raise IntakeError("context_identity_original", "Expected one complete native Gazetteer table")
        text = archive.read(names[0]).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    return [{key.strip(): value.strip() for key, value in row.items()} for row in reader]


def reproduce_county_package(root):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_bytes())
    for name, expected in manifest["members"].items():
        if file_pin(root / name) != expected:
            raise IntakeError("package_integrity", "Changed complete-package member: " + name)
    identities = json.loads(gzip.decompress((root / "references/county-identities.json.gz").read_bytes()))
    if gazetteer_identities(root / "originals/gazetteer-counties.zip") != identities:
        raise IntakeError("context_identity_original", "Derived county identities differ from the complete native original")
    native = build_county_context(root / "source-store")
    expected = json.loads(gzip.decompress((root / "queries/county-native-context.json.gz").read_bytes()))
    if native != expected:
        raise IntakeError("package_reproduction", "Native county query differs from complete original tables")
    geometries = {name.split("-")[-1].split(".")[0]: json.loads((root / name).read_bytes())
        for name in manifest["members"] if name.startswith("references/geometry/county-")}
    files = compile_counties(native, identities, geometries)
    description = json.loads((root / "runtime/dataset.json").read_bytes())
    if set(files) != set(description["files"]):
        raise IntakeError("package_reproduction", "Runtime county coverage differs")
    for name, body in files.items():
        if body != (root / "runtime" / name).read_bytes():
            raise IntakeError("package_reproduction", "Runtime context differs: " + name)
    return dict(status="PASS_complete_native_and_runtime_county_reproduction",
        counties=len(native["records"]), states=len(geometries),
        complete_originals=len(TABLES) + 1, all_members_verified=len(manifest["members"]),
        native_query_exact=True, runtime_files_exact=len(files), acquisition_requests=0,
        geometry_preparations=0, voter_characteristics_inferred=False)


def package_county_context(source_store, native_query, county_reference, dataset_root, output,
                          geometry_root=None, verification=None, verifier=None):
    store, query = Path(source_store), Path(native_query)
    references, dataset, output = Path(county_reference), Path(dataset_root), Path(output)
    geometry_root = Path(geometry_root) if geometry_root is not None else references
    if output.exists():
        raise IntakeError("immutable_package", "Refuse to replace an existing context package")
    description = json.loads((dataset / "dataset.json").read_bytes())
    compilation = json.loads((dataset / "compilation.json").read_bytes())
    if file_pin(query) != compilation["native_query"]:
        raise IntakeError("context_query_integrity", "Frozen native context changed")
    if description["version"] != digest(encoded(dict(files=description["files"],
            contract=description["record_contract"]))):
        raise IntakeError("context_dataset_integrity", "Runtime dataset identity differs")
    paths = {"queries/county-native-context.json.gz": query,
        "references/county-identities.json.gz": references / "complete-2024-county-identities.json.gz",
        "originals/gazetteer-counties.zip": references / "gazetteer-2024-national-counties.zip",
        "runtime/dataset.json": dataset / "dataset.json",
        "runtime/compilation.json": dataset / "compilation.json"}
    if file_pin(paths["references/county-identities.json.gz"]) != compilation["county_identity_original"]:
        raise IntakeError("context_identity_integrity", "Held complete county identities changed")
    for name, expected in compilation["approved_geometry"].items():
        path = geometry_root / name
        if file_pin(path) != expected:
            raise IntakeError("context_geometry_integrity", "Held approved county geometry changed: " + name)
        paths["references/" + name] = path
    for table in TABLES:
        receipt = store / (table + "-receipt.json")
        declaration = json.loads(receipt.read_bytes())
        path = store / "objects" / declaration["sha256"]
        if file_pin(path) != {key: declaration[key] for key in ("bytes", "sha256")}:
            raise IntakeError("context_original_integrity", "Complete public ACS original changed: " + table)
        if any("header" in key.lower() or "cookie" in key.lower() for key in declaration):
            raise IntakeError("context_receipt", "Acquisition headers are not public package inputs")
        paths["source-store/" + receipt.name] = receipt
        paths["source-store/objects/" + declaration["sha256"]] = path
    for name, expected in description["files"].items():
        path = dataset / name
        if file_pin(path) != expected:
            raise IntakeError("context_dataset_integrity", "Frozen runtime file changed: " + name)
        paths["runtime/" + name] = path
    source = Path(__file__).parent
    for path in sorted(source.glob("*.py")):
        paths["code/participation_intake/" + path.name] = path
    test_root = source.parent if (source.parent / "test-participation-intake.py").exists() else source.parent.parent / "tests"
    for path in sorted(test_root.glob("test-participation-*.py")):
        paths["tests/" + path.name] = path
    requirements = source.parent / "requirements-participation-intake.txt"
    paths["requirements.txt"] = requirements if requirements.exists() else source.parent.parent / "requirements.txt"
    if verification is not None or verifier is not None:
        if verification is None or verifier is None:
            raise IntakeError("context_verification", "Supply the independent verifier and its complete proof")
        proof = json.loads(Path(verification).read_bytes())
        if not proof.get("status", "").startswith("PASS") or proof.get("native_query_sha256") != file_pin(query)["sha256"]:
            raise IntakeError("context_verification", "Independent county verification does not match this query")
        paths["checks/independent-native-verification.json"] = Path(verification)
        paths["checks/verify-native.py"] = Path(verifier)
    bodies = {
        "README.txt": (
            "COMPLETE COUNTY RESIDENT CONTEXT\n\n"
            "All five complete public 2020-2024 ACS table originals, the complete\n"
            "2024 Gazetteer original, all county identity queries and 51 approved\n"
            "unrepaired references, full native/runtime queries, maintained common\n"
            "code/tests and checksums are included. No acquisition headers.\n\n"
            "Extract, then run: python reproduce.py\n"
            "Reproduction validates every member, rebuilds every native county\n"
            "cell from the full originals, checks Gazetteer identities and requires\n"
            "byte-identical runtime files. It makes no source requests.\n\n"
            "The independent checker, when included, can also run offline:\n"
            "python checks/verify-native.py --source-store source-store\n"
            "  --query queries/county-native-context.json.gz --runtime runtime\n"
            "  --output independent-recheck.json\n\n"
            "Resident composition is not voter composition or group turnout.\n"
            "Native MOEs, special values and source years remain explicit.\n"
            "No new precinct estimates, averaged medians or derived MOEs.\n"
        ).encode(),
        "reproduce.py": (
            "import json,pathlib,sys\n"
            "root=pathlib.Path(__file__).resolve().parent\n"
            "sys.path.insert(0,str(root/'code'))\n"
            "from participation_intake.context_package import reproduce_county_package\n"
            "print(json.dumps(reproduce_county_package(root),sort_keys=True))\n"
        ).encode(),
    }
    manifest = dict(contract="geographic.resident_context_package.v1",
        dataset_version=description["version"], resident_context_not_voter_data=True,
        members={**{name: file_pin(path) for name, path in paths.items()},
            **{name: pin(body) for name, body in bodies.items()}})
    bodies["manifest.json"] = encoded(manifest)
    write_complete_archive(output, paths, bodies)
    return dict(status="complete_county_context_packet_prepared_not_yet_reproduced_or_published",
        **file_pin(output), members=len(manifest["members"]) + 1,
        complete_original_bytes=sum(json.loads((store / (table + "-receipt.json")).read_bytes())["bytes"]
            for table in TABLES),
        dataset_version=description["version"], metadata_only=False)


def write_complete_archive(output, paths, bodies):
    output = Path(output)
    if output.exists():
        raise IntakeError("immutable_package", "Refuse to replace an existing complete package")
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        archive = zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6)
        created = True
        with archive:
            for name in sorted(set(paths) | set(bodies)):
                entry = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o644 << 16
                with archive.open(entry, "w") as target:
                    if name in bodies:
                        target.write(bodies[name])
                    else:
                        with paths[name].open("rb") as stream:
                            shutil.copyfileobj(stream, target, 1024 * 1024)
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise
