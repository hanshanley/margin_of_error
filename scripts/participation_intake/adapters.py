"""Small direct CSV, JSON/API, PDF and native-statistics adapters."""

import csv
import io
import json
import re

from .contract import IntakeError, VERSION, count, observation_id


FORBIDDEN_FIELDS = {"candidatevotes", "candidatevotetotal", "totalvotes", "demvotes", "repvotes"}
PRIVATE_FIELDS = {"voterid", "ssn", "socialsecuritynumber", "birthdate", "dateofbirth",
                  "firstname", "lastname", "residentialaddress", "mailingaddress"}


def field(row, path, default=None):
    value = row
    for part in str(path).split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdecimal() and int(part) < len(value):
            value = value[int(part)]
        else:
            return default
    return value


def check_fields(row, count_field):
    names = {re.sub(r"[^a-z0-9]", "", str(key).lower()) for key in row}
    if names & PRIVATE_FIELDS:
        raise IntakeError("private_record_input", "This intake accepts public aggregate rows, not voter/person records")
    for value in row.values():
        if isinstance(value, dict):
            check_fields(value, count_field)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    check_fields(item, count_field)
    if re.sub(r"[^a-z0-9]", "", count_field.lower()) in FORBIDDEN_FIELDS:
        raise IntakeError("candidate_vote_substitution", "The selected count field is a candidate/contest vote total")


def make_row(spec, native, index, input_pin, clock, references):
    mapping = spec["columns"]
    check_fields(native, mapping["count"])
    identity_fields = mapping["geography_id"]
    parts = [field(native, name) for name in identity_fields] if isinstance(identity_fields, list) else [field(native, identity_fields)]
    if not parts or any(part is None or part == "" for part in parts):
        raise IntakeError("geographic_scope", "Source row has no declared geographic identity")
    geo_key = "|".join(str(part) for part in parts)
    lookup = references.get("identities", {}).get(geo_key)
    level = spec["geography"]["level"]
    geo = dict(id=lookup["id"] if lookup else geo_key,
        name=lookup["name"] if lookup else str(field(native, mapping.get("geography_name", ""), geo_key)),
        state_code=spec["geography"]["state_code"], level=level,
        parent_id=lookup.get("parent_id") if lookup else None,
        join=dict(status="approved" if lookup else "unreviewed",
            reference_id=lookup.get("reference_id") if lookup else None,
            feature_key=lookup.get("feature_key") if lookup else None,
            evidence=lookup.get("evidence") if lookup else None))
    reported_field = mapping.get("reported")
    missing = object()
    literal = field(native, mapping["count"], missing)
    if literal is missing:
        raise IntakeError("source_schema", "The registered count field is absent, not a reported unknown")
    if reported_field:
        flag = field(native, reported_field, missing)
        if flag is missing or str(flag) not in {
                str(mapping.get("reported_value", "1")), *map(str, mapping.get("unreported_values", ["0"]))}:
            raise IntakeError("source_schema", "Native reporting flag is missing or unrecognized")
        reported = str(flag) == str(mapping.get("reported_value", "1"))
    else:
        reported = literal not in (None, "")
    value = count(literal) if reported else None
    if reported and value is None:
        raise IntakeError("missing_reported_count", "Reported source flag has no numerical count")
    denominator_fields = mapping.get("denominator", [])
    denominator_fields = [denominator_fields] if isinstance(denominator_fields, str) else denominator_fields
    denominator_values = [count(field(native, name)) for name in denominator_fields]
    denominator = None
    if denominator_fields:
        supplied = reported and all(value is not None for value in denominator_values)
        denominator = dict(value=sum(denominator_values) if supplied else None,
            literal=spec["denominator"]["literal"], basis=spec["denominator"]["basis"], qualified=False)
    conflicts = []
    components = mapping.get("components", [])
    if reported and components:
        values = [count(field(native, name)) for name in components]
        if any(value is None for value in values):
            raise IntakeError("missing_component", "A declared native accounting component is absent")
        residual = value - sum(values)
        if residual:
            conflicts.append(dict(code="component_conflict", residual=residual, repaired=False))
    if value is not None and denominator and denominator["value"] is not None and value > denominator["value"]:
        conflicts.append(dict(code="electorate_excess", excess=value-denominator["value"], repaired=False))
    if denominator:
        denominator["qualified"] = (level in spec.get("rate_levels", []) and reported
            and denominator["value"] is not None and denominator["value"] > 0 and not conflicts)
    measure = dict(spec["measure"])
    row_id = observation_id(spec["id"], spec["election"]["id"], geo["id"], measure["id"], measure["mode"])
    return dict(contract=VERSION, id=row_id, election=dict(spec["election"]), geography=geo,
        measure=measure, count=dict(value=value, status="reported" if reported else "unknown", literal=literal),
        denominator=denominator, source_clock=dict(clock),
        reporting_status=dict(literal=spec.get("reporting_status"), reported_units=1 if reported else 0,
            total_units=1, complete=reported),
        source=dict(id=spec["id"], url=spec["inputs"][spec["primary_input"]]["url"],
            input_sha256=input_pin["sha256"], selector=dict(row=index),
            classification=spec["classification"], fields=native),
        quality=dict(conflicts=conflicts, notes=list(spec.get("notes", []))))


