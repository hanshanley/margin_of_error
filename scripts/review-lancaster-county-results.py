"""Reconcile Lancaster's complete public JSON and native summary PDFs."""

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
from urllib.parse import unquote
import zipfile

from pypdf import PdfReader


IDENTITY = dict(year=2026, state_code="PA", county_fips="42071", county="Lancaster")
HOST = "https://electionresults.lancastercountypa.gov"
LANDING = HOST + "/results/public/lancaster-county-pa/elections/2026GeneralElection"
API = HOST + "/results/public/api/elections/lancaster-county-pa/2026GeneralElection"
JURISDICTION = "01000000-0c90-bed5-2b89-08dc580b8c0e"
ELECTION = "01000000-0b19-4b56-dfbf-08df2bb51a40"
URLS = {
    "native-landing.html": LANDING, "election.json": API, "data.json": API + "/data",
    "turnout.json": API + "/turnout", "statistics.json": API + "/stats",
    "voter-registration.json": API + "/vr", "localities.json": API + "/localities",
}
PDFS = {
    "summary-results.pdf", "summary-voting-methods.pdf", "summary-party-details.pdf",
    "detailed-contest-table.pdf", "detailed-results.pdf",
}
PUBLIC_SERVICE_KEY = re.compile(rb"\b(?:AIza[0-9A-Za-z_-]{35}|[ps]k\.[A-Za-z0-9._-]+)")
PUBLIC_TELEMETRY_KEY = re.compile(
    rb"""((?:['"]?(?:[A-Za-z_$]*instrumentationKey|licenseKey)['"]?)\s*[:=]\s*['"])(?!\[REDACTED_PUBLIC_SERVICE_KEY\])([^'"\r\n]+)(['"])""",
    re.I,
)


