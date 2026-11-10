"""Prepare one immutable native-statistics query; never reacquire or overwrite."""

import gzip
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mn_followup", ROOT / "scripts/minnesota-followup.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
source = ROOT / core.VERSION
target = source / "queries.json.gz"
if target.exists():
    raise ValueError("Never replace an existing prepared native query")
data = core.load()
body = gzip.compress(core.encoded(data), mtime=0)
target.write_bytes(body)
(source / "summary.json").write_text(json.dumps(data["summary"], indent=2) + "\n")
print(json.dumps(dict(status="PASS_prepared_native_query_NOT_website_acceptance",
    bytes=len(body), sha256=core.digest(body), summary=data["summary"])))
