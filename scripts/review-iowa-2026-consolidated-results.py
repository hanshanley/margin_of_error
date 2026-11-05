import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tarfile
import zipfile


COMMIT = "feb85f414762b05c7c77f6450336405ef030fbfa"
ARCHIVE_SHA256 = "316fb2f0f50defafef6f053db0356e77e4011c94f97cf37199726d28bc04e0f8"
PDF_HASHES = {
    "linn-2026-general-summary.pdf": "a2d194adfef5761933857f2b57e719297d793b41d54dfd53e2f68015b800572d",
    "linn-2026-general-precinct.pdf": "f9c01726731a42b144006c635fc5e99a105fb7c6521c6d8626f7579dc8ca5504",
    "marion-2026-general-results.pdf": "4627272fdf72d35b2c0d1a20b715efce5242d042ae5e00242cd7242f8d0ae002",
}
ANCHORS = {
    "Linn": {("Lindsay James", "DEM"): 62228, ("Joe Mitchell", "REP"): 39254,
             ("Rick Stewart", "LIB"): 3058, ("Dave Bushaw", ""): 1230,
             ("Write-in", ""): 68},
    "Marion": {("Mariannette Miller-Meeks", "REP"): 9658, ("Christina Bohannan", "DEM"): 5664,
               ("Michael Bridgford", ""): 586, ("Write-in", ""): 15},
}


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def review_house_rows(rows):
    groups = defaultdict(list)
    selected = []
    for row in rows:
        if not re.fullmatch(r"United States Representative District [1-4]", row["contest"]):
            continue
        if row["state"] != "IA" or row["level"] not in {"county", "state"}:
            raise ValueError("Unexpected House source scope")
        if bool(row["county"]) != (row["level"] == "county"):
            raise ValueError("Missing or unexpected county identity")
        for field in ("votes", "contestTotalVotes"):
            if not re.fullmatch(r"[0-9]+", row[field]):
                raise ValueError("Missing or malformed native integer")
        if not row["candidate"]:
            raise ValueError("Missing candidate identity")
        groups[(row["level"], row["county"], row["contest"])].append(row)
        selected.append(row)
    if not groups:
        raise ValueError("No House returns")
    vectors = {}
    tables = {"county": [], "state": []}
    for key, group in sorted(groups.items()):
        identities = [(row["candidate"], row["party"]) for row in group]
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate candidate option")
        vector = {identity: int(row["votes"]) for identity, row in zip(identities, group)}
        totals = {int(row["contestTotalVotes"]) for row in group}
        total = sum(vector.values())
        if len(totals) != 1 or totals != {total}:
            raise ValueError("Candidate sum differs from native contest total")
        vectors[key] = vector
        democratic = sum(value for (_, party), value in vector.items() if party == "DEM")
        republican = sum(value for (_, party), value in vector.items() if party == "REP")
        tables[key[0]].append(dict(
            year=2026, state_code="IA", county=key[1], contest=key[2],
            democratic_votes=democratic, republican_votes=republican,
            other_and_write_in_votes=total - democratic - republican,
            total_candidate_votes=total,
            dem_minus_rep_pct=round(100 * (democratic - republican) / total, 6) if total else None,
            status="unofficial_snapshot",
        ))
    for contest in sorted({key[2] for key in vectors}):
        state = vectors.get(("state", "", contest))
        counties = [value for key, value in vectors.items() if key[0] == "county" and key[2] == contest]
        summed = Counter()
        for vector in counties:
            for identity, value in vector.items():
                summed[identity] += value
        if state is None or not counties or dict(summed) != state:
            raise ValueError("County candidate vectors differ from statewide district vector")
    return selected, tables, vectors


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n")


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_review(bulk, native, output):
    archive_path = bulk / "pushbuild-complete-original.tar.gz"
    if sha256(archive_path.read_bytes()) != ARCHIVE_SHA256:
        raise ValueError("Changed pinned complete source archive")
    tree = json.loads((bulk / "pushbuild-original-tree.json").read_text())
    if tree["sha"] != COMMIT or tree["truncated"]:
        raise ValueError("Changed or truncated pinned Git tree")
    original = next(row for row in tree["tree"] if row["path"] == "data/ia.csv")
    with tarfile.open(archive_path, "r:gz") as archive:
        members = [member for member in archive.getmembers() if member.isfile() and member.name.endswith("/data/ia.csv")]
        if len(members) != 1:
            raise ValueError("Missing or duplicate original Iowa file")
        raw = archive.extractfile(members[0]).read()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if blob != original["sha"] or len(raw) != original["size"]:
        raise ValueError("Changed original Iowa Git blob")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    selected, tables, vectors = review_house_rows(rows)
    if len(rows) != 6010 or len(tables["county"]) != 99 or len(tables["state"]) != 4:
        raise ValueError("Unexpected complete source scope")
    if len({row["county"] for row in tables["county"]}) != 99:
        raise ValueError("Duplicate or split county requires separate review")
    for name, expected in PDF_HASHES.items():
        if sha256((native / name).read_bytes()) != expected:
            raise ValueError("Changed independently reviewed native PDF")
    for county, expected in ANCHORS.items():
        observed = [value for key, value in vectors.items() if key[0] == "county" and key[1] == county]
        if observed != [expected]:
            raise ValueError("County vector differs from independently reviewed native report")
    receipt = json.loads((bulk / "iowa-statewide-source-receipt.json").read_text())
    blocked = (bulk / "iowa-declared-statewide-index.html").read_bytes()
    if receipt["status"] != 403 or sha256(blocked) != receipt["sha256"]:
        raise ValueError("Changed statewide-source limitation evidence")
    output.mkdir(parents=True, exist_ok=False)
    source_bulk = output / "source-bulk"
    source_bulk.mkdir()
    for name in ("pushbuild-complete-original.tar.gz", "pushbuild-original-tree.json",
                 "iowa-statewide-source-receipt.json", "iowa-declared-statewide-index.html"):
        shutil.copyfile(bulk / name, source_bulk / name)
    shutil.copytree(native, output / "source-native")
    (output / "iowa-complete-original.csv").write_bytes(raw)
    write_csv(output / "house-native-candidate-vectors.csv", selected)
    write_csv(output / "county-house-results.csv", tables["county"])
    write_csv(output / "district-house-results.csv", tables["state"])
    audit = dict(
        status="bulk_counts_reconciled_not_map_approved", year=2026, election_date="2026-11-03",
        provider="Pushbuild", source_commit=COMMIT, original_iowa_git_blob=blob,
        original_rows=len(rows), house_candidate_rows=len(selected),
        other_rows_preserved_in_complete_original=len(rows) - len(selected),
        county_contests=99, district_contests=4,
        total_house_candidate_votes=sum(row["total_candidate_votes"] for row in tables["county"]),
        native_zero_total_counties=[row["county"] for row in tables["county"] if row["total_candidate_votes"] == 0],
        county_to_district_every_candidate_reconciles=True,
        independent_anchor_counties=["Linn", "Marion"], independent_pdf_hashes=PDF_HASHES,
        anchor_method="Previously reviewed Linn native PDF extraction and Marion direct visual review; exact original hashes and complete candidate vectors replayed.",
        statewide_primary_index_status=403, primary_verification_of_all_99_counties=False,
        maps_approved=False, geometry_approved=False, participation_available=False,
        notes=[
            "Unofficial provider-declared November 4 snapshot, not certified or complete reporting.",
            "State reporting counters are preserved in native candidate rows; do not infer precinct inventory or allocate them to counties.",
            "Explicit native zeros remain zeros, not proof of final reporting. Missing values are never converted to zeros.",
            "Unknown party stays blank. Every candidate and write-in is included in the margin denominator.",
            "County candidate counts are not precinct counts, ballots, unique voters or turnout.",
            "All 6010 original Iowa rows and the entire 40-state source archive, README and CC0 license are included.",
        ],
    )
    write_json(output / "audit.json", audit)
    shutil.copyfile(Path(__file__), output / Path(__file__).name)
    write_json(output / "checksums.json", {
        str(path.relative_to(output)): dict(bytes=path.stat().st_size, sha256=sha256(path.read_bytes()))
        for path in sorted(output.rglob("*")) if path.is_file()
    })
    files = sorted(path for path in output.rglob("*") if path.is_file())
    with zipfile.ZipFile(output / "complete-iowa-county-review.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            info = zipfile.ZipInfo(str(path.relative_to(output)), (2026, 11, 5, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bulk-originals", type=Path, required=True)
    parser.add_argument("--native-originals", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_review(args.bulk_originals, args.native_originals, args.output), indent=2))
