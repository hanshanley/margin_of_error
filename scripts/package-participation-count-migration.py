"""Package complete accepted-export inputs and exact canonical count reproduction."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode()


def package(root, legacy_source, backend_contract, verification, native_verification, output):
    if output.exists():
        raise ValueError("Refuse to replace an immutable complete count migration")
    data = root / "data/participation-counts/20261110-02"
    runtime = data / "runtime"
    metadata = json.loads((data / "inputs.json").read_bytes())
    descriptor = json.loads((runtime / "dataset.json").read_bytes())
    proof = json.loads(verification.read_bytes())
    native = json.loads(native_verification.read_bytes())
    assert proof["version"] == descriptor["version"] and len(proof["cases"]) == 306
    assert native["records"] == proof["retained_source_appearances_not_people"]
    members = {"inputs.json": (data / "inputs.json").read_bytes(),
        "runtime/dataset.json": (runtime / "dataset.json").read_bytes(),
        "checks/accepted-reader-306-cases.json": verification.read_bytes(),
        "checks/frozen-python-contract.json": native_verification.read_bytes(),
        "code/participation_intake/contract.py": backend_contract.read_bytes(),
        "package.json": encoded(dict(type="module", engines=dict(node=">=22.12.0")))}
    for file, expected in metadata["inputs"].items():
        body = (data / "inputs" / file).read_bytes()
        assert pin(body) == {key: expected[key] for key in ("bytes", "sha256")}
        members["inputs/" + file] = body
    records = []
    for file, expected in descriptor["files"].items():
        body = (runtime / file).read_bytes()
        assert pin(body) == expected
        members["runtime/" + file] = body
        if file.startswith("states/"):
            records.extend(json.loads(gzip.decompress(body))["records"])
    columns = ["id", "election", "geography", "measure", "count", "denominator",
        "source_clock", "reporting_status", "source", "quality", "view"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows({key: json.dumps(row[key], sort_keys=True, ensure_ascii=True)
        if isinstance(row[key], (dict, list)) else row[key] for key in columns} for row in records)
    members["queries/all-observations.csv"] = buffer.getvalue().encode()
    for relative in (
        "scripts/compile-participation-counts.mjs", "scripts/verify-participation-count-migration.mjs",
        "scripts/verify-participation-count-contract.py", "scripts/participation-counts.test.mjs",
        "scripts/package-participation-count-migration.py",
        "public/scripts/participation-counts.js", "public/scripts/participation-dataset.js",
        "public/scripts/participation-geography.js", "public/scripts/provider-county-scopes.js",
    ):
        members[relative] = (root / relative).read_bytes()
    legacy = legacy_source.read_text()
    start = legacy.index("    const additionalLocal = new Map();")
    end = legacy.index("    const electorateLabel", start)
    members["legacy/accepted-count-reader.js"] = (
        "// Maintained source data-selector excerpt, not compiled publisher application code.\n"
        + legacy[start:legacy.index("\n", end) + 1]).encode()
    members["reproduce.mjs"] = b"""import {readFileSync} from "node:fs";
import {verifyMigration} from "./scripts/verify-participation-count-migration.mjs";
globalThis.fetch=()=>{throw new Error("Offline reproduction forbids acquisition");};
const result=await verifyMigration(".",readFileSync("legacy/accepted-count-reader.js","utf8"),"runtime");
console.log(JSON.stringify({status:result.status,version:result.version,records:result.retained_source_appearances_not_people,cases:result.cases.length,exact_runtime_files:result.exact_runtime_files}));
"""
    members["reproduce.py"] = b"""import hashlib,json,pathlib,socket,subprocess,sys
root=pathlib.Path(__file__).resolve().parent
manifest=json.loads((root/'manifest.json').read_bytes())
for name,pin in manifest['members'].items():
 body=(root/name).read_bytes()
 assert len(body)==pin['bytes'] and hashlib.sha256(body).hexdigest()==pin['sha256'],name
def stopped(*args,**kwargs): raise RuntimeError('Offline reproduction forbids acquisition')
socket.create_connection=stopped
socket.socket=stopped
sys.path.insert(0,str(root/'scripts'))
from importlib.util import spec_from_file_location,module_from_spec
spec=spec_from_file_location('verifier',root/'scripts/verify-participation-count-contract.py')
module=module_from_spec(spec);spec.loader.exec_module(module)
native=module.verify(root/'runtime',root/'code/participation_intake/contract.py')
assert native['records']==manifest['retained_source_appearances_not_people']
process=subprocess.run(['node','reproduce.mjs'],cwd=root,text=True,stdout=subprocess.PIPE,check=True)
result=json.loads(process.stdout)
assert result['version']==manifest['dataset_version'] and result['cases']==306
print(json.dumps(dict(status='PASS_complete_count_migration_network_blocked',members_verified=len(manifest['members']),python_contract=native,node_reproduction=result),sort_keys=True))
"""
    members["README.txt"] = b"""COMPLETE ACCEPTED-EXPORT COUNT MIGRATION

This is a one-time migration of previously accepted public aggregate observations,
not new source acquisition, source parsing, boundary qualification or causal work.
Contains EVERY accepted aggregate input consumed: full base query, all 49 full
additional state gzip exports, all reviewed county/state rows, the complete
current state/provider aggregate snapshot and the exact context pointer.
Every retained source appearance has a full canonical query, including original
fields, unknowns, withheld counts, observed zeros, clocks and source qualifications.
All six existing view selections (including the separate UF context selections)
are explicit non-additive bindings. Held source-region queries remain complete.
Source appearances/partitions are not distinct people and must never be summed.
Native conflicts are retained, not newly adjudicated or repaired.

The original raw-source and geographic science remains in the unchanged immutable
complete downloads linked by each accepted export. None of it was re-parsed or
used to approve new geography in this transformation. This archive contains all
sufficient inputs to reproduce THIS migration, not merely an input inventory.
No private respondents, acquisition headers or compiled publisher app are included.

Use Python 3.9+ and Node 22.12+; no package installation or network is required:
  python3 reproduce.py
  node --test scripts/participation-counts.test.mjs

Reproduction verifies every member, checks every observation using the
original frozen Python contract, reconstructs all runtime files byte-for-byte,
and compares every field in all 306 state/view cases against the actual accepted
data-selector source. Runtime ZIPs/queries preserve all known and held data.
"""
    manifest = dict(contract="participation.count_migration_package.v1",
        dataset_version=descriptor["version"],
        retained_source_appearances_not_people=len(records),
        source_export_revision=metadata["source_export_revision"],
        accepted_selector_full_source_sha256=hashlib.sha256(legacy_source.read_bytes()).hexdigest(),
        members={name: pin(body) for name, body in sorted(members.items())})
    members["manifest.json"] = encoded(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, body in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, body, compresslevel=9)
    return dict(status="complete_count_migration_prepared_not_yet_reproduced_or_published",
        **pin(output.read_bytes()), members=len(members), version=descriptor["version"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "legacy_source", "backend_contract", "verification", "native_verification", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(package(**vars(args))))
