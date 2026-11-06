"""Reproduce Greene's complete reviewed county summary without copying its HTML."""

import argparse
from collections import Counter
import csv
from decimal import Decimal, ROUND_HALF_UP
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


REVIEWED_INPUT_SHA256 = "78d2d6dbca161c6cdc1a8e45c8b11ea84a2ec6434612e53a605ccc8e1e0254b4"
ARCHIVE = "complete-greene-county-native-query-01.zip"
TITLES = (
    "Ballots Cast - Total", "Ballots Cast - Blank",
    "Governor And Lieutenant Governor",
    "Representative In Congress 14th Congressional District",
    "Senator In The General Assembly 46th Senatorial District",
    "Representative In The General Assembly 50th Legislative",
)
CHOICES = (
    ("Ballots Cast - Total", "Ballots Cast Total"),
    ("Ballots Cast - Blank", "No Party Specified"),
    ("Dem Josh Shapiro", "Democrat"), ("Rep Stacy Garrity", "Republican"),
    ("Lib Ken Krawchuk", "Libertarian"), ("WRITE-IN", "No Party Specified"),
    ("Dem Alan Bradstock", "Democrat"), ("Rep Guy Reschenthaler", "Republican"),
    ("WRITE-IN", "No Party Specified"),
    ("Rep Camera Bartolotta", "Republican"), ("Ind Jodi Borello", "Independent"),
    ("WRITE-IN", "No Party Specified"),
    ("Dem Lois Bower-bjornson", "Democrat"), ("Rep Ben Humble", "Republican"),
    ("WRITE-IN", "No Party Specified"),
)
ROW_TITLES = [TITLES[0], TITLES[1]] + [TITLES[2]] * 4 + [
    TITLES[3]] * 3 + [TITLES[4]] * 3 + [TITLES[5]] * 3
