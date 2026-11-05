"""Reconcile Bucks reports and a token-redacted HTML snapshot, without new maps."""

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

from bs4 import BeautifulSoup
import fitz


INDEX = "https://buckscounty.gov/1206/Election-Results"
SOURCE = "https://www.livevoterturnout.com/ENR/buckspaenr/24/"
URLS = {
    "official-results-index.html": INDEX,
    "native-results.redacted.html": SOURCE + "en/cyu3o_Index_24.html",
    "summary.csv": SOURCE + "summary_24.csv",
    "native-units.csv": SOURCE + "precincts_24.csv",
    "contests.csv": SOURCE + "contests_24.csv",
    "summary.pdf": SOURCE + "summary_24.pdf",
}
MODES = ["Absentee and Mail-In Votes", "Election Day Votes", "Provisional Votes"]
SUMMARY_HEADERS = ["Contest Name", "Candidate Name", "Party", *MODES, "Total Votes",
                   "Number Of Precincts", "Precincts Reported"]
UNIT_HEADERS = ["Precinct", "Contest Name", "Candidate Name", "Votes", "Voter Turnout"]
CONTEST_HEADERS = ["Contest Name", "Number Of Precincts", "Precincts Reported", "Ballots Cast"]
HTML_PARTIES = {"Dem": "DEM", "Rep": "REP", "Lib": "LIB", "Nonpart": "NONPART",
                "Fwi": "Fwi", "Ind": "Ind"}
HOUSE = "REPRESENTATIVE IN CONGRESS 1ST"
LIMITATIONS = [
    "Bucks County only; not statewide Pennsylvania coverage or district-wide totals outside the county.",
    "UNOFFICIAL RESULTS; both Absentee and Mail-In and In-Person Ballots remain Partially Reported.",
    "All native reporting counters reconcile, but they do not establish completed ballot counting.",
    "Candidate/write-in votes are separate from ballots, registrations and demographic turnout.",
    "CSV and accessible-HTML party literals are both retained, not silently standardized.",
    "Native RegularCheckIns is labeled VOTES CAST; its sum matches county Ballots Counted.",
    "Native geographic keys and literal unit names remain separate; no geometry or crosswalk is approved.",
    "Ballots minus candidate votes is unclassified, not inferred undervotes or overvotes.",
    "Explicit provisional candidate zeroes do not establish zero provisional ballots.",
    "Printed report timestamp has no independently established timezone.",
    "Native HTML omits map-service access tokens; the complete original is retained privately and hashed.",
    "No new map, precinct completeness, final certification or blanket upstream license is asserted.",
]


def integer(value, formatted=False):
    pattern = r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)" if formatted else r"0|[1-9]\d*"
    if isinstance(value, str) and re.fullmatch(pattern, value):
        return int(value.replace(",", ""))
    raise ValueError(f"Missing or invalid explicit integer: {value!r}")


def load_originals(source):
    receipts = json.loads((source / "receipts.json").read_bytes())
    if len(receipts) != len(URLS) or {r["file"] for r in receipts} != set(URLS):
        raise ValueError("Missing or duplicate original receipt")
    raw = {}
    for r in receipts:
        data = (source / r["file"]).read_bytes()
        if (r["url"] != URLS[r["file"]] or r["final_url"] != r["url"]
                or r["status"] != 200 or r["bytes"] != len(data)
                or r["sha256"] != hashlib.sha256(data).hexdigest()):
            raise ValueError("Original differs from county-declared acquisition receipt")
        if r["file"] == "native-results.redacted.html":
            redaction = r.get("redaction", {})
            if (redaction.get("kind") != "map_service_access_tokens"
                    or redaction.get("replacements", 0) < 1
                    or redaction["replacements"] != data.count(b"[REDACTED_MAP_SERVICE_TOKEN]")
                    or not re.fullmatch(r"[a-f0-9]{64}", redaction.get("original_sha256", ""))
                    or redaction.get("original_bytes", 0) <= 0
                    or re.search(rb"\b[ps]k\.[A-Za-z0-9._-]+", data)):
                raise ValueError("Missing or invalid explicit HTML token-redaction receipt")
        elif "redaction" in r:
            raise ValueError("Original CSV/PDF/linking-page bytes must not be redacted")
        raw[r["file"]] = data
    return raw


def native_csv(raw, name, headers):
    lines = raw[name].decode("utf-8-sig").splitlines()
    if lines[:2] != ["UNOFFICIAL RESULTS", "Bucks"]:
        raise ValueError("Wrong native county or result status")
    reader = csv.reader(lines[2:])
    if next(reader, None) != headers:
        raise ValueError("Changed native CSV schema")
    rows = []
    for i, row in enumerate(reader):
        if name == "summary.csv" and i == 0 and len(row) == 2 and row[0] == "Total Precincts Reported":
            row += [""] * (len(headers) - 2)
        if len(row) != len(headers):
            raise ValueError("Malformed native CSV row")
        rows.append(dict(zip(headers, row)))
    return rows


