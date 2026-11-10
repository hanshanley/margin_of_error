"""The shared participation contract; source adapters do not define validation rules."""

import hashlib
import json
import re
from datetime import date
from urllib.parse import urlparse


VERSION = "participation.observation.v1"
STATES = "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
LEVELS = {"state", "county", "county_equivalent", "municipality", "election_administration",
          "source_region", "precinct", "ward", "reporting_unit", "nongeographic"}
MEASURES = {"ballots_cast", "voters_reported", "cards_cast", "returned", "early_activity",
            "source_activity", "participation_reported"}
MODES = {"all_methods", "in_person_early", "mail_returned", "source_defined"}
STATUSES = {"reported", "unknown", "withheld"}
SHA = re.compile(r"^[a-f0-9]{64}$")


class IntakeError(ValueError):
    def __init__(self, code, message, record_id=None):
        super().__init__(message)
        self.code, self.record_id = code, record_id

    def as_dict(self):
        return dict(code=self.code, message=str(self), record_id=self.record_id)


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def pin(body):
    return dict(bytes=len(body), sha256=digest(body))


def count(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise IntakeError("invalid_count", "A boolean is not a native count")
    text = str(value)
    if not re.fullmatch(r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)", text, flags=re.ASCII):
        raise IntakeError("invalid_count", "Count must be a nonnegative literal integer: " + text)
    result = int(text.replace(",", ""))
    if result > 2**53 - 1:
        raise IntakeError("unsafe_count", "Count exceeds the browser's exact integer range")
    return result


def required(value, keys, label):
    if not isinstance(value, dict) or any(key not in value for key in keys):
        raise IntakeError("invalid_contract", "Missing " + label + " fields: " + ",".join(keys))


def text(value, label, nullable=False):
    if value is None and nullable:
        return
    if not isinstance(value, str) or not value:
        raise IntakeError("invalid_contract", label + " must be a nonempty string")


def integer(value, label, nullable=False):
    if value is None and nullable:
        return
    if not isinstance(value, int) or isinstance(value, bool):
        raise IntakeError("invalid_contract", label + " must be an exact integer")
    count(value)


def observation_id(source, election, geography, measure, mode):
    return digest(encoded([source, election, geography, measure, mode]))[:32]


def validate(row):
    required(row, ["contract", "id", "election", "geography", "measure", "count", "denominator",
                   "source_clock", "reporting_status", "source", "quality"], "observation")
    required(row["quality"], ["conflicts", "notes"], "quality")
    if (not isinstance(row["quality"]["conflicts"], list)
            or not isinstance(row["quality"]["notes"], list)
            or any(not isinstance(note, str) for note in row["quality"]["notes"])):
        raise IntakeError("invalid_contract", "Conflicts and qualifications must be explicit arrays")
    for conflict in row["quality"]["conflicts"]:
        required(conflict, ["code"], "conflict")
        text(conflict["code"], "Conflict code")
        if conflict.get("repaired", False) is not False:
            raise IntakeError("source_repair", "Intake retains conflicts without repairing source counts")
    if row["contract"] != VERSION or not isinstance(row["id"], str) or not row["id"]:
        raise IntakeError("invalid_contract", "Unknown contract or missing stable observation ID")
    election, geo, measure, source = (row[key] for key in ("election", "geography", "measure", "source"))
    required(election, ["id", "year", "date", "type", "qualification"], "election")
    for key in ("id", "type", "qualification"):
        text(election[key], "Election " + key)
    if election["date"] is not None:
        text(election["date"], "Election date")
        try:
            election_date = date.fromisoformat(election["date"])
        except ValueError as error:
            raise IntakeError("election_scope", "Invalid literal election date") from error
        if election_date.year != election["year"]:
            raise IntakeError("election_scope", "Election date and year disagree")
    if (not isinstance(election["year"], int) or isinstance(election["year"], bool)
            or election["qualification"] not in ("native", "collector_context", "previously_reviewed")):
        raise IntakeError("election_scope", "Election identity and its qualification must remain explicit")
    required(geo, ["id", "name", "state_code", "level", "parent_id", "join"], "geography")
    for key in ("id", "name", "state_code", "level"):
        text(geo[key], "Geography " + key)
    text(geo["parent_id"], "Geographic parent", nullable=True)
    if geo["state_code"] not in STATES or geo["level"] not in LEVELS or not geo["id"] or not geo["name"]:
        raise IntakeError("geographic_scope", "Unknown jurisdiction, level or native identity")
    required(geo["join"], ["status", "reference_id", "feature_key", "evidence"], "geographic join")
    text(geo["join"]["status"], "Join status")
    for key in ("reference_id", "feature_key", "evidence"):
        text(geo["join"][key], "Join " + key, nullable=True)
    if geo["join"]["status"] not in ("approved", "unreviewed", "unmatched", "nongeographic"):
        raise IntakeError("geographic_join", "Invalid join disposition")
    if geo["join"]["status"] == "approved" and any(
            not geo["join"][key] for key in ("reference_id", "feature_key", "evidence")):
        raise IntakeError("geographic_join", "Approved joins need an explicit reference, key and evidence")
    required(measure, ["id", "literal", "kind", "mode", "unit"], "literal measure")
    for key in ("id", "literal", "kind", "mode", "unit"):
        text(measure[key], "Measure " + key)
    if measure["kind"] not in MEASURES:
        raise IntakeError("candidate_vote_substitution", "Contest/candidate votes are not participation counts")
    if not measure["literal"] or measure["mode"] not in MODES or not measure["unit"]:
        raise IntakeError("measure_scope", "Literal measure, source mode and units must be supplied")
    required(row["count"], ["value", "status", "literal"], "count")
    value, status = row["count"]["value"], row["count"]["status"]
    text(status, "Count status")
    if status not in STATUSES or (status == "reported") != (value is not None):
        raise IntakeError("missing_as_zero", "Only explicitly reported rows have counts; unknown/withheld stay null")
    if value is not None and (not isinstance(value, int) or isinstance(value, bool) or count(value) != value):
        raise IntakeError("invalid_count", "Canonical counts must be exact integers, including real zero")
    denominator = row["denominator"]
    if denominator is not None:
        required(denominator, ["value", "literal", "basis", "qualified"], "denominator")
        integer(denominator["value"], "Denominator", nullable=True)
        text(denominator["literal"], "Literal denominator")
        text(denominator["basis"], "Denominator basis")
        if not isinstance(denominator["qualified"], bool) or not denominator["literal"] or not denominator["basis"]:
            raise IntakeError("denominator_scope", "Native denominator meaning and qualification are required")
        if denominator["qualified"] and (value is None or denominator["value"] is None
                or denominator["value"] <= 0 or value > denominator["value"] or row["quality"]["conflicts"]):
            raise IntakeError("unqualified_rate", "Conflicts, unknowns or electorate excesses cannot approve a rate")
    required(row["source_clock"], ["literal", "timezone"], "source clock")
    text(row["source_clock"]["literal"], "Literal source clock", nullable=True)
    text(row["source_clock"]["timezone"], "Source timezone", nullable=True)
    if row["source_clock"]["literal"] is None and row["source_clock"]["timezone"] is not None:
        raise IntakeError("invented_clock", "Unknown source clock cannot acquire an inferred timezone")
    required(row["reporting_status"], ["literal", "reported_units", "total_units", "complete"], "reporting status")
    for key in ("reported_units", "total_units"):
        integer(row["reporting_status"][key], "Reporting " + key, nullable=True)
    reporting = row["reporting_status"]
    if reporting["complete"] is not None and not isinstance(reporting["complete"], bool):
        raise IntakeError("reporting_status", "Reporting completeness must be explicit or unknown")
    text(reporting["literal"], "Literal reporting status", nullable=True)
    if reporting["reported_units"] is not None and reporting["total_units"] is not None:
        if reporting["reported_units"] > reporting["total_units"]:
            raise IntakeError("reporting_status", "Reported unit inventory exceeds its source total")
        if reporting["complete"] is True and reporting["reported_units"] != reporting["total_units"]:
            raise IntakeError("reporting_status", "Partial reporting cannot be marked complete")
    required(source, ["id", "url", "input_sha256", "selector", "classification", "fields"], "source")
    for key in ("id", "url", "input_sha256", "classification"):
        text(source[key], "Source " + key)
    if not isinstance(source["fields"], dict) or not isinstance(source["selector"], dict):
        raise IntakeError("source_provenance", "Native fields and exact source selector must be objects")
    if (not SHA.fullmatch(source["input_sha256"]) or urlparse(source["url"]).scheme != "https"
            or source["classification"] != "public_aggregate"):
        raise IntakeError("source_provenance", "Public aggregate provenance and exact original hash are required")
    if row["id"] != observation_id(source["id"], election["id"], geo["id"], measure["id"], measure["mode"]):
        raise IntakeError("observation_identity", "Stable observation identity does not match its contract fields")
    return row


def validate_all(rows):
    seen = set()
    for row in rows:
        validate(row)
        key = (row["source"]["id"], row["election"]["id"], row["geography"]["id"],
               row["measure"]["id"], row["measure"]["mode"])
        if row["id"] in seen or key in seen:
            raise IntakeError("duplicate_observation", "Duplicate source/election/geography/measure", row["id"])
        seen.update((row["id"], key))
    return rows


def schema():
    """Portable structural contract; validate() also enforces cross-field semantics."""
    string = dict(type="string", minLength=1)
    nullable_text = dict(type=["string", "null"], minLength=1)
    unsigned = dict(type="integer", minimum=0, maximum=2**53-1)
    nullable_count = dict(anyOf=[unsigned, dict(type="null")])

    def obj(properties):
        return dict(type="object", required=list(properties), properties=properties)

    definitions = dict(
        election=obj(dict(id=string, year=dict(type="integer"),
            date=dict(type=["string", "null"], format="date"), type=string,
            qualification=dict(enum=["native", "collector_context", "previously_reviewed"]))),
        geography=obj(dict(id=string, name=string, state_code=dict(enum=STATES),
            level=dict(enum=sorted(LEVELS)), parent_id=nullable_text,
            join=obj(dict(status=dict(enum=["approved", "unreviewed", "unmatched", "nongeographic"]),
                reference_id=nullable_text, feature_key=nullable_text, evidence=nullable_text)))),
        measure=obj(dict(id=string, literal=string, kind=dict(enum=sorted(MEASURES)),
            mode=dict(enum=sorted(MODES)), unit=string)),
        count=obj(dict(value=nullable_count, status=dict(enum=sorted(STATUSES)),
            literal=dict(type=["integer", "string", "null"]))),
        denominator=dict(anyOf=[dict(type="null"), obj(dict(value=nullable_count,
            literal=string, basis=string, qualified=dict(type="boolean")))]),
        source_clock=obj(dict(literal=nullable_text, timezone=nullable_text)),
        reporting_status=obj(dict(literal=nullable_text, reported_units=nullable_count,
            total_units=nullable_count, complete=dict(type=["boolean", "null"]))),
        source=obj(dict(id=string, url=dict(type="string", pattern=r"^https://"),
            input_sha256=dict(type="string", pattern=SHA.pattern),
            selector=dict(type="object"), classification=dict(const="public_aggregate"),
            fields=dict(type="object"))),
        quality=obj(dict(conflicts=dict(type="array", items=dict(type="object",
            required=["code"], properties=dict(code=string, repaired=dict(const=False)))),
            notes=dict(type="array", items=dict(type="string")))))
    properties = dict(contract=dict(const=VERSION), id=string)
    properties.update({name: {"$ref": "#/$defs/" + name} for name in definitions})
    return dict(obj(properties), **{"$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:participation:observation:v1", "$defs": definitions})
