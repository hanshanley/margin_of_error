#!/usr/bin/env python3
"""Reconcile complete Alabama county exports and separately reported participation offline."""

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timedelta
from decimal import Decimal
import gzip
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import shutil
from urllib.parse import parse_qs, urljoin, urlparse
import xml.etree.ElementTree as ET
import zipfile


ELECTION = "1001305"
TITLE = "2026 GENERAL ELECTION"
XML = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
HEADERS = {
    "AllResults": ("Election Code", "Election Title", "County Code", "County Name",
                   "Contest Code", "Contest Title", "Candidate Number", "Candidate Name",
                   "Votes", "Party Code"),
    "Statistics": ("Election Code", "Election Title", "County Code", "Ballots Cast",
                   "Total Precincts", "Precincts Reported", "Last Updated"),
}
HOUSE = {f"UNITED STATES REPRESENTATIVE, {district}{suffix} CONGRESSIONAL DISTRICT": district
         for district, suffix in [(1, "ST"), (2, "ND"), (3, "RD"), (4, "TH"),
                                  (5, "TH"), (6, "TH"), (7, "TH")]}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def clean(value):
    return " ".join(str(value).split())


def count(value):
    require(isinstance(value, (str, int)) and not isinstance(value, bool)
            and re.fullmatch(r"[0-9]+", str(value)) is not None, "Missing or invalid native count")
    return int(value)


