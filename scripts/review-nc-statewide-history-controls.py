"""Reconcile statewide history records with frozen official all-ballot controls."""

import argparse
from fractions import Fraction
import hashlib
import html
import json
import os
from pathlib import Path
import re


SOURCE_SHA256 = "2f9184a18d834684535f815db8fdb02bfc4589f7c2d6b86897ea3e60eeaf9c5c"


def missing_only_bounds(observed_prior, observed_current, observed_both, official_prior, official_current):
    values = (observed_prior, observed_current, observed_both, official_prior, official_current)
    if any(type(n) is not int or n < 0 for n in values) or observed_both > min(observed_prior, observed_current):
        raise ValueError("Invalid all-ballot overlap controls")
    if observed_prior > official_prior or observed_current > official_current:
        return None
    upper = min(official_prior, official_current,
                observed_both + official_prior - observed_prior + official_current - observed_current)
    return {
        "overlap_count_lower": observed_both, "overlap_count_upper": upper,
        "return_pct_lower": float(Fraction(100 * observed_both, official_prior)) if official_prior else None,
        "return_pct_upper": float(Fraction(100 * upper, official_prior)) if official_prior else None,
    }


def official_ballots(source):
    result = {}
    for table in re.findall(r"<table\b.*?</table>", source, re.S)[:2]:
        for row in re.findall(r"<tr\b.*?</tr>", table, re.S):
            cells = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", cell)).split())
                     for cell in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, re.S)]
            if not cells or cells[0] not in ("2020 General", "2022 General", "2024 General"):
                continue
            year = int(cells[0][:4])
            if len(cells) != 4 or year in result or not cells[2].replace(",", "").isdigit():
                raise ValueError("Ambiguous official all-ballot control")
            result[year] = int(cells[2].replace(",", ""))
    if set(result) != {2020, 2022, 2024}:
        raise ValueError("Missing official election-year controls")
    return result


def review(summary, official):
    if summary["state_code"] != "NC" or set(official) != {2020, 2022, 2024}:
        raise ValueError("Unexpected state or official election scope")
    coverage = [{
        "year": year,
        "unique_history_records": summary["unique_positive_history_records_by_year"][str(year)],
        "official_ballots_cast": total,
        "signed_history_minus_official": summary["unique_positive_history_records_by_year"][str(year)] - total,
    } for year, total in sorted(official.items())]
    comparisons = []
    for comparison in summary["comparisons"]:
        a, b = comparison["prior_year"], comparison["current_year"]
        counts = summary["unique_positive_history_records_by_year"]
        both = comparison["record_presence_matrix"]["recorded_both"]
        comparisons.append({
            "prior_year": a, "current_year": b,
            "observed_archive_overlap": both,
            "missing_record_only_sensitivity_not_ci": missing_only_bounds(
                counts[str(a)], counts[str(b)], both, official[a], official[b]),
            "candidate_choice_retention_validated": False,
        })
    return {
        "status": "statewide_administrative_coverage_checked_not_population_transition_certification",
        "state_code": "NC", "year_controls": coverage, "comparisons": comparisons,
        "bound_assumptions_not_established_by_marginal_agreement": [
            "Each official ballot represents one unique person in that state's general election.",
            "Observed history positives and cross-year identifiers are correct, with no false matches or split identifiers.",
            "Differences from official totals are only missed person-election records, not definition or source-vintage differences.",
            "The missing-only interval is not a design confidence interval and does not bound identifier or history misclassification.",
        ],
        "marginal_coverage_does_not_validate_individual_transitions": True,
        "population_method_validated": False,
        "public_release_qualified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-summary", type=Path, required=True)
    parser.add_argument("--independent-proof", type=Path, required=True)
    parser.add_argument("--official-source-html", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or Path(__file__).resolve().parents[1] in args.output.resolve().parents:
        raise ValueError("Output must be new and outside the repository")
    raw, source = args.history_summary.read_bytes(), args.official_source_html.read_bytes()
    proof_raw = args.independent_proof.read_bytes()
    proof = json.loads(proof_raw)
    if (hashlib.sha256(source).hexdigest() != SOURCE_SHA256
            or proof["status"] != "independent_native_statewide_year_column_verification_passed"
            or hashlib.sha256(raw).hexdigest() != proof["results_sha256"]):
        raise ValueError("Frozen administrative or official-control evidence differs")
    result = review(json.loads(raw), official_ballots(source.decode("utf-8")))
    result["source_binding"] = {
        "history_summary_sha256": hashlib.sha256(raw).hexdigest(),
        "independent_native_proof_sha256": hashlib.sha256(proof_raw).hexdigest(),
        "official_source_html_sha256": SOURCE_SHA256,
        "official_source_url": "https://www.ncsbe.gov/results-data/voter-turnout",
    }
    args.output.mkdir(parents=True, mode=0o700)
    descriptor = os.open(args.output / "official-coverage-check.json",
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as target:
        json.dump(result, target, indent=2, allow_nan=False)
        target.write("\n")
    print(json.dumps({"status": result["status"], "years": len(result["year_controls"])}))


if __name__ == "__main__":
    main()
