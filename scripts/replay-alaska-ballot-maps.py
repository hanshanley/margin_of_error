"""Reproduce the two Alaska map joins from the complete pinned count tables."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

LAYER_SHA = "8c5bf4c88d3d4ab72b3a655189b904f28f7c9a3a6c87047516a39aca9cbc8273"
ROSTER_SHA = "be107e5afd87362baa865bb2e209e787e1ef7f903f9691748698938c626c852b"
APP_SHAPE_SHA = "1e9d6b95b88c4ebeea3a1ec5bcd3d0a6052d0436e82dfee0fb62fbc4c25381eb"
SCOPE = {
    "2024": ("2024-11-05", "aca7ab6e949d1319b48692ab8e8b694835ff6a9bd862fc9efbac91550c25f957"),
    "2026": ("2026-11-03", "ce1807693399216072657bb0a8451e5451b7d081b7f224e2a8306f99d6cedfb0"),
}


def verify(condition, detail):
    if not condition:
        raise ValueError(detail)


def replay(package, output):
    body = (package / "AK.geojson.gz").read_bytes()
    verify(hashlib.sha256(body).hexdigest() == LAYER_SHA, "Unexpected display layer")
    layer = json.loads(gzip.decompress(body))
    ids = sorted(f["properties"]["native_precinct_id"] for f in layer["features"])
    verify(len(ids) == len(set(ids)) == 81, "Incomplete display layer")
    frames, audit = [], {}
    for year, (date, original_sha) in SCOPE.items():
        with gzip.open(package / f"participation-ak-{year}-precinct-ballot-archive.csv.gz",
                       "rt", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        verify(len(rows) == 523 and all(row["state_code"] == "AK" and row["election_date"] == date
                   and row["source_sha256"] == original_sha for row in rows), "Unexpected count edition")
        precincts = [row for row in rows if row["unit_scope"] == "precinct_election_day_only"]
        counts = {row["source_unit_id"]: row for row in precincts}
        verify(len(precincts) == len(counts) == 402 and set(ids) <= counts.keys()
               and hashlib.sha256("\n".join(sorted(counts)).encode()).hexdigest() == ROSTER_SHA,
               "Count and geometry precinct rosters differ")
        verify(all(int(row["reported_ballots"]) == int(row["election_day_ballots"]) >= 0
                   for row in precincts), "Election Day count scope differs")
        frames.extend((date, key, counts[key]["reporting_unit"], counts[key]["election_day_ballots"]) for key in ids)
        audit[year] = {
            "map_precincts": len(ids), "held_precincts": len(counts) - len(ids),
            "central_units_not_allocated": len(rows) - len(counts),
            "mapped_election_day_ballots": sum(int(counts[key]["election_day_ballots"]) for key in ids),
        }
    output.mkdir(parents=True, exist_ok=True)
    with (output / "mapped-election-day-ballots.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("election_date", "precinct_id", "reporting_unit", "election_day_ballots"))
        writer.writerows(frames)
    (output / "map-audit.json").write_text(json.dumps({
        "official_2024_and_2026_geometry_sha256": APP_SHAPE_SHA, "display_subset_sha256": LAYER_SHA,
        "complete_precinct_roster_sha256": ROSTER_SHA, "editions": audit,
        "legal_boundaries_certified": False, "central_ballots_allocated": False, "rates_calculated": False,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    replay(Path(sys.argv[1]), Path(sys.argv[2]))
