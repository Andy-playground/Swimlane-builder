"""Golden snapshot + geometric assertions + lint fixtures.

Run: python3 tests/test_all.py
"""
import json
import sys
import unittest
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from swimlane_builder import layout, themes, validate, xmlgen  # noqa: E402

THEME = themes.load()
SPEC = json.loads((ROOT / "examples" / "po-confirmation.spec.json").read_text("utf-8"))


def gen(spec=SPEC):
    return xmlgen.emit(spec, layout.compute(spec, THEME), THEME)


def codes(spec):
    return {c for c, _ in validate.lint(spec, THEME)}


def mini(nodes=None, edges=None):
    return {
        "meta": {"sop_id": "T", "title": "t"},
        "lanes": [{"id": "a", "label": "A"}],
        "nodes": nodes or [
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
        ],
        "edges": edges or [{"from": "s", "to": "z"}],
    }


class TestLint(unittest.TestCase):
    def test_example_clean(self):
        self.assertEqual(codes(SPEC), set())

    def test_e001_duplicate_id(self):
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "s", "lane": "a", "type": "end", "label": "Z"},
        ], edges=[{"from": "s", "to": "s"}])
        self.assertIn("E001", codes(spec))

    def test_e001_start_end_counts(self):
        spec = mini(nodes=[
            {"id": "s1", "lane": "a", "type": "start", "label": "S"},
            {"id": "s2", "lane": "a", "type": "start", "label": "S"},
        ], edges=[{"from": "s1", "to": "s2"}])
        self.assertIn("E001", codes(spec))  # two starts, no end

    def test_step_accepted(self):
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "t1", "lane": "a", "type": "task", "label": "T1", "step": "3a"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
        ], edges=[{"from": "s", "to": "t1"}, {"from": "t1", "to": "z"}])
        self.assertNotIn("E001", codes(spec))

    def test_e001_duplicate_step(self):
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "t1", "lane": "a", "type": "task", "label": "T1", "step": "3a"},
            {"id": "t2", "lane": "a", "type": "task", "label": "T2", "step": "3a"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
        ], edges=[{"from": "s", "to": "t1"}, {"from": "t1", "to": "t2"}, {"from": "t2", "to": "z"}])
        self.assertIn("E001", codes(spec))

    def test_e001_schema_shape(self):
        self.assertIn("E001", codes({"meta": {}, "lanes": [], "nodes": [], "edges": []}))
        spec = mini()
        spec["nodes"][0]["bogus"] = 1
        self.assertIn("E001", codes(spec))

    def test_e101_unknown_ref(self):
        self.assertIn("E101", codes(mini(edges=[{"from": "s", "to": "ghost"}])))

    def test_e102_cycle(self):
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "t1", "lane": "a", "type": "task", "label": "T1"},
            {"id": "t2", "lane": "a", "type": "task", "label": "T2"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
        ], edges=[
            {"from": "s", "to": "t1"},
            {"from": "t1", "to": "t2"},
            {"from": "t2", "to": "t1"},
            {"from": "t1", "to": "z"},
        ])
        issues = validate.lint(spec, THEME)
        self.assertIn("E102", {c for c, _ in issues})
        self.assertTrue(any("feedback" in m for c, m in issues if c == "E102"))

    def test_w206_explicit_col_below_floor(self):
        """'col' is a floor, so a backward override cannot break layering — it is
        raised to the layered minimum and the author is told."""
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z", "col": 0},
        ])
        found = codes(spec)
        self.assertIn("W206", found)
        self.assertNotIn("E102", found)
        self.assertEqual(layout.assign_columns(spec)["z"], 1)

    def test_explicit_col_propagates_to_successors(self):
        """Pushing one node right shifts its tail instead of tripping E102."""
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "t1", "lane": "a", "type": "task", "label": "T1", "col": 4},
            {"id": "t2", "lane": "a", "type": "task", "label": "T2"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
        ], edges=[{"from": "s", "to": "t1"}, {"from": "t1", "to": "t2"}, {"from": "t2", "to": "z"}])
        cols = layout.assign_columns(spec)
        self.assertEqual((cols["t1"], cols["t2"], cols["z"]), (4, 5, 6))
        self.assertNotIn("E102", codes(spec))

    def test_w207_branch_label_states_more_than_the_condition(self):
        """A branch label states the condition only: the consequence is a step, so it
        belongs on the target node."""
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "d", "lane": "a", "type": "decision", "label": "Booking can be cancelled?"},
            {"id": "t", "lane": "a", "type": "task", "label": "Receive no-change notice"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
        ], edges=[
            {"from": "s", "to": "d"},
            {"from": "d", "to": "t", "label": "No - inform vendor with reason"},
            {"from": "d", "to": "z", "label": "Yes"},
        ])
        self.assertIn("W207", codes(spec))
        spec["edges"][1]["label"] = "No"                     # the relocation clears it
        self.assertNotIn("W207", codes(spec))

    def test_w207_ignores_a_long_label_on_a_non_branch(self):
        """The word bound is a *branch*-label rule — it exists so a decision's exits stay
        readable. An ordinary edge is bounded by width alone (W208)."""
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "t", "lane": "a", "type": "task", "label": "T"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
        ], edges=[
            {"from": "s", "to": "t", "label": "provide four whole words"},
            {"from": "t", "to": "z"},
        ])
        self.assertNotIn("W207", codes(spec))

    def test_w208_label_wider_than_the_bound(self):
        """`LABEL_W_MAX`: the generator never shortens a label — it draws it and reports
        the spec."""
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "t", "lane": "a", "type": "task", "label": "T"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
        ], edges=[
            {"from": "s", "to": "t", "label": "Provide Standard PO / Vendor Booking Number"},
            {"from": "t", "to": "z"},
        ])
        lay = layout.compute(spec, THEME)
        found = [c for c, _ in validate.lint_layout(spec, THEME, lay)]
        self.assertIn("W208", found)
        # and the label is still emitted in full — reporting is not truncating
        self.assertIn("Provide Standard PO / Vendor Booking Number",
                      xmlgen.emit(spec, lay, THEME))

    def test_w209_one_screen_is_a_budget_not_a_constraint(self):
        """The generator reports the achieved read size and does **not** reshape the flow
        to improve it. Calibrated against the shipped examples: it fires on the two widest
        flows and not on the two smaller ones."""
        reads = {}
        for path in sorted((ROOT / "examples").glob("*.spec.json")):
            spec = json.loads(path.read_text("utf-8"))
            lay = layout.compute(spec, THEME)
            fired = "W209" in [c for c, _ in validate.lint_layout(spec, THEME, lay)]
            reads[path.name.replace(".spec.json", "")] = fired
        self.assertEqual(reads, {"booking-change": True, "delivery-dates": True,
                                 "po-confirmation": False, "special-order-shipment": False})

        # a two-column flow is comfortably inside the budget; the same spec on a theme with
        # an unreachable floor is not — the code is about the floor, not about being large
        spec = mini()
        lay = layout.compute(spec, THEME)
        self.assertNotIn("W209", [c for c, _ in validate.lint_layout(spec, THEME, lay)])
        strict = json.loads(json.dumps(THEME))
        strict["geometry"]["READ_MIN_PX"] = 10 ** 6
        self.assertIn("W209", [c for c, _ in validate.lint_layout(spec, strict, lay)])

    def test_w205_partly_numbered_badges(self):
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "t1", "lane": "a", "type": "task", "label": "T1", "step": "3a"},
            {"id": "t2", "lane": "a", "type": "task", "label": "T2"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
        ], edges=[{"from": "s", "to": "t1"}, {"from": "t1", "to": "t2"}, {"from": "t2", "to": "z"}])
        self.assertIn("W205", codes(spec))
        # all-or-nothing numbering is clean either way
        for n in spec["nodes"]:
            if n["type"] == "task":
                n["step"] = n["id"]
        self.assertNotIn("W205", codes(spec))

    def test_e103_decision(self):
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "d", "lane": "a", "type": "decision", "label": "OK?"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
        ], edges=[
            {"from": "s", "to": "d"},
            {"from": "d", "to": "z"},
        ])
        self.assertIn("E103", codes(spec))  # 1 branch, unlabeled

    def test_e104_unreachable(self):
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
            {"id": "orphan", "lane": "a", "type": "task", "label": "O"},
        ])
        self.assertIn("E104", codes(spec))

    def test_w201_long_label(self):
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
            {"id": "t", "lane": "a", "type": "task",
             "label": "confirm the Vendorbookingcancellationandamendment revision"},
        ], edges=[{"from": "s", "to": "t"}, {"from": "t", "to": "z"}])
        # a word wider than the whole line box is never broken, so no width on
        # the ladder can hold it — the node is drawn at NODE_W_MAX and the spec is told
        self.assertIn("W201", codes(spec))
        self.assertEqual(layout.node_size("task", spec["nodes"][2]["label"], THEME)[0],
                         THEME["geometry"]["NODE_W_MAX"])

    def test_w203_start_not_in_first_lane(self):
        spec = mini()
        spec["lanes"] = [{"id": "b", "label": "B"}, {"id": "a", "label": "A"}]
        self.assertIn("W203", codes(spec))

    def test_e001_bad_channel(self):
        self.assertIn("E001", codes(mini(edges=[{"from": "s", "to": "z", "channel": "fax"}])))

    def test_w202_too_many_columns(self):
        nodes = [{"id": "s", "lane": "a", "type": "start", "label": "S"}]
        edges, prev = [], "s"
        for i in range(15):
            nodes.append({"id": f"t{i}", "lane": "a", "type": "task", "label": "T"})
            edges.append({"from": prev, "to": f"t{i}"})
            prev = f"t{i}"
        nodes.append({"id": "z", "lane": "a", "type": "end", "label": "Z"})
        edges.append({"from": prev, "to": "z"})
        self.assertIn("W202", codes(mini(nodes=nodes, edges=edges)))


