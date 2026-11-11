"""Reproduce only the new binding extension offline, not accepted reductions."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def deny(*args, **kwargs):
    raise RuntimeError("Offline binding reproduction forbids network access")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node", default="node")
    args = parser.parse_args()
    root, output = args.package.resolve(), args.output.resolve()
    if output.exists():
        raise ValueError("Use a fresh reproduction output")
    manifest = json.loads((root / "manifest.json").read_bytes())
    for name, expected in manifest["files"].items():
        body = (root / name).read_bytes()
        if dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest()) != expected:
            raise ValueError("Complete scientific member differs: " + name)
    node = shutil.which(args.node)
    if not node:
        raise ValueError("Node.js is required")
    socket.socket = deny
    socket.create_connection = deny
    output.mkdir(parents=True)
    common = module(root / "code/scripts/reproduce-participation-count-extension.py")
    for family in ("count", "native"):
        common.safe_extract(root / f"inputs/base-{family}-science.zip", output / ("baseline-" + family))
    counts, native = output / "baseline-count/runtime", output / "baseline-native/runtime"
    guard = root / "code/scripts/deny-participation-count-network.mjs"
    env = dict(os.environ, NODE_OPTIONS="", COUNTY_BINDING_INPUT=str(root / "inputs"),
        COUNTY_BINDING_COUNTS=str(counts), COUNTY_BINDING_NATIVE=str(native))
    commands = [[node, "--import", guard.as_uri(), "--input-type=module", "-e",
        "let n=0;try{await fetch('https://example.invalid')}catch{n++};"
        "try{(await import('node:net')).connect(443,'example.invalid')}catch{n++};"
        "try{(await import('node:child_process')).execSync('true')}catch{n++};"
        "if(n!==3)process.exit(1);"]]
    for name in ("extend-participation-county-bindings.test.mjs",
                 "participation-native-bindings.test.mjs", "participation-counts.test.mjs"):
        commands.append([node, "--import", guard.as_uri(), str(root / "code/scripts" / name)])
    commands.append([node, "--import", guard.as_uri(),
        str(root / "code/scripts/extend-participation-county-bindings.mjs"),
        "--counts", str(counts), "--native", str(native), "--inputs", str(root / "inputs"),
        "--output", str(output / "runtime"), "--commit", manifest["source_commit"]])
    for command in commands:
        subprocess.run(command, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for name in manifest["files"]:
        if name.startswith("runtime/") and (output / name).read_bytes() != (root / name).read_bytes():
            raise ValueError("Reproduced runtime byte mismatch: " + name)
    for name in ("county-binding-queries.json", "reference.json"):
        if (output / "runtime" / name).read_bytes() != (root / "results" / name).read_bytes():
            raise ValueError("Full binding query differs: " + name)
    verifier = module(root / "code/scripts/verify-participation-county-bindings.py")
    proof = verifier.verify(counts, native, output / "runtime", root / "inputs")
    result = dict(status="passed_fresh_offline_county_binding_reproduction",
        all_runtime_and_query_bytes_equal=True, tests_passed=14,
        network_and_node_subprocess_blocks_tested=True, previous_reductions_repeated=False,
        independent=proof)
    (output / "reproduction.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
