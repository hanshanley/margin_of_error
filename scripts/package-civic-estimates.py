"""Reproduce broad source-weighted Civic estimates from permitted sufficient statistics."""

import csv
from decimal import Decimal, localcontext
import hashlib
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "20261108-01"
DATA = f"data/participation-civic-estimates/{VERSION}"
INPUT_SHA = "00cc086a15eb2f287d1dd210df3e5a65a52345d3f0de8760fed3f57054e2345d"
STATUS = "exploratory_source_weighted_not_population_certified"
ZERO = Decimal(0)


def number(value):
    if not isinstance(value, str):
        raise ValueError("Require exact decimal source statistics")
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("Nonfinite source statistic")
    return result


def review(snapshot):
    if (snapshot["status"] != STATUS or snapshot["raw_source_rows"] != 113020
            or snapshot["states_present"] != 50 or snapshot["dc_present"] is not False
            or snapshot["field_period"] is not None or snapshot["weight_target_and_calibration"] is not None
            or any(snapshot[key] is not False for key in (
                "administrative_turnout_validation", "original_coalition_population_validation",
                "source_weight_units_are_people"))):
        raise ValueError("Study, frame, weight qualification or validation changed")
    if len(snapshot["participation"]) != 79:
        raise ValueError("Require all selected broad participation rows")
    participation, flows, margins = [], [], []
    seen = set()
    with localcontext() as context:
        context.prec = 80
        for row in snapshot["participation"]:
            key = row["scope"], row["dimension"], row["group"]
            if key in seen or row["group"] in {"88", "99", "MISSING"}:
                raise ValueError("Duplicate or excluded demographic disclosure group")
            seen.add(key)
            if (row["scope"] != "POOLED_SOURCE" and row["dimension"] != "overall"
                    or type(row["n"]) is not int or row["n"] < 100):
                raise ValueError("Fine state demographics or unsupported group")
            total, squared, voter, nonvoter, reported = [
                number(row[field]) for field in (
                    "weight", "weight_squared", "modeled_voter_weight",
                    "modeled_nonvoter_weight", "already_voted_self_report_weight")]
            if (min(total, squared) <= 0 or min(voter, nonvoter, reported) < 0
                    or voter + nonvoter != total or reported > total):
                raise ValueError("Full source model frame fails to reconcile")
            participation.append({
                "scope": row["scope"], "dimension": row["dimension"], "group": row["group"],
                "label": row["label"], "n": row["n"],
                "modeled_voter_pct": str(100 * voter / total),
                "modeled_nonvoter_pct": str(100 * nonvoter / total),
                "already_voted_self_report_pct": str(100 * reported / total),
                "source_effective_n": str(total * total / squared),
            })
        if len({r["scope"] for r in participation if r["scope"] != "POOLED_SOURCE"}) != 50:
            raise ValueError("Missing or repeated source state")
        disposition_keys = {
            (r["prior_election"], r["dimension"], r["group"], r["prior_choice"]): r["status"]
            for r in snapshot["conditional_flow_dispositions"]
        }
        for row in snapshot["conditional_flows"]:
            key = row["prior_election"], row["dimension"], row["group"], row["prior_choice"]
            if disposition_keys.get(key) != "selected_broad_conditional_source_estimate":
                raise ValueError("Unqualified conditional row")
            if row["prior_election"] not in {"2024", "2022"} or row["prior_choice"] not in {"D", "R", "N"}:
                raise ValueError("Unsupported retrospective comparison")
            if set(row["weights"]) != {"D", "R", "O_U", "N"} or row["n"] < 100:
                raise ValueError("Incomplete coarse current destinations or source base")
            values = {k: number(v) for k, v in row["weights"].items()}
            total = sum(values.values(), ZERO)
            if total <= 0 or min(values.values()) < 0:
                raise ValueError("Invalid full prior-group denominator")
            flows.append({
                "prior_election": row["prior_election"], "dimension": row["dimension"],
                "group": row["group"], "label": row["label"], "prior_choice": row["prior_choice"],
                "n": row["n"], **{k + "_pct": str(100 * v / total) for k, v in values.items()},
            })
        for row in snapshot["pooled_margin_primitives"]:
            m0, m1, t0, t1 = [number(row[k]) for k in ("m24", "m26", "t24", "t26")]
            parts = {k: number(row[k]) for k in (
                "switching", "modeled_nonparticipation", "no_prior_contest_vote_entry", "other_or_unresolved")}
            if min(t0, t1) <= 0 or sum(parts.values(), ZERO) != m1 - m0:
                raise ValueError("Raw within-source margin components do not reconcile")
            scale = (1 / t0 + 1 / t1) / 2
            normalized = {k + "_pp": 100 * scale * value for k, value in parts.items()}
            denominator = 100 * (m0 + m1) / 2 * (1 / t1 - 1 / t0)
            change = 100 * (m1 / t1 - m0 / t0)
            if abs(sum(normalized.values(), ZERO) + denominator - change) > Decimal("1e-20"):
                raise ValueError("Normalized margin decomposition does not reconcile")
            margins.append({
                "prior_election": row["prior_election"],
                "scope": "POOLED_SOURCE",
                "reported_prior_known_major_party_margin_pp": str(100 * m0 / t0),
                "modeled_current_known_major_party_margin_pp": str(100 * m1 / t1),
                **{k: str(v) for k, v in normalized.items()},
                "denominator_pp": str(denominator),
                "total_within_source_margin_change_pp": str(change),
                "eligibility_residence_component": None,
            })
    return {
        "status": STATUS, "study": snapshot["study"], "version": VERSION,
        "source_urls": snapshot["source_urls"], "csv_sha256": snapshot["csv_sha256"],
        "codebook_sha256": snapshot["codebook_sha256"],
        "field_period": None, "weight_target_and_calibration": None,
        "source_frame_not_original_historical_coalitions": True,
        "source_weight_units_are_people": False, "measured_staying_home": None,
        "population_switchers": None, "causal_persuasion": None,
        "design_confidence_intervals": None,
        "participation": participation, "conditional_flows": flows,
        "conditional_flow_dispositions": snapshot["conditional_flow_dispositions"],
        "margin_components": margins,
        "independent_native_verification": snapshot["independent_native_verification"],
    }


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def frozen_write(path, body):
    if path.exists() and path.read_bytes() != body:
        raise ValueError("Frozen analysis differs; create a new version")
    path.write_bytes(body)


