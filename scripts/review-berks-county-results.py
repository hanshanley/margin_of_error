"""Reproduce Berks' separate native participation and candidate-count snapshots."""

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlparse
import zipfile

from bs4 import BeautifulSoup


IDENTITY = dict(year=2026, state_code="PA", county_fips="42011", county="Berks")
MASTER = "cfa31c250b0f43b29519a948682a84dc"
PARENT = "https://www.berkspa.gov/departments/election-services/election-results"
ROOT = "https://services3.arcgis.com/dGYe1jDYrTw1wwpc/arcgis/rest/services/"
TURNOUT = ROOT + "ElectionResults_dashboard_878c3_a00d9_73a7a_53a1e/FeatureServer"
RESULTS = ROOT + "ElectionResults_join_d9974_a925d_3474f_dbc01/FeatureServer"
LAYERS = {"turnout": TURNOUT + "/0", "raw-native": TURNOUT + "/1",
          "results-table": RESULTS + "/1", "joined-results": RESULTS + "/0"}
DENIED_ITEM = "item-776019e4a1ce442ab1d116d0823fdc8d.json"
SERVICE_KEY = re.compile(rb"\b(?:AIza[0-9A-Za-z_-]{35}|[ps]k\.[A-Za-z0-9._-]+)")
TELEMETRY_KEY = re.compile(
    rb"""['"]?(?:[A-Za-z_$]*instrumentationKey|licenseKey)['"]?\s*[:=]\s*['"](?!\[REDACTED_PUBLIC_SERVICE_KEY\])[^'"\r\n]+['"]""",
    re.I,
)


def load_originals(folder):
    receipts = json.loads((folder / "receipts.json").read_bytes())
    names = [r["file"] for r in receipts]
    if (len(names) != len(set(names)) or not names
            or any(Path(name).name != name for name in names)
            or {p.name for p in folder.iterdir()} != set(names) | {"receipts.json"}):
        raise ValueError("Incomplete original receipt inventory")
    raw = {}
    for r in receipts:
        body = (folder / r["file"]).read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        url = urlparse(r["url"])
        if (r.get("status") != 200 or r["bytes"] != len(body) or r["sha256"] != digest
                or url.scheme != "https" or url.netloc not in {
                    "www.berkspa.gov", "www.arcgis.com", "services3.arcgis.com", "www.apache.org"}
                or r.get("screening") != {
                    "original_bytes": len(body), "original_sha256": digest, "replacements": 0}):
            raise ValueError("Original acquisition receipt mismatch")
        if SERVICE_KEY.search(body) or TELEMETRY_KEY.search(body):
            raise ValueError("Unredacted public service key in source")
        raw[r["file"]] = body
        if r["file"].endswith(".json"):
            error = json.loads(body).get("error")
            if error and not (r["file"] == DENIED_ITEM and error.get("code") == 403):
                raise ValueError("Failed API response cannot be a data input")
    return raw, {r["file"]: r for r in receipts}


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError("Missing or invalid native integer")
    return value


def scope(contest):
    if contest == "Governor and Lieutenant Governor":
        return "governor_lieutenant_governor", ""
    for prefix, office in [
        ("Representative in Congress", "us_house"),
        ("Representative in the General Assembly", "state_house"),
        ("Senator in the General Assembly", "state_senate"),
    ]:
        match = re.fullmatch(re.escape(prefix) + r" (\d+)(?:st|nd|rd|th) District", contest)
        if match:
            return office, match[1]
    raise ValueError("Unreviewed native office")


