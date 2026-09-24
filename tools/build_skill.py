#!/usr/bin/env python3
"""Dev-only: assemble the Skill bundle, stdlib only.

Zips the runtime set under a top-level `swimlane-builder/` folder. The zip is
deterministic — fixed entry order, fixed timestamp, fixed permissions — so the
same tree always yields the same bytes and the printed SHA-256 can pin a
release. Building twice and comparing is the CI check.
"""
import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFIX = "swimlane-builder/"
# Exactly what the Skill needs — instructions, launcher, generator, data, helper, self-test pair.
RUNTIME_SET = [
    "SKILL.md",
    "swimlane-builder.py",
    "prompts/extract_spec.md",
    "schema/spec.schema.json",
    "src/swimlane_builder/__init__.py",
    "src/swimlane_builder/__main__.py",
    "src/swimlane_builder/cli.py",
    "src/swimlane_builder/layout.py",
    "src/swimlane_builder/themes.py",
    "src/swimlane_builder/validate.py",
    "src/swimlane_builder/xmlgen.py",
    "themes/default.json",
    "themes/classic.json",
    "tools/docx2txt.py",
    "examples/po-confirmation.spec.json",
    "examples/po-confirmation.drawio",
]
STAMP = (2026, 1, 1, 0, 0, 0)  # fixed: a zip timestamp is a determinism leak


def build(out: Path) -> str:
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in sorted(RUNTIME_SET):
            info = zipfile.ZipInfo(PREFIX + rel, date_time=STAMP)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, (ROOT / rel).read_bytes())
    return hashlib.sha256(out.read_bytes()).hexdigest()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="assemble dist/swimlane-builder-skill.zip (deterministic)")
    p.add_argument("-o", "--out", default=str(ROOT / "dist" / "swimlane-builder-skill.zip"))
    a = p.parse_args(argv)
    missing = [rel for rel in RUNTIME_SET if not (ROOT / rel).is_file()]
    if missing:
        print(f"missing from runtime set: {', '.join(missing)}", file=sys.stderr)
        return 2
    out = Path(a.out)
    digest = build(out)
    print(f"{out}\nsha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
