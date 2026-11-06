"""Privately review Philadelphia's participation and complete native election export."""

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


IDENTITY = dict(year=2026, state_code="PA", county_fips="42101", county="Philadelphia")
BASE = "https://vote-results.phila.gov/"
SUMMARY_FILES = {
    "statewide-results.html": "STW", "congress-results.html": "CON",
    "state-senate-results.html": "STS", "state-house-results.html": "STR",
    "state-house-results-page2.html": "STR",
    "ballot-question-results.html": "QUE",
}
SOURCE_URLS = {
    "official-results-index.html": BASE,
    "county-exports.html": BASE + "ResultsExport.aspx",
    "county-exports-form.html": BASE + "ResultsExport.aspx",
    "county-participation.html": BASE + "VoterTurnoutDetails.aspx",
    "native-county-export.bin": BASE + "ResultsExport.aspx",
    "official-election-home.html": "https://vote.phila.gov/",
    "official-current-election-index.html": "https://vote.phila.gov/resources-data/election-result/",
    "official-results-redirect.html": "https://vote.phila.gov/results/",
    "official-embedded-results.html": "https://philadelphiaresults.azurewebsites.us/",
    "state-house-pagination-form.html": BASE + "ResultsSW.aspx?type=STR&map=CTY",
    **{name: BASE + "ResultsSW.aspx?type=" + code + "&map=CTY"
       for name, code in SUMMARY_FILES.items()},
}
SERVICE_KEY = re.compile(rb"\b(?:AIza[0-9A-Za-z_-]{35}|[ps]k\.[A-Za-z0-9._-]+)")
TELEMETRY_KEY = re.compile(
    rb"""['"]?(?:[A-Za-z_$]*instrumentationKey|licenseKey)['"]?\s*[:=]\s*['"](?!\[REDACTED_PUBLIC_SERVICE_KEY\])[^'"\r\n]+['"]""",
    re.I,
)
CSV_FIELDS = ["RaceName", "PartyCode", "CandidateName", "PrecinctName", "CurrentDateTime",
              "VoteFor", "CandidateVotes", "CandidatePercentage", "PrecinctsReporting",
              "Election Day", "Mail Votes", "Provisional"]
METHOD_FIELDS = ["Election Day", "Mail Votes", "Provisional"]


def integer(value):
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+", value):
        raise ValueError("Missing or invalid native integer")
    return int(value.replace(",", ""))


def office(contest):
    for prefix, kind in [
        ("GOVERNOR  AND LIEUTENANT GOVERNOR", "governor_lieutenant_governor"),
        ("REPRESENTATIVE IN CONGRESS", "us_house"),
        ("SENATOR IN THE GENERAL ASSEMBLY", "state_senate"),
        ("REPRESENTATIVE IN THE GENERAL ASSEMBLY", "state_house"),
        ("QUESTION #", "ballot_question"),
    ]:
        if contest.startswith(prefix):
            return kind
    raise ValueError("Unreviewed native office")


def load_originals(folder):
    receipts = json.loads((folder / "receipts.json").read_bytes())
    names = [r["path"] for r in receipts]
    if (len(names) != len(set(names)) or set(names) != set(SOURCE_URLS)
            or {p.name for p in folder.iterdir()} != set(names) | {"receipts.json"}):
        raise ValueError("Incomplete original receipt inventory")
    raw = {}
    for receipt in receipts:
        name = receipt["path"]
        body = (folder / name).read_bytes()
        if (receipt["requested_url"] != SOURCE_URLS[name] or receipt["status"] != 200
                or receipt["final_url"].rstrip("?") != SOURCE_URLS[name].rstrip("?")
                or receipt["bytes"] != len(body)
                or receipt["sha256"] != hashlib.sha256(body).hexdigest()):
            raise ValueError("Original acquisition receipt mismatch")
        if SERVICE_KEY.search(body) or TELEMETRY_KEY.search(body):
            raise ValueError("Unredacted public service key in source")
        if name == "native-county-export.bin":
            if (receipt.get("method") != "POST" or receipt.get("form_control") != {
                    "submit_name": "ctl00$MainContent$LinkButton1",
                    "submit_value": "Philadelphia", "command_argument": "Philadelphia|04"}):
                raise ValueError("Undeclared county export form")
        if name == "state-house-results-page2.html" and (
                receipt.get("method") != "POST" or receipt.get("form_control") != {
                    "submit_name": "ctl00$MainContent$btnNext", "submit_value": "Next Page"}):
            raise ValueError("Undeclared state-House pagination")
        raw[name] = body
    return raw


