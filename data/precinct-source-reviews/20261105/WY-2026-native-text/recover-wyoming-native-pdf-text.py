"""Recover archived Type3 text using directly reviewed, exact native glyph drawings."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

import fitz


def require(condition, message):
    if not condition:
        raise ValueError(message)


def font_characters(document, font, reviews):
    xref = font["font_xref"]
    require(document.xref_get_key(xref, "Subtype")[1] == "/Type3", "Expected native Type3 font")
    procedures = int(document.xref_get_key(xref, "CharProcs")[1].split()[0])
    encoding = int(document.xref_get_key(xref, "Encoding")[1].split()[0])
    match = re.search(r"/Differences\s*\[(.*?)\]", document.xref_object(encoding), re.S)
    require(match is not None, "Missing explicit native font encoding")
    codes, current = {}, None
    for token in re.findall(r"\d+|/[^\s\[\]]+", match[1]):
        if token.isdigit():
            current = int(token)
        else:
            require(current is not None and current not in codes, "Ambiguous native glyph code")
            codes[current] = token[1:]
            current += 1
    require(len(codes) == len(font["glyphs"])
            and codes == {g["code"]: g["glyph_name"] for g in font["glyphs"]},
            "Changed native font encoding")
    result = {}
    for glyph in font["glyphs"]:
        code = glyph["code"]
        require(0 <= code <= 255, "Unsupported native character code")
        ref = int(document.xref_get_key(procedures, glyph["glyph_name"])[1].split()[0])
        digest = hashlib.sha256(document.xref_stream(ref)).hexdigest()
        require(digest == glyph["drawing_sha256"], "Changed native glyph drawing")
        review = reviews.get(digest)
        require(review is not None and review.get("method") == "direct_native_glyph_render_review",
                "Missing exact native glyph review")
        character = review.get("character")
        require(isinstance(character, str) and len(character) == 1 and 32 <= ord(character) <= 126,
                "Missing or ambiguous reviewed character")
        result[code] = character
    return result


def recover_pdf(raw, record, reviews):
    require(hashlib.sha256(raw).hexdigest() == record["source_sha256"], "Changed reviewed PDF")
    with fitz.open(stream=raw, filetype="pdf") as document:
        actual = {f[0] for page in document for f in page.get_fonts() if f[2] == "Type3"}
        require(actual == {font["font_xref"] for font in record["fonts"]},
                "Missing or unexpected native font")
        mappings = [(font["font_xref"], font_characters(document, font, reviews))
                    for font in record["fonts"]]
        renders = [hashlib.sha256(page.get_pixmap().samples).hexdigest() for page in document]
        for font_xref, characters in mappings:
            lines = [f"<{code:02x}> <{ord(character):04x}>" for code, character in characters.items()]
            cmap = (
                "/CIDInit /ProcSet findresource begin 12 dict begin begincmap "
                "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def "
                "/CMapName /ReviewedNativeGlyphs def /CMapType 2 def "
                "1 begincodespacerange <00> <ff> endcodespacerange\n")
            for start in range(0, len(lines), 100):
                part = lines[start:start + 100]
                cmap += f"{len(part)} beginbfchar\n" + "\n".join(part) + "\nendbfchar\n"
            cmap += "endcmap CMapName currentdict /CMap defineresource pop end end"
            xref = document.get_new_xref()
            document.update_object(xref, "<<>>")
            document.update_stream(xref, cmap.encode())
            document.xref_set_key(font_xref, "ToUnicode", f"{xref} 0 R")
        result = fitz.open(stream=document.tobytes(), filetype="pdf")
    try:
        require([hashlib.sha256(page.get_pixmap().samples).hexdigest() for page in result] == renders,
                "Recovered metadata changed rendered source pixels")
    except Exception:
        result.close()
        raise
    return result, renders


def build_review(source, inventory_path, reviews_path, catalog_path, output, archive):
    require(not output.exists() and not archive.exists(), "Refusing immutable review overwrite")
    inventory = json.loads(inventory_path.read_text())
    reviews = json.loads(reviews_path.read_text())
    catalog = json.loads(catalog_path.read_text())
    require(len(reviews) == len(catalog) == 570, "Incomplete directly reviewed glyph catalog")
    for index, item in enumerate(catalog):
        require(item["review_index"] == index
                and reviews.get(item["drawing_sha256"], {}).get("review_index") == index,
                "Reviewed character does not match rendered catalog index")
        record = inventory[item["source"]]
        require(record["source_sha256"] == item["source_sha256"]
                and any(font["font_xref"] == item["font_xref"]
                        and any(all(glyph[key] == item[key]
                                    for key in ["code", "glyph_name", "drawing_sha256"])
                                for glyph in font["glyphs"])
                        for font in record["fonts"]), "Catalog source identity mismatch")
    checksums = json.loads((source / "checksums.json").read_text())
    require({p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
            == set(checksums) | {"checksums.json"}, "Incomplete original source package")
    for name, receipt in checksums.items():
        body = (source / name).read_bytes()
        require(len(body) == receipt["bytes"] and hashlib.sha256(body).hexdigest() == receipt["sha256"],
                "Changed original source package member")
    recovered, documents = {}, []
    for name, record in inventory.items():
        raw = gzip.decompress((source / "originals/2026" / (name + ".gz")).read_bytes())
        document, renders = recover_pdf(raw, record, reviews)
        with document:
            pages = [page.get_text() for page in document]
            require("November 3, 2026" in pages[0], "Recovered election identity mismatch")
            require(all(not any(ord(c) < 32 and c not in "\n\r\t" for c in text) for text in pages),
                    "Unrecovered control-character text")
            recovered[name + ".txt.gz"] = gzip.compress("\n\f\n".join(pages).encode(), mtime=0)
            recovered[name + ".words.json.gz"] = gzip.compress(json.dumps([
                dict(rotation=page.rotation, words=page.get_text("words")) for page in document
            ], separators=(",", ":"), ensure_ascii=True).encode(), mtime=0)
            documents.append(dict(source=name, source_sha256=record["source_sha256"],
                pages=len(pages), all_page_render_sha256=renders, every_page_render_byte_identical=True))
    require(len(documents) == 13 and sum(d["pages"] for d in documents) == 224,
            "Incomplete affected-document recovery")
    output.mkdir(parents=True)
    shutil.copytree(source, output / "source-package")
    for path, target in [(inventory_path, "glyph-inventory.json"), (reviews_path, "glyph-reviews.json"),
                         (catalog_path, "glyph-catalog.json")]:
        (output / target).write_bytes(path.read_bytes())
    for number in range(1, 7):
        image = catalog_path.parent / f"wyoming-native-unique-glyphs-{number:02}.png"
        (output / image.name).write_bytes(image.read_bytes())
    (output / "recovered-text").mkdir()
    for name, raw in recovered.items():
        (output / "recovered-text" / name).write_bytes(raw)
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    summary = dict(year=2026, state_code="WY", maps_approved=False, counts_reconciled=False,
        recovered_documents=documents, reviewed_drawing_hashes=570, recovered_pages=224,
        method="Direct native glyph render review; exact source and vector-drawing SHA-256; "
               "ToUnicode metadata only; every page renders byte-identically. No OCR or guessed counts.",
        erratum="The initial acquisition note misread Park's headers as Official. Fresh direct original "
                "render review and recovered text both say Unofficial in both Park documents, "
                "agreeing with banners and source index. Original package is retained unchanged.",
        next_action="Reconcile all 23 counties' House category vectors and separate ballot tables "
                    "to statewide summaries. Retain all native identifiers and reporting scopes; "
                    "acquire correct-election geometry before mapping. No turnout denominator inferred.")
    (output / "recovery.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "checksums.json").write_text(json.dumps({
        path.relative_to(output).as_posix(): dict(bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(output.rglob("*")) if path.is_file()
    }, separators=(",", ":")))
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as target:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                item = zipfile.ZipInfo(path.relative_to(output).as_posix())
                item.external_attr = 0o644 << 16
                target.writestr(item, path.read_bytes())
    return dict(recovered_documents=13, recovered_pages=224, maps_approved=False,
        archive_bytes=archive.stat().st_size, archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["source", "inventory", "reviews", "catalog", "output", "archive"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_review(args.source, args.inventory, args.reviews,
        args.catalog, args.output, args.archive), indent=2))
