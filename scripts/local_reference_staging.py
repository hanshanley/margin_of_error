"""Stage only an unpublished, checksum-pinned new reference in loopback browser tests."""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse


def stage_local_minnesota_reference(context, base_url, root=None):
    if urlparse(base_url).hostname not in ("127.0.0.1", "localhost"):
        return False
    root = root or Path(__file__).resolve().parents[1]
    index = root / "public/participation-precincts/20261110-minnesota-followup-02/index.json"
    if not index.exists():
        return False
    data = json.loads(index.read_bytes())
    path = root / "data/county-source-reviews/20261110-minnesota-followup-02/MN.geojson.gz"
    body = path.read_bytes()
    pin = data["state_metadata"]["MN"]
    if len(body) != pin["bytes"] or hashlib.sha256(body).hexdigest() != pin["sha256"]:
        raise ValueError("The unpublished local reference differs from the exact future artifact")
    context.route(data["states"]["MN"], lambda route: route.fulfill(
        status=200, content_type="application/gzip", body=body))
    return True
