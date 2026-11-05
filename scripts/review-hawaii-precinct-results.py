"""Preserve Hawaii 2026 native reporting modes and audit, not repair, source differences."""

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

import fitz


SOURCE = "https://elections.hawaii.gov/election-results/"
BOUNDARY_SOURCE = "https://elections.hawaii.gov/resources/maps/geographic-information-systems-gis-files/"
ORIGINALS = ("cch.pdf", "coh.pdf", "cok.pdf", "com.pdf", "histatewide.pdf",
             "media.txt", "precinct.pdf", "summary.txt")
RELEASE = ("https://github.com/hanshanley/margin_of_error/releases/download/"
           "voter-precinct-hawaii-20261105/complete-hawaii-2026-source-review.zip")
LABEL = '#"Precinct_Name"'
MEDIA_HEADER = [LABEL, "Split_Name", "precinct_splitId", "Reg_voters", "Ballots",
                "Reporting", "Contest_id", "Contest_title", "Contest_party", "Choice_id",
                "Candidate_name", "Choice_party", "Candidate_Type", "Mail votes", "In-Person votes", ""]
SUMMARY_HEADER = ["#Contest ID", "Contest Title", "Contest Seq Nbr", "Contest Type", "Contest Party",
                  "Mail Blank Votes", "In-Person Blank Votes", "Mail Over Votes", "In-Person Over Votes",
                  "Mail Invalid Votes", "In-Person Invalid Votes", "Registered Voters", "Total Precincts",
                  "Counted Precincts", "Candidate ID", "Candidate Name", "Candidate Seq Nbr",
                  "Candidate Party", "Mail Votes", "In-Person Votes", "Total Votes"]
CONTESTS = {"30": "U.S. Representative, Dist I", "5": "U.S. Representative, Dist II"}
MODES = ("Mail", "In-Person")


def count(value):
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        return int(value)
    raise ValueError("Missing or invalid Hawaii count; not zero")


def party(name):
    match = re.fullmatch(r"\(([DRGNL])\) (.+)", name)
    if not match:
        raise ValueError("Missing or unknown Hawaii explicit candidate-party prefix")
    return match[1]


def read_table(raw, media=False):
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), delimiter="\t")
    if media and next(reader) != [f"Column{i}" for i in range(1, 17)]:
        raise ValueError("Wrong Hawaii media preamble")
    metadata = next(reader)
    if metadata[0] != "#FormatVersion 1" or any(metadata[1:]):
        raise ValueError("Wrong Hawaii source format version")
    header = MEDIA_HEADER if media else SUMMARY_HEADER
    if next(reader) != header:
        raise ValueError("Wrong Hawaii native source header")
    records, previous_line = [], reader.line_num
    for fields in reader:
        if len(fields) != len(header):
            raise ValueError("Truncated or malformed Hawaii native source row")
        records.append(dict(zip(header, fields), _source_lines=[previous_line + 1, reader.line_num]))
        previous_line = reader.line_num
    if not records:
        raise ValueError("Empty Hawaii source")
    return records


