"""Reconcile 2022 Wyoming native workbooks and the separately acquired precinct CSV."""

import argparse
import collections
import csv
from datetime import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile

import openpyxl


CATEGORIES = ["Harriet Hageman (R)", "Lynnette GreyBull (D)", "Richard Brubaker (L)",
              "Marissa Joy Selvig (C)", "Write-Ins", "Overvotes", "Undervotes"]
CSV_CATEGORIES = ["Harriet Hageman", "Lynnette GreyBull", "Richard Brubaker",
                  "Marissa Joy Selvig", "Write-ins", "Over Votes", "Under Votes"]
BOOKS = ["2022_General_County_PbP.xlsx", "2022_General_County_PbP_TBC.xlsx",
         "2022_General_Summaries_Results.xlsx"]
ZIP_NAME = "2022/2022_Wyoming_General_Results.zip"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verified(path, receipt, compressed=False):
    raw = path.read_bytes()
    if compressed:
        raw = gzip.decompress(raw)
    require(len(raw) == receipt["bytes"] and hashlib.sha256(raw).hexdigest() == receipt["sha256"],
            "Source hash mismatch: " + str(path))
    return raw


def native_label(cell):
    label = cell.value
    if isinstance(label, datetime):
        require(cell.number_format in {"mm-dd", "m-d"} and label.year == 2022
                and label.hour == label.minute == label.second == label.microsecond == 0,
                "Unreviewed native Excel precinct date/format")
        display = label.strftime("%m-%d") if cell.number_format == "mm-dd" else f"{label.month}-{label.day}"
        return display, dict(acquired_csv_literal=str(label), native_excel_format=cell.number_format,
                             displayed_precinct=display)
    require(isinstance(label, str) and label.strip() == label and label, "Invalid native precinct label")
    return label, None


def table(sheet, house):
    width, header = (8, 4) if house else (2, 3)
    cells = list(sheet.iter_rows(max_col=width))
    require(len(cells) > header and "November8,2022" in "".join(str(cells[0][1].value).split()),
            "Wrong native election")
    if house:
        require(cells[2][1].value == "United States Representative"
                and [" ".join(str(c.value).split()) for c in cells[header - 1][1:]] == CATEGORIES,
                "Unexpected native House categories")
    else:
        require(cells[header - 1][1].value == "Total Ballots Cast", "Wrong native ballot table")
    found, crosswalk, continuations = {}, {}, 0
    for ordinal, row in enumerate(cells[header:], header + 1):
        if row[0].value is None:
            require(all(c.value is None for c in row), "Unlabeled native data row")
            continue
        if row[0].value == "Precincts Continue\non Next Page" and all(c.value is None for c in row[1:]):
            continuations += 1
            continue
        values = [c.value for c in row[1:]]
        require(all(isinstance(v, (int, float)) and not isinstance(v, bool)
                    and v >= 0 and v == int(v) for v in values), "Invalid native count")
        values = list(map(int, values))
        if row[0].value == "Total":
            require(found, "Empty native table")
            return found, values, crosswalk, continuations
        label, review = native_label(row[0])
        require(label not in found, "Duplicate native precinct")
        found[label] = dict(values=values, row=ordinal)
        if review:
            crosswalk[review["acquired_csv_literal"]] = review
    raise ValueError("Missing native printed total")


