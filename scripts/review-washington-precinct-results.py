"""Reconcile Washington's complete 2026 county exports without inferring turnout."""

import argparse
from collections import defaultdict
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import tarfile
from urllib.parse import quote
import zipfile

from openpyxl import load_workbook

SUMMARY_FIELDS = ["Office Name", "Contest ID", "Ballot Name", "Choice ID", "Party", "Total"]
PRECINCT_FIELDS = ["Precinct"] + SUMMARY_FIELDS
ACCOUNTING = {"Ballots Cast", "Over Votes", "Under Votes"}
HOUSE = re.compile(r"Congressional District ([1-9][0-9]*) - U\.S\. Representative")
PARTIES = {"(Prefers Democratic Party)": "democratic_votes",
           "(Prefers Republican Party)": "republican_votes"}
API = "https://results.votewa.gov/results/public/api/elections/"
EXPORTS = "https://results.votewa.gov/cdn/results/"


def integer(value):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or isinstance(value, float) and not math.isfinite(value)
            or value < 0 or int(value) != value):
        raise ValueError("Missing or noninteger Washington count")
    return int(value)


def english(values):
    matches = [v["text"] for v in values or [] if v["languageId"] == "en"]
    if len(matches) != 1 or not isinstance(matches[0], str) or not matches[0]:
        raise ValueError("Missing or ambiguous native English identity")
    return matches[0]


def read_workbook(path, detailed):
    book = load_workbook(path, read_only=True, data_only=False)
    if book.sheetnames != ["Summary Results", "Precinct Results"]:
        raise ValueError("Unknown Washington export sheets")
    result = {}
    try:
        for sheet_name, fields in [("Summary Results", SUMMARY_FIELDS), ("Precinct Results", PRECINCT_FIELDS)]:
            expected = fields + (["Votes Allowed"] if detailed else [])
            values = iter(book[sheet_name].iter_rows(values_only=True))
            header = next(values)
            if list(header[:len(expected)]) != expected or any(v is not None for v in header[len(expected):]):
                raise ValueError("Unknown Washington export header")
            rows = []
            for values_row in values:
                if all(v is None for v in values_row):
                    continue
                if any(v is not None for v in values_row[len(expected):]):
                    raise ValueError("Unexpected nonempty Washington export column")
                row = dict(zip(expected, values_row))
                for field in expected:
                    value = row[field]
                    if field == "Total" and value is None:
                        continue
                    if field in {"Total", "Votes Allowed"}:
                        row[field] = integer(value)
                    elif value is None and field in {"Choice ID", "Party"}:
                        row[field] = ""
                    elif not isinstance(value, str) or (not value and field not in {"Choice ID", "Party"}):
                        raise ValueError("Missing or nontext Washington export identity")
                if (row["Choice ID"] == "") != (row["Ballot Name"] in ACCOUNTING):
                    raise ValueError("Ambiguous Washington candidate/accounting identity")
                rows.append(row)
            result[sheet_name] = rows
    finally:
        book.close()
    return result


def indexed(rows, fields, allow_missing=False):
    result = {}
    for row in rows:
        key = tuple(row[field] for field in fields)
        if row["Total"] is not None or not allow_missing:
            integer(row["Total"])
        if key in result:
            raise ValueError("Duplicate Washington reporting identity")
        result[key] = row
    return result


