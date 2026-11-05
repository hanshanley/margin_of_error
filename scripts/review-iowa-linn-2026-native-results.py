"""Reconcile Linn County's native 2026 precinct ballots and separate House votes."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import zipfile


HOUSE = "United States Representative District 2"
OPTIONS = ["REP Joe Mitchell", "DEM Lindsay James", "LIB Rick Stewart",
           "Dave Bushaw", "Write-In Totals"]
MODES = ["total", "election_day", "absentee"]
ORIGINALS = {
    "linn-2026-general-summary.pdf": (
        "https://gis.linncountyiowa.gov/web-data/elections/year/2026/20261103GE/sum.pdf",
        "a2d194adfef5761933857f2b57e719297d793b41d54dfd53e2f68015b800572d"),
    "linn-2026-general-precinct.pdf": (
        "https://gis.linncountyiowa.gov/web-data/elections/year/2026/20261103GE/pct.pdf",
        "f9c01726731a42b144006c635fc5e99a105fb7c6521c6d8626f7579dc8ca5504"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(bool(re.fullmatch(r"(?:[0-9]+|[1-9][0-9]{0,2}(?:,[0-9]{3})+)", value)),
            "Missing or malformed native integer")
    return int(value.replace(",", ""))


def cells(words, box, contest=False):
    edges = [198, 278, 318] if contest else [198, 238, 278]
    same = [word for word in words if word[0] > 150
            and abs((word[1] + word[3] - box[1] - box[3]) / 2) < 3.5]
    values = [None] * 3
    percent = None
    for word in same:
        if contest and abs(word[2] - 238) < .2:
            require(percent is None and bool(re.fullmatch(r"[0-9]+\.[0-9]{2}%", word[4])),
                    "Duplicate or malformed native percentage column")
            percent = word[4]
            continue
        columns = [index for index, edge in enumerate(edges) if abs(word[2] - edge) < .2]
        require(len(columns) == 1, "Unreviewed native numeric position")
        index = columns[0]
        require(values[index] is None, "Duplicate native numeric column")
        values[index] = number(word[4])
    return values, percent


def row(page, label, low=0, high=float("inf"), contest=False):
    boxes = [box for box in page.search_for(label) if box.y0 > low and box.y1 < high]
    require(len(boxes) == 1, "Missing or ambiguous native row: " + label)
    return cells(page.get_text("words"), boxes[0], contest)


def vector(values, description):
    require(None not in values and values[0] == sum(values[1:]),
            "Missing or inconsistent " + description + " modes")


def read_pdf(raw, summary=False):
    import fitz

    participation, house, names = [], [], []
    current = None
    with fitz.open(stream=raw, filetype="pdf") as document:
        require(len(document) == (10 if summary else 511), "Unexpected complete native page count")
        for ordinal, page in enumerate(document, 1):
            text = page.get_text()
            require(all(label in text for label in [
                "UNOFFICIAL RESULTS", "November 3, 2026 - General Election",
                "County of Linn, State of Iowa",
                "Election Summary Report" if summary else "Precinct Results Report",
            ]), "Unreviewed native election identity")
            footer = re.findall(r"\bPage ([0-9]+) of\b", text)
            require(footer == [str(ordinal)], "Missing or reordered native page footer")
            name = "Linn County" if summary else text.split("\nUNOFFICIAL RESULTS\n")[0]
            require(bool(name) and "\n" not in name, "Ambiguous literal native precinct identity")
            if "\nStatistics\n" in text:
                require(name not in names, "Duplicate native precinct statistics")
                names.append(name)
                current = name
                registered, _ = row(page, "Registered Voters - Total")
                ballots, _ = row(page, "Ballots Cast - Total")
                blank, _ = row(page, "Ballots Cast - Blank")
                require(registered[0] is not None and registered[1:] == [None, None],
                        "Unreviewed native registration columns")
                vector(ballots, "ballot")
                vector(blank, "blank-ballot")
                require(all(a <= b for a, b in zip(blank, ballots)), "Blank ballots exceed ballots")
                percentages = re.findall(r"Voter Turnout - Total\n([0-9]+\.[0-9]{2})%", text)
                require(len(percentages) == 1 and registered[0] > 0
                        and ballots[0] <= registered[0]
                        and math.isclose(float(percentages[0]), 100 * ballots[0] / registered[0],
                                         rel_tol=0, abs_tol=.005000001),
                        "Printed native registered-voter rate differs")
                participation.append(dict(unit=name, page=ordinal, registered=registered,
                    ballots=ballots, blank=blank, printed_turnout_percent=percentages[0]))
            require(current == name, "Orphan or reordered native precinct section")
            titles = page.search_for(HOUSE)
            if not titles:
                continue
            require(len(titles) == 1 and name not in {record["unit"] for record in house},
                    "Duplicate native House section")
            endings = [box for box in page.search_for("Total Votes Cast") if box.y0 > titles[0].y1]
            require(bool(endings), "Missing native House total")
            end = min(endings, key=lambda box: box.y0)
            left = sorted((word for word in page.get_text("words")
                           if word[0] < 150 and word[1] > titles[0].y1 and word[1] <= end.y1),
                          key=lambda word: (word[1], word[0]))
            labels = []
            for word in left:
                if not labels or abs(word[1] - labels[-1][0]) >= 1:
                    labels.append((word[1], [word]))
                else:
                    labels[-1][1].append(word)
            require([" ".join(word[4] for word in group) for _, group in labels]
                    == ["Vote For 1"] + OPTIONS + ["Total Votes Cast"],
                    "Unreviewed complete native House option inventory")
            options = {}
            for label in OPTIONS:
                values, percent = row(page, label, titles[0].y1, end.y0, contest=True)
                vector(values, "House candidate")
                require(percent is not None, "Missing native printed House percentage")
                options[label] = dict(counts=values, printed_vote_percent=percent)
            total, percent = cells(page.get_text("words"), end, contest=True)
            vector(total, "House total")
            require(percent is not None and
                    [sum(option["counts"][index] for option in options.values()) for index in range(3)] == total,
                    "Native House option sums differ from printed total")
            require(all(a <= b for a, b in zip(total, participation[-1]["ballots"])),
                    "House votes exceed same-unit same-mode ballots")
            house.append(dict(unit=name, page=ordinal, options=options, total=total))
    require(len(participation) == len(house) > 0
            and [record["unit"] for record in participation] == [record["unit"] for record in house],
            "Incomplete native participation/House unit inventory")
    return participation, house


def reconcile(summary, detail):
    county, county_house = summary
    precincts, precinct_house = detail
    require(len(county) == len(county_house) == 1, "Unexpected county summary inventory")
    identities = [record["unit"] for record in precincts]
    require(len(set(identities)) == len(identities) == len(precinct_house) > 0
            and identities == [record["unit"] for record in precinct_house],
            "Duplicate or incomplete native precinct inventory")
    for field in ("registered", "ballots", "blank"):
        expected = county[0][field]
        for index in range(3):
            actual = [record[field][index] for record in precincts]
            require((expected[index] is None and all(value is None for value in actual))
                    or (expected[index] is not None and None not in actual and sum(actual) == expected[index]),
                    "Precinct " + field + " do not reconcile to native county columns")
    for label in OPTIONS:
        for index in range(3):
            require(sum(record["options"][label]["counts"][index] for record in precinct_house)
                    == county_house[0]["options"][label]["counts"][index],
                    "Precinct House candidate/mode differs from county summary")
    require([sum(record["total"][index] for record in precinct_house) for index in range(3)]
            == county_house[0]["total"], "Precinct House totals differ from county summary")


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build(source, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing to overwrite an existing package")
    receipts = json.loads((source / "sources.json").read_text())
    factual = []
    documents = {}
    for name, (url, expected_hash) in ORIGINALS.items():
        found = [record for record in receipts if record["file"] == name]
        require(len(found) == 1 and found[0]["status"] == 200 and found[0]["url"] == url,
                "Missing or conflicting native original receipt")
        raw = (source / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected_hash == found[0]["sha256"]
                and len(raw) == found[0]["bytes"], "Changed native original")
        factual.append(found[0])
        documents[name] = read_pdf(raw, summary="summary" in name)
    summary = documents["linn-2026-general-summary.pdf"]
    detail = documents["linn-2026-general-precinct.pdf"]
    reconcile(summary, detail)
    require(len(detail[0]) == 94, "Incomplete native 94-precinct inventory")
    participation, results, candidates = [], [], []
    for county, parsed in [(True, summary), (False, detail)]:
        for stats, house in zip(*parsed):
            identity = dict(year=2026, state_code="IA", county="Linn County",
                            reporting_unit=stats["unit"], unit_type="county" if county else "native_precinct",
                            source_pdf_page=stats["page"], maps_approved=False)
            participation.append(dict(**identity, registered_voters_total=stats["registered"][0],
                **{"ballots_" + mode: stats["ballots"][index] for index, mode in enumerate(MODES)},
                **{"blank_ballots_" + mode: stats["blank"][index] for index, mode in enumerate(MODES)},
                native_registered_turnout_percent=stats["printed_turnout_percent"],
                registered_turnout_percent=round(100 * stats["ballots"][0] / stats["registered"][0], 6),
                quality_flags="unofficial;county_scoped;registered_denominator_not_vep_or_demographic"))
            for index, mode in enumerate(MODES):
                counts = {label: option["counts"][index] for label, option in house["options"].items()}
                total = house["total"][index]
                democratic, republican = counts["DEM Lindsay James"], counts["REP Joe Mitchell"]
                results.append(dict(**identity, contest=HOUSE, native_mode=mode, total_votes=total,
                    democratic_votes=democratic, republican_votes=republican,
                    other_votes=total - democratic - republican,
                    dem_minus_rep_pct=round(100 * (democratic - republican) / total, 6) if total else ""))
                for label in OPTIONS:
                    party = label.split(" ", 1)[0] if label.split(" ", 1)[0] in {"REP", "DEM", "LIB"} else ""
                    candidates.append(dict(**identity, contest=HOUSE, native_mode=mode,
                        native_option=label, party=party, votes=counts[label],
                        printed_total_vote_percent=house["options"][label]["printed_vote_percent"] if index == 0 else ""))
    audit = dict(year=2026, state_code="IA", scope="Linn County only",
        native_summary_pages=10, native_precinct_pages=511, precincts=94,
        ballots=summary[0][0]["ballots"], registered_voters=summary[0][0]["registered"][0],
        blank_ballots=summary[0][0]["blank"], house_votes=summary[1][0]["total"],
        participation_rows=94, house_mode_rows=282, complete_candidate_mode_rows=len(candidates),
        all_precinct_options_and_modes_reconcile=True, maps_approved=False, geometry_approved=False,
        rate_definition="Ballots divided by each native unit's own total registrations only; no mode-specific, VEP, CPS or demographic rate.",
        native_percentage_note="Preserve printed House percentages separately; they are not substituted for all-candidate margin denominators.",
        license_note="Official public aggregate election reports; no separate open-data license found in acquired declarations.",
        next_action="Obtain and reconcile correct-election native precinct boundaries without changing literal identities; continue remaining 2026 bulk-source reviews.")
    output.mkdir(parents=True)
    (output / "source").mkdir()
    for name in ORIGINALS:
        shutil.copyfile(source / name, output / "source" / name)
    (output / "source/sources.json").write_text(json.dumps(factual, indent=2) + "\n")
    shutil.copyfile(__file__, output / "review.py")
    for name, rows in [("precinct-participation.csv", participation[1:]),
                       ("county-participation.csv", participation[:1]),
                       ("precinct-results.csv", results[3:]), ("county-results.csv", results[:3]),
                       ("all-house-candidate-mode-counts.csv", candidates)]:
        write_csv(output / name, rows)
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    checksums = {path.relative_to(output).as_posix(): dict(
        bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(output.rglob("*")) if path.is_file()}
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
