"""Reproduce the separately dated Monroe selected-fact package without network access."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil


SOURCE_SHA256 = "282b424181a4aa4a511cb828da0861f82656bed11283dedbf5c8f8346e705d52"
SOURCE_URL = "https://agencies2.monroecountypa.gov/ElectionResults/"
SOURCE_CLOCK = "11/6/2026 2:25:30 PM"
MODES = {"Election Day", "Mail-In/Absentee", "Provisional"}
IDENTITIES = {
    ("governor", ""): [
        ("JOSH SHAPIRO", "DEMOCRATIC"), ("STACY GARRITY", "REPUBLICAN"),
        ("KEN KRAWCHUK", "LIBERTARIAN"), ("Write-in", "")],
    ("us_house", "7"): [
        ("BOB BROOKS", "DEMOCRATIC"), ("RYAN MACKENZIE", "REPUBLICAN"), ("Write-in", "")],
    ("us_house", "8"): [
        ("PAIGE COGNETTI", "DEMOCRATIC"), ("ROB BRESNAHAN JR", "REPUBLICAN"), ("Write-in", "")],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def count(value):
    require(type(value) is int and value >= 0, "Invalid native integer count")
    return value


def checksum(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load(source):
    require(checksum(source)["sha256"] == SOURCE_SHA256, "Changed selected source facts")
    return json.loads(source.read_bytes())


def review(selected):
    require((selected["schema_version"], selected["year"], selected["state_code"],
             selected["county"], selected["county_fips"]) == (1, 2026, "PA", "Monroe", "42089"),
            "Wrong selected observation identity")
    participation = selected["participation"]
    require(participation["source_update_literal"] == SOURCE_CLOCK
            and participation["result_status"] == "UNOFFICIAL"
            and participation["total_ballots_tabulated"] == 61587
            and participation["eligible_registered_voters"] == 118818
            and participation["native_printed_turnout_pct"] == 51.83,
            "Changed participation scope, clock or controls")
    require(selected["county_receipt"]["url"] == SOURCE_URL, "Wrong county source")
    receipts = [selected["county_receipt"]]
    units, rows, seen = {}, [], set()
    for contest in selected["contests"]:
        key = contest["office"], contest["district"]
        require(key in IDENTITIES and key not in seen, "Wrong or duplicate selected contest")
        seen.add(key)
        candidates = contest["candidates"]
        require([(row["candidate_html"], row["party_html"]) for row in candidates] == IDENTITIES[key],
                "Changed literal candidate or party inventory")
        require(contest["source_updated_at"] == SOURCE_CLOCK, "Mixed source clocks")
        totals = contest["totals"]
        require(count(totals["contest_votes"]) == sum(count(row["votes"]) for row in candidates),
                "Candidate totals do not reconcile")
        for candidate in candidates:
            require(set(candidate["modes"]) == MODES
                    and sum(count(value) for value in candidate["modes"].values()) == candidate["votes"],
                    "Candidate mode counts do not reconcile")
        native_units = contest["reporting_units"]
        names = [row["name"] for row in native_units]
        require(all(isinstance(name, str) and name.strip() for name in names)
                and len(set(names)) == len(names)
                and len(names) == count(totals["precincts_reported"]) == count(totals["precincts_total"]),
                "Incomplete or duplicate native reporting units")
        for unit in native_units:
            require(len(unit["candidate_counts"]) == len(candidates), "Wrong native candidate width")
            for value in unit["candidate_counts"]:
                count(value)
        require([sum(unit["candidate_counts"][i] for unit in native_units)
                 for i in range(len(candidates))] == [row["votes"] for row in candidates],
                "Reporting-unit candidate counts do not reconcile")
        units[key] = set(names)
        receipt = contest["receipt"]
        require(receipt["url"].startswith(SOURCE_URL + "Contest?"), "Wrong detail source")
        receipts.append(receipt)
        if key[0] == "us_house":
            for candidate in candidates:
                rows.append(dict(year=2026, state_code="PA", county_fips="42089",
                    county="Monroe", office="us_house", district=key[1],
                    candidate=candidate["candidate_html"], party=candidate["party_html"],
                    votes=candidate["votes"]))
    require(seen == set(IDENTITIES), "Incomplete selected contest inventory")
    require(len(units["governor", ""]) == 55 and len(units["us_house", "7"]) == 3
            and len(units["us_house", "8"]) == 52
            and not units["us_house", "7"] & units["us_house", "8"]
            and units["us_house", "7"] | units["us_house", "8"] == units["governor", ""],
            "House reporting units do not form the complete disjoint county cover")
    require(len({receipt["url"] for receipt in receipts}) == 4
            and all(receipt["status"] == 200 and receipt["method"] == "GET"
                    and receipt["url"] == receipt["final_url"]
                    and count(receipt["bytes"]) > 0
                    and len(receipt["sha256"]) == 64 for receipt in receipts),
            "Incomplete source receipts")
    audit = dict(package_kind="selected_native_facts_v1", year=2026, state_code="PA",
        county="Monroe", county_fips="42089", selected_source_sha256=SOURCE_SHA256,
        source_url=SOURCE_URL, source_update_literal=SOURCE_CLOCK, source_update_timezone=None,
        result_status="UNOFFICIAL", house_candidate_votes=sum(row["votes"] for row in rows),
        participation=participation, selected_contests=3, native_reporting_unit_rows=110,
        native_unit_candidate_cells=385, participation_is_fixed_cohort=False,
        precinct_longitudinal_qualified=False, transition_estimate_supplied=False)
    return audit, rows, receipts


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def build(source, output):
    audit, rows, receipts = review(load(source))
    require(not output.exists(), "Refusing to overwrite an existing package")
    output.mkdir(parents=True)
    shutil.copyfile(source, output / "selected-source-facts.json")
    write(output / "audit.json", audit)
    write(output / "source-receipts.json", receipts)
    with (output / "county-candidate-results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    write(output / "methodology-review.json", {
        "selection": "Complete used factual county participation, governor and both House tables: "
                     "all candidate, method and reporting-unit counts and four source receipts. "
                     "Governor units establish the current House partition, not a historical crosswalk. "
                     "No source HTML, newly acquired workbook, unrelated contest or personal data.",
        "native_verification": "Before selection, independent offline HTMLParser extraction checked "
                               "all four frozen originals, 110 unit rows and 385 unit-candidate cells. "
                               "This package reproduces selected facts, not a new native acquisition.",
        "source_precedence": "The November 6 observation is separate from the preserved older official "
                             "package. Never combine older participation with these candidate vectors. "
                             "Provider district major-party vectors must agree before county replacement; "
                             "official write-ins replace the provider's omitted other votes.",
        "literal_party": "Write-in has a blank native HTML party. It is not the older workbook's "
                         "Nonpartisan label. No party is inferred.",
        "literal_name_alias": {
            "district": "PA-08", "official": "ROB BRESNAHAN JR", "provider": "Rob Bresnahan",
            "basis": "The older frozen official package also names BRESNAHAN JR, ROB. "
                     "Only this literal suffix difference was reviewed; no general name waiver."},
        "limitations": [
            "UNOFFICIAL snapshot; source update timezone is not supplied.",
            "Registered voters are a changing administrative denominator, not VEP or a fixed cohort.",
            "Candidate totals are not ballots. Source-reported units do not establish final completeness.",
            "No new map approval, historical precinct identity, individual switching or staying-home estimate.",
            "Provider state/district tables remain separate, not composite county sums."],
        "reproduction": "Run python3 test-review-monroe-house-selection.py, then "
                        "python3 review-monroe-house-selection.py --source selected-source-facts.json "
                        "--output NEW_DIRECTORY. Compare every checksummed member. No network required.",
    })
    for name in ["review-monroe-house-selection.py", "test-review-monroe-house-selection.py"]:
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    write(output / "checksums.json", {path.name: checksum(path) for path in sorted(output.iterdir())})
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2))
