"""Publish a verified data version without rebuilding or committing the website."""

import argparse
import json
from pathlib import Path

from participation_intake.publisher import GitPublisher


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--dataset", type=Path, required=True)
parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument("--proof", type=Path, required=True)
args = parser.parse_args()
result = GitPublisher(args.repository).publish(args.dataset)
args.proof.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
