#!/usr/bin/env python3
"""Review Monroe's complete 2026 originals without reconstructing suppressed votes."""

import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import html
import io
import json
from pathlib import Path
import re
import zipfile


SOURCE = "https://enr.electionsfl.org/MON/4109/"
EXPORTS = "https://s3.amazonaws.com/results.voterfocus.com/enr/exports/reports/MON/4109/"
CONTEST = "Representative in Congress Dist 28"
MODES = ("Provisional Votes", "Mail Votes", "Early Votes", "Election Day Votes")
SUMMARY_FIELDS = ["Contest", "Candidate Issue", "Party", *MODES, "Total Votes", "% of Total Votes"]
PRECINCT_FIELDS = SUMMARY_FIELDS[:3] + ["Precinct Name"] + SUMMARY_FIELDS[3:]
RELEASE = ("https://github.com/hanshanley/margin_of_error/releases/download/"
           "voter-precinct-florida-monroe-20261105/complete-florida-monroe-2026.zip")


def count(value, suppressed=False):
    if suppressed and value == "-":
        return None
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]*", value):
        raise ValueError("Invalid or missing Florida native count")
    return int(value)


def read_table(raw, precinct=True):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    if reader.fieldnames != (PRECINCT_FIELDS if precinct else SUMMARY_FIELDS):
        raise ValueError("Wrong Florida native CSV schema")
    rows = list(reader)
    if not rows or any(set(row) != set(reader.fieldnames) or None in row.values() for row in rows):
        raise ValueError("Incomplete Florida native CSV")
    return rows


def vector(row):
    total = count(row["Total Votes"])
    modes = {mode: count(row[mode], suppressed=True) for mode in MODES}
    known = sum(value for value in modes.values() if value is not None)
    if known > total or (all(value is not None for value in modes.values()) and known != total):
        raise ValueError("Florida native mode vector differs from total")
    return dict(total=total, modes=modes)


def review(rows, summary, expected_units=33):
    expected, grouped, all_rows = {}, defaultdict(list), []
    for row in summary:
        identity = tuple(row[field] for field in SUMMARY_FIELDS[:3])
        if not all(identity[:2]) or identity in expected:
            raise ValueError("Duplicate or missing Florida summary identity")
        expected[identity] = vector(row)
    seen = set()
    for number, row in enumerate(rows, 2):
        identity = tuple(row[field] for field in SUMMARY_FIELDS[:3])
        unit = row["Precinct Name"]
        if not unit or not all(identity[:2]) or (*identity, unit) in seen:
            raise ValueError("Duplicate or missing Florida precinct candidate identity")
        if identity[0].startswith("Representative in Congress") and identity[0] != CONTEST:
            raise ValueError("Wrong Florida House contest identity")
        seen.add((*identity, unit))
        votes = vector(row)
        grouped[identity].append((unit, votes))
        all_rows.append(dict(source_csv_row=number, native=row, parsed_votes=votes))
    if set(expected) != set(grouped):
        raise ValueError("Florida precinct/summary candidate identities differ")
    modes_audit, contests = [], defaultdict(list)
    for identity, values in grouped.items():
        target = expected[identity]
        if sum(v["total"] for _, v in values) != target["total"]:
            raise ValueError("Florida precinct candidate total differs from independent summary")
        contests[identity[0]].append({unit for unit, _ in values})
        for mode in MODES:
            missing = sum(v["modes"][mode] is None for _, v in values)
            known = sum(v["modes"][mode] for _, v in values if v["modes"][mode] is not None)
            native = target["modes"][mode]
            if native is not None and (known > native or (not missing and known != native)):
                raise ValueError("Florida precinct mode total differs from independent summary")
            modes_audit.append(dict(contest=identity[0], candidate=identity[1], party=identity[2],
                mode=mode, known_precinct_votes=known, suppressed_precinct_fields=missing,
                native_summary_votes=native,
                status="reconciled" if not missing and native is not None else "withheld_suppressed"))
    if any(any(units != sets[0] for units in sets[1:]) for sets in contests.values()):
        raise ValueError("Incomplete Florida contest candidate/precinct matrix")
    house = {identity: values for identity, values in grouped.items() if identity[0] == CONTEST}
    if (len(house) != 3 or {identity[2] for identity in house} != {"DEM", "REP", "NPA"}
            or len({identity[1] for identity in house}) != len(house)):
        raise ValueError("Wrong Florida House candidate/party scope")
    units = contests[CONTEST][0]
    if len(units) != expected_units:
        raise ValueError("Florida House precinct set differs from source reporting scope")
    by_unit = defaultdict(list)
    for identity, values in house.items():
        for unit, votes in values:
            by_unit[unit].append((identity, votes))
    results = []
    for unit in sorted(units):
        candidates = by_unit[unit]
        parties = {identity[2]: votes["total"] for identity, votes in candidates}
        suppressed = any(value is None for _, votes in candidates for value in votes["modes"].values())
        results.append(dict(year=2026, state_code="FL", county_fips="12087", county_name="Monroe",
            key="FL|12087|" + unit, source_unit_id=unit, source_precinct_label=unit,
            source_office=CONTEST, source_district="28", source_unit_kind="native_precinct_name",
            democratic_votes=parties["DEM"], republican_votes=parties["REP"],
            other_votes=parties["NPA"], contest_votes=sum(parties.values()),
            candidate_votes=json.dumps({identity[1]: votes["total"] for identity, votes in candidates}),
            quality_flags="native_mode_suppression_retained" if suppressed else "",
            source_url=SOURCE + "Reports/"))
    return results, all_rows, dict(
        all_office_candidate_precinct_rows=len(rows), all_office_summary_candidates=len(expected),
        all_office_contests=len(contests), all_office_candidate_totals="reconciled",
        native_house_precinct_names=sorted(units), mode_comparisons=modes_audit,
        suppressed_native_mode_fields=sum(value is None for row in all_rows
                                         for value in row["parsed_votes"]["modes"].values()))


