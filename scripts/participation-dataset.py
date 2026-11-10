"""Freeze a canonical dataset for independent, hash-checked data publication."""

import argparse
import json
from pathlib import Path

from participation_intake.contract import encoded, digest, pin
from participation_intake.resident import build_county_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-context", type=Path, required=True)
    parser.add_argument("--county-identities", type=Path, required=True)
    parser.add_argument("--geometry-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files, report = build_county_files(args.native_context, args.county_identities, args.geometry_root)
    recipe = digest(encoded(dict(files={name: pin(body) for name, body in sorted(files.items())},
        contract="geographic.resident_context.v1")))
    descriptor = dict(contract="participation.dataset.v1", id="resident-context",
        version=recipe, record_contract="geographic.resident_context.v1",
        index=dict(file="index.json", **pin(files["index.json"])),
        files={name: pin(body) for name, body in sorted(files.items())},
        status="awaiting_publication", complete_download=None)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, body in files.items():
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    (args.output / "dataset.json").write_bytes(encoded(descriptor))
    (args.output / "compilation.json").write_bytes(encoded(report))
    print(json.dumps(dict(id=descriptor["id"], version=recipe,
        files=len(files), runtime_bytes=sum(len(body) for body in files.values()),
        county_contexts=json.loads(files["index.json"])["complete_native_counties"])))


if __name__ == "__main__":
    main()
