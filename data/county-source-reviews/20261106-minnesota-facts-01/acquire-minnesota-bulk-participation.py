"""Save declared Minnesota 2026 aggregate originals privately; never publish estimates as ballots."""

import argparse
import csv
import datetime
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen


INDEX = "https://electionresults.sos.mn.gov/Select/MediaFiles/Index?ersElectionId=201"
IDENTITY = "Tuesday, November 3, 2026"
SOURCES = {
    "View layout of text files": "layout.txt",
    "Precinct Reporting Statistics": "pctstats.txt",
    "Counties": "counties.txt",
    "Precincts": "precincts.txt",
    "Parties": "parties.txt",
    "All Federal, State, and County Races by County": "county-results.txt",
    "All Federal, State, and County Races by Precinct": "precinct-results.txt",
}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.text, self.anchor = [], [], None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            self.anchor = [href, []] if href else None

    def handle_data(self, data):
        self.text.append(data)
        if self.anchor is not None:
            self.anchor[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor is not None:
            href, text = self.anchor
            self.links.append((" ".join(" ".join(text).split()).rstrip("."), urljoin(INDEX, href)))
            self.anchor = None


def declared_sources(body):
    parser = Links()
    parser.feed(body.decode("utf-8-sig"))
    if IDENTITY not in " ".join(" ".join(parser.text).split()):
        raise ValueError("Wrong election identity or inaccessible official parent")
    urls = {}
    for label, name in SOURCES.items():
        matches = [url for title, url in parser.links if title == label]
        if len(matches) != 1:
            raise ValueError("Missing or duplicated actual source declaration: " + label)
        url = matches[0]
        parts = urlsplit(url)
        if name == "layout.txt":
            valid = (parts.scheme == "https" and parts.netloc == "electionresults.sos.mn.gov"
                     and parts.path == "/Results/MediaFileLayout/Index"
                     and parts.query.lower() == "erselectionid=201")
        else:
            valid = (parts.scheme == "https" and parts.netloc == "electionresultsfiles.sos.mn.gov"
                     and parts.path.startswith("/20261103/") and not parts.query
                     and len(parts.path.split("/")) == 3 and parts.path.lower().endswith(".txt"))
        if not valid:
            raise ValueError("Unexpected declared election/source scope: " + name)
        urls[name] = url
    if len(set(urls.values())) != len(urls):
        raise ValueError("Different native tables point to the same export")
    return urls


def statistic_inventory(body):
    rows = list(csv.reader(io.StringIO(body.decode("utf-8-sig")), delimiter=";"))
    if not rows or any(len(row) != 12 or row[0] != "MN" or row[4] not in ("0", "1")
                       or any(not value.isascii() or not value.isdecimal()
                              for value in row[1:3] + row[5:]) for row in rows):
        raise ValueError("Malformed native precinct-statistics schema or reporting flag")
    keys = [(row[1], row[2]) for row in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicated native county/precinct identity")
    return {
        "native_rows": len(rows),
        "reported_statistic_rows": sum(row[4] == "1" for row in rows),
        "unreported_statistic_rows": sum(row[4] == "0" for row in rows),
        "reported_total_number_voted_subtotal": sum(int(row[11]) for row in rows if row[4] == "1"),
        "unreported_native_nonzero_totals": [
            {"county_id": row[1], "precinct_id": row[2], "native_total_number_voted": row[11]}
            for row in rows if row[4] == "0" and int(row[11]) != 0
        ],
        "scope": "Inventory only. Flag-zero totals are not actual ballots, even if nonzero. "
                 "No county aggregate, turnout rate, precinct map or certification is approved.",
    }


def acquire(output):
    output = output.resolve()
    checkout = Path(__file__).resolve().parents[1]
    if output == checkout or checkout in output.parents:
        raise ValueError("Source originals must stay outside the published repository")
    output.mkdir(parents=True, exist_ok=False)

    def fetch(name, url):
        try:
            response = urlopen(url, timeout=120)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            receipt = dict(
                url=url, final_url=response.geturl(), status=response.code,
                content_type=response.headers.get("Content-Type"), bytes=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
                fetched_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        with (output / name).open("xb") as target:
            target.write(body)
        with (output / (name + ".receipt.json")).open("x") as target:
            target.write(json.dumps(receipt, indent=2) + "\n")
        if receipt["status"] != 200 or receipt["final_url"] != url:
            raise ValueError("Source failed or redirected; preserved receipt: " + name)
        print(json.dumps(dict(source_file=name, **receipt)), flush=True)
        return body

    urls = declared_sources(fetch("media-index.html", INDEX))
    for name, url in urls.items():
        fetch(name, url)
    if "Has Reported Statistics (1 = yes, 0 = no)" not in (output / "layout.txt").read_text():
        raise ValueError("Native statistics reporting-flag definition changed")
    inventory = statistic_inventory((output / "pctstats.txt").read_bytes())
    with (output / "statistics-inventory.json").open("x") as target:
        target.write(json.dumps(inventory, indent=2) + "\n")
    print(json.dumps(inventory, indent=2))
    print("All eight declared originals saved privately. No public pointer, rate or map changed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    acquire(parser.parse_args().output)
