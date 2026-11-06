"""Reproduce the complete native Susquehanna query offline with the standard library."""

import argparse
from collections import Counter
import csv
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


if not __debug__:
    raise RuntimeError("Run without -O: numerical validation must remain enabled")

ROOT = Path(__file__).resolve().parent
REPORTS = json.loads((ROOT / "source-inputs.json").read_text())
SPECS = [
    ("GOVERNOR AND LT. GOV", [
        ("JOSH SHAPIRO / AUSTIN DAVIS", "DEM", r"JOSH SHAPIRO / AUSTIN DAVIS {numbers} \(DEM\)"),
        ("STACY GARRITY / JASON RICHEY", "REP", r"STACY GARRITY / JASON {numbers} RICHEY \(REP\)"),
        ("KEN KRAWCHUK / JOHN THOMAS", "LIB", r"KEN KRAWCHUK / JOHN {numbers} THOMAS \(LIB\)"),
        ("Write-in", None, r"Write-in {numbers}"),
    ]),
    ("REPRESENTATIVE IN CONGRESS 9TH DISTRICT", [
        ("RACHEL WALLACE", "DEM", r"RACHEL WALLACE \(DEM\) {numbers}"),
        ("DAN MEUSER", "REP", r"DAN MEUSER \(REP\) {numbers}"),
        ("Write-in", None, r"Write-in {numbers}"),
    ]),
    ("SENATOR IN THE GENERAL ASSEMBLY 20TH DISTRICT", [
        ("JACKIE BAKER", "DEM", r"JACKIE BAKER \(DEM\) {numbers}"),
        ("LISA BAKER", "REP", r"LISA BAKER \(REP\) {numbers}"),
        ("Write-in", None, r"Write-in {numbers}"),
    ]),
    ("REPRESENTATIVE IN THE GENERAL ASSEMBLY 111TH DISTRICT", [
        ("KYLE DEVLIN", "DEM", r"KYLE DEVLIN \(DEM\) {numbers}"),
        ("JONATHAN FRITZ", "REP", r"JONATHAN FRITZ \(REP\) {numbers}"),
        ("Write-in", None, r"Write-in {numbers}"),
    ]),
]


def compact(text):
    return " ".join(text.split())


def integer(text):
    return int(text.replace(",", ""))


def inventory(text):
    return Counter(re.findall(r"[A-Za-z]+|\d+(?:,\d{3})*(?:\.\d+)?", text))


def percentage(votes, denominator, rounding=ROUND_HALF_UP):
    return str((Decimal(votes) * 100 / Decimal(denominator)).quantize(
        Decimal("0.01"), rounding=rounding)) if denominator else None


def check_percentage(votes, denominator, printed, where, conflicts):
    if printed == "-":
        assert votes == 0, (where, votes, printed)
        return
    expected = percentage(votes, denominator)
    half_even = percentage(votes, denominator, ROUND_HALF_EVEN)
    assert half_even is None or Decimal(printed.rstrip("%")) == Decimal(half_even), (
        where, printed, half_even)
    if expected is not None and Decimal(printed.rstrip("%")) != Decimal(expected):
        conflicts.append(dict(where=where, numerator=votes, denominator=denominator,
                              printed=printed, recomputed_round_half_up=expected,
                              recomputed_round_half_even=half_even,
                              exact_half_tie=True))


def header(text, role, page):
    lines = [compact(line) for line in text.splitlines() if compact(line)]
    native_name = "SUSQUEHANNA COUNTY, PA" if role != "precinct" else lines[lines.index("UNOFFICIAL RESULTS") - 1]
    normalized = compact(text)
    date = re.findall(r"Date:\s*(\d+/\d+/\d+)", normalized)
    clock = re.findall(r"Time:\s*(\d+:\d+:\d+ [AP]M EST)", normalized)
    native_page = re.findall(r"Page (\d+)/(\d+)", normalized)
    assert len(date) == len(clock) == len(native_page) == 1, (role, page)
    assert date[0] == "11/3/2026"
    assert "Unofficial Election Day Results" in normalized and "UNOFFICIAL RESULTS" in normalized
    assert native_page[0] == ((str(page), "16") if role == "canvass" else ("1", "1"))
    return dict(role=role, physical_page=page, native_name=native_name,
                native_date=date[0], native_clock=clock[0],
                native_page="/".join(native_page[0]), native_status="UNOFFICIAL RESULTS",
                native_title="Unofficial Election Day Results")


