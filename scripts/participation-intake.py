"""Ingest any registered source through the canonical participation pipeline."""

import argparse
import json
from pathlib import Path
import sys

from participation_intake.contract import IntakeError, encoded, schema
from participation_intake.engine import Store, run
from participation_intake.references import register


ROOT = Path(__file__).resolve().parents[1]


def named_paths(values):
    result = {}
    for value in values:
        if "=" not in value:
            raise IntakeError("input_argument", "Use a registered input ID followed by = and its original path")
        name, path = value.split("=", 1)
        if name in result:
            raise IntakeError("input_argument", "Duplicate supplied input ID")
        result[name] = Path(path)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["ingest", "register-references", "schema"])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--geometry", action="append", default=[])
    args = parser.parse_args()
    store = None
    try:
        if args.command == "schema":
            body = encoded(schema())
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open("xb") as target:
                    target.write(body)
            else:
                sys.stdout.buffer.write(body)
            return 0
        if not args.source:
            parser.error("--source is required for intake/reference registration")
        spec = json.loads(args.source.read_bytes())
        if args.command == "register-references":
            if not args.output:
                parser.error("--output is required for reference registration")
            result = register(spec["reference_registration"],
                {name: path.read_bytes() for name, path in named_paths(args.geometry).items()})
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("xb") as target:
                target.write(encoded(result))
            sys.stdout.buffer.write(encoded(dict(registered=True, identities=len(result["identities"]),
                parents=len(result["parents"]), output=str(args.output))))
            return 0
        if not args.work_dir:
            parser.error("--work-dir is required for intake")
        refs = json.loads((ROOT / spec["references"]).read_bytes()) if spec.get("references") else {}
        store = Store(args.work_dir)
        result = run(spec, store, supplied=named_paths(args.input), references=refs,
            geometry_inputs={name: path.read_bytes() for name, path in named_paths(args.geometry).items()})
        sys.stdout.buffer.write(encoded(result))
        return 0 if result["status"] != "rejected" else 2
    except IntakeError as error:
        sys.stdout.buffer.write(encoded(dict(status="rejected", errors=[error.as_dict()])))
        return 2
    finally:
        if store:
            store.db.close()


if __name__ == "__main__":
    raise SystemExit(main())
