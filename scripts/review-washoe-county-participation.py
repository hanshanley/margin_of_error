"""Reproduce Washoe participation from the complete frozen unofficial county report."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

PDF_SHA256 = "ac8d43ad5b41e41ccb1ac6ddac54cb37630f00b979c44ba2067e4330ad35c63b"
TEXT_SHA256 = "943aa22cf5a32c721b854ee4ee0666708403b1133c6c6908eb4f8eaabe51453e"
SOURCE = ("https://gis.washoecounty.us/webservices/gisdataservice/ElectionResults/"
          "resultpdf/CD00E1B800204305BF4815929830162B/68e81f21-c190-4ea6-9080-11b5f06c41c0")
MODES = ("Early Vote", "Election Day", "Mail", "Prov-Election Day", "Prov-Early Vote", "ICX")
TIMESTAMP = "11/4/2026 6:13:35 PM"
STATUS = "REPORT 6 - UNOFFICIAL RESULTS"


def integer(value):
    if not re.fullmatch(r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)", value):
        raise ValueError("Invalid native Washoe count")
    return int(value.replace(",", ""))


def block(text, label):
    matches = re.findall(r"(?:^|\n)" + re.escape(label) + r"\n((?:[\d,]+\n){6})([\d,]+)", text)
    if len(matches) != 1:
        raise ValueError("Missing or duplicated Washoe accounting block: " + label)
    modes, total = matches[0]
    return [integer(value) for value in modes.splitlines()] + [integer(total)]


def parse_pages(pages):
    if len(pages) != 23 or any(
            not text.startswith(TIMESTAMP + f"\nPage: {index} of 23\n")
            for index, text in enumerate(pages, 1)):
        raise ValueError("Incomplete or changed Washoe report pages or timestamps")
    first = pages[0]
    for literal in ("WASHOE COUNTY", "November 03, 2026", "General Election", STATUS,
                    "Summary for: All Contests, All Districts, All Tabulators, All Counting Groups",
                    "REPRESENTATIVE IN CONGRESS DISTRICT 2 (Vote for  1)"):
        if first.count(literal) != 1:
            raise ValueError("Wrong Washoe election, scope, status or contest")
    header = re.findall(r"Voters Cast: ([\d,]+) of ([\d,]+) \(([\d.]+%)\)", first)
    if len(header) != 1:
        raise ValueError("Missing or duplicated Washoe county header")
    ballots, registered = map(integer, header[0][:2])
    percent = header[0][2]
    summary = first.split("Elector Group\nCounting Group\nVoters Cast\nRegistered Voters\nTurnout\nTotal\n")
    if len(summary) != 2:
        raise ValueError("Missing or duplicated Washoe independent mode summary")
    summary = summary[1]
    totals = re.findall(r"(?:^|\n)Total\n([\d,]+)\n([\d,]+)\n([\d.]+%)\s*$", summary)
    if totals != [(header[0][0], header[0][1], percent)]:
        raise ValueError("Washoe county header and summary disagree")
    mode_rows = []
    for name in MODES:
        values = re.findall(r"(?:^|\n)" + re.escape(name) + r"\n([\d,]+)\n([\d.]+%)", summary)
        if len(values) != 1:
            raise ValueError("Missing or duplicated Washoe counting group")
        count, native_percent = integer(values[0][0]), values[0][1]
        if registered <= 0 or f"{100 * count / registered:.2f}%" != native_percent:
            raise ValueError("Washoe mode fraction disagrees with county registration")
        mode_rows.append(dict(year=2026, state_code="NV", county="Washoe",
            native_counting_group=name, ballots=count, native_registered_voters=registered,
            denominator_scope="entire_county_not_mode_registration", native_reported_percent=native_percent))
    if (sum(row["ballots"] for row in mode_rows) != ballots or ballots > registered
            or f"{100 * ballots / registered:.2f}%" != percent):
        raise ValueError("Washoe modes and county participation disagree")
    for text in (first, pages[-1]):
        casts = re.findall(r"Times Cast\n((?:[\d,]+\n){6})([\d,]+) / ([\d,]+)\n([\d.]+%)", text)
        if len(casts) != 1:
            raise ValueError("Missing or duplicated Washoe independent Times Cast")
        modes, numerator, denominator, printed = casts[0]
        if ([integer(value) for value in modes.splitlines()] != [row["ballots"] for row in mode_rows]
                or integer(numerator) != ballots or integer(denominator) != registered or printed != percent):
            raise ValueError("Washoe independent Times Cast disagrees")
    votes, under, over = (block(first, label) for label in ("Total Votes", "Undervotes", "Overvotes"))
    candidates = []
    pattern = (r"(Benitez-Thompson, Teresa\s+F\.|Chapman, Lynn|Flippo, David)\s+"
               r"(DEM|IAP|REP)\n((?:[\d,]+\n){7})([\d.]+%)")
    for name, party, counts, printed in re.findall(pattern, first):
        values = [integer(value) for value in counts.splitlines()]
        if sum(values[:6]) != values[6] or f"{100 * values[6] / votes[6]:.2f}%" != printed:
            raise ValueError("Washoe House candidate accounting disagrees")
        candidates.append(dict(year=2026, state_code="NV", county="Washoe",
            contest="REPRESENTATIVE IN CONGRESS DISTRICT 2", native_candidate_name_json=json.dumps(name),
            candidate_name=" ".join(name.split()), party_literal=party,
            **dict(zip(MODES, values[:6])), candidate_votes=values[6], native_reported_percent=printed))
    if len(candidates) != 3 or len({row["party_literal"] for row in candidates}) != 3:
        raise ValueError("Incomplete or duplicated Washoe House candidates")
    for index in range(7):
        candidate_sum = sum(row[MODES[index]] if index < 6 else row["candidate_votes"] for row in candidates)
        cast = mode_rows[index]["ballots"] if index < 6 else ballots
        if candidate_sum != votes[index] or votes[index] + under[index] + over[index] != cast:
            raise ValueError("Washoe candidate/under/over accounting disagrees")
    if (ballots, registered, votes[6], under[6], over[6]) != (191830, 329777, 189752, 1954, 124):
        raise ValueError("Frozen Washoe participation totals changed")
    county = dict(year=2026, state_code="NV", county="Washoe", ballots_cast=ballots,
        registered_voters=registered, native_reported_percent=percent,
        source_status_literal=STATUS, source_generated_at=TIMESTAMP,
        source_election_date="November 03, 2026", source_scope="All Contests, All Districts, All Tabulators, All Counting Groups",
        source_pdf_pages=23, source_counting_groups=6,
        qualification="Unofficial county observations; native registration cutoff is not established. "
        "Modes are not precincts. County registration repeats by mode and must not be summed. "
        "No final, demographic, population-based turnout or new map is approved.")
    audit = dict(year=2026, state_code="NV", county="Washoe", county_observations=1,
        ballots=ballots, registrations=registered, native_counting_groups=6,
        house_candidate_votes=votes[6], house_undervotes=under[6], house_overvotes=over[6],
        house_party_votes={row["party_literal"]: row["candidate_votes"] for row in candidates},
        original_pdf_pages=23, source_status_literal=STATUS, source_generated_at=TIMESTAMP,
        maps_approved=False, statewide_completion_approved=False, demographic_rates_approved=False)
    return [county], mode_rows, candidates, audit


def acquire_facts(pdf, receipt):
    import fitz
    from pypdf import PdfReader

    raw = pdf.read_bytes()
    provenance = json.loads(receipt.read_text())
    if (len(raw) != 553410 or hashlib.sha256(raw).hexdigest() != PDF_SHA256
            or provenance["url"] != SOURCE or provenance["status"] != 200
            or provenance["bytes"] != len(raw) or provenance["sha256"] != PDF_SHA256):
        raise ValueError("Washoe original PDF or HTTP receipt mismatch")
    with fitz.open(stream=raw, filetype="pdf") as document:
        pages = [page.get_text() for page in document]
    independent = PdfReader(io.BytesIO(raw))
    if len(independent.pages) != 23 or not re.search(
            r"Voters Cast:\s*191,830\s+of\s+329,777\s*\(58\.17%\)", independent.pages[0].extract_text()):
        raise ValueError("Independent Washoe PDF reader disagrees")
    return dict(input_pdf_sha256=PDF_SHA256, source_receipt=provenance, page_texts=pages)


def build(facts, output):
    receipt = facts["source_receipt"]
    text_digest = hashlib.sha256(json.dumps(facts["page_texts"], ensure_ascii=True,
        separators=(",", ":")).encode()).hexdigest()
    if (facts["input_pdf_sha256"] != PDF_SHA256 or text_digest != TEXT_SHA256
            or receipt["sha256"] != PDF_SHA256 or receipt["bytes"] != 553410
            or receipt["url"] != SOURCE or receipt["status"] != 200):
        raise ValueError("Frozen Washoe original, complete numerical text or receipt changed")
    rows, modes, candidates, audit = parse_pages(facts["page_texts"])
    if output.exists():
        raise ValueError("Refusing to overwrite Washoe participation output")
    output.mkdir(parents=True)
    for name, records in (("county-participation.csv", rows), ("counting-group-participation.csv", modes),
                          ("house-candidate-votes.csv", candidates)):
        with (output / name).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(records)
    (output / "source-receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "source-records.json.gz").write_bytes(gzip.compress(
        (json.dumps(facts, sort_keys=True, separators=(",", ":")) + "\n").encode(), mtime=0))
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    checksums = {path.name: dict(bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(output.iterdir())}
    (output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    with zipfile.ZipFile(output / "complete-washoe-county-participation-01.zip", "x",
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path.suffix == ".zip":
                continue
            info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-pdf", type=Path)
    source.add_argument("--facts", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.source_pdf and args.receipt is None:
        parser.error("--source-pdf requires --receipt")
    facts = acquire_facts(args.source_pdf, args.receipt) if args.source_pdf else json.loads(
        gzip.decompress(args.facts.read_bytes()))
    print(json.dumps(build(facts, args.output), indent=2))


if __name__ == "__main__":
    main()
