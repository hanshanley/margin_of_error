"""Export scoped 2024/2022 MEDSL-origin House counts, preserving withheld observations."""

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
YEARS = ("2024", "2022")
SOURCE_FIELDS = ("source", "office", "state_po", "year")
PROVENANCE = ROOT / "data/county-source-reviews/20261105-historical-provenance-01"
spec = importlib.util.spec_from_file_location("historical", Path(__file__).with_name("review-historical-county-results.py"))
historical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(historical)


def source_key(row):
    return tuple(row[field] for field in SOURCE_FIELDS)


def build_tables(rows, summaries, sources, qa):
    references, source_audit = historical.provenance(rows, sources)
    selected_sources = [row for row in sources if row["office"] == "house"
                        and row["origin"] == "medsl" and row["year"] in YEARS]
    source_keys = {source_key(row) for row in selected_sources}
    selected = [row for row in rows if source_key(row) in source_keys]
    county_keys = {historical.key(row) for row in selected}
    selected_summaries = [row for row in summaries if historical.key(row) in county_keys]
    report, parties, integer_rows, audit = historical.reconcile(selected, selected_summaries)
    qa_index = defaultdict(set)
    for row in qa:
        if "HE" in row["sample"].split("/"):
            qa_index[(row["year"], row["cty_fips"].zfill(5))].add("publisher_qa:" + row["test"])
    accepted_keys = set()
    for row in report:
        reasons = set(filter(None, row["withheld_reasons"].split(";")))
        reasons.update(qa_index[(row["year"], row["county_fips"])])
        if (row["year"], row["state_code"]) == ("2022", "NJ"):
            reasons.add("correction_log_100:district_totals_repeated_in_counties")
        if (row["year"], row["county_fips"]) == ("2022", "28163"):
            reasons.add("correction_log_101:unresolved_yazoo_county")
        row["withheld_reasons"] = ";".join(sorted(reasons))
        row["accepted_for_scoped_export"] = not reasons
        row["fully_complete"] = False
        row["map_approved"] = False
        if not reasons:
            accepted_keys.add((row["year"], row["office"], row["state_code"], row["county_fips"]))
    accepted = [row for row in integer_rows if historical.key(row) in accepted_keys]
    withheld = [row for row in selected if historical.key(row) not in accepted_keys]
    parties = [row for row in parties if
               (row["year"], row["office"], row["state_code"], row["county_fips"]) in accepted_keys]
    state_parties, state_counties = Counter(), defaultdict(set)
    for row in parties:
        identity = row["year"], row["office"], row["state_code"], row["party"], row["party_group"]
        state_parties[identity] += row["votes"]
        state_counties[identity[:3]].add(row["county_fips"])
    state_rows = [dict(zip(("year", "office", "state_code", "party", "party_group"), identity),
                      votes=votes, reviewed_counties=len(state_counties[identity[:3]]),
                      scope="sum_of_reviewed_counties_not_certified_state_total", fully_complete=False)
                  for identity, votes in sorted(state_parties.items(), key=lambda item: (-int(item[0][0]), item[0][1:]))]
    year_rows = []
    for year in YEARS:
        source_rows = [row for row in selected if row["year"] == year]
        accepted_rows = [row for row in accepted if row["year"] == year]
        county_rows = [row for row in report if row["year"] == year]
        year_rows.append(dict(year=year, office="house", source_states=len({r["state_po"] for r in source_rows}),
            reviewed_states=len({r["state_po"] for r in accepted_rows}), source_candidate_rows=len(source_rows),
            reviewed_candidate_rows=len(accepted_rows), withheld_candidate_rows=len(source_rows) - len(accepted_rows),
            source_counties=len(county_rows), reviewed_counties=sum(r["accepted_for_scoped_export"] for r in county_rows),
            withheld_counties=sum(not r["accepted_for_scoped_export"] for r in county_rows),
            reviewed_candidate_votes=sum(int(r["votes"]) for r in accepted_rows),
            fully_complete=False, map_approved=False))
    state_coverage = []
    for year in YEARS:
        for code in sorted(historical.CODES):
            source_rows = [r for r in selected if (r["year"], r["state_po"]) == (year, code)]
            accepted_rows = [r for r in accepted if (r["year"], r["state_po"]) == (year, code)]
            county_rows = [r for r in report if (r["year"], r["state_code"]) == (year, code)]
            state_coverage.append(dict(year=year, office="house", state_code=code,
                status="reviewed_partial_county_download" if accepted_rows else
                "all_scoped_counties_withheld" if source_rows else "outside_selected_source_origin_or_missing",
                source_candidate_rows=len(source_rows), reviewed_candidate_rows=len(accepted_rows),
                source_counties=len(county_rows),
                reviewed_counties=sum(r["accepted_for_scoped_export"] for r in county_rows),
                withheld_counties=sum(not r["accepted_for_scoped_export"] for r in county_rows),
                fully_complete=False, map_approved=False))
    audit.update(years=year_rows, input_rows=len(selected), reviewed_candidate_rows=len(accepted),
        withheld_candidate_rows=len(withheld), reviewed_counties=len(accepted_keys),
        full_archive_source_reference_review=source_audit,
        literal_parties=sorted({row["party"] for row in selected}),
        native_quality_flags=dict(Counter(row["quality_flag"] for row in selected)),
        pinned_qa_records=len(qa), new_maps_approved=False, candidate_votes_are_not_ballots_or_turnout=True)
    return {
        "source-candidate-party-lines.csv": selected,
        "reviewed-candidate-party-lines.csv": accepted,
        "withheld-candidate-party-lines.csv": withheld,
        "reviewed-county-party-totals.csv": parties,
        "reviewed-state-party-sums.csv": state_rows,
        "county-review.csv": report,
        "year-coverage.csv": year_rows,
        "state-coverage.csv": state_coverage,
        "scoped-sources.csv": selected_sources,
        "source-reference-review.csv": [r for r in references if source_key(r) in source_keys],
    }, audit


