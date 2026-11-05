"""Archive actual Connecticut election originals without claiming reconciled precincts."""

import argparse
from collections import Counter
import csv
from datetime import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile


YEARS = {2026: "108", 2024: "91", 2022: "80", 2020: "54", 2018: "31", 2016: "1"}
BASE = "https://ctemspublic.tgstg.net/"
SOURCE = "https://portal.ct.gov/en/SOTS/Election-Services/Election-Results/Election-Results"
JSON_FILES = {
    "Lookupdata.json", "stateVotes_Electiondata.json", "election_Electiondata.json",
    "voterTurnout_Electiondata.json", "townVotes_Electiondata.json",
    "townStatus_Electiondata.json", "reports_Electiondata.json",
    "districts_Electiondata.json", "officePrecincts_Electiondata.json",
    "ballotQuestion_Electiondata.json", "candidateGrouping_Electiondata.json",
}
CANDIDATES = [
    "ElectionName", "TownName", "ElectionCategory", "ElectionDate", "TownClerk",
    "OfficeName", "CandidateName", "PartyName", "PollingPlaceName", "MachineCount",
    "Absentee", "Early Votes", "Same Day Registration (SDR)", "Unknown", "FinalCount",
]
REGISTRY = ["TownName", "Polling_Place_Name", "No.of Names on Registry",
            "No. Checked as Having Voted"]
MODES = [
    "TownName", "Polling_Place_Name", "Machine/Polling Place Total", "Absentee Total",
    "Military Total", "Overseas Total", "Early Votes Total",
    " Same Day Registration (SDR) Total", " Presidential Total", " Provisional Total",
]
QUESTIONS = ["Election", "ElectionDescription", "Town", "QuestionID", "Question",
             "Yes Votes", "No Votes", "NotooHigh", "NotooLow"]


def report_inventory(raw, year, towns):
    text = raw.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows or rows[:2] != [
        ["STATE OF CONNECTICUT OFFICE OF THE SECRETARY OF THE STATE"],
        ["Election Results by Voting District "],
    ]:
        raise ValueError("Wrong Connecticut voting-district report identity")
    positions = []
    for header in (CANDIDATES, REGISTRY, MODES, QUESTIONS):
        found = [i for i, row in enumerate(rows) if row == header]
        if len(found) != 1:
            raise ValueError("Missing or repeated native Connecticut report section")
        positions.append(found[0])
    if positions != sorted(positions) or positions[0] != 2:
        raise ValueError("Wrong native Connecticut report section order")
    sections = []
    for start, end, header, town_column, number_column in zip(
        positions[:3], positions[1:], (CANDIDATES, REGISTRY, MODES), (1, 0, 0), (9, 2, 2)
    ):
        records = [row for row in rows[start + 1:end] if row]
        if not records:
            raise ValueError("Empty native Connecticut candidate/registry/mode section")
        for row in records:
            if len(row) != len(header) + 1 or row[-1] != "":
                raise ValueError("Malformed native Connecticut candidate/registry/mode record")
            if row[town_column] not in towns or not row[8 if town_column else 1]:
                raise ValueError("Unknown native Connecticut town or missing polling label")
            if any(not value.isascii() or not value.removeprefix("-").isdecimal()
                   for value in row[number_column:-1]):
                raise ValueError("Missing or invalid native count; do not substitute zero")
            if town_column and (str(year) not in row[0] or str(year) not in row[3]):
                raise ValueError("Wrong Connecticut report election year")
        keys = Counter((row[town_column], row[8 if town_column else 1]) for row in records)
        section = dict(native_header=header, native_records=len(records),
                       native_record_widths=dict(Counter(map(len, records))),
                       unique_literal_town_polling_labels=len(keys),
                       negative_native_fields=[
                           dict(section_record=ordinal, field=header[column], source_value=value)
                           for ordinal, row in enumerate(records, 1)
                           for column, value in enumerate(row[:-1])
                           if column >= number_column and int(value) < 0
                       ])
        if town_column:
            house = [row for row in records if row[5].startswith("Representative in Congress ")]
            section.update(house_candidate_party_records=len(house),
                           native_mode_sum_discrepancies=sum(
                               sum(map(int, row[9:14])) != int(row[14]) for row in records),
                           house_native_mode_sum_discrepancies=sum(
                               sum(map(int, row[9:14])) != int(row[14]) for row in house))
        else:
            section["duplicate_literal_town_polling_labels"] = [
                dict(town=town, polling_label=label, records=count)
                for (town, label), count in keys.items() if count > 1
            ]
        sections.append(section)
    strict_error = None
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        list(reader)
    except csv.Error as error:
        strict_error = dict(physical_line=reader.line_num, error=str(error))
    return dict(sections=sections, full_report_strict_csv_error=strict_error,
                unreviewed_question_tail_csv_records=len(rows) - positions[3] - 1,
                notes="Default csv.reader permits native section inventory; strict CSV quoting "
                      "errors, including unescaped quotes in candidate names, are recorded. "
                      "Every original byte remains unchanged. Candidate-party lines "
                      "and repeated voting-location denominators are not merged. These checks "
                      "do not reconcile source summaries, native precinct IDs, fusion identities "
                      "or participation definitions. Negative native counts/adjustments are flagged "
                      "and preserved, never clamped. No precinct rates or geometry are produced.")


