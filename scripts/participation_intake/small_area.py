"""Reusable native block-group index for qualified population-weight crosswalks."""

import csv
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from .acs_context import STATE_FIPS, TABLES, native_value
from .contract import IntakeError, encoded, digest


def file_pin(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            checksum.update(block)
    return dict(bytes=Path(path).stat().st_size, sha256=checksum.hexdigest())


def block_group_rows(path, table):
    count = TABLES[table]
    expected = {"GEO_ID"} | {f"{table}_{kind}{i:03d}" for kind in ("E", "M") for i in range(1, count+1)}
    with Path(path).open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source, delimiter="|", strict=True)
        if set(reader.fieldnames or []) != expected or len(reader.fieldnames or []) != len(expected):
            raise IntakeError("context_schema", "Complete block-group table header differs")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise IntakeError("context_schema", "Incomplete source table row")
            native = row["GEO_ID"]
            if not native.startswith("1500000US"):
                continue
            geoid = native.removeprefix("1500000US")
            if not re.fullmatch(r"\d{12}", geoid, re.ASCII):
                raise IntakeError("context_geography", "Invalid native block-group identity")
            if geoid[:2] not in STATE_FIPS:
                continue
            values = [[row[f"{table}_E{i:03d}"], row[f"{table}_M{i:03d}"]] for i in range(1, count+1)]
            for estimate, moe in values:
                native_value(estimate)
                native_value(moe)
            yield geoid, values


def build_block_group_index(source_store, output):
    root, output = Path(source_store), Path(output)
    receipts = {table: json.loads((root / (table+"-receipt.json")).read_bytes()) for table in TABLES}
    recipe = digest(encoded(dict(inputs=receipts,
        adapter=file_pin(Path(__file__)), contract="resident.native_block_group_cells.v1")))
    output.mkdir(parents=True, exist_ok=True)
    proof = output / "summary.json"
    if proof.exists():
        existing = json.loads(proof.read_bytes())
        if existing["recipe"] != recipe or existing["database"] != file_pin(output / "native-cells.sqlite3"):
            raise IntakeError("cache_corruption", "The held native block-group index differs")
        return dict(existing, no_op=True)
    db = sqlite3.connect(output / "native-cells.sqlite3")
    try:
        db.execute("CREATE TABLE IF NOT EXISTS cells(geoid TEXT NOT NULL, table_id TEXT NOT NULL, native_pairs TEXT NOT NULL, PRIMARY KEY(geoid,table_id))")
        db.execute("CREATE TABLE IF NOT EXISTS completed(table_id TEXT PRIMARY KEY, recipe TEXT NOT NULL, rows INTEGER NOT NULL)")
        inventories = {}
        for table in TABLES:
            receipt = receipts[table]
            source = root / "objects" / receipt["sha256"]
            if file_pin(source) != {key: receipt[key] for key in ("bytes", "sha256")}:
                raise IntakeError("context_original_hash", "The complete held ACS original differs")
            prior = db.execute("SELECT recipe,rows FROM completed WHERE table_id=?", (table,)).fetchone()
            if prior:
                if prior[0] != recipe:
                    raise IntakeError("cache_corruption", "Incomplete index uses a different adapter or inputs")
                inventories[table] = prior[1]
                continue
            db.execute("DELETE FROM cells WHERE table_id=?", (table,))
            count, batch = 0, []
            try:
                for geoid, pairs in block_group_rows(source, table):
                    batch.append((geoid, table, json.dumps(pairs, separators=(",", ":"))))
                    count += 1
                    if len(batch) == 2000:
                        db.executemany("INSERT INTO cells VALUES(?,?,?)", batch)
                        db.commit()
                        batch = []
                db.executemany("INSERT INTO cells VALUES(?,?,?)", batch)
            except sqlite3.IntegrityError as error:
                raise IntakeError("context_geography", "Duplicate native block-group identity") from error
            db.execute("INSERT INTO completed VALUES(?,?,?)", (table, recipe, count))
            db.commit()
            inventories[table] = count
        missing = db.execute("SELECT geoid FROM cells GROUP BY geoid HAVING COUNT(*)<>?", (len(TABLES),)).fetchall()
        if missing:
            raise IntakeError("context_geography", "Native block-group identity sets differ; do not silently fill tables")
        states = db.execute("SELECT DISTINCT substr(geoid,1,2) FROM cells").fetchall()
        total = db.execute("SELECT COUNT(DISTINCT geoid) FROM cells").fetchone()[0]
    finally:
        db.close()
    result = dict(status="complete_native_block_group_cells_not_yet_precinct_estimates",
        contract="resident.native_block_group_cells.v1", recipe=recipe, block_groups=total,
        states=len(states), native_table_inventories=inventories,
        database=file_pin(output / "native-cells.sqlite3"),
        source_period="2020-2024", source_geography_vintage=2024,
        precinct_crosswalk_not_yet_qualified=True, original_reacquisitions=0)
    proof.write_bytes(encoded(result))
    return result
