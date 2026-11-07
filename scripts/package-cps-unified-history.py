"""Join frozen CPS histories without recalculating native rates or age bins."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DATA = "data/participation-cps-unified-history/20261107-01"
CODE = ("scripts/package-cps-unified-history.py", "scripts/test-package-cps-unified-history.py")
SOURCES = {
    "early": ("early-history",
              "2cf3e2b15213785cec42b29c5742088519a1b8a677fdc68549fe4b4286d3f45b",
              "52560a64af8ee826036752b18d3aa84723647bf8298418a4c12e5e64c3e8524d"),
    "older": ("older-history",
              "de2f710a390a6cb14f087e19b69611cd9dcf81d15c6e24311f90ef094507ff17",
              "49a6dece89b06214c2394b63e8c5d7281bb3b2be916004869bcfd91700fbb50f"),
    "recent": ("state-history",
               "9a9e39a224cfa84ecca24701badef592c779c41efce73cbae26b502f012efc91",
               "1aa69c635001efd19dec69fc2f1cd3d40ae524adc3c5f9fd766b36f4d08bbd8c"),
}
YEARS = tuple(range(2004, 2025, 2))
GROUPS = (
    "Total", "Male", "Female", "White alone", "White non-Hispanic alone", "Black alone",
    "Asian alone", "Hispanic (any race)", "White alone or in combination",
    "Black alone or in combination", "Asian alone or in combination",
    "White non-Hispanic alone or in combination",
    "18 to 24", "25 to 34", "35 to 44", "25 to 44", "18 to 44", "45 to 54",
    "55 to 64", "45 to 64", "65+", "65 to 74", "75+",
)
EARLY_GROUPS = {
    **{group: ("sex_race", "." + group) for group in GROUPS[:12]},
    "White non-Hispanic alone": ("sex_race", "..White non-Hispanic alone"),
    "White non-Hispanic alone or in combination":
        ("sex_race", "..White non-Hispanic alone or in combination"),
    "Hispanic (any race)": ("sex_race", ".Hispanic (of any race)"),
    **{group: ("age", "." + group) for group in GROUPS[12:]},
}
STATUSES = (
    "published_native_rate", "native_B_not_published", "withheld_small_rounded_population_base",
    "native_zero_or_rounds_to_zero", "not_supplied", "withheld_conflicting_same_year_total",
    "withheld_native_out_of_range_metric", "withheld_conflicting_extra_native_label",
    "withheld_unlabeled_native_geography",
)
NUMERIC_STATUSES = {-1: STATUSES[1], -2: STATUSES[2], -3: STATUSES[3], -4: STATUSES[4]}
LIMITS = (
    "Reported voting, not administrative turnout, candidate choice or 2026 participation.",
    "2004 uses all adults 18+; 2006-2024 use adult citizens 18+. These denominators are never spliced.",
    "The universe is civilian noninstitutionalized adults, not a legal-eligibility count.",
    "All native rates and 90% margins are copied from qualified source displays, never derived from rounded counts.",
    "Published margins exclude nonsampling error and are not confidence intervals for changes or simultaneous intervals.",
    "Exact native age bins remain distinct. Unsupported year/group cells stay unavailable; no age bins or margins are combined.",
    "Race-alone, race-in-combination and Hispanic views overlap. Do not sum them or construct intersections.",
    "The national benchmark includes D.C. and is not computed by adding rounded state observations.",
    "National sex/race blocks in 2006 and 2008 are unlabeled and never assigned to the United States.",
    "Only the explicitly labeled 2008 national age Total supplies that year's national overall observation.",
    "Conflicting 2008 Florida/Georgia/Hawaii totals and the South Dakota out-of-range row remain withheld.",
    "The extra Arizona Non-Hispanic White label is not aliased into a qualified group.",
    "Suppression and changing rounded population-base rules remain as qualified in each original package; population is not sample size.",
    "Repeated cross-sections are not fixed cohorts, individual switching, measured staying home or causal midterm effects.",
    "Education, income and urbanicity are not supplied by these state tables; no county or precinct group rates are inferred.",
    "Joining accepted displays is not fresh native extraction, independent outcome validation or a new estimate.",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_sources(root):
    displays, members = {}, {}
    for key, (part, display_hash, archive_hash) in SOURCES.items():
        base = f"data/participation-cps-{part}/20261107-01/output"
        for name, expected in (("display.json", display_hash), ("complete-analysis.zip", archive_hash)):
            path = f"{base}/{name}"
            raw = (root / path).read_bytes()
            require(digest(raw) == expected, f"Changed frozen input: {path}")
            members[path] = raw
        raw = members[f"{base}/complete-analysis.zip"]
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive.namelist()
            require(len(names) == len(set(names)), "Duplicate original archive member")
            inventory = json.loads(archive.read("checksums.json"))
            require(set(names) == {*inventory, "checksums.json"}, "Incomplete original archive")
            for name, receipt in inventory.items():
                member = archive.read(name)
                require(len(member) == receipt["bytes"] and digest(member) == receipt["sha256"],
                        f"Original archive checksum mismatch: {name}")
            require(archive.read("results/display.json") == members[f"{base}/display.json"],
                    "Original archive/display disagreement")
        displays[key] = json.loads(members[f"{base}/display.json"])
    return displays, members


def join(displays):
    early, older, recent = (displays[key] for key in ("early", "older", "recent"))
    require(len(early) == 2375, "Incomplete early history")
    states = recent["states"]
    require(len(states) == len(set(states)) == 52 and states == older["states"]
            and states[0] == "United States (including D.C.)"
            and "District of Columbia" in states, "Changed geography inventory")
    require(older["years"] == [2010, 2012, 2014, 2016]
            and recent["years"] == [2018, 2020, 2022, 2024], "Changed year inventory")
    early_index = {(r["geography"], r["year"], r["role"], r["native_group"].strip()): (i, r)
                   for i, r in enumerate(early)}
    require(len(early_index) == len(early), "Duplicate early source key")
    rows, values = [], []
    for state_index, state in enumerate(states):
        state_values = []
        geography = "UNITED STATES" if state_index == 0 else state.upper()
        for group in GROUPS:
            cells = []
            for year in YEARS:
                status, rate, moe, pointer = STATUSES[4], None, None, None
                source = "early" if year < 2010 else "older" if year < 2018 else "recent"
                if source == "early":
                    role, native_group = EARLY_GROUPS[group]
                    found = early_index.get((geography, year, role, native_group))
                    if found is None and state_index == 0 and group == "Total" and year == 2008:
                        found = early_index.get((geography, year, "age", ".Total"))
                    if found is not None:
                        i, native = found
                        display = native["display"]
                        require(display["denominator"] == ("all_adults_18_plus" if year == 2004
                                                          else "citizen_adults_18_plus"),
                                "Changed native denominator")
                        status, rate, moe = (display["status"], display["rate_pct"],
                                             display["native_moe90_pp"])
                        pointer = f"/{i}/display"
                else:
                    data = displays[source]
                    require(len(data["groups"]) == len(set(data["groups"])), "Duplicate source group")
                    if group in data["groups"]:
                        group_index, year_index = data["groups"].index(group), data["years"].index(year)
                        native = data["values"][state_index][group_index][year_index]
                        pointer = f"/values/{state_index}/{group_index}/{year_index}"
                        if len(native) == 2:
                            status, rate, moe = STATUSES[0], *native
                        else:
                            require(len(native) == 1 and native[0] in NUMERIC_STATUSES,
                                    "Unknown native display status")
                            status = NUMERIC_STATUSES[native[0]]
                require(status in STATUSES, "Unknown source disposition")
                if status == STATUSES[0]:
                    require(type(rate) in (float, int) and 0 <= rate <= 100
                            and type(moe) in (float, int) and 0 <= moe <= 100, "Invalid native rate")
                    cells.append([rate, moe])
                else:
                    require(rate is None and moe is None, "Withheld source value exposed")
                    cells.append([-STATUSES.index(status)])
                rows.append({
                    "geography": state, "group": group, "year": year,
                    "election_type": "presidential" if year % 4 == 0 else "midterm",
                    "denominator": "all_adults_18_plus" if year == 2004 else "citizen_adults_18_plus",
                    "status": status, "reported_voting_pct": rate, "native_moe90_pp": moe,
                    "source_package": source, "source_display_pointer": pointer,
                })
            state_values.append(cells)
        values.append(state_values)
    display = {"states": states, "groups": list(GROUPS), "years": list(YEARS),
               "statuses": list(STATUSES), "values": values}
    summary = {"query_cells": len(rows), "geographies": len(states), "group_views": len(GROUPS),
               "years": list(YEARS), "dispositions": dict(Counter(r["status"] for r in rows)),
               "source_packages": {key: {"display_sha256": value[1], "complete_zip_sha256": value[2]}
                                   for key, value in SOURCES.items()}, "limits": list(LIMITS)}
    return rows, display, summary


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def package(root=ROOT, output=None):
    displays, members = read_sources(root)
    rows, display, summary = join(displays)
    members.update({path: (root / path).read_bytes() for path in CODE})
    members.update({"results/observations.csv": csv_bytes(rows),
                    "results/display.json": encoded(display),
                    "results/review.json": encoded(summary),
                    "METHODOLOGY.txt": ("\n\n".join(LIMITS) + "\n\n"
                        "Run python3 scripts/package-cps-unified-history.py after extraction. "
                        "Only Python standard-library modules are needed for the join. The three "
                        "included original complete ZIPs separately retain their native workbooks, "
                        "catalogs, receipts, original code, dependencies and reproduction instructions.\n").encode()})
    inventory = {name: {"bytes": len(raw), "sha256": digest(raw)}
                 for name, raw in sorted(members.items())}
    members["checksums.json"] = encoded(inventory)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(members.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 7, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw, compresslevel=9)
    raw = stream.getvalue()
    receipt = {"bytes": len(raw), "sha256": digest(raw), "members": len(members),
               "query_cells": len(rows), "complete_source_packages": 3}
    outputs = {"observations.csv": members["results/observations.csv"],
               "display.json": members["results/display.json"],
               "review.json": members["results/review.json"],
               "complete-analysis.zip": raw, "archive.json": encoded(receipt)}
    destination = Path(output) if output else root / DATA / "output"
    for name, content in outputs.items():
        if (destination / name).exists():
            require((destination / name).read_bytes() == content, f"Frozen output changed: {name}")
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        if not (destination / name).exists():
            (destination / name).write_bytes(content)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.root, args.output), indent=2))
