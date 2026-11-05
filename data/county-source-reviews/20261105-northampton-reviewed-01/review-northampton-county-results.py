"""Reconcile Northampton's native 2026 county results without inferring turnout."""

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

from bs4 import BeautifulSoup


SOURCE_URLS = {
    "official-index.html": "https://www.norcopa.gov/election-result",
    "native-results.html": "https://www.livevoterturnout.com/ENR/northamptonpaenr/12/en/Index_12.html",
}
PUBLIC_SERVICE_KEY = re.compile(rb"\b(?:AIza[0-9A-Za-z_-]{35}|[ps]k\.[A-Za-z0-9._-]+)")
PUBLIC_TELEMETRY_KEY = re.compile(
    rb"""((?:['"]?(?:[A-Za-z_$]*instrumentationKey|licenseKey)['"]?)\s*[:=]\s*['"])(?!\[REDACTED_PUBLIC_SERVICE_KEY\])([^'"\r\n]+)(['"])""",
    re.I,
)
IDENTITY = dict(year=2026, state_code="PA", county_fips="42095", county="Northampton")


def integer(value):
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+", value):
        raise ValueError("Missing or invalid native integer")
    return int(value.replace(",", ""))


def office(contest):
    for prefix, kind in [
        ("GOVERNOR AND LIEUTENANT GOVERNOR", "governor_lieutenant_governor"),
        ("REPRESENTATIVE IN CONGRESS", "us_house"),
        ("SENATOR IN THE GENERAL ASSEMBLY", "state_senate"),
        ("REPRESENTATIVE IN THE GENERAL ASSEMBLY", "state_house"),
    ]:
        if contest.startswith(prefix):
            return kind
    raise ValueError("Unreviewed native office")


def load_originals(folder):
    receipts = json.loads((folder / "receipts.json").read_bytes())
    if (len(receipts) != len(SOURCE_URLS)
            or {r["file"] for r in receipts} != set(SOURCE_URLS)
            or {p.name for p in folder.iterdir()} != set(SOURCE_URLS) | {"receipts.json"}):
        raise ValueError("Incomplete original receipt inventory")
    raw = {}
    for receipt in receipts:
        name = receipt["file"]
        data = (folder / name).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if (receipt["url"] != SOURCE_URLS[name] or receipt["http_status"] != 200
                or receipt["bytes"] != len(data) or receipt["sha256"] != digest):
            raise ValueError("Original acquisition receipt mismatch")
        if PUBLIC_SERVICE_KEY.search(data) or PUBLIC_TELEMETRY_KEY.search(data):
            raise ValueError("Unredacted public service key in source HTML")
        redaction = receipt.get("redaction", {})
        replacements = data.count(b"[REDACTED_PUBLIC_SERVICE_KEY]")
        if (not re.fullmatch(r"[a-f0-9]{64}", redaction.get("original_sha256", ""))
                or redaction.get("original_bytes", 0) <= 0
                or redaction.get("replacements") != replacements
                or (not replacements and (redaction["original_sha256"] != digest
                                           or redaction["original_bytes"] != len(data)))):
            raise ValueError("Missing or invalid explicit HTML screening receipt")
        raw[name] = data
    return raw


