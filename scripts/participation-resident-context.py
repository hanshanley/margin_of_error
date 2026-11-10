"""Reduce held complete ACS originals through the shared resident-context adapter."""

import argparse
import gzip
import json
from pathlib import Path

from participation_intake.acs_context import build_county_context
from participation_intake.contract import encoded, pin


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-store", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    raise ValueError("Refuse to replace an immutable context version")
result = build_county_context(args.source_store)
args.output.mkdir(parents=True)
body = encoded(result)
(args.output / "county-native-context.json.gz").write_bytes(gzip.compress(body, mtime=0))
summary = dict(status="computed_native_county_resident_context_not_yet_map_joined_or_live",
    counties=len(result["records"]), states=len({row["geography"]["state_fips"] for row in result["records"]}),
    source_period=result["source_period"], income_dollar_year=2024,
    full_originals=len(result["sources"]), original_bytes=sum(row["bytes"] for row in result["sources"].values()),
    observed_income_medians=sum(row["median_household_income"]["estimate"] is not None for row in result["records"]),
    bounded_income_medians=sum(row["median_household_income"]["bounded"] for row in result["records"]),
    native_context_query=pin((args.output / "county-native-context.json.gz").read_bytes()),
    conflicts_retained=sum(len(row["conflicts"]) for row in result["records"]),
    resident_context_not_voter_data=True, source_geographic_join_pending=True, precinct_context_pending=True)
(args.output / "summary.json").write_bytes(encoded(summary))
print(json.dumps(summary))
