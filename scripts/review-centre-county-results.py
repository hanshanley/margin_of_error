"""Reconcile Centre's complete native PDFs and ArcGIS records in a private package."""

import argparse
from collections import Counter
import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
import zipfile

from bs4 import BeautifulSoup
from pypdf import PdfReader


IDENTITY = dict(year=2026, state_code="PA", county_fips="42027", county="Centre")
INDEX = "https://centrecountypa.gov/3719/2026-General-Election-Unofficial-Results"
LAYER = "https://services3.arcgis.com/HDjl48g0Y109Q9wX/arcgis/rest/services/PrecinctStats/FeatureServer/0"
FILES = {
    "official-results-index.html", "official-results-www.html",
    "official-precinct-summary.pdf", "official-election-summary.pdf",
    "official-results-browser.html", "official-precinct-summary-browser.pdf",
    "official-election-summary-browser.pdf", "declared-experience.json",
    "declared-experience-data.json", "item-55b9957d0d6a4052adcaaecae1907fa5.json",
    "item-4bada947cd6d49b8af28b448784d0a35.json", "precinct-stats-layer.json",
    "precinct-stats-layer-after.json", "precinct-stats-ids.json",
    "precinct-stats-count.json", "precinct-stats-all.json",
}
FAILED = {"official-results-index.html", "official-results-www.html",
          "official-precinct-summary.pdf", "official-election-summary.pdf"}
SERVICE_KEY = re.compile(rb"\b(?:AIza[0-9A-Za-z_-]{35}|[ps]k\.[A-Za-z0-9._-]+)")
TELEMETRY_KEY = re.compile(
    rb"""['"]?(?:[A-Za-z_$]*instrumentationKey|licenseKey)['"]?\s*[:=]\s*['"](?!\[REDACTED_PUBLIC_SERVICE_KEY\])[^'"\r\n]+['"]""",
    re.I,
)
HEADINGS = {
    "GOVERNOR AND LIEUTENANT GOVERNOR": "governor_lieutenant_governor",
    "REPRESENTATIVE IN CONGRESS": "us_house",
    **{"REPRESENTATIVE IN THE GENERAL ASSEMBLY " + suffix + " LEGISLATIVE DISTRICT":
       "state_house_" + suffix[:-2] for suffix in ["77TH", "82ND", "171ST"]},
}
FIELDS = {
    "governor_lieutenant_governor": {
        "DEM JOSH SHAPIRO / AUSTIN": "DEM_JOSH_SHAPIRO_AUSTIN_DAVIS",
        "REP STACY GARRITY / JASON": "REP_STACY_GARRITY_JASON_RICHEY",
        "LIB KEN KRAWCHUK / JOHN": "LIB_KEN_KRAWCHUK_JOHN_THOMAS",
        "Write-In Totals": "Write_in",
    },
    "us_house": {
        "DEM RAY BILGER": "DEM_RAY_BILGER",
        "REP GLENN GT THOMPSON": "REP_GLENN_GT_THOMPSON",
        "Write-In Totals": "Write_in1",
    },
    "state_house_77": {
        "DEM H SCOTT CONKLIN": "DEM_H_SCOTT_CONKLIN",
        "REP MICHELLE SCHELLBERG": "REP_MICHELLE_SCHELLBERG",
        "Write-In Totals": "Write_in2",
    },
    "state_house_82": {
        "DEM PAUL TAKAC": "DEM_PAUL_TAKAC",
        "REP KIRSTEN MCTERNAN": "REP_KIRSTEN_MCTERNAN",
        "Write-In Totals": "Write_in3",
    },
    "state_house_171": {
        "DEM JOHN ZANGARI": "DEM_JOHN_ZANGARI",
        "REP KERRY A BENNINGHOFF": "REP_KERRY_A_BENNINGHOFF",
        "Write-In Totals": "Write_in4",
    },
}
METHODS = ["InPerson", "Mail", "Provisional"]
VECTOR_FIELDS = ["votes", "election_day_votes", "absentee_mail_votes", "provisional_votes"]
CONFLICT_FIELDS = ["native_api_object_id", "native_api_precinct_code", "native_precinct_label",
                   "method_literal", "field_literal", "api_value", "primary_pdf_value",
                   "api_ballots", "usable_as_ballot_accounting"]