class TestGeometry(unittest.TestCase):
    def setUp(self):
        self.lay = layout.compute(SPEC, THEME)
        self.lanes = {l["id"]: l for l in self.lay["lanes"]}

    def test_layering(self):
        self.assertEqual(self.lay["cols"],
                         {"start": 0, "t1": 1, "d1": 2, "t2": 3, "t3": 3, "end": 4})
        # the canvas this spec settles at, hit exactly
        self.assertEqual((self.lay["canvas_w"], self.lay["canvas_h"]), (700, 640))

    def test_lane_heights_formula(self):
        """With one height for every shape, a lane band collapses to two values —
        170 where the deepest cell holds one shape, 300 where it holds two. That is the
        visible form of the rule, and the thing a reader learns after one diagram."""
        g = THEME["geometry"]
        road = layout.corridor_w(THEME)
        for l in self.lay["lanes"]:
            depth = max(sum(1 for n in self.lay["nodes"] if n["lane"] == l["id"] and n["col"] == c)
                        for c in range(len(self.lay["columns"])))
            self.assertEqual(l["h"], layout.lane_height(THEME, l["label"], depth))
            self.assertEqual(depth, 1)
            self.assertEqual(l["h"], 170)                 # roundup_GRID(2*24 + 120)
            self.assertEqual(l["h"], -(-(2 * road + g["H_NODE"]) // g["GRID"]) * g["GRID"])
        # lanes start below title + legend bars, separated by LANE_GAP (0 = flush pools)
        self.assertEqual([l["y"] for l in self.lay["lanes"]], [130, 300, 470])
        y = THEME["geometry"]["TITLE_H"] + THEME["geometry"]["LEGEND_H"]
        for l in self.lay["lanes"]:
            self.assertEqual(l["y"], y)
            y += l["h"] + THEME["geometry"]["LANE_GAP"]

    def test_step_badges(self):
        seq = {n["id"]: n.get("seq") for n in self.lay["nodes"]}
        self.assertIsNone(seq["start"])
        self.assertIsNone(seq["end"])
        self.assertEqual(seq, {"start": None, "t1": 1, "d1": 2, "t2": 3, "t3": 4, "end": None})
        badges = {n["id"]: n.get("badge_text") for n in self.lay["nodes"] if "badge" in n}
        self.assertEqual(badges, {"t1": "1", "d1": "2", "t2": "3", "t3": "4"})

    def test_explicit_step_shown_verbatim(self):
        """An explicit SOP step wins over the computed ordinal."""
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "t1", "lane": "a", "type": "task", "label": "T1", "step": "3a"},
            {"id": "t2", "lane": "a", "type": "task", "label": "T2"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
        ], edges=[{"from": "s", "to": "t1"}, {"from": "t1", "to": "t2"}, {"from": "t2", "to": "z"}])
        lay = layout.compute(spec, THEME)
        badges = {n["id"]: (n["seq"], n["badge_text"]) for n in lay["nodes"] if "badge" in n}
        self.assertEqual(badges, {"t1": (1, "3a"), "t2": (2, "2")})
        self.assertIn('id="badge_t1" value="3a"', xmlgen.emit(spec, lay, THEME))

    def test_legend_items(self):
        items = [(i["kind"], i["key"]) for i in self.lay["legend"]["items"]]
        self.assertEqual(items, [("shape", "task"), ("shape", "decision"),
                                 ("line", "offline"), ("line", "system"), ("line", "user")])

    def test_nodes_inside_lane_band(self):
        for n in self.lay["nodes"]:
            band = self.lanes[n["lane"]]
            self.assertGreaterEqual(n["x"], THEME["geometry"]["LANE_TITLE_W"])
            self.assertGreaterEqual(n["y"], 0)
            self.assertLessEqual(n["x"] + n["w"], band["w"])
            self.assertLessEqual(n["y"] + n["h"], band["h"])

    def test_no_overlap(self):
        rects = [(n["x"], self.lanes[n["lane"]]["y"] + n["y"], n["w"], n["h"])
                 for n in self.lay["nodes"]]
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                x1, y1, w1, h1 = rects[i]
                x2, y2, w2, h2 = rects[j]
                self.assertTrue(x1 + w1 <= x2 or x2 + w2 <= x1
                                or y1 + h1 <= y2 or y2 + h2 <= y1,
                                f"overlap between rect {i} and {j}")

    def test_column_table_is_the_only_source_of_column_x(self):
        """The canvas width, every node's x-centre and every routing corridor
        read `columns[c]`. Three independent copies of `c · COL_W` is what put an edge
        through a node body once widths stopped being uniform, so the table is asserted
        to agree with what the layout actually placed."""
        columns = self.lay["columns"]
        self.assertEqual(columns[0]["x_left"],
                         THEME["geometry"]["LANE_TITLE_W"] + THEME["geometry"]["MARGIN_X"])
        for c in range(1, len(columns)):
            self.assertEqual(columns[c]["x_left"],
                             columns[c - 1]["x_left"] + columns[c - 1]["w"])
        self.assertEqual(self.lay["canvas_w"], layout.canvas_width(THEME, columns))
        for n in self.lay["nodes"]:
            col = columns[n["col"]]
            self.assertEqual(n["x"] + n["w"] // 2, col["x_left"] + col["w"] // 2,
                             f"{n['id']} is not centred on its column")

    def test_columns_aligned_across_lanes(self):
        centers = {}
        for n in self.lay["nodes"]:
            centers.setdefault(n["col"], set()).add(n["x"] + n["w"] / 2)
        for col, cs in centers.items():
            self.assertEqual(len(cs), 1, f"column {col} centers differ: {cs}")

    def test_one_height_for_every_shape(self):
        """The assertion that keeps the one-height rule from decaying back into a
        per-type table. Height variation between neighbours encodes nothing a reader can
        act on, and a single height is what collapses the lane arithmetic to two possible
        bands."""
        g = THEME["geometry"]
        for path in sorted((ROOT / "examples").glob("*.spec.json")):
            with self.subTest(spec=path.name):
                lay = layout.compute(json.loads(path.read_text("utf-8")), THEME)
                for n in lay["nodes"]:
                    if n["type"] in ("start", "end"):
                        self.assertEqual((n["w"], n["h"]), (g["TERMINAL_D"], g["TERMINAL_D"]),
                                         f"{n['id']} is not a circle")
                    else:
                        self.assertEqual(n["h"], g["H_NODE"], f"{n['id']} is not H_NODE tall")

    def test_every_width_is_on_the_ladder_and_holds_its_label(self):
        """Sizing: widths land on `GRID` inside [NODE_W_MIN, NODE_W_MAX], so a diagram
        uses a handful of discrete widths rather than a continuum — variable, but not
        ragged — and each one actually holds the label it was sized for, or the spec
        raises W201."""
        g = THEME["geometry"]
        budget = layout.lines_available(THEME)
        for path in sorted((ROOT / "examples").glob("*.spec.json")):
            with self.subTest(spec=path.name):
                spec = json.loads(path.read_text("utf-8"))
                lay = layout.compute(spec, THEME)
                warned = {c for c, _ in validate.lint(spec, THEME)}
                for n in lay["nodes"]:
                    if n["type"] in ("start", "end"):
                        continue
                    self.assertEqual(n["w"] % g["GRID"], 0, f"{n['id']} width is off the grid")
                    self.assertGreaterEqual(n["w"], g["NODE_W_MIN"])
                    self.assertLessEqual(n["w"], g["NODE_W_MAX"])
                    lines = layout.wrap_lines(n["label"], n["w"] - 2 * g["PAD_TEXT_X"], THEME)
                    if len(lines) > budget:
                        self.assertIn("W201", warned, f"{n['id']} overflows and nothing said so")

    def test_lane_is_tall_enough_for_its_own_rotated_title(self):
        """`horizontal=0` makes draw.io render the lane name rotated, so the title is a
        *height* demand — asserted here for every example."""
        g = THEME["geometry"]
        title_lines = max(g["LANE_TITLE_W"] // g["LINE_H"], 1)
        for path in sorted((ROOT / "examples").glob("*.spec.json")):
            with self.subTest(spec=path.name):
                lay = layout.compute(json.loads(path.read_text("utf-8")), THEME)
                for l in lay["lanes"]:
                    need = layout.text_width(l["label"], THEME) / title_lines + 2 * g["LANE_TITLE_PAD"]
                    self.assertGreaterEqual(l["h"], need,
                                            f"lane '{l['id']}' would clip its own title")

    def test_stacking_grows_lane(self):
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "p1", "lane": "a", "type": "task", "label": "P1"},
            {"id": "p2", "lane": "a", "type": "task", "label": "P2"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
        ], edges=[
            {"from": "s", "to": "p1"},
            {"from": "s", "to": "p2"},
            {"from": "p1", "to": "z"},
            {"from": "p2", "to": "z"},
        ])
        lay = layout.compute(spec, THEME)
        # a deeper cell grows the lane; it never shrinks the shapes. The second
        # of the two bands a diagram can have — roundup_GRID(2*24 + 2*120 + 10).
        self.assertEqual(lay["lanes"][0]["h"], 300)
        p1, p2 = (next(n for n in lay["nodes"] if n["id"] == i) for i in ("p1", "p2"))
        self.assertEqual((p1["h"], p2["h"]), (120, 120))
        self.assertEqual((p1["y"], p2["y"]), (25, 155))