def review(rows, summary):
    expected, common, summary_lines = {}, {}, {}
    summary_fields = (["Contest Title", "Contest Type", "Contest Party", "Registered Voters",
                       "Total Precincts", "Counted Precincts"]
                      + [f"{mode} {kind} Votes" for mode in MODES for kind in ("Blank", "Over", "Invalid")])
    for row in summary:
        contest = row["#Contest ID"]
        if contest not in CONTESTS:
            if row["Contest Title"].startswith("U.S. Representative"):
                raise ValueError("Unknown Hawaii House contest")
            continue
        if (row["Contest Title"] != CONTESTS[contest] or row["Contest Type"] != "OF"
                or row["Contest Party"] or row["Candidate Party"]):
            raise ValueError("Conflicting Hawaii House identity or party fields")
        facts = {field: row[field] for field in summary_fields}
        if contest in common and facts != common[contest]:
            raise ValueError("Conflicting Hawaii repeated summary fields")
        common[contest] = facts
        key = (contest, row["Candidate ID"])
        count(key[1])
        party(row["Candidate Name"])
        if key in expected or any(k[0] == contest and v["name"] == row["Candidate Name"]
                                  for k, v in expected.items()):
            raise ValueError("Duplicate Hawaii summary candidate")
        votes = {mode: count(row[mode + " Votes"]) for mode in MODES}
        if sum(votes.values()) != count(row["Total Votes"]):
            raise ValueError("Hawaii summary candidate ballot modes disagree")
        expected[key] = dict(name=row["Candidate Name"], votes=votes)
        summary_lines[key] = row["_source_lines"]
    if set(common) != set(CONTESTS):
        raise ValueError("Missing Hawaii House district")
    registrations = {count(r["Registered Voters"]) for r in common.values()}
    if len(registrations) != 1:
        raise ValueError("Hawaii repeated statewide registration values differ")
    units, unit_rows = {}, defaultdict(list)
    for row in rows:
        identity = row["precinct_splitId"]
        count(identity)
        facts = tuple(row[field] for field in (LABEL, "Split_Name", "Reg_voters", "Ballots", "Reporting"))
        if identity in units and facts != units[identity]:
            raise ValueError("Conflicting Hawaii repeated unit identity or participation counts")
        units[identity] = facts
        if row["Contest_id"] in CONTESTS:
            unit_rows[identity].append(row)
        elif row["Contest_title"].startswith("U.S. Representative"):
            raise ValueError("Unknown Hawaii House contest")
    if set(units) != set(unit_rows):
        raise ValueError("Hawaii source units missing House records")
    results, statistics, sums = [], [], Counter()
    district_units, district_reported = Counter(), Counter()
    for identity, records in unit_rows.items():
        label, split, registration, ballots, reporting = units[identity]
        overseas = label in {"OS I", "OS II"}
        if (not (overseas or re.fullmatch(r"[0-9]{2}-[0-9]{2}", label))
                or split not in {"", "VSC"} or overseas and split
                or reporting not in {"0", "1"}):
            raise ValueError("Unknown Hawaii source reporting-unit scope")
        contests = {r["Contest_id"] for r in records}
        if len(contests) != 1:
            raise ValueError("Hawaii reporting unit has ambiguous House district")
        contest = contests.pop()
        candidate_set = {key[1] for key in expected if key[0] == contest}
        if len(records) != len(candidate_set) or {r["Choice_id"] for r in records} != candidate_set:
            raise ValueError("Missing or duplicate Hawaii reporting-unit candidate")
        votes, candidate_modes = {}, {}
        for row in records:
            candidate = expected[(contest, row["Choice_id"])]
            if (row["Contest_title"] != CONTESTS[contest] or row["Candidate_name"] != candidate["name"]
                    or row["Candidate_Type"] != "C" or row["Choice_party"] or row["Contest_party"] or row[""]):
                raise ValueError("Hawaii media/summary candidate identity differs")
            values = {mode: count(row[mode + " votes"]) for mode in MODES}
            if values["Mail" if split else "In-Person"]:
                raise ValueError("Hawaii source split contains unexpected ballot mode")
            votes[candidate["name"]] = sum(values.values())
            candidate_modes[candidate["name"]] = values
            for mode, value in values.items():
                sums[(contest, row["Choice_id"], mode)] += value
        district_units[contest] += 1
        district_reported[contest] += count(reporting)
        registered, ballots = count(registration), count(ballots)
        flags = ["ballot_modes_retained_separately_rates_withheld"]
        if split:
            flags.append("native_vsc_reporting_flag_not_interpreted_as_zero_votes")
        if overseas:
            flags.append("overseas_reporting_unit_not_residential_precinct")
        if not registered:
            flags.append("zero_native_registration_denominator")
        if ballots > registered:
            flags.append("ballots_exceed_native_registration")
        total = sum(votes.values())
        if total > ballots:
            flags.append("candidate_votes_exceed_native_ballots")
        democratic = sum(v for name, v in votes.items() if party(name) == "D")
        republican = sum(v for name, v in votes.items() if party(name) == "R")
        base = dict(key="HI|source-unit-" + identity, year=2026, state_code="HI",
                    precinct=label + (" / " + split if split else ""),
                    source_precinct_label=label, source_split_label=split, source_unit_id=identity,
                    reporting_unit_kind="overseas_reporting_unit" if overseas else
                        "native_vsc_split" if split else "native_mail_split",
                    source_reporting=count(reporting), source_url=SOURCE, source_file="media.txt",
                    source_rows=json.dumps([r["_source_lines"] for r in records], separators=(",", ":")))
        results.append(dict(base, office="U.S. House", source_office=CONTESTS[contest],
            source_contest_id=contest, democratic_votes=democratic, republican_votes=republican,
            other_votes=total - democratic - republican, contest_votes=total,
            candidate_votes=json.dumps(votes, separators=(",", ":"), sort_keys=True),
            candidate_ballot_modes=json.dumps(candidate_modes, separators=(",", ":"), sort_keys=True),
            margin_pp=100 * (democratic - republican) / total if total else None,
            ballot_scope="Uncertified source reporting modes, retained separately; not complete residential turnout.",
            quality_flags=";".join(flags)))
        statistics.append(dict(base, ballots=ballots, registered=registered, reported_pct=None,
            denominator_scope="native_mode_specific_registration_not_combined",
            basis="Rates withheld: mode-specific native denominators and source-snapshot ballot differences "
                  "are not repaired or silently joined. Candidate votes are not ballots or demographic turnout.",
            quality_flags=flags))
    for (contest, candidate), expected_candidate in expected.items():
        for mode in MODES:
            if sums[(contest, candidate, mode)] != expected_candidate["votes"][mode]:
                raise ValueError("Hawaii complete candidate/mode sums differ from native summary")
    for contest, facts in common.items():
        if (district_units[contest] != count(facts["Total Precincts"])
                or district_reported[contest] != count(facts["Counted Precincts"])):
            raise ValueError("Hawaii summary and native reporting-unit scope differ")
    if sum(r["registered"] for r in statistics) != next(iter(registrations)):
        raise ValueError("Hawaii unique-unit registration differs from repeated statewide summary")
    accounting = {}
    for mode in MODES:
        native_ballots = sum(r["ballots"] for r in statistics
                            if bool(r["source_split_label"]) == (mode == "In-Person"))
        candidate_sum = sum(c["votes"][mode] for c in expected.values())
        blanks, over, invalid = (sum(count(f[f"{mode} {kind} Votes"]) for f in common.values())
                                 for kind in ("Blank", "Over", "Invalid"))
        accounted = candidate_sum + blanks + over + invalid
        accounting[mode] = dict(native_unit_ballots=native_ballots, candidate_votes=candidate_sum,
            blank_votes=blanks, over_votes=over, invalid_votes=invalid,
            summary_accounted_ballots=accounted, native_minus_summary=native_ballots - accounted)
    return results, statistics, dict(candidate_totals_by_name={
        c["name"]: sum(c["votes"].values()) for c in expected.values()},
        summary_candidate_lines={f"{k[0]}|{k[1]}": v for k, v in summary_lines.items()},
        reporting_unit_kinds=dict(Counter(r["reporting_unit_kind"] for r in statistics)),
        source_district_units=dict(district_units), source_district_reported=dict(district_reported),
        ballot_accounting_by_mode=accounting,
        quality_flag_counts=dict(Counter(flag for r in statistics for flag in r["quality_flags"])))


