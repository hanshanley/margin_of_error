"""Reconcile three county-declared 2026 reports without extending map coverage."""

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


COUNTIES = {
    "Chester": {
        "fips": "42029", "id": "4", "account": "chesterpaenr",
        "title": "2026 General Election", "csv_county": "Chester", "status": "",
        "parent": "https://www.chesco.org/156/Voter-Services",
    },
    "Franklin": {
        "fips": "42055", "id": "15", "account": "franklinpaenr",
        "title": "2026 Nov General", "csv_county": "Franklin County",
        "status": "Unofficial Election Results",
        "parent": "https://www.franklincountypa.gov/departments/elections-voter-registration/",
    },
    "Lehigh": {
        "fips": "42077", "id": "13", "account": "lehighpaenr",
        "title": "November 2026 General Election", "csv_county": "LEHIGH",
        "status": "Unofficial Election Results",
        "parent": "https://www.lehighcounty.org/Departments/Voter-Registration/Election-Results",
    },
}


def integer(value, formatted=False):
    pattern = r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)" if formatted else r"(?:0|[1-9]\d*)"
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError("Missing or invalid explicit integer")
    return int(value.replace(",", ""))


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate native JSON identity")
        result[key] = value
    return result


def check_rate(literal, ballots, registered, places):
    if not registered or not re.fullmatch(r"\d+\.\d{" + str(places) + "}", literal):
        raise ValueError("Missing native printed participation rate")
    expected = (Decimal(100) * ballots / registered).quantize(
        Decimal(10) ** -places, rounding=ROUND_HALF_UP)
    if Decimal(literal) != expected:
        raise ValueError("Printed participation disagrees with native counts")


def office(contest):
    lower = contest.lower()
    for prefix, kind in [
        ("governor and lieutenant governor", "governor_lieutenant_governor"),
        ("representative in congress", "us_house"),
        ("senator in the general assembly", "state_senate"),
        ("representative in the general assembly", "state_house"),
    ]:
        if lower.startswith(prefix):
            return kind
    if "referendum" in lower:
        return "ballot_question"
    raise ValueError("Unreviewed native office")


def load_originals(folder, county):
    config = COUNTIES[county]
    base = "https://www.livevoterturnout.com/ENR/" + config["account"] + "/" + config["id"] + "/"
    urls = {
        "official-results-index.html": config["parent"],
        "native-results.redacted.html": base + "en/Index_" + config["id"] + ".html",
        "summary.csv": base + "summary_" + config["id"] + ".csv",
    }
    if county != "Lehigh":
        urls["contests.csv"] = base + "contests_" + config["id"] + ".csv"
    receipts = json.loads((folder / "receipts.json").read_bytes())
    if (len(receipts) != len(urls) or {r["file"] for r in receipts} != set(urls)
            or {path.name for path in folder.iterdir()} != set(urls) | {"receipts.json"}):
        raise ValueError("Incomplete original receipt inventory")
    raw = {}
    for receipt in receipts:
        name = receipt["file"]
        data = (folder / name).read_bytes()
        if (receipt["url"] != urls[name] or receipt["final_url"] != urls[name]
                or receipt["status"] != 200 or receipt["bytes"] != len(data)
                or receipt["sha256"] != hashlib.sha256(data).hexdigest()):
            raise ValueError("Original acquisition receipt mismatch")
        redaction = receipt.get("redaction")
        if name.endswith(".html") and redaction:
            if (not re.fullmatch(r"[a-f0-9]{64}", redaction.get("original_sha256", ""))
                    or redaction.get("original_bytes", 0) <= 0
                    or redaction.get("replacements", 0) != data.count(b"[REDACTED_PUBLIC_SERVICE_KEY]")
                    or re.search(rb"\b[ps]k\.[A-Za-z0-9._-]+", data)):
                raise ValueError("Invalid explicit HTML redaction receipt")
        elif name == "native-results.redacted.html":
            raise ValueError("Native HTML requires an explicit redaction receipt")
        raw[name] = data
    return raw


