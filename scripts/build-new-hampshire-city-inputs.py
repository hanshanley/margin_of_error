"""Freeze actual declared city originals/readings and the held full municipality context."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-new-hampshire-cities-01"
PUBLIC = "public/participation-city-counts/20261110-new-hampshire-01"


def build(source):
    target, public = ROOT / VERSION, ROOT / PUBLIC
    if target.exists() or public.exists():
        raise ValueError("Refuse to replace an immutable NH city input version")
    sections = json.loads((source / "manchester-results-index-declared-2026-links.json").read_bytes())
    section = next(r for r in sections if r["native_heading"] == "November 3, 2026 State General Election")
    links = {int(row["text"].split()[-1]): row["url"] for row in section["declared_links"]}
    if set(links) != set(range(1, 13)):
        raise ValueError("Incomplete actual declared general-election ward set")
    files, originals = {}, {}
    def copy(old, relative):
        body = old.read_bytes()
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(old, path)
        name = str(path.relative_to(ROOT))
        files[name] = dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        return name
    for ward in range(1, 13):
        name = f"manchester-ward{ward:02d}-20261103-original"
        receipt = json.loads((source / (name + ".receipt.json")).read_bytes())
        path = source / (name + ".pdf")
        if (receipt["status"] != 200 or receipt["url"] != links[ward]
                or path.stat().st_size != receipt["bytes"]
                or hashlib.sha256(path.read_bytes()).hexdigest() != receipt["sha256"]):
            raise ValueError("Changed or undeclared native Manchester original")
        copy(path, "originals/" + name + ".pdf")
        originals[name + ".pdf"] = dict(receipt, declared_ward=ward, native_election_date="2026-11-03")
        for field in ("header", "ballot_block"):
            copy(source / f"manchester-ward{ward:02d}-{field}.private.png",
                 f"visual-evidence/manchester-ward{ward:02d}-{field}.png")
    name = "concord-20261103-original"
    receipt = json.loads((source / (name + ".receipt.json")).read_bytes())
    body = (source / (name + ".pdf")).read_bytes()
    if (receipt["status"] != 200 or receipt["url"] != "https://www.concordnh.gov/Archive.aspx?ADID=9722"
            or len(body) != receipt["bytes"] or hashlib.sha256(body).hexdigest() != receipt["sha256"]):
        raise ValueError("Changed actual Concord general-election source")
    copy(source / (name + ".pdf"), "originals/" + name + ".pdf")
    originals[name + ".pdf"] = dict(receipt, native_election_date="2026-11-03")
    for ward in (4, 6, 7):
        copy(source / f"manchester-ward{ward:02d}-ballot-block-300dpi.private.png",
             f"visual-evidence/manchester-ward{ward:02d}-ballot-block-300dpi.png")
    copy(source / "concord-general-page04-130dpi.private.png", "visual-evidence/concord-native-page04-130dpi.png")
    copy(source / "manchester-all12-native-ballot-band-receipts.json", "visual-evidence/original-crop-receipts.json")
    readings = copy(source / "native-participation-readings-01.json", "native-readings.json")
    reference = ROOT / "data/participation-local/20261104T220000Z-identity-audit/geometry/2024/municipality-NH.geojson.gz"
    reference_path = copy(reference, "original-municipality-NH-2024.geojson.gz")
    data = reference.read_bytes()
    if hashlib.sha256(data).hexdigest() != "b74e8b9c197371af4f093dbdc2916cb18aaa1bc2ff498e2f875642f2f7e5fdee":
        raise ValueError("Changed full held NH municipality reference")
    indexes = {}
    for city, name in [("manchester", "manchester-results-index"), ("concord", "concord-results-archive")]:
        r = json.loads((source / (name + ".receipt.json")).read_bytes())
        indexes[city] = {k: r[k] for k in ["url", "final_url", "status", "bytes", "sha256", "retrieved_at_utc"]}
    inputs = dict(version=VERSION, files=files, originals=originals, indexes=indexes,
        declared_manchester_general_ward_links=section, readings_path=readings,
        certified_election_boundaries=False, analysis_rates_approved=False,
        reference=dict(path=reference_path,
            url="/participation-city-counts/20261110-new-hampshire-01/NH.geojson.gz",
            sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), boundary_year=2024,
            localities=259, mapped_localities=2, identity_field="key",
            geography_scope="native_partial_city_reporting_context",
            review_id="new-hampshire-native-cities-20261110-01", certified_election_boundaries=False),
        complete_download_url="https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-new-hampshire-native-cities-20261110-01/complete-analysis.zip")
    (target / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    public.mkdir(parents=True)
    shutil.copyfile(reference, public / "NH.geojson.gz")
    print(json.dumps(dict(original_pdfs=len(originals),
        complete_original_bytes=sum(r["bytes"] for r in originals.values()),
        sufficient_input_files=len(files), context_areas=259, contextual_cities=2,
        geometry_repaired=False, source_errors_repaired=False)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    build(parser.parse_args().source)
