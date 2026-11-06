"""Reconcile complete California native county participation and separate contest facts."""

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
from urllib.parse import urljoin
import xml.etree.ElementTree as ET
import zipfile


MEDIA = "https://media.sos.ca.gov/"
RACES = dict(zip(("02", "03", "04", "05", "06", "07", "08", "09", "11",
                  "12", "13", "14", "15", "16", "19"),
                 ("governor", "lieutenant-governor", "secretary-of-state",
                  "controller", "treasurer", "attorney-general", "insurance-commissioner",
                  "board-of-equalization", "us-rep", "state-senate", "state-assembly",
                  "supreme-court", "court-of-appeal", "superintendent-of-public-instruction",
                  "ballot-measures")))
TEXT_NAMES = tuple(letter + "26GG.txt" for letter in "CJPRSV")
BASE_NAMES = ("sources.csv", "source-catalogs.csv", "source-links.csv",
              "native-text-records.csv", "native-reporting-status.csv",
              "native-contest-reports.csv", "election-identity.json")
SCRIPT_NAME = Path(__file__).name


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def document(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def table(rows, fields=None):
    rows = list(rows)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def records(body):
    return list(csv.DictReader(io.StringIO(body.decode("utf-8"))))


def integer(value):
    require(isinstance(value, str) and re.fullmatch(r"\d+", value) is not None,
            "Missing, signed or invalid native integer")
    return int(value)


def percent(numerator, denominator, literal):
    require(denominator > 0 and re.fullmatch(r"\d+(?:\.\d+)?", literal) is not None,
            "Missing or invalid native percentage")
    places = Decimal(literal).as_tuple().exponent
    expected = (Decimal(numerator) * 100 / Decimal(denominator)).quantize(
        Decimal(1).scaleb(places), rounding=ROUND_HALF_UP)
    require(expected == Decimal(literal), "Native percentage arithmetic mismatch")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.text = [], []

    def handle_starttag(self, tag, attrs):
        if tag == "a" and dict(attrs).get("href"):
            href = dict(attrs)["href"]
            self.links.append(dict(native_href=href, resolved_url=urljoin(MEDIA, href)))

    def handle_data(self, data):
        self.text.append(data)


def original_inputs(directory):
    names = ("media-index.html", "json-endpoints.csv", "api-endpoints.csv",
             "bulk-file-locations.xlsx", "status_GG.json", "status_GG.zip",
             "all_GG.zip") + TEXT_NAMES
    originals, receipts = {}, []
    for name in names:
        body = (directory / name).read_bytes()
        receipt = json.loads((directory / (name + ".receipt.json")).read_text())
        expected = MEDIA if name == "media-index.html" else MEDIA + "media/" + name
        require(receipt["url"] == expected and receipt["final_url"] == expected
                and receipt["status"] == 200 and receipt["bytes"] == len(body)
                and receipt["sha256"] == hashlib.sha256(body).hexdigest(),
                "Original source receipt mismatch: " + name)
        originals[name] = body
        receipts.append(dict(source_file=name, **receipt))
    parent = Links()
    parent.feed(originals["media-index.html"].decode("utf-8"))
    identity = "California General Election Tuesday, November 3, 2026"
    require(identity in " ".join(" ".join(parent.text).split()),
            "Wrong election identity on the actual official parent")
    declared = {row["resolved_url"] for row in parent.links}
    require(all(MEDIA + "media/" + name in declared for name in
                TEXT_NAMES + ("json-endpoints.csv", "api-endpoints.csv",
                              "bulk-file-locations.xlsx")), "Undeclared native source")
    catalogs = []
    for name in ("json-endpoints.csv", "api-endpoints.csv"):
        for index, row in enumerate(csv.reader(io.StringIO(
                originals[name].decode("utf-8-sig"))), 1):
            catalogs.append(dict(source_file=name, native_record_index=index,
                                 native_values_json=encoded(row)))
    declared_json = {row[0].rsplit("/", 1)[-1] for row in csv.reader(io.StringIO(
        originals["json-endpoints.csv"].decode("utf-8-sig")))
        if row and row[0].startswith(MEDIA + "media/")}
    expected_json = {name + ".json" for name in RACES.values()} | {"status_GG.json"}
    require(declared_json == expected_json, "Changed complete JSON endpoint catalog")
    with zipfile.ZipFile(io.BytesIO(originals["bulk-file-locations.xlsx"])) as archive:
        strings = ["".join(row.itertext()) for row in ET.fromstring(
            archive.read("xl/sharedStrings.xml"))]
        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        sheets = [name for name in archive.namelist()
                  if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)]
        for name in sheets:
            for row in ET.fromstring(archive.read(name)).findall(".//s:row", ns):
                cells = []
                for cell in row.findall("s:c", ns):
                    value = cell.find("s:v", ns)
                    literal = value.text if value is not None else ""
                    if cell.get("t") == "s":
                        literal = strings[int(literal)]
                    cells.append(dict(native_cell=cell.get("r"), literal=literal))
                catalogs.append(dict(source_file="bulk-file-locations.xlsx:" + name,
                                     native_record_index=row.get("r"),
                                     native_values_json=encoded(cells)))
        require(all(name in strings for name in
                    (MEDIA + "media/", "all_GG.zip", "status_GG.zip")),
                "Bulk archives not declared in the actual workbook")
    text_rows = []
    for name in TEXT_NAMES:
        try:
            text = originals[name].decode("utf-8-sig")
            encoding = "utf-8-sig"
        except UnicodeDecodeError:
            text = originals[name].decode("cp1252")
            encoding = "cp1252"
        for index, raw_line in enumerate(text.splitlines(keepends=True), 1):
            line = raw_line.rstrip("\r\n")
            require(line.startswith("[") and line.endswith("]"),
                    "Malformed complete native text record")
            fields = line[1:-1].split("|")
            text_rows.append(dict(source_file=name, native_record_index=index,
                                  decoding=encoding,
                                  native_line_ending_json=encoded(raw_line[len(line):]),
                                  native_fields_json=encoded(fields)))
    with zipfile.ZipFile(io.BytesIO(originals["status_GG.zip"])) as archive:
        require(archive.namelist() == ["status_GG.json"]
                and archive.read("status_GG.json") == originals["status_GG.json"],
                "Independent status archive bytes differ")
    contests = []
    with zipfile.ZipFile(io.BytesIO(originals["all_GG.zip"])) as archive:
        require(len(archive.namelist()) == len(set(archive.namelist()))
                and set(archive.namelist()) == expected_json
                and archive.read("status_GG.json") == originals["status_GG.json"],
                "Incomplete or inconsistent entire statewide archive")
        for name in archive.namelist():
            if name == "status_GG.json":
                continue
            for index, row in enumerate(json.loads(archive.read(name)), 1):
                contests.append(dict(archive_member=name, native_record_index=index,
                                     native_record_json=encoded(row)))
    status = [dict(native_record_index=index, native_record_json=encoded(row))
              for index, row in enumerate(json.loads(originals["status_GG.json"]), 1)]
    return dict(zip(BASE_NAMES, (
        table(receipts), table(catalogs), table(parent.links), table(text_rows),
        table(status), table(contests), document(dict(
            source_parent=MEDIA, native_election_identity=identity,
            year=2026, election_date="2026-11-03", election_stage="General")))))


