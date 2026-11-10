"""Package complete held ACS county context without acquisition or reduction."""

import argparse
import json
from pathlib import Path

from participation_intake.context_package import package_county_context


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-store", type=Path, required=True)
parser.add_argument("--native-query", type=Path, required=True)
parser.add_argument("--county-reference", type=Path, required=True)
parser.add_argument("--geometry-root", type=Path)
parser.add_argument("--dataset", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--verification", type=Path)
parser.add_argument("--verifier", type=Path)
args = parser.parse_args()
print(json.dumps(package_county_context(args.source_store, args.native_query,
    args.county_reference, args.dataset, args.output,
    args.geometry_root, args.verification, args.verifier)))
