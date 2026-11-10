"""Reproduce the held Minnesota county/precinct decisions without proxy votes."""

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-minnesota-followup-02"
FIELDS = ("state", "county_id", "precinct_id", "precinct_name", "has_reported_statistics",
    "registered_7am", "registered_election_day", "roster_signatures",
    "regular_military_overseas_absentee", "federal_only_absentee",
    "president_only_absentee", "total_number_voted")


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n").encode()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def county_name(value):
    return value.removesuffix(" County").casefold()


def number(value):
    if not value.isascii() or not value.isdecimal() or int(value) > 2**53 - 1:
        raise ValueError("Invalid native unsigned safe count")
    return int(value)


def native(body):
    rows = list(csv.reader(io.StringIO(body.decode("utf-8-sig")), delimiter=";"))
    if len(rows) != 4105 or any(len(row) != 12 or row[0] != "MN" or row[4] not in ("0", "1") for row in rows):
        raise ValueError("Changed original native statistics schema")
    return [dict(zip(FIELDS, [*row[:5], *map(number, row[5:])])) for row in rows]


def review(bodies):
    current = native(bodies["originals/pctstats.txt"])
    previous = native(bodies["originals/previous-pctstats.txt"])
    counties = list(csv.reader(io.StringIO(bodies["reused-frozen-originals/counties.txt"].decode("utf-8-sig")), delimiter=";"))
    precincts = list(csv.reader(io.StringIO(bodies["reused-frozen-originals/precincts.txt"].decode("utf-8-sig")), delimiter=";"))
    references = {(row[0], row[1]): row for row in precincts}
    if (len(counties) != 87 or len({row[0] for row in counties}) != 87
            or len(references) != len(precincts) or len(precincts) != 4105):
        raise ValueError("Changed native reference universe")
    for rows in [current, previous]:
        seen = set()
        for row in rows:
            key = row["county_id"], row["precinct_id"]
            if key in seen or key not in references or row["precinct_name"] != references[key][2]:
                raise ValueError("Duplicate or unmatched county-scoped native precinct")
            seen.add(key)
        if seen != references.keys():
            raise ValueError("Incomplete native statistics inventory")
    shapes = json.loads(gzip.decompress(bodies["MN-county-reference.geojson.gz"]))["features"]
    reference = json.loads(bodies["county-reference.json"])
    if len(shapes) != 87 or reference["boundary_year"] != 2026 or reference["certified_election_boundaries"] is not False:
        raise ValueError("Changed full county reference")
    by_name = {}
    for feature in shapes:
        p = feature["properties"]
        key = county_name(p["name"])
        if p["state_code"] != "MN" or p["boundary_year"] != 2026 or key in by_name:
            raise ValueError("Duplicate/wrong-vintage county context")
        by_name[key] = p
    if (len({row["key"] for row in by_name.values()}) != 87
            or any(not row["key"].startswith("27") or len(row["key"]) != 5 for row in by_name.values())):
        raise ValueError("Invalid explicit Census county identity")
    approved = {row["native_county_id"]: row for row in csv.DictReader(
        io.StringIO(bodies["county-participation-current.csv"].decode()))}
    if len(approved) != 87:
        raise ValueError("Incomplete previously qualified full query")
    decisions, units, comparisons = [], [], []
    for county_id, name, declared in counties:
        if county_name(name) not in by_name or approved[county_id]["county_name"] != name:
            raise ValueError("Unmatched source/Census county name")
        county_reference = by_name[county_name(name)]
        fips = county_reference["key"]
        all_rows = [row for row in current if row["county_id"] == county_id]
        old_all = [row for row in previous if row["county_id"] == county_id]
        reported = [row for row in all_rows if row["has_reported_statistics"] == "1"]
        old_reported = [row for row in old_all if row["has_reported_statistics"] == "1"]
        if len(all_rows) != len(old_all) or len(all_rows) != number(declared):
            raise ValueError("Changed per-county native inventory")
        complete = len(reported) == len(all_rows)
        total = sum(row["total_number_voted"] for row in reported)
        old_total = sum(row["total_number_voted"] for row in old_reported)
        registrations = sum(row["registered_7am"] + row["registered_election_day"] for row in reported)
        conflicts, excesses = 0, 0
        for row in all_rows:
            supplied = row["has_reported_statistics"] == "1"
            residual = row["total_number_voted"] - sum(row[key] for key in FIELDS[7:11])
            excess = row["total_number_voted"] - row["registered_7am"] - row["registered_election_day"]
            conflicts += bool(supplied and residual)
            excesses += bool(supplied and excess > 0)
            units.append(dict(native_county_id=county_id, county=name, county_fips=fips,
                native_precinct_id=row["precinct_id"], native_precinct_name=row["precinct_name"],
                reported_statistics=supplied, total_number_voted=row["total_number_voted"] if supplied else None,
                native_component_residual=residual if supplied else None,
                native_electorate_excess=excess if supplied else None,
                source_record=row, precinct_geometry_approved=False))
        eligible = complete and registrations > 0 and conflicts == 0 and excesses == 0
        supplied = approved[county_id]
        if (supplied["all_statistics_reported"] != str(complete).lower()
                or number(supplied["reported_total_number_voted_subtotal"]) != total
                or number(supplied["reported_statistics"]) != len(reported)
                or number(supplied["precinct_component_conflicts"]) != conflicts
                or number(supplied["precinct_electorate_excesses"]) != excesses
                or supplied["registration_fraction_eligible"] != str(eligible).lower()
                or supplied["native_numerator_label"] != "Total Number Voted"
                or supplied["native_status"] != "Unofficial Results"
                or supplied["native_update_clock"] != "11/07/26 5:18 PM"
                or supplied["native_update_timezone"] != ""):
            raise ValueError("Native counts disagree with the qualified complete query")
        if complete:
            if (number(supplied["complete_total_number_voted"]) != total
                    or number(supplied["complete_derived_7am_plus_election_day_registration"]) != registrations
                    or registrations != number(supplied["complete_registered_7am"]) + number(supplied["complete_registered_election_day"])):
                raise ValueError("Substituted denominator or complete county count")
        elif any(supplied[key] != "" for key in [
                "complete_total_number_voted", "complete_registered_7am", "complete_registered_election_day",
                "complete_derived_7am_plus_election_day_registration"]):
            raise ValueError("Partial statistics must not become a complete county total")
        if (eligible and (total > registrations or
                abs(float(supplied["approved_registration_fraction"]) - total / registrations) > 5.000001e-9)
                or not eligible and supplied["approved_registration_fraction"] != ""):
            raise ValueError("Unqualified or substituted registration fraction")
        decisions.append(dict(native_county_id=county_id, county=name, county_fips=fips,
            reference_county_name=county_reference["name"],
            county_identity_join="case_insensitive_name_and_explicit_County_suffix_NOT_native_ID_as_FIPS",
            reported_statistics=len(reported), reference_precincts=len(all_rows),
            missing_statistics=len(all_rows) - len(reported), all_statistics_reported=complete,
            reported_total_number_voted_subtotal=total, complete_total_number_voted=total if complete else None,
            complete_registration_frame=registrations if complete else None,
            registration_fraction=total / registrations if eligible else None,
            registration_fraction_eligible=eligible, native_component_conflicts=conflicts,
            native_electorate_excesses=excesses, native_record=supplied,
            source_county_id_is_not_fips=True, certified_election_boundaries=False))
        comparisons.append(dict(native_county_id=county_id, county=name,
            previous_reported_statistics=len(old_reported), current_reported_statistics=len(reported),
            previous_complete=len(old_reported) == len(old_all), current_complete=complete,
            previous_reported_subtotal=old_total, current_reported_subtotal=total,
            reported_subtotal_change=total - old_total,
            newly_complete=complete and len(old_reported) != len(old_all)))
    estimated = json.loads(bodies["current-official-web-observation.json"])["official_values"]
    subtotal = sum(row["reported_total_number_voted_subtotal"] for row in decisions)
    if (subtotal != 2827091 or sum(row["reported_statistics"] for row in decisions) != 4079
            or sum(row["all_statistics_reported"] for row in decisions) != 84
            or sum(row["newly_complete"] for row in comparisons) != 9
            or estimated["estimated_voters"] != 2852528 or estimated["counties_complete"] != 87):
        raise ValueError("Changed partial-source/Estimated Voters distinction")
    return dict(summary=dict(native_counties=87, native_precinct_rows=4105, reported_statistics=4079,
        missing_statistics=26, complete_counties=84, partial_counties=3, newly_complete_counties=9,
        reported_total_number_voted_subtotal=subtotal, exact_statewide_total_number_voted=None,
        separate_official_page_estimated_voters=estimated["estimated_voters"],
        qualified_registration_fractions=sum(row["registration_fraction_eligible"] for row in decisions),
        source_native_clock="11/07/26 5:18 PM", source_native_timezone=None,
        source_status="Unofficial Results", source_numerator_literal="Total Number Voted",
        source_counts_repaired=False, candidate_votes_used_as_ballots=False, unique_people_qualified=False,
        precinct_geometry_approved=False, statewide_or_demographic_rate_approved=False),
        complete_county_decisions=decisions, all4105_native_precinct_decisions=units,
        complete87_previous_current_comparisons=comparisons, county_reference=reference)


def load(root=ROOT):
    source = root / VERSION
    inputs = json.loads((source / "inputs.json").read_bytes())
    bodies = {}
    for name, pin in inputs["files"].items():
        body = (source / name).read_bytes()
        if len(body) != pin["bytes"] or digest(body) != pin["sha256"]:
            raise ValueError("Changed sufficient frozen input: " + name)
        bodies[name] = body
    return review(bodies)
