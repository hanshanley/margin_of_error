"""Content-addressed intake, shared checks and deterministic complete downloads."""

import csv
import gzip
import html
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from .adapters import adapt, field
from .contract import IntakeError, VERSION, digest, encoded, observation_id, pin, schema, validate_all


class AllowedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = set(hosts)

    def redirect_request(self, request, response, code, message, headers, url):
        target = urllib.parse.urlparse(url)
        if target.scheme != "https" or target.hostname not in self.hosts:
            raise IntakeError("unapproved_redirect", "Source redirect left its registered public hosts")
        return super().redirect_request(request, response, code, message, headers, url)


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "intake.sqlite3")
        self.db.execute("CREATE TABLE IF NOT EXISTS inputs(url TEXT PRIMARY KEY, sha TEXT, etag TEXT, modified TEXT, stopped TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS runs(recipe TEXT PRIMARY KEY, path TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS geometries(sha TEXT PRIMARY KEY, keys_json TEXT NOT NULL)")

    def object(self, body):
        path = self.root / "objects" / digest(body)
        path.parent.mkdir(exist_ok=True)
        if path.exists():
            if path.read_bytes() != body:
                raise IntakeError("cache_corruption", "Content-addressed original changed")
        else:
            path.write_bytes(body)
        return path

    def acquire(self, description, supplied=None):
        url = description["url"]
        parsed = urllib.parse.urlparse(url)
        hosts = description.get("allowed_hosts", [parsed.hostname])
        if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password:
            raise IntakeError("source_url", "Only registered HTTPS source URLs are permitted")
        if supplied is not None:
            try:
                body = Path(supplied).read_bytes()
            except OSError as error:
                raise IntakeError("source_input_missing", "Supplied original is unavailable: " + str(supplied)) from error
            self.object(body)
            return body, dict(url=url, origin="supplied_original", **pin(body))
        existing = self.db.execute("SELECT sha,etag,modified,stopped FROM inputs WHERE url=?", (url,)).fetchone()
        if description.get("stopped") or existing and existing[3]:
            raise IntakeError("source_stopped", "Recorded access hold; no retry/client/cache/mirror bypass: " + url)
        headers = {}
        if existing and existing[1]:
            headers["If-None-Match"] = existing[1]
        if existing and existing[2]:
            headers["If-Modified-Since"] = existing[2]
        opener = urllib.request.build_opener(AllowedRedirect(hosts))
        try:
            with opener.open(urllib.request.Request(url, headers=headers), timeout=90) as response:
                body = response.read()
                etag, modified = response.headers.get("ETag"), response.headers.get("Last-Modified")
                status = response.status
        except urllib.error.HTTPError as error:
            if error.code == 304 and existing:
                body = (self.root / "objects" / existing[0]).read_bytes()
                if digest(body) != existing[0]:
                    raise IntakeError("cache_corruption", "Cached original hash differs")
                return body, dict(url=url, origin="unchanged_conditional_response", status=304, **pin(body))
            if error.code in (401, 403, 429):
                self.db.execute("INSERT OR REPLACE INTO inputs VALUES(?,?,?,?,?)",
                    (url, existing[0] if existing else None, None, None, "HTTP " + str(error.code)))
                self.db.commit()
            raise IntakeError("source_access", f"HTTP {error.code}; original not replaced or retried") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise IntakeError("source_unavailable", "Source transport failed; no alternate route or empty replacement") from error
        if status != 200:
            raise IntakeError("source_access", "Source did not return a complete successful original")
        if description.get("reject_body_patterns") and any(re.search(pattern, body.decode("utf-8", errors="replace"), re.I)
                for pattern in description["reject_body_patterns"]):
            self.db.execute("INSERT OR REPLACE INTO inputs VALUES(?,?,?,?,?)", (url, None, None, None, "security challenge"))
            self.db.commit()
            raise IntakeError("source_stopped", "Security challenge, not numerical input; route stopped")
        self.object(body)
        self.db.execute("INSERT OR REPLACE INTO inputs VALUES(?,?,?,?,NULL)", (url, digest(body), etag, modified))
        self.db.commit()
        return body, dict(url=url, origin="new_source_response", status=200, **pin(body))

    def geometry_keys(self, asset, body):
        if pin(body) != {key: asset[key] for key in ("bytes", "sha256")}:
            raise IntakeError("geometry_hash", "Approved geometry original differs from its pin")
        if not asset.get("approval_evidence"):
            raise IntakeError("geometry_unreviewed", "A checksum is not a geometry/join approval")
        binding_key = digest(encoded([asset["sha256"], asset.get("key_path", "properties.key")]))
        cached = self.db.execute("SELECT keys_json FROM geometries WHERE sha=?", (binding_key,)).fetchone()
        if cached:
            return set(json.loads(cached[0])), True
        raw = gzip.decompress(body) if body.startswith(b"\x1f\x8b") else body
        data = json.loads(raw)
        keys = [str(field(feature, asset.get("key_path", "properties.key"), "")) for feature in data["features"]]
        if not keys or "" in keys or len(set(keys)) != len(keys):
            raise IntakeError("geometry_identity", "Approved reference contains absent/duplicate feature keys")
        self.db.execute("INSERT INTO geometries VALUES(?,?)", (binding_key, json.dumps(keys)))
        self.db.commit()
        return set(keys), False