def _label_box(e, theme):
    """The label's extent, rebuilt from what was emitted —
    anchor along the path plus the perpendicular offset — so the assertion measures the
    same rectangle draw.io will draw, not the one layout happened to test."""
    g = theme["geometry"]
    w = layout.text_width(e["label"], theme) + 2 * g["LABEL_PAD"]
    lens = [abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(e["path"], e["path"][1:])]
    total = sum(lens)
    want = (e["label_pos"] + 1) / 2 * total
    run = 0.0
    cx, cy = e["path"][0]
    for i, ((a, b), ln) in enumerate(zip(zip(e["path"], e["path"][1:]), lens)):
        if run + ln >= want or i == len(lens) - 1:
            f = (want - run) / ln if ln else 0
            cx, cy = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
            break
        run += ln
    dx, dy = e.get("label_offset") or (0, 0)
    return (cx + dx - w / 2, cy + dy - g["LINE_H"] / 2, w, g["LINE_H"])


def _hit(a, b):
    return (a[0] < b[0] + b[2] and b[0] < a[0] + a[2]
            and a[1] < b[1] + b[3] and b[1] < a[1] + a[3])


def _stress_spec():
    """Hard routing shapes seen in real SOPs: a decision whose branches
    match no primary label, two decisions stacked in one (lane, col), and three edges
    converging on one node."""
    return {
        "meta": {"sop_id": "STRESS", "title": "Port and routing stress"},
        "lanes": [{"id": "vendor", "label": "Vendor"}, {"id": "portal", "label": "Portal"},
                  {"id": "agent", "label": "Agent"}],
        "nodes": [
            {"id": "s", "lane": "vendor", "type": "start", "label": "Start"},
            {"id": "d4", "lane": "vendor", "type": "decision", "label": "Check ship mode", "step": "4"},
            {"id": "d4a", "lane": "portal", "type": "decision", "label": "Check incoterm A", "step": "4a"},
            {"id": "d4b", "lane": "portal", "type": "decision", "label": "Check incoterm B", "step": "4b"},
            {"id": "t3a", "lane": "agent", "type": "task", "label": "Reopen request", "step": "5"},
            {"id": "z", "lane": "agent", "type": "end", "label": "End"},
        ],
        "edges": [
            {"from": "s", "to": "d4"},
            {"from": "d4", "to": "d4a", "label": "Truck/Parcel"},
            {"from": "d4", "to": "d4b", "label": "Ocean/Air"},
            {"from": "d4a", "to": "t3a", "label": "CIF/DDP/DAP"},
            {"from": "d4a", "to": "z", "label": "EXW/FOB"},
            {"from": "d4b", "to": "t3a", "label": "Parcel & Truck"},
            {"from": "d4b", "to": "z", "label": "Other incoterm"},
            {"from": "t3a", "to": "z"},
            {"from": "t3a", "to": "d4", "kind": "feedback"},
        ],
    }


