import argparse
import collections
import hashlib
import json
from pathlib import Path
import re

import fitz


FILES = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, default=FILES / "massachusetts-independent-city-sources-20261110-01")
parser.add_argument("--queries", type=Path)
parser.add_argument("--proof", type=Path)
args = parser.parse_args()
ROOT = args.root
ORIGINALS = ROOT / "declared-results-01"
QUERIES = args.queries or ROOT / "native-count-review-01/complete-native-count-queries.json"
PROOF = args.proof or ROOT / "native-count-review-01/independent-native-verification.json"
assert not PROOF.exists()
result = json.loads(QUERIES.read_bytes())
checks = 0
for source in result["sources"]:
    body = (ORIGINALS / source["name"]).read_bytes()
    assert len(body) == source["bytes"]
    assert hashlib.sha256(body).hexdigest() == source["sha256"]
    checks += 2
document = fitz.open(ORIGINALS / "boston-2026-Unofficial-Statement-Of-Votes-Cast.pdf")
summary, contexts = {}, collections.defaultdict(dict)
context = None
for page_index, page in enumerate(document):
    header = " ".join(page.get_text(clip=fitz.Rect(15, 35, 780, 65)).split())
    if "(Vote for" in header:
        context = header
    text = page.get_text(clip=fitz.Rect(15, 35, 310, page.rect.height-12))
    if page_index < 8:
        for ward, precinct, registered, cast, rate in re.findall(
            r"WARD (\d+), PRECINCT (\d+)\n([\d,]+)\n([\d,]+)\n(N/A)\n", text
        ):
            key = (ward, precinct)
            assert key not in summary
            summary[key] = (int(registered.replace(",", "")), int(cast.replace(",", "")), rate)
    elif "Times Cast" in page.get_text():
        for ward, precinct, cast, registered, blank in re.findall(
            r"WARD (\d+), PRECINCT (\d+)\n([\d,]+)\n([\d,]+)\n([\d,]+)\n", text
        ):
            key = (ward, precinct)
            assert key not in contexts[context]
            contexts[context][key] = (int(cast.replace(",", "")), int(registered.replace(",", "")))
assert len(summary) == len(result["boston_summary"]) == 275
for row in result["boston_summary"]:
    assert summary[row["ward"], row["precinct"]] == (
        row["registered_voters_literal"], row["voters_cast_literal"], row["turnout_literal"])
    assert row["analysis_denominator"] is row["analysis_rate"] is None
    checks += 4
assert set(contexts) == set(result["boston_all_times_cast_frames"])
for context, rows in result["boston_all_times_cast_frames"].items():
    assert len(contexts[context]) == len(rows)
    for row in rows:
        assert contexts[context][row["ward"], row["precinct"]] == (
            row["times_cast_literal"], row["registered_voters_literal"])
        assert row["analysis_denominator"] is row["analysis_rate"] is None
        checks += 3

somerville_document = fitz.open(ORIGINALS / "somerville-election-results-preliminary-20261103.pdf")
page = somerville_document[0]
columns = sorted(
    [word for word in page.get_text("words") if 62 < word[1] < 64 and word[0] > 120],
    key=lambda word: word[0],
)
edges = [122.0] + [
    ((left[0] + left[2]) / 2 + (right[0] + right[2]) / 2) / 2
    for left, right in zip(columns, columns[1:])
] + [990.0]
for index, expected in enumerate(result["somerville_native_counts"]):
    reg = page.get_text(clip=fitz.Rect(edges[index], 97, edges[index+1], 109)).strip()
    cast = page.get_text(clip=fitz.Rect(edges[index], 142, edges[index+1], 154)).strip()
    assert int(reg) == expected["registered_voters_literal"], (index, reg, expected)
    assert int(cast) == expected["ballots_cast_literal"], (index, cast, expected)
    assert expected["analysis_denominator"] is expected["analysis_rate"] is None
    checks += 3
assert {(row["ward"], row["precinct"]) for row in result["somerville_native_counts"]
        if row["precinct"] and row["precinct"].endswith("A")} == {
    ("1", "4A"), ("2", "1A"), ("4", "2A"), ("6", "3A")}
checks += 4


def normalize(value):
    return " ".join(value.upper().replace("&", "AND").split())


web = {normalize(row["native_context"]): row["ballots_cast_literal"]
       for row in result["boston_declaring_page_ballots_cast"]}
web_checks = []
for native_context, rows in result["boston_all_times_cast_frames"].items():
    match = web.get(normalize(native_context))
    total = sum(row["times_cast_literal"] for row in rows)
    web_checks.append(dict(native_context=native_context, native_pdf_times_cast_sum=total,
                           native_web_ballots_cast=match,
                           difference=None if match is None else total-match))
first_six = web_checks[:6]
assert all(row["native_web_ballots_cast"] == row["native_pdf_times_cast_sum"] == 185569
           for row in first_six)
assert result["boston_summary_voters_cast_sum"] == 556369
assert result["boston_summary_voters_cast_sum"] != result["boston_senate_times_cast_sum"]
assert all(row["component_minus_printed"] == 0 for row in result["somerville_all_accounting"])
assert not any(result[field] for field in [
    "source_counts_repaired", "candidate_votes_summed",
    "central_tabulation_added_to_combined", "maps_approved"])
checks += 6 + 2 + len(result["somerville_all_accounting"]) + 4
proof = dict(
    status="PASS_independent_native_field_checks_NOT_geography_or_unique_person_approval",
    checks=checks, source_query_sha256=hashlib.sha256(QUERIES.read_bytes()).hexdigest(),
    boston_summary_rows=275, boston_native_times_cast_rows=sum(map(len, contexts.values())),
    somerville_native_count_rows=len(result["somerville_native_counts"]),
    native_pdf_web_comparisons=web_checks,
    times_cast_contexts_with_native_row_differences=[
        row for row in result["boston_frame_checks"] if not row["all_rows_match_senate_native_field"]],
    zero_registers_not_analysis_denominators=True, summary_fields_not_repaired=True,
    split_precinct_labels_preserved=True, source_geography_approved=False,
)
PROOF.write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof))
