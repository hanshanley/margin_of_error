"""Private statewide history-record transitions from the frozen NC native archive."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import zipfile


SOURCE_SHA256 = "6e0d4fee2f0523ec0937d1939c56e2892f728624526b5d87337e26c8b7e8112c"
DATES = dict(zip(
    ("11/08/2016", "11/06/2018", "11/03/2020", "11/08/2022", "11/05/2024"),
    (2016, 2018, 2020, 2022, 2024)))
BITS = {year: 1 << i for i, year in enumerate(DATES.values())}


def summarize_masks(counts):
    if any(type(mask) is not int or not 1 <= mask < 32 or type(n) is not int or n <= 0
           for mask, n in counts.items()):
        raise ValueError("Invalid history-mask aggregate")
    total = sum(counts.values())
    years = {year: sum(n for mask, n in counts.items() if mask & bit) for year, bit in BITS.items()}
    comparisons = []
    for prior, current in ((2020, 2022), (2022, 2024)):
        matrix = Counter(dict.fromkeys(
            ("recorded_both", "recorded_prior_only", "recorded_current_only", "neither_recorded"), 0))
        earlier = 0
        older_bits = sum(bit for year, bit in BITS.items() if year < prior)
        for mask, n in counts.items():
            before, after = bool(mask & BITS[prior]), bool(mask & BITS[current])
            category = ("recorded_both" if before and after else
                        "recorded_prior_only" if before else
                        "recorded_current_only" if after else "neither_recorded")
            matrix[category] += n
            if not before and after and mask & older_bits:
                earlier += n
        if (sum(matrix.values()) != total
                or matrix["recorded_both"] + matrix["recorded_prior_only"] != years[prior]
                or matrix["recorded_both"] + matrix["recorded_current_only"] != years[current]):
            raise ValueError("Statewide history transitions do not reconcile")
        comparisons.append({
            "prior_year": prior, "current_year": current,
            "record_presence_matrix": dict(matrix),
            "positive_earlier_history_in_current_only_not_first_ever": earlier,
            "current_only_without_earlier_record_first_ever_unresolved": matrix["recorded_current_only"] - earlier,
            "recorded_current_among_recorded_prior_pct": (
                100 * matrix["recorded_both"] / years[prior] if years[prior] else None),
            "confirmed_previously_eligible_nonparticipants": None,
            "first_ever_voters": None,
            "candidate_choice_retention": None,
            "population_turnout_rate": None,
        })
    return {
        "state_code": "NC", "available_2016_through_2024_history_union_records": total,
        "unique_positive_history_records_by_year": years,
        "comparisons": comparisons,
        "population_method_validated": False,
        "public_release_qualified": False,
        "limitations": [
            "This is the statewide source-history universe, not a reconstruction of every historical registration or eligible resident.",
            "Historical retention/removal, migration, death and unmatched or changed identifiers can affect record presence.",
            "Absence of NC history does not prove national nonparticipation or first-ever voting.",
            "Positive earlier history rules out first-ever participation; the record window begins in 2016.",
            "Repeated same-ID/year history records are deduplicated, not counted as additional people.",
            "No 2026 record absence is used and no candidate choices are observed.",
            "Independent official election-time all-ballot controls are still required to qualify historical population coverage.",
        ],
    }


def reduce_rows(rows, connection, batch_size=20000):
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("Positive batch size required")
    connection.execute("CREATE TABLE history (id TEXT PRIMARY KEY, mask INTEGER NOT NULL) WITHOUT ROWID")
    audit = Counter()
    batch = []

    def flush():
        if batch:
            connection.executemany(
                "INSERT INTO history VALUES (?,?) ON CONFLICT(id) DO UPDATE SET mask=history.mask|excluded.mask",
                batch)
            batch.clear()

    for row in rows:
        audit["native_records"] += 1
        year = DATES.get(row["election_lbl"].strip())
        if year is None:
            continue
        if "GENERAL" not in row["election_desc"].upper():
            raise ValueError("Wrong election identity")
        audit[f"raw_general_{year}_records"] += 1
        identity = row["ncid"].strip()
        if not identity:
            audit[f"missing_identifier_{year}_records"] += 1
            continue
        batch.append((identity, BITS[year]))
        if len(batch) >= batch_size:
            flush()
    flush()
    connection.commit()
    masks = dict(connection.execute("SELECT mask,COUNT(*) FROM history GROUP BY mask"))
    return masks, dict(audit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or Path(__file__).resolve().parents[1] in args.output.resolve().parents:
        raise ValueError("Output must be new and outside the repository")
    digest = hashlib.sha256()
    with args.history_archive.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != SOURCE_SHA256:
        raise ValueError("Frozen statewide history differs")
    os.umask(0o077)
    args.output.mkdir(parents=True, mode=0o700)
    print(json.dumps({"phase": "source_verified", "state": "NC"}), flush=True)
    with tempfile.TemporaryDirectory(prefix="private-history-scratch-", dir=args.output) as temporary:
        with sqlite3.connect(str(Path(temporary) / "history.sqlite")) as connection:
            with zipfile.ZipFile(args.history_archive) as archive:
                members = [m for m in archive.infolist() if not m.is_dir()]
                if len(members) != 1:
                    raise ValueError("Expected one native history table")
                with archive.open(members[0]) as source:
                    buffered = io.BufferedReader(source)
                    encoding = "utf-16" if buffered.peek(4)[:2] in (b"\xff\xfe", b"\xfe\xff") else "latin-1"
                    rows = csv.DictReader(io.TextIOWrapper(buffered, encoding=encoding), delimiter="\t")
                    if not {"ncid", "election_lbl", "election_desc"} <= set(rows.fieldnames or []):
                        raise ValueError("Missing native history fields")
                    masks, audit = reduce_rows(rows, connection)
    result = summarize_masks(masks)
    result["source_sha256"] = SOURCE_SHA256
    result["native_audit"] = audit
    result["id_database_removed_after_reduction"] = True
    raw = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode()
    descriptor = os.open(args.output / "statewide-history.json",
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as target:
        target.write(raw)
    print(json.dumps({"phase": "completed", "native_records": audit["native_records"],
                      "results_sha256": hashlib.sha256(raw).hexdigest()}), flush=True)


if __name__ == "__main__":
    main()