def office(contest):
    if contest == "GOVERNOR AND LIEUTENANT GOVERNOR":
        return "governor_lieutenant_governor"
    for prefix, result in [
        ("REPRESENTATIVE IN CONGRESS ", "us_house"),
        ("SENATOR IN THE GENERAL ASSEMBLY ", "state_senate"),
        ("REPRESENTATIVE IN THE GENERAL ASSEMBLY ", "state_house"),
    ]:
        if contest.startswith(prefix) and re.fullmatch(r"\d+(?:ST|ND|RD|TH)", contest[len(prefix):]):
            return result
    raise ValueError("Unreviewed native office")


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate native JSON identity")
        result[key] = value
    return result


def printed_rate(value, ballots, registered, places):
    if not re.fullmatch(r"\d+\.\d{" + str(places) + "}", value) or not registered:
        raise ValueError("Missing native printed participation rate")
    expected = (Decimal(100) * ballots / registered).quantize(
        Decimal(10) ** -places, rounding=ROUND_HALF_UP)
    if Decimal(value) != expected:
        raise ValueError("Native printed participation rate disagrees with counts")


def review(raw):
    index = BeautifulSoup(raw["official-results-index.html"], "html.parser")
    if not any(a.get("href") == URLS["native-results.redacted.html"] for a in index.select("a[href]")):
        raise ValueError("County index does not declare this native report")
    soup = BeautifulSoup(raw["native-results.redacted.html"], "html.parser")
    if (soup.select_one("h1.election-title").get_text(strip=True) != "2026 General Election"
            or soup.select_one("#lblOfficialResults").get_text(strip=True) != "UNOFFICIAL RESULTS"
            or soup.select_one("#electid").get("value") != "24"
            or re.search(r"\btest(?:ing)?\b", soup.body.get_text(" ", strip=True), re.I)):
        raise ValueError("Wrong election or source test/publication status")
    mode_status = [soup.select_one("#" + key).get_text(" ", strip=True)
                   for key in ["mailBallotReporting", "accessibleVotingReporting"]]
    if mode_status != ["Absentee and Mail-In: Partially Reported",
                       "In-Person Ballots: Partially Reported"]:
        raise ValueError("Changed native counting qualifications require review")

    summary = native_csv(raw, "summary.csv", SUMMARY_HEADERS)
    counter_row = summary.pop(0)
    if (counter_row["Contest Name"] != "Total Precincts Reported"
            or any(counter_row[k] for k in SUMMARY_HEADERS[2:])):
        # This native record deliberately has two fields, unlike all candidate rows.
        raise ValueError("Changed native total-reporting record")
    reported = integer(counter_row["Candidate Name"])
    contests = native_csv(raw, "contests.csv", CONTEST_HEADERS)
    units = native_csv(raw, "native-units.csv", UNIT_HEADERS)
    contest_info, candidates, candidate_modes, candidate_index = {}, [], [], {}
    for row in contests:
        name = row["Contest Name"]
        counts = {k: integer(row[k]) for k in CONTEST_HEADERS[1:]}
        if name in contest_info or counts["Precincts Reported"] != counts["Number Of Precincts"]:
            raise ValueError("Duplicate contest or changed reporting status")
        contest_info[name] = counts
    html_rows = {}
    for container in soup.select("#contestListLayer > .list-item"):
        contest = container.select_one(".race-title").get_text(strip=True)
        if container.select_one(".vote-for").get_text(strip=True) != "(VOTE FOR 1)":
            raise ValueError("Unreviewed multi-seat vote opportunity")
        for row in container.select("tr.content-row"):
            cell = row.select_one('[data-candidate="true"]')
            visible = cell.select_one('[aria-hidden="true"]').get_text(strip=True)
            accessible = cell.select_one(".sr-only").get_text(strip=True)
            key = (contest, visible)
            if key in html_rows:
                raise ValueError("Duplicate HTML candidate")
            html_rows[key] = (accessible, integer(
                row.select_one('[data-votes="true"]').get_text(strip=True), formatted=True))
    for row in summary:
        name, candidate, party = (row[k] for k in SUMMARY_HEADERS[:3])
        key = (name, candidate)
        if key in candidate_index or name not in contest_info or party not in HTML_PARTIES:
            raise ValueError("Duplicate or unknown candidate/party identity")
        votes = integer(row["Total Votes"])
        modes = {k: integer(row[k]) for k in MODES}
        if (sum(modes.values()) != votes
                or any(integer(row[k]) != contest_info[name][k] for k in CONTEST_HEADERS[1:3])
                or html_rows.get((name, f"{candidate} ({party})")) != (
                    f"{candidate}, {HTML_PARTIES[party]}", votes)):
            raise ValueError("County HTML, candidate modes or reporting counters disagree")
        data = dict(year=2026, state_code="PA", county_fips="42017",
                    office=office(name), contest_name=name, candidate_literal=candidate,
                    party_csv_literal=party, party_html_literal=HTML_PARTIES[party], votes=votes)
        candidates.append(data)
        candidate_index[key] = data
        candidate_modes.extend(dict(**data, voting_mode_literal=mode, mode_votes=count)
                               for mode, count in modes.items())
    if (len(html_rows) != len(candidates)
            or {r["contest_name"] for r in candidates} != set(contest_info)):
        raise ValueError("Missing county candidate or contest")

    with fitz.open(stream=raw["summary.pdf"], filetype="pdf") as pdf:
        pages = [page.get_text() for page in pdf]
    pdf_text = "\n".join(pages)
    if "2026 General Election (11/03/2026)" not in pdf_text or "UNOFFICIAL RESULTS\nBucks" not in pdf_text:
        raise ValueError("Wrong PDF election or publication status")
    stamps = set(re.findall(r"(?m)^\d{2}/\d{2}/2026 \d{1,2}:\d{2} [AP]M$", pdf_text))
    if len(stamps) != 1:
        raise ValueError("Missing or inconsistent native report timestamp")
    pdf_seen, current = set(), None
    pdf_lines = pdf_text.splitlines()
    for i, line in enumerate(pdf_lines):
        if line in contest_info:
            current = line
        elif re.fullmatch(r".+ \([A-Za-z]+\)", line):
            matches = [r for r in summary if r["Contest Name"] == current
                       and line == f'{r["Candidate Name"]} ({r["Party"]})']
            if len(matches) != 1:
                raise ValueError("Unknown PDF candidate or literal party")
            row = matches[0]
            key = (current, row["Candidate Name"])
            if (key in pdf_seen or [integer(v, formatted=True) for v in pdf_lines[i + 1:i + 5]]
                    != [integer(row[k]) for k in [*MODES, "Total Votes"]]):
                raise ValueError("PDF candidate/mode vector does not reconcile")
            pdf_seen.add(key)
    if pdf_seen != set(candidate_index):
        raise ValueError("PDF does not cover every county candidate")

    scripts = [s.get_text() for s in soup.find_all("script", src=False)
               if "function LoadTurnoutMap()" in s.get_text()]
    if len(scripts) != 1:
        raise ValueError("Missing or ambiguous native participation dataset")
    match = re.search(r"var precinctData = '([^\r\n]+)';", scripts[0])
    turnout = json.loads(match.group(1), object_pairs_hook=unique_json)
    participation, by_name, codes = [], {}, set()
    for geo_key, row in turnout.items():
        name, code = row["PrecinctName"], row["PrecinctCode"]
        integer(code)
        ballots, registered = integer(row["RegularCheckIns"]), integer(row["VoterCount"])
        if (row["ElectionID"] != "24" or row["StatusValue"] != "Reported"
                or geo_key != row["PrecinctGeoName"] or name in by_name or code in codes
                or ballots > registered):
            raise ValueError("Duplicate or inconsistent native participation identity")
        printed_rate(row["RegularTurnout"], ballots, registered, 2)
        data = dict(native_unit_code=code, native_unit_name=name, native_geo_key=geo_key,
                    native_votes_cast=ballots, registered_voters=registered,
                    native_printed_turnout_pct=row["RegularTurnout"],
                    native_status=row["StatusValue"])
        by_name[name] = data
        codes.add(code)
        participation.append(data)
    if len(participation) != reported:
        raise ValueError("Native participation reporting count disagrees")
    ballot_total = sum(r["native_votes_cast"] for r in participation)
    registrations = sum(r["registered_voters"] for r in participation)
    for label, expected in [("Ballots Counted", ballot_total), ("Registered Voters", registrations)]:
        text = soup.find(string=label)
        spans = text.parent.parent.parent.find_all("span")
        if len(spans) != 2 or integer(spans[1].get_text(strip=True), formatted=True) != expected:
            raise ValueError("County participation does not reconcile to native units")
    printed = soup.select_one(".summary-percentage").get_text(strip=True)
    printed_rate(printed.removesuffix("%"), ballot_total, registrations, 1)

    unit_keys, unit_sums, unit_options, contest_units = set(), Counter(), defaultdict(set), defaultdict(set)
    native_counts = []
    for row in units:
        name, contest, candidate = (row[k] for k in UNIT_HEADERS[:3])
        key = (name, contest, candidate)
        if key in unit_keys or name not in by_name or (contest, candidate) not in candidate_index:
            raise ValueError("Duplicate or unknown native candidate observation")
        if row["Voter Turnout"] != by_name[name]["native_printed_turnout_pct"] + "%":
            raise ValueError("Native repeated participation rate disagrees")
        count = integer(row["Votes"])
        unit_keys.add(key)
        unit_sums[(contest, candidate)] += count
        unit_options[(name, contest)].add(candidate)
        contest_units[contest].add(name)
        data = candidate_index[(contest, candidate)]
        native_counts.append(dict(native_unit_name=name, native_unit_code=by_name[name]["native_unit_code"],
                                  contest_name=contest, candidate_literal=candidate,
                                  party_literal_from_summary=data["party_csv_literal"],
                                  votes=count, native_printed_turnout=row["Voter Turnout"]))
    expected_options = defaultdict(set)
    for contest, candidate in candidate_index:
        expected_options[contest].add(candidate)
        if unit_sums[(contest, candidate)] != candidate_index[(contest, candidate)]["votes"]:
            raise ValueError("Native candidate sum disagrees with county summary")
    for (name, contest), options in unit_options.items():
        if options != expected_options[contest]:
            raise ValueError("Missing native candidate option, including an explicit zero")
    office_units = defaultdict(set)
    totals, party_sums = [], Counter()
    for contest, counts in contest_info.items():
        names = contest_units[contest]
        kind = office(contest)
        if (len(names) != counts["Number Of Precincts"]
                or office_units[kind] & names
                or sum(by_name[n]["native_votes_cast"] for n in names) != counts["Ballots Cast"]):
            raise ValueError("Native contest partition or ballot total disagrees")
        office_units[kind].update(names)
        candidate_votes = sum(r["votes"] for r in candidates if r["contest_name"] == contest)
        totals.append(dict(contest_name=contest, office=kind, candidate_votes=candidate_votes,
                           ballots_cast=counts["Ballots Cast"],
                           ballots_minus_candidate_votes_unclassified=counts["Ballots Cast"] - candidate_votes,
                           native_units=counts["Number Of Precincts"],
                           native_units_reported=counts["Precincts Reported"]))
    if set(office_units) != {"governor_lieutenant_governor", "us_house", "state_senate", "state_house"} or any(
            names != set(by_name) for names in office_units.values()):
        raise ValueError("Office district partitions do not cover the same native county units")
    for row in candidates:
        party_sums[(row["office"], row["party_csv_literal"])] += row["votes"]
    county = dict(year=2026, state_code="PA", county_fips="42017", county="Bucks",
                  ballots_counted=ballot_total, registered_voters=registrations,
                  native_printed_turnout=printed, registered_ballot_ratio_pct=100 * ballot_total / registrations,
                  house_candidate_votes=sum(r["votes"] for r in candidates if r["contest_name"] == HOUSE),
                  source_update_literal=next(iter(stamps)), result_status="UNOFFICIAL RESULTS",
                  mail_counting_status=mode_status[0], in_person_counting_status=mode_status[1],
                  final_certified_turnout=False)
    tables = {
        "county-candidate-results.csv": candidates,
        "county-candidate-mode-counts.csv": candidate_modes,
        "county-office-party-totals.csv": [
            dict(year=2026, state_code="PA", county_fips="42017", office=kind,
                 party_literal=party, votes=count) for (kind, party), count in sorted(party_sums.items())],
        "county-contest-totals.csv": totals,
        "county-participation.csv": [county],
        "native-unit-participation.csv": participation,
        "native-unit-candidate-counts.csv": native_counts,
    }
    audit = dict(status="original_backed_county_counts_reviewed_counting_partial",
                 participation=county, native_contests=len(contests), native_units=len(participation),
                 native_unit_candidate_rows=len(units), native_unit_explicit_zeroes=sum(r["Votes"] == "0" for r in units),
                 unit_name_geo_key_differences=sum(r["native_unit_name"] != r["native_geo_key"] for r in participation),
                 house_literal_party_votes={party: votes for (kind, party), votes in party_sums.items() if kind == "us_house"},
                 source_urls=URLS, new_maps_approved=False, fully_complete=False,
                 limitations=LIMITATIONS, table_rows={name: len(rows) for name, rows in tables.items()})
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
    checksums = {p.relative_to(args.output).as_posix(): dict(
        bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths}
    (args.output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in args.output.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(args.output).as_posix())
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
