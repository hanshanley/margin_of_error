"""Build independently audited precinct candidate-result layers, newest elections first."""

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import shutil
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import requests
import shapefile
from pyproj import CRS, Transformer


ROOT = Path(__file__).resolve().parents[1]
NYT = "https://github.com/nytimes/presidential-precinct-map-2024"
NM = "https://electionresults.sos.nm.gov/resultsSW.aspx?type=FED&map=CTY"
NC = "https://www.ncsbe.gov/results-data/election-results/historical-election-results-data"
DE = "https://elections.delaware.gov/results/enr/GE2026.html"
NYT_DATA = "https://int.nyt.com/newsgraphics/elections/map-data/2024/national/"
CSV_FIELDS = ["year", "state_code", "key", "county", "precinct", "office",
              "democratic_votes", "republican_votes", "other_votes", "contest_votes",
              "margin_pp", "ballot_scope", "reporting_unit_kind", "source_url"]


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def integer(value):
    if str(value).strip() == "*":
        return None
    value = int(str(value).replace(",", "").strip())
    if value < 0:
        raise ValueError("Negative candidate votes")
    return value


def result(year, code, county, precinct, office, dem, rep, other, scope, source, kind="precinct"):
    votes = [dem, rep, other]
    total = sum(votes) if all(value is not None for value in votes) else None
    return dict(year=year, state_code=code, key=f"{code}|{county}|{precinct}", county=county,
                precinct=precinct, office=office, democratic_votes=dem, republican_votes=rep,
                other_votes=other, contest_votes=total,
                margin_pp=100 * (dem - rep) / total if total else None,
                ballot_scope=scope, reporting_unit_kind=kind, source_url=source)


def nm_results(precinct_feeds, county_feeds):
    groups, county_counts = defaultdict(list), defaultdict(list)
    seen = set()
    for row in precinct_feeds:
        if int(row["RaceID"]) not in {11186, 11187, 11188} or row["OfficeSeqNo"] != "190":
            raise ValueError("Wrong NM House election/contest identity")
        key = (int(row["RaceID"]), row["CountyName"], row["CandidateID"])
        identity = key + (row["PrecinctName"],)
        if identity in seen:
            raise ValueError("Duplicate NM candidate/precinct identity")
        seen.add(identity)
        county_counts[key].append(integer(row["calcCandidateVotes"]))
        groups[(row["CountyName"], row["PrecinctName"])].append(row)
    expected = {(int(r["RaceID"]), r["CountyName"], r["CandidateID"]): integer(r["calcCandidateVotes"])
                for r in county_feeds}
    if len(expected) != len(county_feeds) or set(expected) != set(county_counts):
        raise ValueError("Missing or duplicate NM county/candidate totals")
    reconciled = defaultdict(lambda: True)
    for key, counts in county_counts.items():
        if None in counts or expected[key] is None:
            reconciled[key[1]] = False
        elif sum(counts) != expected[key]:
            raise ValueError(f"NM precinct/county candidate totals do not reconcile: {key}")
    rows = []
    precinct_number = load_module("build-current-precincts").precinct_number
    for (county, precinct), candidates in groups.items():
        if len({r["RaceID"] for r in candidates}) != 1:
            raise ValueError("NM precinct split between House contests")
        sums = defaultdict(int)
        for candidate in candidates:
            party = candidate["PartyCode"]
            party = party if party in {"DEM", "REP"} else "OTHER"
            count = integer(candidate["calcCandidateVotes"])
            sums[party] = None if count is None or sums[party] is None else sums[party] + count
        row = result(2026, "NM", county, precinct, "U.S. House", sums["DEM"], sums["REP"],
                     sums["OTHER"], "Source-reported precinct votes", NM)
        row["precinct_number"] = precinct_number(precinct, county)
        row["county_reconciled"] = reconciled[county]
        rows.append(row)
    return rows