def summary(soup):
    banner = soup.select_one("#pnlTestBanner")
    if banner is None or "display:none" not in re.sub(r"\s+", "", banner.get("style", "")).lower():
        raise ValueError("Source test banner is visible or unestablished")
    text = soup.get_text(" ", strip=True)
    if "Unofficial 2026 General Election Results November 3, 2026" not in text:
        raise ValueError("Wrong election or result status")
    reg = soup.select_one("#pnlTurnoutReg")
    modes = soup.select_one("#pnlTurnoutInv")
    if (reg is None or modes is None
            or re.sub(r"[\d,\s]", "", reg.get_text()) != "TotalBallotsCastRegisteredVoters"
            or re.sub(r"[\d,\s:]", "", modes.get_text()) !=
            "BallotsCastbyMailBallotsCastatPollingPlaceBallotsCastbyProvisional"):
        raise ValueError("Changed county participation labels")
    ballots, registered = [integer(n.get_text(strip=True)) for n in reg.select("span")]
    mail, election_day, provisional = [integer(n.get_text(strip=True)) for n in modes.select("span")]
    if not registered or ballots > registered or mail + election_day + provisional != ballots:
        raise ValueError("County participation or ballot methods disagree")
    rates = {n.get_text(strip=True) for n in soup.select("#turnoutgraph .dough-percent")}
    expected = (Decimal(100) * ballots / registered).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    if rates != {str(expected) + "%"}:
        raise ValueError("Printed county registration ratio disagrees")
    reporting = soup.select_one("#pnlPrecinctReg")
    counts = [integer(n.get_text(strip=True)) for n in reporting.select("span")]
    if len(counts) != 2 or counts[0] != counts[1]:
        raise ValueError("Incomplete native reporting inventory")
    return dict(ballots_cast=ballots, registered_voters=registered, election_day_ballots=election_day,
                mail_ballots=mail, provisional_ballots=provisional,
                printed_registered_voter_rate=str(expected) + "%",
                reported_divisions=counts[0], total_divisions=counts[1])


