"""Freeze held Maine source activity and full contextual identity/reference inputs without acquisition."""

import gzip
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-maine-locality-activity-01"
GEOMETRY = "public/participation-locality-activity/20261110-maine-01/ME.geojson.gz"
REPRODUCE = """import {reviewMaineLocalityActivity} from './scripts/maine-locality-activity.mjs';
import {readFileSync} from 'node:fs';
process.stdout.write(JSON.stringify(reviewMaineLocalityActivity(JSON.parse(readFileSync(0,'utf8'))).summary));
"""


def build():
    if (ROOT / VERSION).exists() or (ROOT / GEOMETRY).exists():
        raise ValueError("Refuse to replace immutable Maine locality inputs")
    prior = json.loads((ROOT / "data/county-source-reviews/20261109-provider-county-frames-01/inputs.json").read_bytes())
    members, responses, sources = {}, {}, {}
    for category in ["inperson", "returned"]:
        record = prior["responses"]["ME-" + category]
        body = (ROOT / record["path"]).read_bytes()
        if hashlib.sha256(body).hexdigest() != record["receipt"]["sha256"]:
            raise ValueError("Changed original held Maine response")
        name = f"{VERSION}/originals/ME-{category}.json"
        members[name] = body
        responses[category] = dict(path=name, receipt=record["receipt"])
        sources[category] = dict(native=json.loads(body), receipt=record["receipt"])
    context = "data/participation-local/20261104T220000Z-identity-audit"
    original_path = context + "/geometry/2024/municipality-ME.geojson.gz"
    historical_path = context + "/states/ME.json.gz"
    geometry = (ROOT / original_path).read_bytes()
    historical = (ROOT / historical_path).read_bytes()
    members[GEOMETRY] = geometry
    historical_copy = f"{VERSION}/originals/held-ME-all-history-identity-export.json.gz"
    members[historical_copy] = historical
    reference = dict(path=GEOMETRY, url="/" + GEOMETRY.removeprefix("public/"),
        sha256=hashlib.sha256(geometry).hexdigest(),
        uncompressed_sha256=hashlib.sha256(gzip.decompress(geometry)).hexdigest(),
        boundary_year=2024, localities=528, geography_scope="provider_partial_locality_activity",
        identity_field="reference_municipality_key", review_id="maine-locality-activity-20261110-01",
        certified_election_day_geography=False)
    inputs = dict(state_code="ME", collector_election_year=2026, native_election_id_qualified=False,
        rates_approved=False, original_geometry_path=original_path, original_historical_path=historical_path,
        historical_identity_path=historical_copy, reference=reference, responses=responses,
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-maine-locality-activity-20261110-01/complete-analysis.zip",
        files={name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
               for name, body in members.items()})
    summary = json.loads(subprocess.check_output(["node", "--input-type=module", "-e", REPRODUCE],
        cwd=ROOT, input=json.dumps(dict(inputs=inputs, sources=sources,
            original=json.loads(gzip.decompress(geometry)), historical=json.loads(gzip.decompress(historical)))).encode()))
    if (summary["mapped_per_mode"] != dict(in_person_early=480, mail_returned=480)
            or summary["complete_source_region_queries"] != 1168
            or summary["complete_reference_queries"] != 1056):
        raise ValueError("Changed full partial-locality source qualification")
    for name, body in members.items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    (ROOT / VERSION / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    build()
