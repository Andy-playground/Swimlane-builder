# Usage guide

How to get from a process description to a `.drawio` file. For what the tool is and what it
does, see the [README](../README.md).

Requirements: Python 3.11 or later. There is nothing to install and no network access is
needed.

## Try it

```bash
git clone https://github.com/Andy-playground/swimlane-builder.git
cd swimlane-builder
python3 swimlane-builder.py generate examples/po-confirmation.spec.json -o po-confirmation.drawio
```

Open `po-confirmation.drawio` in [draw.io / diagrams.net](https://app.diagrams.net).

## Through an AI assistant (Skill)

[`SKILL.md`](../SKILL.md) drives the whole flow in any agent host that has file access and
Python 3.11 or later. Hand it an SOP as text or `.docx`; it extracts the process, checks it,
shows you a summary to review, and returns the `.drawio`.

1. Download `swimlane-builder-skill.zip` from the
   [latest release](https://github.com/Andy-playground/Swimlane-builder/releases/latest). Its
   SHA-256 is listed there.
2. Upload the zip to Claude as a Skill, or unzip it as plain context files for another agent.
3. Give the assistant your SOP and ask for a swimlane diagram.

To build the same zip yourself:

```bash
python3 tools/build_skill.py        # → dist/swimlane-builder-skill.zip + its sha256
```

## From the command line

1. **Extract.** Give the SOP and [`prompts/extract_spec.md`](../prompts/extract_spec.md) to an
   AI model and save its answer as `myflow.spec.json`. For a `.docx` source, convert it to text
   first:

   ```bash
   python3 tools/docx2txt.py file.docx
   ```

2. **Check.** Fix every `E` code and read the `W` codes. They are explained in
   [CODES.md](CODES.md).

   ```bash
   python3 swimlane-builder.py lint myflow.spec.json
   ```

3. **Generate.**

   ```bash
   python3 swimlane-builder.py generate myflow.spec.json -o myflow.drawio
   ```

4. **Open** the `.drawio` in draw.io.

Never edit the `.drawio` by hand. Edit the spec and regenerate; a hand edit is lost on the
next run.

### Many SOPs at once

```bash
python3 swimlane-builder.py batch specs/ -o diagrams/
```

Every `*.json` in `specs/` becomes a `.drawio` in `diagrams/`.

### Command reference

| Command | What it does |
|---|---|
| `generate SPEC [-o OUT] [--theme NAME]` | Checks the spec and writes one `.drawio`. Without `-o`, the file is written next to the spec |
| `generate SPEC --validate-only` | Checks the spec without writing anything |
| `lint SPEC` | Same check, printing the codes |
| `batch DIR -o OUTDIR [--theme NAME]` | Generates every `*.json` spec in a directory |

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | The spec failed the check; the codes are printed |
| `2` | A file could not be read or written |

## The spec

The spec is the JSON description of the process that the diagram is computed from. It has
three parts: who (`lanes`), what (`nodes`), and how they connect (`edges`).

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

### meta

| Field | Required | Meaning |
|---|---|---|
| `sop_id` | yes | The SOP's identifier, shown in the diagram title |
| `title` | yes | The diagram title |
| `version` | no | The SOP's version |
| `theme` | no | Theme name; `default` if absent |

### lanes

One horizontal band per role or system, drawn top to bottom in the order listed. Each has an
`id` and a `label`. Put the lane that starts the flow first.

### nodes

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Lowercase letters, digits and `_`, starting with a letter; unique across lanes and nodes |
| `lane` | yes | The `id` of the lane that performs the step |
| `type` | yes | `start`, `end`, `task`, `decision`, `subprocess` or `document` |
| `label` | yes | The text in the box. Keep it short and start with a verb |
| `step` | no | The SOP's own step number (`"4a"`), shown as a badge. Give it to every step or to none |
| `note` | no | Context that does not fit the label |
| `col` | no | A minimum column. The layout may still move the node further right |

A spec needs exactly one `start` and at least one `end`.

### edges

| Field | Required | Meaning |
|---|---|---|
| `from`, `to` | yes | Node ids |
| `label` | on decision branches | The condition only: `Yes`, `No`, or a name of at most two words |
| `kind` | no | `feedback` marks a loop back to an earlier step. Every loop needs one |
| `channel` | no | `offline` (default), `system` or `user`; sets the line style |

The full schema is [`schema/spec.schema.json`](../schema/spec.schema.json), and
[`examples/`](../examples) holds four complete specs with their diagrams.

## Themes

Colors, fonts and spacing are data. Two themes are included:

- [`default`](../themes/default.json): draw.io pastels.
- [`classic`](../themes/classic.json): white boxes, black outlines, square corners.

Choose one with `--theme NAME` on the command line or with `meta.theme` in the spec; the
command line wins. To make your own, add a JSON file to `themes/` that lists only the values
it changes from the default.

## Where it fits

It works well when:

- the process has steps with an owner each, especially a RACI matrix or a process table with
  a Responsible column and "go to step N" pointers;
- you maintain many procedures and want them to look like one family;
- procedures change often and the diagrams have to keep up;
- you want diagrams reviewed and versioned like documents.

It is the wrong tool when:

- you want to arrange a diagram by hand, or fine-tune one after it is generated;
- you need something other than a swimlane flowchart, such as full BPMN, an org chart or an
  architecture diagram;
- the procedure is one very long flow. Past about 14 columns the diagram no longer fits a
  laptop screen at a readable size. The tool says so, and splitting the flow is up to you.

## Known limitations

- A long label on a start or end circle can spill outside the circle, and nothing warns about
  it yet.
- Wide flows, from roughly 14 columns, do not fit one laptop screen at a readable size. A
  warning reports it; the tool never reshapes a flow to make it fit.
- The two branches leaving a decision can cross each other near the decision when one branch
  travels further than the other.
- A label on a very short line can overlap the shapes around it. A warning reports it.
- An arrow entering a document shape from below stops just under the shape's wavy bottom edge.
