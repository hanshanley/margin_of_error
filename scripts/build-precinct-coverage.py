"""Maintain the complete state/election worklist, newest elections first."""

import csv
import gzip
import io
import json
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


def build_rows(index=None):
    features = json.loads((ROOT / "public/voter-participation/data/states.geojson").read_text())["features"]
    states = sorted((f["properties"]["STUSAB"], f["properties"]["NAME"]) for f in features
                    if f["properties"]["STUSAB"] not in {"PR", "GU", "VI", "MP", "AS"})
    assert len(states) == 51 and len(set(code for code, _ in states)) == 51
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
            if coverage:
                row.update(candidate_results="acquired", boundaries="reference_acquired",
                           join="validated_partial" if coverage.get("partial") else "validated",
                           validation="passed", publication="snapshot_ready",
                           results_source=coverage["source_url"],
                           next_action=coverage["next_action"], notes=coverage["notes"])
            rows.append(row)
    return rows


def write_ledger(index=None):
    rows = build_rows(index)
    target = ROOT / "public/precinct-coverage.csv"
    with target.open("w", newline="") as file:
        writer = csv.DictWriter(file, FIELDS)
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
        "`reference_acquired` = reference geometry, not certified election-day boundaries;",
        "`validated_partial` = audited subset only; `snapshot_ready` = data built, not yet verified live.",
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
    pointer = ROOT / "public/precinct-results.json"
    index = None
    if pointer.exists():
        base = json.loads(pointer.read_text())["data_directory"]
        index = json.loads((ROOT / base / "index.json").read_text())
    write_ledger(index)