def reconcile(source, acquired):
    sources = json.loads((source / "sources.json").read_text())
    raw = verified(source / "originals" / (ZIP_NAME + ".gz"), sources[ZIP_NAME], True)
    csv_receipt = json.loads((acquired / "acquisition.json").read_text())["states"]["WY"]
    csv_raw = verified(acquired / "WY.csv.gz", csv_receipt, True)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(len(archive.namelist()) == 3 and set(archive.namelist()) == set(BOOKS)
                and archive.testzip() is None, "Incomplete native workbook archive")
        books = [openpyxl.load_workbook(io.BytesIO(archive.read(name)), read_only=True, data_only=True)
                 for name in BOOKS]
    try:
        candidates, ballots, summary = books
        state, state_vector, _, _ = table(summary["Statewide Candidates"], True)
        state_ballots, state_total, _, _ = table(summary["Statewide Total Ballots Cast"], False)
        require(len(state) == 23 and set(candidates.sheetnames) == set(ballots.sheetnames)
                == set(state) == set(state_ballots), "Incomplete county/summary identity set")
        require([sum(item["values"][i] for item in state.values()) for i in range(7)] == state_vector
                and sum(item["values"][0] for item in state_ballots.values()) == state_total[0]
                == sum(state_vector), "Statewide printed totals differ")
        rows, crosswalk, conflicts, county_reviews, continuations = [], {}, [], [], 0
        for county in candidates.sheetnames:
            units, vector, candidate_ids, n = table(candidates[county], True)
            cast, printed, ballot_ids, m = table(ballots[county], False)
            continuations += n + m
            require(units.keys() == cast.keys(), county + " native precinct identity mismatch")
            require([sum(unit["values"][i] for unit in units.values()) for i in range(7)]
                    == vector == state[county]["values"], county + " candidate totals differ")
            precinct_sum = sum(unit["values"][0] for unit in cast.values())
            require(precinct_sum == state_ballots[county]["values"][0] == sum(vector),
                    county + " precinct/state ballot totals differ")
            if printed[0] != precinct_sum:
                conflicts.append(dict(county=county, precinct_sum=precinct_sum,
                    printed_county_total=printed[0], statewide_county_value=state_ballots[county]["values"][0]))
            county_reviews.append(dict(county=county, precincts=len(units), category_vector=vector,
                precinct_ballots=precinct_sum, printed_county_ballots=printed[0],
                statewide_ballots=state_ballots[county]["values"][0]))
            for index, identities in enumerate([candidate_ids, ballot_ids]):
                for literal, review in identities.items():
                    entry = crosswalk.setdefault((county, literal),
                        dict(county=county, **review, native_workbook_occurrences=[]))
                    require(entry["displayed_precinct"] == review["displayed_precinct"],
                            "Ambiguous date-coerced CSV precinct identity")
                    entry["native_workbook_occurrences"].append(dict(workbook=BOOKS[index],
                        sheet=county, native_excel_format=review["native_excel_format"],
                        row=(units if index == 0 else cast)[review["displayed_precinct"]]["row"]))
            for precinct, unit in units.items():
                require(sum(unit["values"]) == cast[precinct]["values"][0],
                        county + " precinct House categories differ from separate ballots")
                rows.append(dict(year=2022, state_code="WY", county=county, precinct=precinct,
                    **dict(zip(CATEGORIES, unit["values"])), ballots=cast[precinct]["values"][0],
                    registered_voters=None, turnout_rate=None,
                    printed_county_ballot_total_reconciled=printed[0] == precinct_sum,
                    source_zip=ZIP_NAME, source_zip_sha256=sources[ZIP_NAME]["sha256"],
                    candidate_workbook=BOOKS[0], ballot_workbook=BOOKS[1], sheet=county,
                    candidate_row=unit["row"], ballot_row=cast[precinct]["row"]))
        derived, derived_ballots = collections.defaultdict(dict), {}
        for item in csv.DictReader(io.StringIO(csv_raw.decode("utf-8-sig"))):
            key = (item["county"], item["precinct"])
            key = (key[0], crosswalk[key]["displayed_precinct"]) if key in crosswalk else key
            if item["office"] == "U.S. House":
                require(item["candidate"] not in derived[key], "Duplicate acquired CSV candidate")
                derived[key][item["candidate"]] = int(item["votes"])
            elif item["office"] == "Ballots Cast":
                require(key not in derived_ballots, "Duplicate acquired CSV ballots")
                derived_ballots[key] = int(item["votes"])
        native = {(r["county"], r["precinct"]): dict(zip(CSV_CATEGORIES, [r[c] for c in CATEGORIES]))
                  for r in rows}
        require(dict(derived) == native and derived_ballots ==
                {(r["county"], r["precinct"]): r["ballots"] for r in rows},
                "Acquired CSV differs from independent native cells")
        result = dict(state_code="WY", year=2022, units=len(rows), counties=county_reviews,
            category_labels=CATEGORIES, statewide_category_vector=state_vector,
            statewide_ballots=state_total[0], candidate_write_in_votes=sum(state_vector[:5]),
            independently_checked_house_cells=7 * len(rows), independently_checked_ballot_cells=len(rows),
            all_acquired_csv_house_and_ballot_cells_match=True,
            explicit_non_count_continuation_markers=continuations,
            native_display_crosswalk=[crosswalk[k] for k in sorted(crosswalk)],
            printed_ballot_conflicts=conflicts, maps_approved=False, geometry_approved=False,
            turnout_rates_available=False, ballot_approval="withheld" if conflicts else "counts_only",
            party_note="Native Selvig (C) and acquired CSV CTRY remain distinct literal labels; no alias inferred.",
            method="Native workbook election/office/category headers, exact cell values and Excel display "
                   "formats independently reconcile acquired CSV cells. Printed ballot conflicts remain "
                   "unrepaired; no geographic allocation or registered denominator is inferred.")
        return result, rows
    finally:
        for book in books:
            book.close()


def build_review(source, acquired, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing immutable review overwrite")
    result, rows = reconcile(source, acquired)
    sources = {k: v for k, v in json.loads((source / "sources.json").read_text()).items()
               if k.startswith("2022/")}
    for name, receipt in sources.items():
        verified(source / "originals" / (name + ".gz"), receipt, True)
    csv_checks = json.loads((acquired / "checksums.json").read_text())
    for name in ["WY.csv.gz", "WY-README.md"]:
        verified(acquired / name, csv_checks[name])
    output.mkdir(parents=True)
    package = output / "source-package"
    (package / "originals").mkdir(parents=True)
    shutil.copytree(source / "originals/2022", package / "originals/2022")
    (package / "sources.json").write_text(json.dumps(sources, separators=(",", ":")))
    csv_package = output / "acquired-csv"
    csv_package.mkdir()
    for name in ["WY.csv.gz", "WY-README.md", "acquisition.json", "checksums.json"]:
        shutil.copyfile(acquired / name, csv_package / name)
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output / "counts-review.json").write_text(json.dumps(result, indent=2) + "\n")
    with (output / "precinct-counts.csv").open("w") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output / "checksums.json").write_text(json.dumps({
        path.relative_to(output).as_posix(): dict(bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(output.rglob("*")) if path.is_file()
    }, separators=(",", ":")))
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as target:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                item = zipfile.ZipInfo(path.relative_to(output).as_posix())
                item.external_attr = 0o644 << 16
                target.writestr(item, path.read_bytes())
    return dict(units=result["units"], printed_ballot_conflicts=result["printed_ballot_conflicts"],
        archive_bytes=archive.stat().st_size, archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["source", "acquired", "output", "archive"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_review(args.source, args.acquired, args.output, args.archive), indent=2))