def original(cache, name, url):
    raw = (cache / name).read_bytes()
    receipt = json.loads((cache / (name + ".source.json")).read_text())
    if (receipt["status_code"] != 200 or receipt["url"] != url or receipt["resolved_url"] != url
            or receipt["bytes"] != len(raw) or receipt["sha256"] != hashlib.sha256(raw).hexdigest()):
        raise ValueError("Changed, failed or wrong-election Florida original receipt: " + name)
    return raw, receipt


def html_statistics(raw):
    text = html.unescape(raw.decode("utf-8"))
    if ('//s3.amazonaws.com/vr-enr/MON/wf_banner.jpg' not in text
            or not re.search(r'id="ElectionName">\s*<h1>November 3, 2026 General</h1>', text)
            or "<h2>Election Date: 11/3/2026</h2>" not in text):
        raise ValueError("Wrong Florida county or election identity")
    values = {}
    for label, field in (("Registered Voters", "registered"), ("Ballots Cast", "ballots"),
                         ("Voter Turnout", "source_reported_percent")):
        found = re.findall(r'TurnoutLabel">\s*' + label + r':\s*</div>\s*'
                           r'<div[^>]*TurnoutValue">([^<]+)</div>', text)
        if len(found) != 1:
            raise ValueError("Missing or repeated Florida county participation field")
        value = found[0].strip()
        if field == "source_reported_percent":
            if not re.fullmatch(r"[0-9]+\.[0-9]{2}%", value) or not 0 <= float(value[:-1]) <= 100:
                raise ValueError("Invalid Florida reported turnout percentage")
            values[field] = value
        else:
            if not re.fullmatch(r"[0-9]{1,3}(?:,[0-9]{3})*|[0-9]+", value):
                raise ValueError("Invalid Florida county count")
            values[field] = count(value.replace(",", ""))
    reporting = re.findall(r'PrecinctsValue">\s*([0-9]+)\s*/\s*([0-9]+)\s*</div>', text)
    if reporting != [("33", "33")] or values["ballots"] > values["registered"]:
        raise ValueError("Wrong Florida reporting scope or county count relationship")
    return values


