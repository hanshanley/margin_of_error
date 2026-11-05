"""Reconcile South Dakota 2026 House exports; keep vote-center denominators separate."""

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from bs4 import BeautifulSoup
import openpyxl

OFFICE = "United States Representative"
SOURCE = "https://electionresults.sd.gov/ResultsExport.aspx"
TURNOUT = "https://electionresults.sd.gov/VoterTurnoutDetails.aspx?map=TURN"
RELEASE = ("https://github.com/hanshanley/margin_of_error/releases/download/"
           "voter-precinct-south-dakota-20261105/complete-south-dakota-2026-source-review.zip")


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Missing South Dakota source label")
    return " ".join(value.split())


def count(value):
    if type(value) is not int or value < 0:
        raise ValueError("Missing or invalid South Dakota count; not zero")
    return value


def house_sheet(rows, source, reported):
    if (rows[0][0] != "2026 Unofficial General Election Results"
            or rows[1][0] != "State of South Dakota"
            or rows[2][0] != (f"Precincts {reported} of {reported} Reporting "
                              f"(Precincts Partially Reported: 0/{reported})")
            or text(rows[6][0]) != OFFICE or rows[6][1] not in {"County", "Precinct"}):
        raise ValueError("Wrong election, reporting status or House export")
    candidates = [text(c) for c in rows[6][2:]]
    if len(candidates) != len(set(candidates)):
        raise ValueError("Ambiguous South Dakota candidate columns")
    records, totals = [], []
    for number, row in enumerate(rows[7:], 8):
        if all(v is None for v in row):
            continue
        if len(row) != len(candidates) + 2:
            raise ValueError("Truncated South Dakota House row")
        label = text(row[1])
        record = dict(label=label, raw_label=row[1], source_row=number,
                      votes={c: count(v) for c, v in zip(candidates, row[2:])})
        (totals if label == "TOTALS" else records).append(record)
    if (len(totals) != 1 or not records
            or any(sum(r["votes"][c] for r in records) != totals[0]["votes"][c] for c in candidates)):
        raise ValueError("South Dakota House rows do not reconcile to their source total")
    return dict(records=records, totals=totals[0]["votes"], source=source,
                source_county=rows[3][0] if rows[6][1] == "Precinct" else None)


def turnout_facts(html):
    soup = BeautifulSoup(html, "html.parser")
    for name, value in [("hidElectionType", "General"), ("hidElectionDate", "11/3/2026")]:
        field = soup.find("input", attrs={"name": "ctl00$" + name})
        if field is None or field.get("value") != value:
            raise ValueError("Wrong South Dakota turnout election")
    counties = []
    for heading in soup.select(".turnout-results-box-a"):
        county_label = heading.h1.get_text(" ", strip=True)
        code = heading.select_one("input[countyid]")["countyid"]
        block = heading.parent.find_next_sibling()
        if block.get("id") != "countyturnout" + code:
            raise ValueError("South Dakota county turnout block mismatch")
        records = []
        for number, row in enumerate(block.select(":scope > .odd,:scope > .even"), 1):
            values = {}
            for field, selector in [("ballots", ".county-cast"), ("registered", ".county-counted")]:
                element = row.select_one(selector)
                raw = element.get_text(strip=True) if element else ""
                if not re.fullmatch(r"[0-9]+(?:,[0-9]{3})*", raw):
                    raise ValueError("Missing or invalid South Dakota displayed count")
                values[field] = int(raw.replace(",", ""))
            raw_label = row.select_one(".county-precinct").get_text(" ", strip=True)
            records.append(dict(label=text(raw_label), raw_label=raw_label,
                                source_row=number, **values))
        is_center = county_label.endswith(" (Vote Center)")
        counties.append(dict(code=code, county=county_label.removesuffix(" (Vote Center)"),
            raw_county=county_label, vote_center=is_center, records=records))
    if not counties or len({c["code"] for c in counties}) != len(counties):
        raise ValueError("Missing or duplicate South Dakota turnout counties")
    return dict(year=2026, election="General Election November 3, 2026",
        source_url=TURNOUT, source_html_sha256=hashlib.sha256(html).hexdigest(),
        extraction="All county headings, reporting labels and displayed ballot/registration counts; "
                   "HTML template/frontend code is not redistributed.",
        counties=counties)


