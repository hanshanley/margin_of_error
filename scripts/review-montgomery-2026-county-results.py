"""Reconcile Montgomery's official 2026 county reports, retaining native portions."""

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import zipfile

from bs4 import BeautifulSoup
import fitz


BASE = "https://gis.montcopa.org/opendata/GE2026/"
URLS = {
    "montgomery.html": "https://www.montgomerycountypa.gov/departments/voter-services/election-results",
    "montgomery-dashboard.html": BASE,
    "montgomery-results.json": BASE + "results.json",
    "vendor-portions.csv": BASE + "data/Colorado Export by Portion.csv",
    "ballot-data.txt": BASE + "data/Ballot_Data.txt",
    "montgomery-summary.pdf": "https://webapp07.montcopa.org/election/2026UnofficialGeneralElectionSummaryReport.pdf",
}
MODES = ("total", "Election Day", "Mail-in", "Provisional")
JSON_MODES = ("total_votes", "election_day", "mail_in", "provisional")
GOVERNOR = "Governor and Lieutenant Governor"
COMMISSION = "Conshohocken Borough Government Study Commission"
LIMITATIONS = [
    "Unofficial, still updating; 428/428 reporting applies only to Election Day in-person ballots.",
    "County counts only, not statewide Pennsylvania completion, demographic turnout or approved maps.",
    "Candidate votes, unresolved write-ins, ballots, registrations and returned mail remain separate.",
    "PDF Total Votes excludes its separately printed Unresolved Write-In lines; JSON and CSV omit those lines.",
    "Unresolved write-ins have no native party label; a blank party is not an invented Nonpartisan affiliation.",
    "Three native precincts have split portions; use exact parent plus Split_name, not parent-only deduplication.",
    "The vote-for-seven commission is PDF-only; its 6743 write-in selections are not 6743 ballots or voters.",
    "Native vendor Reporting_flag values are retained, not used to override the report's reporting status.",
    "Portion residuals remain unclassified; only county residual sums reconcile to printed unresolved write-ins.",
    "The PDF timestamp has no independently established timezone; JSON UTC timestamps remain separate.",
    "Ballot-processing returned, counted, pending and rejected counts are separate native observations.",
    "Native provisional zeroes are observations at this capture, not final certification.",
]


def integer(value):
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)", value):
        return int(value.replace(",", ""))
    raise ValueError(f"Missing or invalid explicit integer: {value!r}")


def equal_vectors(left, right, message):
    if set(left) != set(right) or any(left[key] != right[key] for key in left):
        raise ValueError(message)


def load_originals(source):
    receipts = json.loads((source / "receipts.json").read_bytes())
    if set(receipts) != set(URLS):
        raise ValueError("Incomplete source receipt inventory")
    originals = {}
    for name, url in URLS.items():
        raw = (source / name).read_bytes()
        receipt = receipts[name]
        if (receipt["url"] != url or receipt["status"] != 200 or receipt["bytes"] != len(raw)
                or receipt["sha256"] != hashlib.sha256(raw).hexdigest()):
            raise ValueError("Original byte/URL/status receipt mismatch: " + name)
        if re.search(rb"[ps]k\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", raw):
            raise ValueError("Source requires explicit token redaction before public packaging")
        originals[name] = raw
    return originals


def office(contest):
    if contest == GOVERNOR:
        return "governor_lieutenant_governor"
    for prefix, kind in [("Representative in Congress", "us_house"),
                         ("Senator in the General Assembly", "state_senate"),
                         ("Representative in the General Assembly", "state_house")]:
        if re.fullmatch(re.escape(prefix) + r" \d+(?:st|nd|rd|th) District", contest):
            return kind
    if contest in {COMMISSION + " Question", "Hatfield Township Referendum"}:
        return "ballot_question"
    if contest == COMMISSION:
        return "local_commission"
    raise ValueError("Unreviewed contest identity: " + contest)


