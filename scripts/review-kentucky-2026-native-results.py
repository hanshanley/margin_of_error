#!/usr/bin/env python3
"""Review the complete Daviess County 2026 general-election cumulative PDF."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile


ORIGINAL = "daviess-2026-general-cumulative.pdf"
SOURCE_URL = "https://www.daviessky.org/wp-content/uploads/2026/11/Cumulative.pdf"
MODES = ["Absentee Mail-In", "Absentee Walk-in", "Early Voting", "Election Day Voting", "Total"]
EDGES = [262.35, 356.10, 448.25, 541.56, 640.77]
HEADER = "Choice Party " + " ".join(MODES)
HOUSE = "UNITED STATES REPRESENTATIVE in CONGRESS 2nd Congressional District - (Vote for One)"
INTEGER = re.compile(r"(?:0|[1-9][0-9]*|[1-9][0-9]{0,2}(?:,[0-9]{3})+)\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def count_cells(words):
    cells = [None] * 5
    for x0, _, x1, _, text, *_ in words:
        if x0 < 220 or text.endswith("%") or not re.fullmatch(r"[0-9,]+", text):
            continue
        require(INTEGER.fullmatch(text), "Malformed native integer")
        columns = [i for i, edge in enumerate(EDGES) if abs(x1 - edge) <= 0.7]
        require(len(columns) == 1, "Unreviewed native numeric position")
        column = columns[0]
        require(cells[column] is None, "Duplicate native numeric column")
        cells[column] = int(text.replace(",", ""))
    if any(value is not None for value in cells):
        require(all(value is not None for value in cells), "Missing native numeric column")
        require(sum(cells[:4]) == cells[4], "Native mode total differs")
    return cells


def finish_contest(contest):
    rows = contest["rows"]
    require(len(rows) >= 4, "Missing complete native contest rows")
    require([row["choice"] for row in rows[-3:]] == ["Cast Votes:", "Undervotes:", "Overvotes:"],
            "Missing or reordered native contest totals")
    options = rows[:-3]
    require(all(row["choice"] not in {"Cast Votes:", "Undervotes:", "Overvotes:"} for row in options),
            "Repeated native contest totals")
    require(len({row["choice"] for row in options}) == len(options), "Duplicate native option")
    for column in range(5):
        require(sum(row["counts"][column] for row in options) == rows[-3]["counts"][column],
                "Native candidate/option sum differs from Cast Votes")
    return contest


def review_pdf(raw):
    import fitz
    contests = []
    headers = []
    footer_seen = False
    with fitz.open(stream=raw, filetype="pdf") as document:
        require(len(document) == 13, "Complete native report must contain all 13 pages")
        for number, page in enumerate(document, 1):
            text = page.get_text()
            require("GENERAL ELECTION HELD ON\nOFFICIAL BALLOT FOR DAVIESS COUNTY\n11/3/2026\n" in text
                    and f"Page {number}\nUnofficial Results\n" in text
                    and "Run Time\nRun Date\n8:15 PM\n11/03/2026\n" in text,
                    "Wrong native election/county/page identity")
            ballots = re.findall(r"Ballots Cast\n([0-9]+)\n", text)
            reporting = re.findall(r"Polling Places Reporting\n([0-9]+ of [0-9]+ = [0-9.]+%)\n", text)
            require(len(ballots) == len(reporting) == 1, "Missing or duplicate native county header")
            headers.append((int(ballots[0]), reporting[0]))
            lines = []
            for word in sorted(page.get_text("words"), key=lambda w: ((w[1] + w[3]) / 2, w[0])):
                center = (word[1] + word[3]) / 2
                if center < 140:
                    continue
                if not lines or abs(center - lines[-1][0]) > 0.7:
                    lines.append((center, []))
                lines[-1][1].append(word)
            pending, active = [], None
            for _, words in lines:
                words.sort(key=lambda word: word[0])
                line = " ".join(word[4] for word in words)
                require(not footer_seen, "Unexpected native text after report footer")
                if line == "*** End of report ***":
                    require(number == 13 and active is None, "Unexpected native report footer")
                    footer_seen = True
                    continue
                if line == HEADER:
                    require(active is None and pending, "Missing or duplicate native contest heading")
                    active = dict(contest=" ".join(pending), source_pdf_page=number, rows=[])
                    pending = []
                    continue
                counts = count_cells(words)
                if counts[0] is None:
                    require(active is None, "Unexpected native text inside contest")
                    pending.append(line)
                    continue
                require(active is not None, "Native counts outside a declared contest")
                left = " ".join(word[4] for word in words if word[0] < 220)
                total = left in {"Cast Votes:", "Undervotes:", "Overvotes:"}
                choice = left if total else " ".join(word[4] for word in words if word[0] < 170)
                party = "" if total else " ".join(word[4] for word in words if 170 <= word[0] < 220)
                require(choice or (active["contest"] == "COUNTY SURVEYOR - (Vote for One)"
                                   and not party and counts == [0] * 5),
                        f"Unreviewed unnamed native option on page {number}: {line}")
                active["rows"].append(dict(choice=choice, party=party, counts=counts))
                if choice == "Overvotes:":
                    contests.append(finish_contest(active))
                    active = None
            require(active is None and not pending, "Incomplete native page or contest")
    require(len(set(headers)) == 1, "Conflicting repeated county ballot/reporting headers")
    require(footer_seen, "Missing native report footer")
    require(len(contests) == 36 and len({row["contest"] for row in contests}) == 36,
            "Incomplete or duplicate native contest inventory")
    require(headers[0][1] == "17 of 17 = 100.00%", "Unreviewed native reporting counter")
    house = [row for row in contests if row["contest"] == HOUSE]
    require(len(house) == 1, "Missing or duplicate native House contest")
    house = house[0]
    options = house["rows"][:-3]
    require([(row["choice"], row["party"]) for row in options] ==
            [("S. Brett GUTHRIE", "REP"), ("Megan WINGFIELD", "DEM"), ("Thomas A. LOECKEN", "IND")],
            "Unreviewed complete native House option inventory")
    require(sum(row["counts"][4] for row in house["rows"][-3:]) == headers[0][0],
            "Native House votes/under/over do not conserve county ballots")
    return contests, headers[0], house


def build(source, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing to overwrite an existing package")
    receipts = json.loads((source / "sources.json").read_text())
    factual = [row for row in receipts if row["file"] == ORIGINAL]
    require(len(factual) == 1 and factual[0]["url"] == SOURCE_URL and factual[0]["status"] == 200,
            "Missing or conflicting native original receipt")
    raw = (source / ORIGINAL).read_bytes()
    require(len(raw) == factual[0]["bytes"]
            and hashlib.sha256(raw).hexdigest() == factual[0]["sha256"], "Original byte/hash mismatch")
    contests, (ballots, reporting), house = review_pdf(raw)
    identity = dict(year=2026, state_code="KY", county="Daviess County", native_county_id="",
                    source_row_id="daviess:county:pdf:1", maps_approved=False)
    participation = dict(**identity, ballots_cast_total=ballots, registered_voters_total="",
        turnout_rate="", native_reporting_counter=reporting,
        quality_flags="provisional;county_only;native_polling_places_not_geographic_precincts")
    options = house["rows"][:-3]
    results = dict(**identity, source_pdf_page=house["source_pdf_page"], contest=HOUSE,
        total_votes=house["rows"][-3]["counts"][4],
        democratic_votes=next(row["counts"][4] for row in options if row["party"] == "DEM"),
        republican_votes=next(row["counts"][4] for row in options if row["party"] == "REP"),
        other_votes=sum(row["counts"][4] for row in options if row["party"] not in {"DEM", "REP"}),
        candidates_by_native_mode=json.dumps(options, separators=(",", ":")),
        under_votes=house["rows"][-2]["counts"][4], over_votes=house["rows"][-1]["counts"][4])
    all_rows = []
    for contest_number, contest in enumerate(contests, 1):
        for row_number, row in enumerate(contest["rows"], 1):
            all_rows.append(dict(year=2026, state_code="KY", county="Daviess County",
                source_pdf_page=contest["source_pdf_page"], contest=contest["contest"],
                source_row_id=f"daviess:pdf:{contest['source_pdf_page']}:contest:{contest_number}:row:{row_number}",
                choice=row["choice"], party=row["party"],
                kind="total" if row["choice"] in {"Cast Votes:", "Undervotes:", "Overvotes:"}
                    else "option" if row["choice"] else "unnamed_option",
                **dict(zip(MODES, row["counts"]))))
    audit = dict(year=2026, state_code="KY", scope="Daviess County only",
        native_report_pages=13, native_contests=len(contests), complete_native_rows=len(all_rows),
        unnamed_option_rows=sum(row["kind"] == "unnamed_option" for row in all_rows),
        participation_rows=1, house_rows=1, ballots=ballots, house_votes=results["total_votes"],
        under_votes=results["under_votes"], over_votes=results["over_votes"],
        native_reporting_counter=reporting, geographic_precinct_inventory_inferred=False,
        native_modes=MODES, all_options_modes_and_printed_totals_reconciled=True,
        registered_voters=None, rates_available=False, maps_approved=False,
        source_row_identity="Extraction identity, not a native geographic or precinct identifier.",
        native_status="Unofficial Results", native_run_date="11/03/2026", native_run_time="8:15 PM",
        factual_originals=1, discovery_originals_retained_separately=len(receipts) - 1,
        license_note="Official public aggregate county election report; no separate open-data license "
            "was found in the acquired declarations. No vendor/frontend assets redistributed.",
        next_action="Continue other Kentucky counties. Statewide portal returns an explicit bot-policy "
            "403; do not bypass it. Acquire actual geographic precinct returns, registration "
            "definitions and exact-election boundaries; do not infer rates or allocate county votes.")
    output.mkdir(parents=True)
    (output / "source").mkdir()
    shutil.copyfile(source / ORIGINAL, output / "source" / ORIGINAL)
    shutil.copyfile(source / "sources.json", output / "source/sources.json")
    shutil.copyfile(__file__, output / "review.py")
    for name, rows in [("county-participation.csv", [participation]),
                       ("county-house-results.csv", [results]), ("all-contest-results.csv", all_rows)]:
        with (output / name).open("w", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    checksums = {}
    for path in sorted(output.rglob("*")):
        if path.is_file():
            contents = path.read_bytes()
            checksums[path.relative_to(output).as_posix()] = dict(
                bytes=len(contents), sha256=hashlib.sha256(contents).hexdigest())
    (output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as target:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                entry = zipfile.ZipInfo(path.relative_to(output).as_posix(), (2026, 11, 5, 0, 0, 0))
                entry.external_attr = 0o100644 << 16
                target.writestr(entry, path.read_bytes())
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.archive), indent=2))