def pdf_observations(originals):
    observations = {}
    for name in ORIGINALS:
        if not name.endswith(".pdf"):
            continue
        with fitz.open(stream=originals[name], filetype="pdf") as document:
            pages = [page.get_text().splitlines() for page in document]
        units = defaultdict(list)
        for number, lines in enumerate(pages, 1):
            if ("November 3, 2026" not in lines or not any(
                    line.startswith("GENERAL ELECTION 2026 - State of Hawaii - ") for line in lines)
                    or not any(line.strip() == "REPORT 3" for line in lines)):
                raise ValueError("Wrong Hawaii PDF election, date or report identity")
            labels = [line for line in lines
                      if re.fullmatch(r"(Mail|In-Person) ([0-9]{2}-[0-9]{2}|OS I|OS II)", line)]
            if name == "precinct.pdf" and len(labels) != 1:
                raise ValueError("Ambiguous Hawaii PDF precinct-mode identity")
            units[labels[0] if labels else "summary"].append((number, lines))
        records = []
        for label, grouped in units.items():
            lines = [line.strip() for _, page in grouped for line in page]
            counts, contest = {}, None
            for i, line in enumerate(lines):
                if line in CONTESTS.values():
                    contest = line
                elif contest and re.fullmatch(r"\([DRGNL]\) .+", line):
                    key = contest + "|" + line
                    if key in counts:
                        raise ValueError("Duplicate Hawaii PDF House candidate")
                    counts[key] = count(lines[i + 1].replace(",", ""))
                elif line == "Over Votes:":
                    contest = None
            values = {}
            for field in ("TOTAL REGISTRATION", "TOTAL TURNOUT", "Mail TURNOUT",
                          "In-Person TURNOUT", "PRECINCT REGISTRATION"):
                found = [count(lines[i + 1].replace(",", "")) for i, line in enumerate(lines) if line == field]
                if len(found) > 1:
                    raise ValueError("Duplicate Hawaii PDF participation field")
                if found:
                    values[field] = found[0]
            records.append(dict(label=label, pages=[p for p, _ in grouped], candidate_votes=counts,
                                participation=values))
        observations[name] = dict(pages=len(pages), printed_on=next(
            line for line in pages[0] if line.startswith("Printed on:")), records=records)
    return observations