def reconcile(inputs):
    identity = json.loads(inputs["election-identity.json"])
    require(identity["year"] == 2026 and identity["election_date"] == "2026-11-03"
            and identity["election_stage"] == "General", "Wrong election scope")
    texts = defaultdict(list)
    restored = defaultdict(bytearray)
    sources = {row["source_file"]: row for row in records(inputs["sources.csv"])}
    for record in records(inputs["native-text-records.csv"]):
        fields = json.loads(record["native_fields_json"])
        require(fields[1] == "CAS", "Changed native source identity")
        name = record["source_file"]
        require(integer(record["native_record_index"]) == len(texts[name]) + 1,
                "Missing or duplicate native text row")
        texts[name].append(fields)
        line = "[" + "|".join(fields) + "]" + json.loads(record["native_line_ending_json"])
        restored[name].extend(line.encode(record["decoding"].replace("-sig", "")))
    require(set(texts) == set(TEXT_NAMES), "Incomplete native text files")
    for name, body in restored.items():
        require(len(body) == integer(sources[name]["bytes"])
                and hashlib.sha256(body).hexdigest() == sources[name]["sha256"],
                "Entire native text source reconstruction mismatch")
    kinds = {name: Counter(row[0] for row in rows) for name, rows in texts.items()}
    for name in TEXT_NAMES:
        require(kinds[name]["B"] == kinds[name]["E"] == (2 if name == "V26GG.txt" else 1),
                "Incomplete native framing")
    county_names = {integer(row[3]): row[4] for row in texts["S26GG.txt"] if row[0] == "S"}
    require(set(county_names) == set(range(1, 60)) and county_names[59] == "State of California",
            "Incomplete native county identity inventory")
    native_a = [row for row in texts["V26GG.txt"] if row[0] == "A"]
    require(len(native_a) == 59 and {integer(row[3]) for row in native_a} == set(county_names),
            "Missing or duplicate native participation records")
    native_a = {integer(row[3]): row for row in native_a}
    status = [json.loads(row["native_record_json"])
              for row in records(inputs["native-reporting-status.csv"])]
    require(len(status) == 59 and {row["county"] for row in status} == set(county_names),
            "Missing or duplicate JSON participation records")
    status = {row["county"]: row for row in status}
    native_fields = ("reportTypeCode", "reportNumber", "correctionReportnumber",
                     "precinctsReporting", "precinctsTotal", "precinctsReportingPercent",
                     "voterTurnout", "totalRegisteredVoters", "voterTurnoutPercentage",
                     "firstReportTimestamp", "lastReportTimestamp")
    participation = []
    for code in sorted(status):
        row, native = status[code], native_a[code]
        require(len(native) == 15 and tuple(native[4:]) == tuple(row[k] for k in native_fields),
                "JSON/native participation mismatch")
        require(row["countyName"] == ("Statewide" if code == 59 else county_names[code]),
                "Changed native county name")
        require((row["reportTypeCode"], row["reportType"]) in {("U", "U"), ("F", "SF")},
                "Unreviewed native report status")
        for field in ("firstReportTimestamp", "lastReportTimestamp"):
            require(re.fullmatch(r"2026110[3-6]\d{4}", row[field]) is not None,
                    "Wrong election clock; no inferred timezone")
        turnout, registered = integer(row["voterTurnout"]), integer(row["totalRegisteredVoters"])
        require(0 < turnout <= registered, "Invalid native participation denominator")
        percent(turnout, registered, row["voterTurnoutPercentage"])
        percent(integer(row["precinctsReporting"]), integer(row["precinctsTotal"]),
                row["precinctsReportingPercent"])
        participation.append(dict(
            year=2026, election_date="2026-11-03", state_code="CA",
            geography_level="statewide" if code == 59 else "county",
            native_county_code=str(code), county=row["countyName"],
            native_county_name_in_code_file=county_names[code], county_fips="",
            reported_participation=turnout, registered_voters=registered,
            native_participation_measure_literal="voterTurnout",
            native_denominator_measure_literal="totalRegisteredVoters",
            native_printed_turnout=row["voterTurnoutPercentage"],
            native_report_type=row["reportType"], native_report_type_code=row["reportTypeCode"],
            native_report_number=row["reportNumber"],
            native_correction_report_number=row["correctionReportnumber"],
            precincts_reporting=row["precinctsReporting"], precincts_total=row["precinctsTotal"],
            native_reporting_percent=row["precinctsReportingPercent"],
            native_first_report_timestamp=row["firstReportTimestamp"],
            native_last_report_timestamp=row["lastReportTimestamp"],
            native_timestamp_literal=row["timestamp"], declared_timezone="",
            counting_complete="false", maps_approved="false"))
    for field in ("voterTurnout", "totalRegisteredVoters", "precinctsReporting", "precinctsTotal"):
        require(sum(integer(status[code][field]) for code in range(1, 59))
                == integer(status[59][field]), "County/statewide participation conservation mismatch")
    candidates = {}
    for row in texts["C26GG.txt"]:
        if row[0] != "C":
            continue
        require(len(row) in (11, 12) and (len(row) == 11 or row[-1] == ""),
                "Changed native candidate schema")
        key = (row[3], row[4])
        require(key not in candidates, "Duplicated native candidate identity")
        candidates[key] = row
    contests = {row[3]: row for row in texts["R26GG.txt"] if row[0] == "R"}
    require(all(row[5] == "GG" for row in contests.values()), "Wrong native contest stage")
    precincts = {}
    for row in texts["P26GG.txt"]:
        if row[0] != "P":
            continue
        key = row[3], integer(row[4])
        require(key not in precincts, "Duplicated native contest reporting area")
        precincts[key] = integer(row[5])
    by_name = {name: code for code, name in county_names.items() if code != 59}
    json_reports = {}
    for record in records(inputs["native-contest-reports.csv"]):
        row = json.loads(record["native_record_json"])
        suffix = row["raceTitle"].rsplit(" - ", 1)[-1]
        require(suffix.endswith(" Results"), "Unreviewed native results geography")
        suffix = suffix[:-8]
        code = 59 if suffix in ("Statewide", "Districtwide") else by_name.get(
            suffix, by_name.get(suffix[:-7]) if suffix.endswith(" County") else None)
        require(code is not None, "Unmatched native result county")
        if "candidates" in row:
            subject = ""
            choices = row["candidates"]
            signature = tuple(sorted((c["Name"], integer(c["Votes"].replace(",", "")),
                                      Decimal(c["Percent"])) for c in choices))
        else:
            field = next((k for k in ("supreme-court", "courts-of-appeal", "ballot-measures")
                          if k in row), None)
            require(field is not None and len(row[field]) == 1, "Changed binary-contest schema")
            item = row[field][0]
            subject = item["Name"]
            signature = tuple((label, integer(item[key + "Votes"]), Decimal(item[key + "Percent"]))
                              for label, key in (("NO", "no"), ("YES", "yes")))
        key = record["archive_member"], code, subject, signature
        require(key not in json_reports, "Ambiguous JSON/native contest match")
        json_reports[key] = (record, row, choices if "candidates" in row else None)
    totals, choices, parties, used_json = [], [], defaultdict(int), set()
    party_codes, seen_native = defaultdict(set), set()
    for native in texts["V26GG.txt"]:
        if native[0] != "V":
            continue
        contest, code = native[3], integer(native[4])
        key = contest, code
        require(key not in seen_native and key in precincts and contest in contests,
                "Duplicate or unmatched native contest")
        seen_native.add(key)
        require(integer(native[6]) == precincts[key] and integer(native[5]) <= integer(native[6]),
                "Native contest precinct reconciliation mismatch")
        prefix, subject, items = contest[:2], "", []
        if prefix in ("14", "15"):
            require(len(native) == 15 and native[9] == "YES" and native[12] == "NO",
                    "Changed judicial native schema")
            subject = candidates[(contest, native[8])][10]
            items = [(native[i], integer(native[i + 1]), native[i + 2], "", native[8], "")
                     for i in (9, 12)]
        elif prefix == "19":
            require(len(native) == 14 and native[8] == "YES" and native[11] == "NO",
                    "Changed measure native schema")
            subject = candidates[(contest, "")][10]
            items = [(native[i], integer(native[i + 1]), native[i + 2], "", "", "")
                     for i in (8, 11)]
        else:
            require(prefix in RACES and len(native) >= 12 and (len(native) - 8) % 4 == 0,
                    "Changed candidate native schema")
            for index in range(8, len(native), 4):
                candidate = candidates[(contest, native[index])]
                items.append((candidate[10], integer(native[index + 1]), native[index + 3],
                              native[index + 2], native[index], candidate[9]))
        signature = tuple(sorted((name, votes, Decimal(pct)) for name, votes, pct, _, _, _ in items))
        match = RACES[prefix] + ".json", code, subject, signature
        require(match in json_reports and match not in used_json,
                "JSON/native candidate or contest reconciliation mismatch")
        used_json.add(match)
        source, report, json_candidates = json_reports[match]
        require(report["ReportingTime"] == status[code]["timestamp"],
                "Contest/participation source clocks differ")
        reporting = re.fullmatch(r"([\d.]+)% \(([\d,]+) of ([\d,]+)\) precincts reporting",
                                 report["Reporting"])
        require(reporting is not None and integer(reporting[2].replace(",", "")) == integer(native[5])
                and integer(reporting[3].replace(",", "")) == integer(native[6]),
                "JSON/native contest reporting mismatch")
        percent(integer(native[5]), integer(native[6]), reporting[1])
        total = sum(item[1] for item in items)
        require(total <= integer(status[code]["voterTurnout"]),
                "Single-choice contest exceeds native reported participation")
        base = dict(year=2026, state_code="CA", native_county_code=code,
                    county=status[code]["countyName"],
                    geography_level="statewide_or_districtwide" if code == 59 else "county",
                    native_contest_code=contest, native_contest_label=contests[contest][4],
                    native_election_stage=contests[contest][5], native_subject_literal=subject,
                    native_report_type_code=native[7], archive_member=source["archive_member"],
                    native_json_record_index=source["native_record_index"],
                    native_race_title=report["raceTitle"],
                    native_reporting_literal=report["Reporting"],
                    native_reporting_time_literal=report["ReportingTime"])
        totals.append(dict(**base, contest_votes=total,
                           native_precincts_reporting=native[5], native_precincts_total=native[6],
                           reported_participation_minus_contest_votes_not_classified=
                           integer(status[code]["voterTurnout"]) - total))
        for name, votes, pct, auxiliary, candidate_id, party_code in items:
            party = ""
            if json_candidates is not None:
                candidate = next(c for c in json_candidates if c["Name"] == name)
                party = candidate["Party"]
                require(isinstance(party, str) and party != "" and party_code != "",
                        "Missing literal candidate party")
                party_codes[party_code].add(party)
                parties[(contest, code, party)] += votes
            if total:
                percent(votes, total, pct)
            else:
                require(votes == 0 and Decimal(pct) == 0, "Invalid zero-vote share")
            choices.append(dict(**base, native_candidate_id=candidate_id, choice_literal=name,
                                votes=votes, native_vote_share_literal=pct,
                                native_auxiliary_percentage_literal=auxiliary,
                                party_literal=party, native_party_code=party_code,
                                party_not_applicable=str(json_candidates is None).lower()))
    require(seen_native == set(precincts) and used_json == set(json_reports),
            "Incomplete all-contest, all-county reconciliation")
    require(all(len(values) == 1 for values in party_codes.values()),
            "Conflicting literal party/code association")
    party_rows = [dict(year=2026, state_code="CA", native_county_code=code,
                       county=status[code]["countyName"],
                       geography_level="statewide_or_districtwide" if code == 59 else "county",
                       native_contest_code=contest, native_election_stage=contests[contest][5],
                       native_contest_label=contests[contest][4], party_literal=party,
                       candidate_votes=votes)
                  for (contest, code, party), votes in sorted(parties.items())]
    audit = dict(
        election=identity, county_records=58, separate_statewide_records=1,
        reported_participation=integer(status[59]["voterTurnout"]),
        registered_voters=integer(status[59]["totalRegisteredVoters"]),
        native_printed_turnout=status[59]["voterTurnoutPercentage"],
        complete_native_text_record_counts={name: dict(counts) for name, counts in kinds.items()},
        entire_native_json_contest_reports=len(used_json), contest_choice_records=len(choices),
        party_total_records=len(party_rows),
        native_literal_party_associations={key: sorted(values) for key, values in sorted(party_codes.items())},
        all_58_counties_and_statewide_match_independent_native_A_records=True,
        all_county_participation_registration_and_reporting_sums_match_statewide=True,
        all_contest_choices_match_entire_native_V_records=True,
        all_native_contest_precinct_totals_match_independent_P_records=True,
        all_json_contest_clocks_match_native_county_status=True,
        all_nonzero_choice_percentages_reconciled=True,
        native_source_fips_supplied=False, maps_approved=False, counting_complete=False,
        qualifications=[
            "Native voterTurnout is participation, not a sum of candidate or party votes.",
            "Statewide/districtwide aggregate contests are separate from county records.",
            "Precinct reporting completeness does not establish completed counting or certification.",
            "U, F and SF are preserved literally; certification and report-status expansions are not inferred.",
            "No voting-mode, demographic, blank, overvote, undervote or provisional totals are supplied.",
            "Differences between participation and a contest are unclassified, not inferred undervotes.",
            "Native county codes are not FIPS. No election-year geometry or county mapping is approved.",
            "Native clocks have no declared timezone; no timezone is inferred.",
            "Candidate auxiliary percentage fields are retained literally without an inferred definition.",
            "Original HTML, workbook, archives and text feeds stay private; all factual queries are complete.",
        ])
    return {"county-participation.csv": table(participation[:-1]),
            "statewide-participation.csv": table(participation[-1:]),
            "contest-totals.csv": table(totals), "contest-choices.csv": table(choices),
            "party-totals.csv": table(party_rows), "audit.json": document(audit)}


