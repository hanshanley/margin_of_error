"""Verify migrated queries with the original frozen Python intake contract."""

import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path


def verify(runtime, contract_file):
    runtime, contract_file = Path(runtime), Path(contract_file)
    spec = importlib.util.spec_from_file_location("frozen_contract", contract_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    index = json.loads((runtime / "index.json").read_bytes())
    counts = dict(records=0, zeros=0, unknown=0, withheld=0)
    dispositions = {}
    seen = set()
    for code, declaration in index["states"].items():
        body = (runtime / declaration["file"]).read_bytes()
        assert len(body) == declaration["bytes"]
        assert hashlib.sha256(body).hexdigest() == declaration["sha256"]
        data = json.loads(gzip.decompress(body))
        module.validate_all(data["records"])
        for row in data["records"]:
            assert row["id"] not in seen
            seen.add(row["id"])
            assert row["view"] == row["source"]["fields"]
            counts["records"] += 1
            counts["zeros"] += row["count"]["value"] == 0
            counts["unknown"] += row["count"]["status"] == "unknown"
            counts["withheld"] += row["count"]["status"] == "withheld"
            if row["count"]["value"] is None:
                native = row["view"].get("native_record") or {}
                disposition = str((code, native.get("source_scope_review"), row["view"].get("count_status")))
                dispositions[disposition] = dispositions.get(disposition, 0) + 1
    return dict(status="PASS_all_records_original_frozen_Python_contract",
        contract_sha256=hashlib.sha256(contract_file.read_bytes()).hexdigest(),
        **counts, retained_missing_dispositions=dispositions)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("contract", type=Path)
    parser.add_argument("proof", type=Path)
    args = parser.parse_args()
    result = verify(args.runtime, args.contract)
    args.proof.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