def review(county_sheets, statewide, facts, api, catalog):
    if facts["year"] != 2026 or facts["election"] != "General Election November 3, 2026":
        raise ValueError("Wrong extracted South Dakota turnout election")
    counties = {c["code"]: c for c in facts["counties"]}
    summaries = {r["CountyID"]: r for r in api}
    if (len(counties) != len(facts["counties"]) or len(summaries) != len(api)
            or set(counties) != set(summaries) or set(counties) != set(county_sheets)):
        raise ValueError("South Dakota county scopes differ")
    parties = {}
    for candidate in catalog:
        if candidate["desc"] != OFFICE:
            continue
        name = text(candidate["name"])
        if name in parties or candidate["Party"] not in {"Democratic", "Republican", "Libertarian", "Independent"}:
            raise ValueError("Ambiguous or unknown official South Dakota House party")
        parties[name] = candidate["Party"]
    if set(parties) != set(statewide["totals"]) or not parties:
        raise ValueError("Official South Dakota candidate identities differ from the workbook")
    statewide_counties = {}
    for record in statewide["records"]:
        county = record["label"].removesuffix(" (Vote Center)")
        if county in statewide_counties:
            raise ValueError("Duplicate South Dakota statewide county")
        statewide_counties[county] = record
    if set(statewide_counties) != {c["county"] for c in counties.values()}:
        raise ValueError("South Dakota statewide/county workbook scopes differ")
    results, participation, audits = [], [], {}
    for code, county in sorted(counties.items()):
        summary, sheet = summaries[code], county_sheets[code]
        source, ballots = sheet["records"], county["records"]
        expected_county_label = county["county"] + (" (Vote Center)" if county["vote_center"] else "")
        if (summary["CountyName"] != expected_county_label
                or statewide_counties[county["county"]]["label"] != expected_county_label
                or sheet["source_county"] != county["county"] + " County"
                or sheet["totals"] != statewide_counties[county["county"]]["votes"]
                or set(sheet["totals"]) != set(parties)
                or not summary["IsReported"] or summary["PartialPrecincts"] != 0
                or summary["PrecinctsReporting"] != summary["TotalPrecincts"]
                or len(source) != summary["TotalPrecincts"]
                or Counter(r["label"] for r in source) != Counter(r["label"] for r in ballots)):
            raise ValueError("South Dakota county House/turnout scope or independent totals differ: "
                             + county["county"])
        if sum(count(r["ballots"]) for r in ballots) != count(summary["calcVoterTurnout"]):
            raise ValueError("South Dakota separate precinct ballots do not reconcile to the county API")
        duplicated = {label for label, n in Counter(r["label"] for r in source).items() if n > 1}
        registration_disagrees = (not county["vote_center"]
            and sum(count(r["registered"]) for r in ballots) != count(summary["Voters"]))
        if county["vote_center"] and any(count(r["registered"]) != count(summary["Voters"]) for r in ballots):
            raise ValueError("Unexpected South Dakota vote-center denominator scope")
        unique_source = {r["label"]: r for r in source if r["label"] not in duplicated}
        unique_ballots = {r["label"]: r for r in ballots if r["label"] not in duplicated}
        base = dict(year=2026, state_code="SD", county=county["county"], county_code=code,
                    reporting_unit_kind="vote_center" if county["vote_center"] else "source_precinct")
        for record in source:
            if set(record["votes"]) != set(parties):
                raise ValueError("South Dakota precinct candidate identities differ")
            groups = {party: sum(count(v) for c, v in record["votes"].items() if parties[c] == party)
                      for party in ["Democratic", "Republican"]}
            total = sum(record["votes"].values())
            key = f'SD|{code}|{record["label"]}'
            if record["label"] in duplicated:
                key += f'|workbook-row-{record["source_row"]}'
            results.append(dict(base, key=key, precinct=record["label"], raw_precinct=record["raw_label"],
                office="U.S. House", source_office=OFFICE, source_url=SOURCE,
                source_file=sheet["source"], source_row=record["source_row"],
                democratic_votes=groups["Democratic"], republican_votes=groups["Republican"],
                other_votes=total - sum(groups.values()), contest_votes=total,
                margin_pp=100 * (groups["Democratic"] - groups["Republican"]) / total if total else None,
                ballot_scope="Unofficial source reporting units, including explicitly marked vote centers "
                    "and combined labels; residential all-ballot precinct coverage not independently established.",
                quality_flags="ambiguous_reporting_unit_name" if record["label"] in duplicated else ""))
        for record in ballots:
            flags = []
            if county["vote_center"]:
                flags.append("county_registration_repeated_at_vote_centers_not_a_precinct_denominator")
            if record["label"] in duplicated:
                flags.append("ambiguous_reporting_unit_name_no_cross_source_row_pairing")
            if registration_disagrees:
                flags.append("county_registration_disagrees_with_api")
            if count(record["registered"]) < 25:
                flags.append("missing_or_small_source_registration_denominator")
            if record["ballots"] > record["registered"]:
                flags.append("ballots_exceed_source_registration")
            if (record["label"] in unique_source
                    and sum(unique_source[record["label"]]["votes"].values()) > record["ballots"]):
                flags.append("house_votes_exceed_separately_reported_ballots")
            key = f'SD|{code}|{record["label"]}'
            if record["label"] in duplicated:
                key += f'|turnout-row-{record["source_row"]}'
            participation.append(dict(base, key=key, precinct=record["label"],
                raw_precinct=record["raw_label"], source_row=record["source_row"], source_url=TURNOUT,
                ballots=record["ballots"], registered=record["registered"],
                denominator_scope="county_repeated_at_vote_centers" if county["vote_center"]
                    else "source_reporting_unit_registration",
                reported_pct=None if flags else 100 * record["ballots"] / record["registered"],
                basis="Unofficial ballots/source-registration fraction; not final, eligible-voter "
                      "or demographic turnout. Registration cutoff is not independently established.",
                quality_flags=flags))
        audits[code] = dict(county=county["county"], vote_center=county["vote_center"],
            reporting_rows=len(source), ballots=summary["calcVoterTurnout"],
            registrations=summary["Voters"], duplicate_reporting_labels=sorted(duplicated),
            registration_disagrees=registration_disagrees,
            unique_candidate_ballot_links=len(unique_ballots))
    if (sum(r["contest_votes"] for r in results) != sum(statewide["totals"].values())
            or len({r["key"] for r in results}) != len(results)
            or len({r["key"] for r in participation}) != len(participation)):
        raise ValueError("South Dakota statewide reconciliation or source-row identities failed")
    return results, participation, audits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable South Dakota review")
    receipts = json.loads((args.cache_directory / "sources.json").read_text())
    raw_sources = {}
    page_receipts = (json.loads((args.cache_directory / "source-page-receipts.json").read_text())
                     if (args.cache_directory / "source-page-receipts.json").exists() else {})
    for name, receipt in receipts.items():
        raw = (args.cache_directory / name).read_bytes()
        if len(raw) != receipt["bytes"] or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError("South Dakota source receipt mismatch: " + name)
        if name.endswith(".html"):
            page_receipts[name] = receipt
        elif name != "turnout-facts.json" and name.endswith((".xlsx", ".json", ".pdf")):
            raw_sources[name] = raw
    if (args.cache_directory / "turnout.html").exists():
        facts = turnout_facts((args.cache_directory / "turnout.html").read_bytes())
    else:
        facts = json.loads((args.cache_directory / "turnout-facts.json").read_text())
    if facts["source_html_sha256"] != page_receipts["turnout.html"]["sha256"]:
        raise ValueError("South Dakota factual extract has different source-page provenance")
    api = json.loads(raw_sources["county-turnout-api.json"])["d"]
    reported = sum(count(row["TotalPrecincts"]) for row in api)
    sheets = {}
    statewide = None
    for name, raw in raw_sources.items():
        if not name.endswith(".xlsx"):
            continue
        workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        if any(next(s.values)[0] != "2026 Unofficial General Election Results" for s in workbook):
            raise ValueError("Wrong election in a preserved South Dakota workbook")
        matches = [s for s in workbook if s.title == "14869United States Representat"]
        if name == "legislative-Legislative Results.xlsx":
            if matches:
                raise ValueError("Unexpected House sheet in the legislative export")
            workbook.close()
            continue
        if len(matches) != 1 or matches[0].title != "14869United States Representat":
            raise ValueError("Wrong South Dakota House contest identity")
        parsed = house_sheet(list(matches[0].values), name, reported)
        if name == "statewide-Statewide Results.xlsx":
            statewide = parsed
        else:
            code = receipts[name]["county_id"]
            if code in sheets:
                raise ValueError("Duplicate South Dakota county workbook")
            sheets[code] = parsed
        workbook.close()
    results, statistics, counties = review(sheets, statewide, facts, api,
        json.loads(raw_sources["statewide-public-response-01.json"])["d"])
    args.output.mkdir(parents=True)

    def save(name, value):
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        path.write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)

    for name, raw in raw_sources.items():
        path = args.output / "originals" / (name + ".gz")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(raw, mtime=0))
    save("originals/turnout-facts.json.gz", facts)
    factual_raw = gzip.decompress((args.output / "originals/turnout-facts.json.gz").read_bytes())
    save("sources.json", dict({name: receipts[name] for name in raw_sources},
        **{"turnout-facts.json": dict(url=TURNOUT, derivation=facts["extraction"],
            bytes=len(factual_raw), sha256=hashlib.sha256(factual_raw).hexdigest(),
            source_html_sha256=facts["source_html_sha256"])}))
    save("source-page-receipts.json", page_receipts)
    save("participation.json.gz", statistics)
    csv_file = io.StringIO(newline="")
    writer = csv.DictWriter(csv_file, fieldnames=list(results[0]))
    writer.writeheader()
    writer.writerows(results)
    (args.output / "results.csv.gz").write_bytes(gzip.compress(csv_file.getvalue().encode(), mtime=0))
    audit = dict(year=2026, state_code="SD", complete="no", reporting_units=len(results),
        counties=len(counties), candidate_results="acquired_reconciled",
        participation="acquired_precinct_counts_and_provisional_rates",
        boundaries="correct_election_reference_pending", join="withheld",
        validation="counts_passed_map_withheld", publication="full_counts_download_only",
        source_url=SOURCE, source_election=facts["election"], source_contest="14869",
        native_original_sources=len(raw_sources), native_original_bytes=sum(map(len, raw_sources.values())),
        factual_turnout_extract_rows=sum(len(c["records"]) for c in facts["counties"]),
        candidate_totals={field: sum(r[field] for r in results) for field in
            ["democratic_votes", "republican_votes", "other_votes", "contest_votes"]},
        ballots=sum(c["ballots"] for c in counties.values()),
        registrations=sum(c["registrations"] for c in counties.values()),
        rates_available=sum(r["reported_pct"] is not None for r in statistics),
        rates_withheld=sum(r["reported_pct"] is None for r in statistics),
        reconciliation=counties, complete_download_url=RELEASE,
        notes="All 671 source House rows, including zero-count and duplicate-name rows, reconcile "
            "to every county total and the independent statewide workbook by candidate name, not column "
            "position. Official candidate-party metadata is retained. Other contests remain unreviewed "
            "in all complete workbooks. All separate ballot rows reconcile to county API totals. "
            "Vote centers repeat county registration and never receive precinct rates. Duplicate labels "
            "are preserved with explicit source-row provenance, never silently combined or paired by row "
            "order. Only whitespace is normalized. Complete factual turnout-page observations are "
            "retained with the original HTML receipt; the page template/frontend is not redistributed. "
            "No correct-election boundary polygons or demographic participation are established.",
        next_action="Obtain explicit 2026 reporting-unit boundaries and native-ID crosswalks, especially "
            "vote-center scope and Oglala Lakota duplicate Sacred Heart Church Hall rows. Do not assign "
            "polling-place point locations or county denominators to residential precincts.")
    save("audit.json", audit)
    save("checksums.json", {str(p.relative_to(args.output)): dict(bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(args.output.rglob("*")) if p.is_file()})
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(args.output)))
    print(json.dumps({k: audit[k] for k in ["reporting_units", "counties", "candidate_totals",
        "ballots", "registrations", "rates_available", "rates_withheld"]}, indent=2))


if __name__ == "__main__":
    main()
