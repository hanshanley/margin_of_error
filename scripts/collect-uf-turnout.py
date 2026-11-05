"""Discover and preserve UF's declared public 2026 turnout table and methodology."""

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit
import zipfile

import requests


CATALOG = "https://election.lab.ufl.edu/data-archive/national/"
CODES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC US".split())
COUNTS = ["TOTAL_BALLOTS_COUNTED", "VAP", "INELIGIBLE_PRISON", "INELIGIBLE_PROBATION",
          "INELIGIBLE_PAROLE", "INELIGIBLE_FELONS_TOTAL", "ELIGIBLE_OVERSEAS", "VEP"]
PERCENTAGES = ["NONCITIZEN_PCT", "VEP_TURNOUT_RATE", "VAP_TURNOUT_RATE"]


class Links(HTMLParser):
    def __init__(self, page, base):
        super().__init__()
        self.urls, self.base = [], base
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.urls.append(urljoin(self.base, href))


def public_url(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.netloc != "election.lab.ufl.edu" or parts.query or parts.fragment:
        raise ValueError("UF download must be declared on the public official host")
    return parts.path


def discover(page):
    versions = {}
    for url in Links(page, CATALOG).urls:
        parts = urlsplit(url)
        match = re.fullmatch(r"/dataset/2026-general-election-turnout-rates-v(\d+(?:-\d+)+)/", parts.path)
        if match:
            public_url(url)
            version = tuple(int(part) for part in match[1].split("-"))
            versions[version] = url
    if not versions:
        raise ValueError("Official catalog declares no public 2026 general-election dataset")
    version = max(versions)
    return versions[version], ".".join(map(str, version))


def downloads(page, dataset):
    csv_urls, docs = set(), set()
    for url in Links(page, dataset).urls:
        if "Turnout_2026G_" not in url:
            continue
        path = public_url(url)
        if re.fullmatch(r"/data-downloads/turnoutdata/Turnout_2026G_v[\d.]+\.csv", path):
            csv_urls.add(url)
        if re.fullmatch(r"/data-downloads/turnoutdata/Turnout_2026G_v[\d.]+_doc\.txt", path):
            docs.add(url)
    if len(csv_urls) != 1 or len(docs) != 1:
        raise ValueError("Dataset must declare exactly one public 2026 CSV and methodology")
    return csv_urls.pop(), docs.pop()


def number(value, percentage=False):
    value = value.strip()
    if not value:
        return None
    if percentage:
        if not re.fullmatch(r"\d+(?:\.\d+)?%", value):
            raise ValueError("Invalid literal UF percentage")
        result = float(value[:-1])
        if not 0 <= result <= 100:
            raise ValueError("UF percentage outside 0-100")
        return result
    if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)", value):
        raise ValueError("Invalid explicit UF integer")
    return int(value.replace(",", ""))


def parse(raw):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    expected = {"STATE", "STATE_ABV", "SOURCE", *COUNTS, *PERCENTAGES}
    if reader.fieldnames is None or set(reader.fieldnames) != expected or len(reader.fieldnames) != len(expected):
        raise ValueError("Unrecognized UF turnout schema")
    rows, seen = [], set()
    for original in reader:
        if any(not isinstance(value, str) for value in original.values()):
            raise ValueError("Malformed UF source row")
        code = original["STATE_ABV"]
        if (code not in CODES or code in seen or not original["STATE"].strip()
                or not original["SOURCE"].strip() or None in original):
            raise ValueError("Invalid or duplicate UF jurisdiction/source identity")
        seen.add(code)
        row = dict(original)
        for field in COUNTS:
            row[field] = number(row[field])
        for field in PERCENTAGES:
            row[field] = number(row[field], percentage=True)
        ballots = row["TOTAL_BALLOTS_COUNTED"]
        for basis in ("VEP", "VAP"):
            denominator, rate = row[basis], row[basis + "_TURNOUT_RATE"]
            if rate is not None and (ballots is None or not denominator
                    or abs(100 * ballots / denominator - rate) > .006):
                raise ValueError("Published UF turnout rate does not match its own counts")
        row.update(year=2026, geographic_level="national" if code == "US" else "state",
                   ballots_status="estimate" if re.search(r"\bestimat", row["SOURCE"], re.I)
                   else "source_reported_not_independently_certified")
        rows.append(row)
    if seen != CODES:
        raise ValueError("UF table must contain all 50 states, DC and the separate US aggregate")
    return sorted(rows, key=lambda row: row["STATE_ABV"])


def collect(output, archive_path):
    if output.exists():
        raise FileExistsError("Use a fresh immutable UF output directory")
    output.mkdir(parents=True)
    originals = output / "originals"
    originals.mkdir()
    receipts = []

    def fetch(name, url):
        public_url(url)
        response = requests.get(url, timeout=(20, 90))
        raw = response.content
        path = originals / name
        path.write_bytes(raw)
        receipt = dict(file="originals/" + name, url=url, status=response.status_code,
                       bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                       retrieved_at=datetime.now(timezone.utc).isoformat(),
                       headers={key: value for key, value in response.headers.items()
                                if key.lower() in {"content-type", "etag", "last-modified", "date"}})
        receipts.append(receipt)
        path.with_suffix(path.suffix + ".receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        response.raise_for_status()
        if len(raw) > 20_000_000 or response.url != url:
            raise ValueError("Unexpected UF redirect or download size")
        return raw

    dataset, version = discover(fetch("catalog.html", CATALOG).decode())
    csv_url, documentation_url = downloads(fetch("dataset.html", dataset).decode(), dataset)
    raw = fetch("turnout.csv", csv_url)
    documentation = fetch("documentation.txt", documentation_url).decode()
    if "DOCUMENTATION FOR 2026 GENERAL ELECTION TURNOUT RATES" not in documentation.upper():
        raise ValueError("Methodology does not identify the same 2026 election")
    rows = parse(raw)
    (output / "turnout.json").write_text(json.dumps(rows, indent=2) + "\n")
    normalized = io.StringIO(newline="")
    writer = csv.DictWriter(normalized, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (output / "turnout.csv").write_text(normalized.getvalue())
    audit = dict(year=2026, version=version, dataset_url=dataset, csv_url=csv_url,
                 documentation_url=documentation_url, rows=len(rows),
                 source_labels=dict(Counter(row["SOURCE"] for row in rows)),
                 estimate_rows=sum(row["ballots_status"] == "estimate" for row in rows),
                 receipts=receipts,
                 scope="UF state/national participation, not county candidate votes or demographic turnout. "
                 "Source-labeled estimates stay estimates. Blank fields stay missing; explicit zero stays zero. "
                 "US aggregate is separate and is not added to state totals. Rates use each row's own VEP/VAP.",
                 attribution="Michael McDonald, UF Election Lab; license and population methodology retained "
                 "verbatim in originals/documentation.txt.")
    (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    checksums = {path.relative_to(output).as_posix(): dict(bytes=path.stat().st_size,
                 sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in sorted(output.rglob("*")) if path.is_file()}
    (output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(output).as_posix())
        archive.write(Path(__file__), Path(__file__).name)
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(collect(args.output, args.archive), indent=2))
