"""Reconcile Worcester's native 2026 governor counts without inventing turnout or maps."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
from urllib.parse import urljoin
import zipfile

import fitz
from bs4 import BeautifulSoup
from PIL import Image, ImageOps


SOURCE = "https://www.worcesterma.gov/elections/election-results"
PDF = "official-worcester-declared-2026-general-results.pdf"
INDEX = "official-worcester-results-index.html"
APPROVED_PDF = "2e6a56d549da7fad167874a9b9599ad4434a1b9da5b574571e1742184c39a004"
MODES = {15: "overall", 27: "election_day", 39: "early_voting_1", 51: "early_voting_2"}
COLUMNS = ("democratic_votes", "republican_votes", "independent_votes",
           "write_in_votes", "blank_votes")
RELEASE = "https://github.com/hanshanley/margin_of_error/releases/download/voter-precinct-worcester-counts-20261105/"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reconcile_counts(readings, manual, precincts):
    if (len(precincts) != 62 or len(set(precincts)) != 62
            or not {"4-2A", "7-5A"} <= set(precincts)
            or any(not re.fullmatch(r"(?:[1-9]|10)-[1-6]A?", code) for code in precincts)):
        raise ValueError("Incomplete, duplicate or invalid actual Worcester precinct inventory")
    matrix, names = {}, set()
    for entry in readings:
        name = entry["file"]
        match = re.fullmatch(r"page-(\d{3})-row-(\d{3})-col-([1-5])\.png", name)
        if not match or name in names:
            raise ValueError("Unknown or duplicate Worcester source cell")
        names.add(name)
        page, row, column = map(int, match.groups())
        if name in manual:
            value = manual[name]
            if type(value) is not int or value < 0:
                raise ValueError("Invalid explicitly reviewed Worcester integer")
        else:
            result = entry.get("result")
            if (not result or len(result) != 1 or not isinstance(result[0][0], str)
                    or not re.fullmatch(r"0|[1-9][0-9]*", result[0][0].strip())):
                raise ValueError("Missing or ambiguous Worcester count; never infer zero or repair OCR")
            value = int(result[0][0].strip())
        matrix.setdefault(page, {}).setdefault(row, {})[column] = value
    expected_pages = {page + offset for page in MODES for offset in (0, 1)}
    if set(matrix) != expected_pages or not set(manual) <= names or len(names) != 1260:
        raise ValueError("Incomplete eight-panel Worcester count inventory or unused review")
    values, footers = {}, {}
    for first, mode in MODES.items():
        if (set(matrix[first]) != set(range(1, 39))
                or set(matrix[first + 1]) != set(range(1, 26))):
            raise ValueError("Missing or extra actual Worcester precinct/footer row")
        rows = [matrix[first][row] for row in range(1, 39)]
        rows += [matrix[first + 1][row] for row in range(1, 25)]
        footer = matrix[first + 1][25]
        if any(set(row) != set(range(1, 6)) for row in rows + [footer]):
            raise ValueError("Missing Worcester candidate/write-in/blank cell")
        observed = [sum(row[column] for row in rows) for column in range(1, 6)]
        expected = [footer[column] for column in range(1, 6)]
        if observed != expected:
            raise ValueError(f"Worcester {mode} precinct counts disagree with native footer")
        values[mode] = {precinct: [row[column] for column in range(1, 6)]
                        for precinct, row in zip(precincts, rows)}
        footers[mode] = expected
    for precinct in precincts:
        for column in range(5):
            observed = sum(values[mode][precinct][column] for mode in list(MODES.values())[1:])
            if observed != values["overall"][precinct][column]:
                raise ValueError(f"Worcester {precinct} candidate/mode counts disagree")
    return values, footers


def reviewed_inputs(root):
    originals = root / "sources"
    receipts = {}
    for path in sorted(originals.glob("*.receipt.json")):
        name = path.name.removesuffix(".receipt.json")
        receipt = json.loads(path.read_bytes())
        path = originals / name
        if receipt["sha256"] != digest(path) or receipt["bytes"] != path.stat().st_size:
            raise ValueError("Changed Worcester original source bytes")
        if name in (INDEX, PDF) and receipt["status"] != 200:
            raise ValueError("Failed Worcester original result source")
        receipts[name] = receipt
    declared = {urljoin(SOURCE, a["href"]) for a in
                BeautifulSoup((originals / INDEX).read_bytes(), "html.parser").find_all("a", href=True)}
    if (receipts[INDEX]["url"] != SOURCE or receipts[PDF]["url"] not in declared
            or receipts[PDF]["url"] != "https://www.worcesterma.gov/election-results/20261103.pdf"
            or receipts[PDF]["sha256"] != APPROVED_PDF):
        raise ValueError("Worcester PDF is not declared by actual official results index")
    review_root = root / "review"
    review = json.loads((review_root / "worcester-native-visual-review.json").read_bytes())
    if receipts[PDF]["sha256"] != review["source_pdf_sha256"]:
        raise ValueError("Visual judgments describe another Worcester source PDF")
    for name, key in [
        ("worcester-native-cell-review-manifest.json", "cell_review_manifest_sha256"),
        ("worcester-native-cell-review.png", "cell_review_image_sha256"),
    ]:
        if digest(review_root / name) != review[key]:
            raise ValueError("Changed visually reviewed Worcester evidence")
    for name, sha256 in review["identity_images"].items():
        if digest(review_root / name) != sha256:
            raise ValueError("Changed actual Worcester identity evidence")
    headers = json.loads((review_root / "worcester-native-governor-header-review.json").read_bytes())
    if (headers["source_pdf_sha256"] != APPROVED_PDF
            or headers["election_date"] != "2026-11-03"
            or headers["office"] != "GOVERNOR AND LIEUTENANT GOVERNOR"
            or headers["reporting_group_labels"] != [
                "ELECTION TOTALS - UNOFFICIAL", "ELECTION DAY- UNOFFICIAL",
                "EARLY VOTING #1- UNOFFICIAL", "EARLY VOTING #2- UNOFFICIAL"]
            or digest(review_root / "worcester-native-governor-panel-headers.png") != headers["image_sha256"]):
        raise ValueError("Unapproved Worcester election, office or reporting-group header evidence")
    document = fitz.open(originals / PDF)
    if len(document) != 60:
        raise ValueError("Incomplete Worcester source PDF")
    images = {}
    for page in [page + offset for page in MODES for offset in (0, 1)]:
        raster = document[page - 1].get_pixmap(matrix=fitz.Matrix(240 / 72, 240 / 72), alpha=False)
        image = Image.open(root / "images" / f"derived-worcester-page-{page:03}-240dpi.png").convert("RGB")
        if image.size != (2640, 2040) or image.tobytes() != raster.samples:
            raise ValueError("Worcester derivative pixels differ from complete original PDF")
        images[page] = image
    cells = root / "cells"
    tight = cells / "tight-crops"
    parents = json.loads((cells / "manifest.json").read_bytes())
    crops = json.loads((tight / "manifest.json").read_bytes())
    readings = [entry for path in sorted((tight / "independent-rapidocr").glob("ocr-*.json"))
                for entry in json.loads(path.read_bytes())]
    if (parents["source_pdf_sha256"] != review["source_pdf_sha256"]
            or crops["parent_manifest_sha256"] != digest(cells / "manifest.json")
            or len(parents["cells"]) != 1260 or len(crops["cells"]) != 1260
            or len(readings) != 1260):
        raise ValueError("Changed or incomplete Worcester crop inventory")
    for reading, parent, crop in zip(readings, parents["cells"], crops["cells"]):
        name = parent["file"]
        if (name != crop["file"] or name != reading["file"]
                or digest(cells / name) != parent["sha256"]
                or parent["sha256"] != crop["parent_sha256"]
                or digest(tight / name) != crop["sha256"]
                or digest(root / "images" / parent["source_image"]) != parent["source_image_sha256"]):
            raise ValueError("Changed Worcester source/crop bytes or identity")
        native = images[parent["source_page"]].convert("L").crop(parent["source_pixel_box"])
        native = ImageOps.expand(native.resize((native.width * 3, native.height * 3),
                                               Image.Resampling.LANCZOS), border=24, fill=255)
        actual = Image.open(cells / name).convert("L")
        if native.size != actual.size or native.tobytes() != actual.tobytes():
            raise ValueError("Worcester crop does not reproduce original PDF pixels")
        derived = ImageOps.expand(actual.crop(crop["parent_pixel_box"]), border=12, fill=255)
        actual = Image.open(tight / name).convert("L")
        if derived.size != actual.size or derived.tobytes() != actual.tobytes():
            raise ValueError("Tight Worcester crop altered native grayscale pixels")
    entries = json.loads((review_root / "worcester-native-cell-review-manifest.json").read_bytes())
    judgments = review["cell_values_in_explicit_review_index_order"]
    if len(entries) != len(judgments) or len(entries) != 35:
        raise ValueError("Incomplete explicit Worcester visual review")
    manual = {}
    for index, (entry, value) in enumerate(zip(entries, judgments), 1):
        if (entry["review"] != index or digest(tight / entry["file"]) != entry["tight_crop_sha256"]
                or entry["file"] in manual):
            raise ValueError("Changed or duplicate explicitly reviewed Worcester cell")
        manual[entry["file"]] = value
    return reconcile_counts(readings, manual, review["precinct_codes_read_in_actual_source_order"]), receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Never overwrite an immutable Worcester count review or archive")
    (values, footers), receipts = reviewed_inputs(args.input_root)
    rows = []
    for first, mode in MODES.items():
        for index, (precinct, counts) in enumerate(values[mode].items()):
            votes = sum(counts[:4])
            rows.append(dict(year=2026, state_code="MA", municipality="Worcester",
                precinct=precinct, office="Governor and lieutenant governor", reporting_group=mode,
                **dict(zip(COLUMNS, counts)), contest_votes=votes,
                contest_accounting_total=sum(counts),
                margin_pp=100 * (counts[0] - counts[1]) / votes if votes else None,
                source_page=first + (index >= 38), source_url=receipts[PDF]["url"],
                notes="Unofficial November 3 source. Reporting-group counts are not added to overall. "
                    "Candidate/write-in/blank accounting is not unique voters or turnout."))
    audit = dict(year=2026, state_code="MA", municipality="Worcester",
        office="Governor and lieutenant governor", complete="no",
        candidate_results="acquired_reconciled_city_subset", boundaries="correct_election_reference_pending",
        join="withheld", validation="counts_passed_map_withheld", publication="full_counts_download_only",
        participation="not_inferred_from_contest_counts", reporting_units=62, reporting_groups=4,
        result_rows=len(rows), source_count_cells=1260, source_pages=60,
        governor_panels=[page + offset for page in MODES for offset in (0, 1)],
        visually_reviewed_unknown_or_conflicting_cells=35,
        original_pdf_and_crop_pixels_reproduced=True, candidate_footers=footers,
        original_source_captures=len(receipts),
        original_source_bytes=sum(receipt["bytes"] for receipt in receipts.values()),
        original_source_receipts=receipts,
        precinct_candidate_mode_relations_verified=310, split_precincts_preserved=["4-2A", "7-5A"],
        source_url=SOURCE, source_pdf_url=receipts[PDF]["url"],
        source_pdf_sha256=receipts[PDF]["sha256"],
        complete_download_url=RELEASE + args.archive.name,
        notes="Worcester CITY ONLY, unofficial November 3, 2026 governor report: all 62 actual "
            "precinct identities and four reporting "
            "groups reconcile to their native candidate/write-in/blank footers, and all 310 "
            "precinct/candidate mode equations pass. The original 60-page PDF, native rasters, "
            "both local OCR readings, crop provenance and 35 explicit visual judgments are retained. "
            "Printed zeros are reviewed as zeros; missing OCR is never zero and letters are not "
            "deleted to obtain numbers. The city's declared election dashboard explicitly describes "
            "2025 municipal results, not this election; it is not repurposed as 2026 geometry. "
            "The 144,608 ballot-counter / 120,952 registration anomaly remains unexplained and unused. "
            "No registration denominator, unique-voter count, turnout, demographic rate or map "
            "is inferred. Massachusetts statewide coverage remains incomplete.",
        next_action="Obtain independently applicable 2026 precinct geometry and resolve split units "
            "before mapping; clarify actual ballot-card counter definitions. Preserve Boston's "
            "separate central-only mapped subset and do not replace it with a Worcester-only layer.")
    args.output.mkdir(parents=True)
    def save(name, raw):
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    inputs = {}
    bundle = io.BytesIO()
    with tarfile.open(fileobj=bundle, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for path in sorted(args.input_root.rglob("*")):
            if path.is_file():
                name = path.relative_to(args.input_root).as_posix()
                raw = path.read_bytes()
                inputs[name] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                item = tarfile.TarInfo(name)
                item.size = len(raw)
                item.mode = 0o644
                archive.addfile(item, io.BytesIO(raw))
    save("complete-inputs.tar.gz", gzip.compress(bundle.getvalue(), mtime=0))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    save("results.csv.gz", gzip.compress(stream.getvalue().encode(), mtime=0))
    save("audit.json", (json.dumps(audit, indent=2) + "\n").encode())
    save("inputs.json.gz", gzip.compress((json.dumps(inputs, indent=2) + "\n").encode(), mtime=0))
    save("review-worcester-precinct-results.py", Path(__file__).read_bytes())
    checksums = {path.relative_to(args.output).as_posix(): dict(bytes=path.stat().st_size,
                 sha256=digest(path)) for path in sorted(args.output.rglob("*")) if path.is_file()}
    save("checksums.json", (json.dumps(checksums, indent=2) + "\n").encode())
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                item = zipfile.ZipInfo(path.relative_to(args.output).as_posix(), (2026, 11, 5, 0, 0, 0))
                item.external_attr = 0o100644 << 16
                archive.writestr(item, path.read_bytes())
    print(json.dumps(dict(archive_bytes=args.archive.stat().st_size,
        archive_sha256=digest(args.archive), **audit)))


if __name__ == "__main__":
    main()
