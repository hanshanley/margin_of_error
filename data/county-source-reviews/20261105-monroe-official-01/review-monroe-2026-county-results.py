"""Reconcile Monroe's complete official county returns without approving maps."""

import argparse
from collections import defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import zipfile

from bs4 import BeautifulSoup
import fitz
from openpyxl import load_workbook


SOURCE_URL = "https://agencies2.monroecountypa.gov/ElectionResults/"
MODES = ("Election Day", "Mail-In/Absentee", "Provisional")
HEADERS = ("Contest", "Vote For", "Total Votes", "Precincts Reported",
           "Total Precincts", "Party", "Candidate", "Candidate Votes")


def integer(value):
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)", value):
        return int(value.replace(",", ""))
    raise ValueError(f"Missing or invalid explicit integer: {value!r}")


def checked_html(raw):
    soup = BeautifulSoup(raw, "html.parser")
    if re.search(r"\btest(?:ing)?\b", soup.get_text(" ", strip=True), re.I):
        raise ValueError("Source explicitly contains a test/testing notice")
    if "MONROE COUNTY PENNSYLVANIA" not in soup.get_text(" ", strip=True):
        raise ValueError("Wrong official county")
    return soup


def read_original(source, name):
    raw = (source / name).read_bytes()
    receipt = json.loads((source / (name + ".receipt.json")).read_bytes())
    if (receipt["status"] != 200 or receipt["bytes"] != len(raw)
            or receipt["sha256"] != hashlib.sha256(raw).hexdigest()):
        raise ValueError(f"Original bytes disagree with acquisition receipt: {name}")
    return raw, receipt


def county_summary(soup):
    if ([h.get_text(" ", strip=True) for h in soup.select("h2")] != ["2026 General Election"]
            or "11/3/2026" not in [h.get_text(" ", strip=True) for h in soup.select("h3")]
            or "Results are UNOFFICIAL" not in soup.get_text(" ", strip=True)):
        raise ValueError("Wrong election date, scope or publication status")
    labels = [h.get_text(" ", strip=True) for h in soup.select("h4")]

    def labeled(label, pattern):
        matches = [re.fullmatch(re.escape(label) + pattern, text) for text in labels]
        matches = [match[1] for match in matches if match]
        if len(matches) != 1:
            raise ValueError(f"Missing or ambiguous source observation: {label}")
        return matches[0]

    ballots = integer(labeled("Total Ballots Tabulated: ", r"([\d,]+)"))
    registered = integer(labeled("Eligible Registered Voters: ", r"([\d,]+)"))
    printed = float(labeled("Overall Turnout: ", r"(\d+\.\d+)%"))
    if not 0 < registered or ballots > registered or abs(100 * ballots / registered - printed) > .0051:
        raise ValueError("County ballot, registration or printed percentage disagreement")
    updates = re.findall(r"Last Updated:\s*(\d+/\d+/2026 \d+:\d+:\d+ [AP]M)",
                         soup.get_text(" ", strip=True))
    if len(updates) != 1:
        raise ValueError("Missing or ambiguous source update")
    return dict(year=2026, state_code="PA", county="Monroe", geography_level="county",
                total_ballots_tabulated=ballots, eligible_registered_voters=registered,
                native_printed_turnout_pct=printed, registered_turnout_pct=100 * ballots / registered,
                source_update_literal=updates[0], result_status="UNOFFICIAL")


def contest_scope(name):
    if name == "GOVERNOR AND LIEUTENANT GOVERNOR":
        return "governor", ""
    for prefix, office in [("REPRESENTATIVE IN CONGRESS", "us_house"),
                           ("SENATOR IN THE GENERAL ASSEMBLY", "state_senate"),
                           ("REPRESENTATIVE IN THE GENERAL ASSEMBLY", "state_house")]:
        match = re.fullmatch(re.escape(prefix) + r" (\d+)(?:ST|ND|RD|TH) DISTRICT", name)
        if match:
            return office, match[1]
    raise ValueError(f"Unreviewed contest scope: {name}")


