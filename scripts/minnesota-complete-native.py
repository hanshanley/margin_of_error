"""Reproduce the newly complete Minnesota statistics using unchanged native references."""

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "data/county-source-reviews/20261110-minnesota-complete-native-03"
FIELDS = ("state", "county_id", "precinct_id", "precinct_name", "has_reported_statistics",
    "registered_7am", "registered_election_day", "roster_signatures",
    "regular_military_overseas_absentee", "federal_only_absentee",
    "president_only_absentee", "total_number_voted")
DOWNLOAD = ("https://github.com/hanshanley/margin_of_error/releases/download/"
            "voter-minnesota-complete-native-statistics-20261110-03/complete-analysis.zip")
OLD_VERSION = "data/county-source-reviews/20261110-minnesota-followup-02"


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n").encode()


def pin(body):
    return dict(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def after(texts, label):
    matches = [index for index, value in enumerate(texts) if value.strip() == label]
    if len(matches) != 1:
        raise ValueError("Missing or duplicated native page label: " + label)
    return texts[matches[0] + 1]


def native(body):
    rows = list(csv.reader(io.StringIO(body.decode("utf-8-sig")), delimiter=";"))
    if len(rows) != 4105 or any(len(row) != 12 or row[0] != "MN" or row[4] != "1" for row in rows):
        raise ValueError("New snapshot must contain every explicitly reported native statistics row")
    result = []
    for row in rows:
        if any(not value.isascii() or not value.isdecimal() or int(value) > 2**53 - 1 for value in row[5:]):
            raise ValueError("Invalid native unsigned safe count")
        result.append(dict(zip(FIELDS, [*row[:5], *map(int, row[5:])])))
    if len({(row["county_id"], row["precinct_id"]) for row in result}) != 4105:
        raise ValueError("Duplicated native county/precinct identity")
    return result


def load(root=ROOT):
    source = root / VERSION
    inputs = json.loads((source / "inputs.json").read_bytes())
    bodies = {}
    for name, expected in inputs["files"].items():
        body = (source / name).read_bytes()
        if pin(body) != expected:
            raise ValueError("Changed complete sufficient input: " + name)
        bodies[name] = body
    with zipfile.ZipFile(io.BytesIO(bodies["baseline-complete-native-analysis.zip"])) as archive:
        previous = json.loads(archive.read("queries.json"))
        prior_geometry = json.loads(gzip.decompress(archive.read("MN.geojson.gz")))
        prior_reference = json.loads(archive.read("precinct-reference-queries.json"))
        inherited_manifest = json.loads(archive.read("manifest.json"))
        for name, expected in inherited_manifest["files"].items():
            if pin(archive.read(name)) != expected:
                raise ValueError("Changed nested complete original: " + name)
    current = native(bodies["originals/pctstats.txt"])
    receipt = json.loads(bodies["originals/pctstats.txt.receipt.json"])
    if receipt["status"] != 200 or pin(bodies["originals/pctstats.txt"]) != {
            key: receipt[key] for key in ("bytes", "sha256")}:
        raise ValueError("Native original and one-request receipt disagree")
    page = json.loads(bodies["official-page-factual-fields.json"])
    clock = page["native_update_clock_literal"]
    if clock != "11/10/26 8:08 AM" or page["timezone"] is not None:
        raise ValueError("Changed native clock; receipt times are not update clocks")
    old_units = {(row["native_county_id"], row["native_precinct_id"]): row
                 for row in previous["all4105_native_precinct_decisions"]}
    old_counties = {row["native_county_id"]: row for row in previous["complete_county_decisions"]}
    if len(old_units) != 4105 or len(old_counties) != 87:
        raise ValueError("Changed previous qualified identity universe")
    units = []
    for row in current:
        identity = row["county_id"], row["precinct_id"]
        old = old_units.get(identity)
        if old is None or old["native_precinct_name"] != row["precinct_name"]:
            raise ValueError("Changed native identity/name; no inferred alias or geographic reassignment")
        units.append(dict(native_county_id=identity[0], county=old["county"], county_fips=old["county_fips"],
            native_precinct_id=identity[1], native_precinct_name=row["precinct_name"],
            reported_statistics=True, total_number_voted=row["total_number_voted"],
            native_component_residual=row["total_number_voted"] - sum(row[key] for key in FIELDS[7:11]),
            native_electorate_excess=row["total_number_voted"] - row["registered_7am"] - row["registered_election_day"],
            source_record=row, newly_reported=not old["reported_statistics"],
            source_count_change_from_observed=None if old["total_number_voted"] is None
                else row["total_number_voted"] - old["total_number_voted"],
            precinct_analysis_rate=None))
    counties, comparisons = [], []
    for identity, old in old_counties.items():
        selected = [row for row in units if row["native_county_id"] == identity]
        if len(selected) != old["reference_precincts"]:
            raise ValueError("Changed native per-county inventory")
        total = sum(row["total_number_voted"] for row in selected)
        registered_7am = sum(row["source_record"]["registered_7am"] for row in selected)
        registered_day = sum(row["source_record"]["registered_election_day"] for row in selected)
        registered = registered_7am + registered_day
        conflicts = sum(row["native_component_residual"] != 0 for row in selected)
        excesses = sum(row["native_electorate_excess"] > 0 for row in selected)
        qualified = registered > 0 and conflicts == 0 and excesses == 0
        native_record = dict(native_county_id=identity, county_name=old["county"],
            all_statistics_reported=True, source_precincts=len(selected),
            total_number_voted=total, registered_7am=registered_7am, registered_election_day=registered_day,
            native_component_conflicts=conflicts, native_electorate_excesses=excesses,
            source_clock_literal=clock, source_timezone=None)
        counties.append(dict(native_county_id=identity, county=old["county"], county_fips=old["county_fips"],
            reference_county_name=old["reference_county_name"], reported_statistics=len(selected),
            reference_precincts=len(selected), missing_statistics=0, all_statistics_reported=True,
            complete_total_number_voted=total, complete_registration_frame=registered,
            registration_fraction=total / registered if qualified else None,
            registration_fraction_eligible=qualified, native_component_conflicts=conflicts,
            native_electorate_excesses=excesses, native_record=native_record))
        comparisons.append(dict(native_county_id=identity, county=old["county"],
            previous_complete=old["all_statistics_reported"], current_complete=True,
            previous_reported_statistics=old["reported_statistics"], current_reported_statistics=len(selected),
            previous_complete_count=old["complete_total_number_voted"], current_complete_count=total,
            previous_reported_subtotal=old["reported_total_number_voted_subtotal"],
            reported_subtotal_change=total - old["reported_total_number_voted_subtotal"],
            newly_complete=not old["all_statistics_reported"]))
    by_id = {(row["native_county_id"], row["native_precinct_id"]): row for row in units}
    features, reference_rows = [], []
    previous_reference_rows = {row["native_vtdid"]: row for row in prior_reference["all4105_reference_decisions"]}
    for feature in prior_geometry["features"]:
        prop = feature["properties"]
        row = by_id[prop["native_county_id"], prop["native_precinct_id"]]
        previous_reference = previous_reference_rows[prop["reference_geometry"]["native_vtdid"]]
        if pin(encoded(feature["geometry"]))["sha256"] != previous_reference["source_geometry_sha256"]:
            raise ValueError("Changed original native geometry; no repair or repeat intersection reduction")
        properties = dict(prop, source_snapshot="20261110-minnesota-complete-native-03",
            ballots=row["total_number_voted"], native_record=row["source_record"], source_count_qualified=True,
            source_update_label=f"Native results-page update{clock}; timezone unknown. Receipt time is separate.",
            source_reporting_label="All4105 native statistics rows explicitly report. "
                "Component conflicts, electorate excesses and reported zeros remain literal and unrepaired. "
                "Full unchanged September18,2026 native references, not certified election-day legal boundaries.")
        features.append(dict(type="Feature", properties=properties, geometry=feature["geometry"]))
        reference_rows.append(dict(previous_reference, source_count=row["total_number_voted"],
            source_reported=True, analysis_rate=None, full_coordinates_equal_previously_verified_original=True))
    summary = dict(native_counties=87, native_precinct_rows=4105, reported_statistics=4105,
        missing_statistics=0, complete_counties=87, partial_counties=0, newly_complete_counties=3,
        newly_reported_statistics=sum(row["newly_reported"] for row in units),
        derived_complete_total_number_voted=sum(row["complete_total_number_voted"] for row in counties),
        independently_printed_state_count=None,
        separate_source_page_estimated_voters=int(after(page["source_text"], "Estimated Voters:").replace(",", "")),
        separate_source_page_estimated_turnout=after(page["source_text"], "Estimated Turnout:"),
        source_page_registered_7am=int(after(page["source_text"], "Voters Registered at 7AM:").replace(",", "")),
        qualified_registration_fractions=sum(row["registration_fraction_eligible"] for row in counties),
        native_component_conflicts=sum(row["native_component_residual"] != 0 for row in units),
        native_precinct_electorate_excesses=sum(row["native_electorate_excess"] > 0 for row in units),
        explicit_reported_zero_rows=sum(row["total_number_voted"] == 0 for row in units),
        source_native_clock=clock, source_native_timezone=None, source_status="Unofficial Results",
        source_numerator_literal="Total Number Voted", source_counts_repaired=False,
        unique_people_qualified=False, precinct_analysis_rates=0,
        reference_coordinates_changed=False, new_geometry_acquisitions=0,
        prior_pair_decisions_reused_without_reduction=len(prior_reference["all_bbox_candidate_pair_decisions"]))
    if (summary["derived_complete_total_number_voted"] != 2852618
            or summary["qualified_registration_fractions"] != 73
            or summary["newly_reported_statistics"] != 26):
        raise ValueError("Changed newly complete native source qualification")
    if (sum(row["native_record"]["registered_7am"] for row in counties) != summary["source_page_registered_7am"]
            or summary["separate_source_page_estimated_voters"] != summary["derived_complete_total_number_voted"]):
        raise ValueError("New native statistics and separate page controls disagree")
    return dict(summary=summary, complete_county_decisions=counties, all4105_native_precinct_decisions=units,
        complete87_previous_current_comparisons=comparisons, county_reference=previous["county_reference"],
        full_unchanged_coordinate_feature_collection=dict(type="FeatureCollection", features=features),
        all4105_native_reference_decisions=reference_rows,
        all_bbox_candidate_pair_decisions=prior_reference["all_bbox_candidate_pair_decisions"],
        official_page_factual_fields=page)
