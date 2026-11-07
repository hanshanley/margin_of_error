"""Reconcile frozen Clark native turnout counts without inferring voter transitions."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.parse import unquote


MODES = ("Election Day", "Early Vote", "Mail")
MANIFEST_SHA256 = "0b0e404ba1b746c6e717b173a78ce8ecd337dd49f70cd6cad5d80c8ad74a7598"
REPORTS = (
    (2020, "PRESIDENT", "2020/154.txt", "2020/153.pdf"),
    (2022, "UNITED STATES SENATE", "2022/200.txt", "2022/199.pdf"),
    (2024, "PRESIDENT", "2024/082.txt", "2024/081.pdf"),
    (2024, "UNITED STATES SENATE", "2024/200.txt", "2024/199.pdf"),
)
LIMITATIONS = [
    "Counts are native Turnout fields in the selected contest statements, not candidate votes.",
    "Do not assume different contests contain the same electorate or add repeated contest counts.",
    "Registration repeats across modes; retain it only once per native reporting unit.",
    "Registration timing and eligibility definitions are not independently qualified denominators.",
    "Some native units report turnout above registration; retain them, without a turnout rate.",
    "Precinct codes are source reporting identifiers, not a cross-year boundary crosswalk.",
    "Native footer percentages are preserved but not used; some are 0.0% despite positive counts.",
    "Candidate columns, including suppressed values, are neither extracted nor reconstructed.",
    "Paired PDF/Data agreement is a source-consistency check, not independent outcome evidence.",
    "No separate certification review, 2026 observation, demographic rate or voter linkage is supplied.",
]


def integer(value):
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]*", value):
        raise ValueError("Missing or invalid native registration/turnout count")
    return int(value)


def statement(raw):
    try:
        rows = list(csv.reader(
            io.StringIO(raw.decode("utf-8-sig"), newline=""),
            skipinitialspace=True, strict=True))
    except (UnicodeError, csv.Error) as error:
        raise ValueError("Malformed native statement") from error
    header = ["Precinct", "Tally Type", "Registration", "Turnout", "Total Votes"]
    if not rows or rows[0][:5] != header or len(rows[0]) <= 5:
        raise ValueError("Wrong native statement header")
    offsets = [i for i, row in enumerate(rows) if row[:1] == ["Totals"]]
    if len(offsets) != 1:
        raise ValueError("Missing or duplicate native footer")
    offset = offsets[0]
    data, footer = rows[1:offset], rows[offset:]
    if (not data or len(data) % 4
            or any(len(row) != len(rows[0]) for row in data)
            or len(footer) != 4
            or footer[0] != ["Totals", "Tally Type", "# Voters", "Voters/Turnout"]
            or any(len(row) != 3 for row in footer[1:])
            or tuple(row[0] for row in footer[1:]) != MODES):
        raise ValueError("Incomplete native reporting-unit or footer structure")
    units, seen = [], set()
    for offset in range(0, len(data), 4):
        group = data[offset:offset + 4]
        code = group[0][0]
        if (not re.fullmatch(r"[0-9]{4}", code) or code in seen
                or any(row[0] != code for row in group)
                or tuple(row[1] for row in group) != ("Totals",) + MODES):
            raise ValueError("Duplicate, invalid or misordered native reporting unit")
        seen.add(code)
        registrations = [integer(row[2]) for row in group]
        turnouts = [integer(row[3]) for row in group]
        if len(set(registrations)) != 1 or turnouts[0] != sum(turnouts[1:]):
            raise ValueError("Native unit registration or turnout modes do not reconcile")
        units.append({
            "native_precinct_id": code,
            "native_registration": registrations[0],
            "native_turnout": turnouts[0],
            "native_turnout_by_mode": dict(zip(MODES, turnouts[1:])),
            "turnout_exceeds_registration": turnouts[0] > registrations[0],
            "qualified_turnout_rate": None,
        })
    native_footer = {}
    for mode, value, percentage in footer[1:]:
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?%", percentage):
            raise ValueError("Invalid native footer percentage")
        count = integer(value)
        if sum(row["native_turnout_by_mode"][mode] for row in units) != count:
            raise ValueError("Native reporting units disagree with the mode footer")
        native_footer[mode] = {"native_turnout": count, "native_percentage_unused": percentage}
    total = sum(row["native_turnout"] for row in units)
    if total != sum(row["native_turnout"] for row in native_footer.values()):
        raise ValueError("Native total turnout disagrees with the footer")
    return {
        "native_reporting_units": len(units),
        "native_turnout": total,
        "summed_native_registration_once_per_unit": sum(row["native_registration"] for row in units),
        "native_footer": native_footer,
        "turnout_exceeds_registration_units": sum(row["turnout_exceeds_registration"] for row in units),
        "qualified_turnout_rate": None,
        "units": units,
    }


def frozen(root, key, receipt, url):
    raw = gzip.decompress((root / "originals" / (key + ".gz")).read_bytes())
    if (receipt.get("url") != url or unquote(receipt.get("resolved_url", "")) != unquote(url)
            or receipt.get("status") != 200 or receipt.get("method", "GET") != "GET"
            or receipt.get("bytes") != len(raw)
            or receipt.get("sha256") != hashlib.sha256(raw).hexdigest()):
        raise ValueError("Changed or incorrectly scoped frozen Clark source")
    return raw


def contest_scope(president, senate):
    indexed = [{row["native_precinct_id"]: row for row in result["units"]}
               for result in (president, senate)]
    shared = set(indexed[0]) & set(indexed[1])
    fields = ("native_registration", "native_turnout", "native_turnout_by_mode")
    differences = [
        code for code in sorted(shared)
        if any(indexed[0][code][field] != indexed[1][code][field] for field in fields)
    ]
    return {
        "year": 2024,
        "shared_native_reporting_units": len(shared),
        "shared_units_with_different_participation_fields": differences,
        "president_only_units": [indexed[0][code] for code in sorted(set(indexed[0]) - shared)],
        "senate_only_units": [indexed[1][code] for code in sorted(set(indexed[1]) - shared)],
        "president_minus_senate_native_turnout": president["native_turnout"] - senate["native_turnout"],
        "same_electorate_qualified": False,
        "reason": "Keep literal contest scope; do not infer why a unit is absent or allocate its voters.",
    }


def review(root):
    manifest_raw = (root / "sources.json").read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Require the complete reviewed Clark source manifest")
    manifest = json.loads(manifest_raw)
    observations = []
    for year, contest, data_key, pdf_key in REPORTS:
        name = contest.replace(" ", "%20")
        base = f"https://elections.clarkcountynv.gov/electionresultsTV/SOV/{str(year)[2:]}G/{name}"
        raw = frozen(root, data_key, manifest[data_key], base + ".txt")
        pdf = frozen(root, pdf_key, manifest[pdf_key], base + ".pdf")
        if not pdf.startswith(b"%PDF-"):
            raise ValueError("Paired source is not a native PDF")
        observations.append({
            "year": year, "native_contest": contest, **statement(raw),
            "source_receipts": {data_key: manifest[data_key], pdf_key: manifest[pdf_key]},
            "pdf_content_independently_verified": False,
        })
    return {
        "status": "native_statement_counts_reconciled_not_population_transition_estimates",
        "state_code": "NV", "county_name": "Clark", "county_fips": "32003",
        "source_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "observations": observations,
        "same_year_contest_scope": contest_scope(observations[2], observations[3]),
        "limitations": LIMITATIONS,
        "precinct_maps_qualified": False,
        "cross_year_precinct_comparisons_qualified": False,
        "all_county_ballot_universe_independently_qualified": False,
        "public_release_qualified": False,
        "measured_prior_voter_dropoff": None,
        "new_or_returning_voters": None,
        "party_switchers": None,
        "demographic_turnout_rate": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.exists() or output == repository or repository in output.parents:
        raise ValueError("Require a new private output outside the repository")
    result = review(args.source_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, separators=(",", ":"), ensure_ascii=True) + "\n")
    print(json.dumps({
        "output": str(output), "observations": len(result["observations"]),
        "native_unit_observations": sum(row["native_reporting_units"] for row in result["observations"]),
        "public_release_qualified": False,
    }))


if __name__ == "__main__":
    main()
