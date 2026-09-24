# Extract a process spec from an SOP

Operator: give the model this file plus the SOP document (paste the text, attach the file, or
convert a `.docx` first with `python3 tools/docx2txt.py <file.docx>`). The model's output goes to
`<sop_id>.spec.json` and then through `python3 swimlane-builder.py lint` before anything is
generated. This prompt is host-agnostic: it assumes nothing about which LLM is reading it.

---

## Task

Read the SOP document below and output **one JSON object** — the process spec that
`swimlane-builder` turns into a swimlane diagram.

Output **only** the JSON. No prose before or after, no markdown code fences, no comments.
The object must validate against the schema at the end of this prompt.

## Where the flow lives in the source

Most SOPs carry the flow in a **process table** (often titled "Process Workflow"), typically
with RACI-style columns such as
`# · Phase · Task · Cadence · Responsible · Accountable · Consulted · Informed · Template · Tool · System`.
Read it row by row:

- Each row is one step; the `#` column is the SOP's own step number (`3`, `7a`).
- A Task cell usually ends with an explicit pointer — `→ Step 5`, `If matched → Step 4. If not
  matched → Step 5`, `→ End`. **Those pointers are the edges.** Follow them exactly; do not
  invent transitions the table does not state.
- `Responsible` names the lane that performs the step.
- An **exceptions section** (often titled "Exception Handling") may restate some steps as
  exception scenarios; its rows overlap the process table. Use it for the exception rule below,
  never as extra steps.

In a document without this structure, find the equivalent: the numbered step list or table that
states who does what in what order.

## Rules

### Lanes

- A lane is a role or system that **performs** at least one step (the `Responsible` column).
  Parties that are only consulted or informed are not lanes — they go in the `note` of the steps
  that mention them.
- Merge synonyms into one lane (`Vendor` / `Supplier` / `Factory` named inconsistently is one
  party). 3–6 lanes is typical.
- Order the `lanes` array: requester/initiator first, people before systems, systems last. The
  lane that performs the first step should be the first lane.

### Nodes

- One node per process-table row, plus a `start` node and at least one `end` node.
- `step`: the `#` column's value **verbatim** (`"3"`, `"7a"`), unique. `start`/`end` carry no
  `step`.
- **`start`** is the flow's trigger. If the first row states an event ("PO is released"), that
  row *is* the start node; if it states an action, the start node is the triggering condition
  from the SOP's purpose or scope ("Booking change needed"), and the row is a normal step.
  Exactly one `start`. **`end`** is each final state ("PO status: Confirmed"); at least one.
- `type`: `decision` for a question with branches · `subprocess` for a reference to another
  flow or SOP · `document` for a step whose deliverable is a file or folder artifact · `task`
  otherwise.
- `label`: **≤ 6 words, verb-first, English.** The label is the action; everything else the row
  says moves to `note`.
- `note` carries what the label drops, in this order when present:
  `Cadence` · `Accountable`/`Consulted`/`Informed` parties that differ from the lane · formulas
  and rules referenced (`rule 2`) · `Tool`/`System` · source banners or remarks, condensed.
  Never leave process meaning behind — relocate it here.
- **Exception steps.** A step whose `Cadence` is `Per exception`, or that restates a scenario
  from the exceptions section, must have a `note` that **begins**
  `Cadence: per exception — exception scenario N` (with the scenario number when identifiable).
  This prefix is reserved for machine reading; do not paraphrase it.
- Ambiguous or unknown steps: keep the node, prefix the label `TODO:`. **Never invent process
  detail** — no steps, branches, or conditions the source does not state. If a decision has no
  "all is well" branch in the source, leave that branch absent and record the gap in `note`.

### Decisions and edges

- A `decision` label is a closed question ending in `?` — `Status = Accepted?`, not
  `Check status`.
- Every decision has **≥ 2 outgoing edges, every one labeled**. A branch label states the
  condition and nothing else: bare `Yes` / `No`, or at most **2 words** for a named path
  (`Ocean`, `Truck EXW`, `CIF/DDP/DAP`). A label like `No - inform vendor with reason` is wrong
  twice: the consequence is a step, so it belongs in the target node (or its `note`), and the
  extra words have nowhere to sit on the diagram. Relocate, never delete.
- A loop back to an earlier step (rework, resubmit, recheck) is declared
  `"kind": "feedback"` on the edge that closes the loop. Without it the flow has an undeclared
  cycle and validation fails (E102).
- `channel`, when the medium is discernible: `system` for system-to-system automation,
  `user` for a person acting in a portal/UI, omit otherwise (defaults to `offline`).

### IDs

- Pattern `^[a-z][a-z0-9_]*$`, unique across lanes and nodes.
- Convention: short lane ids (`vendor`, `buyer`, `portal`); node ids `n{step}` (`n1`, `n7a`);
  `start` / `end`.

## Self-check before you output

Walk this list; it mirrors the validator that runs next:

1. Exactly one `start`; at least one `end`.
2. Every edge's `from`/`to` names an existing node id; all ids unique and pattern-legal.
3. Every `decision` has ≥ 2 outgoing edges and every one carries a `label`.
4. Every node is reachable from `start` following normal (non-feedback) edges.
5. No cycle among normal edges — every loop's closing edge is `"kind": "feedback"`.
6. Every process-table row is either a node or deliberately merged; every `→ Step N` pointer is
   an edge; no edge exists that the source does not state.
