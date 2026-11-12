# Messages: errors and warnings

What the `E###` and `W###` codes printed by `lint` and `generate` mean, and what to do about
each one. A Chinese version of this page is [CODES-zh.md](CODES-zh.md); change both together.

## E: errors

An error stops generation. No diagram is produced until it is fixed.

| Code | Meaning | What to do |
|---|---|---|
| E001 | The spec's shape is wrong: invalid JSON, a missing field, a wrong type, a duplicate id or step number, not exactly one start, or no end | Follow the message; it names the field |
| E101 | A node names a lane that does not exist, or an edge names a node that does not exist | Usually a typo in an id |
| E102 | The flow contains a loop that is not declared | Add `"kind": "feedback"` to the edge that closes the loop |
| E103 | A decision has fewer than two exits, or an exit without a label | Give the decision at least two labeled edges |
| E104 | A node cannot be reached from the start | Connect it; an incoming edge is usually missing |

## W: warnings

A warning is advice. The diagram is still produced.

| Code | Meaning | What to do |
|---|---|---|
| W201 | A node label does not fit even the widest box, so the text spills out | Shorten the label; move the rest to `note` |
| W202 | The flow is more than 14 columns wide | Consider splitting the SOP into two flows |
| W203 | The start node is not in the first lane | Put the initiator's lane first in `lanes` |
| W204 | Two decisions share one lane and column, so their branches compete for space | Give one of them a `col` to move it right |
| W205 | Only some nodes carry a `step` number, so badges mix the SOP's numbers with computed ones | Number every step, or none |
| W206 | A requested `col` is lower than the flow allows, so the node was moved right | Usually nothing; `col` is a minimum, not a fixed position |
| W207 | A branch label is longer than two words | State the condition only (`Yes`, `Ocean`) and put the consequence in the next node |
| W208 | An edge label is too wide, or has no free spot and is drawn over something | Shorten the label, or give the flow more room |
| W209 | Fitted to a 1366×768 screen, the text would read below 11 px | The message gives the achieved size and how many columns would fit. Shorten or split the SOP |

W202 and W209 are budgets reported to the author. The layout never reshapes a flow to meet
them.

## Codes that appear together

- **W204 and W208.** Two decisions in one column leave their branch labels nowhere to sit. Fix
  W204 first and W208 often disappears.
- **W202 and W209.** Both say the diagram is too large: W202 counts columns, W209 measures
  whether the text can still be read.
