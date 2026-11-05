"""Export literal-party and candidate votes without collapsing third parties."""

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import zipfile


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def party_tables(counties, districts):
    county_parties, county_candidates, state_parties, district_candidates = [], [], [], []
    located = defaultdict(Counter)
    for row in counties:
        votes = Counter()
        for fragment in row["district_fragments"]:
            for candidate in fragment["candidates"]:
                if type(candidate["votes"]) is not int or candidate["votes"] < 0:
                    raise ValueError("Party exports require explicit nonnegative integer votes")
                votes[candidate["party"]] += candidate["votes"]
                county_candidates.append(dict(year=row["year"], state_code=row["state_code"],
                    county_fips=row["geography"], county_name=row["geography_name"],
                    district=fragment["district"], office="U.S. House", **candidate,
                    source_key=fragment["source_key"], source_url=fragment["source_url"],
                    source_updated_at=fragment["source_updated_at"]))
        if sum(votes.values()) != row["total_votes"]:
            raise ValueError("Party votes do not reconcile to reviewed county candidate votes")
        for party, count in sorted(votes.items()):
            county_parties.append(dict(year=row["year"], state_code=row["state_code"],
                county_fips=row["geography"], county_name=row["geography_name"],
                office="U.S. House district contests aggregated within county", party=party, votes=count))
            located[row["state_code"]][party] += count
    states = defaultdict(Counter)
    for district in districts:
        for candidate in district["candidates"]:
            if type(candidate["votes"]) is not int or candidate["votes"] < 0:
                raise ValueError("Party exports require explicit nonnegative integer votes")
            states[district["state_code"]][candidate["party"]] += candidate["votes"]
            district_candidates.append(dict(year=2026, state_code=district["state_code"],
                district=district["district"], office="U.S. House", **candidate,
                source_url=district["source_url"], source_updated_at=district["source_updated_at"]))
    for code, parties in sorted(states.items()):
        if set(located[code]) - set(parties):
            raise ValueError("County party inventory exceeds its own state source")
        for party, votes in sorted(parties.items()):
            county_votes = located[code][party] if code in {r["state_code"] for r in counties} else None
            if county_votes is not None and county_votes > votes:
                raise ValueError("Located county party votes exceed full district party votes")
            state_parties.append(dict(year=2026, state_code=code,
                office="U.S. House district contests aggregated within state",
                party=party, votes=votes, located_county_votes=county_votes,
                unlocated_votes=votes - county_votes if county_votes is not None else None))
    return {"county-party-totals.csv.gz": county_parties,
            "county-district-candidate-totals.csv.gz": county_candidates,
            "state-party-totals.csv.gz": state_parties,
            "district-candidate-totals.csv.gz": district_candidates}


