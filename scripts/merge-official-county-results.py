"""Merge reviewed Pennsylvania county returns without claiming complete state coverage."""

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = [
    ("42089", "Monroe", "20261105-monroe-official-01"),
    ("42017", "Bucks", "20261105-bucks-reviewed-02"),
    ("42091", "Montgomery", "20261105-montgomery-reviewed-01"),
]
APPROVED_MANIFESTS = {
    "20261105-monroe-official-01": "7e71657b7aba3b73519d4bc09f2c230e8b3325e1932e06370023a3c726df1846",
    "20261105-bucks-reviewed-02": "baa595356ab930959fc60acbd7ba0cb01d55fe5b1f469b0bf45472326d88ebe0",
    "20261105-montgomery-reviewed-01": "389ad6c65ddf69a3624136bb5b3c7a98f66b34e1b3ec0c193548837478b38571",
}


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes())


def write(path, value):
    raw = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == ".gz" else raw)


def checksum(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def verify_package(folder):
    inventory = read(folder / "checksums.json")
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    if actual != set(inventory) | {"checksums.json"}:
        raise ValueError("Incomplete official county package")
    if any(checksum(folder / name) != expected for name, expected in inventory.items()):
        raise ValueError("Changed official county package")


def official_row(folder, fips, name, reference):
    verify_package(folder)
    if (fips not in reference or reference[fips]["STATEFP"] != "42"
            or reference[fips]["NAME"] != name):
        raise ValueError("Official county identity differs from 2026 Census reference")
    audit = read(folder / "audit.json")
    rows = list(csv.DictReader((folder / "county-candidate-results.csv").open()))
    selected = [r for r in rows if r["office"] == "us_house"]
    expected = {"Monroe": {"7", "8"}, "Bucks": {"1"}, "Montgomery": {"1", "4", "5"}}[name]
    fragments, seen = {}, set()
    url = (audit["source_url"] if name == "Monroe" else
           audit["source_urls"]["native-results.redacted.html"] if name == "Bucks" else
           audit["source_urls"]["montgomery-dashboard.html"])
    updated = (audit["source_update_literal"] if name == "Monroe" else
               audit["participation"]["source_update_literal"] if name == "Bucks" else
               audit["participation"]["source_pdf_update_literal"])
    parties = Counter()
    for row in selected:
        if (row["year"] != "2026" or row["state_code"] != "PA"
                or row.get("county_fips", fips) != fips or row.get("county", name) != name):
            raise ValueError("Wrong official election or county")
        if name == "Monroe":
            district, candidate, party = row["district"], row["candidate"], row["party"]
        elif name == "Bucks":
            match = re.fullmatch(r"REPRESENTATIVE IN CONGRESS (\d+)ST", row["contest_name"])
            if not match:
                raise ValueError("Unreviewed Bucks House contest")
            district, candidate, party = match[1], row["candidate_literal"], row["party_csv_literal"]
        else:
            match = re.fullmatch(r"Representative in Congress (\d+)(?:st|th) District", row["contest"])
            if not match or row["selectable_options"] != "1":
                raise ValueError("Unreviewed Montgomery House contest")
            district, candidate, party = match[1], row["candidate"], row["party_literal"]
        key = district, candidate, party
        if key in seen or not re.fullmatch(r"\d+", row["votes"]) or not candidate.strip():
            raise ValueError("Duplicate candidate or invalid explicit vote count")
        seen.add(key)
        votes = int(row["votes"])
        parties[party] += votes
        fragments.setdefault(district, dict(district="PA-" + district.zfill(2), source_url=url,
            source_updated_at=updated, source_key=fips, candidates=[]))["candidates"].append(
                dict(name=candidate, party=party, votes=votes))
    if set(fragments) != expected:
        raise ValueError("Official county House district inventory changed")
    allowed = {"Monroe": {"DEMOCRATIC", "REPUBLICAN", "Nonpartisan"},
               "Bucks": {"Dem", "Rep", "Nonpart"}, "Montgomery": {"DEM", "REP", ""}}[name]
    if set(parties) != allowed:
        raise ValueError("Unreviewed literal party inventory")
    total = sum(parties.values())
    expected_total = audit.get("house_candidate_votes", audit.get("participation", {}).get("house_candidate_votes"))
    if name == "Montgomery":
        expected_total = sum(int(r["votes"]) for r in csv.DictReader(
            (folder / "county-office-party-totals.csv").open()) if r["office"] == "us_house")
    if total != expected_total:
        raise ValueError("Official candidate vector differs from reviewed county total")
    dem = sum(v for p, v in parties.items() if p in {"DEMOCRATIC", "Dem", "DEM"})
    rep = sum(v for p, v in parties.items() if p in {"REPUBLICAN", "Rep", "REP"})
    return dict(year=2026, state_code="PA", level="county", geography=fips,
        geography_name=reference[fips]["NAMELSAD"], contest="U.S. House district contests aggregated within county",
        democratic_votes=dem, republican_votes=rep, other_votes=total-dem-rep, total_votes=total,
        margin_pp=100*(dem-rep)/total if total else None,
        district_fragments=list(fragments.values()), source_kind="official_county_supplement",
        source_note="Unofficial county report; counting may be incomplete. Source update timezone is unestablished. "
                    "Only this county is covered, not all Pennsylvania. Candidate votes are not ballots or turnout.")


def review_provider_overlap(index, rows, additions, reference):
    inventory = {key for key, value in reference.items() if value["STATEFP"] == "42"}
    provider = [row for row in rows if row["state_code"] == "PA"]
    if (len(provider) != len(inventory)
            or {row["geography"] for row in provider} != inventory
            or index["coverage"].get("PA", {}).get("counties") != len(inventory)
            or index.get("official_supplement")):
        raise ValueError("Partial provider Pennsylvania coverage requires explicit review")
    by_county = {row["geography"]: row for row in provider}
    aliases = {"Democratic": "D", "DEMOCRATIC": "D", "Dem": "D", "DEM": "D",
               "Republican": "R", "REPUBLICAN": "R", "Rep": "R", "REP": "R"}

    def major_vectors(row):
        result = Counter()
        for fragment in row["district_fragments"]:
            for candidate in fragment["candidates"]:
                if candidate["party"] in aliases:
                    result[fragment["district"], aliases[candidate["party"]]] += candidate["votes"]
        return dict(result)

    reviewed = {}
    for official in additions:
        native = by_county[official["geography"]]
        if (native.get("source_kind") == "official_county_supplement"
                or native["other_votes"] != 0
                or major_vectors(native) != major_vectors(official)
                or any(native[key] != official[key]
                       for key in ["democratic_votes", "republican_votes"])):
            raise ValueError("Overlapping provider candidate vectors require explicit review")
        reviewed[official["geography"]] = dict(
            provider_row=native, official_other_votes_retained=official["other_votes"])
    return reviewed


def csv_append(path, additions, replaced=()):
    with gzip.open(path, "rt", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    import io
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    rows = [row for row in rows if row["county_fips"] not in replaced]
    writer.writerows(rows + additions)
    path.write_bytes(gzip.compress(out.getvalue().encode(), mtime=0))
    return len(rows) + len(additions)


def merge(folder, reference_folder, packages_root=ROOT / "data/county-source-reviews"):
    spec = importlib.util.spec_from_file_location("county_review",
        Path(__file__).with_name("review-house-county-results.py"))
    county = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(county)
    reference = county.county_reference(reference_folder)
    index, rows, margins = (read(folder / name) for name in
                           ["index.json", "county-results.json.gz", "margins.json"])
    if index["year"] != 2026 or index["boundary_reference_year"] != 2026:
        raise ValueError("Wrong base election or boundary year")
    for _, _, package in PACKAGES:
        if checksum(packages_root / package / "checksums.json")["sha256"] != APPROVED_MANIFESTS[package]:
            raise ValueError("Official package differs from the immutable approved review")
    additions = [official_row(packages_root / package, fips, name, reference)
                 for fips, name, package in PACKAGES]
    replaced = {r["geography"] for r in additions} & {r["geography"] for r in rows}
    overlap = review_provider_overlap(index, rows, additions, reference) if replaced else {}
    if "PA" in index["coverage"] and not overlap:
        raise ValueError("Partial provider Pennsylvania coverage requires explicit review")
    geometries, excluded = county.county_geometries(reference_folder, additions)
    if excluded or len(geometries.get("PA", {}).get("features", [])) != len(additions):
        raise ValueError("Official county geometry is missing or invalid")
    if not overlap:
        write(folder / "geometry/PA.geojson.gz", geometries["PA"])
    inventory = {key for key, value in reference.items() if value["STATEFP"] == "42"}
    removed = [row for row in rows if row["geography"] in replaced]
    rows = [row for row in rows if row["geography"] not in replaced]
    margins = [row for row in margins if row["geography"] not in replaced]
    pa_rows = [row for row in rows if row["state_code"] == "PA"] + additions
    index["coverage"]["PA"] = dict(file="geometry/PA.geojson.gz", counties=len(pa_rows),
        colored_counties=sum(r["margin_pp"] is not None for r in pa_rows),
        reference_counties=len(inventory),
        coverage_status="provider_with_official_county_overrides" if overlap else "partial_official_counties",
        scope_note=("All 67 Pennsylvania county identities are covered. Monroe, Bucks and Montgomery use "
                    "separate official reports, preserving write-ins omitted by the provider; their district "
                    "major-party vectors match. Other counties retain provider counts. Not final counting."
                    if overlap else
                    "Only Monroe, Bucks and Montgomery counties; remaining Pennsylvania counties use state fallback."))
    for row in additions:
        margins.append(dict({k:v for k,v in row.items() if k != "district_fragments"},
            office="U.S. House aggregate", contest_votes=row["total_votes"], provisional=True,
            source_url=row["district_fragments"][0]["source_url"],
            source_urls=[row["district_fragments"][0]["source_url"]],
            district_count=len(row["district_fragments"]), boundary_reference_year=2026))
    rows.extend(additions)
    for key in ["normalized_counties", "mapped_counties"]:
        index[key] += len(additions) - len(removed)
    index["colored_counties"] += (sum(r["margin_pp"] is not None for r in additions)
                                 - sum(r["margin_pp"] is not None for r in removed))
    index["provider_withheld_states"] = index["withheld_states"]
    index["withheld_states"] = {k:v for k,v in index["withheld_states"].items() if k not in index["coverage"]}
    index["scope"] += " Official county supplements are independently joined to exact 2026 Census county identities; " \
        f"Pennsylvania covers {len(pa_rows)} of 67 county identities, not final counting. " \
        "Provider test data remains excluded. D.C. delegate counts are not added."
    index["official_supplement"] = dict(counties=[r["geography"] for r in additions],
        provider_counties_replaced=sorted(replaced), new_precinct_coverage=0, state_completion_promoted=False)
    write(folder / "index.json", index)
    write(folder / "margins.json", margins)
    write(folder / "county-results.json.gz", rows)
    with (folder / "county-results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=county.FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    party_folder = folder / "party-votes"
    county_parties, candidates = [], []
    for row in additions:
        parties = Counter()
        for fragment in row["district_fragments"]:
            for candidate in fragment["candidates"]:
                parties[candidate["party"]] += candidate["votes"]
                candidates.append(dict(year=2026, state_code="PA", county_fips=row["geography"],
                    county_name=row["geography_name"], district=fragment["district"], office="U.S. House",
                    **{k:candidate[k] for k in ["name", "party", "votes"]},
                    source_key=row["geography"], source_url=fragment["source_url"],
                    source_updated_at=fragment["source_updated_at"]))
        county_parties.extend(dict(year=2026, state_code="PA", county_fips=row["geography"],
            county_name=row["geography_name"], office=row["contest"], party=p, votes=v)
            for p,v in sorted(parties.items()))
    for name, additions_table in [("county-party-totals.csv.gz", county_parties),
                                   ("county-district-candidate-totals.csv.gz", candidates)]:
        count = csv_append(party_folder / name, additions_table, replaced)
        party_audit = read(party_folder / "audit.json")
        party_audit["files"][name].update(checksum(party_folder / name), rows=count)
        party_audit["official_county_scope"] = "PA county fragments only; not full-state or full-district totals."
        party_audit["source_precedence"] = (
            "County tables use complete official vectors for Monroe, Bucks and Montgomery. "
            "Provider-only state and district tables remain unchanged and omit those known write-ins; "
            "they are separate source scopes, not recomputed composite totals.")
        write(party_folder / "audit.json", party_audit)
    write(party_folder / "checksums.json", {p.name:checksum(p) for p in sorted(party_folder.iterdir())
        if p.is_file() and p.name != "checksums.json"})
    for _, _, package in PACKAGES:
        shutil.copytree(packages_root / package, folder / "originals/official-counties" / package)
    audit = read(folder / "audit.json")
    audit["official_county_supplement"] = dict(
        counties=additions, new_county_reference_year=2026, provider_results_unchanged=not bool(overlap),
        provider_county_overrides=overlap,
        source_precedence="Official whole-county vectors replace overlapping provider county vectors only "
                          "when every major-party district vector agrees and the provider has zero other "
                          "reported votes. Official write-ins are retained, never added to duplicated majors. "
                          "Provider state/district tables and all provider originals remain unchanged.",
        mapped_counties=len(rows), mapped_state_scopes=len(index["coverage"]),
        state_completion_promoted=False, precinct_coverage_added=0,
        reproduction="First reproduce the provider-only package using its original instructions. "
                     "Extract originals/census-reference.tar.gz into CENSUS. Run "
                     "merge-official-county-results.py --source PROVIDER_PACKAGE --reference CENSUS "
                     "--packages originals/official-counties --output NEW_DIRECTORY --archive NEW_ZIP. "
                     "Provider audit fields remain provider-only; composite coverage is in index.json.")
    write(folder / "audit.json", audit)
    shutil.copyfile(Path(__file__), folder / Path(__file__).name)
    write(folder / "checksums.json", {p.relative_to(folder).as_posix():checksum(p)
        for p in sorted(folder.rglob("*")) if p.is_file() and p != folder / "checksums.json"})
    return additions


def archive(folder, target):
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_STORED) as zipped:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                item = zipfile.ZipInfo(path.relative_to(folder).as_posix(), (2026, 11, 5, 0, 0, 0))
                item.external_attr = 0o100644 << 16
                zipped.writestr(item, path.read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--packages", type=Path, default=ROOT / "data/county-source-reviews")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    shutil.copytree(args.source, args.output)
    merge(args.output, args.reference, args.packages)
    archive(args.output, args.archive)
