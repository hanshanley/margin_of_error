"""Archive every declared Clark historical precinct statement without inferring suppressed votes."""

import argparse
from collections import Counter
import csv
import gzip
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit
import zipfile

import fitz


SOURCE = "https://elections.clarkcountynv.gov/electionresultsTV/results.aspx"
ELECTIONS = {
    2024: ("24G", "November 05, 2024", "11/05/2024", 200),
    2022: ("22G", "November 08, 2022", "11/08/2022", 200),
    2020: ("20G", "November 03, 2020", "11/03/2020", 264),
}
MODES = ["Totals", "Election Day", "Early Vote", "Mail"]
SCOPE = (
    "Clark County only, not statewide Nevada. All declared precinct-statement PDF/Data originals "
    "are retained, including privacy-suppressed fields and native quoting errors. Source bytes, "
    "election identity and record structure are checked, not candidate totals, residential ballot "
    "scope, registration definitions or election-applicable boundaries. No suppressed votes are "
    "reconstructed, repeated registration summed, turnout rates inferred or new maps claimed."
)


class NativeIndex(HTMLParser):
    def __init__(self, raw):
        super().__init__(convert_charrefs=True)
        self.selected, self.links = {}, []
        self.select, self.option = None, None
        self.feed(raw.decode("utf-8-sig"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select":
            self.select = attrs.get("name")
        elif tag == "option" and self.select:
            self.option = [attrs.get("value"), "selected" in attrs, ""]
        elif tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])

    def handle_data(self, data):
        if self.option is not None:
            self.option[2] += data

    def handle_endtag(self, tag):
        if tag == "option" and self.option is not None:
            value, selected, text = self.option
            if selected:
                self.selected.setdefault(self.select, []).append((value, text.strip()))
            self.option = None
        elif tag == "select":
            self.select = None


def report_links(raw, year):
    code, _, date, expected = ELECTIONS[year]
    index = NativeIndex(raw)
    if (index.selected.get("ddlElection") != [(code, f"{year} GENERAL ELECTION ({date})")]
            or index.selected.get("ddlCategory") != [
                ("3", "STATEMENT OF VOTE (RESULTS BY PRECINCT)")]):
        raise ValueError("Wrong Clark native election or report-category selection")
    links = [url for url in index.links if "/SOV/" in url]
    if len(links) != expected or len(set(links)) != expected:
        raise ValueError("Incomplete or duplicated Clark declared report inventory")
    pairs = {}
    for url in links:
        parsed = urlsplit(url)
        prefix = f"/electionresultsTV/SOV/{code}/"
        name = unquote(parsed.path.removeprefix(prefix))
        if (parsed.scheme != "https" or parsed.netloc != "elections.clarkcountynv.gov"
                or not parsed.path.startswith(prefix) or parsed.query or parsed.fragment
                or "/" in name or "\\" in name or Path(name).suffix not in {".pdf", ".txt"}):
            raise ValueError("Wrong Clark declared report source")
        pairs.setdefault(name.rsplit(".", 1)[0], set()).add(Path(name).suffix)
    if any(formats != {".pdf", ".txt"} for formats in pairs.values()):
        raise ValueError("Missing Clark PDF/Data report pair")
    return sorted(links)


def original(root, name, url, method="GET"):
    raw = (root / name).read_bytes()
    receipt = json.loads((root / (name + ".receipt.json")).read_bytes())
    if (receipt["url"] != url or unquote(receipt["resolved_url"]) != unquote(url)
            or receipt["status"] != 200 or receipt.get("method", "GET") != method
            or receipt["bytes"] != len(raw)
            or receipt["sha256"] != hashlib.sha256(raw).hexdigest()):
        raise ValueError("Changed, failed or wrong Clark original receipt")
    return raw, receipt


def text_inventory(raw):
    text = raw.decode("utf-8-sig")
    strict_error = None
    reader = csv.reader(io.StringIO(text, newline=""), skipinitialspace=True, strict=True)
    try:
        list(reader)
    except csv.Error as error:
        strict_error = dict(physical_line=reader.line_num, error=str(error))
    records = list(csv.reader(io.StringIO(text, newline=""), skipinitialspace=True))
    if not records or records[0][:5] != [
            "Precinct", "Tally Type", "Registration", "Turnout", "Total Votes"]:
        raise ValueError("Wrong Clark native Data header")
    header = records[0]
    offsets = [i for i, row in enumerate(records) if row[:1] == ["Totals"]]
    if len(offsets) != 1:
        raise ValueError("Missing or repeated Clark native Data footer")
    offset = offsets[0]
    rows, footer = records[1:offset], records[offset:]
    if (footer[0] != ["Totals", "Tally Type", "# Voters", "Voters/Turnout"]
            or len(footer) != 4 or [row[0] for row in footer[1:]] != MODES[1:]
            or any(len(row) != 3 for row in footer[1:])):
        raise ValueError("Wrong Clark native Data footer structure")
    if (not rows or len(rows) % 4 or any(len(row) != len(header) for row in rows)):
        raise ValueError("Incomplete Clark native Data record structure")
    for i in range(0, len(rows), 4):
        group = rows[i:i + 4]
        if ([row[1] for row in group] != MODES or len({row[0] for row in group}) != 1
                or any(not value.isascii() or not value.isdecimal()
                       for row in group for value in row[2:5])):
            raise ValueError("Changed Clark native precinct/mode record structure")
    return dict(permissive_header=header, native_data_records=len(rows),
        native_record_widths=dict(Counter(len(row) for row in rows)),
        rows_by_tally_type=dict(Counter(row[1] for row in rows)),
        privacy_suppressed_candidate_fields=sum(value == "*" for row in rows for value in row[5:]),
        totals_records_turnout_exceeds_registration=sum(
            row[1] == "Totals" and int(row[3]) > int(row[2]) for row in rows),
        strict_csv_error=strict_error,
        notes="Permissive structure inventory only; malformed quoted names are not canonical candidate "
              "identities. Flags count source records across contests, not distinct precincts. "
              "The native footer is retained, not used to reconstruct suppressed candidate counts.")