def review(raw):
    if set(raw) != set(SOURCE_URLS):
        raise ValueError("Incomplete acquired original inventory")
    pages = {name: BeautifulSoup(body, "html.parser")
             for name, body in raw.items() if name.endswith(".html")}
    if "/resources-data/election-result/" not in {
            a["href"] for a in pages["official-election-home.html"].select("a[href]")}:
        raise ValueError("Missing official current-election index")
    parent = pages["official-current-election-index.html"]
    if "https://vote.phila.gov/results/" not in {a["href"] for a in parent.select("a[href]")}:
        raise ValueError("Missing official election-results declaration")
    if [n.get("src") for n in pages["official-results-redirect.html"].select("iframe")] != [
            "https://philadelphiaresults.azurewebsites.us"]:
        raise ValueError("Changed official embedded-results source")
    county = summary(pages["county-participation.html"])
    for name in ["official-results-index.html", "official-embedded-results.html",
                 "county-exports.html", "county-exports-form.html",
                 "state-house-pagination-form.html", *SUMMARY_FILES]:
        if summary(pages[name]) != county:
            raise ValueError("County snapshot changed across captured originals")
    source_stamps = set()
    for name in ["official-results-index.html", "county-participation.html", *SUMMARY_FILES]:
        found = re.findall(r"Results Last Updated (\d{1,2}/\d{1,2}/2026 \d{1,2}:\d{2}:\d{2} [AP]M)(?: EST)?",
                           pages[name].get_text(" ", strip=True))
        if len(found) != 1:
            raise ValueError("Missing native source update")
        source_stamps.update(found)
    if len(source_stamps) != 1:
        raise ValueError("Source update changed during acquisition")
    if "Results Last Updated " + next(iter(source_stamps)) + " EST" not in pages[
            "county-participation.html"].get_text(" ", strip=True):
        raise ValueError("Unestablished native source timezone")
    county.update(**IDENTITY, source_update_literal=next(iter(source_stamps)),
                  source_update_timezone_literal="EST on native county participation page",
                  status="Unofficial", fully_complete=False, map_approved=False)
    divisions = []
    seen = set()
    for container in pages["county-participation.html"].select('[id^="countyturnout"]'):
        for node in container.select("div.county-precinct"):
            code = node.get_text(strip=True)
            if code == "Ward-Division":
                continue
            cells = node.parent.select(".county-cast")
            if not re.fullmatch(r"\d{2}-\d{2}", code) or code in seen or len(cells) != 5:
                raise ValueError("Duplicate or invalid native participation division")
            seen.add(code)
            registered, ballots, election_day, mail, provisional = [
                integer(n.get_text(strip=True)) for n in cells]
            if ballots != election_day + mail + provisional or ballots > registered:
                raise ValueError("Native division participation does not reconcile")
            divisions.append(dict(**IDENTITY, native_unit=code, registered_voters=registered,
                                  ballots_cast=ballots, election_day_ballots=election_day,
                                  mail_ballots=mail, provisional_ballots=provisional))
    for field in ["registered_voters", "ballots_cast", "election_day_ballots", "mail_ballots", "provisional_ballots"]:
        if sum(r[field] for r in divisions) != county[field]:
            raise ValueError("Division participation differs from county summary")
    if len(divisions) != county["total_divisions"]:
        raise ValueError("Missing native participation divisions")

    lookup, contests = {}, {}
    for name in SUMMARY_FILES:
        for header in pages[name].select(".display-results-box-a h1"):
            container = header.find_parent("div", class_="wrapper-border")
            contest = header.get_text(" ", strip=True)
            if not contest.endswith(" (VOTE FOR 1)") or contest in contests:
                raise ValueError("Duplicate or unsupported native contest")
            total_node = container.select_one(".display-results-box-total h2")
            total = integer(total_node.get_text(strip=True))
            code = office(contest)
            contest_rows = []
            for candidate in container.select(".display-results-box-d"):
                literal = candidate.select_one("h1").get_text(" ", strip=True)
                label = candidate.select_one("h2")
                party = label.get("class", [])
                if len(party) != 1:
                    raise ValueError("Unestablished literal HTML party")
                row = candidate.parent
                votes = integer(row.select_one(".display-results-box-f h1").get_text(strip=True))
                key = contest, literal.casefold()
                if key in lookup:
                    raise ValueError("Duplicate native county option")
                data = dict(**IDENTITY, office=code, contest=contest,
                            candidate_html_literal=literal, html_party_css_class_literal=party[0],
                            html_party_label_literal=label.get_text(" ", strip=True),
                            displayed_candidate_party_suffix_literal=(
                                re.search(r" (DEM|REP|LIB|TIP)$", literal)[1]
                                if re.search(r" (DEM|REP|LIB|TIP)$", literal) else ""),
                            votes=votes)
                lookup[key] = data
                contest_rows.append(data)
            if not contest_rows or sum(r["votes"] for r in contest_rows) != total:
                raise ValueError("County option sum differs from native contest total")
            reporting = container.select_one(".precinct-fully").get_text(" ", strip=True)
            match = re.fullmatch(r"Divisions Reported: (\d+) / (\d+)", reporting)
            if not match or match[1] != match[2]:
                raise ValueError("Unestablished contest reporting scope")
            contests[contest] = dict(**IDENTITY, office=code, contest=contest, candidate_or_option_votes=total,
                                     reported_divisions=int(match[1]), total_divisions=int(match[2]))

    reader = csv.DictReader(io.StringIO(raw["native-county-export.bin"].decode("utf-8-sig"), newline=""))
    if reader.fieldnames != CSV_FIELDS:
        raise ValueError("Changed native export schema")
    observations, identities, sums = [], set(), Counter()
    units, options, parties, export_names = defaultdict(set), defaultdict(set), {}, {}
    method_sums = Counter()
    timestamps = set()
    for native in reader:
        if native.pop(None, None) != [""]:
            raise ValueError("Unexpected trailing native export values")
        values = {}
        for field in CSV_FIELDS:
            value = native[field]
            if not isinstance(value, str) or not value.startswith('="') or not value.endswith('"'):
                raise ValueError("Unreviewed native Excel-string wrapper")
            values[field] = value[2:-1]
        contest, literal, unit = values["RaceName"], values["CandidateName"], values["PrecinctName"]
        key = contest, literal.casefold()
        identity = key + (unit,)
        if key not in lookup or identity in identities or values["VoteFor"] != "1":
            raise ValueError("Duplicate or unknown native export observation")
        identities.add(identity)
        candidate = lookup[key]
        party = values["PartyCode"]
        if party != candidate["html_party_css_class_literal"]:
            raise ValueError("Export party disagrees with native HTML party class")
        if key in parties and parties[key] != party:
            raise ValueError("Changed literal export party")
        parties[key] = party
        if key in export_names and export_names[key] != literal:
            raise ValueError("Changed literal export candidate name")
        export_names[key] = literal
        votes = integer(values["CandidateVotes"])
        methods = [integer(values[f]) for f in METHOD_FIELDS]
        if votes != sum(methods):
            raise ValueError("Native option methods do not equal its votes")
        division = bool(re.fullmatch(r"\d{2}-\d{2}", unit))
        if division:
            if unit not in seen:
                raise ValueError("Candidate division missing from participation")
            units[contest].add(unit)
            for field, value in zip(METHOD_FIELDS, methods):
                method_sums[(contest, unit, field)] += value
        elif unit not in {"2nd Congressional", "3rd Congressional", "5th Congressional"} or votes or any(methods):
            raise ValueError("Unreviewed or nonzero special-unit observation")
        if values["PrecinctsReporting"] != "{}/{}".format(
                contests[contest]["reported_divisions"], contests[contest]["total_divisions"]):
            raise ValueError("Export and HTML reporting scopes disagree")
        if not re.fullmatch(r"\d{1,2}/\d{1,2}/2026 \d{1,2}:\d{2}:\d{2} [AP]M", values["CurrentDateTime"]):
            raise ValueError("Missing native export-generation timestamp")
        timestamps.add(values["CurrentDateTime"])
        sums[key] += votes
        options[(contest, unit)].add(key)
        observations.append(dict(**{k: candidate[k] for k in ["year", "state_code", "county_fips", "county", "office", "contest"]},
            native_unit=unit, native_unit_scope="ward_division" if division else "district_labelled_zero",
            candidate_export_literal=literal, export_party_code=party, votes=votes,
            election_day_votes=methods[0], mail_votes=methods[1], provisional_votes=methods[2],
            native_candidate_percentage=values["CandidatePercentage"],
            export_generation_timestamp_literal=values["CurrentDateTime"]))
    expected_options = defaultdict(set)
    for key in lookup:
        expected_options[key[0]].add(key)
    if (set(sums) != set(lookup) or any(sums[k] != r["votes"] for k, r in lookup.items())
            or any(value != expected_options[contest] for (contest, unit), value in options.items())
            or any(len(units[contest]) != row["total_divisions"] for contest, row in contests.items())):
        raise ValueError("Incomplete native option inventory or county reconciliation")
    participation_lookup = {r["native_unit"]: r for r in divisions}
    for (contest, unit, field), value in method_sums.items():
        ballot_field = dict(zip(METHOD_FIELDS, [
            "election_day_ballots", "mail_ballots", "provisional_ballots"]))[field]
        if value > participation_lookup[unit][ballot_field]:
            raise ValueError("Native candidate mode selections exceed division method ballots")
    for code in ["governor_lieutenant_governor", "us_house", "state_house", "state_senate"]:
        partition = set()
        for contest, row in contests.items():
            if row["office"] == code:
                if partition & units[contest]:
                    raise ValueError("Overlapping district division scopes")
                partition.update(units[contest])
        if code != "state_senate" and partition != seen:
            raise ValueError("Incomplete county office division partition")
    totals, comparison = [], []
    for key, candidate in lookup.items():
        candidate.update(candidate_export_literal=export_names[key], export_party_code=parties[key])
        different = (parties[key] != candidate["html_party_css_class_literal"]
                     or bool(candidate["displayed_candidate_party_suffix_literal"]
                             and parties[key] != candidate["displayed_candidate_party_suffix_literal"]))
        comparison.append(dict(**candidate, literal_party_codes_differ=different))
    aggregate = Counter()
    for candidate in lookup.values():
        if candidate["office"] != "ballot_question":
            aggregate[(candidate["office"], candidate["contest"], candidate["export_party_code"])] += candidate["votes"]
    for (code, contest, party), votes in aggregate.items():
        totals.append(dict(**IDENTITY, office=code, contest=contest, export_party_code=party, votes=votes))
    house = [r for r in lookup.values() if r["office"] == "us_house"]
    county.update(house_candidate_votes=sum(r["votes"] for r in house),
                  house_ballot_residual_unclassified=county["ballots_cast"] - sum(r["votes"] for r in house))
    tables = {
        "county-participation.csv": [county],
        "county-ballot-methods.csv": [dict(**IDENTITY, method_literal=m, ballots=county[f]) for m, f in
            [("Polling Place", "election_day_ballots"), ("Mail", "mail_ballots"), ("Provisional", "provisional_ballots")]],
        "county-contest-option-results.csv": list(lookup.values()),
        "county-contest-party-totals.csv": totals,
        "county-contest-totals.csv": list(contests.values()),
        "native-division-participation.csv": divisions,
        "native-unit-option-counts.csv": observations,
        "native-party-label-comparison.csv": comparison,
    }
    audit = dict(**IDENTITY, county_participation=county, contests=len(contests), native_export_rows=len(observations),
        native_participation_divisions=len(divisions), county_option_rows=len(lookup),
        native_explicit_option_zeroes=sum(r["votes"] == 0 for r in observations),
        special_zero_rows=sum(r["native_unit_scope"] == "district_labelled_zero" for r in observations),
        export_generation_timestamps=sorted(timestamps),
        party_code_difference_rows=sum(r["literal_party_codes_differ"] for r in comparison),
        hidden_template_test_banner=True, new_maps_approved=False, publication_approved=False,
        source_rights_status="Private working review; permission to republish original city HTML is not established.",
        candidate_votes_are_not_ballots_or_turnout=True,
        limitations=[
            "Unofficial counts; all divisions reporting does not establish final counting or certification.",
            "Native source updates and export-generation timestamps are separate, not a single source timestamp.",
            "The hidden Testing in Progress template is not a displayed test-status observation.",
            "Literal HTML and CSV party codes are retained separately; neither is silently recoded.",
            "Ballot-question options are not party votes and never enter candidate-party totals.",
            "Special district-labelled zero rows are not extra divisions or inferred provisional votes.",
            "The House ballot residual is unclassified, not inferred undervotes or overvotes.",
            "Ballots/native registrations is registered-voter participation, not eligible-population or demographic turnout.",
            "Missing candidates remain absent, not manufactured zero-party rows. No new geometry is approved.",
            "These independently reviewed county originals do not approve the separately guarded provider test snapshots.",
            "The original city webpages remain private pending source-specific redistribution review; this is not a public release.",
        ])
    return tables, audit


