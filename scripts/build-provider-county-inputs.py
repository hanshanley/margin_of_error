"""Qualify held provider activity frames against complete Census county identities without new acquisition."""

import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261109-provider-county-frames-01"
SCOPE_FILE = "public/scripts/provider-county-scopes.js"
DOWNLOAD = ("https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-provider-county-frames-20261109-01/complete-analysis.zip")
REVIEW = """import {reviewProviderCountyFrames} from './scripts/provider-county-frames.mjs';
import {readFileSync} from 'node:fs';
process.stdout.write(JSON.stringify(reviewProviderCountyFrames(JSON.parse(readFileSync(0,'utf8')))));
"""


def encoded(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def build():
    output = ROOT / VERSION
    scope_output = ROOT / SCOPE_FILE
    if output.exists() or scope_output.exists():
        raise ValueError("Refuse to replace immutable provider source inputs")
    saved = ROOT / "public/participation-current/20261104T220424Z"
    original_snapshot = (saved / "snapshot.json").read_bytes()
    original_zip = (saved / "complete-snapshot.zip").read_bytes()
    if (hashlib.sha256(original_snapshot).hexdigest()
            != "3686633a86c1ca71890015bf98e690ed48540e519d3312a07251bca5a5c70578"
            or hashlib.sha256(original_zip).hexdigest()
            != "3734886ed3c5cbbc406f6adacd60dff2b1b543c42546fc39e89e46da1220dc08"):
        raise ValueError("Changed already-held complete source snapshot")
    snapshot = json.loads(original_snapshot)
    receipts = {r["file"]: r for r in snapshot["sources"]}
    context = dict(dataset_directory_id="20261104T220424Z",
        source_snapshot_id=snapshot["snapshot_id"], collector_election_date=snapshot["election_date"],
        collector_retrieved_at=snapshot["retrieved_at"], native_election_id_qualified=False,
        rates_approved=False, source_provider="civicAPI early activity",
        states=[dict(state_code=r["state_code"], state=r["state"]) for r in snapshot["coverage"]],
        limitations=snapshot["limitations"], provider=snapshot["providers"][0])
    members, responses, review_sources = {}, {}, {}
    with zipfile.ZipFile(saved / "complete-snapshot.zip") as archive:
        for path in archive.namelist():
            match = re.fullmatch(r"sources/20261104T220425Z/([A-Z]{2})-(inperson|returned)\.json", path)
            if not match:
                continue
            code, category = match.groups()
            name = Path(path).name
            receipt = receipts[name]
            body = archive.read(path)
            if (receipt["bytes"] != len(body)
                    or receipt["sha256"] != hashlib.sha256(body).hexdigest()
                    or receipt["http_status"] != 200):
                raise ValueError("Changed successful raw provider response")
            safe_receipt = dict(url=receipt["url"], retrieved_at=receipt["retrieved_at"],
                source_snapshot_id=receipt["snapshot_id"], bytes=receipt["bytes"],
                sha256=receipt["sha256"], http_status=receipt["http_status"])
            key = code + "-" + category
            members["originals/" + name] = body
            responses[key] = dict(path=VERSION + "/originals/" + name, receipt=safe_receipt)
            review_sources[key] = dict(native=json.loads(body), receipt=safe_receipt)
    if len(responses) != 79 or context["source_snapshot_id"] != "20261104T220425Z":
        raise ValueError("Incomplete held provider response set")
    pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
    index = json.loads((ROOT / pointer["data_directory"] / "index.json").read_bytes())
    if index["boundary_reference_year"] != 2026:
        raise ValueError("Wrong county reference year")
    references, catalogue, reference_files = {}, {}, {}
    for code, source in index["coverage"].items():
        path = "data/" + source["file"].split("/data/", 1)[1]
        body = (ROOT / path).read_bytes()
        decoded = gzip.decompress(body)
        if (hashlib.sha256(body).hexdigest() != source["sha256"]
                or hashlib.sha256(decoded).hexdigest() != source["uncompressed_sha256"]):
            raise ValueError("Changed full county reference")
        geometry = json.loads(decoded)
        reference = dict(path=path, url=source["file"], boundary_year=2026, counties=source["counties"],
            sha256=source["sha256"], uncompressed_sha256=source["uncompressed_sha256"],
            review_id="provider-contextual-county-identities-20261109-01")
        references[code] = reference
        catalogue[code] = dict(reference, identities=[dict(county_fips=f["properties"]["key"],
            county=f["properties"]["name"], state_code=f["properties"]["state_code"],
            boundary_year=f["properties"]["boundary_year"]) for f in geometry["features"]])
        reference_files[path] = dict(bytes=len(body), sha256=source["sha256"])
    result = json.loads(subprocess.check_output(["node", "--input-type=module", "-e", REVIEW],
        cwd=ROOT, input=encoded(dict(context=context, sources=review_sources,
            catalogue=catalogue, completeDownloadUrl=DOWNLOAD))))
    if (result["summary"]["complete_state_mode_queries"] != 102
            or result["summary"]["all_source_region_queries"] != 6371
            or result["summary"]["approved_county_frames"] != 63
            or result["summary"]["approved_states"] != 39):
        raise ValueError("Changed complete source-frame qualification")
    legacy = {(r["state_code"], r["mode"], r["geography"]): r
              for r in csv.DictReader((saved / "early_voting.csv").open())}
    for row in result["region_queries"]:
        prior = legacy[(row["state_code"], row["mode"], row["source_region"])]
        if int(prior["ballots"]) != row["source_count"] or prior["source_date"] != row["source_date"]:
            raise ValueError("Raw-source query disagrees with unchanged collector observation")
    members["source-context.json"] = encoded(context)
    members["legacy-early-voting.csv"] = (saved / "early_voting.csv").read_bytes()
    files = {f"{VERSION}/{name}": dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
             for name, body in members.items()}
    files.update(reference_files)
    scopes = {code: dict(counties=references[code]["counties"], modes=sorted(frames))
              for code, frames in result["county_frames"].items()}
    scope_body = ("export const providerCountyScopes = " + json.dumps(scopes, indent=2) + ";\n").encode()
    files[SCOPE_FILE] = dict(bytes=len(scope_body), sha256=hashlib.sha256(scope_body).hexdigest())
    inputs = dict(version=VERSION, responses=responses, references=references,
        files=files, complete_download_url=DOWNLOAD, all_state_mode_queries=102,
        native_election_context_qualified=False, rates_approved=False)
    output.mkdir(parents=True)
    for name, body in members.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    (output / "inputs.json").write_bytes(encoded(inputs))
    scope_output.write_bytes(scope_body)
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    build()
