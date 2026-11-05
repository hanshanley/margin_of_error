"""Reconcile Boston's 2026 central-tabulation subset, never combined results or turnout."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
from urllib.parse import parse_qs, urljoin, urlparse
import zipfile

import fitz
from bs4 import BeautifulSoup
from shapely.geometry import shape
from shapely.strtree import STRtree


SOURCE = "https://www.boston.gov/departments/elections/unofficial-election-results"
APP = "https://experience.arcgis.com/experience/30b1667d4997442795ae4096b825bc19"
LAYER_ITEM = "8ae9900f3a394baeb490642f62c5f85b"
NAMES = ("HEALEY AND DRISCOLL", "MINOGUE AND OLIVER", "JAMES AND KITTREDGE")
LABELS = (*NAMES, "Total number of write-ins", "Times Blank Voted", "Total Ballots")
SCOPE = "Central Tabulation advanced processing only; NOT combined election results"
TOLERANCE = 1e-10


def page_counts(page):
    text = page.get_text()
    if not all(s in text for s in ("UNOFFICIAL BOSTON STATE", "ELECTION NOVEMBER 2026",
                                   "(CENTRAL TABULATION)", "GOVERNOR & LIEUTENANT")):
        raise ValueError("Wrong Boston election, contest or ballot mode")
    if page.rect.width != 1008 or page.rect.height != 612:
        raise ValueError("Unknown Boston PDF grid")
    words = page.get_text("words")
    starts = [w[1] for w in words if w[4] == "HEALEY" and w[0] < 180]
    if len(starts) != 1:
        raise ValueError("Missing or repeated Boston governor rows")
    grouped = {}
    for w in words:
        if w[0] < 180 and starts[0] - .2 <= w[1] < starts[0] + 85:
            y = next((y for y in grouped if abs(y - w[1]) < .2), w[1])
            grouped.setdefault(y, []).append(w)
    rows = sorted(grouped.items())
    if [" ".join(w[4] for w in sorted(ws)) for _, ws in rows] != list(LABELS):
        raise ValueError("Wrong or missing Boston governor accounting row")
    records, empty_seen = [], False
    for column in range(16):
        left, right = 185.6 + column * 49.2, 234.8 + column * 49.2
        header_words = sorted((w for w in words
                               if left < (w[0] + w[2]) / 2 < right and 150 < w[1] < 205),
                              key=lambda w: (w[1], w[0]))
        header = " ".join(w[4] for w in header_words)
        match = re.fullmatch(r"WARD ([1-9][0-9]*), PRECINCT ([1-9][0-9]*)", header)
        values = []
        for y, _ in rows:
            # Native label/count fonts have a 0.36-point bbox offset within each 14.5-point row.
            cells = [w[4] for w in words if left < (w[0] + w[2]) / 2 < right
                     and abs(w[1] - y) < 1]
            if not header:
                if cells:
                    raise ValueError("Boston values lack a precinct header")
                continue
            if len(cells) != 1 or not re.fullmatch(r"[0-9]+", cells[0]):
                raise ValueError(f"Missing/noninteger Boston {header}, "
                                 f"{LABELS[len(values)]}: {cells}; not zero")
            values.append(int(cells[0]))
        if not header:
            empty_seen = True
            continue
        if empty_seen or not (match or header == "TOTAL"):
            raise ValueError("Unknown or discontinuous Boston column identity")
        if sum(values[:5]) != values[5]:
            raise ValueError("Boston candidate/write-in/blank accounting differs from ballots")
        code = f"{int(match[1]):02}-{int(match[2]):02}" if match else "TOTAL"
        records.append(dict(precinct_code=code, values=values))
    if not records:
        raise ValueError("Empty Boston precinct page")
    return records


def review_pdf(raw):
    document = fitz.open(stream=raw, filetype="pdf")
    records, totals, pages = {}, [], []
    for index, page in enumerate(document):
        if NAMES[0] not in page.get_text():
            continue
        pages.append(index + 1)
        for record in page_counts(page):
            code = record["precinct_code"]
            if code == "TOTAL":
                totals.append(record["values"])
            elif code in records:
                raise ValueError("Duplicate Boston precinct")
            else:
                records[code] = dict(record, source_page=index + 1)
    if len(records) != 275 or len(totals) != 1 or len(pages) != 18 or len(document) != 288:
        raise ValueError("Incomplete Boston precinct inventory or complete PDF")
    observed = [sum(r["values"][i] for r in records.values()) for i in range(6)]
    if observed != totals[0]:
        raise ValueError("Boston precinct sums disagree with native city footer")
    return records, dict(source_pages=len(document), governor_pages=pages,
                         candidate_totals=dict(zip(NAMES, observed[:3])),
                         write_in_votes=observed[3], blank_votes=observed[4],
                         central_tabulation_ballots=observed[5])


def party_evidence(ocr):
    page = ocr[0]
    lines = [line["candidates"][0]["text"] for line in page["lines"]]
    if ("11/03/2026 STATE ELECTION" not in lines
            or "GOVERNOR AND LIEUTENANT GOVERNOR" not in lines):
        raise ValueError("Wrong independent Massachusetts party-evidence election/office")
    evidence = {}
    for line in page["lines"]:
        candidate = line["candidates"][0]
        match = re.fullmatch(r"(.+) \((DEM|REP|IND)\)(?: \.)?", candidate["text"])
        if match and match[1] in NAMES:
            if (match[1] in evidence or candidate["confidence"] < .99
                    or not (.02 < line["bounds"][0] < .05
                            and .24 < line["bounds"][1] < .30)):
                raise ValueError("Ambiguous independent native ticket-party evidence")
            evidence[match[1]] = dict(party=match[2], native_label=candidate["text"],
                                     source_page=1, bounds=line["bounds"])
    if set(evidence) != set(NAMES) or {e["party"] for e in evidence.values()} != {"DEM", "REP", "IND"}:
        raise ValueError("Missing explicit native ticket-party labels; never infer from names")
    return evidence


def mapped_precincts(records, reference, inventory, evidence):
    features = reference["features"]
    field = inventory["objectIdFieldName"]
    ids = inventory["objectIds"]
    if (reference.get("exceededTransferLimit") or inventory.get("exceededTransferLimit")
            or len(ids) != len(set(ids)) or len(ids) != len(features)
            or {f["properties"][field] for f in features} != set(ids)):
        raise ValueError("Incomplete or duplicate Boston native reference IDs")
    mapped, rows, seen = [], [], set()
    for feature in features:
        p = feature["properties"]
        code = p["DISTRICT"]
        if (code not in records or code in seen
                or not re.fullmatch(r"[0-9]{2}-[0-9]{2}", code)
                or p["Ward_and_Precinct"] != code
                or p["Ward"] + "-" + p["Precinct"] != code
                or p["WDPCT"] != p["Ward"] + p["Precinct"]
                or int(p["Ward"]) != p["Ward_1787082447332"]
                or int(p["Precinct"]) != int(p["Precinct_1787082447332"])):
            raise ValueError("Conflicting, missing or duplicate Boston precinct identity")
        geometry = shape(feature["geometry"])
        if (geometry.is_empty or not geometry.is_valid
                or geometry.geom_type not in {"Polygon", "MultiPolygon"}
                or geometry.area <= 0 or not all(math.isfinite(v) for v in geometry.bounds)
                or not (-71.3 < geometry.bounds[0] <= geometry.bounds[2] < -70.6
                        and 42.1 < geometry.bounds[1] <= geometry.bounds[3] < 42.5)):
            raise ValueError("Invalid or wrongly projected Boston precinct reference")
        record = records[code]
        candidates = dict(zip(NAMES, record["values"][:3]))
        votes = {evidence[name]["party"]: value for name, value in candidates.items()}
        dem, rep = votes["DEM"], votes["REP"]
        total = sum(record["values"][:4])
        row = dict(key=f"MA-25025-BOSTON-{code}", year=2026, state_code="MA",
            county_code="25025", county="Suffolk", municipality="Boston",
            precinct_code=code, precinct=f"Boston Ward {int(p['Ward'])}, Precinct {int(p['Precinct'])}",
            office="Governor and lieutenant governor", source_page=record["source_page"],
            source_url=SOURCE, source_reporting_status="Unofficial central tabulation only",
            democratic_votes=dem, republican_votes=rep,
            other_votes=votes["IND"] + record["values"][3], contest_votes=total,
            dem_pct=dem / total * 100 if total else None,
            rep_pct=rep / total * 100 if total else None,
            margin_pp=(dem - rep) / total * 100 if total else None,
            ballots=record["values"][5], blank_votes=record["values"][4],
            write_in_votes=record["values"][3], ballot_scope=SCOPE)
        provenance = ("The November 3, 2026 Boston polling page embeds the official lookup app. "
            "Its selected polygon layer popups explicitly name that general-election date. "
            "Legacy service title says Preliminary and webmap description says Fall 2025; "
            "both are preserved. App-selected reference, not newly surveyed/certified 2026 "
            "boundaries or proof of cross-election stability.")
        properties = dict(row, match_status="matched", official_boundary=True,
            source_object_ids=[p[field]], boundary_date="2026 general-election app-selected reference",
            boundary_provenance=provenance,
            quality_flags="unofficial;central_tabulation_only;no_registration_or_turnout")
        mapped.append(dict(type="Feature", properties=properties, geometry=feature["geometry"]))
        rows.append(row)
        seen.add(code)
    if seen != set(records):
        raise ValueError("Complete Boston candidate/reference precinct sets differ")
    polygons = [shape(f["geometry"]) for f in mapped]
    tree = STRtree(polygons)
    for i, polygon in enumerate(polygons):
        for j in tree.query(polygon, predicate="intersects"):
            if j > i and polygon.intersection(polygons[j]).area > TOLERANCE:
                raise ValueError("Ambiguous Boston precinct overlap; do not allocate or repair")
    return sorted(rows, key=lambda r: r["precinct_code"]), mapped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cache-root", "output", "archive"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.archive.exists():
        raise ValueError("Refusing to overwrite an immutable Boston snapshot")
    sources, originals = {}, {}
    for path in sorted(args.cache_root.glob("official-*")):
        if path.name.endswith(".receipt.json") or not path.is_file():
            continue
        raw = path.read_bytes()
        receipt = json.loads(path.with_name(path.name + ".receipt.json").read_bytes())
        if (receipt["bytes"] != len(raw) or receipt["sha256"] != hashlib.sha256(raw).hexdigest()
                or receipt["status"] not in {200, 403}):
            raise ValueError("Changed original or unexpected acquisition status: " + path.name)
        sources[path.name], originals[path.name] = receipt, raw

    def native(name):
        if sources[name]["status"] != 200:
            raise ValueError("Failed source cannot supply Boston counts or geometry")
        return json.loads(originals[name])

    index = originals["official-boston-unofficial-results.html"].decode()
    declared = {urljoin(SOURCE, a["href"])
                for a in BeautifulSoup(index, "html.parser").find_all("a", href=True)}
    pdf_name = "official-boston-declared-2026-central-tabulation-results.pdf"
    if (sources["official-boston-unofficial-results.html"]["url"] != SOURCE
            or sources["official-boston-unofficial-results.html"]["status"] != 200
            or sources[pdf_name]["status"] != 200
            or not sources[pdf_name]["url"].startswith(
                "https://www.boston.gov/sites/default/files/file/2026/11/")
            or sources[pdf_name]["url"] not in declared):
        raise ValueError("Boston PDF is not declared by the acquired official index")
    webmap = native("official-boston-observed-reference-response-008.json")
    layers = [l for l in webmap["operationalLayers"] if l.get("itemId") == LAYER_ITEM]
    if (len(layers) != 1 or "Tuesday, November 3, 2026" not in json.dumps(layers[0]["popupInfo"])
            or APP not in originals["official-boston-2026-polling-locations.html"].decode()
            or native("official-boston-observed-reference-response-021.json")["geometryType"]
            != "esriGeometryPolygon"):
        raise ValueError("Missing independent general-election reference applicability")
    layer_url = layers[0]["url"]
    if (not layer_url.startswith("https://services.arcgis.com/sFnw0xNflSi8J0uh/")
            or sources["official-boston-observed-reference-response-021.json"]["url"].split("?")[0]
            != layer_url):
        raise ValueError("Reference metadata does not describe the app-selected Boston layer")
    for name, parameters in [
        ("official-boston-app-selected-reference-objectids.json",
         dict(f=["json"], where=["1=1"], returnIdsOnly=["true"])),
        ("official-boston-app-selected-reference.geojson",
         dict(f=["geojson"], where=["1=1"], outFields=["*"], outSR=["4326"],
              returnGeometry=["true"])),
    ]:
        url = sources[name]["url"]
        if url.split("?")[0] != layer_url + "/query" or parse_qs(urlparse(url).query) != parameters:
            raise ValueError("Incomplete or wrong-layer native Boston reference query")
    ocr_path = args.cache_root / "derived-worcester-all-pages-native-vision-ocr.json"
    ocr_receipt = json.loads(ocr_path.with_name(ocr_path.stem + ".receipt.json").read_bytes())
    if (ocr_receipt["ocr_sha256"] != hashlib.sha256(ocr_path.read_bytes()).hexdigest()
            or ocr_receipt["source_sha256"]
            != sources["official-worcester-declared-2026-general-results.pdf"]["sha256"]):
        raise ValueError("Changed independent original/derived ticket-party evidence")
    ocr = json.loads(ocr_path.read_bytes())
    evidence = party_evidence(ocr)
    for page in ocr:
        page["image"] = Path(page["image"]).name
    public_ocr = json.dumps(ocr, separators=(",", ":"), ensure_ascii=True).encode()
    public_ocr_receipt = dict(ocr_receipt,
        original_ocr_sha256=ocr_receipt.get("original_ocr_sha256", ocr_receipt["ocr_sha256"]),
        ocr_sha256=hashlib.sha256(public_ocr).hexdigest(),
        image_identifiers="Basenames only; session paths removed. All OCR counts remain unverified.")
    records, audit = review_pdf(originals[pdf_name])
    rows, mapped = mapped_precincts(records,
        native("official-boston-app-selected-reference.geojson"),
        native("official-boston-app-selected-reference-objectids.json"), evidence)
    audit.update(year=2026, state_code="MA", municipality="Boston", complete="no",
        ballot_scope=SCOPE, mapped_precincts=len(mapped),
        combined_precinct_results_acquired=False, registration_denominators_acquired=False,
        final_turnout_rates=0, demographic_rates=0, rates_available=0,
        candidate_party_evidence=evidence,
        party_evidence_source="official-worcester-declared-2026-general-results.pdf, page 1; "
            "only the visually checked explicit ticket-party labels are used, NOT Worcester counts",
        reference_features=len(mapped), distinct_precinct_overlaps=0,
        overlap_tolerance_degrees_squared=TOLERANCE, topology_repairs=[],
        original_files=len(originals), original_bytes=sum(map(len, originals.values())),
        failed_source_observations=[name for name, r in sources.items() if r["status"] != 200])
    notes = ("BOSTON CENTRAL TABULATION ONLY: advanced-processed early/mail governor votes, "
        "NOT combined Election Day results, all-mode margins or statewide Massachusetts coverage. "
        "All 275 precinct counts and write-in/blank accounting reconcile to the native city footer. "
        "The separate combined citywide HTML is not allocated to these precincts. No registration "
        "denominator, turnout fraction or demographic participation is inferred. Worcester's "
        "complete report supplies only independently visually checked explicit ticket-party labels; "
        "its counts and ballot-counter anomaly are not used for Boston. The actual November 3, "
        "2026 polling-page app selects these polygons and its popups explicitly name that date. "
        "Legacy Preliminary service title and Fall 2025 webmap metadata remain documented: "
        "this is an app-selected reference, not newly surveyed/certified 2026 boundaries. "
        "All complete original documents, native reference and acquisition failures are downloadable.")
    args.output.mkdir(parents=True)

    def save(name, value):
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
        path.write_bytes(gzip.compress(body, mtime=0) if name.endswith(".gz") else body)

    for name, raw in originals.items():
        path = args.output / "originals" / (name + ".gz")
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(gzip.compress(raw, mtime=0))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (args.output / "results.csv.gz").write_bytes(gzip.compress(stream.getvalue().encode(), mtime=0))
    save("2026/MA.geojson.gz", dict(type="FeatureCollection", features=mapped))
    save("party-evidence.json", dict(source_pdf="official-worcester-declared-2026-general-results.pdf",
        source_pdf_sha256=ocr_receipt["source_sha256"], source_page=1,
        source_ocr_lines=[line for line in ocr[0]["lines"]
                          if any(name in line["candidates"][0]["text"] for name in NAMES)],
        verification="Only complete ticket-party labels visually checked against original page 1; "
            "no OCR candidate counts, ballot counts or participation rates approved."))
    save("derived/" + ocr_path.name + ".gz", ocr)
    save("derived/" + ocr_path.stem + ".receipt.json", public_ocr_receipt)
    save("audit.json", audit)
    save("sources.json", sources)
    save("index.json", dict(coverage={"2026": {"MA": dict(file="2026/MA.geojson.gz",
        source_url=SOURCE, boundary_source=layers[0]["url"], partial=True,
        features=len(mapped), colored=sum(r["contest_votes"] > 0 for r in rows),
        office="Governor and lieutenant governor (Boston central tabulation ONLY)",
        notes=notes, boundary_date="2026 general-election app-selected reference",
        participation="central_tabulation_ballot_counts_only_no_registration_or_rates",
        next_action="Acquire combined all-mode Boston precinct returns and other Massachusetts "
            "municipalities; independently reconcile Worcester OCR/modes and ballot counters; "
            "seek unique-person participation and actual group denominators.")}},
        result_rows=len(rows), participation_rows=0, complete_download=args.archive.name,
        metric=notes))
    save("checksums.json", {str(p.relative_to(args.output)): dict(bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(args.output.rglob("*")) if p.is_file()})
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "x", compression=zipfile.ZIP_STORED) as archive:
        for p in sorted(args.output.rglob("*")):
            if p.is_file():
                item = zipfile.ZipInfo(str(p.relative_to(args.output)), (2026, 11, 5, 0, 0, 0))
                item.external_attr = 0o100644 << 16
                archive.writestr(item, p.read_bytes())
    print(json.dumps(dict(archive_bytes=args.archive.stat().st_size,
        archive_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest(), **audit)))


if __name__ == "__main__":
    main()