def election_originals(root, year, identity):
    receipt_paths = sorted(root.rglob("*.source.json"))
    originals, receipts = {}, {}
    for path in receipt_paths:
        name = path.relative_to(root).as_posix().removesuffix(".source.json")
        receipt = json.loads(path.read_bytes())
        raw = (root / name).read_bytes()
        if receipt["status_code"] != 200 or receipt["bytes"] != len(raw) or (
            receipt["sha256"] != hashlib.sha256(raw).hexdigest()
        ):
            raise ValueError("Changed or failed Connecticut original: " + name)
        if receipt.get("resolved_url", receipt["url"]) != receipt["url"] or not (
            receipt["url"] == SOURCE or receipt["url"].startswith(BASE)
        ):
            raise ValueError("Unexpected Connecticut source origin")
        prefix = BASE + "ng-app/data/election/"
        if receipt["url"].startswith(prefix) and not receipt["url"].startswith(prefix + identity + "/"):
            raise ValueError("Wrong Connecticut original election identity")
        originals[name], receipts[name] = raw, receipt
    required = JSON_FILES | {
        "Version.json", "official-voting-district-export-request.json", "official-voting-district-export",
    }
    if not required <= originals.keys():
        raise ValueError("Incomplete Connecticut originals; refuse a metadata-only archive")
    version = json.loads(originals["Version.json"])["Version"]
    prefix = f"{BASE}ng-app/data/election/{identity}/"
    if receipts["Version.json"]["url"] != prefix + "Version.json":
        raise ValueError("Wrong Connecticut version receipt")
    for name in JSON_FILES:
        if receipts[name]["url"] != f"{prefix}{version}/{name}":
            raise ValueError("Mixed Connecticut versioned original identity")
        json.loads(originals[name])
    lookup = json.loads(originals["Lookupdata.json"])
    if lookup["election"]["ID"] != identity or (
        datetime.strptime(lookup["election"]["DT"], "%m/%d/%Y").year != year
    ):
        raise ValueError("Wrong Connecticut lookup election identity/date")
    election = json.loads(originals["election_Electiondata.json"])
    if election["ID"] != identity:
        raise ValueError("Wrong Connecticut summary election identity")
    request_name = "official-voting-district-export-request.json"
    body = receipts[request_name].get("request_body", {})
    if receipts[request_name]["url"] != BASE + "Default.aspx/GetVotingDistrictValues" or (
        receipts[request_name]["method"] != "POST" or body.get("electionID") != identity
    ):
        raise ValueError("Wrong Connecticut report request identity")
    requested = body.get("townID", "").split(",")
    if requested[-1:] != [""] or len(requested[:-1]) != len(set(requested[:-1])) or (
        set(requested[:-1]) != set(lookup["townIds"])
    ):
        raise ValueError("Incomplete Connecticut report town request")
    if receipts["official-voting-district-export"]["url"] != BASE + "Default.aspx?action=VotingDistrict":
        raise ValueError("Wrong Connecticut report response identity")
    inventory = report_inventory(originals["official-voting-district-export"], year,
                                 set(lookup["townIds"].values()))
    return originals, receipts, dict(
        year=year, state_code="CT", election_id=identity, version=version, complete="no",
        candidate_results="acquired_originals_review_pending",
        boundaries="not_acquired_in_this_batch", join="pending",
        validation="complete_source_bytes_and_candidate_registry_section_structure_verified",
        publication="full_originals_download_only", participation="not_reconciled",
        source_url=SOURCE, original_files=len(originals),
        original_bytes=sum(map(len, originals.values())), report_inventory=inventory,
        next_action="Reconcile full reports against versioned summaries; resolve native duplicate/"
                    "unmatched polling labels and explicit candidate-party fusion identities. "
                    "Independently define and reconcile registry/voted/mode scope before publishing "
                    "participation. Obtain correct-election geometry; no row-order or fuzzy joins.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable Connecticut source archive")
    originals, receipts, elections = {}, {}, {}
    for year, identity in YEARS.items():
        raw, sources, election = election_originals(args.cache_root / f"CT-{year}", year, identity)
        originals.update({f"{year}/{name}": body for name, body in raw.items()})
        receipts.update({f"{year}/{name}": receipt for name, receipt in sources.items()})
        elections[str(year)] = election
    args.output.mkdir(parents=True)
    for name, raw in originals.items():
        destination = args.output / "originals" / (name + ".gz")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(gzip.compress(raw, mtime=0))
    for name, value in {
        "sources.json": receipts,
        "acquisition.json": dict(
            state_code="CT", elections=elections, original_files=len(originals),
            original_bytes=sum(map(len, originals.values())),
            notes="Complete HTTP source bytes, including all-office candidate/party/mode reports "
                  "and separate registry/voted observations; not metadata-only. 2026 includes both "
                  "captured API versions, public application/export provenance and alternative "
                  "exports. The 26-byte XML stub is a failed attempt, not usable result data. "
                  "North Canaan's 2026 House report is 1,244 votes above both captured summary "
                  "versions; counts and place identities remain unreconciled. Original CSV "
                  "quoting defects and negative native adjustments are preserved. No map, demographic estimates, "
                  "eligible-population turnout rates or complete statewide coverage is claimed."),
    }.items():
        (args.output / name).write_text(json.dumps(value, separators=(",", ":"), ensure_ascii=True))
    (args.output / "checksums.json").write_text(json.dumps({
        path.relative_to(args.output).as_posix(): dict(bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(args.output.rglob("*")) if path.is_file()
    }, separators=(",", ":")))
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(args.output).as_posix(),
                                       date_time=(2026, 11, 5, 0, 0, 0))
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())
    print(json.dumps(dict(original_files=len(originals), elections=elections,
        archive_bytes=args.archive.stat().st_size,
        archive_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest()), indent=2))


if __name__ == "__main__":
    main()