def review(raw):
    parent = BeautifulSoup(raw["official-index.html"], "html.parser")
    if not any(a["href"] == SOURCE_URLS["native-results.html"] for a in parent.select("a[href]")):
        raise ValueError("County does not declare this result page")
    soup = BeautifulSoup(raw["native-results.html"], "html.parser")
    if (soup.select_one("h1.election-title").get_text(strip=True) != "2026 General Election"
            or soup.select_one("#electid")["value"] != "12"
            or soup.select_one("#lblOfficialResults").get_text(strip=True) != "Unofficial Election Results"
            or re.search(r"\btest(?:ing)?\b", soup.body.get_text(" ", strip=True), re.I)):
        raise ValueError("Wrong election or source publication status")
    summary = soup.select_one("#electionSummaryStats")
    labels = [span.get_text(strip=True) for span in summary.select("span:not([class])")]
    expected_labels = [
        "Ballots Cast", "Election Day", "Mail-in Ballots", "Provisional",
        "Registered Voters", "Partially Reporting", "Fully Reporting", "Total Precincts",
    ]
    if labels[::2] != expected_labels or len(labels) != 2 * len(expected_labels):
        raise ValueError("Changed county participation schema")
    counts = dict(zip(expected_labels, map(integer, labels[1::2])))
    ballots, registered = counts["Ballots Cast"], counts["Registered Voters"]
    if (not registered or ballots > registered
            or sum(counts[label] for label in ["Election Day", "Mail-in Ballots", "Provisional"]) != ballots
            or counts["Partially Reporting"] != 0
            or counts["Fully Reporting"] != counts["Total Precincts"]):
        raise ValueError("County ballot modes, registrations or reporting counts disagree")
    percentages = [node.get_text(strip=True) for node in summary.select(".summary-percentage")]
    expected_rate = (Decimal(100) * ballots / registered).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if percentages != [str(expected_rate) + "%", "100%"]:
        raise ValueError("Printed county participation or reporting rate disagrees")
    stamps = set(re.findall(
        r"Website Updated:\s*(\d{1,2}/\d{1,2}/2026 \d{1,2}:\d{2}:\d{2} [AP]M)",
        soup.get_text(" ", strip=True)))
    if len(stamps) != 1:
        raise ValueError("Missing native update timestamp")
    candidates, lookup, options, contests = [], {}, defaultdict(set), {}
    for container in soup.select("#contestListLayer > .list-item"):
        contest = container.select_one(".race-title").get_text(strip=True)
        if contest in contests or container.select_one(".vote-for").get_text(strip=True) != "(VOTE FOR 1)":
            raise ValueError("Duplicate contest or unreviewed selection limit")
        kind = office(contest)
        contests[contest] = kind
        for row in container.select("tr.content-row"):
            cell = row.select_one('[data-candidate="true"]')
            literal = cell.select_one('[aria-hidden="true"]').get_text(strip=True)
            prefix = re.match(r"^(DEM|REP|LIB) ", literal)
            if not prefix and literal != "Write-in":
                raise ValueError("Missing or unreviewed native party prefix")
            key = contest, literal
            if key in lookup:
                raise ValueError("Duplicate county candidate identity")
            data = dict(**IDENTITY, office=kind, contest=contest,
                        candidate_html_literal=literal,
                        accessible_html_literal=cell.select_one(".sr-only").get_text(strip=True),
                        party_html_prefix_literal=prefix[1] if prefix else "",
                        votes=integer(row.select_one('[data-votes="true"]').get_text(strip=True)))
            candidates.append(data)
            lookup[key] = data
            options[contest].add(literal)
        if not options[contest]:
            raise ValueError("Missing county candidate options")
    if (not contests or len(contests) != integer(soup.select_one("#totalContests").get_text(strip=True))
            or Counter(contests.values())["us_house"] != 1):
        raise ValueError("Missing county contests or ambiguous House scope")
    units, unit_counts, covered, observations = {}, [], defaultdict(set), set()
    sums = Counter()
    for unit in soup.select("#precinctListLayer > .list-item-precinct"):
        name = unit.select_one(".precinct-title").get_text(strip=True)
        code = unit["id"].removeprefix("listid_")
        if not name or not code or name in units.values() or code in units:
            raise ValueError("Duplicate or missing native unit identity")
        units[code] = name
        for fragment in unit.select(".list-item-precinct-race"):
            title = fragment.select_one(".race-title").get_text(strip=True)
            if not title.startswith(name + " - "):
                raise ValueError("Native unit contest has a different unit identity")
            contest = title[len(name + " - "):]
            if contest not in contests or code in covered[contest]:
                raise ValueError("Unknown or duplicate native unit contest")
            covered[contest].add(code)
            seen = set()
            for row in fragment.select("tr.content-row"):
                literal = row.select_one('[dc="true"] [aria-hidden="true"]').get_text(strip=True)
                key = contest, literal
                observation = code, contest, literal
                if key not in lookup or observation in observations:
                    raise ValueError("Unknown or duplicate native candidate observation")
                observations.add(observation)
                seen.add(literal)
                votes = integer(row.select_one('[dv="true"]').get_text(strip=True))
                sums[key] += votes
                unit_counts.append(dict(**{k: lookup[key][k] for k in [
                    "year", "state_code", "county_fips", "county", "office",
                    "contest", "candidate_html_literal", "party_html_prefix_literal"]},
                    native_unit_code=code, native_unit_name=name, votes=votes))
            if seen != options[contest]:
                raise ValueError("Missing native candidate option, including explicit zero")
    if (len(units) != counts["Total Precincts"]
            or any(sums[key] != data["votes"] for key, data in lookup.items())):
        raise ValueError("Native unit inventory or sums differ from county counts")
    for kind in {"governor_lieutenant_governor", "us_house", "state_senate", "state_house"}:
        partition = set()
        for contest in contests:
            if contests[contest] == kind:
                if partition & covered[contest]:
                    raise ValueError("Overlapping native office district partitions")
                partition.update(covered[contest])
        if partition != set(units):
            raise ValueError("Incomplete county office district partition")
        if sum(row["votes"] for row in candidates if row["office"] == kind) > ballots:
            raise ValueError("Office candidate totals exceed county ballots")
    parties = Counter()
    for row in candidates:
        parties[row["office"], row["party_html_prefix_literal"]] += row["votes"]
    contest_rows = []
    for contest, kind in contests.items():
        votes = sum(row["votes"] for row in candidates if row["contest"] == contest)
        countywide = covered[contest] == set(units)
        if votes > ballots:
            raise ValueError("Candidate totals exceed reported county ballots")
        contest_rows.append(dict(**IDENTITY, office=kind, contest=contest,
            native_units=len(covered[contest]), covers_all_county_native_units=countywide,
            candidate_votes=votes, covered_ballots_cast=ballots if countywide else None,
            ballots_minus_candidate_votes_unclassified=ballots-votes if countywide else None,
            native_under_votes=None, native_over_votes=None))
    qualifications = [node.get_text(" ", strip=True) for node in soup.select("[id$='Reporting']")
                      if node.get_text(strip=True)]
    row = dict(**IDENTITY, ballots_cast=ballots, registered_voters=registered,
        native_printed_turnout=percentages[0],
        house_candidate_votes=sum(r["votes"] for r in candidates if r["office"] == "us_house"),
        native_status_literal="Unofficial Election Results", source_update_literal=next(iter(stamps)),
        counting_qualifications_json=json.dumps(qualifications),
        ballot_receipt_notice_literal=" ".join(
            h.get_text(" ", strip=True) for h in soup.select("h2") if "ACT 88" in h.get_text()),
        final_certified_turnout=False)
    tables = {
        "county-participation.csv": [row],
        "county-ballot-mode-counts.csv": [dict(**IDENTITY, ballot_mode_literal=label,
                                             ballots_cast=counts[label])
                                        for label in ["Election Day", "Mail-in Ballots", "Provisional"]],
        "county-candidate-results.csv": candidates,
        "county-office-party-totals.csv": [dict(**IDENTITY, office=kind,
            party_html_prefix_literal=party, votes=votes)
            for (kind, party), votes in sorted(parties.items())],
        "county-contest-totals.csv": contest_rows,
        "native-unit-candidate-counts.csv": unit_counts,
        "native-unit-contest-coverage.csv": [dict(**IDENTITY, office=contests[contest],
            contest=contest, native_unit_code=code, native_unit_name=units[code])
            for contest in contests for code in sorted(covered[contest])],
    }
    audit = dict(status="county_counts_reviewed_not_final_certified", participation=row,
        native_units=len(units), native_contests=len(contests),
        native_unit_explicit_zeroes=sum(r["votes"] == 0 for r in unit_counts),
        source_urls=SOURCE_URLS, table_rows={name: len(rows) for name, rows in tables.items()},
        maps_approved=False, fully_complete=False, demographic_turnout_approved=False,
        limitations=[
            "Unofficial snapshot; native mail-in and Election Day counting remain partial.",
            "Candidate votes, ballots cast, ballot receipt notices and registrations are distinct.",
            "Party identifiers are literal visible HTML prefixes, not CSV party fields.",
            "Write-in has no explicit party prefix; its party remains blank, not NON or independent.",
            "Native reporting units are preserved for count reconciliation only; no new boundaries.",
            "No unit ballot/registration dataset or candidate voting-mode breakdown was acquired.",
            "Missing under/overvotes and district ballot denominators remain blank, not zero.",
            "Countywide ballot residuals are unclassified; do not infer their cause.",
            "Source update timezone is unestablished; reporting 100% is not finished counting.",
            "Complete source HTML is explicitly screened/redacted with original-hash receipts.",
        ])
    return tables, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    tables, audit = review(load_originals(args.source))
    args.output.mkdir(parents=True, exist_ok=False)
    for name, rows in tables.items():
        with (args.output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (args.output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    shutil.copytree(args.source, args.output / "originals")
    shutil.copyfile(__file__, args.output / Path(__file__).name)
    paths = sorted(p for p in args.output.rglob("*") if p.is_file())
    checksums = {p.relative_to(args.output).as_posix(): dict(
        bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths}
    (args.output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in args.output.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(args.output).as_posix())
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