def parse_contests(text, conflicts, where):
    normalized = compact(text)
    positions = []
    for title, choices in SPECS:
        assert normalized.count(title) == 1, (where, title)
        positions.append((normalized.index(title), title, choices))
    result = {}
    positions.sort()
    for index, (start, title, choices) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(normalized)
        body = normalized[start + len(title):end].strip()
        total_match = re.findall(r"Total Votes ([\d,]+)", body)
        assert len(total_match) == 1, (where, title)
        total = integer(total_match[0])
        parsed_choices = []
        for label, party, template in choices:
            pattern = template.format(numbers=r"([\d,]+) (\d+(?:\.\d+)?%)")
            found = re.findall(pattern, body)
            assert len(found) == 1, (where, title, label, body)
            votes, printed = integer(found[0][0]), found[0][1]
            check_percentage(votes, total, printed, [where, title, label], conflicts)
            parsed_choices.append(dict(native_choice=label, native_literal_party=party,
                                       votes=votes, printed_percentage=printed))
            body = re.sub(pattern, "", body, count=1)
        reporting = re.findall(r"Number of Precincts (\d+) Precincts Reporting (\d+) (\d+(?:\.\d+)?%)", compact(body))
        body = re.sub(r"Number of Precincts \d+ Precincts Reporting \d+ \d+(?:\.\d+)?%", "", compact(body))
        body = re.sub(r"Vote For 1 Total Votes [\d,]+", "", compact(body))
        assert not compact(body), (where, title, "unparsed contest tokens", body)
        assert sum(row["votes"] for row in parsed_choices) == total, (where, title)
        assert not reporting or reporting == [("41", "41", "100.00%")]
        result[title] = dict(total_votes=total, choices=parsed_choices,
                             native_reporting=reporting)
    return result


def parse_participation(text, conflicts, where):
    found = re.findall(r"Registered Voters ([\d,]+) - Total Ballots ([\d,]+) : (\d+(?:\.\d+)?%)", compact(text))
    assert len(found) == 1, where
    registrations, ballots, printed = integer(found[0][0]), integer(found[0][1]), found[0][2]
    assert 0 <= ballots <= registrations
    check_percentage(ballots, registrations, printed, [where, "participation"], conflicts)
    return dict(registered_voters=registrations, total_ballots=ballots, printed_percentage=printed)