def review(raw, receipts):
    data = {name: json.loads(body) for name, body in raw.items() if name.endswith(".json")}
    parent = BeautifulSoup(raw["official-results-index.html"], "html.parser")
    if (receipts["official-results-index.html"]["url"] != PARENT
            or "https://www.arcgis.com/apps/dashboards/" + MASTER not in {
                a["href"] for a in parent.select("a[href]")}
            or data["dashboard-item.json"]["title"] !=
            "County Of Berks: 2026 General Election Results Master Dashboard"):
        raise ValueError("Wrong official parent or election identity")
    subtitles = set()

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "subtitle" and isinstance(child, str) and "NOVEMBER" in child:
                    subtitles.add(child)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data["dashboard-data.json"])
    if len(subtitles) != 1 or not re.fullmatch(
            r"NOVEMBER 3, 2026 -- UNOFFICIAL RESULTS -- Updated: \d{1,2}-\d{1,2}-2026 \d{1,2}:\d{2} [AP]M",
            next(iter(subtitles), "")):
        raise ValueError("Missing native general-election status and update")
    if b"Apache License" not in raw["APACHE-LICENSE-2.0.txt"]:
        raise ValueError("Missing preserved source license")
    if data.get(DENIED_ITEM, {}).get("error", {}).get("code") != 403:
        raise ValueError("Missing preserved denied-item response")

    def rows(name):
        schema = data[name + "-layer.json"]
        after = data[name + "-layer-after.json"]
        if schema["editingInfo"] != after["editingInfo"] or schema["fields"] != after["fields"]:
            raise ValueError("Source changed during capture")
        ids = data[name + "-ids.json"]
        expected = ids["objectIds"]
        if len(expected) != len(set(expected)) or len(expected) != data[name + "-count.json"]["count"]:
            raise ValueError("Native count and object IDs disagree")
        oid = ids["objectIdFieldName"]
        if oid != schema["objectIdField"]:
            raise ValueError("Changed native object-ID field")
        result = []
        fields = {f["name"] for f in schema["fields"]}
        for filename in sorted(n for n in data if n.startswith(name + "-post-records-")):
            r, page = receipts[filename], data[filename]
            params = r["parameters"]
            if (r["url"] != LAYERS[name] + "/query" or r["method"] != "POST"
                    or params["where"] != "1=1" or params["outFields"] != "*"
                    or params["returnGeometry"] != "false" or page.get("exceededTransferLimit")):
                raise ValueError("Incomplete or unexpected native query")
            chunk = [int(value) for value in params["objectIds"].split(",")]
            got = []
            for feature in page["features"]:
                row = feature["attributes"]
                if "geometry" in feature or set(row) != fields:
                    raise ValueError("Changed full-field query schema")
                got.append(row[oid])
                result.append(row)
            if len(got) != len(set(got)) or set(got) != set(chunk):
                raise ValueError("Incomplete native object-ID batch")
        actual = [r[oid] for r in result]
        if len(actual) != len(set(actual)) or set(actual) != set(expected):
            raise ValueError("Missing or duplicated full native records")
        return result

    units = rows("turnout")
    candidates = rows("raw-native")
    joined = rows("results-table")
    winners = rows("joined-results")
    by_unit = {r["jurisdictionname"]: r for r in units}
    if len(by_unit) != len(units) or not units:
        raise ValueError("Duplicate or missing participation units")
    for row in units:
        if row["jurisdictiontype"] != "Precinct":
            raise ValueError("Changed native geography scope")
        for field in ("regvoters", "ballotscast", "mail", "electionday"):
            integer(row[field])
        if (not row["regvoters"] or row["ballotscast"] > row["regvoters"]
                or row["earlyvote"] is not None
                or row["mail"] + row["electionday"] != row["ballotscast"]):
            raise ValueError("Participation or observed-method arithmetic disagrees")
    candidate_key = lambda r: tuple(r[k] for k in (
        "contest", "jurisdictionname", "candidate", "party", "numvotes", "globalid"))
    if Counter(map(candidate_key, candidates)) != Counter(map(candidate_key, joined)):
        raise ValueError("Raw and joined full candidate tables disagree")
    for row in joined:
        unit = by_unit.get(row["jurisdictionname"])
        if unit is None or row["jurisdictionname_1648237362721"] != row["jurisdictionname"]:
            raise ValueError("Unallocated or mismatched native candidate unit")
        if any(row[f] != unit[f] for f in ("regvoters", "ballotscast", "mail", "earlyvote", "electionday")):
            raise ValueError("Joined participation disagrees with the separate unit table")

    totals, unit_votes, maxima = Counter(), Counter(), {}
    contest_units = defaultdict(set)
    identities = {}
    for row in candidates:
        contest, unit, candidate, party = (row[k] for k in (
            "contest", "jurisdictionname", "candidate", "party"))
        scope(contest)
        key = contest, unit, candidate, party
        if (key in identities or not candidate or not party or row["category"] != "Elected Office"
                or unit not in by_unit):
            raise ValueError("Duplicate, missing or unallocated native candidate identity")
        votes = integer(row["numvotes"])
        identities[key] = votes
        totals[contest, candidate, party] += votes
        unit_votes[contest, unit] += votes
        maxima[contest, unit] = max(maxima.get((contest, unit), 0), votes)
        contest_units[contest].add(unit)
    aggregates = {}
    for feature in data["native-candidate-aggregates.json"]["features"]:
        r = feature["attributes"]
        key = r["contest"], r["candidate"], r["party"]
        if key in aggregates:
            raise ValueError("Duplicate native aggregate")
        aggregates[key] = integer(r["native_votes"])
    if dict(totals) != aggregates:
        raise ValueError("Local candidate totals disagree with native server aggregates")
    winner_scopes = set()
    for row in winners:
        key = row["contest"], row["jurisdictionname"]
        if (key in winner_scopes or row["numvotes"] != maxima.get(key)
                or identities.get((*key, row["candidate"], row["party"])) != row["numvotes"]):
            raise ValueError("Winner-only view disagrees with complete candidate records")
        winner_scopes.add(key)
    if winner_scopes != set(maxima):
        raise ValueError("Incomplete winner-only comparison")

    office_units = defaultdict(Counter)
    house_votes = Counter()
    for contest, names in contest_units.items():
        office, _ = scope(contest)
        office_units[office].update(names)
        for unit in names:
            if unit_votes[contest, unit] > by_unit[unit]["ballotscast"]:
                raise ValueError("Contest candidate votes exceed separately reported ballots")
            if office == "us_house":
                house_votes[unit] += unit_votes[contest, unit]
    if (set(house_votes) != set(by_unit)
            or any(v > by_unit[u]["ballotscast"] for u, v in house_votes.items())
            or office_units["state_house"] != Counter({u: 1 for u in by_unit})):
        raise ValueError("Congress overlap or state-House scope arithmetic disagrees")
    observed = {f: sum(r[f] for r in units) for f in (
        "regvoters", "ballotscast", "mail", "electionday")}
    native = data["native-participation-aggregates.json"]["features"]
    if (len(native) != 1 or native[0]["attributes"] != {
            **{"sum_" + f: value for f, value in observed.items()}, "earlyvote_nonnull": 0}):
        raise ValueError("Separate participation totals disagree with native aggregates")

    county = [dict(**IDENTITY, office=scope(c)[0], district_literal=scope(c)[1],
                   contest=c, candidate=name, party_literal=party, votes=votes)
              for (c, name, party), votes in sorted(totals.items())]
    parties = Counter()
    for (contest, _, party), votes in totals.items():
        parties[contest, party] += votes
    party_rows = [dict(**IDENTITY, office=scope(c)[0], district_literal=scope(c)[1],
                       contest=c, party_literal=p, votes=v)
                  for (c, p), v in sorted(parties.items())]
    contests = [dict(**IDENTITY, office=scope(c)[0], district_literal=scope(c)[1], contest=c,
                     candidate_votes=sum(v for (name, _, _), v in totals.items() if name == c),
                     native_unit_count=len(names),
                     overlapping_unit_ids=json.dumps(sorted(
                         u for u in names if office_units[scope(c)[0]][u] > 1)))
                for c, names in sorted(contest_units.items())]
    participation = [dict(**IDENTITY, registered_voters=observed["regvoters"],
                          ballots_cast=observed["ballotscast"],
                          reported_ballots_per_registered_percent=str(
                              (Decimal(100) * observed["ballotscast"] /
                               observed["regvoters"]).quantize(Decimal(".000001"))),
                          basis="unofficial native ballots cast / native registered voters",
                          native_unit_count=len(units), certified=False,
                          eligible_population_turnout=None, demographic_turnout=None)]
    methods = [dict(**IDENTITY, native_field=f, count=observed.get(f),
                    observed_units=len(units) if f in observed else 0,
                    null_units=len(units) if f == "earlyvote" else 0,
                    absent_units=len(units) if f == "provisional" else 0,
                    explicit_zero_units=sum(r.get(f) == 0 for r in units),
                    status="observed" if f in observed else
                    "field_all_null" if f == "earlyvote" else "field_not_supplied")
               for f in ("mail", "electionday", "earlyvote", "provisional")]
    tables = {"county-candidate-results.csv": county,
              "county-contest-party-totals.csv": party_rows,
              "county-contest-totals.csv": contests,
              "county-participation.csv": participation,
              "county-voting-method-counts.csv": methods,
              "native-precinct-participation.csv": units,
              "native-precinct-candidate-counts.csv": candidates,
              "native-winner-only-view.csv": winners}
    audit = dict(**IDENTITY, status="reviewed_unofficial_county_snapshot", maps_approved=False,
                 native_status_and_update=next(iter(subtitles)), native_header_timezone="unestablished",
                 native_unit_rows=len(units), native_candidate_rows=len(candidates),
                 native_winner_only_rows=len(winners), county_candidate_rows=len(county),
                 contests=len(contests), native_aggregate_matches=True,
                 raw_and_joined_candidate_records_equal=True, stable_capture_metadata=True,
                 candidate_explicit_zeroes=sum(r["numvotes"] == 0 for r in candidates),
                 congressional_scope_overlaps={
                     u: sorted(c for c, names in contest_units.items()
                               if scope(c)[0] == "us_house" and u in names)
                     for u, n in sorted(office_units["us_house"].items()) if n > 1},
                 participation=participation[0], voting_methods=methods,
                 participation_record_edit_ms=sorted({r["last_edited_date"] for r in units}),
                 candidate_record_edit_ms=sorted({r["last_edited_date"] for r in candidates}),
                 denied_item_preserved_not_used=DENIED_ITEM,
                 source_terms="Native metadata and Apache license retained; no new license applied to county data.",
                 qualifications=[
                     "County-only, unofficial, not certified or final counting.",
                     "Candidate votes are not ballots, unique voters or demographic turnout.",
                     "Participation is summed once per native unit, never from repeated candidate joins.",
                     "Early-in-person values are all null; provisional field is absent, not zero.",
                     "Congressional native unit identifiers overlap across districts; no allocation or district geometry.",
                     "Native header, participation and candidate edit timestamps are distinct and retained.",
                     "Winner-only records are not a complete candidate dataset.",
                     "Denied item metadata was not bypassed and is not a successful data acquisition."])
    return tables, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--originals", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw, receipts = load_originals(args.originals)
    tables, audit = review(raw, receipts)
    args.output.mkdir(parents=True, exist_ok=True)
    originals = args.output / "originals"
    originals.mkdir(exist_ok=True)
    for name in raw:
        shutil.copyfile(args.originals / name, originals / name)
    shutil.copyfile(args.originals / "receipts.json", originals / "receipts.json")
    shutil.copyfile(__file__, args.output / "reproduce.py")
    for name, rows in tables.items():
        with (args.output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (args.output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    archive_name = "complete-berks-2026-county-results-01.zip"
    paths = sorted(p for p in args.output.rglob("*")
                   if p.is_file() and p.name not in {"checksums.json", archive_name})
    checks = {p.relative_to(args.output).as_posix(): {
        "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths}
    (args.output / "checksums.json").write_text(json.dumps(checks, indent=2) + "\n")
    with zipfile.ZipFile(args.output / archive_name, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted([*paths, args.output / "checksums.json"]):
            info = zipfile.ZipInfo(path.relative_to(args.output).as_posix(), (2026, 11, 5, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    print(json.dumps({"csv_rows": {k: len(v) for k, v in tables.items()},
                      "archive_bytes": (args.output / archive_name).stat().st_size,
                      "archive_sha256": hashlib.sha256((args.output / archive_name).read_bytes()).hexdigest(),
                      "maps_approved": False}, indent=2))


if __name__ == "__main__":
    main()
