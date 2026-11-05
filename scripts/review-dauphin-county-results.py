"""Reconcile Dauphin's separate county, precinct and municipality snapshots."""

import argparse
from collections import Counter
import csv
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import parse_qs, urljoin, urlparse
import zipfile

from bs4 import BeautifulSoup


IDENTITY = dict(year=2026, state_code="PA", county_fips="42043", county="Dauphin")
BASE = "https://elections.dauphincounty.gov/"
PARENT = "https://www.dauphincounty.gov/public-records/registration-elections/election2026"
PUBLIC_SERVICE_KEY = re.compile(rb"\b(?:AIza[0-9A-Za-z_-]{35}|[ps]k\.[A-Za-z0-9._-]+)")
PUBLIC_TELEMETRY_KEY = re.compile(
    rb"""((?:['"]?(?:[A-Za-z_$]*instrumentationKey|licenseKey)['"]?)\s*[:=]\s*['"])(?!\[REDACTED_PUBLIC_SERVICE_KEY\])([^'"\r\n]+)(['"])""",
    re.I,
)


def integer(text):
    if not re.fullmatch(r"0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+", text):
        raise ValueError("Missing or invalid native integer")
    return int(text.replace(",", ""))


def text(node):
    if node is None:
        raise ValueError("Missing native HTML field")
    return node.get_text(" ", strip=True)


def load_originals(folder):
    receipts = json.loads((folder / "receipts.json").read_bytes())
    names = {r["file"] for r in receipts}
    expected = ({"official-index.html"} |
                {"native-report-%02d.html" % i for i in range(1, 10)} |
                {"native-detail-%02d.html" % i for i in range(1, 10)})
    if (names != expected or len(receipts) != 19
            or {p.name for p in folder.iterdir()} != expected | {"receipts.json"}):
        raise ValueError("Incomplete original receipt inventory")
    raw = {}
    for receipt in receipts:
        data = (folder / receipt["file"]).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        url = urlparse(receipt["url"])
        if (receipt["status"] != 200 or receipt["final_url"] != receipt["url"]
                or receipt["bytes"] != len(data) or receipt["sha256"] != digest
                or url.scheme != "https"
                or (receipt["url"] != PARENT and (
                    url.netloc != "elections.dauphincounty.gov"
                    or parse_qs(url.query).get("key") != ["42"]))):
            raise ValueError("Original acquisition receipt mismatch")
        if PUBLIC_SERVICE_KEY.search(data) or PUBLIC_TELEMETRY_KEY.search(data):
            raise ValueError("Unredacted public service key in source HTML")
        if receipt.get("screening") != dict(
                original_sha256=digest, original_bytes=len(data), replacements=0):
            raise ValueError("Missing explicit source screening receipt")
        raw[receipt["file"]] = data
    return raw, receipts


def stamp(soup, detailed=False):
    pattern = r"Last update:\s*(\d{1,2}/\d{1,2}/2026 \d{1,2}:\d{2}"
    pattern += r" [AP]M)" if detailed else r":\d{2} [AP]M)"
    matches = re.findall(pattern, soup.get_text(" ", strip=True))
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous source update")
    return matches[0], datetime.strptime(
        matches[0], "%m/%d/%Y %I:%M %p" if detailed else "%m/%d/%Y %I:%M:%S %p")


def scope(contest):
    if contest == "GOVERNOR AND LIEUTENANT GOVERNOR":
        return "governor_lieutenant_governor", ""
    if contest == "REPRESENTATIVE IN CONGRESS":
        return "us_house", ""
    for prefix, office in [
        ("SENATOR IN THE GENERAL ASSEMBLY - SD", "state_senate"),
        ("REPRESENTATIVE IN THE GENERAL ASSEMBLY - HD", "state_house"),
    ]:
        if contest.startswith(prefix) and contest[len(prefix):].isdigit():
            return office, contest[len(prefix):]
    raise ValueError("Unreviewed native office")


