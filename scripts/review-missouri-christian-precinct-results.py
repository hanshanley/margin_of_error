#!/usr/bin/env python3
"""Reconcile Christian County's native 2026 groups without allocating absentee votes."""

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

import fitz


SOURCE = "https://www.christiancountymo.gov/offices/county-clerk/election-information/"
UPLOADS = "https://www.christiancountymo.gov/wp-content/uploads/"
ORIGINALS = {
    "official-election-index.html": SOURCE,
    "official-election-summary.pdf": UPLOADS + "RUN6Election_Summary.pdf",
    "official-precinct-summary.pdf": UPLOADS + "UNOFFICALP00100_to_P10000A_Election_Summary.pdf",
    "official-statement-of-votes-cast.pdf": UPLOADS + "UNOFFICIALSOVC_Nov_3_2026_21_14_26.pdf",
}
CONTEST = "US REPRESENTATIVE DISTRICT 7"
CANDIDATES = {"ERIC W. BURLISON": "REP", "MISSI HESKETH": "DEM", "KEVIN CRAIG": "LIB"}
STATEMENT_HEADER = ["Reg.", "Voters", "Total", "Votes", "ERIC W.", "BURLISON", "(REP)",
                    "MISSI", "HESKETH", "(DEM)", "KEVIN CRAIG", "(LIB)"]
RELEASE = ("https://github.com/hanshanley/margin_of_error/releases/download/"
           "voter-precinct-missouri-christian-20261105/complete-missouri-christian-2026.zip")


def count(value):
    if not isinstance(value, str) or not re.fullmatch(
            r"0|[1-9][0-9]*|[1-9][0-9]{0,2}(?:,[0-9]{3})+", value):
        raise ValueError("Invalid or missing Missouri native count")
    return int(value.replace(",", ""))


def percentage(value, votes, total):
    if value == "-" and total == 0:
        return
    if (not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?%", value) or not total
            or abs(float(value[:-1]) - 100 * votes / total) > 0.011):
        raise ValueError("Missouri displayed percentage disagrees with native counts")


def pdf_pages(raw, title):
    if not raw.startswith(b"%PDF-"):
        raise ValueError("Missouri original is not a PDF")
    with fitz.open(stream=raw, filetype="pdf") as doc:
        pages = [[line.strip() for line in page.get_text().splitlines()] for page in doc]
    for lines in pages:
        if (lines[:5] != [title, "GENERAL ELECTION", "CHRISTIAN COUNTY, MISSOURI",
                          "TUESDAY, NOVEMBER 3, 2026", "ELECTION RESULTS"]
                or "UNOFFICIAL" not in lines or "Date: 11/3/2026" not in lines):
            raise ValueError("Wrong Missouri county, election or native report identity")
    if not pages:
        raise ValueError("Empty Missouri PDF")
    return pages


def statistics(lines):
    matches = [re.fullmatch(r"Registered Voters (.+) - Total Ballots (.+) : (.+)", line)
               for line in lines if line.startswith("Registered Voters")]
    if len(matches) != 1 or matches[0] is None:
        raise ValueError("Missing or repeated Missouri participation field")
    registered, ballots, displayed = matches[0].groups()
    registered, ballots = count(registered), count(ballots)
    if registered:
        if ballots > registered:
            raise ValueError("Missouri ballots exceed native registered count")
        percentage(displayed, ballots, registered)
    elif displayed != "N/A":
        raise ValueError("Missouri zero registration must retain native N/A")
    return dict(registered=registered, ballots=ballots, source_reported_percent=displayed)