def source_clock(spec, inputs):
    description = spec.get("source_clock", {})
    if "input" not in description:
        return dict(literal=description.get("literal"), timezone=description.get("timezone"))
    text = inputs[description["input"]].decode(description.get("encoding", "utf-8-sig"))
    if description.get("html"):
        from html.parser import HTMLParser

        class Text(HTMLParser):
            def __init__(self):
                super().__init__()
                self.values = []

            def handle_data(self, value):
                self.values.append(value)
        parser = Text()
        parser.feed(text)
        text = " ".join(" ".join(parser.values).split())
    matches = list(re.finditer(description["pattern"], text, re.MULTILINE))
    if len(matches) != 1:
        raise IntakeError("source_clock", "Native update clock is absent/ambiguous; retrieval time is not substituted")
    return dict(literal=matches[0].group(description.get("group", 1)), timezone=description.get("timezone"))


def aggregate_parents(rows, spec, references):
    if not spec.get("aggregate_parents"):
        return []
    groups = {}
    for row in rows:
        if row["geography"]["parent_id"] is None:
            raise IntakeError("parent_scope", "Parent aggregation needs explicit declared geographic parents")
        groups.setdefault(row["geography"]["parent_id"], []).append(row)
    result = []
    for identity, children in sorted(groups.items()):
        parent = references.get("parents", {}).get(identity)
        if not parent:
            raise IntakeError("parent_scope", "No approved native parent identity: " + identity)
        if len({json.dumps(row["source_clock"], sort_keys=True) for row in children}) != 1:
            raise IntakeError("mixed_clocks", "Different source clocks must not be summed into a parent")
        complete = all(row["count"]["status"] == "reported" for row in children)
        subtotal = sum(row["count"]["value"] for row in children if row["count"]["value"] is not None)
        conflicts = [dict(conflict, child_id=row["id"]) for row in children for conflict in row["quality"]["conflicts"]]
        denominator = None
        if all(row["denominator"] is not None for row in children):
            native = children[0]["denominator"]
            supplied = complete and all(row["denominator"]["value"] is not None for row in children)
            value = sum(row["denominator"]["value"] for row in children) if supplied else None
            denominator = dict(value=value, literal=native["literal"], basis=native["basis"],
                qualified=bool(parent["level"] in spec.get("rate_levels", []) and supplied
                    and value > 0 and not conflicts and subtotal <= value))
        if not complete:
            conflicts.append(dict(code="partial_reporting", reported_subtotal=subtotal, repaired=False))
        first = children[0]
        geo = dict(id=identity, name=parent["name"], state_code=parent["state_code"], level=parent["level"],
            parent_id=parent.get("parent_id"), join=dict(status="approved",
                reference_id=parent["reference_id"], feature_key=parent["feature_key"], evidence=parent["evidence"]))
        row = dict(first, id=observation_id(spec["id"], first["election"]["id"], identity,
            first["measure"]["id"], first["measure"]["mode"]), geography=geo,
            count=dict(value=subtotal if complete else None, status="reported" if complete else "unknown", literal=None),
            denominator=denominator,
            reporting_status=dict(literal=first["reporting_status"]["literal"], complete=complete,
                reported_units=sum(row["count"]["status"] == "reported" for row in children), total_units=len(children)),
            source=dict(first["source"], selector=dict(derived_parent=identity),
                fields=dict(member_observations=[row["id"] for row in children], reported_subtotal=subtotal)),
            quality=dict(conflicts=conflicts, notes=[*first["quality"]["notes"],
                "Derived native-unit sum, not a separately printed parent or independently unique people."]))
        result.append(row)
    return result


