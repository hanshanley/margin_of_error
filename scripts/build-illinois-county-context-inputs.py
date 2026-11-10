"""Freeze only already-held Illinois source-region counts and unchanged county context."""

import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
OLD = "data/county-source-reviews/20261109-provider-county-frames-01"
VERSION = "data/county-source-reviews/20261110-illinois-county-context-01"
target = ROOT / VERSION
if target.exists():
    raise ValueError("Refuse to replace an immutable Illinois input version")
old = json.loads((ROOT / OLD / "inputs.json").read_bytes())
reference = old["references"]["IL"]
pins = {}
responses = {}
for category in ("inperson", "returned"):
    source = old["responses"]["IL-" + category]
    name = source["path"]
    body = (ROOT / name).read_bytes()
    if len(body) != old["files"][name]["bytes"] or hashlib.sha256(body).hexdigest() != old["files"][name]["sha256"]:
        raise ValueError("Changed held Illinois original")
    path = target / ("original-" + category + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / name, path)
    relative = str(path.relative_to(ROOT))
    pins[relative] = dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    responses[category] = dict(path=relative, receipt=source["receipt"])
body = (ROOT / reference["path"]).read_bytes()
if hashlib.sha256(body).hexdigest() != reference["sha256"]:
    raise ValueError("Changed complete Illinois reference")
path = target / "original-county-context.geojson.gz"
shutil.copyfile(ROOT / reference["path"], path)
relative = str(path.relative_to(ROOT))
pins[relative] = dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
inputs = dict(version=VERSION, reference=dict(reference, path=relative),
    responses=responses, files=pins, native_election_id_qualified=False,
    whole_county_counts_qualified=False, authority_territories_qualified=False,
    rates_approved=False, complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
        "voter-illinois-county-context-20261110-01/complete-analysis.zip")
(target / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
print("Frozen two complete held source responses and unchanged complete 102-county context; no map approval")
