"""Acquire declared current general-election reports privately; never publish unreviewed counts."""

import argparse
import datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen


PARENT = "https://www.nj.gov/state/elections/election-information-2026.shtml"
INDEX = "https://www.nj.gov/state/elections/election-results-information.shtml"
COUNTIES = ("Atlantic", "Bergen", "Burlington", "Camden", "Cape May", "Cumberland",
            "Essex", "Gloucester", "Hudson", "Hunterdon", "Mercer", "Middlesex",
            "Monmouth", "Morris", "Ocean", "Passaic", "Salem", "Somerset", "Sussex",
            "Union", "Warren")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.section = [], None
        self.heading_tag, self.heading, self.anchor = None, [], None

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "h4"):
            self.heading_tag, self.heading = tag, []
        if tag == "a":
            href = dict(attrs).get("href")
            self.anchor = [self.section, href, []] if href else None

    def handle_data(self, data):
        if self.heading_tag:
            self.heading.append(data)
        if self.anchor:
            self.anchor[2].append(data)

    def handle_endtag(self, tag):
        if tag == self.heading_tag:
            label = " ".join(" ".join(self.heading).split())
            if label == "2026 General Election":
                self.section = "general"
            elif re.match(r"2026 .*?(?:Primary|Special).*?Election", label):
                self.section = None
            self.heading_tag = None
        if tag == "a" and self.anchor:
            section, href, text = self.anchor
            self.links.append((section, href, " ".join(" ".join(text).split())))
            self.anchor = None


def catalog(data, today):
    parser = Links()
    parser.feed(data.decode("utf-8"))
    candidates = {}
    for section, href, label in parser.links:
        match = re.fullmatch(r"(.+?)(?: Election Night)? Report - (\d{2})/(\d{2})", label)
        if section != "general" or not match:
            continue
        county = match[1]
        if county not in COUNTIES:
            raise ValueError("Unexpected county in the general-election catalog")
        date = datetime.date(2026, int(match[2]), int(match[3]))
        if not datetime.date(2026, 11, 3) <= date <= today:
            raise ValueError("Out-of-scope or future general-election report")
        url = urljoin(INDEX, href)
        target = urlsplit(url)
        if (target.scheme != "https" or target.netloc != "www.nj.gov" or target.query
                or target.fragment or not target.path.startswith(
                    "/state/elections/assets/pdf/periodic-report/2026/")
                or not target.path.endswith(".pdf")):
            raise ValueError("Unexpected declared export destination")
        candidates.setdefault(county, []).append((date, url, label))
    if set(candidates) != set(COUNTIES):
        raise ValueError("Incomplete 21-county current general-election catalog")
    selected = []
    for county in COUNTIES:
        latest = max(row[0] for row in candidates[county])
        choices = {row for row in candidates[county] if row[0] == latest}
        if len(choices) != 1:
            raise ValueError("Ambiguous latest declared county report")
        date, url, label = choices.pop()
        selected.append(dict(county=county, report_date=date.isoformat(), label=label, url=url))
    if len({row["url"] for row in selected}) != 21:
        raise ValueError("Repeated export URL across county identities")
    return selected


def acquire(output):
    output = output.resolve()
    checkout = Path(__file__).resolve().parents[1]
    if output == checkout or checkout in output.parents:
        raise ValueError("Source originals must stay outside the published repository")
    output.mkdir(parents=True, exist_ok=False)

    def fetch(name, url):
        try:
            response = urlopen(url, timeout=60)
        except HTTPError as error:
            response = error
        with response:
            data = response.read()
            receipt = dict(url=url, final_url=response.geturl(), status=response.getcode(),
                bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                fetched_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        (output / name).write_bytes(data)
        (output / (name + ".receipt.json")).write_text(json.dumps(receipt, indent=2) + "\n")
        if receipt["status"] != 200 or receipt["final_url"] != url:
            raise ValueError("Source HTTP/redirect failure; receipt preserved, acquisition stopped")
        return data

    parent = Links()
    parent.feed(fetch("official-2026-index.html", PARENT).decode("utf-8"))
    if INDEX not in {urljoin(PARENT, href) for section, href, label in parent.links}:
        raise ValueError("State parent no longer declares this consolidated index")
    selected = catalog(fetch("official-periodic-index.html", INDEX),
                       datetime.datetime.now(datetime.timezone.utc).date())
    (output / "declared-latest-general-reports.json").write_text(json.dumps(selected, indent=2) + "\n")
    for row in selected:
        name = row["county"].lower().replace(" ", "-") + "-periodic-report.pdf"
        data = fetch(name, row["url"])
        if not data.startswith(b"%PDF-"):
            raise ValueError("Declared PDF returned a different representation; acquisition stopped")
    return dict(counties=len(selected), private_output=str(output), publication_approved=False,
                next_step="Review all source scopes and counts into a new immutable factual package.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-output", type=Path, required=True)
    print(json.dumps(acquire(parser.parse_args().private_output), indent=2))
