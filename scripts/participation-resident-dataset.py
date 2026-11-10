"""Extend frozen county runtime files with accepted conditional local profiles."""

import argparse
import gzip
import json
from pathlib import Path

from participation_intake.contract import IntakeError, digest, encoded, pin
from participation_intake.resident import add_precinct_context


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-dataset", type=Path, required=True)
parser.add_argument("--contexts", type=Path, required=True)
parser.add_argument("--site-root", type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
base = json.loads((args.base_dataset / "dataset.json").read_bytes())
files = {}
for name, expected in base["files"].items():
    body = (args.base_dataset / name).read_bytes()
    if pin(body) != expected:
        raise IntakeError("context_dataset_integrity", "Frozen county runtime file changed")
    files[name] = body
proof = json.loads((args.contexts / "independent-verification.json").read_bytes())
if not proof.get("status", "").startswith("PASS"):
    raise IntakeError("context_verification", "Independent local context acceptance is required")
summary = json.loads((args.contexts / "summary.json").read_bytes())
contexts, references, crosswalks = {}, {}, {}
for code, declaration in summary["reference_registry"]["states"].items():
    raw = (args.site_root / declaration["file"]).read_bytes()
    if pin(raw) != {key: declaration[key] for key in ("bytes", "sha256")}:
        raise IntakeError("context_reference", "Pinned context reference changed")
    references[code] = json.loads(gzip.decompress(raw))
    for suffix, target, key in (
        ("modeled-resident-context", contexts, "context"),
        ("population-weights", crosswalks, "crosswalk"),
    ):
        body = (args.contexts / (code + "-" + suffix + ".json.gz")).read_bytes()
        if pin(body) != summary["states"][code][key]:
            raise IntakeError("context_query_integrity", "Accepted local context query changed")
        target[code] = json.loads(gzip.decompress(body))
files = add_precinct_context(files, contexts, references, crosswalks)
pins = {name: pin(body) for name, body in sorted(files.items())}
description = dict(contract="participation.dataset.v1", id="resident-context",
    version=digest(encoded(dict(files=pins, contract="geographic.resident_context.v1"))),
    record_contract="geographic.resident_context.v1", files=pins,
    index=dict(file="index.json", **pins["index.json"]),
    status="awaiting_publication", complete_download=None)
args.output.mkdir(parents=True, exist_ok=False)
for name, body in files.items():
    path = args.output / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
(args.output / "dataset.json").write_bytes(encoded(description))
print(json.dumps(dict(status="compiled_accepted_county_and_conditional_resident_runtime",
    version=description["version"], files=len(files), runtime_bytes=sum(len(body) for body in files.values()),
    modeled_precincts=json.loads(files["index.json"])["modeled_precincts"],
    website_builds_started=0, published_or_live=False)))