def reconcile_office(all_results, detailed, contest):
    keys = [field for field in SUMMARY_FIELDS if field != "Total"]
    for sheet_name, fields in [("Summary Results", keys), ("Precinct Results", ["Precinct"] + keys)]:
        original = indexed(all_results[sheet_name], fields, allow_missing=True)
        detail = indexed(detailed[sheet_name], fields)
        if original.keys() != detail.keys() or any(
                original[key]["Total"] is not None and original[key]["Total"] != detail[key]["Total"]
                for key in original):
            raise ValueError("Washington original export counts or identities disagree")
    summary = indexed(detailed["Summary Results"], keys)
    sums = defaultdict(int)
    precinct_groups = defaultdict(dict)
    for row in detailed["Precinct Results"]:
        key = tuple(row[field] for field in keys)
        sums[key] += row["Total"]
        group = (row["Precinct"], row["Office Name"], row["Contest ID"])
        if row["Ballot Name"] in precinct_groups[group]:
            raise ValueError("Ambiguous Washington choice label")
        precinct_groups[group][row["Ballot Name"]] = row
    if sums.keys() != summary.keys() or any(sums[key] != summary[key]["Total"] for key in summary):
        raise ValueError("Washington precinct totals do not reconcile to county summaries")
    candidates = [row for row in detailed["Summary Results"] if row["Choice ID"]]
    options = contest["summaryResults"]["ballotOptions"]
    by_id = {option["nativeId"]: option for option in options}
    if len(by_id) != len(options) or {row["Choice ID"] for row in candidates} != by_id.keys():
        raise ValueError("Washington native candidate IDs disagree")
    for row in candidates:
        option = by_id[row["Choice ID"]]
        party_names = option["party"]["name"]
        party = english(party_names) if party_names else ""
        if (row["Ballot Name"] != english(option["name"]) or row["Party"] != party
                or row["Total"] != integer(option["voteCount"])):
            raise ValueError("Washington native candidate name, party or count disagrees")
    if sum(row["Total"] for row in candidates) != integer(contest["voteTotal"]):
        raise ValueError("Washington native contest total disagrees")
    return precinct_groups


def reconcile_county(all_results, detailed, native, county_name, county_id):
    if native["election"]["electionDate"] != "2026-11-03":
        raise ValueError("Wrong Washington election")
    native_contests = {}
    for contest in native["ballotItems"]:
        name = english(contest["name"])
        if name in native_contests:
            raise ValueError("Duplicate native Washington contest")
        native_contests[name] = contest
    offices = {row["Office Name"] for book in [all_results, detailed] for rows in book.values() for row in rows}
    offices.update(native_contests)
    precinct_groups, office_audits = {}, {}
    for office in sorted(offices):
        try:
            if office not in native_contests:
                raise ValueError("Missing native Washington contest")
            books = [{name: [row for row in rows if row["Office Name"] == office] for name, rows in book.items()}
                     for book in [all_results, detailed]]
            groups = reconcile_office(books[0], books[1], native_contests[office])
            office_audits[office] = dict(status="reconciled", missing_original_count_cells=sum(
                row["Total"] is None for rows in books[0].values() for row in rows))
            if HOUSE.fullmatch(office):
                precinct_groups.update(groups)
        except ValueError as error:
            if HOUSE.fullmatch(office):
                raise ValueError(office + ": " + str(error)) from error
            office_audits[office] = dict(status="not_reconciled", reason=str(error))
    house_rows = []
    for (precinct, office, contest_id), choices in precinct_groups.items():
        match = HOUSE.fullmatch(office)
        if not match:
            continue
        if not ACCOUNTING <= choices.keys() or any(row["Votes Allowed"] != 1 for row in choices.values()):
            raise ValueError("Incomplete or non-single-seat Washington House accounting")
        candidates = [row for row in choices.values() if row["Choice ID"]]
        total = sum(row["Total"] for row in candidates)
        overvotes, undervotes = [choices[name]["Total"] for name in ["Over Votes", "Under Votes"]]
        ballots = choices["Ballots Cast"]["Total"]
        if ballots != total + overvotes + undervotes:
            raise ValueError("Washington House ballot accounting disagrees")
        counts = dict(democratic_votes=0, republican_votes=0, other_votes=0)
        for row in candidates:
            counts[PARTIES.get(row["Party"].strip(), "other_votes")] += row["Total"]
        house_rows.append(dict(year=2026, state_code="WA", state="Washington", county=county_name,
            county_source_id=county_id, precinct=precinct, office="U.S. House",
            congressional_district=match[1], contest_source_id=contest_id,
            key="WA-" + county_id + "-" + quote(precinct, safe="") + "-CD" + match[1],
            **counts, contest_votes=total, reported_ballots=ballots, overvotes=overvotes,
            undervotes=undervotes,
            margin_pp=100 * (counts["democratic_votes"] - counts["republican_votes"]) / total if total else None,
            scope="Unofficial native county reporting unit; candidate votes are not turnout."))
    if not house_rows:
        raise ValueError("No Washington House reporting rows")
    if len({row["key"] for row in house_rows}) != len(house_rows):
        raise ValueError("Washington House reporting keys collide")
    return house_rows, dict(all_office_precinct_rows=len(detailed["Precinct Results"]),
        all_office_summary_rows=len(detailed["Summary Results"]), native_contests=len(native_contests),
        office_reviews=office_audits,
        house_reporting_rows=len(house_rows),
        house_candidate_totals={field: sum(row[field] for row in house_rows)
            for field in ["democratic_votes", "republican_votes", "other_votes", "contest_votes"]},
        validated_scope="U.S. House only; see separate per-office reviews for other contests",
        all_nonmissing_original_house_counts_agree=True, all_house_precinct_sums_reconcile=True,
        all_native_house_candidate_names_ids_parties_counts_reconcile=True)


