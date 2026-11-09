"""Convert held native CSV observations into complete, counts-only browser inputs."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SPECS = [
    ("AZ", "AZ-2026-native-counts", "precinct-participation.csv", 1763, 1),
    ("AR", "AR-2026-native-counts", "precinct-participation.csv", 2768, 82),
    ("WY", "WY-2026-native-counts", "precinct-counts.csv", 432, 0),
]


def count(value):
    if value == "":
        return None
    if not re.fullmatch(r"\d+", value):
        raise ValueError("Invalid native count; do not repair or substitute zero")
    number = int(value)
    if number > 2**53 - 1:
        raise ValueError("Native count exceeds exact browser integer precision")
    return number


def build(output):
    if output.exists():
        raise ValueError("Refuse to replace an immutable reporting-unit input")
    pointer = json.loads((ROOT / "public/precinct-results.json").read_bytes())
    reviews = [json.loads((ROOT / path).read_bytes()) for path in pointer["source_reviews"]]
    descriptors, bodies, receipt = {}, {}, {}
    for code, suffix, filename, expected_rows, expected_missing in SPECS:
        selected = [row for row in reviews if row.get("year") == 2026
                    and row.get("state_code") == code and row.get("data_directory", "").endswith(suffix)]
        if len(selected) != 1:
            raise ValueError("Missing or duplicate native source review")
        review = selected[0]
        directory = ROOT / review["data_directory"]
        path = directory / filename
        raw = path.read_bytes()
        checksum = json.loads((directory / "checksums.json").read_bytes())
        entries = checksum.get("files", checksum)
        if isinstance(entries, list):
            entries = {item["path"]: item for item in entries}
        expected = entries[filename]
        if len(raw) != expected["bytes"] or hashlib.sha256(raw).hexdigest() != expected["sha256"]:
            raise ValueError("Native reporting-unit input checksum changed")
        native = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        if len(native) != expected_rows:
            raise ValueError("Incomplete native reporting-unit inventory")
        rows = []
        for i, original in enumerate(native):
            if original["year"] != "2026" or original["state_code"] != code:
                raise ValueError("Incorrect native reporting-unit election")
            county, precinct = original["county"], original["precinct"]
            if not county or not precinct or original["turnout_rate"] != "":
                raise ValueError("Unknown reporting label or rate qualification")
            ballots = count(original["ballots"])
            registered = count(original["registered_voters"])
            flags = [original.get("quality") or "Native reporting-unit counts; rate and map remain withheld."]
            if ballots is None:
                flags.append("Native ballot total is missing, not zero.")
            if code == "WY":
                flags.append("The retained Washakie candidate-category conflict is not repaired; separate ballot counts remain unchanged.")
            rows.append({
                "key": f"{code}|native-csv-row-{i + 1}", "year": 2026, "state_code": code,
                "county": county, "precinct": f"{county} · {precinct}",
                "source_precinct_label": precinct, "source_csv_row": i + 2,
                "reporting_unit_kind": "native_virtual_reporting_unit"
                    if original.get("native_virtual_precinct") == "True" else "source_reporting_unit",
                "ballots": ballots, "registered": registered, "reported_pct": None,
                "basis": "Native reporting-unit counts, not a population or demographic turnout rate. "
                         "Registration definitions, ballot-mode scope and 2026 boundary joins remain unqualified.",
                "quality_flags": flags, "native_record": original,
                "source_url": review["source_url"],
            })
        if sum(row["ballots"] is None for row in rows) != expected_missing:
            raise ValueError("Native missingness changed; do not substitute zero")
        body = gzip.compress(json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode(), mtime=0)
        bodies[f"{code}.json.gz"] = body
        descriptors[code] = {
            "rows": len(rows), "sha256": hashlib.sha256(body).hexdigest(),
            "data_url": f"/participation-reporting-units/20261109-02/{code}.json.gz",
            "source_url": review["source_url"], "complete_download_url": review["complete_download_url"],
            "source_update_label": "See frozen native source package; no common source clock is inferred",
            "scope": f"All {len(rows)} native reporting-unit rows; {expected_missing} missing ballot totals remain NULL, "
                     "not zero. Native virtual/special units, registration fields and source conflicts are retained. "
                     "Do not sum reporting-unit registrations or infer a statewide/all-mode total. All rates remain withheld.",
            "geometry_note": "No approved 2026 precinct-reference join for these observations; no older boundaries "
                             "or pooled-ballot allocations are substituted.",
        }
        receipt[code] = {
            "source_file": str(path.relative_to(ROOT)), "source_bytes": len(raw),
            "source_sha256": hashlib.sha256(raw).hexdigest(), "rows": len(rows),
            "missing_ballots": expected_missing,
            "observed_ballot_sum_not_statewide_estimate": sum(row["ballots"] or 0 for row in rows),
            "output_sha256": hashlib.sha256(body).hexdigest(),
        }
    output.mkdir(parents=True)
    for name, body in bodies.items():
        (output / name).write_bytes(body)
    (output / "source-index-additions.json").write_text(json.dumps(descriptors, indent=2) + "\n")
    (output / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)
