"""Reproduce the complete factual Sullivan/Wyoming county query offline."""

import argparse
from collections import Counter
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import zipfile


if not __debug__:
    raise RuntimeError("Run without -O: numerical validation must remain enabled")

ROOT = Path(__file__).resolve().parent
SNAPSHOT = "20261106-sullivan-wyoming-native-turnout-01"


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def csv_bytes(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def percentage(numerator, denominator):
    return str((Decimal(numerator) * 100 / Decimal(denominator)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)) + "%"


def review(inputs):
    assert inputs["election_date"] == "2026-11-03"
    assert inputs["native_scope"] == (
        "All Precincts, All Districts, All Counter Groups, All ScanStations, All Contests, All Boxes")
    assert inputs["candidate_columns"] == ["native_choice", "Votes", "Vote %", "ED", "MI", "PR"]
    reports = inputs["reports"]
    assert [r["county"] for r in reports] == ["Sullivan", "Wyoming"]
    participation, candidates, totals, accounting, reporting, pages = [], [], [], [], [], []
    for report, expected in zip(reports, [
            (2712, 4501, "60.25%", 3, "10:36:27"),
            (10542, 18565, "56.78%", 1, "09:15:07")]):
        assert tuple(report[k] for k in (
            "total_ballots", "registered_voters", "printed_percentage", "physical_pages", "native_clock")) == expected
        ballots, registrations = report["total_ballots"], report["registered_voters"]
        assert percentage(ballots, registrations) == report["printed_percentage"]
        assert report["native_date"] == "2026-11-06" and report["native_timezone"] is None
        assert report["native_page_on_summary"] == "1 of 1"
        base = dict(state="Pennsylvania", county=report["county"], election_date="2026-11-03",
                    scope="county", physical_page=1, native_date=report["native_date"],
                    native_clock=report["native_clock"], native_timezone=None,
                    native_title=report["native_title"], native_election=report["native_election"],
                    native_status=report["native_status"],
                    source_file_status_literal=report.get("source_file_status_literal"),
                    status_printed_on_physical_page=report["status_printed_on_physical_page"])
        participation.append(dict(**base, native_ballot_label="Total Ballots Cast",
            total_ballots=ballots, native_registration_label="Registered Voters",
            registered_voters=registrations, native_printed_percentage=report["printed_percentage"],
            native_scope=inputs["native_scope"], native_mode=None, blank_ballots=None,
            overvotes=None, undervotes=None, source_fips=None,
            analysis_ballots_approved=False, analysis_rate_approved=False, map_approved=False))
        assert len(report["contests"]) == (3 if report["county"] == "Sullivan" else 4)
        assert len({c["id"] for c in report["contests"]}) == len(report["contests"])
        for contest in report["contests"]:
            assert contest["vote_for"] == 1
            assert contest["header_registered_voters"] == registrations
            assert contest["header_printed_percentage"] == report["printed_percentage"]
            rows, total = contest["choices"], contest["total"]
            assert total[0] == "Total" and sum(row[1] for row in rows) == total[1]
            assert 0 <= total[1] <= ballots
            assert len({row[0] for row in rows}) == len(rows)
            for row in rows + [total]:
                assert len(row) == 6 and all(type(v) is int and v >= 0 for v in [row[1]] + row[3:])
                assert sum(row[3:]) == row[1], (report["county"], contest["id"], row)
                assert all(row[col] <= total[col] for col in (1, 3, 4, 5))
                if row[2] is not None:
                    assert row[2] == percentage(row[1], total[1]), row
                else:
                    assert report["county"] == "Sullivan"
            for col in (1, 3, 4, 5):
                assert sum(row[col] for row in rows) == total[col]
            identity = dict(**base, contest_id=contest["id"], native_contest=contest["native_contest"])
            for row in rows:
                candidates.append(dict(**identity, native_choice=row[0], votes=row[1],
                    native_printed_percentage=row[2], ED=row[3], MI=row[4], PR=row[5],
                    native_literal_party=None, native_office_district=None))
            totals.append(dict(**identity, native_choice=total[0], votes=total[1],
                native_printed_percentage=total[2], ED=total[3], MI=total[4], PR=total[5],
                repeated_registered_voters_not_additive=contest["header_registered_voters"],
                repeated_native_percentage=contest["header_printed_percentage"],
                repeated_ballots_not_additive=contest["header_ballots"]))
            if report["county"] == "Wyoming":
                assert contest["header_ballots"] == ballots
                assert contest["overvoted_ballots"] == contest["overvotes"] == contest["footer_overvotes"]
                assert contest["undervotes"] == contest["footer_undervotes"]
                assert total[1] + contest["overvoted_ballots"] + contest["undervotes"] == ballots
                residual = 0
            else:
                assert all(contest[key] is None for key in ("header_ballots", "overvoted_ballots",
                    "overvotes", "undervotes", "footer_overvotes", "footer_undervotes"))
                residual = ballots - total[1]
            accounting.append(dict(**identity, total_ballots=ballots, native_total_votes=total[1],
                native_overvoted_ballots=contest["overvoted_ballots"], native_overvotes=contest["overvotes"],
                native_undervotes=contest["undervotes"], native_footer_overvotes=contest["footer_overvotes"],
                native_footer_undervotes=contest["footer_undervotes"], native_blank_ballots=None,
                ballots_less_selections=ballots - total[1], unclassified_residual=residual,
                native_mode_ballots=None))
        assert (report["reported_precincts"], report["total_precincts"]) == (
            (None, None) if report["county"] == "Sullivan" else (28, 28))
        reporting.append(dict(**base, reported_precincts=report["reported_precincts"],
                              total_precincts=report["total_precincts"], counting_complete=None))
        for page in range(1, report["physical_pages"] + 1):
            pages.append(dict(county=report["county"], physical_page=page,
                native_page=report["native_page_on_summary"] if page == 1 else None,
                native_title=report["native_title"] if page == 1 else None,
                native_date=report["native_date"] if page == 1 else None,
                native_clock=report["native_clock"] if page == 1 else None,
                native_timezone=None,
                native_election_label=report["native_election"] if page == 1 else (
                    "General Election November 3, 2026" if page == 2 else None),
                native_status=report["native_status"] if page == 2 else None))

    matrix = inputs["sullivan_write_in_matrix"]
    columns = matrix["columns"]
    assert len(columns) == len(set(columns)) == 15
    assert matrix["unlisted_locality_cells"] is None
    assert all(matrix[key] is None for key in ("native_date", "native_clock", "native_timezone"))
    assert [(s["physical_page"], s["summary_contest_id"], len(s["rows"])) for s in matrix["sections"]] == [
        (2, "governor", 8), (2, "congress", 8), (2, "assembly", 7), (3, "assembly", 36)]
    matrix_rows, missing, zeros = [], 0, 0
    listing = Counter()
    for section in matrix["sections"]:
        assert section["continuation"] == (section["physical_page"] == 3)
        assert (section["native_contest"] is None) == section["continuation"]
        for index, (name, cells, total) in enumerate(section["rows"], 1):
            assert set(cells) <= set(columns)
            assert all(type(v) is int and v > 0 for v in cells.values())
            assert type(total) is int and total >= 0 and sum(cells.values()) == total
            assert (name is None) == (not cells and total == 0)
            values = [cells.get(col) for col in columns] + [total]
            missing += values.count(None)
            zeros += values.count(0)
            listing[section["summary_contest_id"]] += total
            matrix_rows.append(dict(county="Sullivan", physical_page=section["physical_page"],
                section_contest_id=section["summary_contest_id"], row_in_section=index,
                native_contest=section["native_contest"], continuation=section["continuation"],
                native_choice=name, native_literal_party=None,
                **{col: cells.get(col) for col in columns}, TOTALS=total))
    assert listing == {"governor": 1, "congress": 1, "assembly": 48}
    assert missing == 841 and zeros == 16
    reconciliation = []
    for contest in reports[0]["contests"]:
        write_ins = [row[1] for row in contest["choices"] if row[0] == "Write-in"]
        assert len(write_ins) == 1
        reconciliation.append(dict(county="Sullivan", contest_id=contest["id"],
            native_summary_contest=contest["native_contest"], summary_write_ins=write_ins[0],
            listed_write_ins=listing[contest["id"]],
            summary_less_listing_unallocated=write_ins[0] - listing[contest["id"]],
            listing_completeness_approved=False,
            scope_note="Summary district is unprinted; listing districts remain separately scoped. Do not repair either source or allocate missing write-ins."))
    return {
        "county-participation.csv": participation,
        "candidate-results.csv": candidates,
        "contest-totals.csv": totals,
        "contest-accounting.csv": accounting,
        "reporting.csv": reporting,
        "source-pages.csv": pages,
        "write-in-matrix.csv": matrix_rows,
        "write-in-reconciliation.csv": reconciliation,
    }


def build(output):
    inputs = json.loads((ROOT / "source-inputs.json").read_text())
    datasets = review(inputs)
    provenance = json.loads((ROOT / "source-provenance.json").read_text())
    assert [row["county"] for row in provenance] == ["sullivan", "wyoming"]
    for row, expected in zip(provenance, [
            (483343, "b0bb2c4d4c16183237ff898d5aff42ff3ec4e844a26be7b6e9e3dbc74c02c2b5", 3),
            (257897, "37a98318288b3f264c3354cff9798cb7baf3dc3e897a86d0d4f6968cb0721c1c", 1)]):
        assert (row["source"]["bytes"], row["source"]["sha256"], row["pages"]) == expected
        assert row["declared_link"]["url"] == row["source"]["source_url"]
        assert row["source"]["status"] == row["parent"]["status"] == 200
        assert row["source"]["verified_tls"] and row["parent"]["verified_tls"]
    counts = {name: len(rows) for name, rows in datasets.items()}
    assert list(counts.values()) == [2, 22, 7, 7, 2, 4, 59, 3]
    methods = dict(snapshot=SNAPSHOT, election_date="2026-11-03",
        scope="Complete native numerical query; no analysis, rate, geographic identity or map approval yet.",
        native_ballots="Total Ballots Cast; registered-voter fractions, not candidate votes, CVAP/VAP/VEP or demographic participation.",
        reporting="Wyoming 28/28 reporting is not certification or completed counting. Sullivan reporting is missing, not inferred from 15 listing columns.",
        modes="ED / MI / PR are literal candidate-vote columns without an expanded native key; not ballot-mode counts. Totals and repeated contest denominators are not additive.",
        parties="No party labels are printed. Every affiliation remains missing; no party totals or cross-source identities are manufactured.",
        clocks="November 6 summary clocks have no native timezone. The write-in listing prints an election date, not an update date; it receives no invented summary clock.",
        status="Sullivan UNOFFICIAL Election Results is printed on physical page 2, not page 1. Wyoming unofficial status comes from the declared file name, not a printed PDF status.",
        accounting="Sullivan differences 41/32/396 are unclassified, not undervotes. Wyoming native over-voted ballots plus undervotes reconcile each contest; do not double count overvotes. Blank ballots remain missing.",
        write_ins="All 59 rows and 944 locality/total cells retained: 841 blanks are missing, 16 printed zeros are numeric zero. Named listings 1/1/48 differ from summary write-ins 1/5/73; gaps 0/4/25 are unallocated, not additional voters. Page 3 continues the Assembly table; absent native headers remain missing.",
        percentages="Native strings retained and verified with Decimal ROUND_HALF_UP. Sullivan candidate percentages are absent; never replace with derived shares.",
        geography="Native FIPS and summary office districts are missing. Listing districts 9th/84th remain separately scoped. No geography or precinct coverage is approved.",
        source_originals=inputs["transcription_basis"],
        reproduction="python3 -I review-counties.py --output /new/empty/directory",
        tests="python3 -I test_review_counties.py")
    audit = dict(row_counts=counts, physical_pages_reviewed=4, full_write_in_matrix_cells=944,
        missing_matrix_cells=841, printed_zero_matrix_cells=16,
        complete_independent_ocr_equality_claimed=False,
        native_candidate_mode_vectors_reconcile=True, repeated_denominators_checked_not_summed=True,
        native_source_receipts=provenance, analysis_ballots_approved=False,
        analysis_rate_approved=False, map_approved=False)
    files = {name: csv_bytes(rows) for name, rows in datasets.items()}
    files.update({"methods.json": json_bytes(methods), "audit.json": json_bytes(audit)})
    for name in ("source-inputs.json", "source-provenance.json", "review-counties.py", "test_review_counties.py"):
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
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    assert output.resolve() == ROOT or not any(output.iterdir()), "Reproduction output must be empty"
    for name, body in files.items():
        (output / name).write_bytes(body)
    print(json.dumps(dict(files=len(files), zip_members=len(files) - 1, rows=counts,
        zip_bytes=len(files["complete-query.zip"]),
        zip_sha256=hashlib.sha256(files["complete-query.zip"]).hexdigest()), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)
