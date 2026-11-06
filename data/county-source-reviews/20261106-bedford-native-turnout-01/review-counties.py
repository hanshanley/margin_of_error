import argparse
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import zipfile


HERE = Path(__file__).resolve().parent
MODES = ("Election Day", "Mail-In", "Provisional", "Total")
TITLES = (
    "Governor and Lieutenant Governor (Vote for 1)",
    "Representative in Congress- 13th Congressional District (Vote for 1)",
    "Senator in the General Assembly- 32nd Senatorial District (Vote for 1)",
    "Representative in the General Assembly- 78th Legislative District (Vote for 1)",
)
STATIC = ("source-inputs.json", "source-provenance.json", "methods.json",
          "review-counties.py", "test_review_counties.py")
NUMBER = r"([\d,]+)"
VECTOR = r"\s+".join([NUMBER] * 4)


def integer(value):
    return int(value.replace(",", ""))


def one(pattern, text):
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise ValueError(f"Expected one field: {pattern!r}, found {len(matches)}")
    return matches[0]


def vector(match, offset=0):
    values = [integer(value) for value in match.groups()[offset:offset + 4]]
    if len(values) != 4 or sum(values[:3]) != values[3]:
        raise ValueError("Non-reconciling native mode vector")
    return dict(zip(MODES, values))