def csv_bytes(rows):
    buffer = io.StringIO(newline="")
    columns = ["id", "election", "geography", "measure", "count", "denominator",
               "source_clock", "reporting_status", "source", "quality"]
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows({key: json.dumps(row[key], sort_keys=True, ensure_ascii=True) if isinstance(row[key], (dict, list))
        else row[key] for key in columns} for row in rows)
    return buffer.getvalue().encode()


def package(output, spec, inputs, receipts, rows, report, references, reference_bodies):
    members = {"source.json": encoded(spec), "queries.json": encoded(rows),
        "queries.csv": csv_bytes(rows), "validation.json": encoded(report), "references.json": encoded(references),
        "contract.schema.json": encoded(schema())}
    for name, body in inputs.items():
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
            raise IntakeError("input_name", "Unsafe input name")
        policy = spec["inputs"][name].get("publication", "original")
        if policy == "factual_html":
            from html.parser import HTMLParser

            class Facts(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.ignored, self.text = 0, []

                def handle_starttag(self, tag, attrs):
                    if tag in ("script", "style", "noscript"):
                        self.ignored += 1

                def handle_endtag(self, tag):
                    if tag in ("script", "style", "noscript"):
                        self.ignored -= 1

                def handle_data(self, text):
                    if not self.ignored and text.strip():
                        self.text.append(text.strip())
            facts = Facts()
            facts.feed(body.decode("utf-8-sig"))
            body = ("<!doctype html><pre>" + html.escape("\n".join(facts.text)) + "</pre>\n").encode()
        elif policy != "original":
            raise IntakeError("publication_policy", "Private/unqualified originals cannot be packaged")
        members["originals/" + name] = body
    for identity, body in reference_bodies.items():
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", identity):
            raise IntakeError("reference_name", "Unsafe reference ID")
        members["references/" + identity] = body
    members["source-receipts-without-headers.json"] = encoded(receipts)
    for path in sorted(Path(__file__).parent.glob("*.py")):
        members["code/participation_intake/" + path.name] = path.read_bytes()
    tests = Path(__file__).parent.parent / "test-participation-intake.py"
    if tests.exists():
        members["tests/test-participation-intake.py"] = tests.read_bytes()
    requirements = Path(__file__).parent.parent / "requirements-participation-intake.txt"
    if requirements.exists():
        members["requirements.txt"] = requirements.read_bytes()
    members["README.txt"] = (
        "COMPLETE PARTICIPATION INTAKE\n\n"
        "Every permitted original, full accepted observation/query, source fields, conflicts,\n"
        "rejection report, source specification, reference bindings and exact maintained adapter/\n"
        "validator/packager code are included. Unknown is not zero. Native clocks are not receipts.\n"
        "Candidate votes are rejected, not substituted. No source count or geometry is repaired.\n"
        "Originals are named by their registered input IDs; source.json describes their formats.\n"
        "Reproduce without acquisition: python reproduce.py > reproduced-queries.json\n"
    ).encode()
    members["reproduce.py"] = b"""import json,pathlib,sys
root=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(root/'code'))
from participation_intake.engine import reproduce
from participation_intake.contract import encoded
sys.stdout.buffer.write(encoded(reproduce(root)))
"""
    members["manifest.json"] = encoded(dict(contract=VERSION,
        files={name: pin(body) for name, body in sorted(members.items())}))
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, body)
    return dict(**pin(output.read_bytes()), members=len(members))


