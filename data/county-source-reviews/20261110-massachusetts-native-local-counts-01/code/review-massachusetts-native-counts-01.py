import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup
import fitz


FILES = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, default=FILES / "massachusetts-independent-city-sources-20261110-01")
parser.add_argument("--output", type=Path)
args = parser.parse_args()
ROOT = args.root
ORIGINALS = ROOT / "declared-results-01"
OUTPUT = args.output or ROOT / "native-count-review-01"
assert not OUTPUT.exists()


def lines(page, right):
    rows = []
    for word in sorted(
        [word for word in page.get_text("words") if word[0] < right],
        key=lambda word: (word[1], word[0]),
    ):
        if not rows or abs(word[1] - rows[-1][0][1]) > 1:
            rows.append([word])
        else:
            rows[-1].append(word)
    return [sorted(row, key=lambda word: word[0]) for row in rows]


document = fitz.open(ORIGINALS / "boston-2026-Unofficial-Statement-Of-Votes-Cast.pdf")
summary, contexts, printed_totals = [], collections.defaultdict(list), []
context = None
for page_index, page in enumerate(document):
    header = " ".join(page.get_text(clip=fitz.Rect(15, 35, 780, 65)).split())
    if "(Vote for" in header:
        context = header
    is_summary = page_index < 8
    if not is_summary and "Times Cast" not in page.get_text():
        continue
    for row in lines(page, 320):
        label = " ".join(word[4] for word in row if word[0] < 130)
        match = re.fullmatch(r"WARD (\d+), PRECINCT (\d+)", label)
        numeric = [word[4] for word in row if 130 <= word[0] < (245 if is_summary else 280)]
        if match:
            assert len(numeric) == 2, (page_index + 1, label, numeric)
            numbers = [int(value.replace(",", "")) for value in numeric]
            record = dict(
                city="Boston", ward=match[1], precinct=match[2],
                native_label=label, source_page=page_index + 1,
                source_snapshot="2026-11-04 11:39:02 AM",
                analysis_denominator=None, analysis_rate=None,
            )
            if is_summary:
                record.update(registered_voters_literal=numbers[0],
                              voters_cast_literal=numbers[1],
                              turnout_literal=" ".join(word[4] for word in row if word[0] >= 245))
                summary.append(record)
            else:
                record.update(native_context=context, times_cast_literal=numbers[0],
                              registered_voters_literal=numbers[1])
                contexts[context].append(record)
        elif label in ["BOSTON - Total", "Cumulative - Total"] and numeric:
            printed_totals.append(dict(
                context="summary" if is_summary else context, native_label=label,
                source_page=page_index + 1, numeric_literals=numeric,
            ))
assert len(summary) == 275
assert len({(row["ward"], row["precinct"]) for row in summary}) == 275
assert len(contexts) == 44
for name, rows in contexts.items():
    assert len({(row["ward"], row["precinct"]) for row in rows}) == len(rows), name
senate = contexts["SENATOR IN CONGRESS (Vote for 1)"]
assert len(senate) == 275
senate_by_id = {(row["ward"], row["precinct"]): row["times_cast_literal"] for row in senate}
context_checks = [
    dict(native_context=name, precinct_rows=len(rows),
         derived_times_cast_sum=sum(row["times_cast_literal"] for row in rows),
         all_rows_match_senate_native_field=all(
             row["times_cast_literal"] == senate_by_id[row["ward"], row["precinct"]]
             for row in rows),
         native_field_not_candidate_sum=True)
    for name, rows in contexts.items()
]

soup = BeautifulSoup((ROOT / "boston-declaring-page.private.html").read_bytes(), "html.parser")
web_counts = []
for heading in soup.select("h3"):
    name = " ".join(heading.get_text(" ", strip=True).split())
    if "(Vote for" not in name:
        continue
    table = heading.find_next("table")
    if table is None:
        continue
    headers = [cell.get_text(" ", strip=True) for cell in table.select("th")]
    cells = table.select("td")
    if headers and "Ballots Cast" in headers[0] and cells:
        web_counts.append(dict(native_context=name,
                               ballots_cast_literal=int(cells[0].get_text(strip=True).replace(",", ""))))
assert web_counts, "Require native declaring-page count fields, never search snippets"

somerville_document = fitz.open(ORIGINALS / "somerville-election-results-preliminary-20261103.pdf")
page = somerville_document[0]
words = page.get_text("words")
headers = sorted([word for word in words if 62 < word[1] < 64 and word[0] > 120],
                 key=lambda word: word[0])