def house_vector(lines, summary=False):
    if lines.count(CONTEST) != 1:
        raise ValueError("Missing or duplicate Missouri House contest")
    offset = lines.index(CONTEST) + 1
    if summary:
        if lines[offset:offset + 4] != ["Number of Precincts", "27", "Precincts Reporting", "27"]:
            raise ValueError("Wrong Missouri county House reporting scope")
        offset += 4
    if lines[offset:offset + 1] != ["Vote For 1"]:
        raise ValueError("Wrong Missouri House vote-for scope")
    offset += 1
    candidates = {}
    for _ in CANDIDATES:
        name, raw_votes, _displayed = lines[offset:offset + 3]
        match = re.fullmatch(r"(.+?)\s+\((REP|DEM|LIB)\)", name)
        if (not match or match[1] in candidates or CANDIDATES.get(match[1]) != match[2]):
            raise ValueError("Wrong or duplicate Missouri House candidate identity")
        candidates[match[1]] = count(raw_votes)
        offset += 3
    if lines[offset + 1:offset + 2] != ["Total Votes"]:
        raise ValueError("Missing Missouri House total")
    total = count(lines[offset])
    if set(candidates) != set(CANDIDATES) or sum(candidates.values()) != total:
        raise ValueError("Missouri House candidate sum differs from native total")
    start = offset - 9
    for i, votes in enumerate(candidates.values()):
        percentage(lines[start + i * 3 + 2], votes, total)
    return candidates


def precinct_units(pages, expected_units=27):
    if len(pages) != expected_units * 2:
        raise ValueError("Incomplete Missouri precinct PDF")
    units = {}
    for offset in range(0, len(pages), 2):
        first, second = pages[offset:offset + 2]
        unit = first[5]
        if (unit in units or unit != second[5] or first.count("Page 1/2") != 1
                or second.count("Page 2/2") != 1
                or (unit != "ABSENTEE" and not re.fullmatch(r"[1-9][0-9]*\. .+", unit))):
            raise ValueError("Duplicate or conflicting Missouri native unit or page identity")
        counts = statistics(first)
        if counts != statistics(second) or second.count(CONTEST):
            raise ValueError("Conflicting Missouri repeated participation or House fields")
        units[unit] = dict(counts, candidate_votes=house_vector(first),
                           source_pages=[offset + 1, offset + 2])
    return units


def county_summary(pages):
    if len(pages) != 3:
        raise ValueError("Incomplete Missouri county summary")
    for i, lines in enumerate(pages, 1):
        if (lines.count(f"Page {i}/3") != 1
                or lines.count("27 of 27 Precincts Reporting    100.00%") != 1):
            raise ValueError("Wrong Missouri county page or reporting scope")
    counts = statistics(pages[0])
    if any(statistics(lines) != counts for lines in pages[1:]):
        raise ValueError("Conflicting Missouri county participation counts")
    if sum(lines.count(CONTEST) for lines in pages) != 1:
        raise ValueError("Missing or repeated Missouri county House contest")
    return dict(counts, candidate_votes=house_vector(pages[0], summary=True))


def statement_units(pages):
    for i, lines in enumerate(pages, 1):
        if lines.count(f"Page {i}/{len(pages)}") != 1:
            raise ValueError("Incomplete Missouri statement page sequence")
    selected = [lines for lines in pages if CONTEST in lines]
    if len(selected) != 3:
        raise ValueError("Incomplete Missouri House statement")
    body = []
    for i, lines in enumerate(selected):
        offset = lines.index(CONTEST) + 1
        if lines[offset:offset + len(STATEMENT_HEADER)] != STATEMENT_HEADER:
            raise ValueError("Wrong Missouri statement candidate columns")
        offset += len(STATEMENT_HEADER)
        if i == 0:
            if lines[offset:offset + 1] != ["Jurisdiction Wide"]:
                raise ValueError("Missing Missouri statement jurisdiction scope")
            offset += 1
        body.extend(lines[offset:])
    units, offset = {}, 0
    while offset < len(body):
        label = []
        while offset < len(body) and body[offset] != "Normal":
            label.append(body[offset])
            offset += 1
        unit = " ".join(label)
        if not unit or unit in units:
            raise ValueError("Missing or duplicate Missouri statement unit")
        modes = {}
        for mode in (["Normal", "Absentee", "Total"] if unit == "Total" else ["Normal", "Absentee"]):
            if body[offset:offset + 1] != [mode] or len(body[offset + 1:offset + 9]) != 8:
                raise ValueError("Truncated or missing Missouri statement mode")
            values = body[offset + 1:offset + 9]
            registered, total = map(count, values[:2])
            votes = {name: count(values[2 + i * 2]) for i, name in enumerate(CANDIDATES)}
            if sum(votes.values()) != total:
                raise ValueError("Missouri statement candidate sum differs from total")
            for i, value in enumerate(votes.values()):
                percentage(values[3 + i * 2], value, total)
            modes[mode] = dict(registered=registered, candidate_votes=votes)
            offset += 9
        if len({v["registered"] for v in modes.values()}) != 1:
            raise ValueError("Conflicting repeated Missouri statement registration")
        if unit == "Total" and offset != len(body):
            raise ValueError("Missouri statement county total is not last")
        units[unit] = modes
    if "Total" not in units:
        raise ValueError("Missing Missouri statement county total")
    return units


