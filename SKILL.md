---
name: swimlane-builder
description: Turn an SOP document (process table, step list, .docx) into a draw.io swimlane diagram. Use when the user wants a process flow, flowchart, swimlane, or .drawio file from an SOP or procedure text. Extracts the process into a JSON spec internally, then runs a bundled deterministic Python generator — never hand-writes diagram XML. Delivers the .drawio file only.
---

# swimlane-builder — SOP document → draw.io swimlane diagram

You convert SOP documents into business-grade draw.io swimlane diagrams. The division of labor
is fixed: **you extract process semantics; the bundled Python computes every coordinate.** Never
write or edit mxGraph/draw.io XML yourself — hand-authored geometry is the failure mode this
tool exists to remove.

Host requirements: file read/write and `python3` ≥ 3.11 on PATH. The generator is stdlib-only —
no packages to install, no network, no other tools required.

## Pipeline (follow in order)

1. **Read the source.** Accept SOP text, markdown, or `.docx` (for `.docx`, run
   `python3 tools/docx2txt.py <file.docx>` and read its output). The flow usually lives in a
   numbered process table (often a "Process Workflow" section whose Task cells end with
   `→ Step N` pointers); exception scenarios are often listed in a section of their own.

2. **Extract the spec.** Follow `prompts/extract_spec.md` to the letter — it defines the lane /
   node / edge rules, the ≤ 2-word branch-label policy, the exception-note grammar, and the JSON
   Schema. Write the result to a working file, e.g. `work/<sop_id>.spec.json` — the prompt's
   "output only the JSON" rule describes that file's contents, not your reply. The spec is an
   internal artifact: do not show the raw JSON unless the user asks for it.

3. **Lint until clean.** Run:

       python3 swimlane-builder.py lint work/<sop_id>.spec.json

   - `E###` lines are fatal — fix the spec and re-lint. `E102` names an undeclared loop: declare
     that edge `"kind": "feedback"`. `E103`: a decision is missing a branch label or a second
     branch. `E101`/`E104`: an id typo or a step you forgot to connect.
   - `W###` lines are advisories, and they split into two kinds.

     **Yours to act on**, because they are about wording you chose: `W207` (branch label longer
     than the policy — cut it to the condition and move the dropped words into the target node's
     label or `note`), `W208` (a label had nowhere clear to sit, so it is drawn over something —
     shorten it the same way), and `W201` (a node label overflows even the widest box).

     **The author's to decide**, so relay them in one sentence each and do not act alone:
     `W202` (more columns than the budget — the SOP may want splitting), `W204` (two decisions
     in one lane and column), `W209` (fitted to a laptop screen the text reads below 11 px —
     the message names the achieved size and how many columns would fit). These are authoring
     decisions, not extraction errors, and the generator never reshapes the flow to clear them.

4. **Present the extraction summary** (mandatory review — the user never sees the JSON, so this
   summary is their review medium). One screen: the lanes in order · the steps with their lane ·
   each decision with its branch labels · each feedback loop · anything marked `TODO:` or
   `Cadence: per exception`. Incorporate corrections and re-lint.

5. **Generate and deliver.** Run:

       python3 swimlane-builder.py generate work/<sop_id>.spec.json -o <sop_id>.drawio

   Deliver **only** the `.drawio` file — it imports into draw.io / app.diagrams.net as-is.
   Do not deliver the spec JSON unless the user explicitly asks (they may want it for
   version control; it is theirs on request). If the host can render or preview draw.io files
   (e.g. a draw.io MCP), offer a preview — but never require it.

6. **Revise on feedback.** Keep the spec for the session. Every change the user asks for is an
   edit to the spec followed by regeneration — never an edit to the `.drawio`. Regeneration is
   deterministic: the same spec always yields byte-identical output.

## Hard rules

- Never invent steps, branches, or conditions the source does not state. Uncertain → keep the
  node, prefix its label `TODO:`, and say so in the summary.
- Never bypass the linter or deliver a file generated from a spec with `E` errors.
- Branch labels state the condition only (`Yes` / `No` / `Ocean`, ≤ 2 words). Consequences are
  nodes, not label text.
- Exception steps (Cadence `Per exception`, or restatements of an exception scenario) keep
  their provenance in the node's `note`, starting exactly `Cadence: per exception` — reserved
  for machine reading by a later version.
- Themes: `default` (draw.io pastels) unless the user asks for plain black-and-white boxes,
  then `--theme classic`. Restyling is regeneration with a different theme, never manual edits.

## Bundle map

| Path | What it is |
|---|---|
| `swimlane-builder.py` | CLI launcher — `generate` / `lint` / `batch` |
| `prompts/extract_spec.md` | The extraction rules and schema you follow in step 2 |
| `tools/docx2txt.py` | `.docx` → plain text (tables become tab-separated rows) |
| `src/`, `schema/`, `themes/` | Generator internals — read if curious, never required |
| `examples/po-confirmation.spec.json` + `.drawio` | A known-good pair; regenerate to self-test the toolchain |