def pdf_reports(raw):
    with fitz.open(stream=raw, filetype="pdf") as document:
        text = " ".join(" ".join(page.get_text().split()) for page in document)
    if ("Election Summary Report Montgomery County" not in text or "November 03, 2026 General Election" not in text
            or "UNOFFICIAL RESULTS" not in text or "still being updated" not in text
            or "precinct indicator applies only to ballots cast in person" not in text):
        raise ValueError("Wrong PDF election, county or counting status")
    stamps = set(re.findall(r"\d+/\d+/2026 \d+:\d+:\d+ [AP]M", text))
    if len(stamps) != 1:
        raise ValueError("Missing or inconsistent PDF timestamps")
    number = r"(?:\d{1,3}(?:,\d{3})*|\d+)"
    vector = " ".join(["(" + number + ")"] * 4)
    pattern = (r"Candidate Party Election Day Mail-in Provisional Total (.*?)"
               r"Total Votes " + vector +
               r" Election Day Mail-in Provisional Total Unresolved Write-In " + vector +
               r" Election Day Mail-in Provisional Total Times Cast " + vector +
               r" / (" + number + r") (\d+\.\d+)% Precincts Reported: (\d+) of (\d+)"
               r" \([\d.]+%\) (.*?) \(Vote for (\d+)\)")
    reports = {}
    for match in re.finditer(pattern, text):
        values = match.groups()
        candidates, remaining = [], values[0].strip()
        row_pattern = r"(.+?) (DEM|REP|LIB|GRE|PFP) " + vector
        option_pattern = r"(YES|NO) " + vector
        while remaining:
            row = re.match(row_pattern, remaining)
            option = re.match(option_pattern, remaining)
            if row:
                name, party, *counts = row.groups()
                consumed = row.end()
            elif option:
                name, *counts = option.groups()
                party, consumed = "", option.end()
            else:
                raise ValueError("Unparsed PDF candidate or party: " + remaining[:100])
            counts = tuple(map(integer, counts))
            if sum(counts[:3]) != counts[3]:
                raise ValueError("PDF candidate mode disagreement")
            candidates.append(dict(candidate=name, party=party, counts=(counts[3], *counts[:3])))
            remaining = remaining[consumed:].strip()
        listed, writeins, ballots = [
            tuple(map(integer, values[start:start + 4])) for start in (1, 5, 9)]
        for counts in (listed, writeins, ballots):
            if sum(counts[:3]) != counts[3]:
                raise ValueError("PDF summary mode disagreement")
        registered, printed, reported, units = integer(values[13]), values[14], integer(values[15]), integer(values[16])
        contest, selectable = values[17], integer(values[18])
        if contest in reports or reported > units or not 0 < registered or ballots[3] > registered:
            raise ValueError("Duplicated PDF contest or invalid participation")
        rate = (Decimal(100) * ballots[3] / registered).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        if rate != Decimal(printed):
            raise ValueError("PDF ballot/registration/printed rate disagreement")
        if tuple(sum(c["counts"][i] for c in candidates) for i in range(4)) != (listed[3], *listed[:3]):
            raise ValueError("PDF listed candidate totals disagree")
        reports[contest] = dict(candidates=candidates, listed=(listed[3], *listed[:3]),
            writeins=(writeins[3], *writeins[:3]), ballots=(ballots[3], *ballots[:3]),
            registered=registered, printed=printed, reported=reported, units=units,
            selectable=selectable, office=office(contest))
    if len(reports) != 25 or COMMISSION not in reports:
        raise ValueError("Incomplete PDF contest inventory")
    return reports, next(iter(stamps))


