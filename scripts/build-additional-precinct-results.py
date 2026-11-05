"""Acquire audited Minnesota 2026 and original nationwide 2020 precinct results."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import shutil
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import ijson
import requests

sys.path.insert(0, str(Path(__file__).parent))
from importlib import import_module

BASE = import_module("build-precinct-results")
ROOT = BASE.ROOT
MN = "https://electionresults.sos.mn.gov/Select/MediaFiles/Index?ersElectionId=201"
MN_FILES = "https://electionresultsfiles.sos.mn.gov/20261103/"
MN_BOUNDARY = "https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_sos/bdry_votingdistricts/FeatureServer/0"
MN_ITEM = "https://www.arcgis.com/sharing/rest/content/items/6c2c813b33144d49ba993bd86b3a58ba?f=json"
NYT = "https://github.com/TheUpshot/presidential-precinct-map-2020"
NYT_DATA = "https://int.nyt.com/newsgraphics/elections/map-data/2020/national/"


def mn_candidate_rows(text, level):
    rows, seen = [], set()
    for fields in csv.reader(io.StringIO(text), delimiter=";"):
        if not fields:
            continue
        if len(fields) != 16 or fields[0] != "MN":
            raise ValueError("Invalid MN candidate row/state")
        county, precinct, office, title, district, candidate = fields[1:7]
        if not title.startswith("U.S. Representative District ") or int(office) != 103 + int(district):
            raise ValueError("Wrong MN House contest")
        if (level == "state" and (county or precinct)) or (
            level == "county" and (not county or precinct)
        ) or (level == "precinct" and (not county or not precinct)):
            raise ValueError("Wrong MN reporting geography")
        identity = (county, precinct, district, candidate)
        if identity in seen:
            raise ValueError("Duplicate MN candidate/reporting identity")
        seen.add(identity)
        rows.append(dict(county=county, precinct=precinct, district=district,
                         candidate=candidate, name=fields[7], party=fields[10],
                         reported=BASE.integer(fields[11]), units=BASE.integer(fields[12]),
                         votes=BASE.integer(fields[13]), total=BASE.integer(fields[15])))
    if not rows:
        raise ValueError("No MN candidate results")
    return rows


def mn_results(precincts, counties, statewide, names, precinct_table):
    expected = {(r["district"], r["candidate"]): r for r in statewide}
    if len(expected) != len(statewide) or {r["district"] for r in statewide} != set(map(str, range(1, 9))):
        raise ValueError("Missing or duplicate MN district candidates")
    groups, county_groups, state_sums, county_sums = defaultdict(list), defaultdict(list), defaultdict(int), defaultdict(int)
    for r in precincts:
        key = (r["district"], r["candidate"])
        if key not in expected or (r["name"], r["party"]) != (expected[key]["name"], expected[key]["party"]):
            raise ValueError("Unknown MN candidate/party identity")
        if r["county"] not in names or (r["county"], r["precinct"]) not in precinct_table:
            raise ValueError("Unknown MN county/precinct identity")
        if precinct_table[(r["county"], r["precinct"])][3] != r["district"]:
            raise ValueError("MN precinct/district identity mismatch")
        groups[(r["county"], r["precinct"])].append(r)
        state_sums[key] += r["votes"]
        county_sums[(r["county"],) + key] += r["votes"]
    for r in counties:
        county_groups[(r["county"], r["district"])].append(r)
    if len(county_sums) != len(counties) or any(
        county_sums[(r["county"], r["district"], r["candidate"])] != r["votes"] for r in counties
    ) or any(state_sums[key] != r["votes"] for key, r in expected.items()):
        raise ValueError("MN precinct/county/district candidate sums do not reconcile")
    for group in list(groups.values()) + list(county_groups.values()) + [statewide]:
        by_district = defaultdict(list)
        for r in group:
            by_district[r["district"]].append(r)
        for district, candidates in by_district.items():
            if {r["candidate"] for r in candidates} != {c for d, c in expected if d == district}:
                raise ValueError("MN reporting unit omits a candidate")
            if len({r["total"] for r in candidates}) != 1 or sum(r["votes"] for r in candidates) != candidates[0]["total"]:
                raise ValueError("MN candidate votes do not reconcile to reported contest total")
    rows = []
    for (county, precinct), candidates in groups.items():
        if len({r["district"] for r in candidates}) != 1:
            raise ValueError("MN precinct split between House districts")
        parties = defaultdict(int)
        for r in candidates:
            parties[{"DFL": "D", "R": "R"}.get(r["party"], "O")] += r["votes"]
        row = BASE.result(2026, "MN", names[county], precinct_table[(county, precinct)][2],
                          "U.S. House", parties["D"], parties["R"], parties["O"],
                          "Official election-night precinct candidate returns; unofficial until certified", MN)
        row.update(key=f"MN|{county}|{precinct}", precinct_code=precinct, county_code=county)
        rows.append(row)
    return rows


def mn_participation(text, names, precinct_table):
    rows, seen = [], set()
    for f in csv.reader(io.StringIO(text), delimiter=";"):
        if not f:
            continue
        if len(f) != 12 or f[0] != "MN" or (f[1], f[2]) in seen:
            raise ValueError("Invalid or duplicate MN participation identity")
        key = (f[1], f[2])
        seen.add(key)
        if key not in precinct_table or f[1] not in names or f[4] not in {"0", "1"}:
            raise ValueError("Unknown MN participation precinct/reporting flag")
        registered, same_day, roster, absentee, federal, presidential, ballots = map(BASE.integer, f[5:])
        modes = [roster, absentee, federal, presidential]
        modes_reconciled = ballots is not None and None not in modes and ballots == sum(modes)
        denominator = registered + same_day if None not in [registered, same_day] else None
        valid = modes_reconciled and f[4] == "1" and denominator is not None and denominator >= 25 and ballots <= denominator
        rows.append(dict(year=2026, state_code="MN", key=f"MN|{f[1]}|{f[2]}",
                         county=names[f[1]], precinct=f[3], precinct_code=f[2], county_code=f[1],
                         reported=f[4] == "1", registered_at_open=registered,
                         election_day_registrations=same_day, roster_signatures=roster,
                         absentee_ballots=absentee, federal_only_ballots=federal,
                         president_only_ballots=presidential, ballots=ballots, denominator=denominator,
                         ballot_modes_reconciled=modes_reconciled,
                         reported_pct=100 * ballots / denominator if valid else None,
                         denominator_basis="Registered at 7 a.m. plus election-day registrations",
                         quality=("Unofficial reported-ballot fraction; not final turnout" if modes_reconciled
                                  else "Rate withheld: reported voters do not reconcile to ballot modes"),
                         source_url=MN))
    return rows


def nyt_result(feature, fips):
    p = feature["properties"]
    identity = p["GEOID"]
    code = fips.get(identity[:2])
    if not code:
        raise ValueError("Unknown NYT 2020 state FIPS")
    dem, rep, total = [None if p[k] is None else BASE.integer(p[k]) for k in ["votes_dem", "votes_rep", "votes_total"]]
    complete = None not in [dem, rep, total]
    if complete and total < dem + rep:
        raise ValueError("Invalid NYT 2020 candidate totals")
    row = BASE.result(2020, code, identity[:5], identity, "President", dem, rep, total - dem - rep if complete else None,
                      "Source-reported precinct/municipal presidential votes; read original state caveats", NYT)
    row["contest_votes"] = total
    row["boundary_provenance"] = "Source mixes official and reconstructed 2020 boundaries; no per-shape official flag supplied"
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    if (args.output / "index.json").exists() or args.archive.exists():
        raise ValueError("Use a new unpublished output and archive")
    args.output.mkdir(parents=True, exist_ok=True)
    args.sources.mkdir(parents=True, exist_ok=True)
    originals = args.output / "originals"
    originals.mkdir(exist_ok=True)
    sources, external = {}, {}

    def original(name, url):
        cached = args.sources / name
        if not cached.exists():
            response = requests.get(url, timeout=(15, 180))
            response.raise_for_status()
            prefix = response.content[:1000].lstrip().lower()
            if prefix.startswith(b"<!doctype html") or b"<html" in prefix:
                raise ValueError(f"Expected source data, received HTML: {url}")
            cached.write_bytes(response.content)
        sources[name] = url
        if cached.stat().st_size < 90_000_000:
            shutil.copyfile(cached, originals / name)
        else:
            external[name] = dict(source_url=url, bytes=cached.stat().st_size,
                                  sha256=hashlib.sha256(cached.read_bytes()).hexdigest(),
                                  distribution="Full original included in complete ZIP; not duplicated in Git")
        return cached

    def text(name, url):
        return original(name, url).read_text(encoding="utf-8-sig")

    def save(name, value):
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        path.write_bytes(gzip.compress(content, mtime=0) if name.endswith(".gz") else content)

    sys.path.insert(0, str(ROOT.parent / "voter-participation"))
    from scripts.build import simplify

    def geometry(shape):
        if shape is None:
            return None
        polygons = shape["coordinates"] if shape["type"] == "MultiPolygon" else [shape["coordinates"]]
        if shape["type"] not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Unexpected precinct geometry type")
        output = []
        for polygon in polygons:
            rings = []
            for ring in polygon:
                reduced = simplify(ring, .0001)
                rings.append([[round(x, 6), round(y, 6)] for x, y, *rest in
                              (reduced if len(reduced) >= 4 else ring)])
            output.append(rings)
        return dict(type="MultiPolygon", coordinates=output)

    election = json.loads(text("MN-election-identity.json",
        "https://www.arcgis.com/sharing/rest/content/items/6fcc5f80487442de8d0a69eb9f1f0609?f=json"))
    item = json.loads(text("MN-boundary-item.json", MN_ITEM))
    if election["title"] != "2026 Minnesota Election Results" or "September 18, 2026" not in item["description"]:
        raise ValueError("MN election or boundary vintage changed; review before reuse")
    county_table = list(csv.reader(io.StringIO(text("MN-CntyTbl.txt", MN_FILES + "CntyTbl.txt")), delimiter=";"))
    names = {r[0]: r[1] for r in county_table}
    table_rows = list(csv.reader(io.StringIO(text("MN-PrctTbl.txt", MN_FILES + "PrctTbl.txt")), delimiter=";"))
    table = {(r[0], r[1]): r for r in table_rows}
    if len(table) != len(table_rows) or len(names) != 87:
        raise ValueError("Duplicate MN precincts or missing county table")
    feeds = [mn_candidate_rows(text("MN-" + filename, MN_FILES + filename), level) for filename, level in
             [("ushousepct.txt", "precinct"), ("USHouseCty.txt", "county"), ("ushouse.txt", "state")]]
    rows = mn_results(*feeds, names, table)
    participation = mn_participation(text("MN-pctstats.txt", MN_FILES + "pctstats.txt"), names, table)
    contest_votes = {row["key"]: row["contest_votes"] for row in rows}
    for row in participation:
        if row["ballots"] is not None and contest_votes.get(row["key"], 0) > row["ballots"]:
            row.update(reported_pct=None, quality="Rate withheld: House contest votes exceed reported voters")
    save("participation.json.gz", participation)
    count_url = MN_BOUNDARY + "/query?where=1%3D1&returnCountOnly=true&f=json"
    count = json.loads(text("MN-boundary-count.json", count_url))["count"]
    features = []
    for offset in range(0, count, 2000):
        url = requests.Request("GET", MN_BOUNDARY + "/query", params=dict(
            where="1=1", outFields="*", outSR=4326, f="geojson",
            orderByFields="objectid", resultOffset=offset, resultRecordCount=2000)).prepare().url
        page = json.loads(text(f"MN-boundaries-{offset}.geojson", url))
        features += page["features"]
    if len(features) != count:
        raise ValueError("MN paginated boundary count does not reconcile")
    shape_ids = [(str(int(f["properties"]["countycode"])).zfill(2), f["properties"]["pctcode"]) for f in features]
    if len(shape_ids) != len(set(shape_ids)):
        raise ValueError("Duplicate MN boundary identifiers")
    vote_lookup = {(r["county_code"], r["precinct_code"]): r for r in rows}
    stats_lookup = {r["key"]: r for r in participation}
    audit = {}
    for county in names:
        shape_set = {p for c, p in shape_ids if c == county}
        vote_set = {p for c, p in vote_lookup if c == county}
        audit[county] = dict(county=names[county], exact=shape_set == vote_set,
                             boundary_only=sorted(shape_set - vote_set), reporting_only=sorted(vote_set - shape_set))
    mapped = []
    for feature, identity in zip(features, shape_ids):
        row = vote_lookup.get(identity)
        if row is None or not audit[identity[0]]["exact"]:
            continue
        p = dict(row, match_status="matched", boundary_date="2026-09-18")
        stats = stats_lookup.get(row["key"])
        if stats:
            p["participation"] = stats
        mapped.append(dict(type="Feature", properties=p, geometry=geometry(feature["geometry"])))
    save("2026/MN.geojson.gz", dict(type="FeatureCollection", features=mapped))
    notes = ("Official 2026 House precinct votes reconcile candidate-by-candidate to county and district totals. "
             "September 18, 2026 reference boundaries; counties with different precinct sets are withheld. "
             "Unofficial election-night counts, not certified turnout. Complete voting statistics are retained separately.")
    coverage = {"2026": {"MN": dict(file="2026/MN.geojson.gz", source_url=MN, boundary_source=MN_ITEM,
        partial=True, features=len(mapped), colored=sum(f["properties"]["margin_pp"] is not None for f in mapped),
        office="U.S. House", boundary_date="2026-09-18", notes=notes,
        next_action="Review reference-boundary differences, refresh certified returns and verify live interactions.")}, "2020": {}}
    all_rows = list(rows)
    audits = {"2026-MN": audit, "2026-MN-participation": dict(
        rows=len(participation),
        ballot_mode_discrepancies=sum(not r["ballot_modes_reconciled"] for r in participation),
        rates_withheld=sum(r["reported_pct"] is None for r in participation))}
    print("2026 MN:", len(rows), "reporting units;", len(mapped), "mapped;", len(participation), "participation rows", flush=True)

    text("NYT-2020-LICENSE.txt", "https://raw.githubusercontent.com/TheUpshot/presidential-precinct-map-2020/master/LICENSE")
    text("NYT-2020-README.md", "https://raw.githubusercontent.com/TheUpshot/presidential-precinct-map-2020/master/README.md")
    stats = json.loads(text("NYT-2020-statistics.json", NYT_DATA + "precincts-with-results-statistics.json"))
    source = original("NYT-2020-national.geojson.gz", NYT_DATA + "precincts-with-results.geojson.gz")
    states = json.loads((ROOT / "public/voter-participation/data/states.geojson").read_text())["features"]
    fips = {f["properties"]["STATE"]: f["properties"]["STUSAB"] for f in states}
    grouped, seen = defaultdict(list), set()
    with gzip.open(source, "rb") as file:
        for feature in ijson.items(file, "features.item", use_float=True):
            row = nyt_result(feature, fips)
            if row["key"] in seen:
                raise ValueError("Duplicate NYT 2020 state/precinct identity")
            seen.add(row["key"])
            all_rows.append(row)
            grouped[row["state_code"]].append(dict(type="Feature", geometry=geometry(feature["geometry"]),
                                                 properties=dict(row, match_status="matched")))
    if len(grouped) != stats["number_of_states_with_any_coverage"]:
        raise ValueError("NYT 2020 jurisdiction coverage does not match original statistics")
    for code, shapes in sorted(grouped.items()):
        save(f"2020/{code}.geojson.gz", dict(type="FeatureCollection", features=shapes))
        coverage["2020"][code] = dict(file=f"2020/{code}.geojson.gz", source_url=NYT, partial=True,
            features=len(shapes), colored=sum(f["geometry"] is not None and f["properties"]["margin_pp"] is not None for f in shapes),
            office="President", boundary_date="2020 election reference",
            notes="The New York Times / The Upshot original 2020 release, not reallocated 2020 votes on 2024 shapes. "
                  "Source mixes official and reconstructed boundaries without a per-shape official flag. "
                  "Some states use municipal reporting. Missing counties, unjoined returns and omitted write-ins remain missing. "
                  "Read the complete original state caveats and MIT license; candidate votes are not turnout.",
            next_action="Acquire missing counties/precincts and original tabular returns; verify live coverage and retain original source caveats.")
        audits[f"2020-{code}"] = dict(source_shapes=len(shapes),
                                     known_contest_votes=sum(f["properties"]["contest_votes"] or 0 for f in shapes),
                                     missing_vote_rows=sum(f["properties"]["contest_votes"] is None for f in shapes),
                                     geometry_missing=sum(f["geometry"] is None for f in shapes),
                                     reconciliation="D/R/other totals checked within each original source feature; no independent national precinct CSV supplied")
        print("2020", code, len(shapes), "original reporting shapes", flush=True)
    save("audit.json", audits)
    save("sources.json", dict(sources=sources, complete_zip_originals=external))
    save("index.json", dict(coverage=coverage, result_rows=len(all_rows), participation_rows=len(participation),
        metric="Candidate-vote margin is not participation; separate MN participation uses source-defined registered voters.",
        complete_download=args.archive.name, license_file="originals/NYT-2020-LICENSE.txt",
        state_notes="originals/NYT-2020-README.md", attribution="2020: The New York Times / The Upshot; MIT license. Minnesota: Office of the Secretary of State and MnGeo."))
    with gzip.open(args.output / "results.csv.gz", "wt", newline="") as file:
        writer = csv.DictWriter(file, BASE.CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_rows)
    save("checksums.json", {str(p.relative_to(args.output)): dict(bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(args.output.rglob("*")) if p.is_file()})
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for p in sorted(args.output.rglob("*")):
            if p.is_file():
                archive.write(p, str(p.relative_to(args.output)))
        for name in external:
            archive.write(args.sources / name, "originals/" + name)
    print("Completed", len(all_rows), "candidate rows; complete original sources included in ZIP", flush=True)


if __name__ == "__main__":
    main()