def delimited(spec, inputs):
    options = spec.get("format", {})
    try:
        text = inputs[spec["primary_input"]].decode(options.get("encoding", "utf-8-sig"))
        rows = list(csv.DictReader(io.StringIO(text), delimiter=options.get("delimiter", ","),
                                  fieldnames=options.get("fieldnames"), strict=True))
    except (UnicodeError, csv.Error) as error:
        raise IntakeError("source_schema", "Native delimited product could not be decoded completely") from error
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise IntakeError("source_schema", "Native delimited rows have missing or extra columns")
    return rows


def json_records(spec, inputs):
    try:
        data = json.loads(inputs[spec["primary_input"]])
    except (ValueError, UnicodeError) as error:
        raise IntakeError("source_schema", "Native API/JSON product is not valid complete JSON") from error
    path = spec.get("format", {}).get("items_path")
    rows = field(data, path) if path else data
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise IntakeError("source_schema", "The declared API/JSON path must contain aggregate objects")
    return rows


def pdf_records(spec, inputs):
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError as error:
        raise IntakeError("missing_pdf_reader", "The PDF adapter requires the existing pypdf parser") from error
    try:
        reader = PdfReader(io.BytesIO(inputs[spec["primary_input"]]))
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PyPdfError, ValueError, UnicodeError) as error:
        raise IntakeError("source_schema", "Native PDF could not be extracted completely") from error
    options = spec["format"]
    text = "\n".join(pages)
    if not re.search(options["election_pattern"], text):
        raise IntakeError("election_scope", "Native PDF election header does not match the registered product")
    rows = [match.groupdict() for match in re.finditer(options["row_pattern"], text, re.MULTILINE)]
    if not rows:
        raise IntakeError("source_schema", "No native PDF rows match; missing extraction is not zero")
    return rows


ADAPTERS = {"csv": delimited, "json": json_records, "pdf": pdf_records}


def adapt(spec, inputs, input_pins, clock, references):
    name = spec["adapter"]
    if name not in ADAPTERS:
        raise IntakeError("unknown_adapter", "Unregistered direct adapter: " + name)
    rows = ADAPTERS[name](spec, inputs)
    if not rows:
        raise IntakeError("source_schema", "An empty source product is not zero participation")
    if spec.get("expected_rows") is not None and len(rows) != spec["expected_rows"]:
        raise IntakeError("source_schema", "Native row inventory changed; no partial source silently accepted")
    return [make_row(spec, row, index, input_pins[spec["primary_input"]], clock, references)
            for index, row in enumerate(rows, 1)]
