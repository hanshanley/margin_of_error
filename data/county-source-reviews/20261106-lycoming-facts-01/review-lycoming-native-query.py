"""Reproduce Lycoming's complete reviewed county query without redistributing source PDFs."""

import argparse
import csv
from decimal import Decimal, ROUND_HALF_UP
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.parse import unquote
import zipfile


REVIEWED_INPUT_SHA256 = "e4ddf7e6e63e0ddcadd9670fcd1e8218ea656dc4f1966278fb402611e1557004"
ARCHIVE = "complete-lycoming-county-native-query-01.zip"
SCOPES = (
    ("Governor and Lieutenant Governor", 73009, "55.58", (
        "Josh Shapiro", "Stacy Garrity", "Ken Krawchuk", "Write-in")),
    ("Representative in Congress (9th District)", 45774, "53.88", (
        "Rachel Wallace", "Dan Meuser", "Write-in")),
    ("Representative in Congress (15th District)", 27235, "58.51", (
        "Ray Bilger", "Glenn GT Thompson", "Write-in")),
    ("Representative in the General Assembly (83rd District)", 33076, "52.01", (
        "Jamie L. Flick", "Write-in")),
    ("Representative in the General Assembly (84th District)", 39933, "58.54", (
        "Joe Hamm", "Write-in")),
    ("Wolf Ballot Question", 2187, "56.06", ("Yes", "No")),
)
SOURCE_IDENTITIES = (
    ("county-parent.html", 86806, "b3492112412b00db69417b5847a1cbdc7bfaf1a37983e6e29b9db26cc432a096"),
    ("results.pdf", 8607, "0c302b5f01aa3b37fa1afd4229fdeae66f7df3b09d0c90d1653ac4bda0434145"),
    ("act88.pdf", 177029, "2edf92f9c36d77bacb7488016dcb910ff9aea2a8456fd984196f22830db4290f"),
    ("reporting-information.pdf", 267162, "5e68b2b9a0b77a700083d3e8e9f3de3b322b5a74eeea11b0326535029fbd7cd9"),
    ("return-board.pdf", 264396, "495a355d97f55a5385884fc804bd58be8bc08ed4a22e59d9e6c438a59a5ef559"),
)
SOURCE_PATHS = (
    "government/departments/voter_services/index.php",
    "Documents/Government/Departments/Voter Services/ElectionResults.pdf?t=202611051110360",
    "Documents/Government/Departments/Voter Services/2026GEAct88.pdf?t=202611032152120",
    "Documents/Government/Departments/Voter Services/2026GEENR.pdf?t=202611032155320",
    "Documents/Government/Departments/Voter Services/2026GEReturnBoard.pdf?t=202610201416150",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def percent(count, total):
    return (Decimal(100) * count / total).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


def validate(records, check_pinned=True):
    if check_pinned:
        require(hashlib.sha256(json_bytes(records)).hexdigest() == REVIEWED_INPUT_SHA256,
                "Changed complete reviewed factual input")
    require((records["schema_version"], records["year"], records["state_code"], records["county"])
            == (1, 2026, "PA", "Lycoming"), "Changed election identity")
    report = records["native_report"]
    require(report == records["independent_native_report"], "Independent report observations differ")
    require((report["election_literal"], report["county_literal"], report["status_literal"])
            == ("November 3, 2026 General Election", "Lycoming County", "Unofficial Results"),
            "Changed native election or status")
    require((report["source_update_literal"], report["declared_timezone"], report["source_fips"])
            == ("2026-11-05 10:37:43", "", ""), "Changed native clock, timezone or FIPS")
    require(report["scope_literal"] ==
            "All Precincts, All Districts, All Counter Groups, All ScanStations, All Contests, All Boxes",
            "Changed native reporting scope")
    require((report["ballots_cast"], report["registered_voters"], report["native_overall_turnout_pct"])
            == (40596, 73009, "55.60"), "Changed native overall participation")
    require(percent(report["ballots_cast"], report["registered_voters"]) ==
            Decimal(report["native_overall_turnout_pct"]), "Native overall fraction disagrees")
    require((report["reported_precincts"], report["total_precincts"]) == (80, 80),
            "Changed native reporting counts")
    require(report["counter_groups"] == ["ED", "MI", "PR"], "Changed native candidate-counter labels")
    require(report["county_ballot_modes"] is None and report["blank_ballots"] is None,
            "Inferred county ballot modes or blank ballots")
    require(report["counting_complete"] is False and report["maps_approved"] is False,
            "Invented completion or map approval")
    require(len(records["source_receipts"]) == 5, "Incomplete original receipts")
    for row, identity, path in zip(records["source_receipts"], SOURCE_IDENTITIES, SOURCE_PATHS):
        require((row["file"], row["bytes"], row["sha256"]) == identity, "Changed original full-byte receipt")
        require(row["url"] == "https://lycomingcountypa.gov/" + path and
                unquote(row["final_url"]) == row["url"] and row["status"] == 200,
                "Changed native source URL or status")
        require(bool(re.fullmatch(r"2026-11-06T12:10:\d\d\.\d+\+00:00", row["fetched_at_utc"])),
                "Changed separate retrieval clock")
    declarations = records["source_declarations"]
    require(len(declarations) == 4 and [row["url"] for row in declarations] ==
            [row["url"] for row in records["source_receipts"][1:]], "Changed county-parent declarations")
    require([row["label"] for row in declarations] == [
        "Unofficial Results", "Act 88 Reporting Notice", "Election Night Reporting Information",
        "Notice of Meetings of County Return Board"], "Changed native declaration labels")
    require(len(records["source_pages"]) == 4 and all(
        row == dict(file=identity[0], pages=1, sha256=identity[2])
        for row, identity in zip(records["source_pages"], SOURCE_IDENTITIES[1:])),
        "Incomplete native source pages")
    require(records["mail_receipt"] == dict(
        native_measure="absentee and mail-in ballots received", count=5770,
        cutoff_literal="8:00pm on Election Day", source_file="act88.pdf", added_to_ballots=False),
        "Mail receipts are not counted ballots")
    require([row["kind"] for row in records["counting_qualifications"]] == [
        "incomplete_unofficial_count", "scheduled_canvass_not_completed", "native_calendar_label_conflict"],
        "Lost counting qualifications or native calendar conflict")
    require(len(report["contests"]) == len(SCOPES), "Incomplete contest scopes")
    for contest, (title, electorate, turnout, choices) in zip(report["contests"], SCOPES):
        require((contest["title_literal"], contest["vote_for"], contest["registered_voters"],
                 contest["native_turnout_pct"]) == (title, 1, electorate, turnout),
                "Changed native contest scope or unspecified-numerator turnout")
        require([row["choice_literal"] for row in contest["choices"]] == list(choices),
                "Incomplete or harmonized native choices")
        require(contest["total"]["choice_literal"] == "Total" and
                contest["total"]["printed_pct"] == "100.00", "Changed native total")
        for row in contest["choices"] + [contest["total"]]:
            require(set(row) == {"choice_literal", "votes", "printed_pct", "ED", "MI", "PR", "party_literal"},
                    "Changed native choice schema")
            require(row["party_literal"] == "", "Inferred native candidate party")
            require(all(type(row[key]) is int and row[key] >= 0 for key in ("votes", "ED", "MI", "PR")),
                    "Invalid candidate count")
            require(row["votes"] == sum(row[key] for key in ("ED", "MI", "PR")),
                    "Candidate-counter sum disagrees")
            require(bool(re.fullmatch(r"\d+\.\d\d", row["printed_pct"])), "Invalid printed choice fraction")
            require(percent(row["votes"], contest["total"]["votes"]) == Decimal(row["printed_pct"]),
                    "Printed choice fraction disagrees")
        for field in ("votes", "ED", "MI", "PR"):
            require(sum(row[field] for row in contest["choices"]) == contest["total"][field],
                    "Complete choice sum disagrees with native total")
    return report


def csv_bytes(rows):
    require(bool(rows), "Cannot export an empty factual query table")
    target = io.StringIO(newline="")
    writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return target.getvalue().encode()


def tables(records):
    report = validate(records)
    common = dict(year=2026, state_code="PA", county="Lycoming")
    choices, modes, totals, scopes, rates = [], [], [], [], []
    for index, contest in enumerate(report["contests"], 1):
        scope = dict(**common, contest_ordinal=index, contest_literal=contest["title_literal"])
        scopes.append(dict(**scope, vote_for=contest["vote_for"],
                           registered_voters=contest["registered_voters"],
                           native_turnout_pct=contest["native_turnout_pct"],
                           turnout_numerator="unspecified_not_inferred_from_candidate_votes"))
        for row in contest["choices"]:
            kind = ("ballot_question_choice" if index == 6 else
                    "write_in_total" if row["choice_literal"] == "Write-in" else "named_candidate")
            choices.append(dict(**scope, kind=kind, **row))
            modes.extend(dict(**scope, choice_literal=row["choice_literal"],
                              counter_group_literal=mode, votes=row[mode],
                              measure="candidate_or_choice_votes_not_ballot_participation")
                         for mode in report["counter_groups"])
            rates.append(dict(**scope, choice_literal=row["choice_literal"],
                              native_printed_pct=row["printed_pct"],
                              calculated_choice_pct=str(percent(row["votes"], contest["total"]["votes"])),
                              denominator="native_contest_choice_total_not_registered_voters"))
        totals.append(dict(
            **scope, **contest["total"], derived_choice_sum=sum(row["votes"] for row in contest["choices"]),
            county_ballots_comparable=index == 1,
            unclassified_county_ballot_minus_choice_total=40596-contest["total"]["votes"] if index == 1 else "",
            qualifications="Native choice totals are not ballots; district/question counts have no approved county-ballot comparator."))
    return {
        "county-participation.csv": [dict(
            **common, native_measure_literal="Total Ballots Cast", ballots_cast=40596,
            registered_voters=73009, native_printed_turnout_pct="55.60",
            calculated_registered_turnout_pct=str(percent(40596, 73009)),
            blank_ballots="", county_ballot_modes="", native_status_literal="Unofficial Results",
            source_update_literal=report["source_update_literal"], declared_timezone="", source_fips="",
            reported_precincts=80, total_precincts=80, counting_complete=False, maps_approved=False)],
        "native-candidate-results.csv": choices,
        "native-candidate-mode-results.csv": modes,
        "native-contests.csv": scopes,
        "native-contest-totals.csv": totals,
        "native-choice-rate-checks.csv": rates,
        "native-mail-ballot-receipts.csv": [dict(**common, **records["mail_receipt"])],
        "native-counting-qualifications.csv": records["counting_qualifications"],
        "native-source-declarations.csv": records["source_declarations"],
        "native-source-pages.csv": records["source_pages"],
        "source-receipts.csv": records["source_receipts"],
    }


def reproduce(folder):
    records = json.loads(gzip.decompress((folder / "source-records.json.gz").read_bytes()))
    exported = {name: csv_bytes(rows) for name, rows in tables(records).items()}
    exported["audit.json"] = json_bytes(dict(
        year=2026, county="Lycoming", native_contests=6, candidate_or_choice_rows=16,
        candidate_mode_cells=48, ballots_cast=40596, registered_voters=73009,
        native_turnout_pct="55.60", mail_ballot_receipts_separate=5770,
        native_parties_present=False, native_ballot_modes_present=False, native_blank_ballots_present=False,
        counting_complete=False, maps_approved=False, native_query_complete=True,
        original_html_or_pdfs_redistributed=False,
        qualifications=[
            "All six native scopes, sixteen choices, six totals and 48 candidate-mode cells are preserved.",
            "All candidate parties remain missing. Candidate votes and their counter groups are not ballot participation.",
            "Only the overall administrative registered-voter fraction is validated, not demographic or eligible-population turnout.",
            "Native per-contest turnout retains its unspecified numerator; no district ballot count is inferred.",
            "All 5770 Act88 mail receipts remain separate, not added to ballots or equated to counted mail.",
            "80/80 reporting is not completed counting or certification. Source timezone, FIPS and blank ballots are missing.",
            "Scheduled canvass and the native weekday/date conflict survive without fabricated correction.",
            "No new geometry, contextual identity or explorer approval is included."]))
    exported.update({name: (folder / name).read_bytes() for name in (
        "source-records.json.gz", "review-lycoming-native-query.py", "test-lycoming-native-query.py")})
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
