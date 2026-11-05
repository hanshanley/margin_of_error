"""Refresh county candidate results and UF turnout independently, retaining last good pointers."""

import argparse
from datetime import datetime, timezone
import hashlib
import gzip
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import traceback

import requests


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REPO = "hanshanley/margin_of_error"
RAW = "https://raw.githubusercontent.com/" + REPO + "/"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*args, **kwargs):
    return subprocess.run(list(map(str, args)), cwd=ROOT, check=True, **kwargs)


def unpack_originals(source, name, output):
    archive_path = source / "originals" / (name + ".tar.gz")
    if digest(archive_path) != read(source / "checksums.json")["originals/" + name + ".tar.gz"]["sha256"]:
        raise ValueError("Changed original reference archive")
    output.mkdir()
    with tarfile.open(archive_path) as archive:
        for member in archive:
            relative = Path(member.name)
            if not member.isfile() or relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unexpected original archive member")
            path = output / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.extractfile(member).read())


def county_candidate(work, previous, replay_source=None):
    import sys
    old = ROOT / previous["data_directory"]
    reference = work / "census"
    unpack_originals(ROOT / "data/county-results/20261105-house-02", "census-reference", reference)
    provider = work / "provider"
    if replay_source:
        unpack_originals(replay_source, "provider", provider)
    else:
        response = requests.get("https://civicapi.org/api/v2/race/87524", timeout=(20, 90))
        provider.mkdir()
        raw = response.content
        national = work / "national.json"
        national.write_bytes(raw)
        write(provider / "original-national-house.json.receipt.json",
              dict(url=response.url, status=response.status_code, bytes=len(raw),
                   sha256=hashlib.sha256(raw).hexdigest(),
                   acquired_at=datetime.now(timezone.utc).isoformat()))
        response.raise_for_status()
        command(sys.executable, SCRIPTS / "acquire-house-county-results.py",
                "--national-source", national, "--output", provider)
    output, archive = work / "reviewed", work / "complete-county-results.zip"
    with (work / "county-review.log").open("w") as log:
        command(sys.executable, SCRIPTS / "review-house-county-results.py",
                "--source-cache", provider, "--reference-cache", reference,
                "--state-codes", old / "state-codes.json", "--output", output, "--archive", archive, "--map",
                stdout=log)
    validate_county_coverage(read(old / "index.json"), read(output / "index.json"),
                            read(old / "margins.json"), read(output / "margins.json"))
    load("build-county-overview").build(output, work / "county-overview.geojson.gz")
    return output, archive


def validate_county_coverage(old, new, old_rows, new_rows):
    if new["year"] != 2026 or new["boundary_reference_year"] != 2026:
        raise ValueError("Wrong election or boundary year")
    if not set(old["coverage"]) <= set(new["coverage"]):
        raise ValueError("Refresh loses a previously reconciled state; retaining last good pointer")
    if not {row["geography"] for row in old_rows} <= {row["geography"] for row in new_rows}:
        raise ValueError("Refresh loses a previously mapped county; retaining last good pointer")


def unchanged(kind, output, previous):
    if not previous:
        return False
    old = ROOT / previous["data_directory"]
    if kind == "uf":
        current, candidate = read(old / "audit.json"), read(output / "audit.json")
        return (current["version"] == candidate["version"]
                and [(r["url"], r["sha256"]) for r in current["receipts"][-2:]]
                == [(r["url"], r["sha256"]) for r in candidate["receipts"][-2:]])
    if gzip.decompress((old / "county-results.json.gz").read_bytes()) != gzip.decompress(
            (output / "county-results.json.gz").read_bytes()):
        return False
    if not previous.get("party_votes"):
        return False
    party_old = ROOT / previous["party_votes"]["data_directory"]
    files = read(output / "party-votes/audit.json")["files"]
    return (set(files) == set(read(party_old / "audit.json")["files"])
            and all(gzip.decompress((party_old / name).read_bytes())
                    == gzip.decompress((output / "party-votes" / name).read_bytes()) for name in files))