def review(county, raw):
    config = COUNTIES[county]
    source = ("https://www.livevoterturnout.com/ENR/" + config["account"] + "/"
              + config["id"] + "/en/Index_" + config["id"] + ".html")
    parent = BeautifulSoup(raw["official-results-index.html"], "html.parser")
    if not any(a["href"] == source for a in parent.select("a[href]")):
        raise ValueError("County does not declare this result page")
    soup = BeautifulSoup(raw["native-results.redacted.html"], "html.parser")
    if (soup.select_one("h1.election-title").get_text(strip=True) != config["title"]
            or soup.select_one("#electid")["value"] != config["id"]
            or soup.select_one("#lblOfficialResults").get_text(strip=True) != config["status"]
            or re.search(r"\btest(?:ing)?\b", soup.body.get_text(" ", strip=True), re.I)):
        raise ValueError("Wrong election or source publication status")
    lines = raw["summary.csv"].decode("utf-8-sig").splitlines()
    if lines[:2] != [config["status"], config["csv_county"]]:
        raise ValueError("Wrong native CSV county or status")
    reader = csv.DictReader(lines[2:])
    headers = reader.fieldnames
    mode_fields = [field for field in headers if field.endswith(" Votes") and field not in {
        "Total Votes", "Over Votes", "Under Votes"}]
    if (headers[:3] != ["Contest Name", "Candidate Name", "Party"]
            or not mode_fields or len(headers) != len(set(headers))):
        raise ValueError("Changed native CSV schema")
    reporting = next(reader)
    reported = integer(reporting["Candidate Name"])
    if reporting["Contest Name"] != "Total Precincts Reported" or any(
            reporting[field] is not None for field in headers[2:]):
        raise ValueError("Changed native reporting record")

    html_rows, html_contests = {}, {}
    for container in soup.select("#contestListLayer > .list-item"):
        contest = container.select_one(".race-title").get_text(strip=True)
        if contest in html_contests or container.select_one(".vote-for").get_text(strip=True) != "(VOTE FOR 1)":
            raise ValueError("Duplicate contest or unreviewed selection limit")
        html_contests[contest] = container
        for row in container.select("tr.content-row"):
            cell = row.select_one('[data-candidate="true"]')
            visible = cell.select_one('[aria-hidden="true"]').get_text(strip=True)
            key = contest, visible
            if key in html_rows:
                raise ValueError("Duplicate county HTML candidate")
            html_rows[key] = (cell.select_one(".sr-only").get_text(strip=True),
                             integer(row.select_one('[data-votes="true"]').get_text(strip=True), True))
    candidates, modes, lookup, metadata = [], [], {}, {}
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Incomplete CSV candidate record")
        contest, name, party = (row[field] for field in headers[:3])
        if not name or party not in {"DEM", "REP", "LIB", "NON"}:
            raise ValueError("Missing candidate or unreviewed native party")
        prefix = re.match(r"^(DEM|REP|LIB|NON) ", name)
        if prefix and prefix[1] != party:
            raise ValueError("Explicit candidate prefix and CSV party disagree")
        matches = [key for key in [(contest, name), (contest, name + " (" + party + ")")]
                   if key in html_rows]
        if len(matches) != 1 or matches[0] in lookup:
            raise ValueError("CSV and HTML candidate identities disagree")
        key = matches[0]
        votes = integer(row["Total Votes"])
        counts = {field: integer(row[field]) for field in mode_fields}
        native_meta = {field: integer(row[field]) for field in headers[3:]
                       if field not in mode_fields + ["Total Votes"]}
        if (sum(counts.values()) != votes or html_rows[key][1] != votes
                or native_meta.get("Vote For", 1) != 1):
            raise ValueError("Candidate modes, selection limit or HTML counts disagree")
        if contest in metadata and metadata[contest] != native_meta:
            raise ValueError("Repeated native contest accounting disagrees")
        metadata[contest] = native_meta
        data = dict(year=2026, state_code="PA", county_fips=config["fips"], county=county,
                    office=office(contest), contest=contest, candidate_literal=name,
                    party_csv_literal=party, candidate_html_literal=key[1],
                    accessible_html_literal=html_rows[key][0], votes=votes)
        candidates.append(data)
        lookup[key] = data
        modes.extend(dict(**data, voting_mode_literal=field, mode_votes=count)
                     for field, count in counts.items())
    if set(lookup) != set(html_rows) or set(metadata) != set(html_contests):
        raise ValueError("Missing county candidate or contest")
    if county != "Lehigh":
        contest_lines = raw["contests.csv"].decode("utf-8-sig").splitlines()
        if contest_lines[:2] != lines[:2]:
            raise ValueError("Wrong native contest-report county or status")
        contest_rows = csv.DictReader(contest_lines[2:])
        seen_contests = set()
        for row in contest_rows:
            contest = row["Contest Name"]
            if contest not in metadata or contest in seen_contests:
                raise ValueError("Unknown or duplicate native contest-report identity")
            seen_contests.add(contest)
            for field, literal in row.items():
                if field == "Contest Name":
                    continue
                count = integer(literal)
                if field in metadata[contest] and metadata[contest][field] != count:
                    raise ValueError("Native summary and contest accounting disagree")
                metadata[contest][field] = count
        if seen_contests != set(metadata):
            raise ValueError("Missing native contest-report record")

    unit_counts, unit_keys, unit_totals, units_by_contest = [], set(), Counter(), defaultdict(set)
    expected_options = defaultdict(set)
    for contest, name in lookup:
        expected_options[contest].add(name)
    unit_names, unit_codes, code_by_name = set(), set(), {}
    for unit in soup.select("#precinctListLayer > .list-item-precinct"):
        name = unit.select_one(".precinct-title").get_text(strip=True)
        code = unit["id"].removeprefix("listid_")
        if name in unit_names or code in unit_codes:
            raise ValueError("Duplicate native unit identity")
        unit_names.add(name)
        unit_codes.add(code)
        code_by_name[name] = code
        for fragment in unit.select(".list-item-precinct-race"):
            unit_contest = fragment.select_one(".race-title").get_text(strip=True)
            if not unit_contest.startswith(name + " - "):
                raise ValueError("Native unit contest title has a different unit identity")
            contest = unit_contest[len(name + " - "):]
            options = set()
            for row in fragment.select("tr.content-row"):
                literal = row.select_one('[dc="true"] [aria-hidden="true"]').get_text(strip=True)
                key = contest, literal
                observation = name, contest, literal
                if key not in lookup or observation in unit_keys:
                    raise ValueError("Unknown or duplicate native candidate observation")
                options.add(literal)
                unit_keys.add(observation)
                votes = integer(row.select_one('[dv="true"]').get_text(strip=True), True)
                unit_totals[key] += votes
                unit_counts.append(dict(**{k: lookup[key][k] for k in [
                    "year", "state_code", "county_fips", "county", "office", "contest",
                    "candidate_literal", "party_csv_literal"]},
                    native_unit_name=name, native_unit_code=code,
                    native_unit_contest_literal=unit_contest, votes=votes))
            if options != expected_options[contest]:
                raise ValueError("Missing native candidate option, including explicit zero")
            units_by_contest[contest].add(name)
    if len(unit_names) != reported or any(unit_totals[key] != data["votes"] for key, data in lookup.items()):
        raise ValueError("Native unit sums differ from county candidate counts")
    for contest, meta in metadata.items():
        if (len(units_by_contest[contest]) != meta["Number Of Precincts"]
                or meta["Precincts Reported"] != meta["Number Of Precincts"]):
            raise ValueError("Native reporting inventory disagrees")
    for kind in {"governor_lieutenant_governor", "us_house", "state_house", "state_senate"}:
        covered = set()
        for contest in metadata:
            if office(contest) != kind:
                continue
            if covered & units_by_contest[contest]:
                raise ValueError("Overlapping native office district partitions")
            covered.update(units_by_contest[contest])
        if kind in {"governor_lieutenant_governor", "us_house", "state_house"} and covered != unit_names:
            raise ValueError("Incomplete county office district partition")

    scripts = "\n".join(script.get_text() for script in soup.find_all("script", src=False))
    embedded = re.findall(r"(?:var )?precinctData\s*=\s*'([^\r\n]+)';", scripts)
    if len(embedded) != 1:
        raise ValueError("Missing or ambiguous native participation dataset")
    turnout = json.loads(embedded[0], object_pairs_hook=unique_json)
    participation, by_name, codes = [], {}, set()
    for key, row in turnout.items():
        name, code = row["PrecinctName"], row["PrecinctCode"]
        ballots, registered = integer(row["RegularCheckIns"]), integer(row["VoterCount"])
        if (row["ElectionID"] != config["id"] or name in by_name or code in codes
                or name not in unit_names or code != code_by_name[name] or ballots > registered
                or row["StatusValue"] != "Reported"):
            raise ValueError("Invalid or duplicate native participation identity")
        check_rate(row["RegularTurnout"], ballots, registered, 2)
        data = dict(year=2026, state_code="PA", county_fips=config["fips"], county=county,
                    native_unit_name=name, native_unit_code=code, native_json_key=key,
                    native_geo_key=row["PrecinctGeoName"], native_votes_cast=ballots,
                    registered_voters=registered, native_printed_turnout_pct=row["RegularTurnout"],
                    native_status=row["StatusValue"])
        participation.append(data)
        by_name[name] = data
        codes.add(code)
    if set(by_name) != unit_names or codes != unit_codes:
        raise ValueError("Participation and result unit inventories differ")
    ballots = sum(row["native_votes_cast"] for row in participation)
    registered = sum(row["registered_voters"] for row in participation)
    for label, expected in [("Ballots Counted", ballots), ("Registered Voters", registered)]:
        node = soup.find(string=lambda value: value and value.strip() == label)
        spans = node.parent.parent.parent.find_all("span")
        if len(spans) != 2 or integer(spans[1].get_text(strip=True), True) != expected:
            raise ValueError("County participation disagrees with native units")
    printed = soup.select_one(".summary-percentage").get_text(strip=True)
    check_rate(printed.removesuffix("%"), ballots, registered, 1)
    stamps = set(re.findall(r"Website Updated:\s*(\d{1,2}/\d{1,2}/2026 \d{1,2}:\d{2}:\d{2} [AP]M)",
                            soup.get_text(" ", strip=True)))
    if len(stamps) != 1:
        raise ValueError("Missing native update timestamp")
    qualifications = [node.get_text(" ", strip=True) for node in soup.select("[id$='Reporting']")
                      if node.get_text(strip=True)]
    county_row = dict(year=2026, state_code="PA", county_fips=config["fips"], county=county,
        ballots_counted=ballots, registered_voters=registered, native_printed_turnout=printed,
        registered_ballot_ratio_pct=100 * ballots / registered,
        house_candidate_votes=sum(row["votes"] for row in candidates if row["office"] == "us_house"),
        native_status_literal=config["status"], source_update_literal=next(iter(stamps)),
        counting_qualifications_json=json.dumps(qualifications), final_certified_turnout=False)
    contest_totals, conflicts = [], []
    for contest, meta in metadata.items():
        covered_ballots = sum(by_name[name]["native_votes_cast"] for name in units_by_contest[contest])
        count = sum(row["votes"] for row in candidates if row["contest"] == contest)
        if "Ballots Cast" in meta and meta["Ballots Cast"] != covered_ballots:
            conflicts.append(contest)
        unexplained = covered_ballots - count - meta.get("Under Votes", 0) - meta.get("Over Votes", 0)
        if unexplained < 0:
            raise ValueError("Native contest accounting exceeds covered ballots")
        contest_totals.append(dict(year=2026, state_code="PA", county_fips=config["fips"], county=county,
            office=office(contest), contest=contest, candidate_or_option_votes=count,
            covered_unit_votes_cast=covered_ballots,
            ballots_minus_candidate_or_option_votes=covered_ballots-count,
            native_under_votes=meta.get("Under Votes"), native_over_votes=meta.get("Over Votes"),
            ballots_minus_votes_unclassified=unexplained,
            native_csv_fields_json=json.dumps(meta, sort_keys=True),
            native_csv_ballot_count_matches_units=(meta["Ballots Cast"] == covered_ballots)
            if "Ballots Cast" in meta else None))
    parties = Counter()
    for row in candidates:
        if row["office"] != "ballot_question":
            parties[row["office"], row["party_csv_literal"]] += row["votes"]
    tables = {
        "county-candidate-results.csv": candidates,
        "county-candidate-mode-counts.csv": modes,
        "county-office-party-totals.csv": [dict(year=2026, state_code="PA", county_fips=config["fips"],
            county=county, office=kind, party_literal=party, votes=count)
            for (kind, party), count in sorted(parties.items())],
        "county-contest-totals.csv": contest_totals,
        "county-participation.csv": [county_row],
        "native-unit-participation.csv": participation,
        "native-unit-candidate-counts.csv": unit_counts,
    }
    audit = dict(county=county, status="county_counts_reviewed_not_final_certified",
        participation=county_row, native_contests=len(metadata), native_units=len(unit_names),
        native_unit_candidate_rows=len(unit_counts),
        native_unit_explicit_zeroes=sum(row["votes"] == 0 for row in unit_counts),
        native_csv_ballot_count_conflicts=conflicts, house_district_number_in_native_title=county != "Franklin",
        source_url=source, source_county_index=config["parent"],
        maps_approved=False, fully_complete=False, demographic_turnout_approved=False,
        limitations=[
            "County-only provisional snapshot, not statewide completion or certified turnout.",
            "Candidate votes, separate ballot options, ballots and registrations are distinct measures.",
            "Native prefixes, CSV parties and accessible HTML labels remain separate and unnormalized.",
            "State Senate results cover only the county portions with a contest, not every county voter.",
            "Franklin's native House title supplies no district number; none is inferred.",
            "Chester's native CSV contest ballot zeroes conflict with positive unit ballots; retain but do not use as real ballot counts.",
            "Ballot residuals are unclassified; do not infer missing overvotes, undervotes or voters.",
            "Source update timezone is unestablished. Reporting counters do not establish finished counting.",
            "Map-service and instrumentation keys are explicitly redacted; full originals are retained privately.",
        ], table_rows={name: len(rows) for name, rows in tables.items()})
    return tables, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    if {path.name for path in args.source.iterdir()} != {name.lower() for name in COUNTIES}:
        raise ValueError("Unexpected original county source inventory")
    results = {county: review(county, load_originals(args.source / county.lower(), county))
               for county in COUNTIES}
    args.output.mkdir(parents=True, exist_ok=False)
    merged, audits = defaultdict(list), []
    for tables, audit in results.values():
        audits.append(audit)
        for name, rows in tables.items():
            merged[name].extend(rows)
    for name, rows in merged.items():
        with (args.output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (args.output / "audit.json").write_text(json.dumps(dict(
        counties=audits, maps_approved=False, fully_complete=False), indent=2) + "\n")
    shutil.copytree(args.source, args.output / "originals")
    shutil.copyfile(__file__, args.output / Path(__file__).name)
    paths = sorted(path for path in args.output.rglob("*") if path.is_file())
    checksums = {path.relative_to(args.output).as_posix(): dict(
        bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths}
    (args.output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(path for path in args.output.rglob("*") if path.is_file()):
            info = zipfile.ZipInfo(path.relative_to(args.output).as_posix())
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    print(json.dumps({row["county"]: row["participation"] for row in audits}, indent=2))


if __name__ == "__main__":
    main()