def integer(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError("Invalid native count")
    if isinstance(value, str) and not re.fullmatch(r"\d+|\d{1,3}(?:,\d{3})+", value):
        raise ValueError("Invalid native count")
    number = Decimal(str(value).replace(",", ""))
    if not number.is_finite() or number < 0 or number != number.to_integral_value():
        raise ValueError("Invalid native count")
    return int(number)


def english(values):
    matches = [r["text"] for r in values if r["languageId"] == "en"]
    if len(matches) != 1 or not matches[0]:
        raise ValueError("Ambiguous native English label")
    return matches[0]


def unique(rows, key):
    result = {row[key]: row for row in rows}
    if not result or len(result) != len(rows):
        raise ValueError("Missing or duplicate native identities")
    return result


def leaf_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from leaf_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from leaf_strings(item)


def pdf_text(data):
    return "\n".join(page.extract_text(extraction_mode="layout") for page in PdfReader(io.BytesIO(data)).pages)


def pdf_tables(text, titles, width):
    if not all(s in text for s in ["Lancaster County", "2026 General Election", "November 03, 2026"]):
        raise ValueError("Wrong native PDF identity")
    pattern = re.compile(r"^\s*(.*?)\s{2,}" + r"\s+".join([r"(\d[\d,]*)"] * width)
                         + (r"(?:\s+[\d.]+\s*%)?" if width == 1 else "") + r"\s*$")
    tables, current = {}, None
    for line in text.splitlines():
        if line.strip() in titles:
            current = line.strip()
            if current in tables:
                raise ValueError("Duplicate native PDF contest")
            tables[current] = {}
        elif current is not None:
            match = pattern.fullmatch(line)
            if match:
                label = match[1].strip()
                if label in tables[current]:
                    raise ValueError("Duplicate native PDF row")
                tables[current][label] = tuple(integer(n) for n in match.groups()[1:])
    if set(tables) != set(titles):
        raise ValueError("Missing native PDF contest")
    return tables


def load_originals(folder):
    receipts = json.loads((folder / "receipts.json").read_bytes())
    names = set(URLS) | PDFS
    if ({p.name for p in folder.iterdir()} != names | {"receipts.json"}
            or len(receipts) != len(names) or {r["file"] for r in receipts} != names):
        raise ValueError("Incomplete original receipt inventory")
    raw = {}
    for receipt in receipts:
        name = receipt["file"]
        data = (folder / name).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if (receipt["http_status"] != 200 or receipt["bytes"] != len(data)
                or receipt["sha256"] != digest or receipt["final_url"] != receipt["url"]):
            raise ValueError("Original acquisition receipt mismatch")
        if name in URLS and receipt["url"] != URLS[name]:
            raise ValueError("Unexpected public source URL")
        if name in PDFS:
            prefix = HOST + "/cdn/results/" + JURISDICTION + "/"
            if not receipt["url"].startswith(prefix) or not data.startswith(b"%PDF-"):
                raise ValueError("Unexpected public report")
        else:
            if PUBLIC_SERVICE_KEY.search(data) or PUBLIC_TELEMETRY_KEY.search(data):
                raise ValueError("Unredacted public service key")
            screen = receipt.get("redaction", {})
            replacements = data.count(b"[REDACTED_PUBLIC_SERVICE_KEY]")
            if (not re.fullmatch(r"[a-f0-9]{64}", screen.get("original_sha256", ""))
                    or screen.get("original_bytes", 0) <= 0
                    or screen.get("replacements") != replacements
                    or (not replacements and (screen["original_sha256"] != digest
                                               or screen["original_bytes"] != len(data)))):
                raise ValueError("Missing explicit source screening receipt")
        raw[name] = data
    declarations = {s for s in leaf_strings(json.loads(raw["election.json"])["publicReportCategories"])
                    if s.lower().endswith(".pdf")}
    acquired = [unquote(r["url"].rsplit("/", 1)[-1]) for r in receipts if r["file"] in PDFS]
    if len(set(acquired)) != len(PDFS) or set(acquired) != declarations:
        raise ValueError("Incomplete election-declared PDF inventory")
    return raw


def review(raw):
    data = json.loads(raw["data.json"])
    election = json.loads(raw["election.json"])
    if (data["election"] != election or election["id"] != ELECTION
            or data["jurisdiction"]["id"] != JURISDICTION
            or english(election["name"]) != "2026 General Election"
            or not election["electionDate"].startswith("2026-11-03")
            or election["isProduction"] is not True or election["isOfficialResults"] is not False
            or election["isPrimary"] is not False):
        raise ValueError("Wrong election, publication status or mixed snapshot")
    for filename, key in [("statistics.json", "statistics"),
                          ("voter-registration.json", "voterRegistration")]:
        page = json.loads(raw[filename])
        if (page["limit"] != 0 or page["offset"] != 0
                or page["totalRecordCount"] != len(page["data"]) or page["data"] != data[key]):
            raise ValueError("Incomplete auxiliary pagination or mixed snapshot")
    units = unique(data["precincts"], "id")
    if sum(integer(r["value"]) for r in election["precinctReportingStatus"]) != len(units):
        raise ValueError("County reporting inventory does not reconcile")
    turnout = json.loads(raw["turnout.json"])
    observations = unique(turnout["data"], "id")
    if (turnout["limit"] != 0 or turnout["offset"] != 0
            or turnout["totalRecordCount"] != len(units)
            or data["voterTurnout"] != turnout["data"] or set(observations) != set(units)):
        raise ValueError("Incomplete turnout pagination or unit coverage")
    ballots, registrations = integer(election["ballotsCast"]), integer(election["totalVoters"])
    if (not registrations or ballots > registrations
            or sum(integer(r["ballotsCast"]) for r in observations.values()) != ballots
            or sum(integer(r["voterRegistration"]) for r in observations.values()) != registrations):
        raise ValueError("Unit participation does not reconcile to county")
    unit_rows = []
    for key, row in observations.items():
        if (row["precinctName"] != english(units[key]["name"])
                or integer(row["ballotsCast"]) != integer(row["voterTurnout"])
                or integer(row["ballotsCast"]) > integer(row["voterRegistration"])):
            raise ValueError("Changed native unit identity or participation")
        unit_rows.append(dict(**IDENTITY, native_unit_id=key, native_unit_name=row["precinctName"],
                              ballots=integer(row["ballotsCast"]),
                              native_voter_turnout_count=integer(row["voterTurnout"]),
                              registrations=integer(row["voterRegistration"]),
                              native_reporting_status=units[key]["reportingStatus"]))
    contests = unique(data["ballotItems"], "id")
    titles = {english(c["name"]) for c in contests.values()}
    if len(titles) != len(contests):
        raise ValueError("Duplicate native contest titles")
    texts = {name: pdf_text(raw[name]) for name in
             ["summary-results.pdf", "summary-voting-methods.pdf", "summary-party-details.pdf"]}
    summaries = [pdf_tables(texts[name], titles, 1) for name in
                 ["summary-results.pdf", "summary-party-details.pdf"]]
    method_tables = pdf_tables(texts["summary-voting-methods.pdf"], titles, 4)
    parties = unique(election["parties"], "id")
    groups = unique(election["countGroups"], "groupId")
    group_names = [english(r["groupName"]) for r in groups.values()]
    if group_names != ["Election Day Voting", "Mail Voting", "Provisional Voting"]:
        raise ValueError("Changed native PDF voting-method columns")
    statuses = {english(r["groupName"]): r["reportingStatusClientTextKey"]
                for r in election["groupReportingStatus"]}
    if set(statuses) != set(group_names):
        raise ValueError("Missing voting-method status")
    options, modes, contest_rows, accounting, party_rows = [], [], [], [], []
    option_ids = set()
    for contest in contests.values():
        title = english(contest["name"])
        if contest["contestType"] not in ["Candidate", "BallotMeasure"]:
            raise ValueError("Unreviewed native contest type")
        counts = contest["summaryResults"]["ballotOptions"]
        unique(counts, "id")
        expected, party_totals = {}, defaultdict(int)
        coverage = contest["reportingStatus"]
        if (coverage["asOf"] != election["asOf"]
                or not 0 < coverage["totalUnits"] <= len(units)
                or not 0 <= coverage["reportingUnits"] <= coverage["totalUnits"]
                or sum(integer(r["value"]) for r in coverage["reportingStatusDetails"]) != coverage["totalUnits"]):
            raise ValueError("Mixed or incomplete contest reporting snapshot")
        for option in counts:
            if option["id"] in option_ids:
                raise ValueError("Duplicate native option identity")
            option_ids.add(option["id"])
            if not isinstance(option["isWriteIn"], bool):
                raise ValueError("Invalid native write-in flag")
            name, party = english(option["name"]), option["party"]
            party_name = english(party["name"]) if party else ""
            if party and (party["id"] not in parties
                          or any(party[k] != parties[party["id"]][k] for k in ["name", "abbreviation"])):
                raise ValueError("Changed native party identity")
            if contest["contestType"] == "Candidate" and not party and not option["isWriteIn"]:
                raise ValueError("Unexplained missing candidate party")
            label = name + (" (" + party_name + ")" if party else "")
            if label in expected:
                raise ValueError("Duplicate native option label")
            native_groups = unique(option["groupResults"], "groupId")
            if set(native_groups) != set(groups):
                raise ValueError("Incomplete option voting methods")
            vector = [integer(option["voteCount"])]
            for group_id, definition in groups.items():
                item = native_groups[group_id]
                group_name = english(definition["groupName"])
                if item["groupName"] != definition["groupName"]:
                    raise ValueError("Changed native voting-method identity")
                value = integer(item["voteCount"])
                vector.append(value)
                modes.append(dict(**IDENTITY, contest_id=contest["id"], option_id=option["id"],
                                  native_group_id=group_id, native_group_name=group_name, votes=value,
                                  native_reporting_status=statuses[group_name]))
            if sum(vector[1:]) != vector[0]:
                raise ValueError("Option voting methods do not reconcile")
            expected[label] = tuple(vector)
            kind = "ballot_measure_option" if contest["contestType"] == "BallotMeasure" else (
                "write_in" if option["isWriteIn"] else "candidate")
            options.append(dict(**IDENTITY, contest_id=contest["id"], native_contest=title,
                                option_id=option["id"], native_option_id=option["nativeId"],
                                native_option_name=name, option_kind=kind, native_party_name=party_name,
                                native_party_abbreviation=party["abbreviation"] if party else "",
                                native_party_id=party["id"] if party else "", votes=vector[0],
                                native_is_write_in=option["isWriteIn"],
                                native_is_qualified_write_in=option["isQualifiedWriteIn"],
                                native_is_winner=option["isWinner"]))
            if contest["contestType"] == "Candidate":
                party_totals[(party["id"] if party else "", party_name,
                              party["abbreviation"] if party else "")] += vector[0]
        for summary in summaries:
            if (set(summary[title]) != set(expected) | {"Total Votes Cast"}
                    or any(summary[title][label] != (values[0],) for label, values in expected.items())
                    or summary[title]["Total Votes Cast"] != (integer(contest["voteTotal"]),)):
                raise ValueError("Native summary PDF option inventory or totals disagree")
        table = method_tables[title]
        if (set(table) != set(expected) | {"Total Votes Cast", "Overvotes", "Undervotes", "Total Ballots Cast"}
                or any(table[label] != values for label, values in expected.items())
                or table["Total Votes Cast"] != tuple(sum(v[i] for v in expected.values()) for i in range(4))
                or table["Total Votes Cast"][0] != integer(contest["voteTotal"])):
            raise ValueError("Native method PDF options or accounting disagree")
        for label in ["Total Votes Cast", "Overvotes", "Undervotes"]:
            if sum(table[label][1:]) != table[label][0]:
                raise ValueError("Native PDF accounting methods do not reconcile")
        residual = table["Total Ballots Cast"][0] - sum(
            table[label][0] for label in ["Total Votes Cast", "Overvotes", "Undervotes"])
        if residual < 0:
            raise ValueError("Native contest accounting exceeds ballots")
        for key, label in [("underVoteCount", "Undervotes"), ("overVoteCount", "Overvotes")]:
            if contest[key] is not None and integer(contest[key]) != table[label][0]:
                raise ValueError("Nonmissing API/PDF accounting disagrees")
        mode_ballots_usable = (sum(table["Total Ballots Cast"][1:]) == table["Total Ballots Cast"][0]
                               and all(table["Total Ballots Cast"][i] >= sum(
                                   table[label][i] for label in ["Total Votes Cast", "Overvotes", "Undervotes"])
                                       for i in range(1, 4)))
        contest_rows.append(dict(**IDENTITY, contest_id=contest["id"], native_contest=title,
                                 native_contest_type=contest["contestType"],
                                 native_vote_for_json=json.dumps(contest["voteFor"]),
                                 votes=integer(contest["voteTotal"]),
                                 native_api_undervotes=contest["underVoteCount"],
                                 native_api_overvotes=contest["overVoteCount"],
                                 pdf_ballots=table["Total Ballots Cast"][0],
                                 pdf_undervotes=table["Undervotes"][0], pdf_overvotes=table["Overvotes"][0],
                                 remaining_unclassified_ballots=residual,
                                 reporting_units=coverage["reportingUnits"], total_units=coverage["totalUnits"],
                                 native_reporting_details_json=json.dumps(coverage["reportingStatusDetails"],
                                                                          sort_keys=True)))
        for i, group_name in enumerate(["TOTAL"] + group_names):
            reported = i == 0 or statuses[group_name] != "reporting-status-not-reported"
            usable = i == 0 or (mode_ballots_usable and reported)
            accounting.append(dict(**IDENTITY, contest_id=contest["id"], native_contest=title,
                                   native_group_name=group_name, pdf_votes=table["Total Votes Cast"][i],
                                   pdf_undervotes=table["Undervotes"][i], pdf_overvotes=table["Overvotes"][i],
                                   native_pdf_ballots=table["Total Ballots Cast"][i],
                                   usable_as_actual_ballot_count=usable,
                                   qualification="" if usable else
                                   "Native method ballot fields do not reconcile or this method is not "
                                   "reported; not usable as actual method ballot counts."))
        for (party_id, party_name, abbreviation), votes in party_totals.items():
            party_rows.append(dict(**IDENTITY, contest_id=contest["id"], native_contest=title,
                                   native_party_id=party_id, native_party_name=party_name,
                                   native_party_abbreviation=abbreviation, votes=votes,
                                   reporting_units=coverage["reportingUnits"], total_units=coverage["totalUnits"]))
    office_ballots = Counter()
    for row in contest_rows:
        if row["native_contest_type"] == "Candidate":
            matches = [prefix for prefix in [
                "GOVERNOR AND LIEUTENANT GOVERNOR", "REPRESENTATIVE IN CONGRESS",
                "SENATOR IN THE GENERAL ASSEMBLY", "REPRESENTATIVE IN THE GENERAL ASSEMBLY",
            ] if row["native_contest"].startswith(prefix)]
            if len(matches) != 1:
                raise ValueError("Unreviewed native candidate office")
            office_ballots[matches[0]] += row["pdf_ballots"]
    if any(value > ballots for value in office_ballots.values()):
        raise ValueError("Office district accounting exceeds county ballots")
    for label, value in [("Ballots Cast", ballots), ("Voter Registration", registrations)]:
        for text in texts.values():
            matches = re.findall(r"^" + label + r"\s+([\d,]+)\s*$", text, re.M)
            if len(matches) != 1 or integer(matches[0]) != value:
                raise ValueError("PDF county participation does not reconcile")
    printed = re.findall(r"^Voter Turnout\s+([\d.]+)\s*%\s*$", texts["summary-results.pdf"], re.M)
    rate = (Decimal(100) * ballots / registrations).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if printed != [str(rate)]:
        raise ValueError("Printed county turnout does not reconcile")
    native_party_statistics = []
    for party in parties.values():
        name = english(party["name"])
        for statistic in ["Ballots Cast", "VoterRegistration", "Turnout"]:
            matches = re.findall(r"^" + re.escape(name + " - " + statistic)
                                 + r"[ \t]*([^\n]*)$", texts["summary-party-details.pdf"], re.M)
            if len(matches) != 1:
                raise ValueError("Missing native party-statistic field")
            native_party_statistics.append(dict(**IDENTITY, native_party_name=name,
                                                native_statistic=statistic, native_printed_value=matches[0].strip(),
                                                usable_for_party_participation=False,
                                                qualification="Native zero/blank fields are not validated "
                                                "party participation or denominators."))
    aggregate = re.findall(r"^Votes Cast\s+([\d,]+)\s*$", texts["summary-voting-methods.pdf"], re.M)
    if len(aggregate) != 1 or integer(aggregate[0]) != sum(r["votes"] for r in options):
        raise ValueError("Native all-contest selection aggregate does not reconcile")
    audit = dict(**IDENTITY, as_of_utc=election["asOf"], publish_date_utc=election["publishDate"],
                 native_publish_version_id=election["publishVersionId"], official_results=False,
                 ballots=ballots, registrations=registrations, native_pdf_turnout_percent=printed[0],
                 native_all_contest_selections_not_ballots=integer(aggregate[0]),
                 native_ballot_item_count_metadata=election["ballotItemCount"],
                 acquired_contests=len(contests), native_units=len(units), native_options=len(options),
                 explicit_option_zeroes=sum(r["votes"] == 0 for r in options),
                 native_group_reporting_status=election["groupReportingStatus"],
                 native_precinct_reporting_status=election["precinctReportingStatus"],
                 candidate_votes_are_not_ballots=True, map_promotion_approved=False,
                 native_unit_geometry_acquired=False, independent_county_parent_acquired=False,
                 auxiliary_registration_rows=len(data["voterRegistration"]),
                 auxiliary_statistics_rows=len(data["statistics"]),
                 native_ballot_item_count_metadata_is_not_contest_inventory=True,
                 native_party_statistics_are_not_validated_participation=True,
                 district_ballot_totals_by_office=dict(office_ballots),
                 reproduction_command="python review-lancaster-county-results.py --source originals --output reproduced",
                 runtime_dependencies=["pypdf"])
    return audit, {
        "county-participation.csv": [
            dict(**IDENTITY, ballots=ballots, registrations=registrations,
                 native_pdf_turnout_percent=printed[0], as_of_utc=election["asOf"],
                 publish_date_utc=election["publishDate"], official_results=False,
                 native_group_reporting_status_json=json.dumps(election["groupReportingStatus"], sort_keys=True),
                 native_precinct_reporting_status_json=json.dumps(election["precinctReportingStatus"], sort_keys=True),
                 qualification="Reported ballots / native registrations; counting status retained separately. "
                 "Not final, eligible-population or demographic turnout.")],
        "county-option-results.csv": options, "county-option-mode-results.csv": modes,
        "county-contest-accounting.csv": contest_rows, "county-contest-accounting-modes.csv": accounting,
        "county-literal-party-totals.csv": party_rows, "native-unit-participation.csv": unit_rows,
        "native-party-statistics.csv": native_party_statistics,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = load_originals(args.source)
    audit, tables = review(raw)
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise ValueError("Output must be empty")
    shutil.copytree(args.source, args.output / "originals")
    shutil.copyfile(__file__, args.output / Path(__file__).name)
    for name, rows in tables.items():
        with (args.output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (args.output / "audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    checksums = {str(path.relative_to(args.output)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in sorted(args.output.rglob("*")) if path.is_file()}
    (args.output / "checksums.json").write_text(json.dumps(checksums, indent=2, sort_keys=True) + "\n")
    archive = args.output / "complete-lancaster-2026-county-results-01.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for path in sorted(args.output.rglob("*")):
            if path.is_file() and path != archive:
                entry = zipfile.ZipInfo(str(path.relative_to(args.output)), date_time=(2026, 11, 5, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.create_system = 3
                entry.external_attr = 0o644 << 16
                package.writestr(entry, path.read_bytes())
    print(json.dumps(dict(audit=audit, table_rows={k: len(v) for k, v in tables.items()},
                          archive_bytes=archive.stat().st_size,
                          archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest()), indent=2))


if __name__ == "__main__":
    main()
