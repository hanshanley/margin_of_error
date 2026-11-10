"""Complete public aggregate ArcGIS queries with counts and stable pagination."""

import json
from pathlib import Path
import urllib.parse

from .contract import IntakeError, encoded, pin
from .engine import Store


def retained_acquire(store, description, receipt_path):
    receipt_path = Path(receipt_path)
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_bytes())
        body = (store.root / "objects" / receipt["sha256"]).read_bytes()
        if pin(body) != {key: receipt[key] for key in ("bytes", "sha256")}:
            raise IntakeError("cache_corruption", "A retained complete query differs")
        if receipt["url"] != description["url"]:
            raise IntakeError("source_url", "A retained query belongs to another request")
        return body, receipt
    body, receipt = store.acquire(description)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_bytes(encoded(receipt))
    return body, receipt


def checked_json(body):
    data = json.loads(body)
    if "error" in data:
        raise IntakeError("source_api_error", "Public query returned an error, not empty observations: "
            + str(data["error"].get("message")))
    return data


def aggregate_query(spec, root):
    store = Store(root)
    root = Path(root)
    receipts = []
    try:
        def acquire(name, parameters):
            url = spec["url"] + "/query?" + urllib.parse.urlencode(parameters)
            body, receipt = retained_acquire(store, dict(url=url,
                allowed_hosts=spec["allowed_hosts"]), root / (name + "-receipt.json"))
            receipts.append(receipt)
            return checked_json(body)

        control = acquire("count", dict(f="json", where=spec["where"], returnCountOnly="true"))
        count = control.get("count")
        if not isinstance(count, int) or count < 0:
            raise IntakeError("source_schema", "The source did not supply a complete count control")
        keys, rows, offset = set(), [], 0
        while offset < count:
            parameters = dict(f="json", where=spec["where"], returnGeometry="false",
                outFields=",".join(spec["fields"]), orderByFields=spec["key"],
                resultRecordCount=spec["page_size"])
            if offset:
                parameters["resultOffset"] = offset
            data = acquire("page-" + str(offset), parameters)
            page = [feature["attributes"] for feature in data.get("features", [])]
            if not page or any(set(row) != set(spec["fields"]) for row in page):
                raise IntakeError("source_schema", "Incomplete public aggregate page")
            page_keys = [row[spec["key"]] for row in page]
            if page_keys != sorted(page_keys) or any(key in keys for key in page_keys):
                raise IntakeError("source_pagination", "Repeated or unordered public aggregate identities")
            if len(set(page_keys)) != len(page_keys) or rows and page_keys[0] <= rows[-1][spec["key"]]:
                raise IntakeError("source_pagination", "Aggregate pages overlap or changed during acquisition")
            keys.update(page_keys)
            rows.extend(page)
            offset += len(page)
            if not data.get("exceededTransferLimit") and offset < count:
                raise IntakeError("source_pagination", "Source stopped before its declared complete inventory")
        if len(rows) != count:
            raise IntakeError("source_pagination", "Public aggregate query and count control differ")
        report = dict(status="complete_public_aggregate_query", count_control=count,
            records=len(rows), source=spec, receipts=receipts,
            unknown_values_not_replaced=True)
        (root / "complete-query.json").write_bytes(encoded(dict(records=rows, acquisition=report)))
        return rows, report
    finally:
        store.db.close()