7. Branch labels ≤ 2 words; node labels ≤ 6 words; exception notes carry the exact
   `Cadence: per exception` prefix.
8. The lane performing the first step is first in the `lanes` array.

## Example

### Source (abridged)

> **SOP-001 — Purchase Order Confirmation** · PROCESS WORKFLOW
>
> | # | Phase | Task | Cadence | Responsible | Accountable | Consulted | Informed | Tool |
> |---|---|---|---|---|---|---|---|---|
> | 1 | Confirmation | PO is released to the supplier for confirmation. → Step 2 | Per order | Buyer Logistics | Buyer Logistics | — | Supplier | ERP |
> | 2 | Confirmation | Confirm the PO in the portal. → Step 3 | Per order | Supplier | Supplier | — | — | Supplier Portal |
> | 3 | Confirmation | Check that confirmed quantity and date match the PO. If matched → Step 4. If not matched → Step 5 | Per order | Buyer Logistics | Buyer Logistics | — | Purchasing | Supplier Portal |
> | 4 | Confirmation | Approve the confirmation. The portal sets the PO status to Confirmed. → End | Per order | Buyer Logistics | Buyer Logistics | — | — | Supplier Portal |
> | 5 | Confirmation | Revise the confirmation and resubmit. → Step 3 | Per order | Supplier | Supplier | — | — | Supplier Portal |

### Output

{
  "meta": {
    "sop_id": "SOP-001",
    "title": "Purchase Order Confirmation",
    "version": "1.0",
    "theme": "default"
  },
  "lanes": [
    { "id": "buyer",    "label": "Buyer Logistics" },
    { "id": "supplier", "label": "Supplier" },
    { "id": "portal",   "label": "Supplier Portal (System)" }
  ],
  "nodes": [
    { "id": "start", "lane": "buyer",    "type": "start",    "label": "PO released" },
    { "id": "n2",    "lane": "supplier", "type": "task",     "label": "Confirm PO in portal",
      "step": "2", "note": "Cadence: per order. Tool: Supplier Portal." },
    { "id": "n3",    "lane": "buyer",    "type": "decision", "label": "Qty / date match?",
      "step": "3", "note": "Cadence: per order. Informed: Purchasing. Tool: Supplier Portal." },
    { "id": "n4",    "lane": "buyer",    "type": "task",     "label": "Approve confirmation",
      "step": "4", "note": "The portal sets the PO status to Confirmed. Tool: Supplier Portal." },
    { "id": "n5",    "lane": "supplier", "type": "task",     "label": "Revise confirmation",
      "step": "5", "note": "Resubmit for a new check. Tool: Supplier Portal." },
    { "id": "end",   "lane": "portal",   "type": "end",      "label": "PO status: Confirmed" }
  ],
  "edges": [
    { "from": "start", "to": "n2", "channel": "system" },
    { "from": "n2",    "to": "n3", "channel": "user" },
    { "from": "n3",    "to": "n4", "label": "Yes" },
    { "from": "n3",    "to": "n5", "label": "No" },
    { "from": "n5",    "to": "n3", "kind": "feedback", "channel": "user" },
    { "from": "n4",    "to": "end", "channel": "system" }
  ]
}

Row 1 states an event, so it became the `start` node (no `step`); the loop 5 → 3 is the
`feedback` edge; `No` carries no consequence text — the consequence is node `n5`.

## Schema (the output must validate against this)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "swimlane-builder process spec",
  "type": "object",
  "required": ["meta", "lanes", "nodes", "edges"],
  "additionalProperties": false,
  "properties": {
    "meta": {
      "type": "object",
      "required": ["sop_id", "title"],
      "additionalProperties": false,
      "properties": {
        "sop_id":  { "type": "string", "minLength": 1 },
        "title":   { "type": "string", "minLength": 1 },
        "version": { "type": "string" },
        "theme":   { "type": "string", "default": "default" }
      }
    },
    "lanes": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["id", "label"],
        "additionalProperties": false,
        "properties": {
          "id":    { "$ref": "#/$defs/ident" },
          "label": { "type": "string", "minLength": 1 }
        }
      }
    },
    "nodes": {
      "type": "array",
      "minItems": 2,
      "items": {
        "type": "object",
        "required": ["id", "lane", "type", "label"],
        "additionalProperties": false,
        "properties": {
          "id":    { "$ref": "#/$defs/ident" },
          "lane":  { "$ref": "#/$defs/ident" },
          "type":  { "enum": ["start", "end", "task", "decision", "subprocess", "document"] },
          "label": { "type": "string", "minLength": 1 },
          "col":   { "type": "integer", "minimum": 0 },
          "step":  { "type": "string", "minLength": 1 },
          "note":  { "type": "string" }
        }
      }
    },
    "edges": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["from", "to"],
        "additionalProperties": false,
        "properties": {
          "from":    { "$ref": "#/$defs/ident" },
          "to":      { "$ref": "#/$defs/ident" },
          "label":   { "type": "string" },
          "kind":    { "enum": ["normal", "feedback"], "default": "normal" },
          "channel": { "enum": ["offline", "system", "user"], "default": "offline" }
        }
      }
    }
  },
  "$defs": {
    "ident": { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" }
  }
}
```
