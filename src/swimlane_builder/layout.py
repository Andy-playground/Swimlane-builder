"""Layout engine. Pure geometry; never touches XML."""
import re
from collections import defaultdict

# Port sides. The ratio that varies when several edges fan out on one side is the
# second component for L/R (vertical spread) and the first for T/B (horizontal).
ROUND_OUTLINE = ("start", "end", "decision")  # ports off-centre sit outside the outline


def slots(theme):
    """The tracks a corridor holds: `0, +PITCH, −PITCH, …`, `TRACKS` of them.

    One list, sized by the theme, serves both kinds of corridor (the vertical gutter
    between columns and the horizontal road along a lane's edge). Beyond `TRACKS` the
    slots are reused cyclically, which is legal only while the reused runs are disjoint
    in x — the routing tests assert that.
    """
    pitch = theme["geometry"]["TRACK_PITCH"]
    out = [0]
    for i in range(1, theme["geometry"]["TRACKS"]):
        out.append(pitch * ((i + 1) // 2) * (1 if i % 2 else -1))
    return tuple(out)


def corridor_w(theme):
    """`(TRACKS − 1) · TRACK_PITCH + 2 · KERB` — the width a corridor needs to carry its
    tracks and still keep `KERB` of clear space at each edge.

    `ROAD_W` and `GUTTER` are the same expression reached by independent arguments: one
    is the lane's top/bottom padding, the other the term `column_table` adds to a
    column's widest box. They come out equal at 24 px for the shipped constants; that is a coincidence of
    those constants, not a rule, so a theme may raise either alone.
    """
    g = theme["geometry"]
    return (g["TRACKS"] - 1) * g["TRACK_PITCH"] + 2 * g["KERB"]


def text_width(s, theme, size=None):
    """Width of `s` in px. Pure theme data — nothing is measured through a rendering
    engine, because the golden snapshots are compared byte for byte.

    `size` overrides the body `FONT_SIZE` for the furniture that pins its own (title,
    legend, badge). The table is calibrated for the family the theme pins; a theme that
    changes `FONT_FAMILY` must re-derive it.
    """
    m = theme["text_metric"]
    narrow = set(m["NARROW_CHARS"])
    total = 0.0
    for ch in s:
        if ch in narrow:
            total += m["NARROW_W"]
        elif ch.isupper():
            total += m["UPPER_W"]
        elif ord(ch) >= 0x2E80:                     # CJK and other full-width
            total += m["WIDE_W"]
        else:
            total += m["DEFAULT_W"]
    return total * (m["FONT_SIZE"] if size is None else size) / m["METRIC_REF"]


def wrap_lines(s, avail, theme, size=None):
    """The lines `s` takes in a line box `avail` px wide, wrapped greedily at
    whitespace. A word wider than the whole box is **never broken** — it stays on its
    own line and the caller widens the node or reports W201.

    Greedy is the conservative approximation of the browser's line breaking: it never
    packs a line tighter than a real renderer would, so a box sized from it is never too
    small. An explicit newline (or the `<br>` draw.io honours) is a hard break.
    """
    out = []
    for para in s.replace("<br>", "\n").split("\n"):
        line = ""
        for word in para.split():
            trial = f"{line} {word}".strip()
            if line and text_width(trial, theme, size) > avail:
                out.append(line)
                line = word
            else:
                line = trial
        out.append(line)
    return [l for l in out if l != ""] or [""]


def lines_available(theme):
    """How many wrapped lines `H_NODE` offers — derived, never configured.

    A separate line-budget constant would let a theme state a budget its own box height
    could not honour. The budget is whatever the height affords, and there is one place
    to change it.
    """
    g = theme["geometry"]
    return (g["H_NODE"] - 2 * g["PAD_TEXT_Y"]) // g["LINE_H"]


def node_size(ntype, label, theme):
    """(w, h) for one node. **Height is an input; width is the only derived dimension.**

    Width is the binding dimension of a left-to-right flow, so the height is fixed and
    the question is how wide the box must be for the label to wrap into the lines that
    height offers. Widths land on `GRID`, so a diagram uses a handful of discrete widths
    rather than a continuum: variable, but not ragged.

    A `decision` is sized to its **bounding box**, not to the inscribed diamond: draw.io
    wraps a rhombus's label to the cell width and renders overflow across the sloped
    edges, so this sizes decisions the way draw.io lays them out. Fitting the text inside
    the inscribed rectangle was measured and rejected — it inflates every column holding
    a decision and reverses the saving this sizing rule exists to produce.

    Returns the maximum width when nothing fits; the caller reports W201 and the label is
    never truncated.
    """
    g = theme["geometry"]
    if ntype in ("start", "end"):
        return g["TERMINAL_D"], g["TERMINAL_D"]     # a circle — one number, so w cannot drift from h
    budget = lines_available(theme)
    longest = max((text_width(word, theme) for word in label.split()), default=0.0)
    for w in range(g["NODE_W_MIN"], g["NODE_W_MAX"] + 1, g["GRID"]):
        usable = w - 2 * g["PAD_TEXT_X"]
        if usable >= longest and len(wrap_lines(label, usable, theme)) <= budget:
            return w, g["H_NODE"]
    return g["NODE_W_MAX"], g["H_NODE"]


def lane_height(theme, label, depth):
    """A lane band. `H_NODE` is an input, so this needs no pass of its own.

    **A lane title is a height demand, and this is the only place that says so.** The
    lane style pins `horizontal=0`, so draw.io renders the lane's name rotated, running
    along the lane's height inside a band `LANE_TITLE_W` wide — which makes
    `LANE_TITLE_W` the title's *line budget*, not a decoration.

    A deeper cell grows the lane; it never shrinks the shapes. Splitting the band between
    two shapes was measured and rejected — at `H_NODE` 120 a halved box offers two
    wrapped lines at 14 pt, while real SOP labels need up to six.
    """
    g = theme["geometry"]
    h_shapes = 2 * corridor_w(theme) + depth * g["H_NODE"] + max(depth - 1, 0) * g["V_GAP"]
    title_lines = max(g["LANE_TITLE_W"] // g["LINE_H"], 1)
    h_title = -(-text_width(label, theme) // title_lines) + 2 * g["LANE_TITLE_PAD"]
    return int(-(-max(h_shapes, h_title) // g["GRID"]) * g["GRID"])


class CycleError(Exception):
    """Undeclared cycle among normal edges (E102). .edge = (from, to) candidate to re-declare as feedback."""

    def __init__(self, edge):
        self.edge = edge
        super().__init__(f"cycle via edge {edge[0]}->{edge[1]}")


def assign_columns(spec):
    """Longest-path layering over normal edges.

    An explicit 'col' is a *floor* the rest of the graph is solved against, not a
    leaf-level edit: because the floor is applied inside the recursion, every
    successor re-derives its own column from it and the tail of the flow shifts
    automatically. Pushing one node right never strands its successors in an equal
    column (which would otherwise read as a cycle, E102).
    """
    preds = defaultdict(list)
    for e in spec["edges"]:
        if e.get("kind", "normal") == "normal":
            preds[e["to"]].append(e["from"])

    floor = {n["id"]: n["col"] for n in spec["nodes"] if "col" in n}
    cols, on_stack = {}, set()

    def visit(v):
        if v in cols:
            return cols[v]
        on_stack.add(v)
        c = floor.get(v, 0)
        for u in preds[v]:
            if u in on_stack:
                raise CycleError((u, v))
            c = max(c, visit(u) + 1)
        on_stack.discard(v)
        cols[v] = c
        return c

    for n in spec["nodes"]:
        visit(n["id"])
    return cols


def step_key(s):
    """Natural order for SOP step labels: 3 < 3a < 3b < 4 < 11 < 11b."""
    m = re.match(r"\s*(\d+)\s*([a-z]*)", (s or "").lower())
    return (int(m.group(1)), m.group(2)) if m else (10 ** 9, s or "")


def primary_branch(src, branches, steps, primary_labels):
    """Index of the branch that continues the main left-to-right line.

    A decision is not always Yes/No — often it just splits into named paths — so the
    SOP's own step numbering decides the direction: the branch reaching the next step
    is the main line. Falls back to the theme's primary-label list, then to spec order,
    so a decision always has exactly one right-exiting branch.
    """
    src_key = step_key(steps[src]) if steps.get(src) else None
    numbered = [(step_key(steps[e["to"]]), i) for i, e in enumerate(branches) if steps.get(e["to"])]
    if src_key is not None:
        numbered = [c for c in numbered if c[0] > src_key]
    if numbered:
        return min(numbered)[1]
    labelled = [i for i, e in enumerate(branches) if e.get("label", "").strip().lower() in primary_labels]
    return labelled[0] if labelled else 0


def _edge(e, s, t, exit_r, entry_r, ex, en, E, N, pts, label_pos):
    return {"from": s, "to": t, "label": e.get("label", ""),
            "kind": e.get("kind", "normal"), "channel": e.get("channel", "offline"),
            "exit": exit_r, "entry": entry_r, "exit_side": ex, "entry_side": en,
            "path": [E] + pts + [N], "points": pts, "label_pos": label_pos}


def _near_band(lane_i, lane_of, node, s, t, mid_y):
    """Which padding band of the target's lane the detour rides: the one facing the
    source lane, or (within one lane) whichever is closer to the run."""
    ls, lt = lane_i[node[s]["lane"]], lane_i[node[t]["lane"]]
    if lt != ls:
        return "T" if lt > ls else "B"
    lane = lane_of[node[t]["lane"]]
    return "T" if mid_y < lane["y"] + lane["h"] / 2 else "B"


def _inset(ntype, r):
    """How far inside the bounding box the outline sits at ratio `r` along a face.

    The fan-out ratios are relative to the bounding box, but on a rhombus or
    an ellipse the box corner is empty space: a port left at the box edge ends up to
    12 px away from the shape and the arrowhead floats. This pulls it back onto the
    outline (0 at the centre line of the face, ½ at the corner).
    """
    t = abs(r - 0.5) * 2
    if ntype == "decision":
        return 0.5 * t                              # rhombus tapers linearly
    return 0.5 * (1 - (1 - t * t) ** 0.5)           # ellipse


def _on_outline(ntype, side, x, y):
    """Project a port onto the node's visible outline."""
    if ntype not in ROUND_OUTLINE:
        return round(x, 3), round(y, 3)
    if side in ("L", "R"):
        d = _inset(ntype, y)
        x = d if side == "L" else 1 - d
    else:
        d = _inset(ntype, x)
        y = d if side == "T" else 1 - d
    return round(x, 3), round(y, 3)


def _crosses(boxes, p, q):
    """True if segment p-q passes through the interior of any node box."""
    (x1, y1), (x2, y2) = p, q
    lo_x, hi_x, lo_y, hi_y = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
    for bx, by, bw, bh in boxes:
        if bx < hi_x - 1 and bx + bw > lo_x + 1 and by < hi_y - 1 and by + bh > lo_y + 1:
            return True
    return False


def column_table(theme, widest):
    """The column table — `columns[c] = {x_left, w}`, where:

        COL_W(c) = roundup_GRID( w_max(c) + GUTTER )

    The canvas width, every node's x-centre and every routing corridor's x read this
    table. Any drift between a copy that places nodes and a copy that places corridors
    would put an edge through a node body, so this is the single source.

    **The corridor clearance is part of the width's definition, not a check run after
    the fact.** A node is centred, so its left edge sits at least `GUTTER/2` right of the
    column boundary; a vertical run rides that boundary offset by at most `TRACK_PITCH`,
    so it clears every box in the columns either side by at least `KERB`. That is what
    makes variable columns safe — a theme cannot widen a node into a corridor, because
    the corridor widens with it.
    """
    g = theme["geometry"]
    grid, gutter = g["GRID"], corridor_w(theme)
    x = g["LANE_TITLE_W"] + g["MARGIN_X"]
    columns = []
    for w_max in widest:
        w = -(-(w_max + gutter) // grid) * grid            # roundup_GRID
        columns.append({"x_left": x, "w": w})
        x += w
    return columns


def canvas_width(theme, columns):
    """`LANE_TITLE_W + 2 · MARGIN_X + Σ COL_W(c)`."""
    g = theme["geometry"]
    return g["LANE_TITLE_W"] + 2 * g["MARGIN_X"] + sum(c["w"] for c in columns)


def _route_edges(spec, nodes_out, lanes_out, cols, columns, theme):
    """Explicit Manhattan paths. Vertical runs stay in the gaps between
    columns, horizontal runs in a lane's PAD_V band — both are free of nodes by
    construction — so no segment can cross a node body."""
    g = theme["geometry"]
    node = {n["id"]: n for n in nodes_out}
    lane_of = {l["id"]: l for l in lanes_out}
    lane_i = {l["id"]: i for i, l in enumerate(spec["lanes"])}
    steps = {n["id"]: n.get("step") for n in spec["nodes"]}
    primary_labels = {p.lower() for p in theme["primary_labels"]}

    def box(nid):
        n = node[nid]
        return (n["x"], lane_of[n["lane"]]["y"] + n["y"], n["w"], n["h"])

    boxes = {n["id"]: box(n["id"]) for n in nodes_out}

    def others(s, t):
        """Boxes an edge must clear. Its own endpoints are excluded: a port projected
        onto a rhombus or ellipse sits inside the bounding box by design, so the last
        few px of the stub legitimately run through the box's empty corner."""
        return [b for nid, b in boxes.items() if nid not in (s, t)]

    def col_edge(nid, side):                       # x of the column gap beside a node
        c = columns[node[nid]["col"]]
        return c["x_left"] + c["w"] if side == "R" else c["x_left"]

    def band(nid, side):                           # y of one of the lane's two roads
        lane = lane_of[node[nid]["lane"]]
        half = corridor_w(theme) // 2
        return lane["y"] + lane["h"] - half if side == "B" else lane["y"] + half

    # a node stacked directly above/below blocks that side's stub
    stack = defaultdict(list)
    for n in nodes_out:
        stack[(n["lane"], n["col"])].append(n)

    def blocked(nid, side):
        if side not in ("T", "B"):
            return False
        grp = stack[(node[nid]["lane"], node[nid]["col"])]
        y = node[nid]["y"]
        return any((o["y"] > y if side == "B" else o["y"] < y) for o in grp if o is not node[nid])

    # ---- 1. sides: which face of each node an edge leaves from / arrives at
    out_of = defaultdict(list)
    for e in spec["edges"]:
        out_of[e["from"]].append(e)
    primary = {}
    for nid, branches in out_of.items():
        if node[nid]["type"] == "decision":
            fwd = [e for e in branches if e.get("kind", "normal") == "normal"]
            if fwd:
                primary[id(fwd[primary_branch(nid, fwd, steps, primary_labels)])] = True

    def pick(nid, wanted):
        for side in wanted:
            if not blocked(nid, side):
                return side
        return wanted[-1]

    sides = []
    for e in spec["edges"]:
        s, t = e["from"], e["to"]
        below = lane_i[node[t]["lane"]] > lane_i[node[s]["lane"]]
        if e.get("kind", "normal") == "feedback":
            ex = pick(s, ("B", "T", "L"))
        elif node[s]["type"] == "decision" and not primary.get(id(e)):
            ex = pick(s, ("B", "T", "L") if below or node[t]["lane"] == node[s]["lane"] else ("T", "B", "L"))
        else:
            ex = "R"
        if node[t]["col"] != node[s]["col"]:
            en = "L"
        else:
            en = pick(t, ("T", "B") if box(t)[1] > box(s)[1] else ("B", "T"))
        sides.append((ex, en))

    # ---- 2. fan-out: several edges on one face attach at distinct points (i/(k+1))
    groups = defaultdict(list)
    for i, (e, (ex, en)) in enumerate(zip(spec["edges"], sides)):
        groups[(e["from"], ex, "out")].append((node[e["to"]]["col"], lane_i[node[e["to"]]["lane"]], e["to"], i))
        groups[(e["to"], en, "in")].append((node[e["from"]]["col"], lane_i[node[e["from"]]["lane"]], e["from"], i))
    ratio = {}
    for (nid, side, kind), members in groups.items():
        members.sort()
        k = len(members)
        for j, (_, _, _, i) in enumerate(members):
            ratio[(i, kind)] = round(0.5 if k == 1 else (j + 1) / (k + 1), 3)

    # ---- 3. corridor slots: parallel runs in one corridor are offset so they stay apart
    track = slots(theme)                           # one list for both corridors
    used = defaultdict(int)

    def slot(value, offsets):
        k = used[value]
        used[value] = k + 1
        return value + offsets[k % len(offsets)]

    edges_out = []
    for i, (e, (ex, en)) in enumerate(zip(spec["edges"], sides)):
        s, t = e["from"], e["to"]
        rs, rt = ratio[(i, "out")], ratio[(i, "in")]
        label_pos = None                            # computed by _place_labels once the path exists
        sx, sy, sw, sh = box(s)
        tx, ty, tw, th = box(t)
        exit_r = (1.0, rs) if ex == "R" else (0.0, rs) if ex == "L" else (rs, 0.0 if ex == "T" else 1.0)
        entry_r = (0.0, rt) if en == "L" else (1.0, rt) if en == "R" else (rt, 0.0 if en == "T" else 1.0)
        exit_r = _on_outline(node[s]["type"], ex, *exit_r)
        entry_r = _on_outline(node[t]["type"], en, *entry_r)
        E = (round(sx + sw * exit_r[0]), round(sy + sh * exit_r[1]))
        N = (round(tx + tw * entry_r[0]), round(ty + th * entry_r[1]))
        clear = others(s, t)

        # straight shot — the common left-to-right hop needs no waypoints at all
        if ((ex in "RL" and en in "RL" and E[1] == N[1]) or (ex in "TB" and en in "TB" and E[0] == N[0])) \
                and not _crosses(clear, E, N):
            edges_out.append(_edge(e, s, t, exit_r, entry_r, ex, en, E, N, [], label_pos))
            continue

        a_kind = "x" if ex in ("R", "L") else "y"
        b_kind = "x" if en in ("L", "R") else "y"
        a_base = col_edge(s, ex) if a_kind == "x" else band(s, ex)
        b_base = col_edge(t, en) if b_kind == "x" else band(t, en)
        offs = track
        if a_kind == b_kind and a_base == b_base:       # one shared corridor, one slot
            a_val = b_val = slot(a_base, offs)
        else:
            a_val = slot(a_base, offs)
            b_val = slot(b_base, track)
        A = (a_val, E[1]) if a_kind == "x" else (E[0], a_val)
        B = (b_val, N[1]) if b_kind == "x" else (N[0], b_val)

        if a_kind == "x" and b_kind == "x":
            if A[0] == B[0] or (A[1] == B[1] and not _crosses(clear, A, B)):
                pts = [A, B]
            else:                                        # detour through a lane's padding band
                near = _near_band(lane_i, lane_of, node, s, t, (A[1] + B[1]) / 2)
                cy = slot(band(t, near), track)
                pts = [A, (A[0], cy), (B[0], cy), B]
        elif a_kind == "y" and b_kind == "x":
            pts = [A, (B[0], A[1]), B]
        elif a_kind == "x" and b_kind == "y":
            pts = [A, (A[0], B[1]), B]
        elif A[1] == B[1]:
            pts = [A, B]
        else:
            vx = slot(col_edge(t, "R" if node[t]["col"] < node[s]["col"] else "L"), track)
            pts = [A, (vx, A[1]), (vx, B[1]), B]

        edges_out.append(_edge(e, s, t, exit_r, entry_r, ex, en, E, N, pts, label_pos))

    def free_side(nid):
        return "T" if not blocked(nid, "T") else "B"

    return _place_labels(edges_out, boxes, node, theme, free_side)


def _seg_lengths(path):
    return [abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(path, path[1:])]


def _pos_along(path, seg_i):
    """draw.io's label anchor scale: −1 at the source, +1 at the target.

    The anchor is always a segment midpoint, so this is the arc length up to that
    midpoint over the total, mapped onto [−1, 1] and rounded for byte stability.
    """
    lens = _seg_lengths(path)
    total = sum(lens)
    if not total:
        return 0.0
    upto = sum(lens[:seg_i]) + lens[seg_i] / 2
    return round(2 * upto / total - 1, 3)


def _rects_hit(a, b):
    return (a[0] < b[0] + b[2] and b[0] < a[0] + a[2]
            and a[1] < b[1] + b[3] and b[1] < a[1] + a[3])


def _place_labels(edges_out, boxes, node, theme, free_side):
    """Computed label placement. A label has a position *and an extent*.

    One fixed anchor for every branch label cannot work: draw.io centres a label on its
    anchor, so even `Yes` would overlap its decision, because the exit stub is shorter
    than half the label. So candidates are generated from the edge's own path — roads
    first, then offset off the road, then beside the vertical runs, then beside the exit
    stub — and the first whose box clears every node and every label already placed
    wins. If none clears, candidate (a) is used and the edge is flagged for W208.
    """
    g = theme["geometry"]
    h = g["LINE_H"]
    clear = g["LABEL_CLEAR"]
    placed = []                                    # label boxes already on the sheet
    node_boxes = list(boxes.values())

    for e in edges_out:
        e["label_offset"] = None
        e["label_wide"] = False
        if not e["label"]:
            e["label_pos"] = None
            continue
        w = text_width(e["label"], theme) + 2 * g["LABEL_PAD"]
        e["label_wide"] = w > g["LABEL_W_MAX"]
        path = e["path"]
        segs = list(zip(path, path[1:]))
        mid = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in segs]
        horiz = sorted((i for i, (a, b) in enumerate(segs) if a[1] == b[1] and a[0] != b[0]),
                       key=lambda i: (-abs(segs[i][1][0] - segs[i][0][0]), i))
        vert = sorted((i for i, (a, b) in enumerate(segs) if a[0] == b[0] and a[1] != b[1]),
                      key=lambda i: (-abs(segs[i][1][1] - segs[i][0][1]), i))
        sx, sy, sw, sh = boxes[e["from"]]

        def gap_above(pt):
            """Clearance from a point up to the nearest node box overlapping the label's
            x-range — which of the two roads' neighbours a perpendicular offset should
            move away from."""
            xs = [b for b in node_boxes if b[0] < pt[0] + w / 2 and pt[0] - w / 2 < b[0] + b[2]]
            over = [pt[1] - (b[1] + b[3]) for b in xs if b[1] + b[3] <= pt[1]]
            return min(over) if over else 10 ** 6

        def gap_below(pt):
            xs = [b for b in node_boxes if b[0] < pt[0] + w / 2 and pt[0] - w / 2 < b[0] + b[2]]
            under = [b[1] - pt[1] for b in xs if b[1] >= pt[1]]
            return min(under) if under else 10 ** 6

        cands = []                                  # (segment index, (dx, dy))
        for i in horiz:                             # (a) on a horizontal run, no offset
            cands.append((i, (0.0, 0.0)))
        for i in horiz:                             # (b) ... offset off the road, roomier side first
            d = h / 2 + clear
            first = -d if gap_above(mid[i]) >= gap_below(mid[i]) else d
            cands += [(i, (0.0, first)), (i, (0.0, -first))]
        for i in vert:                              # (c) beside a vertical run, away from the source column
            d = w / 2 + clear
            first = -d if segs[i][0][0] <= sx + sw / 2 else d
            cands += [(i, (first, 0.0)), (i, (-first, 0.0))]
        if segs:                                    # (d) beside the exit stub, clear of the source node
            up = (sy - clear - h / 2) - mid[0][1]
            down = (sy + sh + clear + h / 2) - mid[0][1]
            cands += [(0, (0.0, up if free_side(e["from"]) == "T" else down)),
                      (0, (0.0, down if free_side(e["from"]) == "T" else up))]
        if not cands:
            e["label_pos"] = None
            continue

        def box_at(cand):
            i, (dx, dy) = cand
            return (mid[i][0] + dx - w / 2, mid[i][1] + dy - h / 2, w, h)

        chosen = next((c for c in cands
                       if not any(_rects_hit(box_at(c), b) for b in node_boxes)
                       and not any(_rects_hit(box_at(c), b) for b in placed)), None)
        e["label_clear"] = chosen is not None
        if chosen is None:
            chosen = cands[0]                       # fall back to (a); lint reports W208
        i, (dx, dy) = chosen
        e["label_pos"] = _pos_along(path, i)
        e["label_offset"] = (round(dx), round(dy)) if (dx or dy) else None
        placed.append(box_at(chosen))
    return edges_out


def page_size(theme, w, h):
    """Smallest landscape sheet from the theme's ladder that holds the canvas.
    A 14-column flow is an A1 plot, not an A4 — pinning A4 only hid the overflow. A theme
    that sets an explicit 'page' pins the sheet and opts out of the ladder."""
    if theme.get("page"):
        return tuple(theme["page"])
    for pw, ph in theme["page_sizes"]:
        if w <= pw and h <= ph:
            return pw, ph
    return tuple(theme["page_sizes"][-1])


def compute(spec, theme):
    """Full layout. All coordinates are ints; node x/y are lane-relative."""
    g = theme["geometry"]
    cols = assign_columns(spec)
    n_cols = max(cols.values()) + 1

    # sizing precedes the column table, because a column is as wide as its widest node,
    # and both precede routing, because a corridor's x is a column boundary
    sizes = {n["id"]: node_size(n["type"], n["label"], theme) for n in spec["nodes"]}
    widest = [0] * n_cols
    for n in spec["nodes"]:
        widest[cols[n["id"]]] = max(widest[cols[n["id"]]], sizes[n["id"]][0])
    columns = column_table(theme, widest)
    canvas_w = canvas_width(theme, columns)

    stacks = defaultdict(list)  # (lane, col) -> nodes in spec order
    for n in spec["nodes"]:
        stacks[(n["lane"], cols[n["id"]])].append(n)

    def stack_h(group):
        return sum(sizes[n["id"]][1] for n in group) + g["V_GAP"] * (len(group) - 1)

    # lane heights — one pass, because H_NODE is an input. The band follows from
    # the lane's deepest cell; a deeper cell grows the lane, it never shrinks the shapes.
    lane_h = {}
    for lane in spec["lanes"]:
        depth = max((len(grp) for (lid, _), grp in stacks.items() if lid == lane["id"]), default=0)
        lane_h[lane["id"]] = lane_height(theme, lane["label"], depth)

    # pass 2 — lanes stack below the title + legend bars, with a small gap between pools
    lanes_out = []
    y = g["TITLE_H"] + g["LEGEND_H"]
    for lane in spec["lanes"]:
        lanes_out.append({"id": lane["id"], "label": lane["label"],
                          "y": y, "h": lane_h[lane["id"]], "w": canvas_w})
        y += lane_h[lane["id"]] + g["LANE_GAP"]
    y -= g["LANE_GAP"]

    lane_order = {l["id"]: i for i, l in enumerate(spec["lanes"])}
    nodes_out = []
    for lid, col in sorted(stacks, key=lambda k: (lane_order[k[0]], k[1])):
        group = stacks[(lid, col)]
        x_center = columns[col]["x_left"] + columns[col]["w"] // 2
        off = (lane_h[lid] - stack_h(group)) // 2
        for n in group:
            w, h = sizes[n["id"]]
            nodes_out.append({"id": n["id"], "lane": lid, "type": n["type"], "label": n["label"],
                              "col": col, "x": x_center - w // 2, "y": off, "w": w, "h": h,
                              "step": n.get("step")})
            off += h + g["V_GAP"]

    # step badges: non-terminal nodes are numbered in flow order (column, then
    # lane); a node carrying an explicit SOP step shows that value verbatim instead, so
    # the badge cross-references the process table (3a, 11b) rather than our ordinal.
    r = g["BADGE_R"]
    numbered = sorted((n for n in nodes_out if n["type"] not in ("start", "end")),
                      key=lambda n: (n["col"], lane_order[n["lane"]]))
    for i, n in enumerate(numbered, 1):
        n["seq"] = i
        n["badge_text"] = n["step"] or str(i)
        n["badge"] = (n["x"] - r, n["y"] + n["h"] - r, 2 * r)

    # legend: one item per node type actually used; line samples only when >= 2 channels used
    used_types = [t for t in ("task", "decision", "subprocess", "document")
                  if any(n["type"] == t for n in spec["nodes"])]
    used_channels = [c for c in ("offline", "system", "user")
                     if any(e.get("channel", "offline") == c for e in spec["edges"])]
    if len(used_channels) < 2:
        used_channels = []
    keys = [("shape", t) for t in used_types] + [("line", c) for c in used_channels]
    items = [{"kind": kind, "key": key, "x": canvas_w - (len(keys) - i) * 110}
             for i, (kind, key) in enumerate(keys)]

    page_w, page_h = page_size(theme, canvas_w, y)
    return {"canvas_w": canvas_w, "canvas_h": y, "lanes": lanes_out, "nodes": nodes_out,
            "cols": cols, "columns": columns, "title_h": g["TITLE_H"],
            "page_w": page_w, "page_h": page_h,
            "edges": _route_edges(spec, nodes_out, lanes_out, cols, columns, theme),
            "legend": {"y": g["TITLE_H"], "h": g["LEGEND_H"], "items": items}}
