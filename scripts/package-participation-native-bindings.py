"""Package complete held inputs and the exact native-reference migration."""

import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def package(root, dataset, contract, output):
    assert not output.exists()
    runtime = dataset / "runtime"
    descriptor = json.loads((runtime / "dataset.json").read_bytes())
    inputs = json.loads((dataset / "inputs.json").read_bytes())
    members = {"inputs.json": (dataset / "inputs.json").read_bytes(),
        "legacy-reader.js": (dataset / "legacy-reader.js").read_bytes(),
        "runtime/dataset.json": (runtime / "dataset.json").read_bytes(),
        "code/contract.py": contract.read_bytes(),
        "package.json": b'{"type":"module","engines":{"node":">=22.12.0"}}\n'}
    for name, expected in inputs["files"].items():
        body = (root / name).read_bytes()
        assert pin(body) == expected
        members["inputs/" + name] = body
    records = []
    for name, expected in descriptor["files"].items():
        body = (runtime / name).read_bytes()
        assert pin(body) == expected
        members["runtime/" + name] = body
        if name.startswith("counts/"):
            records.extend(json.loads(gzip.decompress(body))["rows"])
        elif name.startswith("tables/"):
            records.extend(json.loads(gzip.decompress(body))["records"])
    spec = importlib.util.spec_from_file_location("frozen", contract)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_all([row["observation"] for row in records])
    members["queries/all-reference-count-queries.json"] = (
        json.dumps(records, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode()
    for relative in (
        "scripts/compile-participation-native-bindings.mjs", "scripts/compile-participation-counts.mjs",
        "scripts/participation-native-bindings.test.mjs", "scripts/participation-counts.test.mjs",
        "scripts/participation-coverage.test.mjs", "scripts/package-participation-native-bindings.py",
        "public/scripts/participation-native-bindings.js", "public/scripts/participation-counts.js",
        "public/scripts/participation-dataset.js", "public/scripts/participation-geography.js",
        "public/scripts/provider-county-scopes.js", "public/scripts/participation-coverage.js",
    ):
        members[relative] = (root / relative).read_bytes()
    members["reproduce.mjs"] = b"""import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compileNativeBindings} from './scripts/compile-participation-native-bindings.mjs';
globalThis.fetch=()=>{throw new Error('Offline reproduction forbids acquisition');};
const result=compileNativeBindings('inputs',readFileSync('legacy-reader.js','utf8'));
const expected=JSON.parse(readFileSync('runtime/dataset.json'));
assert.equal(result.descriptor.version,expected.version);
for(const [file,body]of Object.entries(result.files))
 assert.deepEqual(body,readFileSync('runtime/'+file),file);
console.log(JSON.stringify({status:'PASS_complete_native_binding_runtime_exact',version:expected.version,
 files:Object.keys(result.files).length,layers:Object.keys(result.index.layers).length,
 county_frames:result.index.county_frame_checks,municipal_frames:Object.values(result.index.municipal_bindings).reduce((s,v)=>s+Object.keys(v).length,0),
 acquisitions:0,topology_reductions:0,source_geometry_changed:false}));
"""
    members["reproduce.py"] = b"""import hashlib,importlib.util,json,pathlib,socket,subprocess
root=pathlib.Path(__file__).resolve().parent
manifest=json.loads((root/'manifest.json').read_bytes())
for name,pin in manifest['members'].items():
 body=(root/name).read_bytes()
 assert len(body)==pin['bytes'] and hashlib.sha256(body).hexdigest()==pin['sha256'],name
def stopped(*args,**kwargs):raise RuntimeError('Offline reproduction forbids acquisition')
socket.create_connection=stopped;socket.socket=stopped
spec=importlib.util.spec_from_file_location('contract',root/'code/contract.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
rows=json.loads((root/'queries/all-reference-count-queries.json').read_bytes())
module.validate_all([row['observation'] for row in rows])
process=subprocess.run(['node','reproduce.mjs'],cwd=root,text=True,stdout=subprocess.PIPE,check=True)
result=json.loads(process.stdout)
assert result['version']==manifest['version']
print(json.dumps(dict(status='PASS_full_input_native_binding_reproduction_network_blocked',records=len(rows),
 members_verified=len(manifest['members']),node=result),sort_keys=True))
"""
    members["README.txt"] = b"""COMPLETE NATIVE COUNT / REFERENCE BINDING MIGRATION

Contains every sufficient held input, FULL unchanged native/reference geometry
and complete consumed count tables, all canonical reference/count queries, exact
source-specific legacy checks, original intake contract, maintained compiler,
common validators and focused tests. No original is replaced by a URL inventory.
This transforms already reviewed observations; it does not reacquire sources,
repeat topology campaigns, repair counts or approve new geography.

Counts are separated from fixed reference bytes. Count-only updates can reuse
the same approved hash/key inventory; stale counts embedded in reference files
are ignored. Existing overlaps, excluded strips, partial source scopes, unknowns
and source-specific withheld rates remain. Prior approved reference processing
is preserved literally, not relabeled as an untouched native survey or newly
certified legal boundary. Candidate votes never substitute for participation.
Historical and candidate result readers remain separately reproducible.

Run Python 3.9+ and Node 22.12+, without installation or network:
  python3 reproduce.py
  node --test scripts/participation-native-bindings.test.mjs scripts/participation-coverage.test.mjs

Reproduction checks every member, the original Python count contract, all
source-specific original qualification gates and every runtime file byte-for-byte.
No private respondents, acquisition headers or compiled publisher app included.
Legacy-reader.js is maintained original source used as the qualification oracle.
The source-specific functions are not active in the new browser count reader.
"""
    manifest = dict(contract="participation.native_binding_package.v1",
        version=descriptor["version"], reference_count_queries=len(records),
        members={name: pin(body) for name, body in sorted(members.items())})
    members["manifest.json"] = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, body in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, body, compresslevel=9)
    return dict(status="complete_native_binding_packet_prepared_pending_reproduction",
        **pin(output.read_bytes()), members=len(members), queries=len(records), version=descriptor["version"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "dataset", "contract", "output"):
        parser.add_argument(name, type=Path)
    print(json.dumps(package(**vars(parser.parse_args()))))