def review(originals):
    linking = BeautifulSoup(originals["montgomery.html"], "html.parser")
    dashboard = BeautifulSoup(originals["montgomery-dashboard.html"], "html.parser")
    links = {a["href"] for a in linking.select("a[href]")}
    if (BASE not in links or URLS["montgomery-summary.pdf"] not in links
            or dashboard.h1.get_text(" ", strip=True) != "General Election \u2013 November 3, 2026"
            or not dashboard.select_one('a[href="results.json"]')):
        raise ValueError("Missing county-declared native 2026 source chain")
    for soup in (linking, dashboard):
        if re.search(r"\btest(?:ing)?\s+(?:data|in progress|results)\b", soup.get_text(" ", strip=True), re.I):
            raise ValueError("Source explicitly contains test data")
    for path in ("./data/Colorado Export by Portion.csv", "./data/Ballot_Data.txt"):
        if path not in originals["montgomery-dashboard.html"].decode():
            raise ValueError("Original download not declared by native dashboard")
    data = json.loads(originals["montgomery-results.json"])
    meta = data["meta"]
    if (meta["title"] != "Montgomery County, PA - General Election 2026 Results"
            or meta["status"] != "unofficial" or meta["source"] != "Montgomery County Voter Services"
            or meta["vote_types"] != list(JSON_MODES[1:])
            or "Election Day" not in meta["notes"]):
        raise ValueError("Wrong native JSON election, status or reporting basis")
    reports, stamp = pdf_reports(originals["montgomery-summary.pdf"])
    stream = csv.DictReader(io.StringIO(originals["vendor-portions.csv"].decode("utf-8-sig"), newline=""))
    if len(stream.fieldnames) != 35 or stream.fieldnames[-1] != "":
        raise ValueError("Changed native vendor schema")
    rows = list(stream)
    native, json_native, candidates = Counter(), Counter(), Counter()
    portion_contests, identities = defaultdict(list), set()
    participation_fields = ("Reg_voters", "Selectable_Options") + tuple(
        mode + "_" + field for mode in MODES for field in ("ballots", "under_votes", "over_votes"))
    for row in rows:
        if None in row or row[""] != "" or row["Candidate_Type"] != "C":
            raise ValueError("Malformed vendor row or unreviewed candidate type")
        contest, name, party = row["Contest_title"], row["candidate_name"], row["Party_Code"]
        if contest not in reports or not name or not row["Precinct_name"]:
            raise ValueError("Unreviewed native candidate, unit or contest")
        counts = tuple(integer(row[mode + "_votes"]) for mode in MODES)
        if counts[0] != sum(counts[1:]):
            raise ValueError("Native candidate mode disagreement")
        identity = row["Precinct_name"], row["Split_name"], contest, row["candidate_id"]
        if identity in identities:
            raise ValueError("Duplicated native portion/candidate observation")
        identities.add(identity)
        for field in participation_fields:
            integer(row[field])
        if integer(row["Selectable_Options"]) != reports[contest]["selectable"]:
            raise ValueError("Native selectable-options disagreement")
        for field in ("ballots", "under_votes", "over_votes"):
            if integer(row["total_" + field]) != sum(integer(row[mode + "_" + field]) for mode in MODES[1:]):
                raise ValueError("Native ballot/accounting mode disagreement")
        native[(row["Precinct_name"], contest, name, party,
                integer(row["Reg_voters"]), integer(row["total_ballots"]), *counts)] += 1
        for i, count in enumerate(counts):
            candidates[(contest, name, party, i)] += count
        portion_contests[identity[:3]].append(row)
    for row in data["precinct_results"]:
        counts = tuple(integer(row[mode]) for mode in JSON_MODES)
        if counts[0] != sum(counts[1:]):
            raise ValueError("JSON candidate mode disagreement")
        json_native[(row["precinct"], row["contest"], row["candidate"], row["party"],
                     integer(row["registered_voters"]), integer(row["ballots_cast"]), *counts)] += 1
    equal_vectors(native, json_native, "Full native JSON/CSV row multisets disagree")
    pdf_candidates, json_candidates = {}, {}
    for contest, report in reports.items():
        for row in report["candidates"]:
            for i, count in enumerate(row["counts"]):
                key = contest, row["candidate"], row["party"], i
                if key in pdf_candidates:
                    raise ValueError("Duplicate PDF candidate identity")
                pdf_candidates[key] = count
    for contest in data["contests"]:
        name = contest["contest"]
        if name in json_candidates or name not in reports:
            raise ValueError("Duplicate or unknown JSON contest")
        json_candidates[name] = contest
        if integer(contest["total_votes"]) != reports[name]["listed"][0]:
            raise ValueError("JSON contest total disagreement")
    json_vector = {}
    for contest, result in json_candidates.items():
        for row in result["candidates"]:
            for i, mode in enumerate(JSON_MODES):
                key = contest, row["candidate"], row["party"], i
                if key in json_vector:
                    raise ValueError("Duplicate JSON candidate identity")
                json_vector[key] = integer(row[mode])
    equal_vectors(candidates, pdf_candidates, "CSV/PDF county candidate/party/mode vectors disagree")
    equal_vectors(candidates, json_vector, "CSV/JSON county candidate/party/mode vectors disagree")
    if (len(rows) != integer(meta["record_count"])
            or len(data["contests"]) != integer(meta["contest_count"])
            or len({r["Precinct_name"] for r in rows}) != integer(meta["precincts_total"])
            or integer(meta["precincts_total"]) != reports[GOVERNOR]["units"]
            or integer(meta["precincts_reporting"]) != reports[GOVERNOR]["reported"]):
        raise ValueError("Native inventory/reporting counters disagree")
    accounting, portion_records = [], {}
    for (parent, split, contest), observations in sorted(portion_contests.items()):
        first = observations[0]
        if any(any(row[field] != first[field] for field in participation_fields) for row in observations):
            raise ValueError("Repeated portion/contest participation fields disagree")
        record = dict(native_precinct=parent, native_split_name=split, contest=contest,
                      registered_voters=integer(first["Reg_voters"]))
        for mode in MODES:
            ballots, under, over = (integer(first[mode + "_" + field]) for field in ("ballots", "under_votes", "over_votes"))
            votes = sum(integer(row[mode + "_votes"]) for row in observations)
            residual = ballots - votes - under - over
            if residual < 0:
                raise ValueError("Negative unclassified portion residual")
            record.update({mode + "_ballots": ballots, mode + "_listed_candidate_votes": votes,
                           mode + "_under_votes": under, mode + "_over_votes": over,
                           mode + "_unclassified_residual": residual})
        accounting.append(record)
        if contest == GOVERNOR:
            portion_records[(parent, split)] = dict(native_precinct=parent, native_split_name=split,
                registered_voters=record["registered_voters"],
                **{mode + "_ballots": record[mode + "_ballots"] for mode in MODES})
    for record in accounting:
        portion = portion_records[(record["native_precinct"], record["native_split_name"])]
        if any(record[field] != portion[field] for field in
               ("registered_voters",) + tuple(mode + "_ballots" for mode in MODES)):
            raise ValueError("Native portion participation differs across contests")
    for contest, report in reports.items():
        if contest == COMMISSION:
            if report["candidates"] or report["selectable"] != 7:
                raise ValueError("Changed PDF-only commission scope")
            continue
        observations = [r for r in accounting if r["contest"] == contest]
        if sum(r["registered_voters"] for r in observations) != report["registered"]:
            raise ValueError("Portion registrations disagree with PDF contest")
        for i, mode in enumerate(MODES):
            if (sum(r[mode + "_ballots"] for r in observations) != report["ballots"][i]
                    or sum(r[mode + "_unclassified_residual"] for r in observations) != report["writeins"][i]):
                raise ValueError("Portion ballots/residual sums disagree with PDF ballots/write-ins")
    for kind in ("governor_lieutenant_governor", "us_house", "state_house"):
        partition = [(r["native_precinct"], r["native_split_name"]) for r in accounting
                     if office(r["contest"]) == kind]
        if len(partition) != len(set(partition)) or set(partition) != set(portion_records):
            raise ValueError("Office district partition does not cover the same county portions")
    candidate_rows, mode_rows, contest_rows, party_votes = [], [], [], Counter()
    for contest, report in sorted(reports.items()):
        entries = [dict(row, row_kind="listed_candidate" if report["office"] != "ballot_question" else "ballot_option")
                   for row in report["candidates"]]
        entries.append(dict(candidate="Unresolved Write-In", party="", counts=report["writeins"],
                            row_kind="unresolved_write_in"))
        for row in entries:
            record = dict(year=2026, state_code="PA", county_fips="42091", contest=contest,
                office=report["office"], selectable_options=report["selectable"], candidate=row["candidate"],
                party_literal=row["party"], row_kind=row["row_kind"], votes=row["counts"][0])
            candidate_rows.append(record)
            mode_rows.extend(dict(record, voting_mode=mode, votes=row["counts"][i])
                             for i, mode in enumerate(MODES) if i)
            if report["office"] != "ballot_question":
                party_votes[(report["office"], row["party"], row["row_kind"])] += row["counts"][0]
        observations = [r for r in accounting if r["contest"] == contest]
        contest_rows.append(dict(contest=contest, office=report["office"], selectable_options=report["selectable"],
            listed_candidate_votes=report["listed"][0], unresolved_write_in_votes=report["writeins"][0],
            ballots_cast=report["ballots"][0], registered_voters=report["registered"],
            native_printed_turnout_pct=report["printed"], native_precincts_reported=report["reported"],
            native_precincts_total=report["units"],
            native_under_votes=sum(r["total_under_votes"] for r in observations) if observations else "",
            native_over_votes=sum(r["total_over_votes"] for r in observations) if observations else ""))
    gov = reports[GOVERNOR]
    county = dict(year=2026, state_code="PA", county_fips="42091", county="Montgomery",
        ballots_cast=gov["ballots"][0], election_day_ballots=gov["ballots"][1],
        mail_in_ballots=gov["ballots"][2], provisional_ballots=gov["ballots"][3],
        registered_voters=gov["registered"], native_printed_turnout_pct=gov["printed"],
        result_status="UNOFFICIAL RESULTS", reporting_basis="Election Day in-person only",
        source_pdf_update_literal=stamp, source_pdf_timezone="not independently established",
        source_json_exported_utc=meta["results_exported_utc"], source_json_generated_utc=meta["generated_utc"],
        final_certified_turnout=False)
    processing = []
    for line in originals["ballot-data.txt"].decode("utf-8-sig").splitlines():
        if line.strip() in {"", ","}:
            continue
        match = re.fullmatch(r"(.+?) - ([\d,]+)", line)
        if not match:
            raise ValueError("Unparsed ballot-processing observation")
        processing.append(dict(native_measure=match[1], count=integer(match[2])))
    if len(processing) != 9 or len({r["native_measure"] for r in processing}) != 9:
        raise ValueError("Incomplete ballot-processing report")
    processed = {r["native_measure"]: r["count"] for r in processing}
    if processed["Absentee & Mail in Ballots Counted"] != county["mail_in_ballots"]:
        raise ValueError("Separate counted-mail observations disagree")
    tables = {
        "county-candidate-results.csv": candidate_rows,
        "county-candidate-mode-counts.csv": mode_rows,
        "county-office-party-totals.csv": [dict(year=2026, state_code="PA", county_fips="42091",
            office=kind, party_literal=party, row_kind=row_kind, votes=count)
            for (kind, party, row_kind), count in sorted(party_votes.items())],
        "county-contest-totals.csv": contest_rows,
        "county-participation.csv": [county],
        "county-ballot-processing.csv": processing,
        "native-portion-participation.csv": [portion_records[key] for key in sorted(portion_records)],
        "native-portion-contest-accounting.csv": accounting,
        "native-portion-candidate-counts.csv": [dict(source_row=i, **row) for i, row in enumerate(rows, 1)],
        "native-json-candidate-counts.csv": [dict(source_row=i, **row)
            for i, row in enumerate(data["precinct_results"], 1)],
    }
    audit = dict(status="original_backed_county_counts_unofficial", participation=county,
        native_json_contests=len(data["contests"]), native_pdf_contests=len(reports),
        native_parent_precincts=meta["precincts_total"], native_portions=len(portion_records),
        native_split_parents=sorted({parent for parent, split in portion_records if split}),
        native_candidate_rows=len(rows), native_explicit_zeroes=sum(r["total_votes"] == "0" for r in rows),
        native_reporting_flag_literals=dict(Counter(r["Reporting_flag"] for r in rows)),
        house_votes=[r for r in tables["county-office-party-totals.csv"] if r["office"] == "us_house"],
        source_json_metadata=meta, source_urls=URLS, limitations=LIMITATIONS,
        fully_complete=False, new_maps_approved=False, table_rows={k: len(v) for k, v in tables.items()})
    return tables, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    tables, audit = review(load_originals(args.source))
    args.output.mkdir(parents=True, exist_ok=False)
    for name, rows in tables.items():
        with (args.output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (args.output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    shutil.copytree(args.source, args.output / "originals")
    shutil.copyfile(__file__, args.output / Path(__file__).name)
    paths = sorted(p for p in args.output.rglob("*") if p.is_file())
    (args.output / "checksums.json").write_text(json.dumps({
        p.relative_to(args.output).as_posix(): dict(bytes=p.stat().st_size,
            sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths}, indent=2) + "\n")
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in args.output.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(args.output).as_posix())
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
