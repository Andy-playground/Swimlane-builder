# Development

For people changing the generator. To use the tool, see the [usage guide](USAGE.md).

The runtime is Python 3.11 or later with the standard library only. Two developer tools need
more: `check_schema.py` needs `pip install jsonschema`, and `preview.py` needs Chromium.

## Commands

```bash
python3 tests/test_all.py                                 # full suite: lint rules, geometry, golden XML
python3 tests/test_all.py TestXml.test_golden_snapshot    # one test or class
python3 tools/check_schema.py                             # examples vs. the JSON Schema
python3 tools/preview.py out.drawio -o shots/out.png      # render a .drawio to PNG without draw.io
python3 tools/build_skill.py                              # assemble the Skill zip and print its SHA-256
python3 tools/showreel/render.py                          # re-render the overview film (needs Node + Playwright, ffmpeg, numpy, Inter)
```

`tools/preview.py` approximates draw.io's renderer. It is evidence about the computed
geometry, not a replacement for opening the file in draw.io.

## Code layout

The pipeline is spec → theme → lint → layout → XML, and each stage has one module in
`src/swimlane_builder/`:

| Module | Role |
|---|---|
| `cli.py` | Loads the spec and theme, then calls `validate.lint`, `layout.compute` and `xmlgen.emit` |
| `validate.py` | Hand-rolled schema check plus semantic lint; returns `[(code, message)]` |
| `layout.py` | Pure geometry: columns, sizes, lane heights, ports, routes, label placement |
| `xmlgen.py` | Writes mxGraph XML from the layout; computes nothing |
| `themes.py` | Loads `themes/*.json` |

Elsewhere in the repository:

| Path | Role |
|---|---|
| `swimlane-builder.py` | Launcher for the CLI |
| `schema/spec.schema.json` | The JSON Schema of the spec |
| `themes/` | Colors, fonts and spacing as data |
| `prompts/extract_spec.md` | The extraction instructions an AI model follows |
| `SKILL.md` | The instructions an agent follows when the repository is used as a Skill |
| `examples/` | Specs with their generated diagrams; these are also the golden files for the tests |
| `tools/` | Developer tools, plus `docx2txt.py`, which ships in the Skill |
| `tools/showreel/` | Source of the overview film in `docs/media/`: a page drawn from the generator's own layout, stepped frame by frame, and a synthesized soundtrack |

`SKILL.md` and `prompts/extract_spec.md` are written for an AI model to follow, not as
documentation for people. Both ship in the Skill zip, so editing either changes the model's
behavior and the zip's SHA-256.

## Rules that keep it working

1. **Keep the stages apart.** `layout.py` never knows about XML; `xmlgen.py` never computes
   geometry. New geometry goes in layout, new styling in a theme file, new markup in xmlgen.
2. **Determinism is tested byte for byte.** `test_golden_snapshot` regenerates every
   `examples/*.spec.json` and compares it with the committed `.drawio`. After an intentional
   output change, regenerate them, review the diff, and open them in draw.io before
   committing:

   ```bash
   python3 swimlane-builder.py generate examples/<name>.spec.json -o examples/<name>.drawio
   ```

3. **The schema lives in two places.** `schema/spec.schema.json` and `validate._shape`, so
   that the runtime stays standard-library only. Change one, change the other. CI runs
   `check_schema.py` to catch drift. The schema is also copied into
   `prompts/extract_spec.md`.
4. **The font is pinned.** Box widths are computed from a Helvetica 14 text metric in the
   theme, so every style must carry `fontFamily` and `fontSize`. Otherwise the reader's
   draw.io re-flows the text.
5. **Every lint code has a failing fixture** in `tests/test_all.py`.
6. **The lint codes are documented twice.** [CODES.md](CODES.md) and
   [CODES-zh.md](CODES-zh.md); change both together.

## Releases

Pushing a `v*` tag, or publishing a release in the GitHub web UI, runs
`.github/workflows/release.yml`. The tag must match `__version__` in
`src/swimlane_builder/__init__.py`. The workflow runs the test suite, builds the Skill zip,
and attaches it, its SHA-256 and the showreel to the release. The zip is deterministic: the same
tree always produces the same bytes.