def reproduce(root):
    manifest = json.loads((root / "manifest.json").read_bytes())
    for name, expected in manifest["files"].items():
        if pin((root / name).read_bytes()) != expected:
            raise IntakeError("package_integrity", "Changed complete package member: " + name)
    spec = json.loads((root / "source.json").read_bytes())
    inputs = {name: (root / "originals" / name).read_bytes() for name in spec["inputs"]}
    references = json.loads((root / "references.json").read_bytes())
    expected = json.loads((root / "validation.json").read_bytes())
    try:
        rows = adapt(spec, inputs, {name: pin(body) for name, body in inputs.items()},
                     source_clock(spec, inputs), references)
        rows.extend(aggregate_parents(rows, spec, references))
        validate_all(rows)
        reference_keys = {}
        for identity, asset in references.get("assets", {}).items():
            path = root / "references" / identity
            if not path.exists():
                raise IntakeError("geometry_original_missing", "Approved reference original is absent: " + identity)
            body = path.read_bytes()
            if pin(body) != {key: asset[key] for key in ("bytes", "sha256")}:
                raise IntakeError("geometry_hash", "Complete package reference differs")
            raw = gzip.decompress(body) if body.startswith(b"\x1f\x8b") else body
            reference_keys[identity] = {str(field(feature, asset.get("key_path", "properties.key")))
                for feature in json.loads(raw)["features"]}
        check_joins(rows, reference_keys)
    except IntakeError as error:
        if expected["status"] == "rejected" and error.code in {item["code"] for item in expected["errors"]}:
            rows = []
        else:
            raise
    else:
        if expected["status"] == "rejected":
            raise IntakeError("rejection_not_reproduced", "The recorded rejection did not reproduce")
    if encoded(rows) != (root / "queries.json").read_bytes():
        raise IntakeError("reproduction_mismatch", "Reproduced full queries differ from the packaged results")
    return rows


def check_joins(rows, reference_keys):
    for row in rows:
        join = row["geography"]["join"]
        if join["status"] == "approved" and (join["reference_id"] not in reference_keys
                or str(join["feature_key"]) not in reference_keys[join["reference_id"]]):
            raise IntakeError("geographic_join", "Observation key is absent from its approved reference", row["id"])


