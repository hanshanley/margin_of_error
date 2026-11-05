"""Review archived native voter-count tables, not candidate votes or precinct maps."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import zipfile

import fitz


INTEGER = re.compile(r"(?:0|[1-9]\d*)(?:,\d{3})*")


def integer(text):
    if not INTEGER.fullmatch(text):
        raise ValueError(f"Not an explicit nonnegative integer: {text!r}")
    return int(text.replace(",", ""))


def display_rows(page):
    rows = []
    for word in page.get_text("words"):
        box = fitz.Rect(word[:4]) * page.rotation_matrix
        y = (box.y0 + box.y1) / 2
        row = next((row for row in rows if abs(row[0] - y) < 2), None)
        if row is None:
            row = [y, []]
            rows.append(row)
        row[1].append((box, word[4]))
    return [(y, sorted(words, key=lambda word: word[0].x0)) for y, words in sorted(rows)]


def labeled_integer(page, label):
    anchors = page.search_for(label)
    if not anchors:
        return None
    if len(anchors) != 1:
        raise ValueError(f"Ambiguous source label: {label}")
    box = anchors[0] * page.rotation_matrix
    matches = [(r.x0, text) for y, row in display_rows(page) for r, text in row
               if abs(y - (box.y0 + box.y1) / 2) < 4
               and r.x0 > box.x1 and INTEGER.fullmatch(text)]
    if not matches:
        raise ValueError(f"No explicit count next to {label}")
    return integer(min(matches)[1])


def printed_turnout(page):
    anchors = page.search_for("Percentage of Voter Turnout:") or page.search_for("Voter Percentage Turnout")
    if not anchors:
        return None
    if len(anchors) != 1:
        raise ValueError("Ambiguous native turnout-percentage label")
    box = anchors[0] * page.rotation_matrix
    values = [float(text[:-1]) for y, row in display_rows(page) for r, text in row
              if abs(y - (box.y0 + box.y1) / 2) < 4 and r.x0 > box.x1
              and re.fullmatch(r"\d+(?:\.\d+)?%", text)]
    if len(values) > 1 or any(not 0 <= value <= 100 for value in values):
        raise ValueError("Invalid or ambiguous native turnout percentage")
    return values[0] if values else None


def lewiston_voters(page):
    anchors = page.search_for("Total Number of Voters")
    if len(anchors) != 1:
        raise ValueError("Missing or ambiguous native ward voter-count table")
    anchor = anchors[0] * page.rotation_matrix
    rows = display_rows(page)
    headers = [(y, row) for y, row in rows if anchor.y1 < y < anchor.y1 + 60
               and "C-V" in [text for _, text in row]
               and any(text in {"Total", "Totals"} for _, text in row)]
    if len(headers) != 1:
        raise ValueError("Missing or ambiguous ward/central/total columns")
    y, header = headers[0]
    labels = [text for _, text in header]
    expected = ([str(n) for n in range(1, 8)] if len(labels) == 9
                else [f"{ward}-{precinct}" for ward in range(1, 8) for precinct in [1, 2]])
    if labels[:-2] != expected or labels[-2:] not in [["C-V", "Total"], ["C-V", "Totals"]]:
        raise ValueError(f"Unexpected or duplicate reporting-unit columns: {labels}")
    candidates = [(yy, [(box, text) for box, text in row if INTEGER.fullmatch(text)])
                  for yy, row in rows if y < yy < y + 30]
    if len(candidates) != 1 or len(candidates[0][1]) != len(header):
        raise ValueError("Missing explicit count in the native voter row")
    values = candidates[0][1]
    for (heading, _), (value, _) in zip(header, values):
        if abs((heading.x0 + heading.x1 - value.x0 - value.x1) / 2) > 15:
            raise ValueError("Voter counts do not align with native column coordinates")
    counts = [integer(text) for _, text in values]
    if sum(counts[:-1]) != counts[-1]:
        raise ValueError("Native ward and central counts do not equal the native city total")
    return dict(zip(labels[:-1], counts[:-1])), counts[-1]


def pa_mail_table(pages, percent):
    rows = {}
    pattern = re.compile(r"([A-Za-z]+) (\d[\d,]*)" + (r" (\d+\.\d+)%" if percent else ""))
    for number, page in pages:
        for _, words in display_rows(page):
            match = pattern.fullmatch(" ".join(text for _, text in words))
            if not match or match[1] == "Statewide":
                continue
            name = match[1]
            if name in rows:
                raise ValueError(f"Duplicate native Pennsylvania county: {name}")
            row = dict(county=name, mail_returns=integer(match[2]), pdf_page=number)
            if percent:
                value = float(match[3])
                if not 0 <= value <= 100:
                    raise ValueError("Invalid native mail-counting progress")
                row["mail_percent_remaining_to_count"] = value
            rows[name] = row
    if len(rows) != 67:
        raise ValueError(f"Expected all 67 native Pennsylvania county rows, found {len(rows)}")
    return rows


def review(source):
    inventory = json.loads((source / "index.json").read_bytes())
    raw = (source / "complete-originals.tar.gz").read_bytes()
    assert len(raw) == inventory["archive"]["bytes"]
    assert hashlib.sha256(raw).hexdigest() == inventory["archive"]["sha256"]
    cities, units = [], []
    metadata = {item["file"]: item for item in inventory["originals"]}
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        documents = {}
        for item in inventory["originals"]:
            body = archive.extractfile(item["file"]).read()
            assert len(body) == item["bytes"] and hashlib.sha256(body).hexdigest() == item["sha256"]
            documents[item["file"]] = fitz.open(stream=body, filetype="pdf")
        for item in inventory["originals"]:
            if item["state_code"] != "ME" or "Write-In" in item["label"]:
                continue
            year = int(Path(item["file"]).name[:4])
            doc = documents[item["file"]]
            page = doc[-1]
            if year == 2020:
                total = labeled_integer(page, "Total Votes Cast")
                counts = {label: labeled_integer(page, "Total Ballots Voted " + label)
                          for label in ["Absentee", "In Person"]}
                assert total is not None and all(value is not None for value in counts.values())
                assert sum(counts.values()) == total
                registered = labeled_integer(page, "Total Registered Voters")
            else:
                counts, total = lewiston_voters(page)
                registered = labeled_integer(page, "Total Number of Registered Voters:")
            assert registered is None or total <= registered
            common = dict(year=year, state_code="ME", municipality="Lewiston", source_file=item["file"],
                          source_url=item["url"], source_sha256=item["sha256"], pdf_page=len(doc))
            cities.append(dict(common, geography_level="municipality", voters=total,
                               registered_voters=registered,
                               registered_turnout_pct=100 * total / registered if registered else None,
                               native_printed_turnout_pct=printed_turnout(page),
                               native_source_index_label=item["label"]))
            for label, count in counts.items():
                units.append(dict(common, native_unit=label, voters=count,
                                  scope="city_voting_mode" if year == 2020 else
                                  "central_voting_unallocated" if label == "C-V" else
                                  "ward_precinct" if "-" in label else "ward",
                                  registered_voters=None, turnout_pct=None))
        assert sorted(row["year"] for row in cities) == list(range(2002, 2027, 2))
        standalone_name = "PA/1201.report.2026general.pdf"
        report_name = "PA/pados_enrsupplementalboard_2026general.pdf"
        standalone = pa_mail_table(enumerate(documents[standalone_name], 1), False)
        report = documents[report_name]
        supplemental = pa_mail_table([(i + 1, report[i]) for i in [1, 2, 3]], True)
        assert {k: v["mail_returns"] for k, v in standalone.items()} == {
            k: v["mail_returns"] for k, v in supplemental.items()}
        overview_text = report[0].get_text()
        total = sum(row["mail_returns"] for row in standalone.values())
        assert f"{total:,}" in overview_text
        for literal in ["9,052,695", "9,065", "9,055 (99.89%)", "10 (0.11%)"]:
            assert literal in overview_text
        timestamp = re.search(r"\d{1,2}/\d{1,2}/2026 \d{1,2}:\d{2}:\d{2} [AP]M", overview_text)[0]
        pa = [dict(year=2026, state_code="PA", **standalone[name],
                   supplemental_pdf_page=supplemental[name]["pdf_page"],
                   mail_percent_remaining_to_count=supplemental[name]["mail_percent_remaining_to_count"],
                   source_file=standalone_name, supplemental_source_file=report_name,
                   source_url=metadata[standalone_name]["url"],
                   source_sha256=metadata[standalone_name]["sha256"],
                   supplemental_source_url=metadata[report_name]["url"],
                   supplemental_source_sha256=metadata[report_name]["sha256"],
                   source_update_literal=timestamp, turnout_pct=None)
              for name in sorted(standalone)]
    audit = dict(status="reviewed_counts_only", maps_approved=False, candidate_results=False,
                 demographic_breakdown_available=False, lewiston_years=sorted(row["year"] for row in cities),
                 lewiston_city_rows=len(cities), lewiston_unit_rows=len(units),
                 pa_counties=len(pa), pa_recorded_mail_returns=total,
                 pa_source_update_literal=timestamp,
                 pa_overview=dict(registered_voters=9052695, precincts_reported=9055,
                                  precincts_remaining=10, precincts_total=9065),
                 scope_notes=[
                     "Lewiston only, not statewide Maine; native election-specific units are not stable boundaries.",
                     "C-V is unallocated Central Voting, not Absentees and not assigned among wards.",
                     "2020 reports city voting modes rather than ward voter counts; no ward counts are inferred.",
                     "Registered-voter rates exist only for native city totals with an explicit denominator.",
                     "Native printed percentages are retained separately, including blanks and rounded values.",
                     "Pennsylvania records returned mail ballots, not all-mode ballots, candidate votes or final turnout.",
                     "Mail-counting and precinct-reporting progress are not voter participation percentages.",
                     "Montour's explicit zero administrative returns are not evidence of zero voter participation.",
                     "No earlier snapshot is overwritten or silently combined with these dated observations.",
                 ], original_archive=inventory["archive"])
    return {"lewiston-city-participation": cities, "lewiston-native-voter-counts": units,
            "pennsylvania-county-mail-returns": pa}, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    tables, audit = review(args.source_package)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, rows in tables.items():
        with (args.output / (name + ".csv")).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        (args.output / (name + ".json")).write_text(json.dumps(rows, indent=2) + "\n")
    (args.output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    originals = args.output / "originals"
    originals.mkdir()
    for name in ["index.json", "checksums.json", "complete-originals.tar.gz"]:
        (originals / name).write_bytes((args.source_package / name).read_bytes())
    (args.output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    files = sorted(path for path in args.output.rglob("*") if path.is_file())
    checksums = {path.relative_to(args.output).as_posix():
                 dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in files}
    (args.output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(path for path in args.output.rglob("*") if path.is_file()):
            info = zipfile.ZipInfo(path.relative_to(args.output).as_posix())
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
