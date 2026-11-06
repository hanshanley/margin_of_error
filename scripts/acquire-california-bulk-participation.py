"""Save actually declared California 2026 bulk sources privately; never move public pointers."""

import argparse
import csv
import datetime
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import urlopen
import xml.etree.ElementTree as ET
import zipfile


PARENT = "https://media.sos.ca.gov/"
IDENTITY = "California General Election Tuesday, November 3, 2026"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls, self.text = set(), []

    def handle_starttag(self, tag, attrs):
        if tag == "a" and dict(attrs).get("href"):
            self.urls.add(urljoin(PARENT, dict(attrs)["href"]))

    def handle_data(self, data):
        self.text.append(data)


def declared_parent(body):
    parser = Links()
    parser.feed(body.decode("utf-8"))
    if IDENTITY not in " ".join(" ".join(parser.text).split()):
        raise ValueError("Wrong election identity or inaccessible official parent")
    required = tuple(letter + "26GG.txt" for letter in "CJPRSV") + (
        "json-endpoints.csv", "api-endpoints.csv", "bulk-file-locations.xlsx")
    urls = {name: urljoin(PARENT, "media/" + name) for name in required}
    if not set(urls.values()) <= parser.urls:
        raise ValueError("Missing actual parent declaration; do not guess an export")
    return urls


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
            raise ValueError("Source request failed or redirected; preserved receipt: " + name)
        print(json.dumps(dict(source_file=name, **receipt)), flush=True)
        return body

    urls = declared_parent(fetch("media-index.html", PARENT))
    for name in ("json-endpoints.csv", "api-endpoints.csv", "bulk-file-locations.xlsx"):
        fetch(name, urls[name])
    catalog = list(csv.reader(io.StringIO(
        (output / "json-endpoints.csv").read_text(encoding="utf-8-sig"))))
    status_url = PARENT + "media/status_GG.json"
    if not any(row and row[0] == status_url for row in catalog):
        raise ValueError("No actual status-JSON declaration")
    with zipfile.ZipFile(output / "bulk-file-locations.xlsx") as archive:
        strings = ["".join(row.itertext()) for row in ET.fromstring(
            archive.read("xl/sharedStrings.xml"))]
    if not all(name in strings for name in (PARENT + "media/", "status_GG.zip", "all_GG.zip")):
        raise ValueError("No actual complete-archive declarations")
    fetch("status_GG.json", status_url)
    for name in ("status_GG.zip", "all_GG.zip"):
        fetch(name, urljoin(PARENT, "media/" + name))
    for name in tuple(letter + "26GG.txt" for letter in "CJPRSV"):
        fetch(name, urls[name])
    print("All thirteen declared originals saved privately. Review before publishing; no pointer changed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    acquire(parser.parse_args().output)