def export(source, output, archive_path=None):
    review = load("review-house-county-results")
    provider = source / "originals/provider.tar.gz"
    if (source / "checksums.json").exists():
        checksums = json.loads((source / "checksums.json").read_bytes())
        for name in ("originals/provider.tar.gz", "county-results.json.gz"):
            if hashlib.sha256((source / name).read_bytes()).hexdigest() != checksums[name]["sha256"]:
                raise ValueError("Reviewed party source changed: " + name)
    counties = json.loads(gzip.decompress((source / "county-results.json.gz").read_bytes()))
    districts, native, excluded = [], {}, {}
    with tarfile.open(provider) as archive:
        read = lambda name: archive.extractfile(name).read()
        acquisition = json.loads(read("acquisition.json"))
        raw = read("original-national-house.json")
        if hashlib.sha256(raw).hexdigest() != acquisition["national_source_sha256"]:
            raise ValueError("National House declaration changed")
        declared = review.sources.declared_districts(json.loads(raw))
        for key, binding in declared.items():
            try:
                raw = read(key + ".json")
                receipt = json.loads(read(key + ".json.receipt.json"))
                if (receipt["status"] != 200 or receipt["url"] != binding["url"]
                        or receipt["bytes"] != len(raw) or receipt["sha256"] != hashlib.sha256(raw).hexdigest()):
                    raise ValueError("District party source does not match its acquisition receipt")
                data = json.loads(raw)
                review.sources.district_scope(data, binding)
                review.candidate_vector(data["candidates"])
                native[binding["district"]] = data
                districts.append(dict(state_code=binding["state_code"], district=binding["district"],
                    source_url=binding["url"], source_updated_at=data.get("last_updated"),
                    candidates=[{field: candidate[field] for field in ("name", "party", "votes")}
                                for candidate in data["candidates"]]))
            except (ValueError, KeyError) as error:
                excluded[key] = dict(state_code=binding["state_code"], error=str(error))
    withheld = {row["state_code"] for row in excluded.values()}
    districts = [row for row in districts if row["state_code"] not in withheld]
    for county in counties:
        for fragment in county["district_fragments"]:
            actual = native[fragment["district"]]["region_results"][fragment["source_key"]]["candidates"]
            if review.candidate_vector(actual) != review.candidate_vector(fragment["candidates"]):
                raise ValueError("County candidate export differs from its original district source")
    tables = party_tables(counties, districts)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Refusing to replace a published party-vote snapshot")
    output.mkdir(parents=True, exist_ok=True)
    audit = dict(year=2026, office="U.S. House", declared_districts=len(declared),
        source_districts=len(districts), withheld_states=sorted(withheld), excluded_districts=excluded,
        state_party_coverage=len({r["state_code"] for r in districts}),
        county_party_coverage=len({r["state_code"] for r in counties}), counties=len(counties),
        literal_parties=sorted({r["party"] for r in tables["state-party-totals.csv.gz"]}),
        scope="Unofficial candidate votes, not ballots, unique voters, party registration or demographic turnout. "
        "Party labels and candidate names are literal, including independents and fusion lines; no inferred affiliation. "
        "County party totals aggregate only actual county fragments. State party totals include all declared "
        "district candidate votes in accepted states, including unlocated returns; an invalid district withholds "
        "its entire state rather than publishing a partial state total. Withheld county states retain missing located counts. "
        "Absent parties have no invented zero rows; explicitly reported zero candidate votes remain zero.",
        source_snapshot=source.name, files={})
    for name, rows in tables.items():
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        raw = gzip.compress(buffer.getvalue().encode(), mtime=0)
        (output / name).write_bytes(raw)
        audit["files"][name] = dict(rows=len(rows), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    if archive_path:
        with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(output.iterdir()):
                if path.is_file():
                    archive.write(path, path.name)
            source_prefix = "source/" + source.name + "/"
            for name in ("originals/provider.tar.gz", "county-results.json.gz", "checksums.json", "audit.json"):
                if (source / name).exists():
                    archive.write(source / name, source_prefix + name)
            archive.write(Path(__file__), Path(__file__).name)
            for name in ("review-house-county-results.py", "acquire-house-county-results.py",
                         "requirements-precinct-results.txt"):
                archive.write(Path(__file__).with_name(name), name)
            archive.writestr("REPRODUCE.txt",
                "Unofficial 2026 U.S. House candidate votes; not ballots, turnout, or Senate results.\n"
                "Pennsylvania test responses are retained only as excluded originals, never real-vote totals.\n"
                "Maine has valid district totals but no reconciled county allocation. Missing is not zero.\n\n"
                "From an extracted archive with Python 3.9+:\n"
                "python -m pip install -r requirements-precinct-results.txt\n"
                "python export-county-party-votes.py --source source/" + source.name + " --output reproduced\n\n"
                "Compare each reproduced CSV gzip SHA256 with audit.json. All four tables must match.\n"
                "The source directory includes every original district response and receipt, the complete\n"
                "national district declaration, reviewed county fragments, original county audit and checksums.\n"
                "The county geometry archive remains a separate complete-source download on the website.\n")
    print(json.dumps(audit, indent=2))
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    export(args.source, args.output, args.archive)
