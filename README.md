# swimlane-builder

**Turn an SOP (standard operating procedure) into a clean draw.io swimlane diagram — the same
input always gives the same picture.**

An LLM reads the SOP and writes down *what* happens — who does which step, where the flow
branches, which steps loop back — as a small JSON spec. A plain Python program then works out
*where* everything goes: columns, lane heights, box widths, and every line's route. The result
is a `.drawio` file you open in [draw.io / diagrams.net](https://app.diagrams.net).

- **No hand-drawn geometry.** Boxes are sized from their text, lines never cut through boxes,
  and labels are placed where they do not cover anything — or you get a warning saying so.
- **Deterministic.** The same spec produces a byte-identical file every time, so diagrams can
  live in version control and be regenerated after every SOP change.
- **Zero dependencies.** Python ≥ 3.11, standard library only. No network, no AI in the
  generator.

中文說明：[docs/OVERVIEW.md](docs/OVERVIEW.md)（這工具在幹嘛、術語對照） ·
錯誤碼白話表：[docs/CODES-zh.md](docs/CODES-zh.md)

## How it works

```
SOP document ──① extract──▶ spec.json ──② lint──▶ ③ layout ──④ emit──▶ diagram.drawio
            (an LLM does this)          (this program: pure Python, no AI, no network)
```

1. **Extract** — an LLM follows [`prompts/extract_spec.md`](prompts/extract_spec.md) to turn
   the SOP into a spec. This is the only step that needs to understand natural language.
2. **Lint** — the spec is checked: dangling references, decisions with a single exit,
   undeclared loops, labels too long to fit. Problems are printed as `E###` / `W###` codes.
3. **Layout** — pure geometry: columns by longest-path layering, box widths from the label
   text, and Manhattan routes that run only through the free corridors between boxes.
4. **Emit** — the computed numbers are written out as draw.io (mxGraph) XML.

## Quick start

```bash
git clone https://github.com/Andy-playground/swimlane-builder.git
cd swimlane-builder
python3 swimlane-builder.py generate examples/po-confirmation.spec.json -o po-confirmation.drawio
```

Open `po-confirmation.drawio` in draw.io. Nothing to install.

## Use it as an AI Skill

[`SKILL.md`](SKILL.md) drives the whole flow in any agent host that has file access and
Python ≥ 3.11: hand it an SOP (text or `.docx`) and it extracts, lints, shows you a summary to
review, and returns the `.drawio`. Build the portable bundle with:

```bash
python3 tools/build_skill.py        # → dist/swimlane-builder-skill.zip + its sha256
```

Upload the zip to Claude as a Skill, or unzip it as plain context files for any other agent.

## Use it by hand

1. **Extract:** give the SOP plus [`prompts/extract_spec.md`](prompts/extract_spec.md) to your
   LLM and save the answer as `myflow.spec.json`
   (for a `.docx` source, run `python3 tools/docx2txt.py file.docx` first).
2. **Lint:** `python3 swimlane-builder.py lint myflow.spec.json` — fix every `E` code, read the
   `W` codes.
3. **Generate:** `python3 swimlane-builder.py generate myflow.spec.json -o myflow.drawio`
4. **Open** the `.drawio` in draw.io. Never hand-edit it — edit the spec and regenerate.

Many SOPs at once, one visual standard:

```bash
python3 swimlane-builder.py batch specs/ -o diagrams/ [--theme NAME]
```

Exit codes: `0` ok · `1` validation failed (codes printed) · `2` file I/O error.

## The spec in one minute

```json
{
  "meta":  { "sop_id": "SOP-001", "title": "Purchase Order Confirmation" },
  "lanes": [
    { "id": "buyer",    "label": "Buyer Logistics" },
    { "id": "supplier", "label": "Supplier" }
  ],
  "nodes": [
    { "id": "start", "lane": "buyer",    "type": "start",    "label": "PO released" },
    { "id": "t1",    "lane": "supplier", "type": "task",     "label": "Confirm PO in portal" },
    { "id": "d1",    "lane": "buyer",    "type": "decision", "label": "Qty / date match?" },
    { "id": "end",   "lane": "buyer",    "type": "end",      "label": "PO confirmed" }
  ],
  "edges": [
    { "from": "start", "to": "t1", "channel": "system" },
    { "from": "t1",    "to": "d1" },
    { "from": "d1",    "to": "end", "label": "Yes" },
    { "from": "d1",    "to": "t1",  "label": "No", "kind": "feedback" }
  ]
}
```

- **lanes** — who: one horizontal band per role or system, top to bottom.
- **nodes** — what: `start`, `end`, `task`, `decision`, `subprocess`, `document`. Optional
  `step` (the SOP's own step number, shown as a badge), `note` (context that does not fit the
  label), and `col` (a *minimum* column — the layout may still push a node further right).
- **edges** — how steps connect. `label` is required on decision branches. `kind: "feedback"`
  marks a loop back to an earlier step. `channel` (`offline` / `system` / `user`) sets the line
  style.

The full schema is [`schema/spec.schema.json`](schema/spec.schema.json).

## Lint codes

| Code | Meaning |
|---|---|
| **E001** | The spec's shape is wrong: missing field, wrong type, duplicate id, not exactly one start |
| **E101** | A node or edge points to a lane or node that does not exist |
| **E102** | A loop that is not declared — mark the edge that closes it `"kind": "feedback"` |
| **E103** | A decision has fewer than two exits, or an unlabeled exit |
| **E104** | A node cannot be reached from the start |
| W201 | A node label does not fit even the widest box |
| W202 | Too many columns — consider splitting the flow |
| W203 | The start node is not in the first lane |
| W204 | Two decisions share one lane and column, so their branches compete for space |
| W205 | Only some nodes carry a `step` number |
| W206 | A requested `col` is below what the flow allows, so the node was moved right |
| W207 | A branch label is longer than two words — state the condition only |
| W208 | An edge label is too wide, or has no free spot and is drawn over something |
| W209 | Fitted to a 1366×768 screen, the text would read below 11 px |

`E` codes stop generation; `W` codes are advice, and the diagram is still produced. W202 and
W209 are budgets reported to the author — the layout never reshapes a flow to chase them.

## Themes

Colors, fonts and spacing are data, not code: [`themes/default.json`](themes/default.json)
(draw.io pastels) and [`themes/classic.json`](themes/classic.json) (white boxes, black
outlines, square corners). A theme file only lists what it changes. Pick one with `--theme`
or with `meta.theme` in the spec.

## Examples

Each spec ships with its generated `.drawio` next to it. The process content is fictional.

| Spec | What it shows |
|---|---|
| [`po-confirmation`](examples/po-confirmation.spec.json) | The minimal flow — a decision, a rework loop, three lanes |
| [`special-order-shipment`](examples/special-order-shipment.spec.json) | 13 steps: documents, a subprocess, all three line styles |
| [`booking-change`](examples/booking-change.spec.json) | 17 steps: seven decisions, branch labels that are not Yes/No, four lines merging on one node |
| [`delivery-dates`](examples/delivery-dates.spec.json) | 15 columns: exception steps carried in `note`, long decision questions |

## Development

```bash
python3 tests/test_all.py                                 # full suite: lint rules, geometry, golden XML
python3 tests/test_all.py TestXml.test_golden_snapshot    # one test or class
python3 tools/check_schema.py                             # examples vs. the JSON Schema (needs `pip install jsonschema`)
python3 tools/preview.py out.drawio -o shots/out.png      # render a .drawio to PNG without draw.io (needs Chromium)
```

Code layout (`src/swimlane_builder/`):

- `cli.py` — loads spec → theme → `validate.lint` → `layout.compute` → `xmlgen.emit`.
- `validate.py` — hand-rolled schema check plus semantic lint; returns `[(code, message)]`.
- `layout.py` — pure geometry: columns, sizes, lane heights, ports, routes, label placement.
- `xmlgen.py` — writes mxGraph XML from the layout; computes nothing.
- `themes.py` — loads `themes/*.json`.

Rules that keep it working:

1. **Keep the stages apart.** `layout.py` never knows about XML; `xmlgen.py` never computes
   geometry. New geometry goes in layout, new styling in a theme file, new markup in xmlgen.
2. **Determinism is tested byte for byte.** `test_golden_snapshot` regenerates every
   `examples/*.spec.json` and compares it with the committed `.drawio`. After an intentional
   output change, regenerate them
   (`python3 swimlane-builder.py generate examples/<name>.spec.json -o examples/<name>.drawio`),
   review the diff, and open them in draw.io before committing.
3. **The schema lives in two places.** `schema/spec.schema.json` and `validate._shape` (the
   runtime stays stdlib-only). Change one, change the other; CI's `check_schema.py` catches drift.
4. **The font is pinned.** Box widths are computed from a Helvetica 14 text metric in the
   theme, so every style must carry `fontFamily`/`fontSize` — otherwise the reader's draw.io
   re-flows the text.
5. **Every lint code has a failing fixture** in `tests/test_all.py`.

`tools/preview.py` approximates draw.io's renderer: it is evidence about the computed geometry,
not a replacement for opening the file in draw.io.

## Known limitations

- A long `start`/`end` label can overflow its fixed-size circle, and no lint code reports it yet.
- Wide flows (roughly 14 columns and up) do not fit one laptop screen at a readable size. W209 says so;
  splitting the SOP into two flows is the author's call.

## License

[MIT](LICENSE) © 2026 Andy-playground
