"""Maintain the complete state/election worklist, newest elections first."""

import argparse
import csv
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
YEARS = list(range(2026, 1963, -2))
NYT = "https://github.com/nytimes/presidential-precinct-map-2024"
NC = "https://www.ncsbe.gov/results-data/election-results/historical-election-results-data"
NM = "https://electionresults.sos.nm.gov/resultsSW.aspx?type=FED&map=CTY"
FIELDS = [
    "priority", "year", "state_code", "state", "complete", "candidate_results",
    "boundaries", "join", "validation", "publication", "participation",
    "results_source", "boundary_source", "next_action", "notes",
]


def refresh_sources():
    features = json.loads((ROOT / "public/voter-participation/data/states.geojson").read_text())["features"]
    codes = sorted(f["properties"]["STUSAB"] for f in features
                   if f["properties"]["STUSAB"] not in {"PR", "GU", "VI", "MP", "AS"})

    def review(code):
        repository = f"openelections/openelections-data-{code.lower()}"
        branch = "main" if code == "MD" else "master"
        request = subprocess.run(["gh", "api", f"repos/{repository}/git/trees/{branch}?recursive=1"],
                                 capture_output=True, text=True, check=True)
        tree = json.loads(request.stdout)
        if tree.get("truncated"):
            raise ValueError(f"{code}: truncated source inventory; do not mark archive reviewed")
        years = {str(year): [] for year in YEARS}
        for item in tree["tree"]:
            path = item["path"]
            lower = path.lower()
            match = re.search(r"(?:^|/)((?:19|20)\d{2})11\d{2}__", path)
            if (item["type"] == "blob" and lower.endswith(".csv") and match
                and "general" in lower and ("precinct" in lower or "ward" in lower)
                and not any(word in lower for word in ["primary", "runoff", "special"])
                and match.group(1) in years):
                years[match.group(1)].append(dict(path=path, git_blob=item["sha"], bytes=item.get("size"),
                    url=f"https://github.com/{repository}/blob/{branch}/{path}"))
        print(code, sum(bool(files) for files in years.values()), "elections with general precinct-file leads", flush=True)
        return code, dict(repository=repository, branch=branch, tree_sha=tree["sha"],
                          truncated=False, elections=years)

    states = dict(ThreadPoolExecutor(max_workers=4).map(review, codes))
    target = ROOT / "public/precinct-source-inventory.json"
    target.write_text(json.dumps(dict(reviewed_at=datetime.now(timezone.utc).isoformat(),
        scope="Complete recursive OpenElections archive inventory for all 51 jurisdictions; November general-election precinct/ward filenames are leads, not validated ballot scope, licensing, joins or publication. No match here does not establish unavailability elsewhere.",
        states=states), indent=2) + "\n")


