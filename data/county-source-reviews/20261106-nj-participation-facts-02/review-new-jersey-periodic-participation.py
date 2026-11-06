"""Reproduce the complete 21-county current participation query, not candidate votes."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


PARENT = "https://www.nj.gov/state/elections/election-information-2026.shtml"
INDEX = "https://www.nj.gov/state/elections/election-results-information.shtml"
COUNTIES = ("Atlantic", "Bergen", "Burlington", "Camden", "Cape May", "Cumberland",
            "Essex", "Gloucester", "Hudson", "Hunterdon", "Mercer", "Middlesex",
            "Monmouth", "Morris", "Ocean", "Passaic", "Salem", "Somerset", "Sussex",
            "Union", "Warren")
FIELDS = ("early_machines_deployed", "early_machines_not_included", "early_votes_cast",
          "election_day_machines_deployed", "election_day_machines_not_included",
          "election_day_votes_cast", "mail_ballots_issued", "mail_received_into_svrs",
          "mail_ballots_tallied", "mail_ballots_to_be_processed", "provisional_ballots_issued")
FACTS_SHA256 = "1ea704a9d560b967a70a2921fbdbbe86a3a8848768610017409c02283725ae67"
QUALIFICATIONS = [
    "Complete 21-county query of current county and native aggregate participation rows, not a transcription of every municipal row or attached candidate table.",
    "Votes Cast in the Early Voting and Election Day columns and Vote-by-Mail Ballots Tallied are participation counts, not candidate selections.",
    "Except for the separately verified Cape May summary, usable totals are derived EV + ED + VBM-tallied subtotals, excluding provisional ballots; not native all-mode ballot totals or unique-voter estimates.",
    "Issued, received and to-be-processed counts are separate processing measures and never added to participation. Provisional ballots issued are not provisional ballots counted.",
    "Native blanks, explicit zeroes, competing subtotals, source labels and undeclared timezones remain separate. Registrations and printed turnout remain missing except where explicitly supplied.",
    "Essex's conflicting ED aggregates and Hudson's missing early-voting observations are withheld from combined county counts, not filled with zeroes or chosen silently.",
    "Hunterdon's three participation-mode counts agree across both native totals. Union's selected congressional total includes the 405 overseas ballots explicitly excluded from its municipality mail tally; both native totals remain available.",
    "Morris pages 3-6 are older appended snapshots, including primary-labeled pages; only current general-election pages 1-2 supply current participation.",
    "Original source PDF/HTML presentation and unreviewed candidate attachments remain private. All selected county query records, native aggregate alternatives, counting notes and provenance are reproduced in full.",
    "Unofficial snapshots, not certification, completed statewide counting, demographic participation or map approval.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def number(value):
    require(isinstance(value, str) and (value == "" or re.fullmatch(
        r"-?(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)", value)), "Invalid native count literal")
    return int(value.replace(",", "")) if value else None


def mode_counts(row):
    return tuple(number(row["count_literals"][index]) for index in (2, 5, 8))


def select(report):
    rows = report["aggregates"]
    county_rows = [row for row in rows if row["label_literal"] == report["county"] + " County"]
    require(county_rows and all(row["count_literals"] == county_rows[0]["count_literals"]
                              for row in county_rows), "Conflicting repeated county rows")
    county = county_rows[0]
    if report["county"] in ("Essex", "Hudson"):
        return None
    if report["county"] in ("Hunterdon", "Union"):
        congressional, = [row for row in rows if row["label_literal"] == "Congressional TOTALS"]
        municipality, = [row for row in rows if row["label_literal"] == "Municipality TOTALS"]
        a, b = mode_counts(congressional), mode_counts(municipality)
        if report["county"] == "Hunterdon":
            require(a == b, "Hunterdon participation aggregates disagree")
        else:
            require(a[:2] == b[:2] and a[2] - b[2] == 405
                    and any("405 overseas ballots tallied" in note["literal"]
                            for note in report["notes"]), "Unexplained Union overseas scope")
        county = congressional
    require(all(value is not None and value >= 0 for value in mode_counts(county)),
            "Missing or negative counted participation")
    return county


def validate(facts):
    require(facts["schema"] == "nj-2026-current-county-participation-query-v1", "Changed query schema")
    reports = facts["reports"]
    require(tuple(row["county"] for row in reports) == COUNTIES, "Incomplete county query")
    for report in reports:
        require(report["native_status_literal"] == "UNOFFICIAL"
                and report["declared_timezone"] is None, "Changed native status/timezone")
        receipt = facts["source_receipts"][report["source_file"]]
        require(receipt["url"] == receipt["final_url"] == report["source_url"]
                and receipt["status"] == 200 and receipt["bytes"] > 0
                and re.fullmatch(r"[a-f0-9]{64}", receipt["sha256"]), "Invalid source receipt")
        for row in report["aggregates"]:
            require(len(row["count_literals"]) == len(FIELDS)
                    and row["source_page"] in report["selected_periodic_pages"],
                    "Incomplete or out-of-scope aggregate vector")
            for value in row["count_literals"]:
                number(value)
        select(report)
    require(sum(len(row["aggregates"]) for row in reports) == 65, "Incomplete native aggregate query")
    cape = next(row for row in reports if row["county"] == "Cape May")
    summary = cape["attached_participation_summary"]
    require(summary["source_page"] == 2 and summary["registered_voters_literal"] == "76,899"
            and summary["ballot_count_literals"] == ["41,278", "9,678", "24,033", "7,567", "0", "0", "0"]
            and summary["native_printed_turnout"] == "53.68%"
            and number(summary["ballot_count_literals"][0]) == sum(mode_counts(select(cape))),
            "Changed attached native participation summary")
    require(len(facts["source_receipts"]) == 23, "Incomplete source provenance")
    require(FACTS_SHA256 and digest(facts) == FACTS_SHA256, "Frozen complete county query changed")
    return facts


def acquire(directory):
    import fitz
    import pdfplumber
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin

    receipts = {}

    def body(name, url=None):
        data = (directory / name).read_bytes()
        receipt = json.loads((directory / (name + ".receipt.json")).read_text())
        require(receipt["status"] == 200 and receipt["bytes"] == len(data)
                and receipt["sha256"] == hashlib.sha256(data).hexdigest()
                and receipt["url"] == receipt["final_url"]
                and (url is None or receipt["url"] == url), "Original source receipt mismatch")
        receipts[name] = receipt
        return data

    parent = BeautifulSoup(body("official-2026-index.html", PARENT), "html.parser")
    require(INDEX in {urljoin(PARENT, a["href"]) for a in parent.select("a[href]")},
            "State parent does not declare periodic index")
    catalog = BeautifulSoup(body("official-periodic-index.html", INDEX), "html.parser")
    heading = next(node for node in catalog.select("h1,h2,h3,h4")
                   if node.get_text(" ", strip=True) == "2026 General Election")
    declared = []
    for node in heading.find_all_next():
        if node.name in ("h1", "h2", "h3", "h4") and node.get_text(" ", strip=True) == "2026 Primary Election":
            break
        if node.name == "a" and node.has_attr("href") and "11/05" in node.get_text(" ", strip=True):
            declared.append((node.get_text(" ", strip=True).split(" Report - ")[0], urljoin(INDEX, node["href"])))
    require(tuple(county for county, url in declared) == COUNTIES
            and len({url for county, url in declared}) == 21, "Changed declared general-election inventory")
    reports = []
    for county, url in declared:
        name = county.lower().replace(" ", "-") + "-periodic-report.pdf"
        body(name, url)
        aggregates, notes, pages = [], [], []
        with fitz.open(directory / name) as mupdf, pdfplumber.open(directory / name) as plumber:
            selected = list(range(1, (2 if county == "Morris" else 1 if county == "Cape May" else len(plumber.pages)) + 1))
            report = dict(county=county, source_file=name, source_url=url, total_pdf_pages=len(plumber.pages),
                          selected_periodic_pages=selected, native_status_literal="UNOFFICIAL",
                          declared_timezone=None, aggregates=aggregates, notes=notes, page_updates=pages)
            if county == "Bergen":
                vector = ["23", "0", "60,373", "560", "0", "200,273", "83,613", "58,010", "58,857", "0", "3,502"]
                for page in (1, 2):
                    for label in ("Bergen County", "Legislative TOTALS"):
                        aggregates.append(dict(source_page=page, label_literal=label, count_literals=vector[:]))
                municipal = vector[:]
                municipal[0] = "20"
                aggregates.append(dict(source_page=2, label_literal="Municipality TOTALS", count_literals=municipal))
                pages.extend(dict(source_page=page, table_update_literal="11/5/26 3:55 PM",
                                  other_update_literals=["11/5/2026 3:56:32 PM"]) for page in (1, 2))
                notes.append(dict(source_page=2, literal="COMMENTS FROM BOARD OF ELECTIONS: (Column K - negatives are due to Board of Elections pending voter profile updates.) Rescanning envelopes for missed barcodes when bulk scanning---no remaining Vote by Mail ballots to be counted as of 11/5"))
                report["extraction"] = "Both scanned pages directly visually reviewed; local Apple Vision OCR corroborates county figures. No external OCR service."
            else:
                for number_ in selected:
                    page = plumber.pages[number_ - 1]
                    text = " ".join((page.extract_text() or "").split())
                    independent = " ".join(mupdf[number_ - 1].get_text().replace("*", " ").split())
                    require("PRIMARY" not in text.upper() and "UNOFFICIAL" in text.upper(),
                            "Wrong election/status on selected current page")
                    for table in page.find_tables():
                        rows = table.extract()
                        if len(rows) < 3 or len(rows[0]) != 12:
                            continue
                        pages.append(dict(source_page=number_, table_update_literal=rows[0][0],
                                          other_update_literals=list(dict.fromkeys(re.findall(
                                              r"\b11/\d{1,2}/(?:2026|26)(?:\s+\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M)?", text)))))
                        for row in rows:
                            if row[0] not in (county + " County", "Congressional TOTALS",
                                              "Legislative TOTALS", "Municipality TOTALS"):
                                continue
                            if county == "Cape May" and row[0] == "Congressional TOTALS":
                                require(row[4] == "133 0 24033 10498 7963 7567 396 347"
                                        and all(value in (None, "") for value in row[5:]),
                                        "Changed Cape May merged aggregate cell")
                                row = row[:4] + row[4].split()
                            require(len(row) == 12 and all(value is not None for value in row),
                                    "Unresolved merged native aggregate cells")
                            literals = [" ".join((value or "").split()) for value in row]
                            require(" ".join(value for value in literals if value) in independent,
                                    "Independent complete aggregate vector disagreement")
                            aggregates.append(dict(source_page=number_, label_literal=literals[0],
                                                   count_literals=literals[1:]))
                    if "COMMENTS:" in text and text.partition("COMMENTS:")[2].strip():
                        notes.append(dict(source_page=number_, literal=text.partition("COMMENTS:")[2].strip()))
                report["extraction"] = "pdfplumber native aggregate cells agree with independent MuPDF complete ordered row vectors; no crop-dependent clipping."
            if county == "Morris":
                report["excluded_appended_pages"] = [
                    dict(source_page=i, header_literal=" ".join(plumber.pages[i - 1].extract_text().split())[:100])
                    for i in range(3, 7)]
            if county == "Cape May":
                text = " ".join(plumber.pages[1].extract_text().split())
                independent = " ".join(mupdf[1].get_text().split())
                count = re.search(r"Ballots Cast - Total ((?:[\d,]+ ){6}[\d,]+)", text)
                registration = re.search(r"Registered Voters - Total ([\d,]+)", text)
                rate = re.search(r"Voter Turnout - Total ([\d.]+%)", text)
                require(count and registration and rate, "Missing attached participation summary")
                vector = count[1].split()
                require("Registered Voters - Total " + registration[1] + " " + vector[0]
                        + " Ballots Cast - Total " + " ".join(vector[1:]) in independent
                        and "Voter Turnout - Total " + rate[1] in independent,
                        "Independent attached summary disagreement")
                report["attached_participation_summary"] = dict(source_page=2,
                    registered_voters_literal=registration[1], ballot_count_literals=vector,
                    native_printed_turnout=rate[1], native_status_literal="UNOFFICIAL RESULTS",
                    counted_mode_literals=["Total", "Early Voting", "Election Day", "Mail-in", "Provisional", "Emergency", "State/Fed"])
            reports.append(report)
    return dict(schema="nj-2026-current-county-participation-query-v1", reports=reports,
                source_receipts=receipts)


def build(facts, output):
    validate(facts)
    output.mkdir(parents=True, exist_ok=False)
    tables = {name: [] for name in ("county-participation.csv", "native-aggregate-participation.csv",
                                   "native-source-pages.csv", "native-counting-qualifications.csv")}
    for report in facts["reports"]:
        common = dict(year=2026, state_code="NJ", county=report["county"], source_url=report["source_url"],
                      native_status_literal=report["native_status_literal"], declared_timezone="")
        selected = select(report)
        county, = [row for row in report["aggregates"] if row["label_literal"] == report["county"] + " County"][:1]
        modes = mode_counts(selected) if selected else (None, None, None)
        summary = report.get("attached_participation_summary")
        reason = {"Essex": "Conflicting ED congressional/municipality totals: 133271 versus 137294; county header blank.",
                  "Hudson": "Early Voting observation missing; county header blank and zero native subtotal is not a measured zero."}.get(report["county"], "")
        tables["county-participation.csv"].append(dict(**common,
            source_page=summary["source_page"] if summary else selected["source_page"] if selected else county["source_page"],
            periodic_source_page=selected["source_page"] if selected else county["source_page"],
            registration_source_page=summary["source_page"] if summary else "",
            reported_participation_subtotal=sum(modes) if selected else "",
            native_participation_measure_literal="Ballots Cast - Total" if summary else "",
            participation_measure_label="Ballots Cast - Total" if summary else
                "Derived Early Voting Votes Cast + Election Day Votes Cast + Vote-by-Mail Ballots Tallied; provisional excluded",
            selected_native_aggregate_literal=selected["label_literal"] if selected else "",
            early_voting_votes_cast=modes[0], election_day_votes_cast=modes[1], mail_ballots_tallied=modes[2],
            provisional_ballots_counted=0 if summary else "",
            registered_voters=number(summary["registered_voters_literal"]) if summary else "",
            native_printed_turnout=summary["native_printed_turnout"] if summary else "",
            native_county_count_literals_json=json.dumps(county["count_literals"]),
            withheld_reason=reason, counting_qualifications_json=json.dumps(QUALIFICATIONS)))
        for row in report["aggregates"]:
            native = dict(**common, source_page=row["source_page"], native_aggregate_literal=row["label_literal"])
            native.update(zip(FIELDS, row["count_literals"]))
            tables["native-aggregate-participation.csv"].append(native)
        for row in report["page_updates"]:
            tables["native-source-pages.csv"].append(dict(**common, source_page=row["source_page"],
                source_role="periodic_report",
                source_update_literal=row["table_update_literal"],
                other_update_literals_json=json.dumps(row["other_update_literals"])))
        if summary:
            tables["native-source-pages.csv"].append(dict(
                **{**common, "native_status_literal": summary["native_status_literal"]},
                source_page=summary["source_page"], source_role="attached_participation_summary",
                source_update_literal="", other_update_literals_json="[]"))
        for row in report["notes"]:
            tables["native-counting-qualifications.csv"].append(dict(**common,
                source_page=row["source_page"], literal=row["literal"]))
    for name, rows in tables.items():
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / name).write_text(stream.getvalue())
    (output / "source-records.json.gz").write_bytes(gzip.compress(
        (json.dumps(facts, sort_keys=True, indent=2) + "\n").encode(), mtime=0))
    audit = dict(scope="Complete 21-county current participation query; 19 usable reported subtotals, two withheld",
                 maps_approved=False, demographic_turnout_approved=False, statewide_completion_approved=False,
                 qualifications=QUALIFICATIONS, table_rows={name: len(rows) for name, rows in tables.items()},
                 usable_counties=[row["county"] for row in tables["county-participation.csv"] if not row["withheld_reason"]],
                 withheld_counties=[row for row in tables["county-participation.csv"] if row["withheld_reason"]])
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "source-receipts.json").write_text(json.dumps(facts["source_receipts"], sort_keys=True, indent=2) + "\n")
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output / "checksums.json").write_text(json.dumps({path.name: dict(bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(output.iterdir())}, indent=2) + "\n")
    target = output / "complete-new-jersey-2026-participation-query-02.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path != target:
                info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
                info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
                archive.writestr(info, path.read_bytes())
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--private-source", type=Path)
    source.add_argument("--facts", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    facts = acquire(args.private_source) if args.private_source else json.loads(gzip.decompress(args.facts.read_bytes()))
    print(json.dumps(build(facts, args.output), indent=2))