def publish(kind, output, archive, work, run_id, previous):
    tag = "voter-" + kind + "-2026-" + run_id.lower()
    command("gh", "release", "create", tag, archive, "--repo", REPO, "--target", "main",
            "--title", "2026 " + kind + " reviewed snapshot " + run_id,
            "--notes", "Complete original-backed snapshot. Candidate counts and UF turnout remain separate. "
            "All missingness, test exclusions, source receipts and literal party labels retained.")
    downloaded = work / "release-verification.zip"
    command("gh", "release", "download", tag, "--repo", REPO, "--pattern", archive.name,
            "--output", downloaded)
    if digest(downloaded) != digest(archive):
        raise ValueError("Published complete source ZIP differs from reviewed bytes; pointer unchanged")
    destination = ROOT / "data" / ("uf-turnout" if kind == "uf" else "county-results") / run_id
    destination.mkdir(parents=True, exist_ok=False)
    if kind == "uf":
        shutil.copytree(output, destination, dirs_exist_ok=True)
    else:
        for name in ("index.json", "margins.json", "audit.json", "county-results.json.gz",
                     "county-results.csv", "state-codes.json"):
            shutil.copyfile(output / name, destination / name)
        shutil.copytree(output / "party-votes", destination / "party-votes")
        index = read(destination / "index.json")
        old_index = read(ROOT / previous["data_directory"] / "index.json")
        source_checksums = read(output / "checksums.json")
        old_checksums = read(ROOT / previous["data_directory"] / "checksums.json")
        for code, coverage in index["coverage"].items():
            native = output / coverage["file"]
            old_coverage = old_index["coverage"].get(code)
            coverage["sha256"] = source_checksums[coverage["file"]]["sha256"]
            coverage["uncompressed_sha256"] = hashlib.sha256(gzip.decompress(native.read_bytes())).hexdigest()
            old_hash = (old_coverage.get("sha256") or old_checksums.get(old_coverage["file"], {}).get("sha256")
                        if old_coverage else None)
            old_semantic_hash = old_coverage.get("uncompressed_sha256") if old_coverage else None
            if old_coverage and old_semantic_hash is None:
                old_native = ROOT / previous["data_directory"] / old_coverage["file"]
                if old_native.is_file():
                    old_semantic_hash = hashlib.sha256(gzip.decompress(old_native.read_bytes())).hexdigest()
            if old_coverage and (coverage["sha256"] == old_hash
                                 or coverage["uncompressed_sha256"] == old_semantic_hash):
                from urllib.parse import urljoin
                coverage["file"] = urljoin(previous["base_url"], old_coverage["file"])
                coverage["sha256"] = old_hash
            else:
                target = destination / coverage["file"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(native, target)
        write(destination / "index.json", index)
        write(destination / "checksums.json",
              {path.relative_to(destination).as_posix(): dict(bytes=path.stat().st_size, sha256=digest(path))
               for path in sorted(destination.rglob("*")) if path.is_file()})
    relative = destination.relative_to(ROOT).as_posix()
    env = dict(os.environ, GIT_AUTHOR_NAME="Hans Hanley", GIT_COMMITTER_NAME="Hans Hanley")
    command("git", "add", relative)
    command("git", "commit", "-m", "Preserve reviewed 2026 " + kind + " source snapshot " + run_id, env=env)
    commit = command("git", "rev-parse", "HEAD", capture_output=True, text=True).stdout.strip()
    pointer = dict(year=2026, data_directory=relative, base_url=RAW + commit + "/" + relative + "/",
                   complete_download_url="https://github.com/" + REPO + "/releases/download/" + tag + "/" + archive.name,
                   complete_download_bytes=archive.stat().st_size, complete_download_sha256=digest(archive))
    if kind == "uf":
        pointer.update(label="UF 2026 state/national turnout " + run_id + "; source estimates remain estimates",
                       previous_snapshots=([{k: v for k, v in previous.items() if k != "previous_snapshots"},
                                            *previous.get("previous_snapshots", [])] if previous else []))
        pointer_path = ROOT / "public/uf-turnout.json"
    else:
        index, party_audit = read(output / "index.json"), read(output / "party-votes/audit.json")
        pointer.update(label="2026 U.S. House county / equivalent results",
                       overview_url="/county-results-overview.geojson.gz", states=len(index["coverage"]),
                       normalized_counties=index["mapped_counties"], participation_available=False,
                       publication="reviewed_pending_live_verification",
                       previous_snapshots=[{k: v for k, v in previous.items() if k != "previous_snapshots"},
                                           *previous.get("previous_snapshots", [])])
        labels = {"county-party-totals.csv.gz": "Every county-party total",
                  "county-district-candidate-totals.csv.gz": "Every county/district candidate",
                  "state-party-totals.csv.gz": "Every full-state party total",
                  "district-candidate-totals.csv.gz": "Every accepted House district candidate"}
        pointer["party_votes"] = dict(data_directory=relative + "/party-votes",
            base_url=pointer["base_url"] + "party-votes/",
            complete_download_url=pointer["complete_download_url"],
            tables=[dict(file=name, label=labels[name] + ": " + str(meta["rows"]) + " rows")
                    for name, meta in party_audit["files"].items()])
        shutil.copyfile(work / "county-overview.geojson.gz", ROOT / "public/county-results-overview.geojson.gz")
        pointer_path = ROOT / "public/county-results.json"
    write(pointer_path, pointer)
    command("git", "add", pointer_path.relative_to(ROOT))
    if kind == "county":
        command("git", "add", "public/county-results-overview.geojson.gz")
    command("git", "commit", "-m", "Point to original-backed 2026 " + kind + " refresh " + run_id, env=env)
    command("git", "push", "origin", "HEAD:main")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        command("gh", "workflow", "run", "deploy.yml", "--ref", "main", "--repo", REPO)
    return pointer


def refresh(kind, work, run_id, do_publish=False, replay_source=None):
    work.mkdir(parents=True, exist_ok=False)
    pointer_path = ROOT / ("public/uf-turnout.json" if kind == "uf" else "public/county-results.json")
    previous = read(pointer_path) if pointer_path.exists() else None
    if kind == "uf":
        output, archive = work / "reviewed", work / "complete-uf-turnout.zip"
        load("collect-uf-turnout").collect(output, archive)
    else:
        output, archive = county_candidate(work, previous, replay_source)
    if unchanged(kind, output, previous):
        return dict(status="unchanged", pointer_retained=True)
    if do_publish:
        publish(kind, output, archive, work, run_id, previous)
    return dict(status="published" if do_publish else "reviewed_not_published",
                output=str(output), archive=str(archive), pointer_retained=not do_publish)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["county", "uf", "both"], default="both")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--replay-county-source", type=Path)
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=False)
    results = {}
    for kind in (["uf", "county"] if args.source == "both" else [args.source]):
        pointer = ROOT / ("public/uf-turnout.json" if kind == "uf" else "public/county-results.json")
        previous_bytes = pointer.read_bytes() if pointer.exists() else None
        try:
            results[kind] = refresh(kind, args.work_dir / kind, args.run_id,
                                    args.publish, args.replay_county_source)
        except Exception as error:
            traceback.print_exc()
            results[kind] = dict(status="failed", error=str(error),
                local_pointer_unchanged=(pointer.read_bytes() if pointer.exists() else None) == previous_bytes,
                remote_publication_not_claimed_on_error=True)
        write(args.work_dir / "status.json", results)
    print(json.dumps(results, indent=2))
    if any(result["status"] == "failed" for result in results.values()):
        raise SystemExit(1)
