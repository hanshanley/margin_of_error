"""Preserve all advertised Wyoming 2026/2022 general-election originals."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import zipfile

import fitz


YEARS = (2026, 2022)
COUNTIES = (
    "Albany", "Big Horn", "Campbell", "Carbon", "Converse", "Crook", "Fremont",
    "Goshen", "Hot Springs", "Johnson", "Laramie", "Lincoln", "Natrona",
    "Niobrara", "Park", "Platte", "Sheridan", "Sublette", "Sweetwater",
    "Teton", "Uinta", "Washakie", "Weston",
)


def source_url(year):
    return f"https://sos.wyo.gov/Elections/Docs/{year}/{year}GeneralResults.aspx"


def advertised_files(raw, year):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.urls = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "a" and attrs.get("href"):
                self.urls.append(urljoin(source_url(year), attrs["href"]))

    parser = Links()
    parser.feed(raw.decode("utf-8-sig"))
    prefix = f"https://sos.wyo.gov/Elections/Docs/{year}/Results/General/"
    files = sorted({url for url in parser.urls
                    if url.startswith(prefix) and url.lower().endswith((".pdf", ".zip"))})
    names = [urlsplit(url).path.rsplit("/", 1)[1] for url in files]
    required = {f"{year}_{county.replace(' ', '_')}_County_General_PbP{suffix}.pdf"
                for county in COUNTIES for suffix in ("", "_TBC")}
    required |= {f"{year}_General_Statewide_{kind}_Summary.pdf"
                 for kind in ("Candidates", "Total_Ballots_Cast")}
    if not required <= set(names) or len(names) != len(set(names)):
        raise ValueError("Missing or ambiguous Wyoming county/precinct/ballot originals")
    return files


def document_inventory(raw, name, year, visual_identity=None):
    if name.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if archive.testzip() is not None:
                raise ValueError("Corrupt Wyoming original ZIP")
            names = [name for name in archive.namelist() if not name.endswith("/")]
            if not names or len(names) != len(set(names)):
                raise ValueError("Missing or duplicate Wyoming original ZIP members")
            return dict(zip_members=names, zip_crc_valid=True)
    if not raw.startswith(b"%PDF") or not raw.rstrip().endswith(b"%%EOF"):
        raise ValueError("Incomplete or non-PDF Wyoming original")
    with fitz.open(stream=raw, filetype="pdf") as document:
        day = 3 if year == 2026 else 8
        literal = f"November {day}, {year}"
        if not len(document) or document.is_repaired:
            raise ValueError("Wrong election identity or repaired Wyoming PDF")
        method = "native_text"
        if literal not in document[0].get_text():
            if not visual_identity or visual_identity.get("year") != year or (
                visual_identity.get("source_sha256") != hashlib.sha256(raw).hexdigest()
                or visual_identity.get("literal_election_date") != literal
                or visual_identity.get("method") != "direct_rendered_header_review"
            ):
                raise ValueError("Wrong or unreadable election identity; exact visual source review required")
            method = "direct_rendered_header_review"
        return dict(pdf_pages=len(document),
                    election_date_literal=literal, election_date_verification=method,
                    extracted_text_bytes=sum(len(page.get_text().encode()) for page in document))


def download(cache, year):
    import requests

    directory = cache / str(year)
    directory.mkdir(parents=True, exist_ok=True)

    def fetch(url):
        name = "results-index.html" if url == source_url(year) else urlsplit(url).path.rsplit("/", 1)[1]
        path = directory / name
        receipt = directory / (name + ".source.json")
        if path.exists() or receipt.exists():
            if not path.exists() or not receipt.exists():
                raise ValueError("Incomplete cached Wyoming response: " + name)
            return path.read_bytes()
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        body = response.content
        path.write_bytes(body)
        receipt.write_text(json.dumps(dict(url=url, resolved_url=response.url,
            status_code=response.status_code, retrieved_at=datetime.now(timezone.utc).isoformat(),
            headers=dict(response.headers), bytes=len(body), sha256=hashlib.sha256(body).hexdigest()),
            indent=2) + "\n")
        return body

    raw = fetch(source_url(year))
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(fetch, advertised_files(raw, year)))


def archive_sources(cache, output, archive_path, visual_identities=None):
    if output.exists() or archive_path.exists():
        raise ValueError("Refusing to overwrite an immutable Wyoming package")
    originals, receipts, elections = {}, {}, {}
    for year in YEARS:
        directory = cache / str(year)
        index = (directory / "results-index.html").read_bytes()
        urls = [source_url(year), *advertised_files(index, year)]
        documents = {}
        for url in urls:
            name = "results-index.html" if url == source_url(year) else urlsplit(url).path.rsplit("/", 1)[1]
            body = (directory / name).read_bytes()
            receipt = json.loads((directory / (name + ".source.json")).read_text())
            if receipt["url"] != url or receipt["resolved_url"] != url or receipt["status_code"] != 200 or (
                receipt["bytes"] != len(body) or receipt["sha256"] != hashlib.sha256(body).hexdigest()
            ):
                raise ValueError("Changed or failed Wyoming original: " + name)
            if name != "results-index.html":
                documents[name] = document_inventory(body, name, year,
                    (visual_identities or {}).get(name))
            key = f"{year}/{name}"
            originals[key], receipts[key] = body, receipt
        elections[str(year)] = dict(year=year, state_code="WY", complete="no",
            candidate_results="acquired_originals_review_pending",
            boundaries="not_acquired_in_this_batch", join="pending",
            validation="complete_advertised_originals_pdf_identity_and_zip_crc_verified",
            publication="full_originals_download_only", participation="not_reconciled",
            source_url=source_url(year), original_files=len(urls),
            original_bytes=sum(len(originals[f"{year}/{name}"]) for name in ["results-index.html", *documents]),
            source_index_status="unofficial" if year == 2026 else "official", documents=documents,
            next_action="Reconcile all native precinct candidate vectors, write-ins, overvotes, undervotes "
                        "and separate ballots against county/state summaries. For 2022 independently "
                        "compare the acquired OpenElections CSV to these originals. Acquire actual-election "
                        "precinct or county geometry; do not infer registered denominators or allocate votes.")
    output.mkdir(parents=True)
    if visual_identities:
        (output / "visual-identity-reviews.json").write_text(json.dumps(visual_identities, indent=2) + "\n")
    for key, body in originals.items():
        path = output / "originals" / (key + ".gz")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(body, mtime=0))
    for name, value in {
        "sources.json": receipts,
        "acquisition.json": dict(state_code="WY", elections=elections,
            original_files=len(originals), original_bytes=sum(map(len, originals.values())),
            maps_approved=False, notes="Complete advertised 2026 and 2022 statewide and all 23 county "
                "precinct-result/ballot originals, including the native 2022 data ZIP. Calendar/navigation "
                "PDFs are not result documents. These are individually dated captures, not a simultaneous "
                "or reconciled statewide snapshot. Thirteen 2026 Type3-font PDF dates required direct "
                "rendered-header review, bound to exact source SHA-256; text extraction is not repaired "
                "or treated as numeric data. Park's 2026 native headers say Official while its banner "
                "and the source index say Unofficial; retain both labels. No new turnout rate, "
                "precinct join or map is approved."),
    }.items():
        (output / name).write_text(json.dumps(value, separators=(",", ":"), ensure_ascii=True))
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output / "checksums.json").write_text(json.dumps({
        path.relative_to(output).as_posix(): dict(bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(output.rglob("*")) if path.is_file()
    }, separators=(",", ":")))
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(output).as_posix())
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())
    return dict(original_files=len(originals), original_bytes=sum(map(len, originals.values())),
                archive_bytes=archive_path.stat().st_size,
                archive_sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(), elections=elections)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--visual-identities", type=Path)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    if args.download:
        for year in YEARS:
            download(args.cache_root, year)
    identities = json.loads(args.visual_identities.read_text()) if args.visual_identities else None
    print(json.dumps(archive_sources(args.cache_root, args.output, args.archive, identities), indent=2))