def run(spec, store, supplied=None, references=None, geometry_inputs=None):
    supplied, references, geometry_inputs = supplied or {}, references or {}, geometry_inputs or {}
    if spec.get("classification") != "public_aggregate":
        raise IntakeError("private_record_input", "Only declared public aggregate products can enter public intake")
    inputs, receipts = {}, {}
    try:
        for name, description in spec["inputs"].items():
            inputs[name], receipts[name] = store.acquire(description, supplied.get(name))
    except IntakeError as error:
        report = dict(contract=VERSION, source_id=spec["id"], status="rejected",
            errors=[error.as_dict()], acquired_input_pins={name: pin(body) for name, body in inputs.items()},
            source_counts_repaired=False, geometry_repaired=False, acquisition_incomplete=True)
        attempts = store.root / "attempts"
        attempts.mkdir(exist_ok=True)
        target = attempts / (digest(encoded(spec)) + ".json")
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(encoded(report))
        os.replace(temporary, target)
        return dict(report, no_op=False, directory=None)
    input_pins = {name: pin(body) for name, body in inputs.items()}
    code = {path.name: digest(path.read_bytes()) for path in Path(__file__).parent.glob("*.py")}
    for name in ("test-participation-intake.py", "requirements-participation-intake.txt"):
        path = Path(__file__).parent.parent / name
        if path.exists():
            code[name] = digest(path.read_bytes())
    recipe = digest(encoded(dict(source=spec, inputs=input_pins, references=references, code=code)))
    cached = store.db.execute("SELECT path FROM runs WHERE recipe=?", (recipe,)).fetchone()
    if cached:
        path = Path(cached[0])
        report = json.loads((path / "validation.json").read_bytes())
        expected = json.loads((path / "manifest.json").read_bytes())
        for name, entry in expected["files"].items():
            if pin((path / name).read_bytes()) != entry:
                raise IntakeError("cache_corruption", "Previously verified intake output changed")
        complete = expected["files"].get("complete-analysis.zip")
        return dict(report, no_op=True, parsed_inputs=0, geometry_parses=0, directory=str(path),
            complete_download=dict(complete, members=expected["complete_download_members"]) if complete else None)
    final_directory = store.root / "runs" / recipe
    staging = store.root / "staging"
    staging.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix=recipe + ".", dir=staging))
    errors, rows, geometry_parses, reference_bodies = [], [], 0, {}
    try:
        rows = adapt(spec, inputs, input_pins, source_clock(spec, inputs), references)
        rows.extend(aggregate_parents(rows, spec, references))
        validate_all(rows)
        reference_keys = {}
        for identity, asset in references.get("assets", {}).items():
            body = geometry_inputs.get(identity)
            if body is None:
                cached_body = store.root / "objects" / asset["sha256"]
                if not cached_body.exists():
                    raise IntakeError("geometry_original_missing", "Approved reference original must be supplied once: " + identity)
                body = cached_body.read_bytes()
            store.object(body)
            reference_bodies[identity] = body
            keys, reused = store.geometry_keys(asset, body)
            reference_keys[identity] = keys
            geometry_parses += not reused
        check_joins(rows, reference_keys)
    except IntakeError as error:
        errors.append(error.as_dict())
        rows = []
    if any(error["code"] == "private_record_input" for error in errors):
        report = dict(contract=VERSION, source_id=spec["id"], recipe=recipe, status="rejected",
            errors=errors, raw_inputs_quarantined_not_packaged=True)
        (directory / "validation.json").write_bytes(encoded(report))
        (directory / "manifest.json").write_bytes(encoded(dict(recipe=recipe,
            files={"validation.json": pin((directory / "validation.json").read_bytes())})))
        final_directory.parent.mkdir(exist_ok=True)
        directory.rename(final_directory)
        store.db.execute("INSERT INTO runs VALUES(?,?)", (recipe, str(final_directory)))
        store.db.commit()
        return dict(report, no_op=False, directory=str(final_directory))
    report = dict(contract=VERSION, source_id=spec["id"], recipe=recipe,
        status="rejected" if errors else "awaiting_publication",
        errors=errors, observations=len(rows), reported=sum(row["count"]["status"] == "reported" for row in rows),
        unknown=sum(row["count"]["status"] != "reported" for row in rows),
        observed_zeros=sum(row["count"]["value"] == 0 for row in rows),
        conflicts=sum(len(row["quality"]["conflicts"]) for row in rows),
        states=sorted({row["geography"]["state_code"] for row in rows}),
        source_counts_repaired=False, geometry_repaired=False, geometry_parses=geometry_parses,
        original_pins=input_pins)
    (directory / "queries.json").write_bytes(encoded(rows))
    (directory / "queries.json.gz").write_bytes(gzip.compress(encoded(rows), mtime=0))
    (directory / "validation.json").write_bytes(encoded(report))
    members = {"queries.json": pin((directory / "queries.json").read_bytes()),
        "queries.json.gz": pin((directory / "queries.json.gz").read_bytes()),
        "validation.json": pin((directory / "validation.json").read_bytes())}
    complete = package(directory / "complete-analysis.zip", spec, inputs, receipts, rows, report, references, reference_bodies)
    members["complete-analysis.zip"] = {key: complete[key] for key in ("bytes", "sha256")}
    (directory / "manifest.json").write_bytes(encoded(dict(recipe=recipe, files=members,
        complete_download_members=complete["members"])))
    final_directory.parent.mkdir(exist_ok=True)
    directory.rename(final_directory)
    store.db.execute("INSERT INTO runs VALUES(?,?)", (recipe, str(final_directory)))
    store.db.commit()
    return dict(report, no_op=False, parsed_inputs=len(inputs), directory=str(final_directory), complete_download=complete)