assert len(headers) == 40
registered = sorted([word for word in words if 98 < word[1] < 100 and word[0] > 120],
                    key=lambda word: word[0])
cast = sorted([word for word in words if 143 < word[1] < 145 and word[0] > 120],
              key=lambda word: word[0])
assert len(registered) == len(cast) == 40
somerville = []
ward = 1
for header, reg, ballot in zip(headers, registered, cast):
    center = (header[0] + header[2]) / 2
    assert all(abs((word[0] + word[2]) / 2 - center) < 6 for word in [reg, ballot])
    label = header[4]
    assert re.fullmatch(r"\d+A?|TOTAL|Total", label)
    level = "city" if label == "Total" else "ward" if label == "TOTAL" else "precinct"
    somerville.append(dict(
        city="Somerville", ward=None if level == "city" else str(ward),
        precinct=label if level == "precinct" else None, native_level=level,
        registered_voters_literal=int(reg[4]), ballots_cast_literal=int(ballot[4]),
        source_page=1, native_date="2026-11-03",
        source_document_literal_status="UnOfficial",
        declaring_page_heading_literal_status="Official",
        analysis_denominator=None, analysis_rate=None,
        unique_voter_count_qualified=False,
    ))
    if level == "ward":
        ward += 1
assert ward == 8
assert sum(row["native_level"] == "precinct" for row in somerville) == 32
accounting = []
for field in ["registered_voters_literal", "ballots_cast_literal"]:
    city = next(row[field] for row in somerville if row["native_level"] == "city")
    total = sum(row[field] for row in somerville if row["native_level"] == "ward")
    accounting.append(dict(field=field, level="city", printed=city,
                           component_sum=total, component_minus_printed=total-city))
    for ward in range(1, 8):
        printed = next(row[field] for row in somerville
                       if row["native_level"] == "ward" and row["ward"] == str(ward))
        total = sum(row[field] for row in somerville
                    if row["native_level"] == "precinct" and row["ward"] == str(ward))
        accounting.append(dict(field=field, level="ward", ward=str(ward), printed=printed,
                               component_sum=total, component_minus_printed=total-printed))

result = dict(
    status="PASS_native_field_extraction_NOT_unique_voter_rate_or_geography_approval",
    boston_summary=summary, boston_all_times_cast_frames=dict(contexts),
    boston_printed_parent_fields=printed_totals, boston_frame_checks=context_checks,
    boston_declaring_page_ballots_cast=web_counts,
    boston_summary_voters_cast_sum=sum(row["voters_cast_literal"] for row in summary),
    boston_senate_times_cast_sum=sum(row["times_cast_literal"] for row in senate),
    boston_summary_and_contest_fields_not_substituted=True,
    somerville_native_counts=somerville, somerville_all_accounting=accounting,
    somerville_ballots_over_registered=[
        dict(ward=row["ward"], precinct=row["precinct"], native_level=row["native_level"],
             native_difference=row["ballots_cast_literal"]-row["registered_voters_literal"])
        for row in somerville if row["ballots_cast_literal"] > row["registered_voters_literal"]
    ],
    source_counts_repaired=False, candidate_votes_summed=False,
    central_tabulation_added_to_combined=False, maps_approved=False,
    sources=[dict(name=path.name, bytes=path.stat().st_size, pages=len(fitz.open(path)),
                  sha256=hashlib.sha256(path.read_bytes()).hexdigest())
             for path in sorted(ORIGINALS.glob("*.pdf"))],
)
OUTPUT.mkdir()
(OUTPUT / "complete-native-count-queries.json").write_text(json.dumps(result, indent=2) + "\n")
for name, rows in [
    ("boston-summary-native.csv", summary),
    ("boston-all-native-times-cast.csv", [row for rows in contexts.values() for row in rows]),
    ("somerville-native-counts.csv", somerville),
]:
    with (OUTPUT / name).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
print(json.dumps(dict(
    status=result["status"], boston_summary_rows=len(summary),
    boston_native_times_cast_frames=len(contexts),
    boston_native_times_cast_rows=sum(map(len, contexts.values())),
    boston_summary_voters_cast=result["boston_summary_voters_cast_sum"],
    boston_senate_times_cast=result["boston_senate_times_cast_sum"],
    boston_declaring_page_counts=web_counts[:6],
    somerville_precinct_rows=32, somerville_all_native_rows=len(somerville),
    somerville_accounting_disagreements=[row for row in accounting if row["component_minus_printed"]],
    somerville_ballots_over_registered_rows=len(result["somerville_ballots_over_registered"]),
    full_PDFs=len(result["sources"]), full_pages=sum(row["pages"] for row in result["sources"]),
)))