def package(inputs, script):
    outputs = dict(inputs, **reconcile(inputs))
    outputs[SCRIPT_NAME] = script
    outputs["checksums.json"] = document({
        name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        for name, body in sorted(outputs.items())})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, body in sorted(outputs.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, body, compresslevel=9)
    outputs["complete-query.zip"] = stream.getvalue()
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--original-dir", type=Path)
    mode.add_argument("--reproduce-from", type=Path)
    mode.add_argument("--verify", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = args.verify or args.reproduce_from
    if source:
        inputs = {name: (source / name).read_bytes() for name in BASE_NAMES}
    else:
        inputs = original_inputs(args.original_dir)
    outputs = package(inputs, Path(__file__).read_bytes())
    if args.verify:
        require({path.name for path in source.iterdir() if path.is_file()} == set(outputs),
                "Missing or unexpected query files")
        for name, body in outputs.items():
            require((source / name).read_bytes() == body, "Whole-file reproduction mismatch: " + name)
        print(encoded(dict(verified=True, entire_files=len(outputs),
                           entire_zip_members=len(outputs) - 1)))
    else:
        require(args.output is not None, "--output is required")
        args.output.mkdir(parents=True, exist_ok=False)
        for name, body in outputs.items():
            (args.output / name).write_bytes(body)
        print(outputs["audit.json"].decode("utf-8"))


if __name__ == "__main__":
    main()