def percentage(numerator, denominator):
    return str((Decimal(numerator) * 100 / Decimal(denominator)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse(pages):
    if len(pages) != 2 or not all(isinstance(page, str) for page in pages):
        raise ValueError("Two complete numerical pages are required")
    text = [" ".join(page.split()) for page in pages]
    clocks = []
    for page_number, page in enumerate(text, 1):
        match = one(r"Page: (\d+) of (\d+) (\d+/\d+/\d+ \d+:\d+:\d+ [AP]M)", page)
        if (int(match[1]), int(match[2])) != (page_number, 2):
            raise ValueError("Physical and printed pages disagree")
        clocks.append(match[3])
    if len(set(clocks)) != 1:
        raise ValueError("Native page clocks disagree")
    first = text[0]
    for literal in ("Bedford County - Unofficial",
                    "Summary for: All Contests, All Districts, All Tabulators, All Counting Groups"):
        one(re.escape(literal), first)
    modes_text = first.split("Elector Group Counting Group Cards Cast Voters Cast Registered Voters Turnout", 1)[1]
    modes_text = modes_text.split("Precincts Reported:", 1)[0]
    mode_rows = []
    for mode in MODES:
        pattern = re.escape(mode) + r" " + NUMBER + r" " + NUMBER
        pattern += (r" " + NUMBER) if mode == "Total" else ""
        pattern += r" (\d+\.\d{2})%"
        match = one(pattern, modes_text)
        cards, voters = integer(match[1]), integer(match[2])
        registered = integer(match[3]) if mode == "Total" else None
        printed = match[4] if mode == "Total" else match[3]
        mode_rows.append(dict(native_counting_group=mode, cards_cast=cards,
            voters_cast=voters, registered_voters=registered,
            native_turnout_pct=printed, is_aggregate=mode == "Total", source_page=1))
    total = mode_rows[-1]
    for field in ("cards_cast", "voters_cast"):
        if sum(row[field] for row in mode_rows[:-1]) != total[field]:
            raise ValueError("Native county mode counts do not reconcile")
    for row in mode_rows:
        if row["cards_cast"] != row["voters_cast"]:
            raise ValueError("This report's native cards/voters equality changed")
        if percentage(row["voters_cast"], total["registered_voters"]) != row["native_turnout_pct"]:
            raise ValueError("Native county/mode turnout changed")
    summary = first.split(TITLES[0], 1)[0]
    reported = one(r"Precincts Reported: (\d+) of (\d+) \((\d+\.\d{2})%\)", summary)
    if percentage(int(reported[1]), int(reported[2])) != reported[3]:
        raise ValueError("Native reporting percentage does not reconcile")
    county = dict(native_county="Bedford County", native_status="Unofficial",
        voters_cast=total["voters_cast"], cards_cast=total["cards_cast"],
        registered_voters=total["registered_voters"], native_turnout_pct=total["native_turnout_pct"],
        native_report_clock=clocks[0], native_timezone=None, native_fips=None,
        analysis_rate_approved=False, map_approved=False, source_page=1)
    voters_line = one(r"Voters Cast: " + NUMBER + r" of " + NUMBER + r" \((\d+\.\d{2})%\)", summary)
    if (integer(voters_line[1]), integer(voters_line[2]), voters_line[3]) != (
            county["voters_cast"], county["registered_voters"], county["native_turnout_pct"]):
        raise ValueError("Repeated native voters/registrations disagree")
    if integer(one(r"Cards Cast: " + NUMBER, summary)[1]) != county["cards_cast"]:
        raise ValueError("Repeated native cards disagree")
    reporting = [dict(scope="County summary", reported=int(reported[1]),
        total=int(reported[2]), native_pct=reported[3], source_page=1)]
    candidates, contests, accounting, unresolved = [], [], [], []
    for index, title in enumerate(TITLES):
        page_number = 1 if index < 2 else 2
        page = text[page_number - 1]
        one(re.escape(title), page)
        section = page.split(title, 1)[1]
        next_title = TITLES[index + 1] if index in (0, 2) else None
        if next_title:
            section = section.split(next_title, 1)[0]
        report = one(r"Precincts Reported: (\d+) of (\d+) \((\d+\.\d{2})%\)", section)
        if tuple(report.groups()) != tuple(reported.groups()):
            raise ValueError("Native contest reporting differs from the county summary")
        reporting.append(dict(scope=title, reported=int(report[1]),
            total=int(report[2]), native_pct=report[3], source_page=page_number))
        times = one(r"Times Cast " + VECTOR + r" / " + NUMBER + r" (\d+\.\d{2})%", section)
        times_vector = vector(times)
        if (times_vector["Total"], integer(times[5]), times[6]) != (
                county["voters_cast"], county["registered_voters"], county["native_turnout_pct"]):
            raise ValueError("Contest times cast changed")
        if any(times_vector[mode] != row["voters_cast"] for mode, row in zip(MODES, mode_rows)):
            raise ValueError("Contest times-cast modes changed")
        unders = vector(one(r"Undervotes " + VECTOR, section))
        overs = vector(one(r"Overvotes " + VECTOR, section))
        totals = vector(one(r"Total Votes " + VECTOR, section))
        writeins = vector(one(r"(?<!Unresolved )Write-in " + VECTOR + r" (\d+\.\d{2})%", section))
        unresolved_vector = vector(one(r"Unresolved Write-In " + VECTOR, section))
        if writeins != unresolved_vector:
            raise ValueError("Native write-in/unresolved vectors differ; review new semantics")
        candidate_text = section.split("Candidate Party Election Day Mail-In Provisional Total", 1)[1]
        candidate_text = candidate_text.split("Total Votes ", 1)[0].strip()
        pattern = r"(.+?) (?:(DEM|REP|LIB) )?" + VECTOR + r" (\d+\.\d{2})%"
        position = 0
        parsed_candidates = []
        for match in re.finditer(pattern, candidate_text):
            if candidate_text[position:match.start()].strip():
                raise ValueError("Unparsed candidate text")
            name, party = match[1].strip(), match[2]
            counts = vector(match, 2)
            printed = match[7]
            if percentage(counts["Total"], totals["Total"]) != printed:
                raise ValueError("Native candidate percentage does not reconcile")
            parsed_candidates.append(dict(contest=title, candidate=name, native_party=party,
                election_day=counts["Election Day"], mail_in=counts["Mail-In"],
                provisional=counts["Provisional"], total=counts["Total"],
                native_pct=printed, is_unresolved_write_in=name == "Write-in",
                source_page=page_number))
            position = match.end()
        if candidate_text[position:].strip() or not parsed_candidates:
            raise ValueError("Incomplete candidate extraction")
        if len([row for row in parsed_candidates if row["is_unresolved_write_in"]]) != 1:
            raise ValueError("Missing or repeated native write-in candidate row")
        if any(row["native_party"] is not None for row in parsed_candidates if row["is_unresolved_write_in"]):
            raise ValueError("Unresolved write-in affiliation invented")
        keys = ("election_day", "mail_in", "provisional", "total")
        for mode, key in zip(MODES, keys):
            if sum(row[key] for row in parsed_candidates if not row["is_unresolved_write_in"]) != totals[mode]:
                raise ValueError("Named candidate vectors do not reconcile with native Total Votes")
            if totals[mode] + unders[mode] + overs[mode] != times_vector[mode]:
                raise ValueError("Native Total Votes/under/over accounting changed")
            accounting.append(dict(contest=title, counting_group=mode,
                times_cast=times_vector[mode], native_total_votes=totals[mode],
                native_undervotes=unders[mode], native_overvotes=overs[mode],
                native_unresolved_write_in=unresolved_vector[mode],
                unresolved_not_added_again=True, source_page=page_number))
        candidates.extend(parsed_candidates)
        contests.append(dict(contest=title, vote_for=1, native_total_votes=totals["Total"],
            times_cast=times_vector["Total"], native_undervotes=unders["Total"],
            native_overvotes=overs["Total"], source_page=page_number))
        unresolved.append(dict(contest=title, election_day=writeins["Election Day"],
            mail_in=writeins["Mail-In"], provisional=writeins["Provisional"],
            total=writeins["Total"], native_candidate_label="Write-in",
            native_detail_label="Unresolved Write-In", is_nonadditive=True,
            allocation_to_undervotes_or_overvotes=None, source_page=page_number))
    return dict(county=[county], ballot_modes=mode_rows, candidates=candidates,
        contests=contests, accounting=accounting, unresolved=unresolved, reporting=reporting,
        pages=[dict(physical_page=n, printed_page=n, printed_pages=2,
            native_report_clock=clock, native_timezone=None) for n, clock in enumerate(clocks, 1)])


def review(inputs):
    if inputs["election_scope_origin"] != "Official declaring page: 2026 General Election":
        raise ValueError("Election scope declaration changed")
    if inputs["numeric_pages_sha256"] != hashlib.sha256(
            json.dumps(inputs["extractions"], ensure_ascii=True, sort_keys=True).encode()).hexdigest():
        raise ValueError("Complete numerical page evidence changed")
    parsed = [parse(inputs["extractions"][name]) for name in ("pymupdf", "pdfplumber")]
    if parsed[0] != parsed[1]:
        raise ValueError("Independent complete numerical extractions disagree")
    return parsed[0]


def encode_json(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def build(output):
    output = Path(output)
    if output.exists():
        raise ValueError("Refusing to overwrite an existing output")
    source = json.loads((HERE / "source-inputs.json").read_text())
    parsed = review(source)
    output.mkdir(parents=True)
    for name in STATIC:
        shutil.copyfile(HERE / name, output / name)
    filenames = dict(county="county-participation.csv", ballot_modes="ballot-modes.csv",
        candidates="candidate-results.csv", contests="contest-totals.csv",
        accounting="contest-accounting.csv", unresolved="unresolved-write-ins.csv",
        reporting="reporting.csv", pages="source-pages.csv")
    for key, filename in filenames.items():
        rows = parsed[key]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / filename).write_bytes(stream.getvalue().encode())
    audit = dict(row_counts={filenames[key]: len(rows) for key, rows in parsed.items()},
        two_complete_independent_extractions_match=True, all_named_candidate_mode_vectors_reconcile=True,
        all_native_mode_and_accounting_vectors_reconcile=True,
        unresolved_write_in_totals=[row["total"] for row in parsed["unresolved"]],
        unresolved_write_ins_not_added_to_native_total_votes=True,
        unresolved_allocation_to_under_or_overvotes_not_inferred=True,
        native_timezone_missing=True, native_fips_missing=True,
        analysis_rate_approvals=0, map_approvals=0, all_complete_pages_in_source_inputs=True,
        source_pdf_sha256=source["source_pdf_sha256"],
        scope="Complete native numerical query; no statewide, precinct-geometry, certified-turnout, "
              "unique-person deduplication, or completed-counting claim.")
    (output / "audit.json").write_bytes(encode_json(audit))
    files = sorted(path for path in output.iterdir() if path.is_file())
    manifest = dict(files=[dict(path=path.name, bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in files],
        scope="Every factual/static query file; manifest and complete-query.zip excluded to avoid self-reference. "
              "The archive includes this manifest but never includes itself.")
    (output / "checksums.json").write_bytes(encode_json(manifest))
    with zipfile.ZipFile(output / "complete-query.zip", "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path in sorted(output.iterdir()):
            if path.name == "complete-query.zip":
                continue
            info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Review and reproduce the complete Bedford native numerical query offline.")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