def read_workbook(body):
    with zipfile.ZipFile(io.BytesIO(body)) as workbook:
        strings = ["".join(node.itertext()) for node in ET.fromstring(
            workbook.read("xl/sharedStrings.xml")).findall(XML + "si")]
        relations = {node.attrib["Id"]: node.attrib["Target"] for node in ET.fromstring(
            workbook.read("xl/_rels/workbook.xml.rels"))}
        sheets = ET.fromstring(workbook.read("xl/workbook.xml")).findall(
            XML + "sheets/" + XML + "sheet")
        require({sheet.attrib["name"] for sheet in sheets} == set(HEADERS), "Unexpected native sheets")
        result, audit = {}, {}
        for sheet in sheets:
            name = sheet.attrib["name"]
            relation = sheet.attrib[
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = relations[relation]
            require(re.fullmatch(r"worksheets/sheet[12]\.xml", target), "Unexpected worksheet path")
            document = ET.fromstring(workbook.read("xl/" + target))
            records, blanks = [], 0
            for row in document.findall(XML + "sheetData/" + XML + "row"):
                values = [None] * len(HEADERS[name])
                for cell in row.findall(XML + "c"):
                    require(cell.find(XML + "f") is None, "Unreviewed native formula")
                    reference = re.fullmatch(r"([A-Z]+)[0-9]+", cell.attrib["r"])
                    require(reference is not None, "Invalid native cell reference")
                    column = 0
                    for letter in reference[1]:
                        column = column * 26 + ord(letter) - ord("A") + 1
                    require(1 <= column <= len(values), "Unexpected native column")
                    kind = cell.attrib.get("t")
                    value = cell.findtext(XML + "v")
                    if kind == "s" and value is not None:
                        value = strings[count(value)]
                    elif kind == "inlineStr":
                        value = "".join(cell.find(XML + "is").itertext())
                    else:
                        require(kind in {None, "n"}, "Unreviewed native cell type")
                    require(values[column - 1] is None, "Duplicate native column")
                    values[column - 1] = value
                if all(value in {None, ""} for value in values):
                    blanks += 1
                    continue
                if not records:
                    require(tuple(values) == HEADERS[name] and row.attrib["r"] == "1",
                            "Native worksheet header conflict")
                records.append(values)
            require(records, "Empty native worksheet")
            result[name] = [dict(zip(HEADERS[name], row)) for row in records[1:]]
            audit[name] = dict(observed_rows=len(result[name]), empty_xml_rows=blanks,
                               native_dimension=document.find(XML + "dimension").attrib["ref"])
    return result, audit


class NativePage(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}
    IDS = {"lblElectionName", "lblCountyName", "lblScopeName", "lblTotalBallotsCast",
           "lblTotalRegisteredVoters", "lblVoterTurnout", "lblLastUpdated", "lblCountiesReported"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth, self.captures, self.values, self.contests, self.links = 0, [], {}, [], []
        self.candidate_name = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag in self.VOID:
            return
        self.depth += 1
        classes = set(attrs.get("class", "").split())
        kind = attrs.get("id") if attrs.get("id") in self.IDS else None
        if "enrContestHeader" in classes:
            kind = "contest"
        elif classes & {"enrCandidateListItemCol", "enrAltCandidateListItemCol"}:
            if "enrCandNameCol" in classes:
                kind = "candidate"
            elif "enrCandVoteNumCol" in classes:
                kind = "votes"
        elif {"enrCandidatesFooter", "enrCandVoteNumCol"} <= classes:
            kind = "total"
        if kind:
            self.captures.append(dict(depth=self.depth, kind=kind, text=""))

    def handle_data(self, text):
        for capture in self.captures:
            capture["text"] += text

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        for capture in list(self.captures):
            if capture["depth"] != self.depth:
                continue
            text, kind = clean(capture["text"]), capture["kind"]
            if kind == "contest":
                require(self.candidate_name is None, "Unclosed native candidate")
                self.contests.append(dict(title=text, candidates=[], total=None))
            elif kind == "candidate":
                require(self.candidate_name is None, "Duplicate native candidate label")
                self.candidate_name = text
            elif kind == "votes":
                require(self.contests and self.candidate_name is not None, "Unscoped native candidate")
                self.contests[-1]["candidates"].append(
                    dict(label=self.candidate_name, votes=count(text.replace(",", ""))))
                self.candidate_name = None
            elif kind == "total":
                require(self.contests and self.contests[-1]["total"] is None, "Duplicate native total")
                self.contests[-1]["total"] = count(text.replace(",", ""))
            else:
                require(kind not in self.values, "Duplicate native statistic")
                self.values[kind] = text
            self.captures.remove(capture)
        self.depth -= 1


def page(body):
    parsed = NativePage()
    parsed.feed(body.decode("utf-8-sig"))
    require(parsed.values.get("lblElectionName") == TITLE, "Wrong native page election")
    require(parsed.contests and parsed.candidate_name is None and not parsed.captures,
            "Incomplete native result markup")
    require(len({contest["title"] for contest in parsed.contests}) == len(parsed.contests),
            "Ambiguous native contest title")
    for contest in parsed.contests:
        require(contest["candidates"] and contest["total"] is not None
                and sum(candidate["votes"] for candidate in contest["candidates"]) == contest["total"],
                "Native HTML candidate/total residual")
    return parsed


def compare_candidates(records, contest):
    expected = {}
    for row in records:
        party, name = row["Party Code"], row["Candidate Name"]
        label = name if party == "NON" else name + " (" + party + ")"
        require(label not in expected, "Ambiguous native candidate display label")
        expected[label] = count(row["Votes"])
    actual = {candidate["label"]: candidate["votes"] for candidate in contest["candidates"]}
    require(len(actual) == len(contest["candidates"]) and actual == expected,
            "Native HTML/workbook candidate conflict")


def participation(values):
    ballots = count(values["lblTotalBallotsCast"].replace(",", ""))
    registered = count(values["lblTotalRegisteredVoters"].replace(",", ""))
    reported = values["lblVoterTurnout"]
    require(re.fullmatch(r"[0-9]+\.[0-9]{2}%", reported) is not None
            and 0 < registered and ballots <= registered, "Invalid native participation scope")
    require(abs(Decimal(reported[:-1]) - Decimal(100) * ballots / registered) <= Decimal("0.005"),
            "Native reported percentage conflict")
    return dict(ballots=ballots, registered_voters=registered,
                source_reported_turnout_percent=reported, turnout_rate=None,
                last_updated_native=values["lblLastUpdated"])


def review(sheets, statewide, counties, declarations):
    results, statistics = sheets["AllResults"], sheets["Statistics"]
    require(results and statistics and set(counties) == set(declarations),
            "Incomplete native county declarations")
    by_scope, titles, identities, names, candidate_keys = defaultdict(list), {}, {}, {}, set()
    for row in results:
        row = dict(row)
        require(row["Election Code"] == ELECTION and clean(row["Election Title"]) == TITLE,
                "Wrong native workbook election")
        for field in ["County Code", "County Name", "Contest Code", "Contest Title",
                      "Candidate Number", "Candidate Name", "Party Code"]:
            require(isinstance(row[field], str) and clean(row[field]), "Missing native identity")
            row[field] = clean(row[field])
        county, contest = row["County Code"], row["Contest Code"]
        require(county in counties and declarations[county] == row["County Name"],
                "Native county identity conflict")
        require(row["Party Code"] in {"DEM", "REP", "NON", "IND"}, "Unreviewed native party")
        count(row["Votes"])
        key = (county, contest, row["Candidate Number"])
        require(key not in candidate_keys, "Duplicate native candidate identity")
        candidate_keys.add(key)
        title = row["Contest Title"]
        require(contest not in titles or titles[contest] == title, "Native contest identity conflict")
        titles[contest] = title
        candidate_key = (contest, row["Candidate Number"])
        identity = (row["Candidate Name"], row["Party Code"])
        require(candidate_key not in identities or identities[candidate_key] == identity,
                "Native candidate identity conflict")
        identities[candidate_key] = identity
        names[county] = row["County Name"]
        by_scope[county, contest].append(row)
    require(set(names) == set(counties), "Native workbook county scope conflict")
    federal_titles = {contest["title"]: contest for contest in statewide.contests}
    require(set(HOUSE) <= set(federal_titles), "Incomplete native statewide House summaries")
    reviewed_ids = {}
    for title, contest in federal_titles.items():
        codes = [code for code, name in titles.items() if name == title]
        require(len(codes) == 1, "Ambiguous statewide contest identity")
        code = codes[0]
        aggregated = {}
        for (county, native_id), records in by_scope.items():
            if native_id != code:
                continue
            for row in records:
                number = row["Candidate Number"]
                if number not in aggregated:
                    aggregated[number] = dict(row, Votes="0")
                aggregated[number]["Votes"] = str(count(aggregated[number]["Votes"]) + count(row["Votes"]))
        compare_candidates(list(aggregated.values()), contest)
        reviewed_ids[code] = title
    counts, participants, reviewed_cells = [], [], 0
    stat_ids = set()
    for row in statistics:
        require(row["Election Code"] == ELECTION and clean(row["Election Title"]) == TITLE,
                "Wrong native statistics election")
        county = row["County Code"]
        require(county in counties and county not in stat_ids, "Duplicate or unknown native statistics county")
        stat_ids.add(county)
        native = counties[county]
        require(native.values.get("lblCountyName") == names[county] + " County",
                "Native county page scope conflict")
        observed = participation(native.values)
        require(observed["ballots"] == count(row["Ballots Cast"]), "Native county ballot residual")
        require(count(row["Precincts Reported"]) <= count(row["Total Precincts"]),
                "Native precinct-reporting residual")
        updated = datetime(1899, 12, 30) + timedelta(days=float(row["Last Updated"]))
        displayed = datetime.strptime(observed["last_updated_native"], "%m/%d/%Y %I:%M:%S %p")
        require(abs((updated - displayed).total_seconds()) < 0.5, "Native county snapshot timestamp conflict")
        participants.append(dict(year=2026, state_code="AL", county_code=county, county=names[county],
                                 **observed, total_precincts=count(row["Total Precincts"]),
                                 precincts_reported=count(row["Precincts Reported"]),
                                 last_updated_excel_serial=row["Last Updated"]))
        actual = {contest["title"]: contest for contest in native.contests}
        for (scope, contest), records in by_scope.items():
            if scope != county or contest not in reviewed_ids:
                continue
            title = reviewed_ids[contest]
            require(title in actual, "Native county summary missing reviewed contest")
            compare_candidates(records, actual[title])
            reviewed_cells += len(records)
            if title not in HOUSE:
                continue
            total = sum(count(record["Votes"]) for record in records)
            candidates = {record["Candidate Number"]: dict(
                name=record["Candidate Name"], party=record["Party Code"], votes=count(record["Votes"]))
                for record in records}
            democratic = sum(candidate["votes"] for candidate in candidates.values() if candidate["party"] == "DEM")
            republican = sum(candidate["votes"] for candidate in candidates.values() if candidate["party"] == "REP")
            counts.append(dict(year=2026, state_code="AL", county_code=county, county=names[county],
                               contest_id=contest, district=HOUSE[title], total_votes=total,
                               democratic_votes=democratic, republican_votes=republican,
                               margin=None if total == 0 else 100 * (democratic - republican) / total,
                               candidates=json.dumps(candidates, separators=(",", ":"), sort_keys=True),
                               maps_approved=False))
        require(sum(item["total_votes"] for item in counts if item["county_code"] == county)
                <= observed["ballots"], "House candidate votes exceed native county ballots")
    require(stat_ids == set(counties), "Incomplete native statistics county scope")
    state_participation = participation(statewide.values)
    for field in ["ballots", "registered_voters"]:
        require(sum(row[field] for row in participants) == state_participation[field],
                "Native county/state participation residual")
    require(count(statewide.values["lblCountiesReported"]) == len(counties), "State county scope conflict")
    return sorted(counts, key=lambda row: (row["district"], row["county_code"])), sorted(
        participants, key=lambda row: row["county_code"]), dict(
            year=2026, state_code="AL", complete="no", unofficial=True,
            maps_approved=False, rates_available=False, native_candidate_rows=len(results),
            native_counties=len(counties), county_house_vectors=len(counts),
            native_ballots=state_participation["ballots"],
            native_registered_voters=state_participation["registered_voters"],
            native_state_participation=state_participation,
            reviewed_state_contests=len(federal_titles), county_summary_candidate_cells=reviewed_cells,
            all_reviewed_candidate_scopes_reconcile=True, all_county_state_participation_scopes_reconcile=True)


def build(source, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing to overwrite an existing package")
    sources = json.loads((source / "sources.json").read_text())
    require(set(sources) == {"official-statewide-results", "official-declared-native-export",
                            "official-declared-county-selector"} | {
                                key for key in sources if re.fullmatch(r"official-county-[0-9]{2}", key)},
            "Unexpected native original set")
    require({path.stem for path in (source / "originals").glob("*.gz")} == set(sources),
            "Missing or unreceipted original")
    payloads = {}
    for key, receipt in sources.items():
        body = gzip.decompress((source / "originals" / (key + ".gz")).read_bytes())
        require(receipt["status"] == 200 and len(body) == receipt["bytes"]
                and hashlib.sha256(body).hexdigest() == receipt["sha256"], "Native receipt conflict")
        payloads[key] = body
    selector = NativePage()
    selector.feed(payloads["official-declared-county-selector"].decode())
    declared_urls = {urljoin(sources["official-declared-county-selector"]["effective_url"], link)
                     for link in selector.links if "countyResultsByContest.aspx?" in link}
    counties, declarations = {}, {}
    for key, receipt in sources.items():
        if not key.startswith("official-county-"):
            continue
        require(receipt["url"] in declared_urls, "County page not declared by actual selector")
        query = parse_qs(urlparse(receipt["url"]).query)
        code = receipt["county_code"]
        require(query == {"cid": [code], "ecode": [ELECTION]} and code == key.rsplit("-", 1)[1]
                and code not in counties, "Native declared county URL conflict")
        counties[code] = page(payloads[key])
        declarations[code] = receipt["county_name"]
    require(len(declared_urls) == len(counties) == 67, "Incomplete native county originals")
    sheets, worksheet_audit = read_workbook(payloads["official-declared-native-export"])
    counts, participants, audit = review(sheets, page(payloads["official-statewide-results"]), counties, declarations)
    require(audit["native_candidate_rows"] == 5613 and audit["reviewed_state_contests"] == 10,
            "Native snapshot scope changed; review before publication")
    audit["worksheets"] = worksheet_audit
    output.mkdir(parents=True)
    shutil.copytree(source / "originals", output / "native-source/originals")
    shutil.copyfile(source / "sources.json", output / "native-source/sources.json")
    shutil.copyfile(Path(__file__), output / Path(__file__).name)
    for name, records in [("all-native-candidate-counts.csv", sheets["AllResults"]),
                          ("county-house-counts.csv", counts), ("county-participation.csv", participants)]:
        with (output / name).open("w") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    (output / "counts-review.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "checksums.json").write_text(json.dumps({
        path.relative_to(output).as_posix(): dict(bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(output.rglob("*")) if path.is_file()
    }, separators=(",", ":")) + "\n")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as target:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                member = zipfile.ZipInfo(path.relative_to(output).as_posix())
                member.external_attr = 0o644 << 16
                target.writestr(member, path.read_bytes())
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["source", "output", "archive"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.archive), indent=2))