def reproduce(originals, output):
    raw = load_originals(originals)
    tables, audit = review(raw)
    output.mkdir(parents=True, exist_ok=False)
    for name, rows in tables.items():
        with (output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    shutil.copytree(originals, output / "originals")
    shutil.copyfile(__file__, output / "review-philadelphia-county-results.py")
    members = {str(p.relative_to(output)): p.read_bytes() for p in sorted(output.rglob("*")) if p.is_file()}
    checksums = {name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest()) for name, body in members.items()}
    checksum_body = (json.dumps(checksums, indent=2) + "\n").encode()
    (output / "checksums.json").write_bytes(checksum_body)
    members["checksums.json"] = checksum_body
    with zipfile.ZipFile(output / "private-philadelphia-2026-native-review-01.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(members.items()):
            item = zipfile.ZipInfo(name, (2026, 11, 6, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o644 << 16
            archive.writestr(item, body)
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--originals", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True,
                        help="New private working directory; this command does not approve redistribution.")
    args = parser.parse_args()
    result = reproduce(args.originals, args.private_output)
    print(json.dumps({key: result[key] for key in [
        "county_participation", "contests", "native_export_rows", "native_participation_divisions",
        "county_option_rows", "special_zero_rows", "party_code_difference_rows"]}, indent=2))
