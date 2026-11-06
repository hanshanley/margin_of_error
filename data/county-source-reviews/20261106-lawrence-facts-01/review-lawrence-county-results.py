"""Reproduce Lawrence numerical facts while keeping mail-only and district scopes distinct."""

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


INDEX = "https://www.lawrencecountypa.gov/departments/voter-elections/election-results"
SOURCES = {
    "county": "https://www.lawrencecountypa.gov/getmedia/4e14f6c4-9bae-435d-af0b-a7fb38adec3c/2026-General-Election-Unofficial-First-Drop.pdf",
    "mail_only": "https://www.lawrencecountypa.gov/getmedia/90d467d8-6de9-435f-9e8c-6dad2c70f93d/2026-General-Election-Unoffical-Mail-in-Results.pdf",
    "unit": "https://www.lawrencecountypa.gov/getmedia/d4fc72b7-2447-44e9-bec5-79a0084d9e78/2026-General-Election-Unofficial-Precinct-Report.pdf",
}
FILES = {"county": "lawrence-summary.pdf", "mail_only": "lawrence-mail-summary.pdf",
         "unit": "lawrence-precinct.pdf"}
SOURCE_HASHES = {
    "lawrence-parent.html": (74153, "f44c11d83dd29a0b6fc87992c5e51bfd894105cc92f40cb76e27a5e595b07844"),
    "lawrence-summary.pdf": (40858, "297c129003670334b40df85e5c6e846559803ed2f3edd00f5d1c0ea079692699"),
    "lawrence-mail-summary.pdf": (40665, "06b008488dbaeb0e65caba8a3d87165a945ef5ea8313fe571af7e0978771a9f5"),
    "lawrence-precinct.pdf": (1270911, "112d50a55997b1f1de0969df8e4e0fa246a3f0e118e3eaa0a1377db7a0eb571f"),
}
OFFICES = (
    "GOVERNOR AND LIEUTENANT GOVERNOR", "REPRESENTATIVE IN CONGRESS",
    "SENATOR IN THE GENERAL ASSEMBLY DISTRICT 50",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 8TH DISTRICT",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 9TH DISTRICT",
)
MODES = ("Total", "Election Day", "Mail Vote", "Provisional Vote")
NUMBER = r"(?:0|[1-9]\d*)(?:,\d{3})*"
HEADERS = set("STATISTICS TOTAL ELECTION DAY MAIL VOTE PROVISION AL PROVISIONA L %".split())
REPORT_FACTS_SHA256 = "cc6bee4894c1827a10a0b3bbca526ed8308736b05b8f5214a146651dbb20ecb2"
QUALIFICATIONS = [
    "The saved originals report 31,401 ballots and 57,470 registered voters, not the differing preliminary web extraction.",
    "All 74 distinct native unit participation rows reconcile to county registrations, ballots, blank ballots and modes.",
    "The current total is 25,293 Election Day + 6,108 Mail Vote + an explicit provisional zero; blank ballots are separately 0 + 2 + 0.",
    "The separate 8:21 PM mail-only report is 6,108 mail ballots, not another all-mode county total or zero Election Day participation.",
    "Current county, mail-only and unit clocks are respectively 9:27 PM, 8:21 PM and 9:39 PM on November 3; no timezone is supplied.",
    "The current report declares 74/74 Election Day and absentee/early reporting, 0/74 complete and 74/74 partially reported; unofficial is not certified or finished counting.",
    "The calculated registered-voter fraction and native printed 54.64% are separate, not CVAP/VAP/VEP or demographic turnout.",
    "Two native unit printed rates differ from the calculated fraction by just over half a final printed decimal point; their usable rates are withheld and both values remain in the rate-check table.",
    "Native candidate selections, literal parties, write-in totals and overlapping write-in details stay separate from participation and from one another.",
    "State Senate District 50 includes only 58 reporting units; the two state-House districts partition the 74 units. Do not assign each district the whole-county electorate.",
    "Unit reports supply overvotes, undervotes and contest totals; county summaries do not. Unit-derived district electorates are explicitly derived, not native county-summary denominators.",
    "No native FIPS, new precinct geometry, demographic turnout, statewide completion or certification approval. Original HTML/PDF presentation templates remain private.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    require(isinstance(value, str) and re.fullmatch(NUMBER, value), "Invalid native integer")
    return int(value.replace(",", ""))


def counts(values):
    require(isinstance(values, list) and len(values) == 4, "Incomplete native count vector")
    result = [integer(value) for value in values]
    require(result[0] == sum(result[1:]), "Native mode vector does not reconcile")
    return result


def digest(reports):
    return hashlib.sha256(json.dumps(reports, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def parse_pages(texts, kind):
    require(kind in SOURCES and len(texts) == (206 if kind == "unit" else 4), "Incomplete report")
    pages = []
    for ordinal, text in enumerate(texts, 1):
        text = re.sub(r"(\d+\.\d+%)\s*Voter Turnout - Total", r"Voter Turnout - Total \1", text)
        lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
        if re.fullmatch(r"Page \d+ of \d+", lines[-2]):
            lines[-3:-1] = [" ".join(lines[-3:-1])]
        require(lines[:3] == ["Summary Results Report UNOFFICIAL RESULTS",
                "2026 General", "November 3, 2026 Lawrence"], "Changed election, county or status")
        footer = re.fullmatch(r"(Election|Precinct) Summary - (11/03/2026 \d{1,2}:\d{2} [AP]M) Page (\d+) of (\d+)",
                              lines[-2])
        require(footer and footer[1] == ("Precinct" if kind == "unit" else "Election")
                and int(footer[3]) == ordinal and int(footer[4]) == len(texts)
                and lines[-1] == "Report generated with Electionware Copyright \u00a9 2007-2020",
                "Changed page, timestamp or pagination")
        page = dict(page_number=ordinal, unit=lines[3] if kind == "unit" else "Lawrence",
                    source_update_literal=footer[2], declared_timezone=None,
                    native_status_literal="UNOFFICIAL RESULTS", participation=None, reporting=[], contests=[])
        contest = None
        for line in lines[4 if kind == "unit" else 3:-2]:
            if set(line.split()) <= HEADERS:
                continue
            if line in OFFICES:
                contest = dict(office_literal=line, vote_for_literal=None, rows=[], reporting=[])
                page["contests"].append(contest)
            elif line == "Vote For 1":
                require(contest is not None and contest["vote_for_literal"] is None, "Duplicate vote-for scope")
                contest["vote_for_literal"] = line
            elif line.startswith("Registered Voters - Total "):
                require(page["participation"] is None, "Duplicate participation")
                page["participation"] = dict(registered_voters_literal=line.split()[-1])
            elif line.startswith(("Ballots Cast - Total ", "Ballots Cast - Blank ")):
                field = "ballot_count_literals" if " - Total " in line else "blank_count_literals"
                require(page["participation"] is not None and field not in page["participation"],
                        "Unexpected or duplicate ballots")
                page["participation"][field] = line.split()[-4:]
            elif line.startswith("Voter Turnout - Total "):
                require(page["participation"] is not None
                        and "printed_turnout_literal" not in page["participation"], "Duplicate turnout")
                page["participation"]["printed_turnout_literal"] = line.split()[-1]
            elif line.startswith("Precincts Reporting "):
                match = re.fullmatch(r"Precincts Reporting (\d+) of (\d+)", line)
                require(contest is not None and match is not None, "Invalid contest reporting")
                contest["reporting"].append(dict(reported_literal=match[1], total_literal=match[2]))
            elif line.startswith(("Election Day Precincts", "Absentee/ Early Precincts",
                                  "Precincts Complete", "Precincts Partially Reported")):
                match = re.fullmatch(r"(.+?) (\d+) of (\d+) (\d+) (\d+) (\d+)", line)
                require(kind != "unit" and match is not None, "Invalid county reporting")
                page["reporting"].append(dict(label_literal=match[1], reported_literal=match[2],
                    total_literal=match[3], mode_count_literals=list(match.groups()[3:])))
            else:
                match = re.fullmatch(rf"(.+?) ({NUMBER})(?: (\d+\.\d+%))? ({NUMBER}) ({NUMBER}) ({NUMBER})", line)
                require(contest is not None and match is not None, "Unrecognized native result line: " + line)
                contest["rows"].append(dict(label_literal=match[1],
                    count_literals=[match[2], match[4], match[5], match[6]], printed_share_literal=match[3]))
        pages.append(page)
    return dict(kind=kind, source_url=SOURCES[kind], pages=pages)


def validate(facts):
    require(facts["schema"] == "lawrence-2026-complete-numerical-facts-v1", "Changed schema")
    require(set(facts["source_receipts"]) == set(SOURCE_HASHES), "Incomplete source receipts")
    for name, (size, sha) in SOURCE_HASHES.items():
        receipt = facts["source_receipts"][name]
        url = INDEX if name == "lawrence-parent.html" else SOURCES[next(k for k in FILES if FILES[k] == name)]
        require(receipt["url"] == receipt["final_url"] == url and receipt["status"] == 200
                and receipt["bytes"] == size and receipt["sha256"] == sha, "Changed source provenance")
    require([r["kind"] for r in facts["reports"]] == list(SOURCES), "Incomplete native report inventory")
    participation, contests = {}, {}
    for report in facts["reports"]:
        kind = report["kind"]
        require(report["source_url"] == SOURCES[kind] and len(report["pages"]) == (206 if kind == "unit" else 4),
                "Incomplete native pages")
        for ordinal, page in enumerate(report["pages"], 1):
            key = kind, page["unit"]
            require(page["page_number"] == ordinal and page["declared_timezone"] is None
                    and page["native_status_literal"] == "UNOFFICIAL RESULTS"
                    and page["source_update_literal"] == "11/03/2026 " + {
                        "county": "9:27 PM", "mail_only": "8:21 PM", "unit": "9:39 PM"}[kind],
                    "Changed page, clock or status")
            native = page["participation"]
            if native is not None:
                require(key not in participation and set(native) == {"registered_voters_literal",
                        "ballot_count_literals", "blank_count_literals", "printed_turnout_literal"},
                        "Duplicate or incomplete participation")
                ballots, blanks = counts(native["ballot_count_literals"]), counts(native["blank_count_literals"])
                denominator = integer(native["registered_voters_literal"])
                require(denominator > 0 and ballots[0] <= denominator
                        and all(b <= a for a, b in zip(ballots, blanks)), "Invalid participation scope")
                require(re.fullmatch(r"\d+\.\d{2}%", native["printed_turnout_literal"]),
                        "Invalid printed turnout")
                if kind != "unit":
                    require(abs(float(native["printed_turnout_literal"].removesuffix("%"))
                                - 100 * ballots[0] / denominator) <= .005001, "Printed turnout does not reconcile")
                participation[key] = native
            for contest in page["contests"]:
                identity = (*key, contest["office_literal"])
                require(identity not in contests and identity[2] in OFFICES
                        and contest["vote_for_literal"] == "Vote For 1", "Duplicate or unknown contest")
                rows = {r["label_literal"]: counts(r["count_literals"]) for r in contest["rows"]}
                require(len(rows) == len(contest["rows"])
                        and {"Write-In Totals", "Not Assigned", "Total Votes Cast"} <= set(rows),
                        "Duplicate or missing candidate/accounting rows")
                require(all(label in {"Write-In Totals", "Not Assigned", "Total Votes Cast",
                        "Overvotes", "Undervotes", "Contest Totals"}
                        or label.startswith(("DEM ", "REP ", "LIB ", "Write-In: ")) for label in rows),
                        "Unknown native row type")
                selected = [v for label, v in rows.items()
                            if label == "Write-In Totals" or label.startswith(("DEM ", "REP ", "LIB "))]
                require([sum(v[i] for v in selected) for i in range(4)] == rows["Total Votes Cast"],
                        "Candidate selections do not reconcile")
                details = [v for label, v in rows.items() if label == "Not Assigned" or label.startswith("Write-In: ")]
                require([sum(v[i] for v in details) for i in range(4)] == rows["Write-In Totals"],
                        "Write-in details do not reconcile")
                require(("Contest Totals" in rows) == (kind == "unit"), "Changed native accounting availability")
                if kind == "unit":
                    require({"Overvotes", "Undervotes"} <= set(rows)
                            and [sum(rows[label][i] for label in ("Total Votes Cast", "Overvotes", "Undervotes"))
                                 for i in range(4)] == rows["Contest Totals"],
                            "Unit contest accounting does not reconcile")
                    require(rows["Contest Totals"] == counts(participation[key]["ballot_count_literals"]),
                            "Unit contest electorate differs from native ballots")
                contests[identity] = rows
    require(len(participation) == 76 and len(contests) == 290, "Incomplete unit or contest inventory")
    units = [unit for kind, unit in participation if kind == "unit"]
    county, mail = participation["county", "Lawrence"], participation["mail_only", "Lawrence"]
    require(counts(county["ballot_count_literals"]) == [31401, 25293, 6108, 0]
            and counts(county["blank_count_literals"]) == [2, 0, 2, 0]
            and integer(county["registered_voters_literal"]) == 57470, "Changed county participation")
    require(counts(mail["ballot_count_literals"]) == [6108, 0, 6108, 0]
            and counts(mail["blank_count_literals"]) == [2, 0, 2, 0]
            and mail["registered_voters_literal"] == county["registered_voters_literal"],
            "Mail-only scope changed")
    require(sum(integer(participation["unit", u]["registered_voters_literal"]) for u in units) == 57470,
            "Unit registrations do not equal county")
    for field in ("ballot_count_literals", "blank_count_literals"):
        require([sum(counts(participation["unit", u][field])[i] for u in units) for i in range(4)]
                == counts(county[field]), "Unit ballots/blanks do not equal county")
    for office in OFFICES:
        county_rows = contests["county", "Lawrence", office]
        native = [rows for (kind, unit, label), rows in contests.items() if kind == "unit" and label == office]
        require(len(native) == dict(zip(OFFICES, (74, 74, 58, 23, 51)))[office], "Changed district unit inventory")
        for label, values in county_rows.items():
            require(all(label in rows for rows in native)
                    and [sum(rows[label][i] for rows in native) for i in range(4)] == values,
                    "Unit selections do not equal county")
            require(contests["mail_only", "Lawrence", office][label] == [values[2], 0, values[2], 0],
                    "Separate mail snapshot differs from county mail counts")
    require(digest(facts["reports"]) == REPORT_FACTS_SHA256, "Complete reviewed report facts changed")
    return facts


def build(facts, output):
    validate(facts)
    facts = json.loads(json.dumps(facts, sort_keys=True))
    output.mkdir(parents=True, exist_ok=False)
    tables = {name: [] for name in ("county-participation.csv", "mail-only-participation.csv",
        "native-unit-participation.csv", "native-candidate-results.csv", "native-contest-accounting.csv",
        "county-literal-party-totals.csv", "native-reporting-statements.csv", "native-source-pages.csv",
        "native-turnout-checks.csv")}
    parties = Counter()
    common = dict(year=2026, state_code="PA", county="Lawrence")
    for report in facts["reports"]:
        kind = report["kind"]
        for page in report["pages"]:
            base = dict(**common, native_unit=page["unit"], source_report=kind,
                source_page=page["page_number"], source_url=report["source_url"],
                source_update_literal=page["source_update_literal"], declared_timezone="",
                native_status_literal=page["native_status_literal"])
            tables["native-source-pages.csv"].append(base)
            native = page["participation"]
            if native is not None:
                ballots, blanks = counts(native["ballot_count_literals"]), counts(native["blank_count_literals"])
                denominator = integer(native["registered_voters_literal"])
                calculated = 100 * ballots[0] / denominator
                difference = float(native["printed_turnout_literal"].removesuffix("%")) - calculated
                rate_usable = abs(difference) <= .005001
                tables["native-turnout-checks.csv"].append(dict(**base,
                    native_printed_turnout=native["printed_turnout_literal"],
                    calculated_registered_turnout_percent=calculated,
                    printed_minus_calculated_percentage_points=difference,
                    within_half_final_printed_decimal_point=rate_usable))
                name = {"county": "county-participation.csv", "mail_only": "mail-only-participation.csv",
                        "unit": "native-unit-participation.csv"}[kind]
                tables[name].append(dict(**base, ballots_cast=ballots[0], election_day_ballots=ballots[1],
                    mail_ballots=ballots[2], provisional_ballots=ballots[3], registered_voters=denominator,
                    native_printed_turnout=native["printed_turnout_literal"],
                    registered_turnout_percent=calculated if rate_usable else "", blank_ballots=blanks[0],
                    native_count_literals_json=json.dumps(native), qualifications_json=json.dumps(QUALIFICATIONS)))
            for row in page["reporting"]:
                tables["native-reporting-statements.csv"].append(dict(**base, office_literal="", **row))
            for contest in page["contests"]:
                scope = dict(**base, office_literal=contest["office_literal"], vote_for_literal=contest["vote_for_literal"])
                for row in contest["reporting"]:
                    tables["native-reporting-statements.csv"].append(dict(**base,
                        office_literal=contest["office_literal"], label_literal="Precincts Reporting",
                        **row, mode_count_literals=[]))
                for native in contest["rows"]:
                    label, values = native["label_literal"], counts(native["count_literals"])
                    party = label.split(" ", 1)[0] if label.startswith(("DEM ", "REP ", "LIB ")) else ""
                    accounting = label in {"Total Votes Cast", "Overvotes", "Undervotes", "Contest Totals"}
                    row_kind = ("candidate" if party else "accounting" if accounting else
                                "write_in_total" if label == "Write-In Totals" else "write_in_detail")
                    row = dict(**scope, label_literal=label, party_literal=party, row_kind=row_kind,
                        printed_share_literal=native["printed_share_literal"] or "",
                        native_count_literals_json=json.dumps(native["count_literals"]))
                    row.update(zip(MODES, values))
                    tables["native-contest-accounting.csv" if accounting else "native-candidate-results.csv"].append(row)
                    if kind == "county" and party:
                        for mode, value in zip(MODES, values):
                            parties[contest["office_literal"], party, mode] += value
    tables["county-literal-party-totals.csv"] = [dict(**common, office_literal=office,
        party_literal=party, mode_literal=mode, candidate_votes=value)
        for (office, party, mode), value in parties.items()]
    for name, rows in tables.items():
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / name).write_text(stream.getvalue())
    (output / "source-records.json.gz").write_bytes(gzip.compress(
        (json.dumps(facts, sort_keys=True, indent=2) + "\n").encode(), mtime=0))
    audit = dict(scope="Lawrence only; complete numerical facts, not source presentation templates",
        maps_approved=False, demographic_turnout_approved=False, statewide_completion_approved=False,
        county_participation=tables["county-participation.csv"][0], qualifications=QUALIFICATIONS,
        table_rows={name: len(rows) for name, rows in tables.items()})
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "source-receipts.json").write_text(json.dumps(facts["source_receipts"], indent=2) + "\n")
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output / "checksums.json").write_text(json.dumps({p.name: dict(bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(output.iterdir())}, indent=2) + "\n")
    target = output / "complete-lawrence-2026-numerical-facts-01.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path != target:
                info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
                info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
                archive.writestr(info, path.read_bytes())
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--private-source", type=Path)
    source.add_argument("--facts", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.private_source:
        import fitz
        import pdfplumber
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        receipts = {r["file"]: r for r in json.loads((args.private_source / "receipts.json").read_text())
                    if r["file"] in SOURCE_HASHES}
        for name, receipt in receipts.items():
            body = (args.private_source / name).read_bytes()
            require(receipt["bytes"] == len(body) and receipt["sha256"] == hashlib.sha256(body).hexdigest(),
                    "Original bytes differ from acquisition receipt")
        soup = BeautifulSoup((args.private_source / "lawrence-parent.html").read_bytes(), "html.parser")
        require(set(SOURCES.values()) <= {urljoin(INDEX, a["href"]) for a in soup.select("a[href]")},
                "County does not declare the reports")
        reports = []
        for kind, name in FILES.items():
            with fitz.open(args.private_source / name) as doc:
                first = parse_pages([page.get_text(sort=True) for page in doc], kind)
            with pdfplumber.open(args.private_source / name) as doc:
                second = parse_pages([p.extract_text() for p in doc.pages], kind)
            require(first == second, "Independent PDF engines disagree on native facts")
            reports.append(first)
        facts = dict(schema="lawrence-2026-complete-numerical-facts-v1", reports=reports,
            source_receipts=receipts,
            independent_extraction="PyMuPDF sorted text and pdfplumber coordinate-sensitive text agree on all page facts")
    else:
        facts = json.loads(gzip.decompress(args.facts.read_bytes()))
    print(json.dumps(build(facts, args.output), indent=2))


if __name__ == "__main__":
    main()
