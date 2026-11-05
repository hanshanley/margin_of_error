"""Archive declared 2026 House district APIs; county counts still require review."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil

import requests

API = "https://civicapi.org/api/v2/race/"
STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())


def election_scope(data, province):
    if (data.get("test_data") is not False or data.get("country") != "US"
            or data.get("province") != province
            or not isinstance(data.get("election_date"), str)
            or data["election_date"][:10] != "2026-11-03"
            or data.get("election_type") != "House of Representatives"
            or data.get("election_scope") != "General"):
        raise ValueError("Wrong 2026 House election, jurisdiction, scope or test-data flag")


def declared_districts(data):
    election_scope(data, "US")
    districts = {}
    source_ids = set()
    regions = data.get("region_results")
    if not isinstance(regions, dict):
        raise ValueError("Missing complete national district inventory")
    for key, region in regions.items():
        match = re.fullmatch(r"([a-z]{2})-(al|0[1-9]|[1-4][0-9]|5[0-3])", key)
        source_id = region.get("election_id")
        if (not match or match[1].upper() not in STATES
                or region.get("type") != "Congressional District"
                or type(source_id) is not int or source_id <= 0 or source_id in source_ids):
            raise ValueError("Ambiguous declared House district identity or API identifier")
        source_ids.add(source_id)
        districts[key] = dict(state_code=match[1].upper(), district=key.upper(),
                              source_id=source_id, url=API + str(source_id))
    if len(districts) != 435 or {r["state_code"] for r in districts.values()} != STATES:
        raise ValueError("House inventory must declare 435 unique districts across all 50 states")
    return districts


def district_scope(data, declared):
    election_scope(data, declared["state_code"])
    if data.get("district") != declared["district"] or not isinstance(data.get("region_results"), dict):
        raise ValueError("Wrong declared district or missing native breakdown collection")


def saved_response(folder, key, declared):
    path = folder / (key + ".json")
    receipt = json.loads(path.with_suffix(".json.receipt.json").read_bytes())
    raw = path.read_bytes()
    if (receipt["status"] != 200 or receipt["url"] != declared["url"]
            or receipt["bytes"] != len(raw) or receipt["sha256"] != hashlib.sha256(raw).hexdigest()):
        raise ValueError("Cached district bytes or declared source receipt disagree")
    data = json.loads(raw)
    district_scope(data, declared)
    return data, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--national-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed-cache", type=Path)
    args = parser.parse_args()
    raw = args.national_source.read_bytes()
    national = json.loads(raw)
    districts = declared_districts(national)
    args.output.mkdir(parents=True, exist_ok=True)
    original = args.output / "original-national-house.json"
    if original.exists() and original.read_bytes() != raw:
        raise ValueError("Refusing to replace original national declaration")
    original.write_bytes(raw)
    if args.seed_cache:
        for key, declared in districts.items():
            path = args.seed_cache / (key + ".json")
            target = args.output / path.name
            if not path.exists() or target.exists():
                continue
            _, receipt = saved_response(args.seed_cache, key, declared)
            receipt["headers"] = {k: v for k, v in receipt.get("headers", {}).items()
                                  if k.lower() in {"content-type", "etag", "last-modified", "date"}}
            shutil.copyfile(path, target)
            target.with_suffix(".json.receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")

    def acquire(item):
        key, declared = item
        path = args.output / (key + ".json")
        try:
            if path.exists():
                data, receipt = saved_response(args.output, key, declared)
            else:
                response = requests.get(declared["url"], timeout=(20, 90))
                content = response.content
                receipt = dict(url=declared["url"], status=response.status_code, bytes=len(content),
                               sha256=hashlib.sha256(content).hexdigest(),
                               acquired_at=datetime.now(timezone.utc).isoformat(),
                               headers={k: v for k, v in response.headers.items()
                                        if k.lower() in {"content-type", "etag", "last-modified", "date"}})
                path.write_bytes(content)
                path.with_suffix(".json.receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
                response.raise_for_status()
                data, receipt = saved_response(args.output, key, declared)
            regions = data["region_results"]
            result = dict(declared, status="original_acquired_scope_verified", file=path.name,
                          bytes=receipt["bytes"], sha256=receipt["sha256"],
                          native_region_count=len(regions),
                          native_region_types=sorted({r["type"] for r in regions.values()}),
                          source_updated_at=data.get("last_updated"))
        except Exception as error:
            result = dict(declared, status="not_promoted", error=str(error),
                          exception=type(error).__name__)
        print(key, result["status"], result.get("native_region_types", result.get("error")), flush=True)
        return key, result

    results = dict(ThreadPoolExecutor(max_workers=4).map(acquire, districts.items()))
    manifest = dict(year=2026, scope="Provider House district originals; not verified county maps or participation",
                    declared_districts=435, national_source_url=API + "87524",
                    national_source_sha256=hashlib.sha256(raw).hexdigest(),
                    national_source_updated_at=national.get("last_updated"), districts=results,
                    acquired=sum(r["status"] == "original_acquired_scope_verified" for r in results.values()),
                    next_action="Reconcile complete candidate vectors to each district's own county breakdown, "
                    "validate explicit county FIPS against contextual geometry, require complete state district "
                    "coverage before aggregating county fragments, preserve all unmatched and noncounty regions. "
                    "Do not allocate district totals or use missing candidate counts as zero. "
                    "Different source snapshots may have different update times.")
    (args.output / "acquisition.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("ACQUIRED", manifest["acquired"], "of 435 declared district originals", flush=True)


if __name__ == "__main__":
    main()