def build_rows(index=None, published=False, source_batches=None, participation_reviews=None):
    features = json.loads((ROOT / "public/voter-participation/data/states.geojson").read_text())["features"]
    states = sorted((f["properties"]["STUSAB"], f["properties"]["NAME"]) for f in features
                    if f["properties"]["STUSAB"] not in {"PR", "GU", "VI", "MP", "AS"})
    assert len(states) == 51 and len(set(code for code, _ in states)) == 51
    inventory_path = ROOT / "public/precinct-source-inventory.json"
    inventory = json.loads(inventory_path.read_text())["states"] if inventory_path.exists() else {}
    pointer = ROOT / "public/precinct-results.json"
    reviews = {}
    source_rows = {}
    if participation_reviews is None:
        path = ROOT / "public/participation-source-reviews.json"
        participation_reviews = json.loads(path.read_text())["reviews"] if path.exists() else []
    if pointer.exists():
        registration = json.loads(pointer.read_text())
        for path in registration.get("source_reviews", []):
            review = json.loads((ROOT / path).read_text())
            reviews[(review["year"], review["state_code"])] = review
        if source_batches is None:
            source_batches = [
                dict(json.loads((ROOT / batch["data_directory"] / "acquisition.json").read_text()),
                     complete_download_url=batch["complete_download_url"])
                for batch in registration.get("source_batches", [])]
    for batch in source_batches or []:
        for code, source in batch.get("states", {}).items():
            source_rows[(batch["year"], code)] = dict(source, complete_download_url=batch["complete_download_url"])
        for source in batch.get("elections", {}).values():
            source_rows[(source["year"], source["state_code"])] = dict(
                source, complete_download_url=batch["complete_download_url"])
    rows = []
    for year in YEARS:
        for code, name in states:
            row = dict.fromkeys(FIELDS, "")
            row.update(
                priority=len(rows) + 1, year=year, state_code=code, state=name, complete="no",
                candidate_results="not_reviewed", boundaries="not_reviewed", join="pending",
                validation="pending", publication="not_published", participation="not_acquired",
                next_action="Review state and county archives for this election; acquire exact-year returns and boundaries.",
                notes="Not reviewed is not a finding of unavailability. State/CPS and county observations do not count as precinct coverage.",
            )
            reviewed = inventory.get(code)
            if reviewed:
                files = reviewed["elections"][str(year)]
                row.update(candidate_results="source_identified" if files else "reviewed_archive_no_match",
                           results_source=files[0]["url"] if files else "https://github.com/" + reviewed["repository"])
                row["notes"] += (f" OpenElections full tree reviewed: {len(files)} general precinct CSV leads. "
                                 "These filenames are not proof of correct contest, residential ballot allocation, boundary vintage or licensing. "
                                 "No match in this one archive does not establish absence from state/county or other historical archives.")
            if code == "NC" and 2002 <= year <= 2024:
                row["participation"] = "published_counts"
                row["notes"] += " NC residential voter-history participation is published; not candidate votes."
                if year in {2006, 2012, 2014, 2016, 2020, 2022, 2024}:
                    row["participation"] = "published_counts_and_reference_map"
            if year == 2024:
                row["results_source"] = NYT
                if code == "AK":
                    row.update(candidate_results="absent_from_reviewed_release",
                               next_action="Review Alaska Division of Elections precinct results and district/precinct maps.")
                else:
                    row.update(candidate_results="acquired", boundaries="acquired",
                               boundary_source=NYT,
                               next_action="Validate state rows against the complete release; join and publish with boundary/reporting caveats.")
                    row["notes"] += " NYT: some boundaries are approximate; New England includes townships; some counties/votes are omitted. Retain all state notes and license."
            if year == 2026 and code in {"NC", "NM"}:
                row.update(candidate_results="acquired", boundaries="reference_acquired",
                           results_source=NC if code == "NC" else NM,
                           next_action="Reconcile candidate counts and audit county-scoped precinct identities; publish only verified joins.")
                if code == "NM":
                    row.update(participation="published_partial_reference_map",
                               boundary_source="https://gstore.unm.edu/apps/rgis/datasets/297dcb42-ac88-4026-abda-f1e614e79e8a/")
                    row["notes"] += " July 2026 geometry; three county precinct sets differ. Never allocate state/county results into precinct shapes."
                else:
                    row["boundary_source"] = "https://s3.amazonaws.com/dl.ncsbe.gov/ShapeFiles/Precinct/SBE_PRECINCTS_20260824.zip"
                    row["notes"] += " Election-night residential precincts exclude separately reported early/mail units. Do not call these all-ballot residential results."
            coverage = (index or {}).get("coverage", {}).get(str(year), {}).get(code)
            source = source_rows.get((year, code))
            if source:
                row.update(candidate_results="acquired_originals_review_pending",
                           results_source=source["source_url"],
                           validation=source.get("validation", "source_bytes_verified_scope_pending"),
                           publication="full_originals_download_only", next_action=source["next_action"])
                if (row["participation"] == "not_acquired" and source.get("participation")
                        and (not coverage or not source.get("county_name"))):
                    row["participation"] = source["participation"]
                if "original_files" in source:
                    row["notes"] += (
                        f' Complete original archive acquired: {source["original_files"]} files, '
                        f'{source["original_bytes"]:,} uncompressed bytes. '
                        "Original receipt SHA-256 values and native text record structure verified; "
                        "not independently reconciled candidate totals, validated precinct geography, "
                        "or inferred participation. Complete ZIP: " + source["complete_download_url"])
                else:
                    row["notes"] += (f' Complete original archive acquired: {source["rows"]:,} CSV rows. '
                                     "Exact source Git blob verified; not independently reconciled candidate totals, "
                                     "validated precinct geography, or inferred participation. Complete ZIP: "
                                     + source["complete_download_url"])
                if source.get("notes"):
                    row["notes"] += " " + source["notes"]
            review = reviews.get((year, code))
            if review:
                row.update({field: review[field] for field in [
                    "candidate_results", "boundaries", "join", "validation", "publication", "next_action"]})
                row.update(results_source=review["source_url"],
                           boundary_source=review.get("boundary_source") or review.get("sources", {}).get("boundary-service.json", ""),
                           notes=review["notes"] + " Complete ZIP: " + review["complete_download_url"])
                if review.get("participation"):
                    row["participation"] = review["participation"]
            if coverage:
                row.update(candidate_results="acquired", boundaries="reference_acquired",
                           join="validated_partial" if coverage.get("partial") else "validated",
                           validation="passed", publication="published_partial" if coverage.get("live_verified", published) else "snapshot_ready",
                           results_source=coverage["source_url"],
                           boundary_source=coverage.get("boundary_source", coverage["source_url"]),
                           next_action=coverage["next_action"], notes=coverage["notes"])
                if year == 2026 and code == "MN":
                    row["participation"] = "acquired_precinct_counts_and_registration"
                if coverage.get("participation"):
                    row["participation"] = coverage["participation"]
                if review and review.get("municipality"):
                    row["notes"] += (" Additional city-only count review: " + review["notes"]
                                     + " Complete ZIP: " + review["complete_download_url"])
            for participation_review in participation_reviews:
                for scope in participation_review["coverage"]:
                    if code == scope["state_code"] and year in scope["years"]:
                        if row["participation"] == "not_acquired":
                            row["participation"] = scope["status"]
                        row["notes"] += (" Separate participation review: " + scope["notes"]
                                         + " Complete ZIP: " + participation_review["complete_download_url"])
            rows.append(row)
    return rows