def load_originals(cache):
    originals, receipts = {}, {}
    for name in ("official-reports.html", "official-summary.html"):
        suffix = "Reports/" if name == "official-reports.html" else "Summary/"
        originals[name], receipts[name] = original(cache, name, SOURCE + suffix)
    reports = html.unescape(originals["official-reports.html"].decode("utf-8"))
    for kind in ("CandidateResultsbyPrecinctandParty", "CandidateSummaryResultsbyParty"):
        for extension in ("csv", "pdf"):
            matches = list(cache.glob(kind + "_*." + extension))
            if len(matches) != 1:
                raise ValueError("Missing or ambiguous complete Florida original")
            name = matches[0].name
            if not re.fullmatch(kind + r"_2026-11-03T22:29:4[78]_[0-9a-f-]{36}\." + extension, name):
                raise ValueError("Wrong Florida native report election timestamp")
            url = EXPORTS + name
            if 'href="' + url + '"' not in reports:
                raise ValueError("Florida original not declared by native reports index")
            originals[name], receipts[name] = original(cache, name, url)
            if extension == "pdf" and not originals[name].startswith(b"%PDF-"):
                raise ValueError("Florida advertised PDF is not a PDF")
    statistics = [html_statistics(originals[name]) for name in ("official-reports.html", "official-summary.html")]
    if statistics[0] != statistics[1]:
        raise ValueError("Florida county participation source snapshots differ")
    return originals, receipts, statistics[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable Florida review")
    originals, receipts, county_counts = load_originals(args.cache_directory)
    precinct_name = next(name for name in originals if name.startswith("CandidateResults") and name.endswith(".csv"))
    summary_name = next(name for name in originals if name.startswith("CandidateSummary") and name.endswith(".csv"))
    results, native, reconciliation = review(
        read_table(originals[precinct_name]), read_table(originals[summary_name], precinct=False))
    participation = [dict(year=2026, state_code="FL", county_fips="12087", county_name="Monroe",
        source_unit_kind="county", source_url=SOURCE + "Summary/", source_certified=False,
        **county_counts, denominator_scope="source_county_registered_voters_definition_not_crosswalked",
        basis="Native county counts and displayed percentage only; not precinct or demographic turnout.",
        quality_flags=["unofficial", "county_only", "precinct_denominators_not_acquired"])]
    totals = {field: sum(row[field] for row in results) for field in
              ("democratic_votes", "republican_votes", "other_votes", "contest_votes")}
    if totals["contest_votes"] > county_counts["ballots"]:
        raise ValueError("Florida House candidate votes exceed native county ballots")
    audit = dict(year=2026, state_code="FL", county_fips="12087", county_name="Monroe",
        complete="no", source_election="November 3, 2026 General", source_election_date="2026-11-03",
        source_certified=False, reporting_units=len(results), counties=1, candidate_results="acquired_reconciled",
        participation="county_counts_only_precinct_denominators_not_acquired",
        boundaries="election_year_reference_pending", join="withheld",
        validation="all_office_native_candidate_totals_passed_suppressed_modes_retained",
        publication="full_counts_download_only", source_url=SOURCE + "Reports/",
        complete_download_url=RELEASE, native_original_sources=len(originals),
        native_original_bytes=sum(map(len, originals.values())), candidate_totals=totals,
        county_ballots=county_counts["ballots"], county_registered=county_counts["registered"],
        rates_available=0, rates_withheld=len(results), reconciliation=reconciliation,
        notes="Monroe County only, not statewide Florida. All native all-office candidate totals reconcile "
              "to the separately exported county summary. Full precinct labels are identities; shared "
              "polling-place names are not merged. Dashes remain missing source-suppressed vote modes; "
              "no residual allocation or imputed zeros. Precinct participation denominators and explicitly "
              "2026 geometry are not established. Separate native county participation counts are not "
              "precinct or demographic turnout. Originals include both full CSVs, both full PDFs and "
              "both source HTML pages. No map, precinct rate or statewide completion is claimed.",
        next_action="Seek official explicitly 2026 Monroe geometry and independent precinct ballot/"
                    "registration definitions. Continue other Florida counties, retaining Palm Beach's "
                    "explicitly unpublished precinct endpoint and county-only scope separately.")
    args.output.mkdir(parents=True)

    def save(name, value):
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        (args.output / name).write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)

    (args.output / "originals").mkdir()
    for name, raw in originals.items():
        (args.output / "originals" / (name + ".gz")).write_bytes(gzip.compress(raw, mtime=0))
    save("sources.json", receipts)
    save("native-rows.json.gz", native)
    save("participation.json.gz", participation)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(results[0]))
    writer.writeheader()
    writer.writerows(results)
    (args.output / "results.csv.gz").write_bytes(gzip.compress(buffer.getvalue().encode(), mtime=0))
    save("audit.json", audit)
    save("checksums.json", {str(path.relative_to(args.output)): dict(bytes=path.stat().st_size,
         sha256=hashlib.sha256(path.read_bytes()).hexdigest())
         for path in sorted(args.output.rglob("*")) if path.is_file()})
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(str(path.relative_to(args.output)), date_time=(2026, 11, 5, 0, 0, 0))
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())
    print(json.dumps({key: audit[key] for key in ("reporting_units", "candidate_totals",
        "county_ballots", "county_registered", "native_original_sources", "native_original_bytes")}, indent=2))


if __name__ == "__main__":
    main()