SOURCE_URLS = (
    "https://greenecountypa.gov/elections/",
    "https://greenecountypa.gov/elections/Default.aspx?PageLayout=SUMMARY&Election=30069",
)
SOURCE_HASHES = (
    "d77e59fc2e95ece940d403c8b86c000067b2ce44c83b324ab367a83d38cdc081",
    "7134871fe0c1b970c9eda80a75d058d48bda053ab15c60a6e48235f10159bf3e",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def validate(records, check_pinned=True):
    if check_pinned:
        require(hashlib.sha256(json_bytes(records)).hexdigest() == REVIEWED_INPUT_SHA256,
                "Changed complete reviewed factual input")
    require((records["year"], records["state_code"], records["county"]) == (2026, "PA", "Greene"),
            "Changed election identity")
    require(records["native_header"] == [
        "2026 General Election", "Tuesday, November 3, 2026",
        "42 of 42 precincts reporting.", "Unofficial Results with MI and Absentee"],
        "Changed native header or reporting scope")
    require(records["registered_voters"] is None, "Invented registration denominator")
    require(all(records[key] == "" for key in (
        "native_printed_turnout", "source_update_literal", "declared_timezone", "source_fips")),
        "Invented rate, update clock, timezone or native FIPS")
    require(records["counting_complete"] is False and records["maps_approved"] is False,
            "Invented counting or mapping approval")
    receipts = records["source_receipts"]
    require(len(receipts) == 2, "Incomplete original response receipts")
    for row, name, url, size, digest in zip(receipts, (
        "greene-parent.html", "greene-all-returns.html"), SOURCE_URLS, (9199, 12992), SOURCE_HASHES):
        require((row["file"], row["url"], row["final_url"], row["status"], row["bytes"], row["sha256"])
                == (name, url, url, 200, size, digest), "Changed original response identity")
        require(bool(re.fullmatch(r"2026-11-06T10:56:29\.\d+\+00:00", row["fetched_at_utc"])),
                "Changed retrieval clock")
        require(row["content_type"] == "text/html; charset=utf-8", "Changed response type")
    require(records["source_declarations"] == [
        dict(county="Greene", label="All returns", url=SOURCE_URLS[1])],
        "Changed actual county-parent declaration")
    rows = records["native_rows"]
    require(len(rows) == 15, "Incomplete native query")
    groups = {}
    for row, title, (name, party) in zip(rows, ROW_TITLES, CHOICES):
        require(set(row) == {"contest_literal", "candidate_or_measure_literal", "party_literal",
                             "votes", "printed_pct"}, "Changed native query schema")
        require((row["contest_literal"], row["candidate_or_measure_literal"], row["party_literal"])
                == (title, name, party), "Changed native contest, candidate or literal party")
        require(type(row["votes"]) is int and row["votes"] >= 0, "Invalid native vote count")
        require(bool(re.fullmatch(r"\d+(?:\.\d)?%", row["printed_pct"])),
                "Changed native percentage format")
        groups.setdefault(title, []).append(row)
    require(rows[0]["votes"] == 11105 and rows[1]["votes"] == 5,
            "Changed native total or blank ballots")
    for title, group in groups.items():
        total = sum(row["votes"] for row in group)
        require(0 < total <= 11105, "Invalid candidate sum")
        for row in group:
            calculated = (Decimal(100) * row["votes"] / total).quantize(
                Decimal(".1"), rounding=ROUND_HALF_UP)
            require(calculated == Decimal(row["printed_pct"][:-1]),
                    "Printed candidate fraction disagrees")
    return groups


def csv_bytes(rows):
    require(bool(rows), "Cannot export an empty query table")
    target = io.StringIO(newline="")
    writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return target.getvalue().encode()


def tables(records):
    groups = validate(records)
    rows = records["native_rows"]
    candidates = [dict(year=2026, state_code="PA", county="Greene", **row,
                       kind="write_in_total" if row["candidate_or_measure_literal"] == "WRITE-IN"
                       else "candidate") for row in rows[2:]]
    accounting = [dict(
        year=2026, state_code="PA", county="Greene", contest_literal=title,
        vote_for="", derived_candidate_sum=sum(row["votes"] for row in group),
        native_ballots=11105, unclassified_ballot_minus_candidate_sum=11105-sum(row["votes"] for row in group),
        qualifications="Candidate sum is derived, not an administrative ballot measure; residual is unclassified.")
        for title, group in list(groups.items())[2:]]
    parties = []
    for title, group in list(groups.items())[2:]:
        totals = Counter()
        for row in group:
            totals[row["party_literal"]] += row["votes"]
        parties.extend(dict(year=2026, state_code="PA", county="Greene",
                            contest_literal=title, party_literal=party, votes=votes,
                            scope="candidate_choice_votes_not_party_participation")
                       for party, votes in totals.items())
    return {
        "native-summary-query.csv": rows,
        "county-candidate-results.csv": candidates,
        "county-contest-accounting.csv": accounting,
        "county-literal-party-totals.csv": parties,
        "county-participation.csv": [dict(
            year=2026, state_code="PA", county="Greene",
            native_participation_measure_literal="Ballots Cast - Total",
            ballots_cast=11105, blank_ballots=5, registered_voters="",
            native_printed_turnout="", registered_turnout_pct="",
            source_status_literal=records["native_header"][3], source_update_literal="",
            declared_timezone="", reported_precincts=42, total_precincts=42,
            native_reporting_percent="", counting_complete=False, source_fips="", maps_approved=False)],
        "native-reporting-statistics.csv": [dict(
            native_header_ordinal=index, native_header_literal=literal)
            for index, literal in enumerate(records["native_header"], 1)],
        "native-source-declarations.csv": records["source_declarations"],
        "source-receipts.csv": records["source_receipts"],
    }


def reproduce(folder):
    records = json.loads(gzip.decompress((folder / "source-records.json.gz").read_bytes()))
    exported = {name: csv_bytes(rows) for name, rows in tables(records).items()}
    exported["audit.json"] = json_bytes(dict(
        county="Greene", year=2026, source_summary_rows=15, administrative_measure_rows=2,
        candidate_choice_rows=13, candidate_contests=4, ballots_cast=11105, blank_ballots=5,
        native_registered_voters=None, turnout_rate=None, native_report_update_literal="",
        native_declared_timezone="", counting_complete=False, maps_approved=False,
        original_html_redistributed=False, native_query_complete=True,
        qualifications=[
            "The complete factual county summary is reproduced, not the original HTML template.",
            "Blank ballots are retained separately and are not added to total ballots.",
            "No registration denominator, turnout rate, timezone or report-update clock is inferred.",
            "42 of 42 reporting is not completed counting or certification.",
            "Administrative pseudo-party labels are excluded from candidate-party tables.",
            "Candidate-party choices are not voter participation by party.",
            "Ballot-minus-candidate residuals are unclassified; legislative scopes are not extrapolated.",
            "No exact election geometry, demographic turnout or nationwide completion is approved."]))
    exported.update({name: (folder / name).read_bytes() for name in (
        "source-records.json.gz", "review-greene-county-native-query.py", "test-greene-native-query.py")})
    exported["checksums.json"] = json_bytes([
        dict(file=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        for name, data in sorted(exported.items())])
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(exported.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compresslevel=9)
    exported[ARCHIVE] = target.getvalue()
    return exported


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    folder = Path(__file__).parent
    expected = reproduce(folder)
    for name, data in expected.items():
        if args.write:
            (folder / name).write_bytes(data)
        require((folder / name).read_bytes() == data, "Changed complete output: " + name)
    print(f"All {len(expected)} entire files reproduce, including the complete archive.")
