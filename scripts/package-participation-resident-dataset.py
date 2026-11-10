"""Package a complete reproducible resident runtime and its accepted full science."""

import argparse
import json
from pathlib import Path

from participation_intake.dataset_package import package_resident_dataset


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--runtime", type=Path, required=True)
parser.add_argument("--science", type=Path, required=True)
parser.add_argument("--native-intake", type=Path, required=True)
parser.add_argument("--native-proof", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
print(json.dumps(package_resident_dataset(
    args.runtime, args.science, args.native_intake, args.native_proof, args.output)))