def write_ledger(index=None, published=False):
    rows = build_rows(index, published)
    target = ROOT / "public/precinct-coverage.csv"
    with target.open("w", newline="") as file:
        writer = csv.DictWriter(file, FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Precinct coverage: state-by-state, election-by-election", "",
        "Priority: **2026, 2024, 2022, 2020, then every earlier even year through 1964**.",
        "All 50 states and DC appear in every election: **1,632 tracked state/election cells**.",
        "Canonical machine-readable worklist: `public/precinct-coverage.csv`.",
        "Regenerate with `python scripts/build-precinct-coverage.py`.", "",
        "No state/year is complete until its actual candidate returns, correct-election reference",
        "boundaries, unique joins, count reconciliation, browser checks and live publication",
        "are verified. Partial coverage is not completion. Participation inputs are tracked separately;",
        "candidate votes are never demographic participation or turnout denominators.",
        "An unreviewed archive is not an unavailable archive. Do not borrow another election's",
        "boundaries, silently allocate county early/mail votes, or extrapolate state colors into precinct results.",
        "Full source downloads, state caveats, licenses and unmapped rows must remain available.", "",
        "Status key: `not_reviewed` = still to investigate; `acquired` = source saved, not yet mapped;",
        "`acquired_originals_review_pending` = complete original file saved, contest/ballot scope unverified;",
        "`full_originals_download_only` = complete source download, not validated maps or inferred turnout;",
        "`reference_acquired` = reference geometry, not certified election-day boundaries;",
        "`validated_partial` = audited subset only; `snapshot_ready` = data built, not yet verified live;",
        "`published_partial` = the acquired layer passed live browser checks, not complete statewide coverage.",
        "`reviewed_city_only_voter_counts` = limited municipal participation, not statewide or demographic coverage;",
        "`reviewed_county_mail_returns_only` = administrative mail returns, not all-mode ballots or final turnout.",
        "Checkmarks are reserved for verified, complete live coverage.", "",
    ]
    for year in YEARS:
        lines += [f"## {year}", "",
                  "| Done | State | Candidate returns | Boundaries | Join | Validation | Publication | Participation |",
                  "|---|---|---|---|---|---|---|---|"]
        for row in rows:
            if row["year"] == year:
                lines.append("| [ ] | " + " | ".join(str(row[field]) for field in [
                    "state", "candidate_results", "boundaries", "join", "validation",
                    "publication", "participation"]) + " |")
        lines.append("")
    (ROOT / "PRECINCT-COVERAGE.md").write_text("\n".join(lines))
    print(f"Tracked {len(rows)} state/election cells, newest first")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-sources", action="store_true")
    args = parser.parse_args()
    if args.refresh_sources:
        refresh_sources()
    pointer = ROOT / "public/precinct-results.json"
    index = None
    published = False
    if pointer.exists():
        settings = json.loads(pointer.read_text())
        index = {"coverage": {}}
        for snapshot in [settings] + settings.get("additional_snapshots", []):
            source = json.loads((ROOT / snapshot["data_directory"] / "index.json").read_text())
            for year, states in source["coverage"].items():
                index["coverage"].setdefault(year, {}).update({
                    code: dict(coverage, live_verified=snapshot.get("publication") == "live_verified_partial")
                    for code, coverage in states.items()
                })
    write_ledger(index, published)
