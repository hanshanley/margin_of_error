"""Freeze already-held permitted Alaska inputs; do not acquire or repair source data."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("alaska_display", ROOT / "scripts/alaska-native-display.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def build(files):
    target = ROOT / core.VERSION
    if target.exists():
        raise ValueError("Refuse to replace immutable Alaska inputs")
    old = ROOT / "data/precinct-boundary-reviews/20261105/AK/count-review"
    sources = {f"originals/{p.name}": p for p in (old / "originals").iterdir() if p.is_file()}
    sources.update({
        "original-source-receipts.json": old / "sources.json",
        "qualified-source-count-queries.json.gz":
            ROOT / "data/precinct-source-reviews/20261105/AK/participation.json.gz",
        "prior-count-review.json": old / "audit.json",
        "held-topology-queries.json": files / "alaska-native-delta-topology-review-01.json",
        "independent-integer-coordinates.json": files / "alaska-delta-integer-decoder-01.json",
        "independent-decoder-agreement.json": files / "alaska-native-delta-independent-decoder-01.json",
        "native-display-format-facts.json": files / "alaska-native-display-format-facts-01.json",
    })
    if len([name for name in sources if name.startswith("originals/")]) != 6:
        raise ValueError("Incomplete already-held source originals")
    pins = {}
    for name, source in sources.items():
        body = source.read_bytes()
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, path)
        pins[str(path.relative_to(ROOT))] = dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    inputs = dict(snapshot=core.SNAPSHOT, source_url=core.SOURCE,
        complete_download_url=core.DOWNLOAD, source_election="Alaska 2026 General Election",
        geometry_scope="valid_unrepaired_single_path_native_app_reference_subset",
        certified_legal_boundaries=False, counts_allocated=False, rates_approved=False, files=pins)
    (target / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    data = core.load()
    print(json.dumps(data["summary"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=Path, required=True)
    build(parser.parse_args().files)