def nc_results(source):
    groups, seen = defaultdict(list), set()
    for row in source:
        if not row["Contest Name"].startswith("US HOUSE OF REPRESENTATIVES"):
            continue
        if row["Election Date"] != "11/03/2026":
            raise ValueError("Wrong NC election date")
        identity = (row["County"], row["Precinct"], row["Contest Name"], row["Choice"])
        if identity in seen:
            raise ValueError("Duplicate NC candidate/reporting unit")
        seen.add(identity)
        if integer(row["Total Votes"]) != sum(integer(row[field]) for field in
                                                ["Election Day", "Early Voting", "Absentee by Mail", "Provisional"]):
            raise ValueError("NC candidate ballot modes do not reconcile")
        groups[(row["County"], row["Precinct"])].append(row)
    rows = []
    for (county, precinct), candidates in groups.items():
        sums = defaultdict(int)
        real = all(row["Real Precinct"] == "Y" for row in candidates)
        for candidate in candidates:
            party = candidate["Choice Party"]
            sums[party if party in {"DEM", "REP"} else "OTHER"] += integer(candidate["Total Votes"])
        rows.append(result(2026, "NC", county, precinct, "U.S. House aggregate", sums["DEM"],
                           sums["REP"], sums["OTHER"],
                           "Election-night residential reporting; excludes separately reported early/mail/provisional units"
                           if real else "Nonresidential administrative reporting unit; not mapped to residential precincts",
                           NC, "precinct" if real else "administrative"))
    if not rows:
        raise ValueError("No NC House precinct returns")
    return rows


def de_results(source, statewide):
    contest = "Representative In Congress"
    expected, totals, groups, seen = {}, defaultdict(int), defaultdict(list), set()
    modes = ["Machine Votes", "Absentee Votes", "Early Voting Votes", "Total Votes"]
    for row in statewide:
        if row["Contest Title"] != contest:
            continue
        if row["Election Id"] != "GE2026" or row["Election Date"] != "2026-11-03":
            raise ValueError("Wrong DE election identity")
        key = (row["Candidate Name"], row["Party Name"])
        if key in expected:
            raise ValueError("Duplicate DE statewide candidate")
        expected[key] = {mode: integer(row[mode]) for mode in modes}
    for row in source:
        if row["Contest Title"] != contest:
            continue
        if row["Election Id"] != "GE2026" or not row["Election District"].startswith("Election District "):
            raise ValueError("Wrong DE election/district identity")
        key = (row["Candidate Name"], row["Party Name"])
        identity = (row["Election District"], key)
        if identity in seen or key not in expected:
            raise ValueError("Duplicate or unknown DE candidate/district")
        seen.add(identity)
        counts = {mode: integer(row[mode]) for mode in modes}
        if None in counts.values() or counts["Total Votes"] != sum(counts[mode] for mode in modes[:-1]):
            raise ValueError("DE candidate ballot modes do not reconcile")
        for mode, count in counts.items():
            totals[(key, mode)] += count
        groups[row["Election District"]].append(row)
    if not expected or not groups or any(
        totals[(key, mode)] != count for key, counts in expected.items() for mode, count in counts.items()
    ):
        raise ValueError("DE precinct/state candidate totals do not reconcile")
    rows = []
    for district, candidates in groups.items():
        if {(r["Candidate Name"], r["Party Name"]) for r in candidates} != set(expected):
            raise ValueError("DE district omits a candidate")
        sums = defaultdict(int)
        for candidate in candidates:
            party = {"Democratic Party": "DEM", "Republican Party": "REP"}.get(candidate["Party Name"], "OTHER")
            sums[party] += integer(candidate["Total Votes"])
        rows.append(result(2026, "DE", "", district.removeprefix("Election District "),
                           "U.S. House", sums["DEM"], sums["REP"], sums["OTHER"],
                           "Official district-reported machine, absentee and early voting counts", DE))
    return rows


