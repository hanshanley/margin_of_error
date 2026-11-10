"""Prepare the exact complete county query once, without network access."""

import gzip
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nevada", ROOT / "scripts/nevada-native-counties.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
directory = ROOT / core.VERSION
target = directory / "queries.json.gz"
if target.exists():
    raise ValueError("Never replace an existing prepared native query")
data = core.load()
body = gzip.compress(core.encoded(data), mtime=0)
target.write_bytes(body)
(directory / "summary.json").write_bytes(core.encoded(data["summary"]))
print(json.dumps(dict(status="PASS_complete_query_prepared", **core.pin(body), summary=data["summary"])))