def verified_file(path, expected_url):
    receipt = json.loads(path.with_name(path.name + ".receipt.json").read_bytes())
    raw = path.read_bytes()
    if (receipt["status"] != 200 or quote(receipt["url"], safe=":/%") != expected_url
            or receipt["bytes"] != len(raw) or receipt["sha256"] != hashlib.sha256(raw).hexdigest()):
        raise ValueError("Washington original source receipt changed: " + path.name)
    return raw


def archive_inputs(folder, output):
    buffer = io.BytesIO()
    inventory = {}
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_symlink():
                raise ValueError("Symlink in Washington original input")
            if not path.is_file():
                continue
            name, raw = path.relative_to(folder).as_posix(), path.read_bytes()
            inventory[name] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            item = tarfile.TarInfo(name)
            item.size, item.mode = len(raw), 0o644
            archive.addfile(item, io.BytesIO(raw))
    output.write_bytes(gzip.compress(buffer.getvalue(), mtime=0))
    return inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reference-cache", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive and args.archive.exists():
        raise ValueError("Refusing to overwrite Washington review output")
    if args.archive and not args.reference_cache:
        raise ValueError("A published review must retain the complete acquired reference originals")
    state_path = args.source_cache / "original-state-data.json"
    state = json.loads(state_path.read_bytes())
    receipt = next(r for r in json.loads(
        (args.source_cache / "original-state-response-receipts.json").read_bytes())
        if r["url"] == API + "washington/20261103/data")
    if (receipt["status"] != 200 or receipt["bytes"] != state_path.stat().st_size
            or receipt["sha256"] != hashlib.sha256(state_path.read_bytes()).hexdigest()
            or state["election"]["electionDate"] != "2026-11-03"
            or state["election"]["isPrimary"] is not False
            or state["election"]["isProduction"] is not True):
        raise ValueError("Incorrect Washington state source")
    children = state["jurisdiction"]["childLocalities"]
    if (len(children) != len({c["id"].casefold() for c in children})
            or len(children) != len({c["shortName"] for c in children}) or len(children) != 39
            or any(not re.fullmatch(r"[a-z]+(?:-[a-z]+)*-county-wa", c["shortName"]) for c in children)):
        raise ValueError("Incomplete Washington county inventory")
    counties, rows = {}, []
    for child in children:
        short = child["shortName"]
        try:
            folder = args.source_cache / short
            native = json.loads(verified_file(folder / "original-county-data.json", API + short + "/20261103/data"))
            if native["jurisdiction"]["id"].casefold() != child["id"].casefold():
                raise ValueError("Incorrect native county binding")
            if (native["election"]["isPrimary"] is not False or native["election"]["isProduction"] is not True
                    or native["election"]["jurisdictionId"].casefold() != child["id"].casefold()):
                raise ValueError("Incorrect native county election scope")
            reports = {r["reportName"]: r for category in native["election"]["publicReportCategories"]
                       for r in category["reports"]}
            books = {}
            for name, detailed in [("All Results Excel", False), ("Summary and Precinct Results Excel", True)]:
                blob = reports[name]["blobName"]
                if "/" in blob or "\\" in blob or ".." in blob:
                    raise ValueError("Unsafe Washington report filename")
                path = folder / blob
                verified_file(path, EXPORTS + native["jurisdiction"]["id"].lower() + "/" + quote(blob))
                books[detailed] = read_workbook(path, detailed)
            county_rows, audit = reconcile_county(books[False], books[True], native,
                                                  english(child["name"]), child["id"])
            rows.extend(county_rows)
            counties[short] = dict(status="counts_reconciled_geometry_not_reviewed", **audit)
        except (ValueError, KeyError, TypeError) as error:
            counties[short] = dict(status="review_failed_all_originals_retained", reason=str(error))
        county_audit = counties[short]
        print(short, county_audit["status"], county_audit.get("house_reporting_rows", 0),
              county_audit.get("reason", ""), flush=True)
    args.output.mkdir(parents=True)
    (args.output / "results.json.gz").write_bytes(gzip.compress(
        json.dumps(rows, separators=(",", ":")).encode(), mtime=0))
    audit = dict(status="partial_count_review_not_map_or_participation_approval", year=2026, state_code="WA",
        complete="no", source_url="https://results.votewa.gov/results/public/washington/20261103",
        source_updated=state["election"]["asOf"], publication="full_counts_download_only",
        candidate_results="partial_house_counts_reconciled", boundaries="acquired_exact_year_join_review_pending",
        join="withheld", validation="partial_counts_passed_map_withheld",
        expected_counties=39, counties=counties,
        reconciled_counties=sum(c["status"] == "counts_reconciled_geometry_not_reviewed" for c in counties.values()),
        house_reporting_rows=len(rows), source_cache_all_originals_retained=True,
        participation="not_inferred_from_candidate_counts",
        margin_definition="100 * (Democratic - Republican) / all candidate votes; positive is Democratic",
        notes="All 39 county APIs and 78 complete native Excel originals are retained. "
              "House candidate counts are accepted only after detailed precinct-to-summary reconciliation, "
              "native summary candidate ID/name/literal-party/count agreement, explicit-count agreement between exports, "
              "and single-seat House ballot accounting. Missing All Results cells remain missing; "
              "only separately explicit detailed-export counts are used, never a zero substitution. "
              "Non-House contest discrepancies remain in per-office audits. Whole counties with ambiguous House "
              "identities or House ballot-accounting discrepancies remain withheld. Complete 2026 General base "
              "and split geometry is archived, not yet approved for joining. No map, demographic participation "
              "or final turnout is inferred from these unofficial candidate counts.",
        next_action="Audit full base/split identity universes and explicit congressional districts; map only exact "
                    "complete county joins after validity/overlap review. Resolve King duplicate House labels, "
                    "Jefferson and Walla Walla House ballot accounting independently without allocations or repairs.",
        reproduction="Extract originals/native-counties.tar.gz and originals/official-discovery.tar.gz into "
                     "separate empty directories, then run the archived parser with --source-cache, "
                     "--reference-cache, --output and --archive pointing to new paths.")
    if args.archive:
        inputs = {}
        originals = args.output / "originals"
        originals.mkdir()
        inputs["native-counties"] = archive_inputs(args.source_cache, originals / "native-counties.tar.gz")
        inputs["official-discovery"] = archive_inputs(args.reference_cache, originals / "official-discovery.tar.gz")
        (args.output / "inputs.json.gz").write_bytes(gzip.compress(
            (json.dumps(inputs, indent=2) + "\n").encode(), mtime=0))
        (args.output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
        audit["original_files"] = sum(len(inventory) for inventory in inputs.values())
        audit["original_bytes"] = sum(item["bytes"] for inventory in inputs.values() for item in inventory.values())
        audit["candidate_totals"] = {field: sum(row[field] for row in rows)
            for field in ["democratic_votes", "republican_votes", "other_votes", "contest_votes"]}
        audit["complete_download_url"] = "https://github.com/hanshanley/margin_of_error/releases/download/" \
            "voter-precinct-washington-counts-20261105-02/complete-washington-2026-count-review-02.zip"
    (args.output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    if args.archive:
        checksums = {path.relative_to(args.output).as_posix(): dict(bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(args.output.rglob("*")) if path.is_file()}
        (args.output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
        args.archive.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
            for path in sorted(args.output.rglob("*")):
                if path.is_file():
                    item = zipfile.ZipInfo(path.relative_to(args.output).as_posix(), (2026, 11, 5, 0, 0, 0))
                    item.external_attr = 0o100644 << 16
                    archive.writestr(item, path.read_bytes())
        print("ARCHIVE", args.archive.stat().st_size, hashlib.sha256(args.archive.read_bytes()).hexdigest(), flush=True)
    print("WASHINGTON_REVIEW", audit["reconciled_counties"], "counties", len(rows), "House units", flush=True)


if __name__ == "__main__":
    main()