RATE_DIFFERENCE_FIELDS = ["native_scope_literal", "native_rate_literal", "calculated_rate",
                          "difference_percentage_points"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    require(type(value) is int and value >= 0, "Missing or invalid native integer")
    return value


def vector(values):
    result = tuple(int(v.replace(",", "")) for v in values)
    require(result[0] == sum(result[1:]), "Native total differs from its methods")
    return result


def total(vectors):
    return tuple(map(sum, zip(*vectors)))


def rate(ballots, registered):
    require(registered > 0, "Missing registered-voter denominator")
    return str((Decimal(ballots) * 100 / registered).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)) + "%"


def load_originals(folder):
    receipts = json.loads((folder / "receipts.json").read_bytes())
    names = [r["path"] for r in receipts]
    require(len(names) == len(set(names)) and set(names) == FILES
            and {p.name for p in folder.iterdir()} == FILES | {"receipts.json"},
            "Incomplete original receipt inventory")
    raw = {}
    for receipt in receipts:
        name = receipt["path"]
        body = (folder / name).read_bytes()
        require(receipt["bytes"] == len(body)
                and receipt["sha256"] == hashlib.sha256(body).hexdigest(),
                "Original acquisition receipt mismatch")
        require(not SERVICE_KEY.search(body) and not TELEMETRY_KEY.search(body),
                "Unredacted public service key in source")
        requested, final = [urlsplit(receipt[k]) for k in ["requested_url", "final_url"]]
        require(requested.scheme == final.scheme == "https"
                and requested.netloc == final.netloc and requested.path == final.path,
                "Unexpected source redirect")
        if name.startswith("official-"):
            expected = INDEX
            if "www" in name:
                expected = INDEX.replace("https://", "https://www.")
            if "precinct-summary" in name:
                expected = "https://centrecountypa.gov/DocumentCenter/View/44859/precinctsummary"
            if "election-summary" in name:
                expected = "https://centrecountypa.gov/DocumentCenter/View/44860/electionsummary"
            require(receipt["requested_url"] == expected, "Unexpected primary report URL")
        elif name.startswith("precinct-stats-"):
            require(receipt["requested_url"].split("?")[0] == LAYER + (
                "" if name in {"precinct-stats-layer.json", "precinct-stats-layer-after.json"} else "/query"),
                "Unexpected native layer URL")
        else:
            item = {"declared-experience.json": "637f95443bd04cb4a891b0f2de161129",
                    "declared-experience-data.json": "637f95443bd04cb4a891b0f2de161129",
                    "item-55b9957d0d6a4052adcaaecae1907fa5.json": "55b9957d0d6a4052adcaaecae1907fa5",
                    "item-4bada947cd6d49b8af28b448784d0a35.json": "4bada947cd6d49b8af28b448784d0a35"}[name]
            require(requested.netloc == "www.arcgis.com"
                    and requested.path == "/sharing/rest/content/items/" + item + (
                        "/data" if name == "declared-experience-data.json" else ""),
                    "Unexpected declared application URL")
        require(receipt["status"] == (404 if name in FAILED else 200),
                "Unexpected acquisition status")
        if name in FAILED:
            require(body == b"", "Changed failed acquisition evidence")
        screening = receipt.get("screening", {})
        require(screening.get("replacements") == (2 if name == "official-results-browser.html" else 0),
                "Missing explicit source screening receipt")
        if name != "official-results-browser.html":
            require(screening.get("original_sha256") == receipt["sha256"]
                    and screening.get("original_bytes") == len(body), "Unexpected source transformation")
        else:
            require(body.count(b"[REDACTED_PUBLIC_SERVICE_KEY]") == 2
                    and screening.get("service_key_replacements") == screening.get("telemetry_key_replacements") == 1
                    and screening.get("original_bytes") == len(body) + screening.get("removed_value_bytes", 0)
                    - 2 * len(b"[REDACTED_PUBLIC_SERVICE_KEY]")
                    and re.fullmatch(r"[a-f0-9]{64}", screening.get("original_sha256", "")),
                    "Missing linking-page redaction provenance")
        raw[name] = body
    require(json.loads(raw["item-55b9957d0d6a4052adcaaecae1907fa5.json"]).get("error", {}).get("code") == 400,
            "Changed inaccessible child-item evidence")
    return raw