def package():
    source = (ROOT / DATA / "selected-aggregates.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != INPUT_SHA:
        raise ValueError("Selected source statistics changed")
    selected = json.loads(source)
    selection = json.loads((ROOT / DATA / "selection-review.json").read_text())
    if (selection["public_input_sha256"] != INPUT_SHA
            or selection["state_participation_only_no_state_choice_flows_published"] is not True
            or selection["source_dataset_or_document_license_not_claimed"] is not True):
        raise ValueError("Public selection basis changed")
    analysis = review(selected)
    out = ROOT / DATA / "output"
    out.mkdir(exist_ok=True)
    outputs = {"summary.json": encoded(analysis)}
    for filename, rows in (
        ("participation.csv", analysis["participation"]),
        ("conditional-flows.csv", analysis["conditional_flows"]),
        ("flow-dispositions.csv", analysis["conditional_flow_dispositions"]),
        ("margin-components.csv", analysis["margin_components"]),
    ):
        outputs[filename] = csv_bytes(rows)
    for name, body in outputs.items():
        frozen_write(out / name, body)
    paths = [f"{DATA}/selected-aggregates.json", f"{DATA}/selection-review.json",
             "scripts/package-civic-estimates.py", "scripts/test-package-civic-estimates.py"]
    contents = {path: (ROOT / path).read_bytes() for path in paths}
    contents.update({f"{DATA}/output/{name}": body for name, body in outputs.items()})
    contents["REPRODUCTION.txt"] = (
        "Python>=3.9, standard library only. Verify checksums.json, then run:\n"
        "python3 scripts/test-package-civic-estimates.py\n"
        "python3 scripts/package-civic-estimates.py\n"
        "All complete selected aggregate inputs, query outputs, tests and code are included.\n"
        "NORC Civic Health and Elections Project 2026; supplied public-use CSV/codebook\n"
        "hashes and source URLs are in selected-aggregates.json. No respondent records,\n"
        "identifiers, source documents or private fine cells are redistributed.\n"
        "This reproduces selected sufficient-statistic analysis, not a fresh native CSV audit.\n"
        "Original private extraction was independently checked:113020rows/97700jointcells/\n"
        "3908decompositions/246204checks. The public selection combines Other/unknown current\n"
        "choices; full source-frame unknowns remain in all overall denominators.\n"
        "These are exploratory SOURCE-WEIGHTED estimates, not administratively observed\n"
        "turnout, nationally representative population estimates or original-coalition rates.\n"
        "The exact CHEP_WEIGHT target/calibration and field period remain unqualified;\n"
        "a questionnaire date is not a field period. Model nonvoter is not measured staying\n"
        "home. Choices mix reported and intended votes; prior choices are recalled.\n"
        "N means no recalled vote in the prior contest, not no ballot/first-ever/new eligibility.\n"
        "Pooled source is not certified national; current demographics are not fixed cohorts.\n"
        "RUCC is county context; SEX is assigned-at-birth and distinct from GENDER3.\n"
        "Known-major-party margins use changing source denominators. Their exact denominator\n"
        "component is included; other/unresolved terms are explicitly combined publicly.\n"
        "No population scaling, reweighting to past partisan shares, design CIs, causal\n"
        "persuasion or downward state-to-county allocation. Eligibility/migration is unknown.\n"
        "Source-support selection followed analysis and is not preregistered or a precision/\n"
        "anonymity guarantee. Every withheld conditional row has an explicit disposition.\n"
        "Attribution to NORC does not imply endorsement or a native-document redistribution license.\n"
    ).encode()
    contents["checksums.json"] = encoded({
        path: {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
        for path, body in sorted(contents.items())
    })
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, body in sorted(contents.items()):
            member = zipfile.ZipInfo(path, date_time=(2026, 11, 8, 0, 0, 0))
            member.external_attr = 0o100644 << 16
            archive.writestr(member, body, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    archive_body = buffer.getvalue()
    frozen_write(out / "complete-analysis.zip", archive_body)
    metadata = {
        "version": VERSION, "file": "complete-analysis.zip",
        "bytes": len(archive_body), "sha256": hashlib.sha256(archive_body).hexdigest(),
        "members": len(contents), "complete_selected_queries_inputs_and_code": True,
        "raw_respondent_data_included": False, "population_validation": False,
        "participation_rows": len(analysis["participation"]),
        "conditional_rows": len(analysis["conditional_flows"]),
        "dispositions": len(analysis["conditional_flow_dispositions"]),
        "margin_comparisons": len(analysis["margin_components"]),
    }
    frozen_write(out / "download.json", encoded(metadata))
    print(json.dumps(metadata))


if __name__ == "__main__":
    package()
