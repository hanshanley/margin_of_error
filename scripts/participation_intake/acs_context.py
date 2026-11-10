"""Direct ACS table-based adapter for resident context, never voter participation."""

import csv
import hashlib
import json
from pathlib import Path
import re

from .contract import IntakeError


TABLES = {"B19013": 1, "B03002": 21, "B19001": 17, "B15003": 25, "B01001": 49}
STATE_FIPS = set("01 02 04 05 06 08 09 10 11 12 13 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56".split())
JAM_VALUES = {
    "-666666666": "estimate_not_computable",
    "-999999999": "insufficient_sample_cases",
    "-888888888": "not_applicable_or_not_available",
    "-222222222": "moe_not_computable",
    "-333333333": "open_ended_median_interval",
    "-555555555": "controlled_estimate_no_sampling_moe",
}
RACE_GROUPS = [
    ("nh_white", "Non-Hispanic White alone", 3),
    ("nh_black", "Non-Hispanic Black alone", 4),
    ("nh_aian", "Non-Hispanic American Indian / Alaska Native alone", 5),
    ("nh_asian", "Non-Hispanic Asian alone", 6),
    ("nh_nhpi", "Non-Hispanic Native Hawaiian / Pacific Islander alone", 7),
    ("nh_other", "Non-Hispanic some other race alone", 8),
    ("nh_multiracial", "Non-Hispanic two or more races", 9),
    ("hispanic_any_race", "Hispanic / Latino, any race", 12),
]


def native_value(literal):
    if literal in JAM_VALUES:
        return None, JAM_VALUES[literal]
    if not re.fullmatch(r"\d+", literal, re.ASCII):
        raise IntakeError("context_value", "Unrecognized ACS value; do not infer missing as zero")
    return int(literal), "native_numeric"


def cell(estimate, moe, median=False):
    value, status = native_value(estimate)
    uncertainty, moe_status = native_value(moe)
    result = dict(estimate=value, margin_of_error=uncertainty,
        native_estimate_literal=estimate, native_moe_literal=moe,
        estimate_status=status, moe_status=moe_status, bounded=False)
    if median and value in (2499, 250001):
        result.update(estimate=None, bounded=True,
            lower_bound=250000 if value == 250001 else None,
            upper_bound=2500 if value == 2499 else None,
            estimate_status="open_ended_income_median")
    return result


def parse_table(path, table):
    count = TABLES[table]
    selected, all_rows, excluded_territory_rows = {}, 0, 0
    expected = {"GEO_ID"} | {f"{table}_{kind}{i:03d}" for kind in ("E", "M") for i in range(1, count+1)}
    with Path(path).open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source, delimiter="|", strict=True)
        if set(reader.fieldnames or []) != expected:
            raise IntakeError("context_schema", "ACS complete table header differs: " + table)
        for row in reader:
            all_rows += 1
            if None in row or any(value is None for value in row.values()):
                raise IntakeError("context_schema", "Incomplete ACS source row")
            native_geo = row["GEO_ID"]
            if not native_geo.startswith("0500000US"):
                continue
            geoid = native_geo.removeprefix("0500000US")
            if not re.fullmatch(r"\d{5}", geoid, re.ASCII):
                raise IntakeError("context_geography", "Invalid native Census county GEO_ID")
            if geoid[:2] not in STATE_FIPS:
                excluded_territory_rows += 1
                continue
            if geoid in selected:
                raise IntakeError("context_geography", "Duplicate native county identity")
            selected[geoid] = {f"{i:03d}": cell(row[f"{table}_E{i:03d}"], row[f"{table}_M{i:03d}"],
                median=table == "B19013") for i in range(1, count+1)}
    return selected, dict(source_rows=all_rows, selected_counties=len(selected),
        territory_county_rows_excluded=excluded_territory_rows)


def total(cells, indices):
    parts = [cells[f"{i:03d}"]["estimate"] for i in indices]
    return sum(parts) if all(value is not None for value in parts) else None


def percent(value, denominator):
    return 100*value/denominator if value is not None and denominator is not None and denominator > 0 else None


def county_record(geoid, tables):
    return dict(geography=dict(level="county", census_geoid=geoid, state_fips=geoid[:2],
        native_geo_id="0500000US"+geoid, source_geography_vintage=2024), **resident_metrics(tables))