class TestRouting(unittest.TestCase):
    """Routing assertions over every example plus a stress fixture."""

    # every committed example plus the stress fixture
    CASES = {p.name: json.loads(p.read_text("utf-8")) for p in sorted((ROOT / "examples").glob("*.spec.json"))}
    CASES["stress"] = _stress_spec()

    def layouts(self):
        for name, spec in self.CASES.items():
            with self.subTest(spec=name):
                yield name, spec, layout.compute(spec, THEME)

    @staticmethod
    def _boxes(lay):
        lane_y = {l["id"]: l["y"] for l in lay["lanes"]}
        return {n["id"]: (n["x"], lane_y[n["lane"]] + n["y"], n["w"], n["h"]) for n in lay["nodes"]}

    def test_no_label_covers_a_node_or_another_label(self):
        """A label's *box* — not just its anchor — clears every node and every label
        placed before it. W208 is the only escape, so a green
        suite means each label was either verified clear or its spec was warned. There is
        no third state, which is what stops a silent overlap from shipping."""
        for name, spec, lay in self.layouts():
            boxes = list(self._boxes(lay).values())
            placed = []
            for e in lay["edges"]:
                if not e["label"] or not e.get("label_clear", True):
                    continue                       # reported W208, the one allowed overlap
                box = _label_box(e, THEME)
                for b in boxes:
                    self.assertFalse(_hit(box, b),
                                     f"{name}: label '{e['label']}' ({e['from']}->{e['to']}) covers a node")
                for other, ob in placed:
                    self.assertFalse(_hit(box, ob),
                                     f"{name}: labels '{e['label']}' and '{other}' overlap")
                placed.append((e["label"], box))

    def test_w208_is_reported_whenever_a_label_could_not_be_placed(self):
        """The generator never shortens a label — it draws it at candidate (a) and
        says so. The pair 'no clear anchor' and 'no W208' is the state
        this test exists to make impossible."""
        for name, spec, lay in self.layouts():
            stuck = [e for e in lay["edges"] if e["label"] and not e.get("label_clear", True)]
            codes = [c for c, _ in validate.lint_layout(spec, THEME, lay)]
            self.assertEqual(len(stuck) <= len(codes), True,
                             f"{name}: {len(stuck)} unplaceable labels but {len(codes)} W208")
            for e in stuck:
                self.assertIsNotNone(e["label_pos"], f"{name}: {e['label']} has no anchor at all")

    def test_no_segment_crosses_a_node(self):
        """No segment enters a node it does not belong to. Its own endpoints are
        exempt — a port projected onto a rhombus or ellipse sits inside the bounding box
        by design, so the stub's last few px cross the box's empty corner."""
        for name, _spec, lay in self.layouts():
            boxes = self._boxes(lay)
            for e in lay["edges"]:
                path = e["path"]
                for p, q in zip(path, path[1:]):
                    lo_x, hi_x = sorted((p[0], q[0]))
                    lo_y, hi_y = sorted((p[1], q[1]))
                    for nid, (bx, by, bw, bh) in boxes.items():
                        if nid in (e["from"], e["to"]):
                            continue
                        inside = (bx < hi_x and bx + bw > lo_x and by < hi_y and by + bh > lo_y)
                        self.assertFalse(inside, f"{name}: {e['from']}->{e['to']} segment "
                                                 f"{p}-{q} runs through node '{nid}'")

    def test_ports_sit_on_the_visible_outline(self):
        """A fan-out port on a rhombus or ellipse is projected onto the shape, not
        left on the bounding box where the arrowhead would float in white space."""
        shapes = {"decision": lambda x, y: abs(x - 0.5) + abs(y - 0.5),
                  "start": lambda x, y: ((x - 0.5) ** 2 + (y - 0.5) ** 2) ** 0.5,
                  "end": lambda x, y: ((x - 0.5) ** 2 + (y - 0.5) ** 2) ** 0.5}
        for name, _spec, lay in self.layouts():
            types = {n["id"]: n["type"] for n in lay["nodes"]}
            for e in lay["edges"]:
                for nid, port in ((e["from"], e["exit"]), (e["to"], e["entry"])):
                    if types[nid] in shapes:
                        self.assertAlmostEqual(
                            shapes[types[nid]](*port), 0.5, delta=0.005,
                            msg=f"{name}: port {port} on {types[nid]} '{nid}' is off the outline")

    def test_no_two_edges_share_an_attach_point(self):
        for name, _spec, lay in self.layouts():
            seen = defaultdict(list)
            for e in lay["edges"]:
                seen[(e["from"], e["exit"])].append(f"{e['from']}->{e['to']}")
                seen[(e["to"], e["entry"])].append(f"{e['from']}->{e['to']}")
            for (nid, port), users in sorted(seen.items()):
                self.assertEqual(len(users), 1, f"{name}: {users} share port {port} on '{nid}'")

    def test_every_decision_has_exactly_one_right_exit(self):
        for name, spec, lay in self.layouts():
            kinds = {n["id"]: n["type"] for n in spec["nodes"]}
            right = defaultdict(int)
            for e in lay["edges"]:
                if kinds[e["from"]] == "decision" and e["kind"] == "normal":
                    right[e["from"]] += e["exit_side"] == "R"
            for nid, count in sorted(right.items()):
                self.assertEqual(count, 1, f"{name}: decision '{nid}' has {count} right-exiting branches")

    def test_step_order_picks_the_primary_branch(self):
        """A decision with no Yes/No label follows the SOP's step numbering."""
        spec = _stress_spec()
        lay = layout.compute(spec, THEME)
        sides = {(e["from"], e["to"]): e["exit_side"] for e in lay["edges"]}
        self.assertEqual(sides[("d4", "d4a")], "R")   # step 4a follows step 4
        self.assertNotEqual(sides[("d4", "d4b")], "R")

    def test_w204_stacked_decisions(self):
        self.assertIn("W204", codes(_stress_spec()))

    def test_corridors_stay_free_in_every_shipped_theme(self):
        """The clearance is part of the column width's *definition*, so this asserts
        the definition rather than one theme's numbers — per column, per theme. A test
        can only speak for the specs in `examples/`, not for the SOP an author writes
        tomorrow; the definition is what covers that one."""
        for path in sorted((ROOT / "themes").glob("*.json")):
            with self.subTest(theme=path.stem):
                th = themes.load(path.stem)
                g = th["geometry"]
                road = layout.corridor_w(th)
                track = max(abs(o) for o in layout.slots(th))
                # a road carries its tracks and still keeps KERB at each edge
                self.assertLessEqual(2 * track + 2 * g["KERB"], road,
                                     "a road no longer holds its own tracks")
                for name, spec, lay in self.layouts():
                    by_col = defaultdict(list)
                    for n in lay["nodes"]:
                        by_col[n["col"]].append(n)
                    for c, col in enumerate(lay["columns"]):
                        widest = max(n["w"] for n in by_col[c]) if by_col[c] else 0
                        # a node is centred, so its edge sits (COL_W - w)/2 right of the
                        # boundary; a run rides that boundary offset by at most one track
                        self.assertGreaterEqual((col["w"] - widest) / 2 - track, g["KERB"],
                                                f"{name} column {c}: a vertical run comes "
                                                f"within {g['KERB']} px of a node")