def review(engine, summary_columns):
    conflicts = []
    summary_text = REPORTS["summary"]["native_pages"][engine][0]
    summary = dict(**header(summary_text, "summary", 1),
                   **parse_participation(summary_text, conflicts, "county summary"),
                   contests=parse_contests(" ".join(summary_columns), conflicts, "county summary"))
    assert re.search(r"41 of 41 Precincts Reporting\s+100\.00%", compact(summary_text))
    precincts = []
    for page, text in enumerate(REPORTS["precinct"]["native_pages"][engine], 1):
        row = dict(**header(text, "precinct", page),
                   **parse_participation(text, conflicts, ["precinct", page]),
                   contests=parse_contests(text, conflicts, ["precinct", page]))
        for contest in row["contests"].values():
            assert contest["total_votes"] <= row["total_ballots"], row["native_name"]
            contest["ballots_less_contest_votes_unclassified"] = row["total_ballots"] - contest["total_votes"]
        precincts.append(row)
    names = {row["native_name"] for row in precincts}
    assert len(precincts) == len(names) == 41
    for field in ("registered_voters", "total_ballots"):
        assert sum(row[field] for row in precincts) == summary[field], field
    for title, contest in summary["contests"].items():
        assert sum(row["contests"][title]["total_votes"] for row in precincts) == contest["total_votes"], title
        contest["ballots_less_contest_votes_unclassified"] = summary["total_ballots"] - contest["total_votes"]
        for index, candidate in enumerate(contest["choices"]):
            assert sum(row["contests"][title]["choices"][index]["votes"] for row in precincts) == candidate["votes"]

    canvass, source_pages = [], []
    for page, text in enumerate(REPORTS["canvass"]["native_pages"][engine], 1):
        info = header(text, "canvass", page)
        title, choices = SPECS[(page - 1) // 4]
        assert title in compact(text), (page, title)
        source_pages.append(info)
        lines = [compact(line) for line in text.splitlines() if compact(line)]
        native_name = None
        for index, line in enumerate(lines):
            matched = re.fullmatch(r"(Normal|Absentee / Mail-In|Total) (\d+) (\d+) (.+)", line)
            if not matched:
                continue
            mode, registrations, votes, rest = matched.groups()
            if mode == "Normal":
                native_name = lines[index - 1]
                assert native_name in names or native_name == "Total", (page, native_name)
            assert native_name is not None
            values = re.findall(r"(\d+) (\d+(?:\.\d+)?%|-)", rest)
            assert len(values) == len(choices) and " ".join(a + " " + b for a, b in values) == rest
            vector = [int(value) for value, _ in values]
            assert sum(vector) == int(votes), (page, line)
            for candidate_index, (value, printed) in enumerate(values):
                check_percentage(int(value), int(votes), printed,
                                 ["canvass", page, native_name, title, mode, candidate_index], conflicts)
            canvass.append(dict(**info, contest=title, jurisdiction=native_name,
                                native_mode=mode, repeated_registered_voters=int(registrations),
                                native_total_votes=int(votes), candidate_vote_vector=vector,
                                printed_percentage_vector=[printed for _, printed in values]))

    for title, choices in SPECS:
        rows = [row for row in canvass if row["contest"] == title]
        assert len(rows) == 85, (title, len(rows))
        for native_name in names | {"Total"}:
            selected = [row for row in rows if row["jurisdiction"] == native_name]
            expected_modes = {"Normal", "Absentee / Mail-In", "Total"} if native_name == "Total" else {"Normal", "Absentee / Mail-In"}
            assert {row["native_mode"] for row in selected} == expected_modes
            assert len(selected) == len(expected_modes)
            original = summary if native_name == "Total" else next(row for row in precincts if row["native_name"] == native_name)
            assert all(row["repeated_registered_voters"] == original["registered_voters"] for row in selected)
            modes = [row for row in selected if row["native_mode"] != "Total"]
            assert sum(row["native_total_votes"] for row in modes) == original["contests"][title]["total_votes"]
            for index in range(len(choices)):
                assert sum(row["candidate_vote_vector"][index] for row in modes) == original["contests"][title]["choices"][index]["votes"]
            if native_name == "Total":
                for mode in expected_modes:
                    total_row = next(row for row in selected if row["native_mode"] == mode)
                    if mode == "Total":
                        reference = original["contests"][title]
                        assert total_row["native_total_votes"] == reference["total_votes"]
                        assert total_row["candidate_vote_vector"] == [choice["votes"] for choice in reference["choices"]]
                    else:
                        constituents = [row for row in rows if row["jurisdiction"] != "Total" and row["native_mode"] == mode]
                        assert len(constituents) == 41
                        assert sum(row["native_total_votes"] for row in constituents) == total_row["native_total_votes"]
                        assert [sum(row["candidate_vote_vector"][index] for row in constituents) for index in range(len(choices))] == total_row["candidate_vote_vector"]
    return dict(summary=summary, precincts=precincts, canvass=canvass,
                source_pages=source_pages, round_half_up_differences=conflicts)


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def csv_bytes(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def validated():
    assert hashlib.sha256((ROOT / "source-inputs.json").read_bytes()).hexdigest() == (
        "2d4d1abb11743dd35cf94457579d07251937e850059e1bc1a4d0eec3bb3f79d9")
    assert hashlib.sha256((ROOT / "summary-columns.json").read_bytes()).hexdigest() == (
        "f43fcc505071fe1e1283d4fff0a3cd2b35a5fff12a7c56f673937b33f628a63a")
    assert set(REPORTS) == {"summary", "precinct", "canvass"}
    for role, expected in (("summary", 1), ("precinct", 41), ("canvass", 16)):
        report = REPORTS[role]
        assert report["physical_pages"] == expected
        assert set(report["native_pages"]) == {"pymupdf", "pdfplumber"}
        left, right = (report["native_pages"][engine] for engine in ("pymupdf", "pdfplumber"))
        assert len(left) == len(right) == expected
        assert all(inventory(a) == inventory(b) for a, b in zip(left, right))
    columns = json.loads((ROOT / "summary-columns.json").read_text())
    assert set(columns) == {"pymupdf", "pdfplumber"}
    assert all(len(value) == 2 for value in columns.values())
    assert inventory(" ".join(columns["pymupdf"])) == inventory(" ".join(columns["pdfplumber"]))
    left = review("pymupdf", columns["pymupdf"])
    right = review("pdfplumber", columns["pdfplumber"])
    assert left == right
    expected_ties = {
        (226, 320, "70.62%"), (57, 160, "35.62%"), (101, 160, "63.12%"),
        (13, 32, "40.62%"), (109, 160, "68.12%"),
    }
    assert len(left["round_half_up_differences"]) == len(expected_ties)
    assert {(row["numerator"], row["denominator"], row["printed"])
            for row in left["round_half_up_differences"]} == expected_ties
    return left


def tables(parsed):
    participation, candidates, accounting, reporting = [], [], [], []
    for unit in [parsed["summary"]] + parsed["precincts"]:
        base = dict(state="Pennsylvania", county="Susquehanna", election_date="2026-11-03",
                    native_unit=unit["native_name"], scope="county" if unit["role"] == "summary" else "precinct",
                    source_role=unit["role"], physical_page=unit["physical_page"],
                    native_date=unit["native_date"], native_clock=unit["native_clock"],
                    native_status=unit["native_status"], native_title=unit["native_title"])
        participation.append(dict(**base, native_ballot_label="Total Ballots",
            total_ballots=unit["total_ballots"], native_registration_label="Registered Voters",
            registered_voters=unit["registered_voters"], native_printed_percentage=unit["printed_percentage"],
            native_mode="", blank_ballots="", overvotes="", undervotes="", source_fips="",
            analysis_ballots_approved=False, analysis_rate_approved=False, map_approved=False))
        for title, contest in unit["contests"].items():
            accounting.append(dict(**base, native_contest=title, native_mode="",
                native_total_votes=contest["total_votes"], total_ballots=unit["total_ballots"],
                ballots_less_contest_votes_unclassified=contest["ballots_less_contest_votes_unclassified"],
                native_overvotes="", native_undervotes="", native_blank_ballots=""))
            for choice in contest["choices"]:
                candidates.append(dict(**base, native_contest=title, native_mode="",
                    native_choice=choice["native_choice"],
                    native_literal_party=choice["native_literal_party"] or "",
                    votes=choice["votes"], native_printed_percentage=choice["printed_percentage"],
                    native_contest_total_votes=contest["total_votes"]))
            if unit["role"] == "summary":
                assert contest["native_reporting"] == [("41", "41", "100.00%")]
                reporting.append(dict(**base, native_contest=title, reporting=41,
                                      number_of_precincts=41, native_printed_percentage="100.00%"))
        if unit["role"] == "summary":
            reporting.insert(0, dict(**base, native_contest="", reporting=41,
                                    number_of_precincts=41, native_printed_percentage="100.00%"))

    canvass, pages = [], []
    truncated_governor = ("JOSH SHAPIRO / AUSTIN", "STACY GARRITY / JASON",
                          "KEN KRAWCHUK / JOHN", "Write-in")
    for row in parsed["canvass"]:
        choices = parsed["summary"]["contests"][row["contest"]]["choices"]
        governor = row["contest"] == SPECS[0][0]
        for index, choice in enumerate(choices):
            canvass.append(dict(state="Pennsylvania", county="Susquehanna",
                election_date="2026-11-03", scope="county" if row["jurisdiction"] == "Total" else "precinct",
                native_unit=row["jurisdiction"], native_contest=row["contest"],
                native_mode=row["native_mode"], source_role="canvass", physical_page=row["physical_page"],
                native_date=row["native_date"], native_clock=row["native_clock"],
                native_status=row["native_status"], native_title=row["native_title"],
                repeated_registered_voters_not_additive=row["repeated_registered_voters"],
                native_total_votes=row["native_total_votes"], native_choice_column=index + 1,
                native_choice=truncated_governor[index] if governor else choice["native_choice"],
                native_literal_party="" if governor else choice["native_literal_party"] or "",
                matched_summary_choice=choice["native_choice"],
                matched_summary_literal_party=choice["native_literal_party"] or "",
                identity_match_basis="same contest and ordered choice columns; all 41 precinct and county choice vectors reconcile",
                votes=row["candidate_vote_vector"][index],
                native_printed_percentage=row["printed_percentage_vector"][index],
                native_ballots="", native_ballot_mode_count="", source_fips=""))
    for role, units in (("summary", [parsed["summary"]]), ("precinct", parsed["precincts"]),
                        ("canvass", parsed["source_pages"])):
        for unit in units:
            page = unit["physical_page"]
            text = REPORTS[role]["native_pages"]["pdfplumber"][page - 1]
            column_header = ""
            if role == "canvass":
                title = SPECS[(page - 1) // 4][0]
                normalized = compact(text)
                column_header = normalized.split(title, 1)[1].split("Jurisdiction Wide", 1)[0].strip()
                if title == SPECS[0][0]:
                    assert "(DEM)" not in column_header and "(REP)" not in column_header and "(LIB)" not in column_header
                    assert all(token in column_header for token in ("SHAPIRO", "GARRITY", "KRAWCHUK", "Write-in"))
                else:
                    assert "(DEM)" in column_header and "(REP)" in column_header
            pages.append(dict(source_role=role, physical_page=page, native_page=unit["native_page"],
                native_unit=unit["native_name"], native_date=unit["native_date"],
                native_clock=unit["native_clock"], native_status=unit["native_status"],
                native_title=unit["native_title"], native_column_header=column_header))
    parties = []
    for row in candidates:
        identity = {key: value for key, value in row.items()
                    if key not in {"native_choice", "native_printed_percentage"}}
        assert not any(all(other[key] == identity[key] for key in
                   ("native_unit", "native_contest", "native_literal_party")) for other in parties)
        parties.append(dict(**identity, party_basis="literal source affiliation; empty is missing, not a party"))
    return {
        "county-participation.csv": participation[:1],
        "precinct-participation.csv": participation[1:],
        "candidate-results.csv": candidates,
        "literal-party-results.csv": parties,
        "canvass-candidate-results.csv": canvass,
        "contest-accounting.csv": accounting,
        "reporting.csv": reporting,
        "source-pages.csv": pages,
    }


def build(output):
    output = Path(output)
    parsed = validated()
    datasets = tables(parsed)
    expected_counts = dict(zip(datasets, (1, 41, 546, 546, 1105, 168, 5, 58)))
    assert {name: len(rows) for name, rows in datasets.items()} == expected_counts
    provenance = json.loads((ROOT / "source-provenance.json").read_text())
    assert len(provenance["source_receipts"]) == 4 and len(provenance["declarations"]) == 3
    for receipt in provenance["source_receipts"]:
        assert receipt["status"] == 200 and receipt["url"] == receipt["final_url"]
        assert receipt["url"].startswith("https://www.susqco.com/")
    methods = dict(
        snapshot="20261106-susquehanna-native-turnout-01", election_date="2026-11-03",
        scope="Complete native numerical query; no analysis, rate, geographic identity or map approval yet.",
        native_ballots="Total Ballots, retained separately from candidate votes and mail-process observations.",
        denominator="Native Registered Voters; not CVAP, VAP, VEP or CPS.",
        reporting="41/41 reported is not certification or completed counting.",
        modes="Normal / Absentee / Mail-In are candidate-vote modes, not ballot-mode counts. County Total repeats mode sums. Never sum county with precinct or Total with its components.",
        registrations="Canvass registration denominators repeat in every mode/contest; they are checked, not added.",
        accounting="Blank ballots, ballot modes, overvotes and undervotes are absent, not zero. Ballots minus contest votes are unclassified residuals.",
        parties="Summary/precinct affiliations are literal. Governor canvass labels are truncated and lack parties; matched_summary fields are explicitly cross-report matched identities, not native canvass affiliations. Empty affiliation means missing.",
        percentages="Native strings retained. Every numeric percentage reconciles under Decimal ROUND_HALF_EVEN; five exact ties differ from ROUND_HALF_UP. A dash is a missing percentage display on zero votes, not a numeric zero.",
        clocks="All 58 page clocks, including three distinct precinct seconds, and native vs physical page numbers retained; no acquisition clock replaces a native clock.",
        parent_mail_process=dict(issued=3000, received=2708, added_to_ballots=False),
        geography="No FIPS or polygon identity inferred. Preserve existing precinct datasets; this packet creates no geographic coverage.",
        reproduction="python3 -I review-susquehanna.py --output /new/empty/directory",
        tests="python3 -I test_review_susquehanna.py",
        source_originals="Complete original parent/PDF bytes retained privately with full size/hash receipts; both entire numerical text extractions and summary column extractions included.",
        source_receipts=provenance["source_receipts"], declarations=provenance["declarations"])
    audit = dict(full_page_inventory_checks=58, independent_complete_parses_equal=True,
        all_41_precinct_participation_and_4_contest_mode_matrices_reconcile=True,
        full_canvass_vectors=340, all_printed_percentages_reconcile_under_round_half_even=True,
        row_counts=expected_counts, analysis_ballots_approved=False,
        analysis_rate_approved=False, map_approved=False,
        parsed=parsed)
    files = {name: csv_bytes(rows) for name, rows in datasets.items()}
    files.update({"methods.json": json_bytes(methods), "audit.json": json_bytes(audit)})
    for name in ("source-inputs.json", "summary-columns.json", "source-provenance.json",
                 "review-susquehanna.py", "test_review_susquehanna.py"):
        files[name] = (ROOT / name).read_bytes()
    files["checksums.json"] = json_bytes({
        name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        for name, body in sorted(files.items())})
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
        for name, body in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zipped.writestr(info, body)
    files["complete-query.zip"] = archive.getvalue()
    output.mkdir(parents=True, exist_ok=True)
    assert output.resolve() == ROOT or not any(output.iterdir()), "Reproduction output must be empty"
    for name, body in files.items():
        (output / name).write_bytes(body)
    print(json.dumps(dict(files=len(files), zip_members=len(files) - 1,
        rows=expected_counts, zip_bytes=len(files["complete-query.zip"]),
        zip_sha256=hashlib.sha256(files["complete-query.zip"]).hexdigest()), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)