def parse_pages(pages, precinct):
    units, contests, annotations, stamps = {}, {}, [], set()
    county = None
    for page_number, text in enumerate(pages, 1):
        require("Centre County" in text and "UNOFFICIAL RESULTS" in text
                and "2026 General Gubernatorial Election" in text and "November 3, 2026" in text,
                "Unreviewed native report identity")
        footer = re.search(r"(Precinct|Election) Summary - ([^\n]+?)\s+(\d+)Page (\d+) of", text)
        require(footer and footer[1] == ("Precinct" if precinct else "Election")
                and int(footer[3]) == len(pages) and int(footer[4]) == page_number,
                "Incomplete native PDF page inventory")
        stamps.add(footer[2])
        unit = None
        if precinct:
            label = re.match(r"(\d+) ([^\n]+)\nCentre County", text)
            require(label is not None, "Missing native precinct label")
            unit = dict(native_report_precinct_id=int(label[1]),
                        native_precinct_label=label[1] + " " + label[2])
            require(unit["native_precinct_label"] not in units, "Duplicate native precinct")
        heads = list(re.finditer(r"^(" + "|".join(re.escape(h) for h in HEADINGS) + r")$", text, re.M))
        require(heads and text.count("Vote For 1") == len(heads), "Unreviewed contest header")
        if precinct or page_number == 1:
            stats = text[:heads[0].start()]
            registered = re.search(r"^Registered Voters - Total ([\d,]+)$", stats, re.M)
            ballots = re.search(r"^([\d,]+)Ballots Cast - Total ([\d,]+) ([\d,]+) ([\d,]+)$", stats, re.M)
            blanks = re.search(r"^([\d,]+)Ballots Cast - Blank ([\d,]+) ([\d,]+) ([\d,]+)$", stats, re.M)
            printed_rate = re.search(r"^Voter Turnout - Total (\d+\.\d{2}%)$", stats, re.M)
            require(registered and ballots and blanks and printed_rate, "Missing primary participation")
            participation = dict(registered_voters=int(registered[1].replace(",", "")),
                                 ballots=vector(ballots.groups()), blanks=vector(blanks.groups()),
                                 registered_voter_rate_literal=printed_rate[1])
            require(all(b <= a for a, b in zip(participation["ballots"], participation["blanks"]))
                    and participation["ballots"][0] <= participation["registered_voters"]
                    and Decimal(printed_rate[1][:-1]) <= 100,
                    "Invalid primary participation accounting")
            participation["registered_voter_rate_calculated"] = rate(
                participation["ballots"][0], participation["registered_voters"])
            participation["registered_voter_rate_difference_percentage_points"] = str(
                Decimal(printed_rate[1][:-1]) - Decimal(participation["registered_voter_rate_calculated"][:-1]))
            if precinct:
                unit.update(participation)
                units[unit["native_precinct_label"]] = unit
            else:
                county = participation
                county["reporting_lines"] = [line for line in stats.splitlines()
                    if re.match(r"(Election Day Precincts Reporting|Precincts Complete|"
                                r"Precincts Partially Reported|Absentee/ Early Precincts Reporting) ", line)]
                require(len(county["reporting_lines"]) == 4, "Missing native reporting qualifications")
        seen = set()
        for i, head in enumerate(heads):
            office = HEADINGS[head[1]]
            require(office not in seen, "Duplicate report contest")
            seen.add(office)
            block = text[head.end():heads[i + 1].start() if i + 1 < len(heads) else footer.start()]
            rows = {}
            for label, *values in re.findall(r"^(.+?) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+)$", block, re.M):
                require(label not in rows, "Duplicate report option")
                rows[label] = vector(values)
            annotation_names = {"Not Assigned", "Write-In: ASD"} if office == "governor_lieutenant_governor" else {"Not Assigned"}
            require(set(rows) == set(FIELDS[office]) | annotation_names | {"Total Votes Cast", "Contest Totals"},
                    "Incomplete native option or annotation inventory")
            require(total([rows[k] for k in FIELDS[office]]) == rows["Total Votes Cast"]
                    and total([rows[k] for k in annotation_names]) == rows["Write-In Totals"]
                    and all(v <= b for v, b in zip(rows["Total Votes Cast"], rows["Contest Totals"])),
                    "Invalid primary contest accounting")
            if precinct:
                require(rows["Contest Totals"] == unit["ballots"], "Contest ballot scope mismatch")
            else:
                reporting = re.search(r"Precincts Reporting (\d+) of (\d+)", block)
                require(reporting and reporting[1] == reporting[2], "Missing native contest reporting")
            key = (unit["native_precinct_label"] if unit else "County", office)
            require(key not in contests, "Duplicate native contest scope")
            contests[key] = dict(rows=rows, contest_literal=head[1],
                                 precincts_reporting=None if precinct else int(reporting[1]))
            for name in sorted(annotation_names):
                annotations.append(dict(scope=key[0], office=office, annotation_literal=name,
                                        **dict(zip(VECTOR_FIELDS, rows[name]))))
        if precinct:
            require({"governor_lieutenant_governor", "us_house"} <= seen
                    and len(seen) == 3, "Missing or ambiguous native state-House scope")
            unit["state_house_scope"] = next(c for c in seen if c.startswith("state_house_"))
    require(len(stamps) == 1, "Mixed native PDF report updates")
    return units, contests, annotations, county, next(iter(stamps))


