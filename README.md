# swimlane-builder

**Today's tools draw swimlane flowcharts worse than you would expect, so this Skill builds one
as a draw.io file that opens directly in the tools you already use.**

Mermaid, SVG and Visio output are planned.

<p align="center">
  <img src="docs/media/hero.webp" width="800"
       alt="swimlane-builder laying out a diagram: the lanes appear, each step lands in its column, and the lines are routed between the boxes">
</p>

<p align="center">
  <a href="docs/media/swimlane-builder-showreel.mp4"><b>▶ 30-second overview</b></a> (with sound)
  &nbsp;·&nbsp;
  <a href="https://github.com/Andy-playground/Swimlane-builder/releases/latest"><b>Download the Skill</b></a>
  &nbsp;·&nbsp;
  <a href="docs/OVERVIEW.md"><b>中文說明</b></a>
</p>

## Works with

| | |
|---|---|
| **To make a diagram** | Claude, with the Skill added · any AI agent that can read files and run Python · any LLM plus the command line |
| **To open the result** | [draw.io / diagrams.net](https://app.diagrams.net) on the web or desktop, and anything else that imports `.drawio` files |
| **To run it** | Python 3.11 or later. Nothing to install, and the generator works offline |

## How to use it

Describe the process to your AI assistant and ask for a swimlane diagram. It shows you a short
summary of what it understood, you confirm or correct it, and you get the `.drawio` file.

What you can hand over:

- **A RACI matrix or process table (best).** Parties, steps and tools are stated outright, so
  nothing has to be guessed.
- **A written procedure.** A numbered step list or an SOP, as text or `.docx`.
- **A paragraph or meeting notes.** A description of who does what, or the record of the
  meeting where the process was agreed. Sorting that into steps is what language models are
  good at.

Anything the source leaves unclear is marked for you to settle, never filled in.

To change the diagram, say what changed and it is regenerated. Step-by-step instructions for
the Skill and the command line are in the [usage guide](docs/USAGE.md).

## What it does for you

Lanes, steps, decisions and arrows are the baseline. The rest is what you would otherwise fix
by hand:

**Layout**

- Every box is sized to its text, and every lane to what it holds.
- The main path reads straight from left to right; branches and rework loops are placed
  around it.
- The page size is chosen to fit the finished diagram.

**Lines**

- A line never cuts through a box.
- Lines that travel together run side by side, never on top of each other.
- Each line takes the route with the fewest turns, and where several meet at one box they are
  ordered to cross as little as possible.
- Rework loops go around the flow, so "back to step 3" is visible at a glance.
- System, user and offline interactions each get their own line style.

**Labels and annotations**

- Branch labels sit beside the line they name and cover nothing.
- Each step carries the step number from your own document, so the diagram and the text can
  be read side by side.
- A legend is added, listing only the shapes and line styles the diagram uses.

**Checks before drawing**

- The process itself is checked: steps nothing leads to, decisions with only one way out,
  loops that were never stated.
- You are told when a diagram is too wide to read on a laptop screen, and how much would fit.

**Consistency**

- The same input gives the same file every time, so a diagram can be versioned and compared
  like any document.
- Colors, fonts and spacing come from a theme. A whole folder of procedures can be generated
  in one run and look like one family. Two themes are included.

## Examples

Open any of these in draw.io to see a result. The process content is fictional.

| Example | What it shows |
|---|---|
| [Purchase order confirmation](examples/po-confirmation.drawio) | The smallest useful flow: three lanes, one decision, one rework loop |
| [Special order shipment](examples/special-order-shipment.drawio) | 13 steps with documents, a sub-process, and all three line styles |
| [Booking change](examples/booking-change.drawio) | 17 steps and seven decisions, with branches that are not just Yes/No |
| [Delivery dates](examples/delivery-dates.drawio) | A wide flow of 15 columns with exception steps and long decision questions |

## Documentation

| Document | For |
|---|---|
| [Usage guide](docs/USAGE.md) | Running the tool, the input format, themes, where it fits, known limitations |
| [Messages](docs/CODES.md) | What each error and warning means and what to do about it |
| [Development](docs/DEVELOPMENT.md) | Code layout, tests, and the rules that keep output stable |
| [中文說明](docs/OVERVIEW.md) · [錯誤碼白話表](docs/CODES-zh.md) | 中文版的介紹、術語對照與錯誤碼 |

## License

[MIT](LICENSE) © 2026 Andy-playground