def html_contest(table, soup):
    name = table.select_one("thead th").get_text(" ", strip=True).rstrip(" ▶")
    body = table.find("tbody", recursive=False)
    if body is None:
        raise ValueError("Missing native contest body")
    rows = body.find_all("tr", recursive=False)
    text = " ".join(row.get_text(" ", strip=True) for row in rows
                    if row.find("details") is None)
    if "Vote for not more than 1 Candidate" not in text:
        raise ValueError("Unexpected contest vote-for rule")
    reporting = re.findall(r"Precincts Returned (\d+)/(\d+)", text)
    totals = [integer(cells[1].get_text(strip=True)) for row in rows
              for cells in [row.find_all("td", recursive=False)]
              if len(cells) == 3 and cells[0].get_text(strip=True) == "Total"]
    if len(reporting) != 1 or len(totals) != 1:
        raise ValueError("Ambiguous native reporting counters or contest total")
    candidates = []
    for row in rows:
        cells = row.find_all("td", recursive=False)
        button = cells[0].select_one("button[data-bs-target] b") if len(cells) == 3 else None
        if button is None:
            continue
        candidate = button.get_text(" ", strip=True)
        party = cells[0].select_one("i")
        party = party.get_text(strip=True).strip("()") if party else ""
        count = integer(cells[1].get_text(strip=True))
        target = button.find_parent("button")["data-bs-target"]
        modals = soup.select(target)
        if len(modals) != 1:
            raise ValueError("Missing or ambiguous candidate-mode source")
        modal = modals[0]
        if modal.select_one("h5").get_text(" ", strip=True) != candidate:
            raise ValueError("Candidate-mode heading mismatch")
        values = [cell.get_text(" ", strip=True) for cell in modal.select(".modal-body label, .modal-body span")]
        if len(values) != 6 or tuple(values[::2]) != MODES:
            raise ValueError("Missing, duplicate or unreviewed ballot-mode columns")
        modes = dict(zip(MODES, map(integer, values[1::2])))
        if sum(modes.values()) != count:
            raise ValueError("Candidate ballot modes do not reconcile")
        candidates.append(dict(candidate_html=candidate, party_html=party, votes=count, modes=modes))
    if (not candidates or len({row["candidate_html"] for row in candidates}) != len(candidates)
            or sum(row["votes"] for row in candidates) != totals[0]):
        raise ValueError("Duplicate candidates or candidate/contest total disagreement")
    reported, total = map(integer, reporting[0])
    if reported > total:
        raise ValueError("Invalid native reporting counters")
    return name, candidates, dict(contest_votes=totals[0], precincts_reported=reported,
                                  precincts_total=total)


def native_units(soup, candidates, totals):
    tables = soup.select("table.table-bordered")
    if len(tables) != 1:
        raise ValueError("Missing or ambiguous native reporting-unit table")
    rows = tables[0].find_all("tr")
    header = [cell.get_text(" ", strip=True) for cell in rows[0].find_all("th")]
    if header != ["Districts"] + [row["candidate_html"] for row in candidates]:
        raise ValueError("Native unit candidate columns disagree")
    units = []
    for row in rows[1:]:
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        if len(cells) != len(header) or not cells[0]:
            raise ValueError("Incomplete native reporting-unit row")
        units.append((cells[0], list(map(integer, cells[1:]))))
    if len(units) != totals["precincts_total"] or len({name for name, _ in units}) != len(units):
        raise ValueError("Missing or duplicate native reporting units")
    if [sum(counts[i] for _, counts in units) for i in range(len(candidates))] != [
            row["votes"] for row in candidates]:
        raise ValueError("Native reporting-unit candidate vectors do not reconcile")
    return units