def review(raw, receipts):
    by_name = {r["file"]: r for r in receipts}
    parent = BeautifulSoup(raw["official-index.html"], "html.parser")
    declared = {urljoin(BASE, a["href"]) for a in parent.select("a[href]")}
    method_parents = [r for r in receipts if r["url"] == PARENT]
    if (by_name["official-index.html"]["url"] != BASE + "?key=42"
            or by_name["native-report-09.html"]["url"] != BASE + "Machine?key=42"
            or BASE + "Machine?key=42" not in declared or len(method_parents) != 1):
        raise ValueError("Missing declared county source identity")
    used = {"official-index.html", "native-report-09.html", method_parents[0]["file"]}
    county, units, contests, reporting = [], {"precinct": [], "municipality": []}, [], []
    coverage = {"precinct": {}, "municipality": {}}
    updates = set()
    for i in range(1, 9):
        filename = "native-report-%02d.html" % i
        receipt = by_name[filename]
        soup = BeautifulSoup(raw[filename], "html.parser")
        if (receipt["url"] not in declared or soup.select_one("#Key")["value"] != "42"
                or text(soup.select_one("h1")) != "2026 General Election Results"
                or text(soup.select_one("#merrP")) != "UNOFFICIAL RESULTS"):
            raise ValueError("Wrong election or undeclared summary")
        literal_stamp, updated = stamp(soup)
        updates.add(literal_stamp)
        table = soup.select_one("#tblRace")
        rows = table.find_all("tr", recursive=False)
        heading = text(rows[0].select_one("span.font-weight-bolder"))
        match = re.fullmatch(r"(.+?)\s+\( Vote For\s+1 \)", heading)
        if not match:
            raise ValueError("Unreviewed contest or selection limit")
        contest = match[1]
        if contest in coverage["precinct"]:
            raise ValueError("Duplicate contest")
        office, district = scope(contest)
        common = dict(**IDENTITY, office=office, district_literal=district, contest=contest)
        qualifier = text(table.select_one('[alt="In-Person Preceincts Reporting"]'))
        match = re.fullmatch(r"In-Person Precincts Reporting - (\d+) of (\d+)", qualifier)
        if not match:
            raise ValueError("Changed native reporting schema")
        reported, total_units = map(integer, match.groups())
        if reported > total_units:
            raise ValueError("Impossible native reporting count")
        options = {}
        for row in rows[2:-1]:
            strong = row.select_one(".col-xs-8 strong")
            party = text(strong.select_one("span.party"))
            candidate = " ".join(" ".join(strong.find_all(string=True, recursive=False)).split())
            if not party or not candidate or candidate in options:
                raise ValueError("Missing or duplicate native candidate")
            votes = integer(text(row.select_one(".col-md-12")))
            options[candidate] = dict(**common, candidate=candidate,
                                      party_literal=party, votes=votes)
        if not options or text(rows[-1].select_one(".col-xs-8")) != "TOTAL:":
            raise ValueError("Missing county candidate total")
        total = integer(text(rows[-1].select_one(".col-xs-4")))
        if sum(r["votes"] for r in options.values()) != total:
            raise ValueError("County candidate sum disagrees with printed total")
        for row, option in zip(rows[2:-1], options.values()):
            percent = Decimal(text(row.select_one(".progress-bar")))
            expected = (Decimal(100) * option["votes"] / total).quantize(
                Decimal(".01"), rounding=ROUND_HALF_UP)
            if percent != expected:
                raise ValueError("Printed candidate percentage disagrees")
        county.extend(options.values())
        links = {urljoin(BASE, a["href"]) for a in rows[0].select("a[href]")}
        details = [r for r in receipts if r["url"] in links
                   and urlparse(r["url"]).path == "/Races"]
        if len(details) != 1 or PARENT not in links:
            raise ValueError("Missing or ambiguous declared detail")
        used.update([filename, details[0]["file"]])
        detail = BeautifulSoup(raw[details[0]["file"]], "html.parser")
        _, detail_update = stamp(detail, detailed=True)
        if (detail_update != updated.replace(second=0)
                or text(detail.select_one("#merrP")) != "Totals include all ballots counted."
                or not any(text(h) == "Results by Municipalities" for h in detail.select("h3"))):
            raise ValueError("Changed detail timestamp or geographic qualification")
        outer_tables = [detail.select("table.my_tab"), detail.select("table.tab2")]
        leaves = [t for t in detail.select("table") if t.find("table") is None]
        if len(leaves) != 2 or any(len(group) != 1 for group in outer_tables):
            raise ValueError("Changed detail geography schema")
        for level, group in zip(["precinct", "municipality"], outer_tables):
            outer = group[0]
            if text(outer.find("tr", recursive=False)) != contest:
                raise ValueError("Detail belongs to another contest")
            inner = outer.find("table")
            grid = [[text(c) for c in r.find_all(["td", "th"], recursive=False)]
                    for r in inner.find_all("tr", recursive=False)]
            if grid[0] != ["", *options]:
                raise ValueError("Detail candidate columns disagree")
            names, sums = set(), Counter()
            for cells in grid[1:]:
                if len(cells) != len(options) + 1 or not cells[0] or cells[0] in names:
                    raise ValueError("Missing or duplicate native geography")
                names.add(cells[0])
                for candidate, value in zip(options, cells[1:]):
                    votes = integer(value)
                    sums[candidate] += votes
                    units[level].append(dict(**common, geography_level=level,
                        native_unit=cells[0], candidate=candidate,
                        party_literal=options[candidate]["party_literal"], votes=votes))
            if dict(sums) != {name: r["votes"] for name, r in options.items()}:
                raise ValueError("Native geographic candidate sums disagree")
            if level == "precinct" and len(names) != total_units:
                raise ValueError("Precinct row count disagrees with native reporting scope")
            coverage[level][contest] = names
        contests.append(dict(**common, candidate_votes=total,
            native_precincts=len(coverage["precinct"][contest]),
            native_municipalities=len(coverage["municipality"][contest])))
        reporting.append(dict(**common, native_status="UNOFFICIAL RESULTS",
            source_update_literal=literal_stamp, in_person_reporting_literal=qualifier,
            in_person_precincts_reported=reported, in_person_precincts_total=total_units,
            counted_ballot_scope_literal="Totals include all ballots counted.",
            mail_ballots=None, provisional_ballots=None, final_certified=False))
    if used != set(raw):
        raise ValueError("Unreviewed source inventory")
    if len(updates) != 1:
        raise ValueError("County summaries are different snapshots")
    for level, scopes in coverage.items():
        countywide = scopes["REPRESENTATIVE IN CONGRESS"]
        if scopes["GOVERNOR AND LIEUTENANT GOVERNOR"] != countywide:
            raise ValueError("Countywide geographic scopes disagree")
        districts = [scopes[r["contest"]] for r in contests if r["office"] == "state_house"]
        if (len(districts) != 5 or set.union(*districts) != countywide
                or (level == "precinct" and sum(map(len, districts)) != len(countywide))
                or any(not names <= countywide for names in scopes.values())):
            raise ValueError("Native district geographic coverage disagrees")
    parties = Counter()
    for row in county:
        parties[row["office"], row["district_literal"], row["contest"], row["party_literal"]] += row["votes"]
    tables = {
        "county-candidate-results.csv": county,
        "county-contest-totals.csv": contests,
        "county-contest-party-totals.csv": [dict(**IDENTITY, office=o, district_literal=d,
            contest=c, party_literal=p, votes=v) for (o, d, c, p), v in sorted(parties.items())],
        "county-participation.csv": [dict(**IDENTITY, ballots_cast=None, registered_voters=None,
            turnout_percent=None, house_candidate_votes=sum(
                r["votes"] for r in county if r["office"] == "us_house"),
            native_status="UNOFFICIAL RESULTS", source_update_literal=next(iter(updates)),
            final_certified=False)],
        "native-precinct-candidate-counts.csv": units["precinct"],
        "native-municipality-candidate-counts.csv": units["municipality"],
        "native-contest-reporting.csv": reporting,
    }
    audit = dict(status="candidate_counts_reviewed_participation_unavailable",
        **IDENTITY, native_contests=len(contests), native_candidate_rows=len(county),
        table_rows={name: len(rows) for name, rows in tables.items()},
        geographic_explicit_zeroes={level: sum(r["votes"] == 0 for r in rows)
                                   for level, rows in units.items()},
        fully_complete=False, maps_approved=False, demographic_turnout_approved=False,
        limitations=[
            "Unofficial snapshot; reporting every in-person precinct does not establish final counting.",
            "The native detail says totals include all ballots counted, not all ballots received.",
            "Precinct and municipality tables reconcile separately; never add the two geographic levels.",
            "Mail reporting markup is commented out, not an observed zero-mail count.",
            "No ballot, registration, turnout or demographic denominator was acquired.",
            "Parties are literal HTML values; NONPARTISAN write-ins are not independent candidates.",
            "Absent Republican rows in HD104 and HD105 are missing, not manufactured zeroes.",
            "State legislative districts are explicit; the House heading does not supply a district number.",
            "The method-report parent and precinct-progress list are retained, not inferred method totals.",
            "Source update timezone is unestablished; detail timestamps have only minute precision.",
            "No geometry, complete statewide results or certified participation is asserted.",
        ])
    return tables, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    raw, receipts = load_originals(args.source)
    tables, audit = review(raw, receipts)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, rows in tables.items():
        with (args.output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (args.output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    shutil.copytree(args.source, args.output / "originals")
    shutil.copyfile(__file__, args.output / Path(__file__).name)
    checksums = {p.relative_to(args.output).as_posix(): dict(
        bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(args.output.rglob("*")) if p.is_file()}
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