def resident_metrics(tables):
    race, age, education, income = (tables[key] for key in ("B03002", "B01001", "B15003", "B19001"))
    population = race["001"]["estimate"]
    groups = []
    for key, label, index in RACE_GROUPS:
        source = race[f"{index:03d}"]
        groups.append(dict(id=key, label=label, **source, percent=percent(source["estimate"], population),
            percentage_moe=None, percentage_moe_not_derived=True))
    race_values = [row["estimate"] for row in groups]
    race_residual = sum(race_values)-population if population is not None and all(
        value is not None for value in race_values) else None
    age_total = age["001"]["estimate"]
    under18 = total(age, [*range(3, 7), *range(27, 31)])
    age65 = total(age, [*range(20, 26), *range(44, 50)])
    age18_64 = total(age, [*range(7, 20), *range(31, 44)])
    edu_total = education["001"]["estimate"]
    bachelors = total(education, range(22, 26))
    household_total = income["001"]["estimate"]
    bins = {key: value for key, value in income.items() if key != "001"}
    income_total = total(income, range(2, 18))
    conflicts = []
    if population is not None and age_total is not None and population != age_total:
        conflicts.append(dict(code="published_population_totals_differ", race_total=population, age_total=age_total))
    if race_residual:
        conflicts.append(dict(code="published_race_partition_residual", residual=race_residual, repaired=False))
    if all(value is not None for value in (age_total, under18, age18_64, age65)):
        age_residual = under18+age18_64+age65-age_total
        if age_residual:
            conflicts.append(dict(code="published_age_partition_residual", residual=age_residual, repaired=False))
    if household_total is not None and income_total is not None and household_total != income_total:
        conflicts.append(dict(code="published_income_bin_residual", residual=income_total-household_total, repaired=False))
    return dict(resident_population=dict(race["001"]), median_household_income=dict(
            tables["B19013"]["001"], unit="2024_USD", universe="households"),
        race_ethnicity=dict(universe="all_residents", mutually_exclusive=True, groups=groups,
            source_partition_residual=race_residual),
        age=dict(universe="all_residents", source_total=age_total,
            groups=[dict(id=key, estimate=value, percent=percent(value, age_total),
                derived_moe=None) for key, value in (
                    ("under18", under18), ("18_64", age18_64), ("65plus", age65))]),
        education=dict(universe="residents_age25plus", source_total=edu_total,
            bachelors_or_higher=bachelors, bachelors_or_higher_pct=percent(bachelors, edu_total),
            derived_moe=None),
        household_income_distribution=dict(universe="households", source_total=household_total,
            bins=bins, source_bin_residual=income_total-household_total
                if income_total is not None and household_total is not None else None,
            median_never_averaged_or_allocated=True),
        native_tables=tables, conflicts=conflicts, values_repaired=False,
        resident_composition_is_not_voter_composition=True, voter_participation_rate=None,
        precinct_estimates=None)


def build_county_context(source_store):
    root = Path(source_store)
    parsed, sources, inventories = {}, {}, {}
    for table in TABLES:
        receipt = json.loads((root / (table+"-receipt.json")).read_bytes())
        path = root / "objects" / receipt["sha256"]
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024*1024), b""):
                digest.update(block)
        if path.stat().st_size != receipt["bytes"] or digest.hexdigest() != receipt["sha256"]:
            raise IntakeError("context_original_hash", "Held complete Census original differs")
        parsed[table], inventories[table] = parse_table(path, table)
        sources[table] = receipt
    keys = set(parsed["B19013"])
    if any(set(values) != keys for values in parsed.values()):
        raise IntakeError("context_geography", "ACS table county identities differ; no partial silent join")
    rows = [county_record(key, {table: parsed[table][key] for table in TABLES}) for key in sorted(keys)]
    return dict(contract="geographic.resident_context.v1", source_product="ACS 2020-2024 five-year",
        source_period="2020-2024", income_dollar_year=2024,
        geography_scope="50_states_and_DC_native_Census_counties",
        records=rows, sources=sources, full_original_inventories=inventories,
        source_geometry_reacquired=False, election_year=None, source_is_election_data=False,
        source_geography_matched_to_loaded_reference=False,
        precinct_crosswalk_not_yet_qualified=True,
        limitations=[
            "Resident context is not voter composition, group turnout or individual vote choice.",
            "County GEO_IDs are native 2024 ACS identifiers; loaded-map code and boundary compatibility need separate checks.",
            "Native MOEs, controlled/suppressed values and open-ended income medians stay explicit.",
            "Derived sums/percentages have no newly inferred MOE or confidence interval.",
            "Income medians are never averaged into another geography.",
            "No county/precinct demographic or voting count is filled from a state estimate."])
