"""Freeze complete existing client inputs for the source-mode selection review."""

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-native-mode-frames-01"
BASELINE = "2a33e0ef0b4ec0c984feda099aebe92f67de8281"


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


class Facts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reviewed = None
        self.additional = None
        self.snapshot = None

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if "data-reviewed-county-participation" in values:
            self.reviewed = json.loads(values["data-reviewed-county-participation"])
        if "data-additional-participation" in values:
            self.additional = json.loads(values["data-additional-participation"])
        if values.get("id") == "nationwide-participation":
            self.snapshot = {key: value for key, value in values.items() if key.startswith("data-")}


def freeze(audit):
    target = ROOT / VERSION
    if target.exists():
        raise ValueError("Never overwrite an existing scientific source version")
    parser = Facts()
    parser.feed((ROOT / "dist/voter-participation/index.html").read_text())
    if not isinstance(parser.reviewed, list) or len(parser.additional) != 49:
        raise ValueError("Missing or changed complete client source inventory")
    bodies = {}
    source_files = {}
    for path in sorted((ROOT / "dist/participation-local").glob("*.json.gz")):
        code = path.name.split(".", 1)[0]
        if len(code) != 2 or not code.isupper():
            raise ValueError("Unexpected local source identity")
        name = f"source-data/local/{path.name}"
        bodies[name] = path.read_bytes()
        source_files[code] = name
    if len(source_files) != 49 or set(source_files) & {"AK", "DC"}:
        raise ValueError("Changed native local-export scope")
    base = ROOT / "public/participation-current/20261104T220424Z"
    snapshot = json.loads((base / "snapshot.json").read_bytes())
    if snapshot["local_file"] != "local.json":
        raise ValueError("Changed shared native input")
    shared = json.loads((base / "local.json").read_bytes())
    if any(row.get("state_code") in {"AK", "DC"} for name in ["counties", "precincts"] for row in shared[name]):
        raise ValueError("Review Alaska/DC shared inputs before replacing their explicit missingness")
    bodies["source-data/shared-native-snapshot.json"] = (base / "snapshot.json").read_bytes()
    bodies["source-data/shared-native-local.json"] = (base / "local.json").read_bytes()
    bodies["source-data/all-reviewed-counties.json"] = encoded(parser.reviewed)
    bodies["source-data/additional-coverage.json"] = encoded(parser.additional)
    bodies["source-data/declared-shared-snapshot.json"] = encoded(parser.snapshot)
    for name in ["participation-geography.js", "provider-county-scopes.js", "participation-explorer.js"]:
        bodies["source-code/" + name] = subprocess.check_output(
            ["git", "-C", str(ROOT), "show", f"{BASELINE}:public/scripts/{name}"])
    result = json.loads(audit.read_bytes())
    if result["source_commit"] != BASELINE or len(result["complete_decisions"]) != 102:
        raise ValueError("Changed complete source-mode review")
    bodies["prior-audit/all102-original-selection-decisions.json"] = audit.read_bytes()
    target.mkdir(parents=True)
    for name, body in bodies.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    inputs = dict(version=VERSION, baseline_website_commit=BASELINE,
        files={name: pin(body) for name, body in sorted(bodies.items())},
        state_local_files=source_files,
        missing_separate_local_exports=["AK", "DC"],
        shared_native_AK_DC_county_and_unit_rows=0,
        native_precinct_modes_separately_guarded_in_original_explorer=True,
        whole_source_queries_and_counts_retained=True,
        legacy_frame_raw_inputs_not_reacquired=True,
        new_normalized_mode_or_population_qualification=False,
        previous_source_releases_preserved=True,
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-native-mode-frames-20261110-01/complete-analysis.zip")
    (target / "inputs.json").write_bytes(encoded(inputs))
    print(json.dumps(dict(status="PASS_frozen_complete_existing_client_inputs_NOT_live_fix",
        sufficient_inputs=len(bodies), state_local_exports=49, prior_audit_decisions=102,
        reviewed_county_rows=len(parser.reviewed), new_acquisitions=0)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    freeze(parser.parse_args().audit)
