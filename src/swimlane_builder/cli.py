"""Command-line interface. Exit codes: 0 success, 1 validation failure, 2 I/O error."""
import argparse
import json
import sys
from pathlib import Path

from . import layout, themes, validate, xmlgen


def _out_name(spec_path: Path) -> str:
    return spec_path.name.removesuffix(".json").removesuffix(".spec") + ".drawio"


def _generate(spec_path, out_path, theme_name, validate_only=False):
    spec_path = Path(spec_path)
    try:
        text = spec_path.read_text("utf-8")
    except OSError as e:
        print(f"I/O error: {e}", file=sys.stderr)
        return 2
    try:
        spec = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"E001: {spec_path}: invalid JSON — {e}", file=sys.stderr)
        return 1

    name = theme_name or (spec.get("meta", {}).get("theme", "default") if isinstance(spec, dict) else "default")
    try:
        theme = themes.load(name)
    except OSError as e:
        print(f"I/O error: theme '{name}': {e}", file=sys.stderr)
        return 2

    issues = validate.lint(spec, theme)
    for code, msg in issues:
        print(f"{code}: {msg}", file=sys.stderr)
    if any(code.startswith("E") for code, _ in issues):
        return 1

    # W208 is a statement about placed geometry, so it needs the layout the emitter is
    # about to consume — computed here even for --validate-only, where reporting it is
    # the whole point.
    lay = layout.compute(spec, theme)
    for code, msg in validate.lint_layout(spec, theme, lay):
        print(f"{code}: {msg}", file=sys.stderr)
    if validate_only:
        return 0

    xml = xmlgen.emit(spec, lay, theme)
    out = Path(out_path) if out_path else spec_path.parent / _out_name(spec_path)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(xml, "utf-8")
    except OSError as e:
        print(f"I/O error: {e}", file=sys.stderr)
        return 2
    print(out)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="swimlane-builder",
                                description="JSON process spec -> draw.io swimlane diagram (deterministic, stdlib only)")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate one .drawio from a spec")
    g.add_argument("spec")
    g.add_argument("-o", "--out")
    g.add_argument("--theme")
    g.add_argument("--validate-only", action="store_true")

    b = sub.add_parser("batch", help="generate every *.json spec in a directory")
    b.add_argument("specs_dir")
    b.add_argument("-o", "--out", required=True)
    b.add_argument("--theme")

    l = sub.add_parser("lint", help="validate a spec and print issues")
    l.add_argument("spec")

    a = p.parse_args(argv)
    if a.cmd == "generate":
        return _generate(a.spec, a.out, a.theme, a.validate_only)
    if a.cmd == "lint":
        return _generate(a.spec, None, None, validate_only=True)

    specs = sorted(Path(a.specs_dir).glob("*.json"))
    if not specs:
        print(f"I/O error: no *.json specs in {a.specs_dir}", file=sys.stderr)
        return 2
    rc = 0
    for s in specs:
        rc = max(rc, _generate(s, Path(a.out) / _out_name(s), a.theme))
    return rc
