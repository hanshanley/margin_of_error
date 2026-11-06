"""Reproduce complete Fulton numerical facts without redistributing source templates."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


OFFICES = (
    "GOVERNOR AND LIEUTENANT GOVERNOR",
    "REPRESENTATIVE IN CONGRESS 13TH DISTRICT",
    "SENATOR IN THE GENERAL ASSEMBLY 30TH DISTRICT",
    "REPRESENTATIVE IN THE GENERAL ASSEMBLY 78TH DISTRICT",
)
UNITS = (
    "Ayr Township", "Belfast Township", "Bethel Township", "Brush Creek Township",
    "Dublin Township", "Licking Creek Township", "McConnellsburg Borough",
    "Taylor Township", "Thompson Township", "Todd Township", "Union Township",
    "Valley Hi Borough", "Wells Township",
)
MODES = ("Mail", "Election Day Voting", "Provisional", "Total")
NUMBER = r"(?:0|[1-9]\d*)(?:,\d{3})*"
PAIR = rf"({NUMBER})\s+(\d+\.\d{{2}}%)"
VECTOR = re.compile(rf"^{PAIR}\s+{PAIR}\s+{PAIR}\s+{PAIR}$")
STAT = re.compile(rf"({NUMBER}) of ({NUMBER})(?: registered voters)? = (\d+\.\d{{2}}%)")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    require(re.fullmatch(NUMBER, value), f"Invalid native integer: {value!r}")
    return int(value.replace(",", ""))


def vector(value):
    match = VECTOR.fullmatch(value)
    require(match is not None, f"Incomplete native count/percentage vector: {value}")
    values = match.groups()
    return {"count_literals": list(values[::2]), "percent_literals": list(values[1::2])}


def parse_report(text, label, url):
    require(text.splitlines()[0].startswith(label + " ")
            and "FULTON COUNTY, PENNSYLVANIA" in text
            and "GENERAL ELECTION, NOVEMBER 3, 2026" in text
            and "Registered Voters" in text and "Precincts Reporting" in text
            and "Official Results" in text and "*** End of report ***" in text,
            "Missing native election identity, status or report end")
    statements = [list(match) for match in STAT.findall(text)]
    require(len(statements) == (2 if label == "Cumulative Results" else 3),
            "Missing or unexpected native participation/reporting statements")
    headings = list(re.finditer(r"^(.+?) - \((Vote for (?:One|the candidates of ONE Party))\)$", text, re.M))
    require(tuple(match[1] for match in headings) == OFFICES, "Incomplete native contest inventory")
    contests = []
    for index, heading in enumerate(headings):
        body = text[heading.end():headings[index + 1].start() if index + 1 < len(headings) else text.index("*** End of report ***")]
        candidates, accounting = [], {}
        for line in (line.strip() for line in body.splitlines()):
            if not line:
                continue
            if " ".join(line.split()) == "Choice Party Mail Election Day Voting Provisional Total":
                continue
            if line.startswith("Cast Votes:"):
                require("cast" not in accounting, "Duplicate cast-vote row")
                accounting["cast"] = vector(line.split(":", 1)[1].strip())
            elif line.startswith(("Undervotes:", "Overvotes:")):
                kind, values = line.split(":", 1)
                kind = kind.lower()
                require(kind not in accounting, "Duplicate native accounting row")
                counts = values.split()
                require(len(counts) == 4, "Incomplete under/overvote vector")
                for value in counts:
                    integer(value)
                accounting[kind] = counts
            else:
                match = re.fullmatch(r"(.+?)\s+([A-Z][A-Z0-9_-]*)\s+(\d.+)", line)
                require(match is not None, f"Unrecognized native result line: {line}")
                candidates.append({"name": match[1], "party_literal": match[2], **vector(match[3])})
        require(candidates and set(accounting) == {"cast", "undervotes", "overvotes"},
                "Incomplete candidates or native ballot accounting")
        contests.append({"office_literal": heading[1], "vote_for_literal": heading[2],
                         "candidates": candidates, "accounting": accounting})
    date, time = re.search(r"Run Date\s+(\d{2}/\d{2}/\d{4})", text), re.search(r"Run Time\s+(\d{1,2}:\d{2} [AP]M)", text)
    require(date is not None and time is not None and date[1] == "11/03/2026",
            "Missing or mismatched native run date/time")
    return {"label": label, "source_url": url, "native_status_literal": "Official Results",
            "run_date_literal": date[1], "run_time_literal": time[1],
            "declared_timezone": None, "statements": statements, "contests": contests}


def counts(row):
    values = [integer(value) for value in row["count_literals"]]
    require(sum(values[:3]) == values[3], "Native mode counts do not equal total")
    return values


def validate(facts):
    require(facts["schema"] == "fulton-2026-complete-numerical-facts-v1", "Unknown facts schema")
    reports = facts["reports"]
    require([row["label"] for row in reports] == ["Cumulative Results", *UNITS],
            "Missing, duplicated or unexpected source report")
    for report in reports:
        require(report["native_status_literal"] == "Official Results"
                and report["run_date_literal"] == "11/03/2026"
                and report["declared_timezone"] is None, "Changed native status/time scope")
        statements = report["statements"]
        require(len(statements) == (2 if report["label"] == "Cumulative Results" else 3),
                "Incomplete native participation statements")
        for numerator, denominator, percent in statements:
            numerator, denominator = integer(numerator), integer(denominator)
            require(denominator > 0 and 0 <= numerator <= denominator
                    and abs(100 * numerator / denominator - float(percent[:-1])) <= .005000001,
                    "Native printed fraction does not match its own counts")
        require([integer(value) for value in statements[1][:2]] == (
            [13, 13] if report["label"] == "Cumulative Results" else [0, 1]),
            "Changed native reporting counters require a new qualified profile")
        if len(statements) == 3:
            require([integer(value) for value in statements[0][:2]]
                    == [integer(value) for value in statements[2][:2]],
                    "Header and municipal participation differ")
        require(tuple(row["office_literal"] for row in report["contests"]) == OFFICES,
                "Incomplete office inventory")
        mode_ballots = []
        for contest in report["contests"]:
            require(contest["vote_for_literal"] == (
                "Vote for the candidates of ONE Party" if contest["office_literal"] == OFFICES[0] else "Vote for One"),
                "Unsupported vote-for scope")
            identities = [(row["name"], row["party_literal"]) for row in contest["candidates"]]
            require(len(identities) == len(set(identities)), "Duplicate native candidate")
            cast = counts(contest["accounting"]["cast"])
            summed = [sum(counts(row)[mode] for row in contest["candidates"]) for mode in range(4)]
            require(summed == cast, "Candidate vectors do not reconcile to native cast votes")
            for row in [*contest["candidates"], contest["accounting"]["cast"]]:
                require(len(row["percent_literals"]) == 4, "Missing native percentage")
                for value, percent, denominator in zip(counts(row), row["percent_literals"], cast):
                    expected = 100 * value / denominator if denominator else 0
                    require(re.fullmatch(r"\d+\.\d{2}%", percent)
                            and abs(expected - float(percent[:-1])) <= .005000001,
                            "Native candidate percentage does not match cast votes")
            under = [integer(value) for value in contest["accounting"]["undervotes"]]
            over = [integer(value) for value in contest["accounting"]["overvotes"]]
            require(len(under) == len(over) == 4
                    and sum(under[:3]) == under[3] and sum(over[:3]) == over[3],
                    "Incomplete native under/overvote vector")
            mode_ballots.append([sum(values) for values in zip(cast, under, over)])
        require(all(row == mode_ballots[0] for row in mode_ballots)
                and mode_ballots[0][3] == integer(statements[0][0]),
                "Independent contest ballot accounting does not match native participation")
        report["accounted_ballots_by_mode"] = mode_ballots[0]
    county, units = reports[0], reports[1:]
    for column in (0, 1):
        require(sum(integer(row["statements"][0][column]) for row in units)
                == integer(county["statements"][0][column]),
                "Municipal participation does not reconcile to county")
    for office in range(4):
        expected = {(row["name"], row["party_literal"]): counts(row)
                    for row in county["contests"][office]["candidates"]}
        actual = {key: [0] * 4 for key in expected}
        for unit in units:
            candidates = unit["contests"][office]["candidates"]
            require({(row["name"], row["party_literal"]) for row in candidates} == set(expected),
                    "Municipal candidate inventory differs from county")
            for row in candidates:
                key = (row["name"], row["party_literal"])
                actual[key] = [left + right for left, right in zip(actual[key], counts(row))]
        require(actual == expected, "Municipal candidate vectors do not reconcile to county")
        for kind in ("undervotes", "overvotes"):
            expected_counts = [integer(value) for value in county["contests"][office]["accounting"][kind]]
            require([sum(integer(unit["contests"][office]["accounting"][kind][mode]) for unit in units)
                     for mode in range(4)] == expected_counts,
                    "Municipal accounting does not reconcile to county")
    return facts


def build(facts, output):
    facts = validate(facts)
    output.mkdir(parents=True, exist_ok=False)
    reports = facts["reports"]
    county = reports[0]
    common = {"year": 2026, "state_code": "PA", "county": "Fulton", "county_fips": "42057"}
    qualifications = [
        "Accounted ballots independently match the native registered-participation numerator in all four vote-for-one/ticket contests; candidate votes alone are not ballots.",
        "County reporting is 13 of 13; all thirteen municipal reports separately print 0 of 1 despite positive counts. These counters do not establish finished counting.",
        "Official Results is the native literal, not independently established certification. Separate write-in rows are absent, not inferred zeroes.",
        "Each report retains its own November 3 run time; no source timezone is declared. No county or precinct mapping is approved.",
    ]
    tables = {}
    tables["county-participation.csv"] = [{
        **common, "accounted_ballots": county["accounted_ballots_by_mode"][3],
        "native_reported_participants": integer(county["statements"][0][0]),
        "registered_voters": integer(county["statements"][0][1]),
        "native_printed_turnout": county["statements"][0][2],
        "native_status_literal": county["native_status_literal"],
        "source_update_literal": f'{county["run_date_literal"]} {county["run_time_literal"]}; native run time, timezone not declared',
        "county_fips_basis": "Reviewed 2026 Census county identity, not a native PDF field",
        "counting_qualifications_json": json.dumps(qualifications),
    }]
    participation, candidates, accounting, statements = [], [], [], []
    for report in reports:
        base = {**common, "source_report": report["label"], "source_url": report["source_url"],
                "run_date_literal": report["run_date_literal"], "run_time_literal": report["run_time_literal"],
                "declared_timezone": "", "native_status_literal": report["native_status_literal"]}
        if report is not county:
            participation.append({**base, "native_reported_participants": integer(report["statements"][0][0]),
                                  "registered_voters": integer(report["statements"][0][1]),
                                  "native_printed_turnout": report["statements"][0][2],
                                  "reported_units": integer(report["statements"][1][0]),
                                  "total_units": integer(report["statements"][1][1])})
        for ordinal, (numerator, denominator, percent) in enumerate(report["statements"]):
            statements.append({**base, "statement_ordinal": ordinal,
                               "statement_kind": "precincts_reporting" if ordinal == 1 else "registered_participation",
                               "numerator_literal": numerator, "denominator_literal": denominator,
                               "printed_percent_literal": percent})
        for contest in report["contests"]:
            scope = {**base, "office_literal": contest["office_literal"], "vote_for_literal": contest["vote_for_literal"]}
            for candidate in contest["candidates"]:
                row = {**scope, "candidate": candidate["name"], "party_literal": candidate["party_literal"]}
                for mode, value, literal, percent in zip(MODES, counts(candidate), candidate["count_literals"], candidate["percent_literals"]):
                    row.update({mode: value, mode + "_count_literal": literal, mode + "_percent_literal": percent})
                candidates.append(row)
            row = {**scope}
            for mode, index in zip(MODES, range(4)):
                for kind in ("cast", "undervotes", "overvotes"):
                    raw = contest["accounting"][kind]
                    literal = raw["count_literals"][index] if kind == "cast" else raw[index]
                    row.update({mode + "_" + kind: integer(literal), mode + "_" + kind + "_literal": literal})
                row[mode + "_cast_percent_literal"] = contest["accounting"]["cast"]["percent_literals"][index]
                row[mode + "_accounted_ballots"] = report["accounted_ballots_by_mode"][index]
            accounting.append(row)
    tables.update({
        "native-unit-participation.csv": participation,
        "county-candidate-results.csv": [row for row in candidates if row["source_report"] == "Cumulative Results"],
        "native-unit-candidate-results.csv": [row for row in candidates if row["source_report"] != "Cumulative Results"],
        "county-contest-accounting.csv": [row for row in accounting if row["source_report"] == "Cumulative Results"],
        "native-unit-contest-accounting.csv": [row for row in accounting if row["source_report"] != "Cumulative Results"],
        "native-source-statements.csv": statements,
    })
    party = Counter()
    for row in tables["county-candidate-results.csv"]:
        party[row["office_literal"], row["party_literal"]] += row["Total"]
    tables["county-literal-party-totals.csv"] = [
        {**common, "office_literal": office, "party_literal": label, "candidate_votes": votes}
        for (office, label), votes in party.items()
    ]
    for filename, rows in tables.items():
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / filename).write_text(buffer.getvalue())
    (output / "source-records.json").write_text(json.dumps(facts, indent=2) + "\n")
    audit = {"scope": "Fulton County only, 2026 general election; complete numerical facts from all fourteen county-declared PDFs",
             "maps_approved": False, "demographic_turnout_approved": False,
             "county_participation": tables["county-participation.csv"][0],
             "table_rows": {name: len(rows) for name, rows in tables.items()},
             "qualifications": qualifications,
             "source_representation": "Complete numerical facts, native identities/status/timestamps and receipt digests. Original PDF/HTML presentation bytes remain private; no template redistribution license is claimed."}
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "review-fulton-county-results.py").write_bytes(Path(__file__).read_bytes())
    files = sorted(path for path in output.iterdir() if path.is_file())
    checksums = {path.name: {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in files}
    (output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    archive_path = output / "complete-fulton-2026-numerical-facts-01.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path == archive_path:
                continue
            info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
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
        receipts = json.loads((args.private_source / "receipts.json").read_text())
        manifest = json.loads((args.private_source / "reports.json").read_text())
        reports = []
        for record in manifest:
            raw = (args.private_source / record["file"]).read_bytes()
            receipt = next(row for row in receipts if row["file"] == record["file"])
            require(receipt["status"] == 200 and len(raw) == receipt["bytes"]
                    and hashlib.sha256(raw).hexdigest() == receipt["sha256"], "Source receipt mismatch")
            with fitz.open(stream=raw, filetype="pdf") as document:
                require(len(document) == 1, "Unexpected source pagination")
                text = document[0].get_text("text", sort=True)
            reports.append(parse_report(text, record["label"], record["url"]))
        facts = {"schema": "fulton-2026-complete-numerical-facts-v1", "reports": reports,
                 "source_receipts": receipts,
                 "source_context_url": "https://www.co.fulton.pa.us/elections-enr-2026b.php",
                 "source_terms_url": "https://www.co.fulton.pa.us/terms-of-use.php"}
    else:
        facts = json.loads(args.facts.read_text())
    print(json.dumps(build(facts, args.output), indent=2))


if __name__ == "__main__":
    main()