def export(archive_path, source_review, output):
    acquisition = json.loads(historical.ACQUISITION.read_bytes())
    raw = archive_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != acquisition["complete_download_sha256"]:
        raise ValueError("Changed pinned original historical archive")
    receipts = json.loads((source_review / "receipts.json").read_bytes())
    for receipt in receipts:
        content = (source_review / receipt["path"]).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if (receipt["source_commit"] != acquisition["source_commit"]
                or blob != receipt["git_blob_sha"] or len(content) != receipt["bytes"]
                or hashlib.sha256(content).hexdigest() != receipt["sha256"]):
            raise ValueError("Changed pinned source-review original")
    license_review = json.loads((PROVENANCE / "primary-source-review.json").read_bytes())
    registry = PROVENANCE / "originals/datacite"
    registry_receipts = {r["doi"].upper(): r for r in json.loads((registry / "receipts.json").read_bytes())}
    declarations = {}
    for year in YEARS:
        doi = license_review["dataset_dois_by_year"][year]
        receipt = registry_receipts[doi.upper()]
        content = (registry / receipt["response_file"]).read_bytes()
        metadata = json.loads(content)["data"]["attributes"]
        if (hashlib.sha256(content).hexdigest() != receipt["sha256"]
                or metadata["doi"].upper() != doi.upper()
                or not any("House" in title["title"] and year in title["title"] for title in metadata["titles"])
                or not any(right.get("rightsIdentifier") == "cc0-1.0" for right in metadata["rightsList"])):
            raise ValueError("Missing or changed scoped House CC0 declaration")
        declarations[year] = dict(doi=doi, titles=metadata["titles"], rights=metadata["rightsList"])
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt original historical archive")

        def table(name):
            return list(csv.DictReader(io.StringIO(archive.read(name).decode("utf-8-sig"), newline="")))

        qa = list(csv.DictReader(io.StringIO((source_review / "R/output/qa_medsl_sweep_flags.csv").read_text())))
        tables, audit = build_tables(table("us_county_results_long.csv"), table("us_county_results_summary.csv"),
                                     table("SOURCES.csv"), qa)
        corrections = archive.read("data_corrections_log.csv")
    audit.update(source_commit=acquisition["source_commit"],
        complete_original_url=acquisition["complete_download_url"],
        complete_original_sha256=acquisition["complete_download_sha256"],
        scope="2024/2022 House only; native source origin=medsl; other origins/offices/years excluded.",
        compilation_attribution="Paul Heideman (2026), U.S. county-level election results, v1.0.0, CC BY 4.0.",
        upstream_attribution="MIT Election Data and Science Lab; dataset DOI/title/CC0 declarations below.",
        dataset_declarations=declarations,
        changes="Selected MEDSL-origin House rows; reconciled full county vectors; withheld known QA anomalies; "
        "summed literal compiler party labels without recoding. Official replacement sources are outside this scope.",
        limitations=[
            "Reviewed means scoped arithmetic/provenance checks and known-anomaly exclusions, not official certification.",
            "All raw scoped rows are retained; withheld rows never enter reviewed county or state aggregates.",
            "State sums contain only reviewed counties, not guaranteed complete statewide or district totals.",
            "Party/candidate labels are the compiler's literals, not independently verified original ballot labels.",
            "Preserve surname_only/initials_only flags; no identities or zeros are invented.",
            "Compiler 2024 Oregon major-party overrides use secondary Wikipedia facts; code and attribution retained.",
            "Generated candidate_name_overrides.csv is not in the pinned repository; no complete name audit is claimed.",
            "The pinned QA CSV has 53 records, while correction-log prose says 64; Yazoo 2022 is separately withheld.",
            "NJ 2022 and 2024 are already official-source replacements, outside this MEDSL-only scope. "
            "The old NJ 2022 MEDSL duplication warning is not a defect in the current official-source rows.",
            "Native Montana 2022 believed_cc0 remains unchanged; the 2022 House DOI independently declares CC0.",
            "No new county maps, historical boundary crosswalks, turnout or demographic participation estimates.",
            "Full mixed-source original archive is referenced by URL and checksum, not mirrored under a blanket license.",
        ])
    output.mkdir(parents=True, exist_ok=False)
    for name, records in tables.items():
        (output / (name + ".gz")).write_bytes(gzip.compress(historical.csv_bytes(records), mtime=0))
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "checksums.json").write_text(json.dumps({
        path.name: dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(output.iterdir())}, indent=2) + "\n")
    with zipfile.ZipFile(output / "complete-historical-house.zip", "w", zipfile.ZIP_DEFLATED) as package:
        for path in sorted(output.iterdir()):
            if path.suffix != ".zip":
                package.write(path, path.name)
        for path in sorted(source_review.rglob("*")):
            if path.is_file():
                package.write(path, "originals/compiler/" + path.relative_to(source_review).as_posix())
        for path in sorted(PROVENANCE.rglob("*")):
            if path.is_file():
                package.write(path, path.relative_to(ROOT).as_posix())
        for path in [Path(__file__), Path(historical.__file__), historical.ACQUISITION]:
            package.write(path, path.relative_to(ROOT).as_posix())
        package.writestr("originals/compiler/data_corrections_log.csv", corrections)
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--source-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.source_archive, args.source_review, args.output), indent=2))
