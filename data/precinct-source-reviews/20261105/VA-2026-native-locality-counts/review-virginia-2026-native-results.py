"""Review Virginia's original 2026 reports without repairing source accounting gaps."""

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import zipfile


MODES = ["Provisional", "Post-Election", "Election Day", "Early Voting", "Mailed Absentee"]
DEMOGRAPHIC_FIELDS = ["LocalityName", "CongressionalDistrict", "AgeRange", "Gender",
                      "Reason", "ApplicationType", "ReceiptType", "TheCount"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def count(value):
    require(isinstance(value, str) and (value == "" or re.fullmatch(r"[0-9]+", value)),
            "Invalid native count")
    return int(value) if value else None


def english(translations):
    found = [item["text"] for item in translations if item["languageId"] == "en"]
    require(len(found) == 1, "Missing or ambiguous English source label")
    return found[0]


def candidate_count(row):
    write_in = row["CandidateId"] == "wi-" + row["OfficeId"]
    if write_in:
        require(row["CandidateName"] == "WRITE IN VOTES" and row["TOTAL_VOTES"] == "",
                "Unreviewed native write-in columns")
    else:
        require(row["CandidateName"] != "WRITE IN VOTES" and row["WriteInVote"] == "0",
                "Unexpected named-candidate write-in count")
    field = "WriteInVote" if write_in else "TOTAL_VOTES"
    value = count(row[field])
    require(value is not None, "Missing native candidate count")
    return value, field


def review_demographics(rows, data):
    require(rows and list(rows[0]) == DEMOGRAPHIC_FIELDS, "Changed native demographic schema")
    applications, returned, seen = Counter(), Counter(), set()
    normalized, grouped = [], {}
    for ordinal, row in enumerate(rows, 2):
        require(None not in row and None not in row.values(), "Malformed demographic CSV")
        key = tuple(row[field] for field in DEMOGRAPHIC_FIELDS[:-1])
        require(key not in seen, "Duplicate demographic dimensions")
        seen.add(key)
        value = count(row["TheCount"])
        require(value is not None, "Missing demographic count")
        applications[row["ApplicationType"]] += value
        receipt = row["ReceiptType"]
        if receipt:
            returned[receipt] += value
        group_key = tuple(row[field] for field in DEMOGRAPHIC_FIELDS[:4])
        group = grouped.setdefault(group_key, dict(year=2026, state_code="VA",
            locality=row["LocalityName"], district=row["CongressionalDistrict"],
            age_range=row["AgeRange"], gender=row["Gender"],
            absentee_applications=0, returned_absentee_ballots=None,
            registered_voters=None, turnout_rate=None))
        group["absentee_applications"] += value
        if receipt:
            group["returned_absentee_ballots"] = (group["returned_absentee_ballots"] or 0) + value
        normalized.append(dict(year=2026, state_code="VA", **row,
            applications=value, returned_ballots=value if receipt else None, source_row=ordinal))
    sections = {english(section["name"]): section for section in data["statistics"]}
    groups = {english(group["name"]): group
              for group in sections["Absentee (updates at noon each day)"]["groups"]}
    for label, actual in [("Absentee Applications by Application Type", applications),
                          ("Absentee Ballots Returned by Method", returned)]:
        expected = {}
        for item in groups[label]["children"]:
            value = item["value"]
            require(isinstance(value, (int, float)) and not isinstance(value, bool)
                    and value >= 0 and value == int(value), "Missing native statistic")
            name = english(item["name"])
            require(name not in expected, "Duplicate native statistic label")
            expected[name] = int(value)
        require(dict(actual) == expected, "Native demographic/statistic conflict: " + label)
    review = dict(native_rows=len(rows), demographic_groups=len(grouped),
        absentee_applications=sum(applications.values()),
        returned_absentee_ballots=sum(returned.values()),
        application_type_totals=dict(applications), receipt_type_totals=dict(returned),
        all_native_application_and_returned_method_totals_match=True,
        blank_receipt_type="Not reported; not silently converted to a returned-ballot zero",
        scope="Absentee applications and their explicitly reported returned-ballot subsets only; "
              "not all voting, final turnout, accepted/countable ballots or group turnout rates.")
    return review, normalized, [grouped[key] for key in sorted(grouped)]


def review_candidates(rows, data):
    offices = {}
    for item in data["ballotItems"]:
        name = english(item["name"])
        if re.fullmatch(r"Member, House of Representatives \(\d+(?:st|nd|rd|th) District\)", name):
            require(name not in offices, "Duplicate native House summary")
            offices[name] = item
    require(len(offices) == 11, "Incomplete native House summary set")
    expected, actual, units, identities = {}, defaultdict(Counter), {}, set()
    for name, item in offices.items():
        options = item["summaryResults"]["ballotOptions"]
        expected[name] = {option["nativeId"]: option["voteCount"] for option in options}
        require(len(expected[name]) == len(options), "Duplicate native candidate identity")
        require(all(type(v) is int and v >= 0 for v in expected[name].values()),
                "Missing native summary candidate count")
        require(sum(expected[name].values()) == item["voteTotal"], "Native summary accounting gap")
    for ordinal, row in enumerate(rows, 2):
        require(None not in row and None not in row.values(), "Malformed original results CSV")
        require((row["ElectionName"], row["ElectionDate"], row["ElectionType"]) ==
                ("2026 November General", "2026-11-03", "General"), "Wrong native result election")
        if row["OfficeTitle"] not in offices:
            require("House of Representatives" not in row["OfficeTitle"], "Unmatched House office")
            continue
        name = row["OfficeTitle"]
        district = re.search(r"\((\d+)", name).group(1)
        require(row["DistrictType"] == "congressional" and int(row["DistrictName"]) == int(district)
                and row["NumberOfSeats"] == "1", "Native House scope conflict")
        require(row["CandidateId"] in expected[name], "Unmatched native candidate identity")
        key = (row["LocalityCode"], row["PrecinctId"], name)
        identity = key + (row["CandidateId"],)
        require(identity not in identities, "Duplicate native candidate cell")
        identities.add(identity)
        value, field = candidate_count(row)
        actual[name][row["CandidateId"]] += value
        unit = units.setdefault(key, dict(year=2026, state_code="VA",
            locality_code=row["LocalityCode"], locality=row["LocalityName"],
            precinct_id=row["PrecinctId"], precinct=row["PrecinctName"],
            district=district, office_id=row["OfficeId"], candidates=[],
            registered_voters=None, ballots=None, turnout_rate=None, maps_approved=False))
        require((unit["locality"], unit["precinct"], unit["office_id"]) ==
                (row["LocalityName"], row["PrecinctName"], row["OfficeId"]),
                "Conflicting native reporting-unit identity")
        unit["candidates"].append(dict(id=row["CandidateId"], name=row["CandidateName"],
            party=row["Party"], votes=value, native_count_field=field, source_row=ordinal))
    conflicts = []
    for name in sorted(offices):
        require(set(actual[name]) == set(expected[name]), "Incomplete native candidate identities")
        if dict(actual[name]) != expected[name]:
            conflicts.append(dict(office=name, original_csv=dict(actual[name]),
                                  native_summary=expected[name]))
    for key, unit in units.items():
        require({c["id"] for c in unit["candidates"]} == set(expected[key[2]]),
                "Incomplete precinct candidate vector")
        unit["candidate_votes"] = sum(c["votes"] for c in unit["candidates"])
        unit["state_candidate_vector_matches"] = dict(actual[key[2]]) == expected[key[2]]
        unit["candidates"] = json.dumps(unit["candidates"], ensure_ascii=True, separators=(",", ":"))
    return dict(units=len(units), native_candidate_cells=len(identities),
        original_csv_candidate_votes=sum(sum(v.values()) for v in actual.values()),
        summary_candidate_votes=sum(sum(v.values()) for v in expected.values()),
        candidate_vector_conflicts=conflicts, maps_approved=False), [units[k] for k in sorted(units)]


def review_turnout(rows, results, data):
    names = defaultdict(set)
    for row in results:
        names[row["LocalityName"]].add(row["LocalityCode"])
    require(all(len(codes) == 1 for codes in names.values()), "Ambiguous native locality names")
    localities = {item["id"].lower(): item["mapFeatureId"] for item in data["jurisdiction"]["childLocalities"]}
    registration = {}
    for item in data["voterRegistration"]:
        code = localities[item["id"].lower()]
        require(code not in registration, "Duplicate native locality registration")
        registration[code] = item
    seen, normalized, totals = set(), [], defaultdict(lambda: Counter())
    for ordinal, row in enumerate(rows, 2):
        require(None not in row and None not in row.values(), "Malformed turnout CSV")
        require((row["election"], row["election_date"]) ==
                ("2026 November General", "11/03/2026 00:00:00"), "Wrong native turnout election")
        require(row["locality"] in names, "Unmatched native turnout locality")
        code = next(iter(names[row["locality"]]))
        key = (code, row["precinct"])
        require(key not in seen, "Duplicate native turnout reporting unit")
        seen.add(key)
        values = {field: count(row[field]) for field in
                  [*MODES, "TotalVoteTurnout", "ActiveRegisteredVoters",
                   "InactiveRegisteredVoters", "TotalRegisteredVoters"]}
        flags = []
        if values["TotalVoteTurnout"] is None:
            flags.append("missing_total_vote_turnout")
        if any(values[field] is None for field in MODES):
            flags.append("incomplete_mode_vector")
        elif sum(values[field] for field in MODES) != values["TotalVoteTurnout"]:
            flags.append("mode_total_conflict")
        a, b, total = [values[field] for field in
                      ["ActiveRegisteredVoters", "InactiveRegisteredVoters", "TotalRegisteredVoters"]]
        if a is None or b is None or total is None:
            flags.append("missing_registration")
        elif a + b != total:
            flags.append("registration_component_conflict")
        for field in ["ActiveRegisteredVoters", "InactiveRegisteredVoters", "TotalRegisteredVoters"]:
            if values[field] is not None:
                totals[code][field] += values[field]
        normalized.append(dict(year=2026, state_code="VA", locality_code=code,
            locality=row["locality"], precinct=row["precinct"], **values,
            turnout_rate=None, quality_flags=";".join(flags), source_row=ordinal))
    require(set(totals) == set(registration) and len(totals) == 133, "Incomplete locality scope")
    conflicts = []
    for code, values in sorted(totals.items()):
        expected = registration[code]
        if [values[k] for k in ["ActiveRegisteredVoters", "InactiveRegisteredVoters",
                               "TotalRegisteredVoters"]] != [expected[k] for k in
                               ["activeVoters", "inactiveVoters", "total"]]:
            conflicts.append(dict(locality_code=code, original_csv=dict(values),
                native_summary={k: expected[k] for k in ["activeVoters", "inactiveVoters", "total"]}))
    return dict(units=len(normalized), missing_total_vote_turnout=sum(
        row["TotalVoteTurnout"] is None for row in normalized),
        known_vote_turnout_subtotal=sum(row["TotalVoteTurnout"] for row in normalized
                                       if row["TotalVoteTurnout"] is not None),
        registration_conflicts=conflicts, turnout_rates_available=False,
        scope="Native precinct totals and modes remain uncorrected; blank totals/modes are missing. "
              "Known-count subtotals are not statewide turnout. No candidate votes substitute for ballots."
        ), normalized


def verified(source, key, receipt):
    body = gzip.decompress((source / "originals" / (key + ".gz")).read_bytes())
    require(len(body) == receipt["bytes"] and hashlib.sha256(body).hexdigest() == receipt["sha256"],
            "Source hash mismatch: " + key)
    require(receipt["status"] == 200, "Non-success source response")
    return body


def build_review(source, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing immutable review overwrite")
    sources = json.loads((source / "sources.json").read_text())
    originals = {key: verified(source, key, receipt) for key, receipt in sources.items()}
    keys = [key for key, receipt in sources.items() if receipt["url"].endswith(
        "/api/elections/virginia/2026-November-General/data")]
    require(len(keys) == 1, "Ambiguous native election snapshot")
    data = json.loads(originals[keys[0]])
    require(data["election"]["electionDate"] == "2026-11-03"
            and english(data["election"]["name"]) == "2026 November General"
            and data["election"]["isProduction"] is True
            and data["election"]["isOfficialResults"] is False, "Unreviewed native election identity")
    reports = {}
    for key in ["report-election-results", "report-election-turnout", "report-enrabsenteerawcsv"]:
        reports[key] = list(csv.DictReader(io.StringIO(
            originals[key].decode(sources[key]["reviewed_csv_encoding"]))))
    candidates, candidate_rows = review_candidates(reports["report-election-results"], data)
    turnout, turnout_rows = review_turnout(reports["report-election-turnout"],
                                           reports["report-election-results"], data)
    demographics, native_groups, grouped_rows = review_demographics(
        reports["report-enrabsenteerawcsv"], data)
    result = dict(year=2026, state_code="VA", election_date=data["election"]["electionDate"],
        as_of=data["election"]["asOf"], publish_version_id=data["election"]["publishVersionId"],
        is_official=False, original_files=len(sources), original_result_rows=len(
            reports["report-election-results"]), candidates=candidates, turnout=turnout,
        demographics=demographics, maps_approved=False, geometry_approved=False,
        rates_available=False, method="Candidate and write-in columns have different native semantics. "
            "Each native House vector is compared independently to the newer statewide JSON. "
            "All original source conflicts, missing counts and literal demographic categories remain. "
            "Returned absentee counts are not all voting, accepted ballots or group turnout rates.")
    output.mkdir(parents=True)
    package = output / "source-package"
    package.mkdir()
    shutil.copytree(source / "originals", package / "originals")
    for name in ["sources.json", "official-2026-advertised-reports.json"]:
        shutil.copyfile(source / name, package / name)
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output / "counts-review.json").write_text(json.dumps(result, indent=2) + "\n")
    for name, rows in [("precinct-counts.csv", candidate_rows),
                       ("precinct-turnout.csv", turnout_rows),
                       ("native-demographic-records.csv", native_groups),
                       ("demographic-participation.csv", grouped_rows)]:
        with (output / name).open("w") as target:
            writer = csv.DictWriter(target, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (output / "checksums.json").write_text(json.dumps({
        path.relative_to(output).as_posix(): dict(bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(output.rglob("*")) if path.is_file()
    }, separators=(",", ":")))
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as target:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                item = zipfile.ZipInfo(path.relative_to(output).as_posix())
                item.external_attr = 0o644 << 16
                target.writestr(item, path.read_bytes())
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["source", "output", "archive"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = build_review(args.source, args.output, args.archive)
    print(json.dumps({key: value for key, value in result.items()
                      if key not in {"candidates", "turnout"}}, indent=2))
