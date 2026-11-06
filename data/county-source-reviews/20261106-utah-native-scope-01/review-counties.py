import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile


HERE = Path(__file__).resolve().parent
STATIC = ("source-qualification.json", "methods.json", "review-counties.py", "test_review_counties.py")


def review(source):
    reports = source["reports"]
    catalog = source["native_county_catalog"]
    names = [row["county_literal"] for row in catalog]
    if len(names) != 29 or len(set(names)) != 29:
        raise ValueError("Incomplete or repeated native county inventory")
    if len(reports) != 26 or len({row["source_ordinal"] for row in reports}) != 26:
        raise ValueError("Incomplete or repeated native report inventory")
    if any(source[key] is not False for key in
           ("generic_turnout_approved", "county_fips_join_approved", "map_approved", "context22_modified")):
        raise ValueError("Source qualification is not geographic or generic turnout approval")
    latest = {}
    observations = []
    receipts = []
    by_ordinal = {row["source_ordinal"]: row for row in reports}
    for row in reports:
        county = row["county_literal"]
        if county not in names or row["analysis_rate_approved"] or row["map_approved"] or row["native_fips"] is not None:
            raise ValueError("Invalid native county or invented approval")
        if row["source_receipt"]["status"] != 200:
            raise ValueError("Unacquired report cannot supply native observations")
        total = row["fields"]["ballots_counted"]
        qualified = row["counted_total_scope_review"] == "native_counted_total"
        if qualified:
            if not row["native_counted_label"] or type(total) is not int or total < 0:
                raise ValueError("Missing or invalid native counted-total observation")
        elif total is not None:
            raise ValueError("Received, processed, scanned, daily or credited values are not counted totals")
        if row["latest_selection"]:
            if county in latest:
                raise ValueError("Multiple latest reports would double-count a county")
            latest[county] = row
        else:
            target = by_ordinal.get(row.get("superseded_for_latest_selection_by_ordinal"))
            if target is None or target["county_literal"] != county or not target["latest_selection"]:
                raise ValueError("Invalid superseded report relationship")
        receipt = row["source_receipt"]
        receipts.append(dict(source_ordinal=row["source_ordinal"], native_county=county,
            report_name=receipt["report_name"], source_updated_literal=row["source_updated_literal"],
            source_timezone_literal=row["source_timezone_literal"],
            upload_date_literal=receipt.get("upload_date_literal"),
            requested_url=receipt["requested_url"], final_url=receipt["final_url"],
            bytes=receipt["bytes"], sha256=receipt["sha256"],
            latest_selection=row["latest_selection"],
            counted_total_scope_review=row["counted_total_scope_review"]))
        for scope in ("fields", "reconciliation", "historical_column", "historical_scanned_observation",
                      "historical_tabulated"):
            values = row.get(scope)
            if values is None:
                continue
            groups = values if isinstance(values, list) else [values]
            for index, group in enumerate(groups):
                for field, value in group.items():
                    if value is not None and type(value) not in (str, int, float):
                        raise ValueError("Unsupported native field type")
                    observations.append(dict(source_ordinal=row["source_ordinal"], native_county=county,
                        scope=scope, scope_index=index, field=field, value=value,
                        value_state="missing" if value is None else "observed",
                        value_type="null" if value is None else type(value).__name__))
    if len(latest) != 25 or sorted(set(names) - set(latest)) != source["counties_without_declared_ballot_statistics"]:
        raise ValueError("County source coverage changed")
    counties = []
    for name in sorted(names):
        row = latest.get(name)
        qualified = row is not None and row["counted_total_scope_review"] == "native_counted_total"
        counties.append(dict(native_county=name, native_status="Unofficial",
            source_ordinal=row["source_ordinal"] if row else None,
            ballots_counted=row["fields"]["ballots_counted"] if qualified else None,
            registered_voters=row["fields"]["registered_voters"] if row else None,
            native_counted_label=row["native_counted_label"] if row else None,
            native_denominator_label=row["native_denominator_label"] if row else None,
            source_updated_literal=row["source_updated_literal"] if row else None,
            source_timezone_literal=row["source_timezone_literal"] if row else None,
            source_scope_review=row["counted_total_scope_review"] if row else "missing_declared_report",
            native_fips=None, analysis_rate_approved=False, map_approved=False))
    registrations = source["registration_review"]["native_rows"]
    pairs = [(row["county_literal"], row["party_literal"]) for row in registrations]
    if len(registrations) != 228 or len(set(pairs)) != 228:
        raise ValueError("Incomplete or repeated native registration rows")
    party_totals = {}
    for row in registrations:
        if row["county_literal"] + " County" not in names or type(row["active_registered_voters"]) is not int:
            raise ValueError("Invalid registration affiliation observation")
        party = row["party_literal"]
        party_totals[party] = party_totals.get(party, 0) + row["active_registered_voters"]
    state_rows = source["registration_review"]["native_state_party_rows"]
    for row in state_rows:
        observed = sum(party_totals.values()) if row["party_literal"] == "Total" else party_totals.get(row["party_literal"], 0)
        if observed != row["active"]:
            raise ValueError("Independent county/party active registration sum changed")
    counted = [row for row in counties if row["ballots_counted"] is not None]
    if len(counted) != 19 or sum(row["registered_voters"] is not None for row in counted) != 18:
        raise ValueError("Counted-total or same-report denominator coverage changed")
    return dict(counties=counties, observations=observations, receipts=receipts,
                registrations=registrations, state_registrations=state_rows, catalog=catalog)


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def build(output):
    output = Path(output)
    if output.exists():
        raise ValueError("Refusing to overwrite an existing output")
    source = json.loads((HERE / "source-qualification.json").read_text())
    parsed = review(source)
    output.mkdir(parents=True)
    for name in STATIC:
        shutil.copyfile(HERE / name, output / name)
    filenames = dict(counties="county-participation.csv", observations="source-native-observations.csv",
        receipts="source-reports.csv", registrations="county-party-registrations.csv",
        state_registrations="state-party-registrations.csv", catalog="native-county-catalog.csv")
    for key, filename in filenames.items():
        rows = parsed[key]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        (output / filename).write_bytes(stream.getvalue().encode())
    audit = dict(row_counts={filenames[key]: len(rows) for key, rows in parsed.items()},
        source_counts=source["counts"], native_counted_total_candidates=19,
        same_report_registration_candidates=18,
        native_parent_arithmetic_discrepancies=source["registration_review"]["native_parent_arithmetic_discrepancies"],
        discrepancies_not_corrected=True, county_party_absences_not_filled=True,
        backend_zero_placeholders_not_participation=True,
        latest_davis_selected_without_adding_earlier_report=True,
        six_scope_withholds_and_four_missing_reports_preserved=True,
        no_registration_pdf_denominator_substitution=True,
        no_mode_or_provisional_double_counting=True,
        native_timezone_missing=True, native_fips_missing=True,
        analysis_rate_approvals=0, map_approvals=0,
        scope="Complete portable query over all reviewed numerical facts in the qualification input, "
              "including all 26 report observations, 29 county records, native historical fields and "
              "228 registration-affiliation records. Not a complete raw-source or operational-workbook mirror, "
              "candidate-results dataset, certified turnout dataset, geographic join or live explorer update.")
    (output / "audit.json").write_bytes(encode(audit))
    paths = sorted(path for path in output.iterdir() if path.is_file())
    manifest = dict(files=[dict(path=path.name, bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths],
        scope="All numerical inputs, complete tables, methods and executable query/tests. "
              "Manifest and ZIP excluded from hashes to prevent self-reference.")
    (output / "checksums.json").write_bytes(encode(manifest))
    with zipfile.ZipFile(output / "complete-query.zip", "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path in sorted(output.iterdir()):
            if path.name == "complete-query.zip":
                continue
            entry = zipfile.ZipInfo(path.name, date_time=(2026, 11, 6, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, path.read_bytes())
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.output), indent=2))
