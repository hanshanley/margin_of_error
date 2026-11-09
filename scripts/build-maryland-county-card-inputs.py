"""Join the held Maryland card report to its complete 2026 county reference."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlsplit
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261109-maryland-cards-01"
NATIVE_SHA = "ea2c98e95e8e708042ae83292f2c07eacd680fa7065ae2be8f6f2ea109027521"
PDF_SHA = "f4ac1aa87b06fbde98ebf0114338ef4c1155d3bf34bb7c5a797ec6a5170f5029"


def key(name):
    return name.lower().removesuffix(" county").replace("saint mary's", "st. mary's")


def build(native, accepted, output):
    if output.exists():
        raise ValueError("Refuse to replace reviewed Maryland inputs")
    raw = native.read_bytes()
    if hashlib.sha256(raw).hexdigest() != NATIVE_SHA:
        raise ValueError("Changed held Maryland sufficient-input archive")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        checksums = json.loads(archive.read("checksums.json"))
        members = {}
        for name in ("general-election-night-turnout.pdf", "independent-card-grid.json", "source-scope.json"):
            body = archive.read(name)
            if len(body) != checksums[name]["bytes"] or hashlib.sha256(body).hexdigest() != checksums[name]["sha256"]:
                raise ValueError("Changed held native member: " + name)
            members[name] = body
        if hashlib.sha256(members["general-election-night-turnout.pdf"]).hexdigest() != PDF_SHA:
            raise ValueError("Wrong Maryland card-report original")
        links = json.loads(archive.read("declared-original-links.json"))
        urls = [row["url"] for row in links if row["url"].endswith("2026-general_election_night_unofficial_turnout.pdf")]
        if len(urls) != 1:
            raise ValueError("Ambiguous native card-report URL")
    grid = json.loads(members["independent-card-grid.json"])
    accepted_raw = accepted.read_bytes()
    accepted_rows = list(csv.DictReader(io.StringIO(accepted_raw.decode())))
    if len(accepted_rows) != 25 or any(
        row["native_county_label"] != saved["native_county_label"]
        or row["native_cards_cast"] != saved["native_cards_cast"]
        or row["native_eligible_voters"] != saved["native_eligible_voters"]
        or row["native_percentage"] != saved["native_percentage"]
        for row, saved in zip(grid["rows"], accepted_rows)
    ):
        raise ValueError("Held original grid differs from accepted complete card query")
    pointer = json.loads((ROOT / "public/county-results.json").read_bytes())
    index = json.loads((ROOT / pointer["data_directory"] / "index.json").read_bytes())
    reference = index["coverage"]["MD"]
    if index["boundary_reference_year"] != 2026 or reference["counties"] != 24:
        raise ValueError("Incorrect Maryland reference inventory")
    path = "/".join(urlsplit(reference["file"]).path.split("/")[4:])
    geometry = (ROOT / path).read_bytes()
    decoded = gzip.decompress(geometry)
    if (hashlib.sha256(geometry).hexdigest() != reference["sha256"]
            or hashlib.sha256(decoded).hexdigest() != reference["uncompressed_sha256"]):
        raise ValueError("Changed full Maryland county reference")
    features = json.loads(decoded)["features"]
    names = {key(row["properties"]["name"]): row["properties"] for row in features}
    if len(names) != 24 or len(grid["rows"]) != 25:
        raise ValueError("Incomplete Maryland reference or source query")
    crosswalk = []
    for row in grid["rows"][:-1]:
        p = names[key(row["native_county_label"])]
        if p["state_code"] != "MD" or p["boundary_year"] != 2026:
            raise ValueError("Incorrect Maryland county identity")
        crosswalk.append(dict(native_county_label=row["native_county_label"],
            county_fips=p["key"], reference_name=p["name"],
            identity_basis="explicit Saint Mary's/St. Mary's alias" if "Saint Mary's" in row["native_county_label"]
                else "exact county name; case and County suffix normalized"))
    if len({row["county_fips"] for row in crosswalk}) != 24:
        raise ValueError("Duplicate Maryland identity; retain Baltimore city separately")
    members["accepted-card-references.csv"] = accepted_raw
    members["county-crosswalk.json"] = (json.dumps(crosswalk, indent=2) + "\n").encode()
    files = {f"{VERSION}/{name}": dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
             for name, body in members.items()}
    files[path] = dict(bytes=len(geometry), sha256=hashlib.sha256(geometry).hexdigest())
    inputs = dict(version=VERSION, year=2026, state_code="MD", native_archive_sha256=NATIVE_SHA,
        source_url=urls[0], pdf_sha256=PDF_SHA, files=files,
        reference=dict(path=path, url=reference["file"], sha256=reference["sha256"],
            uncompressed_sha256=reference["uncompressed_sha256"], boundary_year=2026, counties=24,
            review_id="maryland-native-card-counts-20261109-01"),
        count_reference_join_approved=True, cast_ballot_count_qualified=False,
        unique_voter_count_qualified=False, rates_approved=False, precincts_approved=False,
        complete_download_url="/participation-county-cards/20261109-01/complete-analysis.zip")
    output.mkdir(parents=True)
    for name, body in members.items():
        (output / name).write_bytes(body)
    (output / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    print(json.dumps(dict(county_card_queries=24, separate_state_query=1, rates_approved=False,
        cast_ballot_count_qualified=False, unique_voter_count_qualified=False)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--accepted", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / VERSION)
    args = parser.parse_args()
    build(args.native, args.accepted, args.output)
