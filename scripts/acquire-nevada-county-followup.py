"""Acquire distinct public county reports once, without retrying state access holds."""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import urllib.request


SOURCES = {
    "Clark": "https://elections.clarkcountynv.gov/ElectionResults_NV/EnrEng/EnrMain",
    "Churchill": "https://www.churchillcountynv.gov/ArchiveCenter/ViewFile/Item/1426",
    "White Pine": "https://whitepinecounty.net/DocumentCenter/View/14265/WhitePine-2026-GENERAL-Summary-02",
}


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


class NumericalPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ignored = 0
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.ignored += 1
        if self.ignored:
            return
        if tag == "table":
            if self.table is not None:
                raise ValueError("Nested source tables require explicit qualification")
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.ignored -= 1
            return
        if self.ignored:
            return
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None

    def handle_data(self, value):
        if self.ignored:
            return
        text = " ".join(value.split())
        if text:
            self.text.append(text)
            if self.cell is not None:
                self.cell.append(text)


def acquire(output):
    import fitz
    import io
    from pypdf import PdfReader

    if output.exists():
        raise ValueError("Refusing to overwrite or reacquire an existing acquisition")
    output.mkdir(parents=True)
    receipts = {}
    for county, url in SOURCES.items():
        name = county.lower().replace(" ", "-")
        started = datetime.now(timezone.utc).isoformat()
        with urllib.request.urlopen(url, timeout=90) as response:
            body = response.read()
            status, effective = response.status, response.url
            content_type = response.headers.get("Content-Type")
        if status != 200:
            raise ValueError("Stopped unsuccessful native acquisition: " + county)
        receipt = dict(url=url, effective_url=effective, status=status,
            content_type=content_type, started_at_utc=started,
            finished_at_utc=datetime.now(timezone.utc).isoformat(), **pin(body))
        receipts[county] = receipt
        if county == "Clark":
            text = body.decode("utf-8-sig")
            if "REGISTRATION" not in text or "2026 General Election" not in text:
                raise ValueError("Wrong election or challenge body, not numerical source")
            parser = NumericalPage()
            parser.feed(text)
            facts = dict(all_tables=parser.tables, source_text=parser.text,
                publisher_application_code_excluded=True)
            (output / (name + "-original.html.gz")).write_bytes(gzip.compress(body, mtime=0))
        else:
            if not body.startswith(b"%PDF-"):
                raise ValueError("Not a native PDF; no alternative-client retry")
            (output / (name + "-original.pdf")).write_bytes(body)
            with fitz.open(stream=body, filetype="pdf") as document:
                pages = [page.get_text() for page in document]
            independent = PdfReader(io.BytesIO(body))
            if len(independent.pages) != len(pages):
                raise ValueError("Independent native PDF page counts disagree")
            facts = dict(page_texts=pages,
                independent_first_page_text=independent.pages[0].extract_text(),
                original_pdf_pages=len(pages))
        (output / (name + "-complete-numerical-facts.json")).write_bytes(encoded(facts))
        print(json.dumps(dict(county=county, source=receipt,
            complete_factual_tables=len(facts.get("all_tables", [])),
            complete_pdf_pages=facts.get("original_pdf_pages"))), flush=True)
    (output / "source-receipts-without-headers.json").write_bytes(encoded(receipts))
    (output / "access-holds.json").write_bytes(encoded(dict(
        reviewed_date="2026-11-10",
        stopped_sources=[
            dict(url="https://silverstateelection.nv.gov/",
                reason="Additional security check; automated traffic explicitly prohibited",
                HTTP_status_not_established=True),
            dict(url="https://www.nvsos.gov/vivid/",
                reason="Additional security check; automated traffic explicitly prohibited",
                HTTP_status_not_established=True),
        ],
        no_alternative_client_cache_mirror_key_or_challenge_bypass=True,
        new_sources_are_distinct_county_administration_reports=True)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    acquire(parser.parse_args().output)