def pdf_inventory(raw, year):
    if not raw.startswith(b"%PDF-"):
        raise ValueError("Clark original is not PDF")
    with fitz.open(stream=raw, filetype="pdf") as doc:
        if not len(doc):
            raise ValueError("Empty Clark PDF")
        identity_pages, blank_pages = 0, []
        for page in doc:
            lines = [line.strip() for line in page.get_text().splitlines() if line.strip()]
            if not lines:
                if (page.number == 0 or page.number != len(doc) - 1
                        or page.get_images() or page.get_drawings()
                        or min(page.get_pixmap(alpha=False).samples) != 255):
                    raise ValueError("Unexpected textless Clark PDF page")
                blank_pages.append(page.number + 1)
                continue
            if page.number == 0 or any(
                    line.casefold().endswith(" general election") or line == "Statement of Vote"
                    for line in lines):
                if (lines[0].casefold() != f"{year} general election"
                        or lines[1:4] != [ELECTIONS[year][1], "Statement of Vote", "Clark County"]):
                    raise ValueError("Wrong Clark PDF election, date or county")
                identity_pages += 1
        return dict(pages=len(doc), source_county="Clark County",
                    source_election_date=ELECTIONS[year][1],
                    pages_with_election_identity=identity_pages,
                    continuation_pages_without_repeated_identity=len(doc) - identity_pages - len(blank_pages),
                    blank_terminal_pages=blank_pages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable Clark historical archive")
    originals, receipts, elections, inventories = {}, {}, {}, {}

    def retain(key, name, url, method="GET"):
        raw, receipt = original(args.cache_root, name, url, method)
        originals[key], receipts[key] = raw, receipt
        return raw

    name = "official-fresh-results-selector.html"
    retain("index/" + name, name, SOURCE)
    for year, (code, _, _, _) in ELECTIONS.items():
        keys = []
        for role in ["election-selection", "precinct-statement-index"]:
            name = f"official-{code}-{role}.html"
            key = f"{year}/{name}"
            raw = retain(key, name, SOURCE, "POST")
            keys.append(key)
        urls = report_links(raw, year)
        formats = {}
        for i, url in enumerate(urls, 1):
            key = f"{year}/{i:03d}{Path(urlsplit(url).path).suffix}"
            raw = retain(key, key, url)
            try:
                formats[key] = text_inventory(raw) if key.endswith(".txt") else pdf_inventory(raw, year)
            except ValueError as error:
                raise ValueError(f"{key}: {error}") from error
            keys.append(key)
        inventories[str(year)] = formats
        elections[str(year)] = dict(year=year, state_code="NV", county_name="Clark",
            county_fips="32003", complete="no",
            candidate_results="acquired_originals_review_pending",
            boundaries="not_acquired_in_this_batch", join="pending",
            validation="county_only_source_bytes_election_identity_and_native_structure_verified",
            publication="full_originals_download_only", participation="not_reconciled",
            source_url=SOURCE, original_files=len(keys),
            original_bytes=sum(len(originals[key]) for key in keys),
            declared_report_files=len(urls), native_pdf_pages=sum(
                item.get("pages", 0) for item in formats.values()),
            native_data_records=sum(item.get("native_data_records", 0) for item in formats.values()),
            strict_csv_error_files=sum(item.get("strict_csv_error") is not None
                                      for item in formats.values()),
            notes=SCOPE,
            next_action="Clark County only. Independently reconcile each native contest and ballot-mode "
                        "scope to separate official summaries, preserving privacy suppression and quoting "
                        "errors. Review election-applicable boundaries and registration before any "
                        "map or turnout rate; continue other Nevada counties. Previously acquired "
                        "statewide source files and existing maps remain separately available.")
    args.output.mkdir(parents=True)
    for key, raw in originals.items():
        path = args.output / "originals" / (key + ".gz")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(raw, mtime=0))
    acquisition = dict(state_code="NV", county_name="Clark", county_fips="32003",
        elections=elections, original_files=len(originals),
        original_bytes=sum(map(len, originals.values())), notes=SCOPE)
    for name, value in {"sources.json": receipts, "acquisition.json": acquisition,
                        "native-inventory.json.gz": inventories}.items():
        raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        (args.output / name).write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)
    checksums = {str(path.relative_to(args.output)): dict(bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(args.output.rglob("*")) if path.is_file()}
    (args.output / "checksums.json").write_text(json.dumps(checksums, separators=(",", ":")))
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(str(path.relative_to(args.output)), (2026, 11, 5, 0, 0, 0))
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())
    print(json.dumps(acquisition, indent=2))


if __name__ == "__main__":
    main()
