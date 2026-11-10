"""Conditional small-area resident estimates, never survey-to-precinct allocation."""

from collections import defaultdict
from fractions import Fraction
import json
from pathlib import Path
import sqlite3

from .acs_context import TABLES, cell, resident_metrics
from .contract import IntakeError


INCOME_BOUNDS = [0, 10000, 15000, 20000, 25000, 30000, 35000, 40000,
    45000, 50000, 60000, 75000, 100000, 125000, 150000, 200000, None]


def json_numbers(value):
    if isinstance(value, Fraction):
        return float(value)
    if isinstance(value, dict):
        return {key: json_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_numbers(item) for item in value]
    return value


def median_band(table):
    values = [table[f"{index:03d}"]["estimate"] for index in range(2, 18)]
    if any(value is None for value in values) or sum(values) <= 0:
        return None
    half, cumulative = sum(values)/2, Fraction(0)
    for i, value in enumerate(values):
        cumulative += value
        if cumulative >= half:
            upper = INCOME_BOUNDS[i+1]
            if cumulative == half:
                following = next((j for j in range(i+1, len(values)) if values[j] > 0), None)
                if following is not None:
                    upper = INCOME_BOUNDS[following+1]
            return dict(lower_bound=INCOME_BOUNDS[i], upper_bound=upper,
                unit="2024_USD", status="modeled_income_bin_interval_not_exact_median")


def estimate_context(crosswalk, database):
    connection = sqlite3.connect("file:" + str(Path(database).resolve()) + "?mode=ro", uri=True)
    cache, by_reference = {}, defaultdict(list)
    for link in crosswalk["links"]:
        by_reference[link["reference_key"]].append(link)
    if "reference_keys" not in crosswalk and crosswalk.get("qualified_reference_features", len(by_reference)) != len(by_reference):
        raise IntakeError("context_coverage", "Supply every approved reference key, including units without proxy points")
    for key in crosswalk.get("reference_keys", []):
        by_reference[key]
    records = []
    try:
        for key, links in sorted(by_reference.items()):
            sums = {table: {f"{i:03d}": Fraction(0) for i in range(1, count+1)}
                    for table, count in TABLES.items()}
            unknown, used, missing = set(), set(), set()
            positive = {"population": False, "housing": False}
            for link in links:
                bg = link["census_2020_block_group"]
                if bg not in cache:
                    raw = connection.execute(
                        "SELECT table_id,native_pairs FROM cells WHERE geoid=?", (bg,)).fetchall()
                    cache[bg] = {table: {f"{i:03d}": cell(*pair, median=table == "B19013")
                        for i, pair in enumerate(json.loads(pairs), 1)} for table, pairs in raw}
                native = cache[bg]
                if set(native) != set(TABLES):
                    missing.add(bg)
                    continue
                used.add(bg)
                for table in TABLES:
                    if table == "B19013":
                        continue
                    family = "housing" if table == "B19001" else "population"
                    literal = link["housing_proxy_fraction" if family == "housing" else "population_fraction"]
                    if literal is None:
                        if link["assigned_housing_units" if family == "housing" else "assigned_population"] > 0:
                            unknown.update((table, variable) for variable in sums[table])
                        continue
                    weight = Fraction(literal)
                    if not 0 <= weight <= 1:
                        raise IntakeError("context_weight", "Proxy fractions must be between zero and one")
                    if weight <= 0:
                        continue
                    positive[family] = True
                    for variable, source in native[table].items():
                        value = source["estimate"]
                        if value is None:
                            unknown.add((table, variable))
                        else:
                            sums[table][variable] += weight*value
            tables, exact = {}, {}
            for table, values in sums.items():
                tables[table], exact[table] = {}, {}
                family = "housing" if table == "B19001" else "population"
                for variable, value in values.items():
                    held = table == "B19013" or missing or not positive[family] or (table, variable) in unknown
                    estimate = None if held else value
                    tables[table][variable] = dict(estimate=estimate, margin_of_error=None,
                        estimate_status="model_withheld" if held else "modeled_small_area_estimate",
                        moe_status="not_derived", native_estimate_literal=None, native_moe_literal=None, bounded=False)
                    exact[table][variable] = None if held else str(value)
            metrics = resident_metrics(tables)
            metrics.pop("native_tables")
            for family in ("age", "education", "household_income_distribution"):
                metrics[family]["estimated_universe"] = metrics[family].pop("source_total")
            metrics.update(geography=dict(level="precinct_reference", reference_key=key,
                state_code=crosswalk["state_code"]), context_status="conditional_population_proxy_estimate",
                source_period="2020-2024", income_dollar_year=2024, weight_year=2020,
                modeled_income_median_band=median_band(tables["B19001"]),
                exact_weighted_source_cells=exact, source_block_groups=sorted(used),
                missing_2024_block_groups=sorted(missing),
                population_proxy_available=positive["population"], housing_proxy_available=positive["housing"],
                source_block_group_code_equivalence_is_assumption=True,
                income_medians_averaged=False, resident_composition_is_not_voter_composition=True,
                source_geometry_repaired=False)
            records.append(json_numbers(metrics))
    finally:
        connection.close()
    return dict(contract="geographic.resident_context.v1", state_code=crosswalk["state_code"],
        records=records, source_period="2020-2024", weight_year=2020, income_dollar_year=2024,
        not_administrative_or_voter_demographics=True,
        limitations=crosswalk["limitations"] + [
            "Matching 2020/2024 block-group codes is a geographic equivalence assumption, not boundary certification.",
            "2024 demographic composition is assumed uniform over each block group's 2020 population proxy.",
            "Age25+ uses the all-age population proxy; occupied households use housing-unit proxies.",
            "Income is an interval from weighted income bins, never an average of source medians.",
            "No new sampling MOE or confidence interval is inferred. Unknown source cells stay unknown."])