def join_counties(features, rows, number_field="precinct"):
    by_county, reporting = defaultdict(list), defaultdict(list)
    for feature in features:
        by_county[feature["properties"]["county"]].append(feature)
    for row in rows:
        if row["reporting_unit_kind"] == "precinct":
            reporting[row["county"]].append(row)
    audit = []
    for county in sorted(set(by_county) | set(reporting)):
        shapes, votes = by_county[county], reporting[county]
        shape_keys = [f["properties"]["precinct"] for f in shapes]
        vote_keys = [r.get(number_field) for r in votes]
        exact = bool(shapes) and None not in vote_keys and all(r.get("county_reconciled", True) for r in votes) and (
            len(shape_keys) == len(set(shape_keys)) and len(vote_keys) == len(set(vote_keys))
            and set(shape_keys) == set(vote_keys))
        lookup = dict(zip(vote_keys, votes)) if exact else {}
        matched = 0
        for feature in shapes:
            p = feature["properties"]
            row = lookup.get(p["precinct"])
            if row:
                p.update({field: value for field, value in row.items() if field != "precinct_number"})
                p["match_status"] = "matched"
                matched += p["margin_pp"] is not None
            else:
                p["match_status"] = "county_precinct_set_mismatch"
        audit.append(dict(county=county, exact_precinct_set=exact, shapes=len(shapes),
                          reporting_precincts=len(votes), colored_precincts=matched,
                          boundary_only=sorted(set(shape_keys) - set(vote_keys), key=str),
                          reporting_only=sorted(set(vote_keys) - set(shape_keys), key=str)))
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="Resume an unpublished partial build without a completed index")
    args = parser.parse_args()
    if args.output.exists() and (not args.resume or (args.output / "index.json").exists()):
        raise ValueError("Use a new immutable output directory")
    args.output.mkdir(parents=True, exist_ok=args.resume)
    originals = args.output / "originals"
    originals.mkdir(exist_ok=args.resume)
    sys.path.insert(0, str(ROOT.parent / "voter-participation"))
    from scripts.build import simplify

    def save(name, value):
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        path.write_bytes(gzip.compress(content, mtime=0) if name.endswith(".gz") else content)

    def original(name, url=None):
        cached = args.sources / name
        if not cached.exists():
            response = requests.get(url, timeout=(15, 180))
            response.raise_for_status()
            cached.write_bytes(response.content)
        target = originals / name
        shutil.copyfile(cached, target)
        return target.read_bytes()

    def simplified(geometry, transform=None):
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        output = []
        for polygon in polygons:
            rings = []
            for ring in polygon:
                points = [list(transform(x, y)) for x, y, *rest in ring] if transform else ring
                reduced = simplify(points, .0001)
                if len(reduced) < 4:
                    reduced = points
                rings.append([[round(x, 6), round(y, 6)] for x, y, *rest in reduced])
            output.append(rings)
        return {"type": "MultiPolygon", "coordinates": output}

    coverage, audits, all_rows = {"2026": {}, "2024": {}}, {}, []
    nm_precincts, nm_counties = [], []
    for race in [11186, 11187, 11188]:
        nm_precincts += json.loads(original(f"NM-{race}-precincts.json"))
        nm_counties += json.loads(original(f"NM-{race}-counties.json"))
    rows = nm_results(nm_precincts, nm_counties)
    reference = ROOT / "data/participation-precincts/20261104T230000Z"
    shapes = json.loads(gzip.decompress((reference / "NM.geojson.gz").read_bytes()))["features"]
    features = [{"type": "Feature", "geometry": f["geometry"],
                 "properties": {k: f["properties"][k] for k in
                                ["state_code", "county", "precinct", "boundary_date", "source_geocode"]}}
                for f in shapes]
    audits["2026-NM"] = join_counties(features, rows, "precinct_number")
    shutil.copyfile(reference / "originals/NM-precincts-20260717.zip",
                    originals / "NM-precincts-20260717.zip")
    save("2026/NM.geojson.gz", {"type": "FeatureCollection", "features": features})
    all_rows += rows
    coverage["2026"]["NM"] = dict(file="2026/NM.geojson.gz", source_url=NM, partial=True,
        features=len(features), colored=sum(r["colored_precincts"] for r in audits["2026-NM"]),
        office="U.S. House", boundary_date="2026-07-17",
        notes="Colored counties' official precinct candidate votes reconcile exactly to official county/candidate totals. July reference boundaries. Counties with suppressed counts, unreconciled totals or different precinct sets remain unmapped; state colors remain beneath them.",
        next_action="Resolve suppressed candidate counts and election-day boundary/precinct-set differences; verify live drilldown.")
    print("2026 NM", coverage["2026"]["NM"]["colored"], "colored precincts", flush=True)

    with zipfile.ZipFile(io.BytesIO(original("NC-results-20261103.zip"))) as archive:
        text = archive.read("results_pct_20261103.txt").decode("utf-8-sig")
        # The source encodes some absent party affiliations as a NUL-valued field.
        text = text.replace("\t\x00\t", "\t\t")
        if "\x00" in text:
            raise ValueError("Unexpected NUL inside an NC source field")
        rows = nc_results(csv.DictReader(io.StringIO(text), delimiter="\t"))
    with zipfile.ZipFile(io.BytesIO(original("NC-precincts-20260824.zip"))) as archive:
        stem = next(name[:-4] for name in archive.namelist() if name.endswith(".shp"))
        transform = Transformer.from_crs(CRS.from_wkt(archive.read(stem + ".prj").decode()), 4326, always_xy=True).transform
        reader = shapefile.Reader(**{ext: io.BytesIO(archive.read(stem + "." + ext)) for ext in ["shp", "shx", "dbf"]})
        features = []
        for record in reader.iterShapeRecords():
            p = record.record.as_dict()
            features.append(dict(type="Feature", properties=dict(state_code="NC", county=p["county_nam"],
                            precinct=p["prec_id"], boundary_date="2026-08-24"),
                            geometry=simplified(record.shape.__geo_interface__, transform)))
    audits["2026-NC"] = join_counties(features, rows)
    save("2026/NC.geojson.gz", {"type": "FeatureCollection", "features": features})
    all_rows += rows
    coverage["2026"]["NC"] = dict(file="2026/NC.geojson.gz", source_url=NC, partial=True,
        features=len(features), colored=sum(r["colored_precincts"] for r in audits["2026-NC"]),
        office="U.S. House aggregate · partial ballot modes", boundary_date="2026-08-24",
        notes="Election-night residential precinct returns only: excludes separately reported early/mail/provisional administrative units. These are not all-ballot residential results. No county votes allocated. August reference boundaries; mismatched county sets stay unmapped.",
        next_action="Acquire post-election residential precinct-sorted returns when published; document any official statistical noise. Resolve unmatched county sets and verify live drilldown.")
    print("2026 NC", coverage["2026"]["NC"]["colored"], "colored precincts", flush=True)

    original("NYT-2024-LICENSE.txt", "https://raw.githubusercontent.com/nytimes/presidential-precinct-map-2024/main/LICENSE")
    original("NYT-2024-README.md", "https://raw.githubusercontent.com/nytimes/presidential-precinct-map-2024/main/README.md")
    tabular = list(csv.DictReader(io.StringIO(gzip.decompress(original("NYT-2024-national.csv.gz")).decode())))
    grouped = defaultdict(dict)
    for row in tabular:
        if row["GEOID"] in grouped[row["state"]]:
            raise ValueError("Duplicate NYT precinct identity")
        grouped[row["state"]][row["GEOID"]] = row
    if len(grouped) != 50 or "AK" in grouped:
        raise ValueError("NYT release coverage changed: review every state before publication")
    for code in sorted(grouped):
        source = original(f"NYT-2024-{code}.geojson.gz", NYT_DATA + f"{code}-precincts-with-results.geojson.gz")
        features = json.loads(gzip.decompress(source))["features"]
        seen, mapped, mismatches = set(), [], []
        prior_file = args.output / f"2024/{code}.geojson.gz"
        prior = {f["properties"]["key"]: f for f in
                 json.loads(gzip.decompress(prior_file.read_bytes()))["features"]} if prior_file.exists() else {}
        normalized = {}
        for identity, source_row in grouped[code].items():
            dem, rep, total = [integer(source_row[k]) for k in ["votes_dem", "votes_rep", "votes_total"]]
            if total < dem + rep:
                raise ValueError("Invalid NYT national CSV vote totals")
            normalized[identity] = result(2024, code, identity[:5], identity, "President", dem, rep, total - dem - rep,
                                         "Source-reported precinct or municipal presidential votes", NYT)
        all_rows += list(normalized.values())
        for feature in features:
            p = feature["properties"]
            identity = p["GEOID"]
            if p["state"] != code or identity in seen:
                raise ValueError("Wrong state or duplicate NYT geometry")
            seen.add(identity)
            if feature["geometry"] is None:
                mismatches.append(dict(key=identity, reason="source_geometry_missing"))
                continue
            source_row = grouped[code].get(identity)
            if not source_row or any(integer(source_row[field]) != integer(p[field])
                                     for field in ["votes_dem", "votes_rep", "votes_total"]):
                mismatches.append(dict(key=identity, reason="geometry_and_national_csv_do_not_reconcile"))
                continue
            dem, rep, total = [integer(p[k]) for k in ["votes_dem", "votes_rep", "votes_total"]]
            if total < dem + rep or not isinstance(p["official_boundary"], bool):
                raise ValueError("Invalid NYT vote totals/boundary provenance")
            row = normalized[identity]
            feature["properties"] = dict(row, official_boundary=p["official_boundary"], match_status="matched")
            cached = prior.get(row["key"])
            feature["geometry"] = cached["geometry"] if cached and cached["properties"] == feature["properties"] else simplified(feature["geometry"])
            mapped.append(feature)
        audits[f"2024-{code}"] = dict(source_shapes=len(features), source_rows=len(normalized),
            matched_shapes=len(mapped), mismatched_shapes=mismatches,
            unmapped_result_ids=sorted(set(normalized) - {f["properties"]["precinct"] for f in mapped}))
        save(f"2024/{code}.geojson.gz", {"type": "FeatureCollection", "features": mapped})
        coverage["2024"][code] = dict(file=f"2024/{code}.geojson.gz", source_url=NYT, partial=True,
            features=len(mapped), colored=sum(f["properties"]["margin_pp"] is not None for f in mapped),
            office="President", boundary_date="2024 election reference",
            notes="The New York Times 2024 precinct/municipal release. Every colored shape's votes reconcile exactly to the complete national CSV; mismatched identities/votes are withheld and retained in the audit and originals. Some New England areas are townships; some boundaries are approximate (marked per shape); some counties, unjoined returns, suppressed votes and write-ins are absent. Read the complete original state notes. No 2020 votes reallocated into 2024 shapes are used.",
            next_action="Review the original state-specific caveats, acquire omitted precincts/votes where possible, and verify live drilldown. Do not equate release coverage with every precinct.")
        print("2024", code, len(mapped), "shapes reconciled;", len(normalized) - len(mapped), "unmapped CSV rows", flush=True)
    save("audit.json", audits)
    save("index.json", dict(coverage=coverage, result_rows=len(all_rows),
        metric="100 * (Democratic votes - Republican votes) / all contest votes; not participation",
        attribution="2024 data: The New York Times. Redistribution is governed by the included NYT C-UDA license; editorial use is permitted. Retain all credits and require downstream recipients to retain the same terms.",
        complete_download="complete-precinct-results.zip",
        license_file="originals/NYT-2024-LICENSE.txt", state_notes="originals/NYT-2024-README.md"))
    with (args.output / "results.csv.gz").open("wb") as file:
        text = io.StringIO()
        writer = csv.DictWriter(text, CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)
        file.write(gzip.compress(text.getvalue().encode(), mtime=0))
    load_module("build-precinct-coverage").write_ledger(json.loads((args.output / "index.json").read_text()))
    shutil.copyfile(ROOT / "public/precinct-coverage.csv", args.output / "coverage.csv")
    save("checksums.json", {str(path.relative_to(args.output)): {
        "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in sorted(args.output.rglob("*")) if path.is_file()})
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(args.output)))
    print("Completed", len(all_rows), "result rows; complete originals retained", flush=True)


if __name__ == "__main__":
    main()