def compare_pdf_observations(results, statistics, pdfs):
    pdf_units = {r["label"]: r for r in pdfs["precinct.pdf"]["records"]}
    seen, differences = set(), []
    for row, stats in zip(results, statistics):
        mode = "In-Person" if row["source_split_label"] else "Mail"
        label = mode + " " + row["source_precinct_label"]
        if label in seen or label not in pdf_units:
            raise ValueError("Missing or ambiguous Hawaii literal PDF/mode comparison")
        seen.add(label)
        observation = pdf_units[label]
        native_candidates = {row["source_office"] + "|" + name: votes
                             for name, votes in json.loads(row["candidate_votes"]).items()}
        fields = {"candidate_votes": (native_candidates, observation["candidate_votes"]),
                  "ballots": (stats["ballots"], observation["participation"][mode + " TURNOUT"]),
                  "registered": (stats["registered"], observation["participation"]["PRECINCT REGISTRATION"])}
        for field, (native, pdf) in fields.items():
            if native != pdf:
                differences.append(dict(source_unit_id=row["source_unit_id"], pdf_label=label,
                    pdf_pages=observation["pages"], field=field, native_value=native, pdf_value=pdf))
                flag = "native_pdf_" + field + "_difference_retained"
                stats["quality_flags"].append(flag)
                row["quality_flags"] += ";" + flag
    pdf_only = [record for label, record in pdf_units.items() if label not in seen]
    county_candidates, county_participation = Counter(), Counter()
    for name in ("cch.pdf", "coh.pdf", "cok.pdf", "com.pdf"):
        county = pdfs[name]["records"][0]
        county_candidates.update(county["candidate_votes"])
        county_participation.update(county["participation"])
    statewide = pdfs["histatewide.pdf"]["records"][0]
    return dict(comparison_basis="Literal precinct label and source mode only; not a spatial crosswalk, "
                                  "denominator substitution or merged reporting unit.",
        native_units_compared=len(seen), pdf_units=len(pdf_units), differences=differences,
        difference_fields=dict(Counter(r["field"] for r in differences)), pdf_only_units=pdf_only,
        county_candidate_totals=dict(county_candidates),
        county_minus_state_candidate_votes={name: county_candidates[name] - votes
                                            for name, votes in statewide["candidate_votes"].items()},
        county_minus_state_participation={field: county_participation[field] - value
                                         for field, value in statewide["participation"].items()},
        pdf_printed_on={name: value["printed_on"] for name, value in pdfs.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable Hawaii review")
    receipts = json.loads((args.cache_directory / "sources.json").read_text())
    originals = {}
    for name in ORIGINALS:
        raw = (args.cache_directory / name).read_bytes()
        if (len(raw) != receipts[name]["bytes"]
                or hashlib.sha256(raw).hexdigest() != receipts[name]["sha256"]
                or receipts[name]["url"] !=
                    "https://elections.hawaii.gov/wp-content/results/2026 General/" + name):
            raise ValueError("Hawaii original receipt or election-source URL mismatch: " + name)
        originals[name] = raw
    rows = read_table(originals["media.txt"], media=True)
    summary = read_table(originals["summary.txt"])
    results, statistics, reconciliation = review(rows, summary)
    pdfs = pdf_observations(originals)
    reconciliation["pdf_comparison"] = compare_pdf_observations(results, statistics, pdfs)
    reconciliation["quality_flag_counts"] = dict(Counter(
        flag for r in statistics for flag in r["quality_flags"]))
    statewide_pdf = pdfs["histatewide.pdf"]["records"][0]
    csv_candidates = {r["source_office"] + "|" + name: 0
                      for r in results for name in json.loads(r["candidate_votes"])}
    for row in results:
        for name, value in json.loads(row["candidate_votes"]).items():
            csv_candidates[row["source_office"] + "|" + name] += value
    if statewide_pdf["candidate_votes"] != csv_candidates:
        raise ValueError("Hawaii statewide PDF and text candidate identities/counts differ")
    source_turnout = statewide_pdf["participation"]
    if (source_turnout["TOTAL REGISTRATION"] != sum(r["registered"] for r in statistics)
            or source_turnout["TOTAL TURNOUT"] != sum(
                f["summary_accounted_ballots"] for f in reconciliation["ballot_accounting_by_mode"].values())
            or any(source_turnout[mode + " TURNOUT"] !=
                   reconciliation["ballot_accounting_by_mode"][mode]["summary_accounted_ballots"] for mode in MODES)):
        raise ValueError("Hawaii statewide PDF and text summary ballot accounting differs")
    audit = dict(year=2026, state_code="HI", complete="no", source_election="GENERAL ELECTION 2026",
        source_election_date="2026-11-03", source_report="REPORT 3", source_certified=False,
        source_updated=pdfs["histatewide.pdf"]["printed_on"], reporting_units=len(results),
        candidate_results="acquired_reconciled", participation="acquired_reporting_unit_counts_rates_withheld",
        boundaries="reviewed_official_page_exact_year_reference_pending", join="withheld",
        validation="native_candidate_counts_passed_ballot_differences_retained", publication="full_counts_download_only",
        source_url=SOURCE, boundary_source=BOUNDARY_SOURCE, complete_download_url=RELEASE,
        complete_original_csv_rows=len(rows), complete_original_summary_rows=len(summary),
        native_original_sources=len(originals), native_original_bytes=sum(map(len, originals.values())),
        candidate_totals={field: sum(r[field] for r in results) for field in
                          ("democratic_votes", "republican_votes", "other_votes", "contest_votes")},
        ballots=sum(r["ballots"] for r in statistics), registrations=sum(r["registered"] for r in statistics),
        source_summary_ballots=source_turnout["TOTAL TURNOUT"], rates_available=0, rates_withheld=len(statistics),
        reconciliation=reconciliation,
        notes="All 496 original House reporting units and both candidate ballot modes reconcile by exact native "
              "candidate IDs/names and explicit party prefixes to both text and statewide PDF summaries. "
              "The native 249 blank-split units include 247 geographic labels and OS I/II; 247 VSC splits "
              "have separate IDs, zero native registrations and Reporting=0 despite nonzero votes. "
              "Do not interpret Reporting as missing votes, combine unit identities or count the repeated "
              "853399 statewide summary registration once per district. Native ballots total 365903, "
              "six above summary 365897 (mail +1, in-person +5). All eight complete originals, 806 precinct "
              "PDF pages, separate county PDF snapshots, native unit/mode counts, zero denominators and "
              "source discrepancies remain available. Rates and maps are withheld, not repaired. "
              "The official GIS page advertises 2022 and 2018 precinct references, not explicit 2026 vintage. "
              "No other contest has been reconciled and no demographic turnout is inferred.",
        next_action="Resolve the retained source ballot/denominator differences without replacing native "
                    "counts or inferring completion from Reporting. Seek explicit 2026 boundary confirmation from the advertised state "
                    "GIS portal before a separately tested immutable mapped supplement. Do not borrow "
                    "another election's boundaries or silently allocate VSC/overseas votes.")
    args.output.mkdir(parents=True)

    def save(name, value):
        path = args.output / name
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        path.write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)

    for name, raw in originals.items():
        path = args.output / "originals" / (name + ".gz")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(raw, mtime=0))
    save("sources.json", {name: receipts[name] for name in ORIGINALS})
    save("participation.json.gz", statistics)
    save("pdf-observations.json.gz", pdfs)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(results[0]))
    writer.writeheader()
    writer.writerows(results)
    (args.output / "results.csv.gz").write_bytes(gzip.compress(buffer.getvalue().encode(), mtime=0))
    save("audit.json", audit)
    save("checksums.json", {str(p.relative_to(args.output)): dict(bytes=p.stat().st_size,
         sha256=hashlib.sha256(p.read_bytes()).hexdigest())
         for p in sorted(args.output.rglob("*")) if p.is_file()})
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(str(path.relative_to(args.output)), date_time=(2026, 11, 5, 0, 0, 0))
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())
    print(json.dumps({key: audit[key] for key in ("reporting_units", "candidate_totals", "ballots",
        "registrations", "source_summary_ballots", "rates_withheld", "reconciliation")}, indent=2))


if __name__ == "__main__":
    main()