class TestXml(unittest.TestCase):
    def test_golden_snapshot(self):
        """Every example spec must reproduce its committed .drawio byte for byte."""
        specs = sorted((ROOT / "examples").glob("*.spec.json"))
        self.assertGreaterEqual(len(specs), 3, "example specs missing from examples/")
        for path in specs:
            with self.subTest(spec=path.name):
                spec = json.loads(path.read_text("utf-8"))
                golden = path.with_name(path.name.replace(".spec.json", ".drawio"))
                self.assertEqual(gen(spec), golden.read_text("utf-8"),
                                 f"{golden.name} is stale — regenerate and eyeball the diff")

    def test_deterministic(self):
        self.assertEqual(gen(), gen())

    def test_wellformed_and_cell_count(self):
        root = ET.fromstring(gen())
        cells = root.findall(".//mxCell")
        # 2 root + title + legend + 5 legend items + 3 lanes + 6 nodes + 4 badges + 6 edges
        self.assertEqual(len(cells), 2 + 1 + 1 + 5 + 3 + 6 + 4 + 6)
        for c in cells:
            if c.get("edge") == "1":
                geo = c.find("mxGeometry")
                self.assertIsNotNone(geo, f"edge {c.get('id')} missing geometry child")
                self.assertEqual(geo.get("relative"), "1")

    def test_edge_ports(self):
        xml = gen()
        sides = {(e["from"], e["to"]): (e["exit_side"], e["entry_side"])
                 for e in layout.compute(SPEC, THEME)["edges"]}
        # main flow reads left to right
        self.assertEqual(sides[("start", "t1")], ("R", "L"))
        self.assertEqual(sides[("t2", "end")], ("R", "L"))
        # 'Yes' matches the primary-label list, so it is the branch that exits right
        self.assertEqual(sides[("d1", "t2")], ("R", "L"))
        # the other branch drops out of the bottom and still merges at the target's left
        self.assertEqual(sides[("d1", "t3")], ("B", "L"))
        # cross-lane feedback merges into the target's LEFT entry point
        self.assertEqual(sides[("t3", "d1")], ("B", "L"))
        self.assertIn('value="Yes"', xml)

    def test_same_lane_feedback_ports(self):
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "S"},
            {"id": "t1", "lane": "a", "type": "task", "label": "T1"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
        ], edges=[
            {"from": "s", "to": "t1"},
            {"from": "t1", "to": "z"},
            {"from": "t1", "to": "s", "kind": "feedback"},
        ])
        loop = next(e for e in layout.compute(spec, THEME)["edges"] if e["kind"] == "feedback")
        self.assertEqual((loop["exit_side"], loop["entry_side"]), ("B", "L"))
        # it leaves below the row, runs back, and rises into the entry
        self.assertTrue(loop["points"], "feedback loop must carry explicit waypoints")

    def test_waypoints_emitted_as_array(self):
        root = ET.fromstring(gen())
        cell = next(c for c in root.findall(".//mxCell") if c.get("id") == "e_t3__d1")
        pts = cell.findall("./mxGeometry/Array[@as='points']/mxPoint")
        self.assertTrue(pts)
        for p in pts:
            self.assertEqual(float(p.get("x")), int(float(p.get("x"))))  # integral coords

    def test_branch_label_anchored_to_its_own_path(self):
        """The anchor is computed from the edge's own path, not from one constant for
        every branch. Only labelled edges get one."""
        lay = layout.compute(SPEC, THEME)
        pos = {(e["from"], e["to"]): e["label_pos"] for e in lay["edges"]}
        self.assertIsNotNone(pos[("d1", "t2")])                                      # 'Yes'
        self.assertIsNone(pos[("start", "t1")])                                      # unlabelled
        self.assertIsNone(pos[("t3", "d1")])                                         # not a branch
        for (f, t), p in pos.items():
            if p is not None:
                self.assertGreaterEqual(p, -1.0, f"{f}->{t} anchor off the path")
                self.assertLessEqual(p, 1.0, f"{f}->{t} anchor off the path")
        root = ET.fromstring(xmlgen.emit(SPEC, lay, THEME))
        cell = next(c for c in root.findall(".//mxCell") if c.get("id") == "e_d1__t2")
        self.assertIsNotNone(cell.find("mxGeometry").get("x"))

    def test_page_grows_with_the_canvas(self):
        """The sheet is the smallest ISO landscape page that holds the canvas —
        a 14-column flow is an A1 plot and the file should say so."""
        self.assertEqual(layout.page_size(THEME, 1000, 700), (1169, 826))     # A4
        self.assertEqual(layout.page_size(THEME, 1200, 700), (1654, 1169))    # A3
        self.assertEqual(layout.page_size(THEME, 99999, 99999), (4681, 3300))  # clamps at A0
        pinned = {**THEME, "page": [1169, 826]}
        self.assertEqual(layout.page_size(pinned, 9000, 9000), (1169, 826))   # theme may pin
        lay = layout.compute(SPEC, THEME)
        self.assertIn(f'pageWidth="{lay["page_w"]}" pageHeight="{lay["page_h"]}"',
                      xmlgen.emit(SPEC, lay, THEME))

    def test_furniture_and_channels(self):
        xml = gen()
        self.assertIn('id="title"', xml)
        self.assertIn("SOP-001 – Purchase Order Confirmation", xml)
        self.assertIn('id="legend"', xml)
        self.assertEqual(xml.count('id="badge_'), 4)
        self.assertIn("strokeColor=#0066CC;dashed=1;", xml)   # user channel
        self.assertIn("jumpStyle=arc", xml)                   # line jumps

    def test_parallel_edge_ordinal(self):
        spec = mini(edges=[{"from": "s", "to": "z"}, {"from": "s", "to": "z", "label": "alt"}])
        xml = gen(spec)
        self.assertIn('id="e_s__z"', xml)
        self.assertIn('id="e_s__z_2"', xml)

    def test_every_shipped_theme_pins_the_font(self):
        """The text-width metric is meaningless unless the file pins the font it
        measures. A style that omits it hands the choice to the reader's draw.io, so the
        generator sizes for Helvetica and the reader sees something else re-flowed."""
        for name in ("default", "classic"):
            th = themes.load(name)
            for kind, style in list(th["node_styles"].items()) + [("edge", th["edge_style"])]:
                with self.subTest(theme=name, style=kind):
                    self.assertIn("fontFamily=", style)
                    self.assertIn("fontSize=", style)
            self.assertEqual(th["text_metric"]["FONT_FAMILY"], "Helvetica")

    def test_line_weight_is_uniform_and_the_legend_matches_it(self):
        """Connectors and shape outlines carry one weight; the lane, title and legend
        frames keep the default. The legend's line samples are a *key*, so they are drawn
        at whatever the edge style sets rather than at a width of their own — a key that
        disagrees with the lines it describes is worse than no key."""
        for name in ("default", "classic"):
            th = themes.load(name)
            with self.subTest(theme=name):
                for kind, style in th["node_styles"].items():
                    self.assertIn("strokeWidth=2;", style, f"{kind} outline is not 2")
                self.assertIn("strokeWidth=2;", th["edge_style"])
                self.assertEqual(xmlgen._stroke_w(th["edge_style"]), "2")
        root = ET.fromstring(gen())
        for cid in ("lane_buyer", "title", "legend"):
            cell = next((c for c in root.iter("mxCell") if c.get("id") == cid), None)
            if cell is not None:
                self.assertNotIn("strokeWidth", cell.get("style"), f"{cid} should keep the default")
        for c in root.iter("mxCell"):
            if (c.get("id") or "").startswith("legend_line_"):
                self.assertIn("strokeWidth=2;", c.get("style"))

    def test_preview_measures_text_with_the_shipped_metric(self):
        """`tools/preview.py` must measure text exactly as the generator does. A preview
        that measures differently reports 'no difference' for a sizing fix that works —
        so it reads the theme, and this pins the two together."""
        sys.path.insert(0, str(ROOT / "tools"))
        import preview
        labels = [n["label"] for n in SPEC["nodes"]] + \
                 [e.get("label", "") for e in SPEC["edges"]] + \
                 [l["label"] for l in SPEC["lanes"]]
        for s in labels:
            self.assertEqual(preview.text_width(s, 12), layout.text_width(s, THEME, 12), s)
            self.assertEqual(preview.wrap(s, 12, 100), layout.wrap_lines(s, 100, THEME, 12), s)

    def test_second_theme_needs_no_code_change(self):
        """themes/classic.json restyles every diagram through data alone."""
        classic = themes.load("classic")
        xml = xmlgen.emit(SPEC, layout.compute(SPEC, classic), classic)
        ET.fromstring(xml)
        self.assertIn("User Action", xml)                    # legend labels are theme data
        self.assertIn("rounded=0;whiteSpace=wrap", xml)      # square boxes
        self.assertIn("startSize=40;collapsible=0;html=1;rounded=0;", xml)   # lane style too
        # geometry is untouched by styling: same lane bands as the default theme
        self.assertEqual([l["y"] for l in layout.compute(SPEC, classic)["lanes"]],
                         [l["y"] for l in layout.compute(SPEC, THEME)["lanes"]])

    def test_label_escaping(self):
        spec = mini(nodes=[
            {"id": "s", "lane": "a", "type": "start", "label": "a & \"b\" <c>"},
            {"id": "z", "lane": "a", "type": "end", "label": "Z"},
        ])
        root = ET.fromstring(gen(spec))
        cell = next(c for c in root.findall(".//mxCell") if c.get("id") == "n_s")
        self.assertEqual(cell.get("value"), 'a & "b" <c>')


if __name__ == "__main__":
    unittest.main(verbosity=2)