def review(source):
    raw, receipt = read_original(source, "monroe.html")
    if receipt["url"] != SOURCE_URL:
        raise ValueError("Wrong county source URL")
    soup = checked_html(raw)
    participation = county_summary(soup)
    workbook, workbook_receipt = read_original(source, "monroe-all-contests.xlsx")
    if workbook_receipt["url"] != SOURCE_URL.rstrip("/") + "?handler=Excel" or workbook_receipt["method"] != "POST":
        raise ValueError("Wrong declared complete-workbook export")
    book = load_workbook(io.BytesIO(workbook), read_only=True, data_only=True)
    if book.sheetnames != ["ElectionData"]:
        raise ValueError("Unreviewed workbook sheets")
    values = list(book.active.values)
    if tuple(values[0]) != HEADERS:
        raise ValueError("Native workbook column mismatch")
    sheet = {}
    for row in values[1:]:
        if len(row) != 8 or not all(isinstance(row[i], str) and row[i] for i in [0, 5, 6]):
            raise ValueError("Incomplete native workbook row")
        record = dict(zip(HEADERS, row))
        for field in [*HEADERS[1:5], HEADERS[-1]]:
            record[field] = integer(record[field])
        key = (row[0], row[6])
        if key in sheet:
            raise ValueError("Duplicate native workbook candidate identity")
        sheet[key] = record
    tables = {"county-candidate-results": [], "county-candidate-mode-counts": [],
              "native-unit-candidate-counts": [], "county-contest-totals": [],
              "county-office-party-totals": [], "county-participation": [participation]}
    consumed, partitions = set(), defaultdict(list)
    party_totals = defaultdict(int)
    contest_tables = soup.select("table:has(> thead)")
    for i, table in enumerate(contest_tables):
        name, candidates, totals = html_contest(table, soup)
        office, district = contest_scope(name)
        common = dict(year=2026, state_code="PA", county="Monroe", office=office,
                      district=district, native_contest=name,
                      source_update_literal=participation["source_update_literal"])
        original, original_receipt = read_original(source, f"monroe-contest-{i:02d}.html")
        link = table.select_one("thead a")["href"]
        if original_receipt["url"] != "https://agencies2.monroecountypa.gov" + link:
            raise ValueError("Contest original does not match the declared link")
        detail = checked_html(original)
        detail_tables = detail.select("table:has(> thead)")
        if len(detail_tables) != 1 or html_contest(detail_tables[0], detail) != (name, candidates, totals):
            raise ValueError("County and detail contest vectors disagree")
        units = native_units(detail, candidates, totals)
        partitions[office].append({label for label, _ in units})
        tables["county-contest-totals"].append(dict(common, **totals))
        for j, candidate in enumerate(candidates):
            matches = []
            for key, record in sheet.items():
                literal = record["Candidate"]
                display = " ".join(reversed(literal.split(", "))) if ", " in literal else literal
                if key[0] == name and display == candidate["candidate_html"]:
                    matches.append((key, record))
            if len(matches) != 1:
                raise ValueError("HTML candidate has no unique native workbook identity")
            key, record = matches[0]
            if (key in consumed or record["Candidate Votes"] != candidate["votes"]
                    or record["Total Votes"] != totals["contest_votes"]
                    or record["Precincts Reported"] != totals["precincts_reported"]
                    or record["Total Precincts"] != totals["precincts_total"] or record["Vote For"] != 1
                    or (record["Party"] != candidate["party_html"]
                        and not (record["Candidate"] == "Write-in" and record["Party"] == "Nonpartisan"
                                 and candidate["party_html"] == ""))):
                raise ValueError("Native workbook and HTML candidate fields disagree")
            consumed.add(key)
            identity = dict(common, candidate=record["Candidate"], party=record["Party"],
                            candidate_html=candidate["candidate_html"], party_html=candidate["party_html"])
            tables["county-candidate-results"].append(dict(identity, votes=candidate["votes"]))
            tables["county-candidate-mode-counts"].extend(
                dict(identity, native_mode=mode, votes=count) for mode, count in candidate["modes"].items())
            tables["native-unit-candidate-counts"].extend(
                dict(identity, native_unit=label, votes=counts[j]) for label, counts in units)
            party_totals[(office, record["Party"])] += candidate["votes"]
    if consumed != set(sheet):
        raise ValueError("Complete workbook contains unmatched rows")
    if len(partitions["governor"]) != 1:
        raise ValueError("Missing countywide reference contest")
    county_units = partitions["governor"][0]
    if set(partitions) != {"governor", "us_house", "state_senate", "state_house"}:
        raise ValueError("Unexpected county office scope")
    for parts in partitions.values():
        if set().union(*parts) != county_units or sum(map(len, parts)) != len(county_units):
            raise ValueError("District reporting units overlap or do not cover the county")
    for (office, party), votes in sorted(party_totals.items()):
        tables["county-office-party-totals"].append(dict(
            year=2026, state_code="PA", county="Monroe", office=office, party=party, candidate_votes=votes))
    pdf, _ = read_original(source, "monroe-act88.pdf")
    with fitz.open(stream=pdf, filetype="pdf") as document:
        text = " ".join(" ".join(page.get_text().split()) for page in document)
    match = re.search(r"Monroe County received a total of (\d+) Absentee and Mail-In ballots "
                      r"by 8:00 PM on November 3, 2026, Election Day", text)
    if not match:
        raise ValueError("Missing native Act88 election/mail-receipt observation")
    participation["act88_mail_ballots_received_by_election_day_deadline"] = integer(match[1])
    excluded, _ = read_original(source, "philadelphia.html")
    if not re.search(r"Testing in Progress", BeautifulSoup(excluded, "html.parser").get_text()):
        raise ValueError("Excluded Philadelphia testing observation changed; review separately")
    house_votes = sum(row["votes"] for row in tables["county-candidate-results"] if row["office"] == "us_house")
    audit = dict(status="reviewed_county_only_unofficial_counts", year=2026, state_code="PA",
                 county="Monroe", fully_complete=False, maps_approved=False,
                 source_url=SOURCE_URL, source_update_literal=participation["source_update_literal"],
                 table_rows={name: len(rows) for name, rows in tables.items()},
                 native_contests=len(contest_tables), native_reporting_units=len(county_units),
                 total_ballots_tabulated=participation["total_ballots_tabulated"],
                 eligible_registered_voters=participation["eligible_registered_voters"],
                 house_candidate_votes=house_votes,
                 scope_notes=[
                     "Monroe County only; not statewide Pennsylvania or an approved map.",
                     "All native workbook, HTML, candidate/mode and reporting-unit vectors reconcile.",
                     "House and state legislative district partitions cover the same native county units without overlap.",
                     "Candidate votes, including literal Nonpartisan write-ins, are not ballots or turnout.",
                     "The workbook's Nonpartisan write-in label and HTML's blank label remain separate native fields.",
                     "Act88 received mail ballots are not counted ballots or candidate mail votes.",
                     "Registered-voter participation uses only this county's explicit native denominator, not VEP or CPS.",
                     "All results remain unofficial; native reported/total counters are not final certification.",
                     "Philadelphia explicitly says Testing in Progress; every Philadelphia count is excluded.",
                     "No geometry, historical crosswalk, demographic estimates or new precinct coverage is approved.",
                     "Official factual returns; no blanket license claim is made for source pages or report design.",
                 ])
    return tables, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    tables, audit = review(args.source)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, rows in tables.items():
        with (args.output / (name + ".csv")).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (args.output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    shutil.copytree(args.source, args.output / "originals")
    shutil.copyfile(__file__, args.output / Path(__file__).name)
    files = sorted(path for path in args.output.rglob("*") if path.is_file())
    checksums = {path.relative_to(args.output).as_posix(): dict(
        bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in files}
    (args.output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(path for path in args.output.rglob("*") if path.is_file()):
            info = zipfile.ZipInfo(path.relative_to(args.output).as_posix())
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
