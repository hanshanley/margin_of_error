"""Package complete held conditional resident context without reacquisition."""

import argparse
import json
from pathlib import Path

from participation_intake.precinct_package import package_precinct_context


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--results", type=Path, required=True)
parser.add_argument("--site-root", type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument("--blocks-root", type=Path, required=True)
parser.add_argument("--database", type=Path, required=True)
parser.add_argument("--county-packet", type=Path, required=True)
parser.add_argument("--county-verification", type=Path, required=True)
parser.add_argument("--verification", type=Path, required=True)
parser.add_argument("--verifier", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
print(json.dumps(package_precinct_context(args.results, args.site_root, args.blocks_root,
    args.database, args.county_packet, args.county_verification, args.verification, args.verifier, args.output)))
