"""Freeze complete native aggregate tables with independent row-vector checks."""

import argparse
import hashlib
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--proof", type=Path, required=True)
    args = parser.parse_args()
    import fitz
    import pdfplumber

    requests = json.loads(args.requests.read_bytes())
    receipts = {row["name"]: row for row in json.loads((args.source_root / "receipts.json").read_bytes())}
    reports, checks = [], 0
    for request in requests["reports"]:
        receipt = receipts[request["file"]]
        path = args.source_root / request["file"]
        if receipt["status"] != 200 or hashlib.sha256(path.read_bytes()).hexdigest() != receipt["sha256"]:
            raise ValueError("Pinned native source bytes differ")
        with pdfplumber.open(path) as primary, fitz.open(path) as independent:
            if len(primary.pages) != 1 or len(independent) != 1:
                raise ValueError("Changed source page scope")
            tables = [table for table in primary.pages[0].extract_tables()
                if len(table[0]) == len(request["columns"]) + 1]
            if len(tables) != 1:
                raise ValueError("Ambiguous native table")
            table = tables[0]
            first = [" ".join((value or "").split()) for value in table[0]]
            second = [" ".join((value or "").split()) for value in table[1]]
            if first != request["header_groups"] or second != request["header_columns"]:
                raise ValueError("Native column meanings changed")
            native_text = " ".join(independent[0].get_text().replace("*", " ").split())
            text = primary.pages[0].extract_text() or ""
            if "UNOFFICIAL" not in text or "PRIMARY" in text.upper():
                raise ValueError("Changed native election/status scope")
            rows = []
            for native in table[2:]:
                values = [" ".join((value or "").split()) for value in native]
                if " ".join(value for value in values if value) not in native_text:
                    raise ValueError("Independent complete native row differs")
                if any(value and not re.fullmatch(r"\d+(?:,\d{3})*", value) for value in values[1:]):
                    raise ValueError("Unparsed native count")
                rows.append(dict(label=values[0], count_literals=values[1:]))
                checks += len(values)
            if len(rows) != request["expected_rows"]:
                raise ValueError("Incomplete native row inventory")
            reports.append(dict(key=request["key"], geography=request["geography"],
                election=request["election"], source=receipt,
                source_clock=dict(literal=first[0], timezone=None), native_status_literal="UNOFFICIAL",
                columns=request["columns"], rows=rows))
    result = dict(contract="participation.native_table_counts.v1", reports=reports,
        native_presentation_redistributed=False, all_selected_table_cells_retained=True,
        native_parent_context=requests["native_parent_context"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists() or args.proof.exists():
        raise ValueError("Do not replace an immutable source extraction")
    args.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
    proof = dict(status="passed_independent_complete_native_table_vectors",
        source_reports=len(reports), complete_rows=sum(len(report["rows"]) for report in reports),
        cells_and_labels_checked=checks, source_sha256={report["key"]: report["source"]["sha256"] for report in reports},
        original_presentations_kept_private=True, missing_native_cells_not_zero=True)
    args.proof.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    print(json.dumps(proof, sort_keys=True))


if __name__ == "__main__":
    main()