def review(raw):
    soup = BeautifulSoup(raw["official-results-browser.html"], "html.parser")
    links = {a.get("href") for a in soup.select("a[href]")}
    require(any("637f95443bd04cb4a891b0f2de161129" in h for h in links)
            and {"/DocumentCenter/View/44859/precinctsummary",
                 "/DocumentCenter/View/44860/electionsummary"} <= links,
            "Primary page does not declare reviewed sources")
    index_ids = [int(m[1]) for a in soup.select("a[href]")
                 if (m := re.fullmatch(r"(\d+) - .+", a.get_text(" ", strip=True)))]
    index_update = re.search(r"Updated:\s*(\d+/\d+/\d{4} at \d+:\d+ [ap]m)",
                             soup.get_text(" ", strip=True))
    require(index_update is not None, "Missing native index update")
    units, detail, annotations, _, precinct_update = parse_pages(
        [p.extract_text() for p in PdfReader(io.BytesIO(raw["official-precinct-summary-browser.pdf"])).pages], True)
    _, county_contests, county_annotations, county, county_update = parse_pages(
        [p.extract_text() for p in PdfReader(io.BytesIO(raw["official-election-summary-browser.pdf"])).pages], False)
    require(len(units) == 87 and len(index_ids) == len(set(index_ids)) == 87
            and set(index_ids) == {u["native_report_precinct_id"] for u in units.values()},
            "Primary precinct inventories differ")
    require(set(k[1] for k in county_contests) == set(FIELDS), "Incomplete county contests")
    require(sum(u["registered_voters"] for u in units.values()) == county["registered_voters"]
            and total([u["ballots"] for u in units.values()]) == county["ballots"]
            and total([u["blanks"] for u in units.values()]) == county["blanks"],
            "County and precinct participation differ")
    for (_, office), contest in county_contests.items():
        scope = [d for (_, code), d in detail.items() if code == office]
        require(len(scope) == contest["precincts_reporting"], "Native district reporting scope differs")
        for label in contest["rows"]:
            require(total([d["rows"][label] for d in scope]) == contest["rows"][label],
                    "County and precinct contest totals differ")
    metadata = json.loads(raw["precinct-stats-layer.json"])
    after = json.loads(raw["precinct-stats-layer-after.json"])
    require(metadata["fields"] == after["fields"] and metadata["editingInfo"] == after["editingInfo"],
            "Native layer changed during acquisition")
    feature_set = json.loads(raw["precinct-stats-all.json"])
    require(not feature_set.get("exceededTransferLimit"), "Native layer export is truncated")
    observations = [f["attributes"] for f in feature_set["features"]]
    oid = metadata["objectIdField"]
    ids = json.loads(raw["precinct-stats-ids.json"])["objectIds"]
    require(len(ids) == len(set(ids)) == len(observations)
            == json.loads(raw["precinct-stats-count.json"])["count"] == 261
            and {r[oid] for r in observations} == set(ids),
            "Incomplete independent ArcGIS object inventory")
    groups, api_codes, crosswalk, conflicts = {}, {}, [], []
    for row in observations:
        label, method = row["PRECINCT_NAME"], row["VotingType"]
        require(label in units and method in METHODS and (label, method) not in groups,
                "Unmatched or duplicate native precinct method")
        groups[label, method] = row
        unit = units[label]
        code = integer(row["PRECINCT_CODE"])
        require(api_codes.setdefault(label, code) == code, "Inconsistent API precinct code")
        pos = METHODS.index(method) + 1
        require(integer(row["BALLOTS_CAST_TOTAL"]) == unit["ballots"][pos],
                "Native API and PDF ballots differ")
        require(row["REGISTERED_VOTERS_TOTAL"] == (
            unit["registered_voters"] if method == "InPerson" else None),
            "Native registration null/zero or scope differs")
        if method == "InPerson":
            integer(row["REGISTERED_VOTERS_TOTAL"])
        for office, fields in FIELDS.items():
            active = office in {"governor_lieutenant_governor", "us_house", unit["state_house_scope"]}
            for option, field in fields.items():
                require(integer(row[field]) == (detail[label, office]["rows"][option][pos] if active else 0),
                        "Native API option counts or district scopes differ")
        blank = integer(row["BALLOTS_CAST_BLANK"])
        pdf_blank = unit["blanks"][pos]
        if blank != pdf_blank:
            require(method == "Provisional" and blank > row["BALLOTS_CAST_TOTAL"],
                    "Unreviewed native blank-ballot discrepancy")
            conflicts.append(dict(zip(CONFLICT_FIELDS, [
                row[oid], code, label, method, "BALLOTS_CAST_BLANK", blank, pdf_blank,
                row["BALLOTS_CAST_TOTAL"], False])))
    require(len(groups) == 3 * len(units) and len(set(api_codes.values())) == len(units),
            "Incomplete precinct-method identity crosswalk")
    participation, options, county_options, party_totals, contest_totals = [], [], [], [], []
    for label, unit in units.items():
        crosswalk.append(dict(native_report_precinct_id=unit["native_report_precinct_id"],
                              native_precinct_label=label, native_api_precinct_code=api_codes[label],
                              state_house_scope_from_pdf=unit["state_house_scope"]))
        participation.append(dict(**IDENTITY, **crosswalk[-1], registered_voters=unit["registered_voters"],
            ballots=unit["ballots"][0], election_day_ballots=unit["ballots"][1],
            absentee_mail_ballots=unit["ballots"][2], provisional_ballots=unit["ballots"][3],
            blank_ballots=unit["blanks"][0], registered_voter_rate_literal=unit["registered_voter_rate_literal"],
            registered_voter_rate_calculated=unit["registered_voter_rate_calculated"],
            registered_voter_rate_difference_percentage_points=unit["registered_voter_rate_difference_percentage_points"]))
    for source, output in [(detail, options), (county_contests, county_options)]:
        for (label, office), contest in source.items():
            parties = Counter()
            for option, field in FIELDS[office].items():
                values = contest["rows"][option]
                party = option.split(" ", 1)[0] if option != "Write-In Totals" else ""
                output.append(dict(**IDENTITY, native_scope_literal=label, office=office,
                    contest_literal=contest["contest_literal"], option_literal=option,
                    native_party_literal=party, native_api_field=field, **dict(zip(VECTOR_FIELDS, values))))
                if party:
                    parties[party] += values[0]
            if source is county_contests:
                for party, votes in parties.items():
                    party_totals.append(dict(**IDENTITY, office=office, native_party_literal=party, votes=votes))
                contest_totals.append(dict(**IDENTITY, office=office,
                    candidate_votes=contest["rows"]["Total Votes Cast"][0],
                    contest_ballots=contest["rows"]["Contest Totals"][0],
                    ballot_residual_unclassified=contest["rows"]["Contest Totals"][0]
                    - contest["rows"]["Total Votes Cast"][0], precincts_reporting=contest["precincts_reporting"]))
    county_row = dict(**IDENTITY, registered_voters=county["registered_voters"],
        ballots=county["ballots"][0], blank_ballots_from_pdf=county["blanks"][0],
        registered_voter_rate_literal=county["registered_voter_rate_literal"],
        registered_voter_rate_calculated=county["registered_voter_rate_calculated"],
        registered_voter_rate_difference_percentage_points=county["registered_voter_rate_difference_percentage_points"],
        house_candidate_votes=county_contests["County", "us_house"]["rows"]["Total Votes Cast"][0],
        house_ballot_residual_unclassified=county["ballots"][0]
        - county_contests["County", "us_house"]["rows"]["Total Votes Cast"][0])
    method_rows = [dict(**IDENTITY, method_literal=m, ballots=county["ballots"][i + 1],
        blank_ballots_from_pdf=county["blanks"][i + 1],
        blank_ballots_from_api=sum(r["BALLOTS_CAST_BLANK"] for r in observations if r["VotingType"] == m),
        api_blank_accounting_usable=not any(c["method_literal"] == m for c in conflicts))
        for i, m in enumerate(METHODS)]
    updates = [dict(source=name, native_update_literal=value, declared_timezone="")
        for name, value in [("official_index", index_update[1]), ("county_pdf", county_update),
                            ("precinct_pdf", precinct_update)]]
    updates.extend(dict(source="arcgis_" + key, native_update_literal=str(value), declared_timezone="UTC milliseconds")
                   for key, value in metadata["editingInfo"].items())
    rate_differences = [dict(zip(RATE_DIFFERENCE_FIELDS, [
        label, unit["registered_voter_rate_literal"], unit["registered_voter_rate_calculated"],
        unit["registered_voter_rate_difference_percentage_points"]]))
        for label, unit in [*units.items(), ("County", county)]
        if Decimal(unit["registered_voter_rate_difference_percentage_points"]) != 0]
    tables = {"county-participation.csv": [county_row], "county-ballot-methods.csv": method_rows,
        "county-contest-option-results.csv": county_options, "county-contest-party-totals.csv": party_totals,
        "county-contest-totals.csv": contest_totals, "native-precinct-participation.csv": participation,
        "native-precinct-option-results.csv": options, "native-pdf-write-in-breakdown.csv": annotations + county_annotations,
        "native-precinct-identity-crosswalk.csv": crosswalk, "native-api-observations.csv": observations,
        "native-source-conflicts.csv": conflicts, "native-source-updates.csv": updates,
        "native-printed-rate-differences.csv": rate_differences}
    audit = dict(**IDENTITY, county_participation=county_row, county_ballot_methods=method_rows,
        native_precincts=len(units), native_api_records=len(observations),
        state_house_precinct_scopes=dict(Counter(u["state_house_scope"] for u in units.values())),
        api_precinct_codes_differ_from_report_ids=sum(
            api_codes[label] != u["native_report_precinct_id"] for label, u in units.items()),
        native_reporting_qualifications=county["reporting_lines"],
        native_conflict_rows=len(conflicts),
        conflicting_api_blank_total=sum(c["api_value"] for c in conflicts),
        native_printed_rate_difference_rows=len(rate_differences),
        table_rows={name: len(rows) for name, rows in tables.items()},
        publication_approved=False, new_maps_approved=False,
        limitations=[
            "Unofficial and partially reported; reporting precincts are not completed counting or certification.",
            "Registered-voter participation is not eligible-population or demographic-group turnout.",
            "Native printed percentages and ratios calculated from printed counts are separate; differences are retained.",
            "API PRECINCT_CODE is not the printed report precinct ID; join by the full native precinct label.",
            "State-House membership comes from explicit PDF headings, not zero candidate columns.",
            "Provisional API blank counts conflict with primary PDFs and exceed API ballots; unusable as accounting.",
            "Primary PDF blank counts are retained independently, without altering conflicting API observations.",
            "Absent API method registrations remain null, not zero or duplicated county registrations.",
            "Write-in breakdowns are annotations, not additional candidate votes or inferred party votes.",
            "Candidate totals and unclassified ballot residuals are not participation or inferred undervotes.",
            "Source update literals retain their separate meanings and undeclared PDF/index timezones.",
            "One linking-page service key and one telemetry key were redacted; the private original is not packaged.",
            "This private complete review is not a public release or a change to the live map.",
        ])
    return tables, audit


def reproduce(originals, output):
    tables, audit = review(load_originals(originals))
    output.mkdir(parents=True, exist_ok=False)
    for name, rows in tables.items():
        with (output / name).open("w", newline="") as stream:
            empty_fields = {"native-source-conflicts.csv": CONFLICT_FIELDS,
                            "native-printed-rate-differences.csv": RATE_DIFFERENCE_FIELDS}
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else empty_fields[name])
            writer.writeheader()
            writer.writerows(rows)
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    shutil.copytree(originals, output / "originals")
    shutil.copyfile(__file__, output / "review-centre-county-results.py")
    members = {str(p.relative_to(output)): p.read_bytes() for p in sorted(output.rglob("*")) if p.is_file()}
    checksums = {name: dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest()) for name, body in members.items()}
    members["checksums.json"] = (json.dumps(checksums, indent=2) + "\n").encode()
    (output / "checksums.json").write_bytes(members["checksums.json"])
    with zipfile.ZipFile(output / "private-centre-2026-native-review-01.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(members.items()):
            item = zipfile.ZipInfo(name, (2026, 11, 6, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o644 << 16
            archive.writestr(item, body)
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--originals", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(reproduce(args.originals, args.private_output), indent=2))
