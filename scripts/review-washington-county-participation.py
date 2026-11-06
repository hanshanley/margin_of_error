"""Reconcile Washington county ballots against frozen state and county originals."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import tarfile
import zipfile

ARCHIVE_SHA256 = "4fcdabb811bae6c45256a1418d294a5dd2ccef13fbcfb6d3da444ee012f1ac68"
API = "https://results.votewa.gov/results/public/api/elections/"
ELECTION_FIELDS = (
    "id", "jurisdictionId", "electionDate", "name", "isPrimary", "isProduction",
    "isOfficialResults", "asOf", "lastUpdated", "publishDate", "publishVersionId",
    "ballotsCast", "totalVoters", "precinctsReporting", "precinctReportingStatus",
    "groupReportingStatus", "includePrecinctResults",
)


def integer(value):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0 or int(value) != value):
        raise ValueError("Missing or invalid native Washington count")
    return int(value)


def english(values):
    matches = [row["text"] for row in values if row["languageId"] == "en"]
    if len(matches) != 1 or not isinstance(matches[0], str) or not matches[0]:
        raise ValueError("Missing or ambiguous Washington identity")
    return matches[0]


def snapshot(election):
    return {field: election[field] for field in ELECTION_FIELDS}


def acquire_facts(path):
    raw = path.read_bytes()
    if len(raw) != 45339062 or hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Frozen Washington input archive changed")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        files = {member.name: member for member in archive if member.isfile()}
        receipts = []

        def read(name, url, receipt=None):
            body = archive.extractfile(files[name]).read()
            receipt = receipt or json.load(archive.extractfile(files[name + ".receipt.json"]))
            if (receipt["status"] != 200 or receipt["url"] != url
                    or receipt["bytes"] != len(body)
                    or receipt["sha256"] != hashlib.sha256(body).hexdigest()):
                raise ValueError("Washington response receipt mismatch: " + name)
            receipts.append({key: receipt[key] for key in
                             ("url", "status", "bytes", "sha256", "captured_at")})
            return json.loads(body)

        url = API + "washington/20261103/data"
        state_receipts = json.load(archive.extractfile(files["original-state-response-receipts.json"]))
        receipt = [row for row in state_receipts if row["url"] == url]
        if len(receipt) != 1:
            raise ValueError("Missing or duplicated Washington state receipt")
        state = read("original-state-data.json", url, receipt[0])
        counties = []
        for child in state["jurisdiction"]["childLocalities"]:
            short = child["shortName"]
            county = read(short + "/original-county-data.json", API + short + "/20261103/data")
            counties.append({
                "jurisdiction": {key: county["jurisdiction"][key] for key in ("id", "name", "shortName")},
                "election": snapshot(county["election"]),
                "voterTurnout": county["voterTurnout"],
            })
        return {
            "input_archive_sha256": ARCHIVE_SHA256,
            "state_jurisdiction": {key: state["jurisdiction"][key] for key in
                                   ("id", "name", "shortName", "childLocalities")},
            "state_election": snapshot(state["election"]),
            "state_locality_elections": [snapshot(row) for row in state["localityElections"]],
            "counties": counties,
            "response_receipts": receipts,
        }


def reconcile(facts):
    if facts["input_archive_sha256"] != ARCHIVE_SHA256:
        raise ValueError("Wrong Washington snapshot provenance")
    state = facts["state_jurisdiction"]
    if state["shortName"] != "washington" or english(state["name"]) != "Washington":
        raise ValueError("Wrong Washington state identity")
    children = state["childLocalities"]
    child_ids = {row["id"].lower(): row for row in children}
    localities = {row["jurisdictionId"].lower(): row for row in facts["state_locality_elections"]}
    counties = {row["jurisdiction"]["id"].lower(): row for row in facts["counties"]}
    if (len(children) != len(child_ids) or len(children) != 39
            or len(facts["state_locality_elections"]) != 39 or len(facts["counties"]) != 39
            or child_ids.keys() != localities.keys() or child_ids.keys() != counties.keys()
            or len({row["shortName"] for row in children}) != 39):
        raise ValueError("Missing, duplicated or mismatched Washington county")
    for election in [facts["state_election"]] + list(localities.values()) + [
            row["election"] for row in counties.values()]:
        if (election["electionDate"] != "2026-11-03" or election["isPrimary"] is not False
                or election["isProduction"] is not True or election["isOfficialResults"] is not False
                or english(election["name"]) != "2026 General"):
            raise ValueError("Wrong Washington election or native status")
    if facts["state_election"]["jurisdictionId"].lower() != state["id"].lower():
        raise ValueError("Wrong Washington statewide election binding")
    rows, units = [], []
    for identity, child in child_ids.items():
        native = counties[identity]
        election, statewide = native["election"], localities[identity]
        if (native["jurisdiction"]["shortName"] != child["shortName"]
                or native["jurisdiction"]["name"] != child["name"]
                or election["jurisdictionId"].lower() != identity
                or any(election[field] != statewide[field] for field in
                       ("id", "ballotsCast", "totalVoters", "electionDate",
                        "isPrimary", "isProduction", "isOfficialResults"))):
            raise ValueError("Independent Washington county/state records disagree")
        ballots = integer(election["ballotsCast"])
        registered = integer(election["totalVoters"])
        source_units = native["voterTurnout"]
        if (not source_units or len({unit["id"] for unit in source_units}) != len(source_units)
                or any(set(unit) != {"id", "precinctName", "ballotsCast", "voterTurnout",
                                     "voterRegistration"} for unit in source_units)):
            raise ValueError("Missing, duplicated or changed Washington unit inventory")
        unit_ballots = sum(integer(unit["ballotsCast"]) for unit in source_units)
        unit_registered = sum(integer(unit["voterRegistration"]) for unit in source_units)
        if (not registered or ballots > registered or registered != unit_registered
                or any(integer(unit["ballotsCast"]) != integer(unit["voterTurnout"])
                       or not isinstance(unit["precinctName"], str) or not unit["precinctName"]
                       for unit in source_units)):
            raise ValueError("Washington registration or native unit accounting disagrees")
        gap = ballots - unit_ballots
        if gap and not (child["shortName"] == "king-county-wa" and unit_ballots == 0 and gap > 0):
            raise ValueError("Unreviewed Washington county/unit ballot discrepancy")
        quality = ("Unofficial frozen county ballots; native totalVoters independently equals "
                   "the complete source-unit voterRegistration sum. Not CVAP, VEP, demographic "
                   "turnout, certification or a new map approval.")
        if gap:
            quality += (" King reports zero in every native unit ballot field despite its "
                        "nonzero county total; those ballots remain unallocated, not zero participation.")
        county = english(child["name"])
        rows.append(dict(year=2026, state_code="WA", county=county, county_id=child["id"],
            source_short_name=child["shortName"], ballots_cast=ballots, registered_voters=registered,
            registered_turnout_percent=100 * ballots / registered,
            native_total_voters=election["totalVoters"],
            source_is_official_results=election["isOfficialResults"],
            source_as_of=election["asOf"], source_last_updated=election["lastUpdated"],
            source_publish_date=election["publishDate"],
            state_locality_source_as_of=statewide["asOf"],
            state_locality_source_last_updated=statewide["lastUpdated"],
            source_unit_rows=len(source_units), source_unit_ballots=unit_ballots,
            source_unit_registrations=unit_registered, unallocated_county_ballots=gap,
            quality_flags=quality))
        for unit in source_units:
            units.append(dict(year=2026, state_code="WA", county=county, county_id=child["id"],
                source_unit_id=unit["id"], source_unit_name=unit["precinctName"],
                ballots_cast=integer(unit["ballotsCast"]),
                native_voter_turnout=integer(unit["voterTurnout"]),
                registered_voters=integer(unit["voterRegistration"]),
                quality_flags="Native zero ballot fields do not allocate King county ballots." if gap else ""))
    audit = dict(year=2026, state_code="WA", county_observations=len(rows),
        native_unit_observations=len(units), independently_matched_state_county_headers=len(rows),
        county_ballots_sum=sum(row["ballots_cast"] for row in rows),
        county_registered_sum=sum(row["registered_voters"] for row in rows),
        native_state_ballots=integer(facts["state_election"]["ballotsCast"]),
        native_state_total_voters=integer(facts["state_election"]["totalVoters"]),
        unallocated_county_ballots=sum(row["unallocated_county_ballots"] for row in rows),
        maps_approved=False, statewide_completion_approved=False, demographic_rates_approved=False,
        qualification="The native statewide ballot field is zero, not the county ballot sum. "
        "It is preserved, not repaired, used as statewide turnout or allocated to units. "
        "County observations have distinct source timestamps and are not certified final totals.")
    if (audit["county_observations"], audit["native_unit_observations"], audit["county_ballots_sum"],
            audit["county_registered_sum"], audit["native_state_ballots"],
            audit["native_state_total_voters"], audit["unallocated_county_ballots"]) != (
            39, 9588, 2266746, 5170951, 0, 5170951, 601199):
        raise ValueError("Frozen Washington participation inventory or accounting changed")
    return rows, units, audit


def build(facts, output):
    rows, units, audit = reconcile(facts)
    if output.exists():
        raise ValueError("Refusing to overwrite Washington participation output")
    output.mkdir(parents=True)
    for name, records in (("county-participation.csv", rows), ("native-unit-participation.csv", units)):
        with (output / name).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(records)
    for name, value in (("audit.json", audit),):
        (output / name).write_text(json.dumps(value, indent=2) + "\n")
    (output / "source-records.json.gz").write_bytes(gzip.compress(
        (json.dumps(facts, sort_keys=True, separators=(",", ":")) + "\n").encode(), mtime=0))
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    checksums = {path.name: dict(bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(output.iterdir())}
    (output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    with zipfile.ZipFile(output / "complete-washington-county-participation-01.zip", "x",
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path.suffix == ".zip":
                continue
            info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-archive", type=Path)
    source.add_argument("--facts", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    facts = acquire_facts(args.source_archive) if args.source_archive else json.loads(
        gzip.decompress(args.facts.read_bytes()))
    print(json.dumps(build(facts, args.output), indent=2))


if __name__ == "__main__":
    main()