def review(units, summary, statement, expected_units=27):
    if (len(units) != expected_units or "ABSENTEE" not in units
            or set(statement) != set(units) | {"Total"}):
        raise ValueError("Missouri reporting unit sets differ")
    if (units["ABSENTEE"]["registered"] != 0
            or units["ABSENTEE"]["source_reported_percent"] != "N/A"
            or not units["ABSENTEE"]["ballots"]):
        raise ValueError("Wrong Missouri centralized absentee scope")
    totals, mode_totals = Counter(), {mode: Counter() for mode in ("Normal", "Absentee")}
    results, participation = [], []
    for unit, values in units.items():
        modes = statement[unit]
        if modes["Normal"]["registered"] != values["registered"]:
            raise ValueError("Missouri unit registration differs between reports")
        combined = {name: sum(modes[m]["candidate_votes"][name] for m in mode_totals)
                    for name in CANDIDATES}
        if combined != values["candidate_votes"]:
            raise ValueError("Missouri unit House vector differs between reports")
        absentee = unit == "ABSENTEE"
        empty_mode = "Normal" if absentee else "Absentee"
        if any(modes[empty_mode]["candidate_votes"].values()):
            raise ValueError("Changed Missouri centralized absentee mode scope")
        votes = sum(combined.values())
        if votes > values["ballots"] or (not absentee and values["ballots"] > values["registered"]):
            raise ValueError("Missouri candidate/ballot/registration relationship differs")
        totals.update(combined)
        for mode in mode_totals:
            mode_totals[mode].update(modes[mode]["candidate_votes"])
        common = dict(year=2026, state_code="MO", county_fips="29043", county_name="Christian",
                      key="MO|29043|" + unit, source_unit_id=unit, source_precinct_label=unit,
                      source_unit_kind="countywide_absentee" if absentee else "native_precinct_or_combined_group",
                      source_url=ORIGINALS["official-precinct-summary.pdf"])
        flag = ("countywide_absentee_not_residentially_allocated" if absentee
                else "geographic_counts_exclude_centralized_absentee")
        results.append(dict(common, source_office=CONTEST, source_district="7",
            democratic_votes=combined["MISSI HESKETH"], republican_votes=combined["ERIC W. BURLISON"],
            other_votes=combined["KEVIN CRAIG"], contest_votes=votes,
            candidate_votes=json.dumps(combined), quality_flags=flag))
        participation.append(dict(common, registered=values["registered"], ballots=values["ballots"],
            source_reported_percent=values["source_reported_percent"], source_certified=False,
            turnout_rate=None, rate_status="withheld_centralized_absentee_not_residentially_allocated",
            source_pages=values["source_pages"], native_statement_modes=modes,
            quality_flags=["unofficial", flag, "not_demographic_turnout"]))
    if (dict(totals) != summary["candidate_votes"]
            or sum(v["registered"] for v in units.values()) != summary["registered"]
            or sum(v["ballots"] for v in units.values()) != summary["ballots"]):
        raise ValueError("Missouri native groups differ from independent county totals")
    for mode, totals_for_mode in mode_totals.items():
        if dict(totals_for_mode) != statement["Total"][mode]["candidate_votes"]:
            raise ValueError("Missouri statement mode totals differ from native unit sum")
    county = statement["Total"]
    if (county["Total"]["candidate_votes"] != summary["candidate_votes"]
            or any(v["registered"] != summary["registered"] for v in county.values())):
        raise ValueError("Missouri statement county totals differ from independent summary")
    return results, participation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable Missouri review")
    originals, receipts, pages = {}, {}, {}
    titles = ["Election Summary Report", "Precinct Summary Report", "Statement of Votes Cast"]
    for i, (name, url) in enumerate(ORIGINALS.items()):
        raw = (args.cache_directory / name).read_bytes()
        receipt = json.loads((args.cache_directory / (name + ".receipt.json")).read_text())
        if (receipt["url"] != url or receipt["resolved_url"] != url or receipt["status"] != 200
                or receipt["bytes"] != len(raw) or receipt["sha256"] != hashlib.sha256(raw).hexdigest()):
            raise ValueError("Changed or wrong Missouri original receipt")
        originals[name], receipts[name] = raw, receipt
        if i:
            if url not in originals["official-election-index.html"].decode("utf-8"):
                raise ValueError("Missouri original not declared by official source index")
            pages[name] = pdf_pages(raw, titles[i - 1])
    units = precinct_units(pages["official-precinct-summary.pdf"])
    summary = county_summary(pages["official-election-summary.pdf"])
    results, participation = review(units, summary, statement_units(pages["official-statement-of-votes-cast.pdf"]))
    audit = dict(year=2026, state_code="MO", county_fips="29043", county_name="Christian",
        complete="no", source_election="November 3, 2026 General", source_election_date="2026-11-03",
        source_certified=False, reporting_units=len(results), counties=1,
        candidate_results="acquired_reconciled",
        participation="native_reporting_unit_counts_centralized_absentee_unallocated",
        boundaries="election_year_reference_pending", join="withheld",
        validation="house_vectors_and_native_participation_independently_reconciled",
        publication="full_counts_download_only", source_url=SOURCE, complete_download_url=RELEASE,
        native_original_sources=len(originals), native_original_bytes=sum(map(len, originals.values())),
        native_pdf_pages=sum(map(len, pages.values())), county_ballots=summary["ballots"],
        county_registered=summary["registered"], county_source_reported_percent=summary["source_reported_percent"],
        candidate_totals={field: sum(row[field] for row in results) for field in
                          ("democratic_votes", "republican_votes", "other_votes", "contest_votes")},
        geographic_reporting_groups=len(results) - 1, countywide_absentee_buckets=1,
        rates_available=0, rates_withheld=len(results),
        notes="Christian County only, not statewide Missouri. Native combined groups are not split. "
              "House vectors reconcile per native group and mode to the separate statement of votes "
              "cast and independent county summary. Registration repeats across statement modes "
              "are counted once, not summed. ABSENTEE has zero native registration and remains a "
              "countywide bucket. Geographic groups exclude these centralized absentee votes, so "
              "their displayed source percentages are retained, not relabeled full precinct turnout. "
              "No absentee allocation, full precinct rate, demographic rate, map or statewide completion "
              f"is claimed. All four originals and all {sum(map(len, pages.values()))} PDF pages are included. Normalized candidate "
              "review covers House District 7 only; other offices remain in full original reports.",
        next_action="Seek election-applicable boundaries and residential absentee allocation from the "
                    "county; continue other Missouri counties and remaining 2026 states/DC.")
    args.output.mkdir(parents=True)

    def save(name, value):
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        (args.output / name).write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)

    (args.output / "originals").mkdir()
    for name, raw in originals.items():
        (args.output / "originals" / (name + ".gz")).write_bytes(gzip.compress(raw, mtime=0))
    save("sources.json", receipts)
    save("native-pages.json.gz", pages)
    save("participation.json.gz", participation)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(results[0]))
    writer.writeheader()
    writer.writerows(results)
    (args.output / "results.csv.gz").write_bytes(gzip.compress(buffer.getvalue().encode(), mtime=0))
    save("audit.json", audit)
    save("checksums.json", {str(path.relative_to(args.output)): dict(bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(args.output.rglob("*")) if path.is_file()})
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(str(path.relative_to(args.output)), date_time=(2026, 11, 5, 0, 0, 0))
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
