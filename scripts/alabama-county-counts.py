"""Reproduce native Alabama county counts and explicit Census reference joins."""

import csv
from datetime import datetime, timedelta
import gzip
import hashlib
import importlib.util
import io
from itertools import combinations
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-alabama-native-county-counts-02"


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def count(value):
    text = str(value).replace(",", "")
    require(re.fullmatch(r"[0-9]+", text) is not None, "Missing or invalid native count")
    return int(text)


def name_key(name):
    return name.removesuffix(" County").casefold()


def qualify(sheets, facts, legacy, geometry, reference, pairs):
    require(len(sheets["Statistics"]) == len(legacy) == len(geometry["features"]) == 67,
            "Incomplete county statistics or reference")
    names = {}
    for row in sheets["AllResults"]:
        require(row["Election Code"] == "1001305" and row["Election Title"] == "2026 GENERAL ELECTION",
                "Incorrect native workbook election")
        names.setdefault(row["County Code"], set()).add(row["County Name"])
    require(len(names) == 67 and all(len(values) == 1 for values in names.values()),
            "Ambiguous native county names")
    source_by_id = {row["county_code"]: row for row in legacy}
    require(len(source_by_id) == 67, "Duplicate legacy county identity")
    shapes = {name_key(feature["properties"]["name"]): feature for feature in geometry["features"]}
    fips = {feature["properties"]["key"] for feature in geometry["features"]}
    require(len(shapes) == len(fips) == 67 and reference["boundary_year"] == 2026,
            "Duplicate county reference or wrong vintage")
    require(all(feature["properties"]["state_code"] == "AL"
                and feature["properties"]["boundary_year"] == 2026
                and re.fullmatch(r"01[0-9]{3}", feature["properties"]["key"])
                for feature in shapes.values()), "Incorrect Alabama county reference")
    require(len(pairs) == 2211 and
            {(row["left"], row["right"]) for row in pairs} == set(combinations(sorted(fips), 2))
            and all(row["overlap_degrees_squared"] == 0 for row in pairs),
            "Incomplete or positive native county overlap review")
    counties, seen = [], set()
    for native in sheets["Statistics"]:
        code = native["County Code"]
        require(native["Election Code"] == "1001305" and native["Election Title"] == "2026 GENERAL ELECTION",
                "Incorrect native statistics election")
        require(code in source_by_id and code in names and code not in seen,
                "Missing, duplicate or unreviewed ordinal county identity")
        seen.add(code)
        old = source_by_id[code]
        factual = facts["official-county-" + code]
        page = factual["literal_source_fields"]
        source_name = factual["native_county_name"]
        require(factual["native_county_code"] == code
                and name_key(source_name) == name_key(old["county"])
                and name_key(source_name) == name_key(next(iter(names[code])))
                and name_key(source_name) == name_key(page["lblCountyName"]),
                "Native county names disagree")
        feature = shapes.get(name_key(source_name))
        require(feature is not None, "Unmatched native county name")
        ballots = count(native["Ballots Cast"])
        registered = count(page["lblTotalRegisteredVoters"])
        total, reported = count(native["Total Precincts"]), count(native["Precincts Reported"])
        require(page["lblElectionName"] == "2026 GENERAL ELECTION"
                and old["year"] == "2026" and old["state_code"] == "AL"
                and ballots == count(page["lblTotalBallotsCast"]) == count(old["ballots"])
                and registered == count(old["registered_voters"])
                and total == count(old["total_precincts"])
                and reported == count(old["precincts_reported"]) and reported == total,
                "Native county statistics or source frames disagree")
        updated = datetime(1899, 12, 30) + timedelta(days=float(native["Last Updated"]))
        literal = page["lblLastUpdated"]
        require(abs((datetime.strptime(literal, "%m/%d/%Y %I:%M:%S %p") - updated).total_seconds()) < 1
                and literal == old["last_updated_native"]
                and native["Last Updated"] == old["last_updated_excel_serial"]
                and page["lblVoterTurnout"] == old["source_reported_turnout_percent"],
                "Native clocks or printed percentages disagree")
        counties.append(dict(
            native_county_code=code, county=source_name,
            native_workbook_county_name=next(iter(names[code])),
            reference_county_name=feature["properties"]["name"],
            county_fips=feature["properties"]["key"], ballots=ballots, registered=registered,
            source_reported_units=reported, source_total_units=total,
            source_update_literal=literal, source_update_timezone=None,
            native_printed_pct=page["lblVoterTurnout"], reported_pct=None,
            source_count_qualified=True, registration_frame_qualified=False,
            cast_ballot_count_independently_qualified=False, unique_voter_count_qualified=False,
            precinct_coverage_approved=False, native_workbook_statistics=native,
            native_factual_fields=page, legacy_record=old))
    require(len(seen) == 67 and len({row["county_fips"] for row in counties}) == 67,
            "Incomplete native county identity universe")
    parent = facts["official-statewide-results"]["literal_source_fields"]
    require(parent["lblElectionName"] == "2026 GENERAL ELECTION"
            and count(parent["lblCountiesReported"]) == 67
            and sum(row["ballots"] for row in counties) == count(parent["lblTotalBallotsCast"]) == 1693621
            and sum(row["registered"] for row in counties) == count(parent["lblTotalRegisteredVoters"]) == 3852947,
            "Native state/county count disagreement")
    return dict(county_decisions=sorted(counties, key=lambda row: row["county_fips"]),
        all2211_county_pair_decisions=pairs, native_state_factual_fields=parent,
        county_reference=reference,
        summary=dict(counties=67, native_ballots=1693621, native_registered=3852947,
            approved_analysis_rates=0, approved_precinct_maps=0,
            valid_unrepaired_county_shapes=67, complete_pair_decisions=2211, positive_overlap_pairs=0,
            source_measure_literal="Ballots Cast", native_county_codes_are_not_FIPS=True,
            certification_inferred=False, unique_voter_count_qualified=False,
            source_counts_repaired=False, candidate_votes_used_as_ballots=False))


def frozen(root=ROOT):
    source = Path(root) / VERSION
    inputs = json.loads((source / "inputs.json").read_bytes())
    require(inputs["version"] == VERSION and len(inputs["files"]) == 11, "Changed sufficient-input scope")
    for name, pin in inputs["files"].items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "Unsafe frozen source path")
        body = (source / name).read_bytes()
        require(len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"],
                "Changed sufficient input: " + name)
    spec = importlib.util.spec_from_file_location("held_alabama_reader", source / "code/held-native-reader.py")
    held = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(held)
    sheets, _ = held.read_workbook(gzip.decompress((source / "originals/full-native-export.gz").read_bytes()))
    return dict(sheets=sheets,
        facts=json.loads((source / "originals/all67-county-and-state-literal-fields.json").read_bytes()),
        legacy=list(csv.DictReader(io.StringIO((source / "legacy/all67-native-county-participation.csv").read_text()))),
        geometry=json.loads(gzip.decompress((source / "AL-full-county-reference.geojson.gz").read_bytes())),
        reference=json.loads((source / "county-reference.json").read_bytes()),
        pairs=json.loads((source / "prior-join-review/queries.json").read_bytes())["all_county_pairs"])


def load(root=ROOT):
    return qualify(**frozen(root))


if __name__ == "__main__":
    sys.stdout.buffer.write(encoded(load()))
