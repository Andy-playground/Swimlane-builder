# swimlane-builder

**Swimlane flowcharts that come out right the first time, delivered as a draw.io file you can
open in the tools you already use.**

More formats are on the way: Mermaid, SVG and Visio.

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

If something in your source is unclear, the assistant asks you. It does not make up steps.

To change the diagram, tell the assistant what changed and it draws a new one. Step-by-step instructions for
the Skill and the command line are in the [usage guide](docs/USAGE.md).

## What it does for you

Every tool can draw lanes, boxes and arrows. This one also handles the parts you would
normally fix by hand:

**Layout**

- Boxes grow to fit their text, and lanes grow to fit their boxes.
- The main flow runs in a straight line from left to right. Side branches are placed around
  it.
- The page size is picked to fit the diagram.

**Lines**

- Lines never cut through a box.
- Lines never sit on top of each other. When several go the same way, they run side by side.
- Lines take the route with the fewest turns and cross each other as little as possible.
- An arrow that sends work back to an earlier step runs around the outside, so it is easy to
  spot.
- Line styles show how a handover happens: system to system, a person using a system, or
  offline (email, phone).

**Labels and annotations**

- "Yes" and "No" labels sit next to their own arrow and do not cover a box or another line.
- Each box shows the step number from your document, so you can match the diagram to the
  text.
- A legend is added automatically.

**Checks before drawing**

- It finds gaps in the process before drawing. For example: a step that no arrow leads to,
  or a yes/no question that only has a "yes" path.
- It warns you when the diagram is too wide to read on a laptop screen.

**Consistency**

- The same input always gives the same diagram. When the diagram changes, it is because the
  process changed.
- All your diagrams share one look. Colors, fonts and spacing come from a theme, and two
  themes are included.
- A whole folder of procedures can be drawn in one run.

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
