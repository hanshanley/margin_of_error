"""Freeze only new Nashua/Dover inputs while preserving every first-release input byte."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import fitz


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-new-hampshire-cities-02"
PRIOR = "data/county-source-reviews/20261110-new-hampshire-cities-01/inputs.json"


def build(source):
    target = ROOT / VERSION
    if target.exists():
        raise ValueError("Refuse to replace an immutable city extension input version")
    prior = json.loads((ROOT / PRIOR).read_bytes())
    files = dict(prior["files"])
    originals = dict(prior["originals"])
    target.mkdir(parents=True)

    def receipt(body):
        return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())

    def copy(old, relative):
        body = old.read_bytes()
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(old, path)
        name = path.relative_to(ROOT).as_posix()
        files[name] = receipt(body)
        return name

    files[PRIOR] = receipt((ROOT / PRIOR).read_bytes())
    for name in ["nashua-20261103-original.pdf", "dover-20261103-native-turnout-original.pdf"]:
        native = json.loads((source / (name + ".receipt.json")).read_bytes())
        body = (source / name).read_bytes()
        if native["status"] != 200 or receipt(body) != {key: native[key] for key in ["bytes", "sha256"]}:
            raise ValueError("Changed complete native city original")
        copy(source / name, "originals/" + name)
        originals[name] = {key: native[key] for key in [
            "url", "final_url", "status", "bytes", "sha256", "retrieved_at_utc"]}
    readings = {city: copy(source / f"{city}-native-participation-readings-01.json",
                           city + "-native-readings.json") for city in ["nashua", "dover"]}
    crop_receipts = []
    document = fitz.open(source / "nashua-20261103-original.pdf")
    for ward, native_page in enumerate([1, 7, 9, 11, 14, 19, 22, 24, 26], 1):
        header_path = target / f"visual-evidence/nashua-ward{ward:02d}-header.png"
        header_path.parent.mkdir(parents=True, exist_ok=True)
        box = fitz.Rect(0, 0, document[native_page - 1].rect.width, 170)
        document[native_page - 1].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), clip=box,
                                             alpha=False).save(header_path)
        header_name = header_path.relative_to(ROOT).as_posix()
        files[header_name] = receipt(header_path.read_bytes())
        block_name = copy(source / f"nashua-ward{ward:02d}-ballot-band-300dpi.private.png",
                          f"visual-evidence/nashua-ward{ward:02d}-ballot-block.png")
        crop_receipts.append(dict(ward=ward, native_page=native_page, clips=[
            dict(path=header_name, native_pdf_box=list(box), render_scale=1.5),
            dict(path=block_name, native_pdf_box=[0,170,document[native_page-1].rect.width,285],
                 render_scale=300/72)]))
    copy(source / "dover-native-turnout-page01-160dpi.private.png",
         "visual-evidence/dover-native-turnout-page01.png")
    safe_declarations = dict(
        nashua=json.loads((source / "nashua-declared-general-link.json").read_bytes()),
        dover=json.loads((source / "dover-canonical-www-declared-turnout-links.json").read_bytes()),
        dover_index_receipt=json.loads((source / "dover-canonical-www-general-index.private.html.receipt.json").read_bytes()))
    for name, value in [("native-crop-receipts.json", dict(
        original_pdf_sha256=originals["nashua-20261103-original.pdf"]["sha256"], records=crop_receipts)),
        ("safe-source-declarations.json", safe_declarations)]:
        body = (json.dumps(value, indent=2) + "\n").encode()
        path = target / name
        path.write_bytes(body)
        files[path.relative_to(ROOT).as_posix()] = receipt(body)
    reference = dict(prior["reference"], mapped_localities=4,
                     review_id="new-hampshire-native-cities-20261110-02")
    inputs = dict(version=VERSION, prior_inputs_path=PRIOR, files=files, originals=originals,
        readings_paths=readings, reference=reference, certified_election_boundaries=False,
        analysis_rates_approved=False, native_ballot_and_register_percentages_separate=True,
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-new-hampshire-native-cities-20261110-02/complete-analysis.zip")
    (target / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    print(json.dumps(dict(sufficient_input_files=len(files), original_pdfs=len(originals),
        complete_original_bytes=sum(row["bytes"] for row in originals.values()),
        prior_inputs_preserved=True, unchanged_full_reference_sha256=reference["sha256"],
        new_cities=2, all_cities=4, unknown_contextual_areas=255)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    build(parser.parse_args().source)
