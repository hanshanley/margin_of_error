"""Build complete jurisdiction and reviewed county/contest inventories, not fabricated attribution."""

import argparse
import csv
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODES = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()


def build(model, county_rows, districts, nc_candidates):
    states = model["models"][0]["group_diagnostics"]["state"]
    diagnostics = {row["group"]: row for row in states}
    if set(diagnostics) != set(CODES):
        raise ValueError("Missing or unexpected historical-model jurisdiction")
    groups = defaultdict(list)
    for row in county_rows:
        if (row["year"] != "2026" or row["office"] != "U.S. House" or int(row["votes"]) < 0
                or row["state_code"] not in CODES or len(row["county_fips"]) != 5
                or not row["county_fips"].isdigit()):
            raise ValueError("Unexpected county/contest scope")
        groups[(row["state_code"], row["county_fips"], row["district"])].append(row)
    county_contests = []
    county_districts = defaultdict(set)
    for state, county, district in groups:
        county_districts[(state, county)].add(district)
    for (state, county, district), rows in sorted(groups.items()):
        parties = defaultdict(int)
        for row in rows:
            parties[row["party"]] += int(row["votes"])
        reasons = ["No reviewed 2024 presidential baseline for this exact 2026 contest geography",
                   "No qualified all-mode longitudinal participation / entry model",
                   "Election stage, round and literal-party assignments require contest review"]
        if len(county_districts[(state, county)]) > 1:
            reasons.append("County is split across House contests; do not compare a partial county with its entire presidential vote")
        if not parties.get("Democratic", 0) or not parties.get("Republican", 0):
            reasons.append("No ordinary two-major-party comparison in the supplied candidate vector")
        county_contests.append({
            "state_code": state, "county_fips": county, "county_name": rows[0]["county_name"],
            "contest": district, "office": "U.S. House", "candidate_rows": len(rows),
            "literal_party_totals": dict(sorted(parties.items())),
            "source_urls": sorted({row["source_url"] for row in rows}),
            "source_update_labels": sorted({row["source_updated_at"] for row in rows}),
            "historical_preference_model_available": True, "attribution_available": False,
            "comparison_status": "not_yet_qualified", "exclusions": reasons,
            "next_action": "Review district/year scope and historical baseline; acquire cohort/participation evidence before fitting local transitions",
        })
    for county in sorted({row["county"] for row in nc_candidates}):
        if any(row["county"] == county and row["year"] == 2026 and row["contest"] == "US SENATE"
               for row in nc_candidates):
            county_contests.append({
                "state_code": "NC", "county_name": county, "county_fips": None,
                "contest": "US SENATE", "office": "U.S. Senate",
                "historical_preference_model_available": True, "attribution_available": False,
                "comparison_status": "provisional_descriptive_county_swing_available",
                "exclusions": ["An experimental Durham model is not validated statewide or countywide individual attribution"],
                "next_action": "Validate the Durham three-component model, then construct corresponding county-specific aggregate cohorts",
            })
    jurisdiction_rows = []
    for state in CODES:
        state_districts = [row for row in districts if row["state_code"] == state and row["level"] == "district"]
        counties = {county for code, county, _ in groups if code == state}
        jurisdiction_rows.append({
            "state_code": state, "jurisdiction_type": "federal_district" if state == "DC" else "state",
            "historical_choice_model": "fitted_low_effective_sample" if diagnostics[state]["low_effective_sample"] else "fitted_internal_county_holdout",
            "historical_choice_validation": diagnostics[state],
            "county_candidate_source_counties": len(counties),
            "house_contests_in_national_source": len(state_districts),
            "house_applicability": "No voting House district; delegate requires separate scope" if state == "DC" else "District contests, not one statewide race",
            "senate_inventory": "Reviewed native NC Senate county results available" if state == "NC" else "Contest schedule and result sources not yet inventoried; not assumed absent",
            "governor_inventory": "Contest schedule and result sources not yet inventoried; not assumed absent",
            "attribution_available": False,
            "next_action": (
                "Fit and validate the native linked-cohort county model; extend county-by-county, then aggregate without double counting"
                if state == "NC" else
                "Acquire independently scoped delegate/local evidence; do not include DC in the 435 voting House districts"
                if state == "DC" else
                "Inventory actual Senate/governor contests and their ballots; acquire lawful registration/history or qualify an explicitly weaker aggregate transition model"),
        })
    return {
        "status": "nationwide_scope_ledger_not_completed_nationwide_attribution",
        "state_count": 50, "dc_separate": True,
        "historical_model_coverage_is_not_attribution_coverage": True,
        "jurisdictions": jurisdiction_rows, "county_contests": county_contests,
        "precinct_policy": "No downward allocation of state/county estimates; reconcile boundaries and ballot assignment before precinct models",
    }


def run(model_path, output):
    if output.exists():
        raise ValueError("Refusing to overwrite an existing scope review")
    pointer_path = ROOT / "public/county-results.json"
    pointer = json.loads(pointer_path.read_text())
    county_path = ROOT / pointer["party_votes"]["data_directory"] / "county-district-candidate-totals.csv.gz"
    result_pointer_path = ROOT / "public/participation-results/latest.json"
    result_pointer = json.loads(result_pointer_path.read_text())
    district_path = ROOT / "public/participation-results" / result_pointer["snapshot_id"] / "margins.json"
    nc_path = ROOT / "data/participation-swing/20261106-candidate-scope-01/county-contest-methods.json"
    with gzip.open(county_path, "rt", newline="") as source:
        rows = list(csv.DictReader(source))
    result = build(json.loads(model_path.read_text()), rows, json.loads(district_path.read_text()),
                   json.loads(nc_path.read_text()))
    result["inputs"] = [
        {"role": role, "file": path.name, "bytes": path.stat().st_size,
         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for role, path in [("historical_choice_models", model_path), ("county_source_pointer", pointer_path),
                           ("complete_county_candidate_vectors", county_path), ("district_pointer", result_pointer_path),
                           ("complete_national_district_results", district_path), ("native_nc_contest_methods", nc_path)]
    ]
    output.mkdir(parents=True, exist_ok=False)
    (output / "nationwide-scope.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"states": 50, "dc_separate": True, "county_contests": len(result["county_contests"]),
                      "published_attribution_states": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--choice-model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.choice_model, args.output)
