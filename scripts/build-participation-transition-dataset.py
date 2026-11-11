"""Freeze the released conditional-scenario viewer for independent data publication."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path


SOURCE_SHA = "db104e263ff4616d69505f1f916ae08e8e8ff1e1dac90985aca434c6f6a5cdeb"
RELEASE = "https://github.com/hanshanley/margin_of_error/releases/download/participation-transition-simulation-20261111-01/"
CONTRACT = "participation.transition_scenarios.v1"


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False) + "\n").encode()


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viewer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze-source", type=Path)
    args = parser.parse_args()
    body = args.viewer.read_bytes()
    if pin(body)["sha256"] != SOURCE_SHA:
        raise ValueError("Use the exact reviewed immutable scientific viewer")
    data = json.loads(body)
    if data["status"] != "conditional_source_frame_scenarios_not_population_validated" \
            or len(data["state_scenarios"]) != 50 or len(data["complete_demographic_decisions"]) != 1530:
        raise ValueError("Changed source-frame inventory or qualification")
    compressed = gzip.compress(body, compresslevel=9, mtime=0)
    index = dict(contract=CONTRACT, source_viewer_sha256=SOURCE_SHA,
        source_release=RELEASE, source_commit="ddfabf759bd8c7ee2e9e48637260d07c6bdd740c",
        viewer=dict(file="viewer-data.json.gz", **pin(compressed)),
        source_states=50, complete_demographic_decisions=1530,
        conditional_source_frame=True, population_transport_validated=False,
        local_allocation=False)
    files = {"index.json": encoded(index), "viewer-data.json.gz": compressed}
    pins = {name: pin(value) for name, value in sorted(files.items())}
    version = pin(encoded(dict(files=pins, contract=CONTRACT)))["sha256"]
    descriptor = dict(contract="participation.dataset.v1", id="transition-scenarios-2026",
        version=version, record_contract=CONTRACT, status="awaiting_publication",
        index=dict(file="index.json", **pins["index.json"]), files=pins,
        complete_download=dict(url=RELEASE + "complete-analysis.zip", bytes=9977891,
            sha256="422d14209bc6be35919e95a5b69aee6af58e9721c095453bf343139f59f883a2",
            verified_anonymously=True, immutable=True, release_id=441189732, members=20))
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in files.items():
        (args.output / name).write_bytes(value)
    (args.output / "dataset.json").write_bytes(encoded(descriptor))
    if args.freeze_source:
        args.freeze_source.mkdir(parents=True, exist_ok=False)
        (args.freeze_source / "viewer-data.json").write_bytes(body)
        (args.freeze_source / "publication.json").write_bytes(encoded(dict(
            source_viewer=pin(body), dataset_version=version, complete_download=descriptor["complete_download"])))
    print(json.dumps(dict(id=descriptor["id"], version=version,
        runtime_files=len(files), runtime_bytes=sum(len(value) for value in files.values()),
        public_complete_archive_bytes=9977891)))


if __name__ == "__main__":
    main()
