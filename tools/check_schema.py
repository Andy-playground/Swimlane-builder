#!/usr/bin/env python3
"""CI-only: validate every examples/*.spec.json against the normative
schema with the real `jsonschema` — the check that catches drift between
`schema/spec.schema.json` and the hand-rolled `validate._shape`.

Requires the dev-only `jsonschema` package; the runtime never imports this.
"""
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    schema = json.loads((ROOT / "schema" / "spec.schema.json").read_text("utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    failed = False
    for spec_path in sorted(ROOT.glob("examples/*.spec.json")):
        errors = sorted(validator.iter_errors(json.loads(spec_path.read_text("utf-8"))),
                        key=lambda e: e.json_path)
        for e in errors:
            print(f"{spec_path.name}: {e.json_path}: {e.message}", file=sys.stderr)
        failed = failed or bool(errors)
        print(f"{'FAIL' if errors else 'ok  '} {spec_path.name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
