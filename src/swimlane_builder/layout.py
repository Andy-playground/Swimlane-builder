"""Layout engine. Pure geometry; never touches XML."""
import re
from collections import defaultdict

# Port sides. The ratio that varies when several edges fan out on one side is the
# second component for L/R (vertical spread) and the first for T/B (horizontal).
ROUND_OUTLINE = ("start", "end", "decision")  # ports off-centre sit outside the outline


def corridor_need(theme, k):
    """Width a corridor needs to carry `k` parallel runs:
    `(k − 1) · TRACK_PITCH + 2 · KERB` — the runs `TRACK_PITCH` apart, centred on the
    corridor's axis, and `KERB` of clear space beyond the outermost one on each side.

    A fixed number of tracks per corridor, reused cyclically once they ran out, put two
    runs on top of each other the first time a gutter carried four. A corridor is now as
    wide as its own traffic: this is the width, `k` is the overlap depth `_route_edges`
    measures, and `column_table` and the lane heights are built from it.
    """
    g = theme["geometry"]
    return (max(k, 1) - 1) * g["TRACK_PITCH"] + 2 * g["KERB"]


def corridor_w(theme):
    """The baseline corridor — `corridor_need(TRACKS)` — every road and gutter is built
    with before any traffic is counted, so an empty corridor is never narrower than this.
    `ROAD_W` and `GUTTER` are this number until their own traffic asks for more."""
    return corridor_need(theme, theme["geometry"]["TRACKS"])


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


def lane_height(theme, label, depth, road=None):
    """A lane band. `H_NODE` is an input, so this needs no pass of its own.

    **A lane title is a height demand, and this is the only place that says so.** The
    lane style pins `horizontal=0`, so draw.io renders the lane's name rotated, running
    along the lane's height inside a band `LANE_TITLE_W` wide — which makes
    `LANE_TITLE_W` the title's *line budget*, not a decoration.

    A deeper cell grows the lane; it never shrinks the shapes. Splitting the band between
    two shapes was measured and rejected — at `H_NODE` 120 a halved box offers two
    wrapped lines at 14 pt, while real SOP labels need up to six.

    `road` is this lane's road width — the baseline unless the lane's own
    traffic needs more; both roads take the wider of the two so the shape row stays
    centred.
    """
    g = theme["geometry"]
    road = corridor_w(theme) if road is None else road
    h_shapes = 2 * road + depth * g["H_NODE"] + max(depth - 1, 0) * g["V_GAP"]
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
        return round(x, 6), round(y, 6)
    if side in ("L", "R"):
        d = _inset(ntype, y)
        x = d if side == "L" else 1 - d
    else:
        d = _inset(ntype, x)
        y = d if side == "T" else 1 - d
    return round(x, 6), round(y, 6)


def _crosses(boxes, p, q):
    """True if segment p-q passes through the interior of any node box."""
    (x1, y1), (x2, y2) = p, q
    lo_x, hi_x, lo_y, hi_y = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
    for bx, by, bw, bh in boxes:
        if bx < hi_x - 1 and bx + bw > lo_x + 1 and by < hi_y - 1 and by + bh > lo_y + 1:
            return True
    return False


def column_table(theme, widest, gutter_need=None):
    """The column table — `columns[c] = {x_left, w}`, where:

        COL_W(c) = roundup_GRID( w_max(c) + max( GUTTER, need(c), need(c + 1) ) )

    where `need(b)` is the width the gutter on column boundary `b` needs for its own
    traffic (boundary `b` is the left edge of column `b`). The canvas width, every node's
    x-centre and every routing corridor's x read this table. Any drift between a copy that
    places nodes and a copy that places corridors would put an edge through a node body,
    so this is the single source.

    **The corridor clearance is part of the width's definition, not a check run after
    the fact.** A node is centred, so each of its sides sits half the column's slack from
    a boundary; that half is at least half of what either boundary's gutter needs, so
    every run in the gutter — at most `(k − 1)·TRACK_PITCH / 2` off the boundary — clears
    every box in the columns either side by at least `KERB`. A theme cannot widen a node
    into a corridor, and traffic cannot crowd one, because the corridor widens with both.
    """
    g = theme["geometry"]
    grid, base = g["GRID"], corridor_w(theme)
    need = gutter_need or {}
    x = g["LANE_TITLE_W"] + g["MARGIN_X"]
    columns = []
    for c, w_max in enumerate(widest):
        gutter = max(base, need.get(c, 0), need.get(c + 1, 0))
        w = -(-(w_max + gutter) // grid) * grid            # roundup_GRID
        columns.append({"x_left": x, "w": w})
        x += w
    return columns


def canvas_width(theme, columns):
    """`LANE_TITLE_W + 2 · MARGIN_X + Σ COL_W(c)`."""
    g = theme["geometry"]
    return g["LANE_TITLE_W"] + 2 * g["MARGIN_X"] + sum(c["w"] for c in columns)


class _Track:
    """A run's place in a corridor, decided late.

    A path is built first with every corridor run as one of these, carrying only *which*
    corridor it rides — `("gutter", b)` for column boundary `b`, `("road", lane, side)`
    for one of a lane's two roads. Its offset is assigned once every path exists, from
    the runs that actually overlap it, so the allocator counts overlaps rather than calls."""
    __slots__ = ("key", "base", "val")

    def __init__(self, key, base):
        self.key, self.base, self.val = key, base, None


def _at(v):
    """A coordinate as routing reasons about it: a track's corridor axis until the track
    has an offset."""
    return v.base if isinstance(v, _Track) else v


def _orders(n):
    """Every ordering of `range(n)` — `itertools.permutations` without the import, which
    the stdlib-only runtime does not list. Callers that need a tie-break impose one."""
    if n == 0:
        yield ()
        return
    for rest in _orders(n - 1):
        for i in range(n, -1, -1):
            yield rest[:i] + (n - 1,) + rest[i:]


def _parallel_close(p, q, a, b, gap):
    """True if segment p-q and segment a-b are parallel, closer than `gap`, and overlap
    along their length — two runs a reader cannot tell apart."""
    for ax in (0, 1):
        o = 1 - ax
        if p[ax] == q[ax] and a[ax] == b[ax] and abs(p[ax] - a[ax]) < gap:
            if min(max(p[o], q[o]), max(a[o], b[o])) > max(min(p[o], q[o]), min(a[o], b[o])):
                return True
    return False


FAN_SEARCH_MAX = 4      # ports on one face whose orders are all tried (4! = 24)


def _crossings(edges):
    """How many times a vertical segment of one edge crosses a horizontal segment of
    another, strictly inside both — the budget the routing tests hold each example to."""
    segs = [(i, p, q) for i, e in enumerate(edges) for p, q in zip(e["path"], e["path"][1:])]
    vert = [(i, p, q) for i, p, q in segs if p[0] == q[0] and p[1] != q[1]]
    horiz = [(i, p, q) for i, p, q in segs if p[1] == q[1] and p[0] != q[0]]
    n = 0
    for i, v1, v2 in vert:
        lo, hi = sorted((v1[1], v2[1]))
        for j, h1, h2 in horiz:
            if i != j and min(h1[0], h2[0]) < v1[0] < max(h1[0], h2[0]) and lo < h1[1] < hi:
                n += 1
    return n


def _assign_tracks(uses, pitch):
    """Offsets for every corridor run. Returns {corridor key: overlap depth}.

    Runs in one corridor are grouped by overlap along the corridor — spans closer than
    one `pitch` count as overlapping, so two runs never meet end to end on one line —
    and each group of `k` runs takes `k` distinct tracks, `pitch` apart and centred on
    the corridor's axis. That is the whole invariant: no two runs share a line, at any
    depth. Within a group the order is the one that crosses least, where a run's stub
    leaving towards the far side of a neighbour inside that neighbour's span is one
    crossing; ties, and groups too large to search, keep the spans' own order.
    """
    depth = {}

    def cost(u, v):                                 # u on the lower-coordinate track
        c = sum(1 for at, side in u["ends"] if side > 0 and v["lo"] < at < v["hi"])
        return c + sum(1 for at, side in v["ends"] if side < 0 and u["lo"] < at < u["hi"])

    for key in sorted(uses, key=repr):
        runs = sorted(uses[key], key=lambda u: (u["lo"], u["hi"], u["order"]))
        groups, cur, reach = [], [], None
        for u in runs:
            if cur and u["lo"] <= reach + pitch:
                cur.append(u)
                reach = max(reach, u["hi"])
            else:
                if cur:
                    groups.append(cur)
                cur, reach = [u], u["hi"]
        groups.append(cur)
        for grp in groups:
            k = len(grp)
            order = range(k)
            if 1 < k <= 6:
                order = min(_orders(k), key=lambda p: (sum(cost(grp[p[a]], grp[p[b]])
                                                           for a in range(k) for b in range(a + 1, k)), p))
            for j, i in enumerate(order):
                grp[i]["track"].val = round(grp[i]["track"].base + (j - (k - 1) / 2) * pitch)
            depth[key] = max(depth.get(key, 0), k)
    return depth


def _route_edges(spec, nodes_out, lanes_out, cols, columns, theme):
    """Explicit Manhattan paths. Returns `(edges, depth)` — the routed edges, and the
    overlap depth of every corridor, which the column table and lane heights are sized from.

    Two kinds of path, and both keep clear of every node by construction:
    - a **shortcut** — one bend, straight from the exit face to the entry face — taken
      only when both of its segments clear every other node by half a baseline corridor
      and no other shortcut runs alongside it;
    - otherwise a **corridor path**: vertical runs on column boundaries, horizontal runs in
      a lane's roads, both free of nodes because the column and lane sizes make them so.
    """
    g = theme["geometry"]
    node = {n["id"]: n for n in nodes_out}
    lane_of = {l["id"]: l for l in lanes_out}
    lane_i = {l["id"]: i for i, l in enumerate(spec["lanes"])}
    steps = {n["id"]: n.get("step") for n in spec["nodes"]}
    primary_labels = {p.lower() for p in theme["primary_labels"]}
    right_edge = columns[-1]["x_left"] + columns[-1]["w"]

    def box(nid):
        n = node[nid]
        return (n["x"], lane_of[n["lane"]]["y"] + n["y"], n["w"], n["h"])

    boxes = {n["id"]: box(n["id"]) for n in nodes_out}

    def others(s, t):
        """Boxes an edge must clear. Its own endpoints are excluded: a port projected
        onto a rhombus or ellipse sits inside the bounding box by design, so the last
        few px of the stub legitimately run through the box's empty corner."""
        return [b for nid, b in boxes.items() if nid not in (s, t)]

    def gutter(b):                                  # a run on column boundary b
        return _Track(("gutter", b), columns[b]["x_left"] if b < len(columns) else right_edge)

    def col_edge(nid, side):                        # the column boundary beside a node
        return gutter(node[nid]["col"] + (1 if side == "R" else 0))

    def road_y(lane, side):
        half = lane["road"] // 2
        return lane["y"] + lane["h"] - half if side == "B" else lane["y"] + half

    def band(nid, side):                            # a run in one of the lane's two roads
        lane = lane_of[node[nid]["lane"]]
        return _Track(("road", lane["id"], side), road_y(lane, side))

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

    exits = []
    for e in spec["edges"]:
        s, t = e["from"], e["to"]
        below = lane_i[node[t]["lane"]] > lane_i[node[s]["lane"]]
        if e.get("kind", "normal") == "feedback":
            exits.append(pick(s, ("B", "T", "L")))
        elif node[s]["type"] == "decision" and not primary.get(id(e)):
            exits.append(pick(s, ("B", "T", "L") if below or node[t]["lane"] == node[s]["lane"]
                              else ("T", "B", "L")))
        else:
            exits.append("R")
    exit_faces = {(e["from"], ex) for e, ex in zip(spec["edges"], exits)}

    sides = []
    for e, ex in zip(spec["edges"], exits):
        s, t = e["from"], e["to"]
        ls, lt = lane_i[node[s]["lane"]], lane_i[node[t]["lane"]]
        if node[t]["col"] == node[s]["col"]:
            en = pick(t, ("T", "B") if box(t)[1] > box(s)[1] else ("B", "T"))
        else:
            en = "L"
            # forward flow arriving from another lane enters on the face it arrives from,
            # unless that face is blocked or already carries one of the target's exits
            if e.get("kind", "normal") == "normal" and node[t]["col"] > node[s]["col"] and lt != ls:
                face = "T" if lt > ls else "B"
                if not blocked(t, face) and (t, face) not in exit_faces:
                    en = face
        sides.append((ex, en))

    # ---- 2. fan-out: several edges on one face attach at distinct points (i/(k+1))
    groups = defaultdict(list)
    for i, (e, (ex, en)) in enumerate(zip(spec["edges"], sides)):
        groups[(e["from"], ex, "out")].append((node[e["to"]]["col"], lane_i[node[e["to"]]["lane"]], e["to"], i))
        groups[(e["to"], en, "in")].append((node[e["from"]]["col"], lane_i[node[e["from"]]["lane"]], e["from"], i))
    order = {key: [m[-1] for m in sorted(members)] for key, members in groups.items()}

    def ratios(order):
        out = {}
        for (nid, side, kind), members in order.items():
            k = len(members)
            for j, i in enumerate(members):
                out[(i, kind)] = round(0.5 if k == 1 else (j + 1) / (k + 1), 3)
        return out

    def port(nid, side, r):
        """A port on face `side` at ratio `r`, snapped so its along-face coordinate is a
        whole pixel — the axis the first or last waypoint shares with it — then projected
        onto the visible outline. Returns (ratio pair, point)."""
        bx, by, bw, bh = boxes[nid]
        if side in ("L", "R"):
            along = round(by + bh * r)
            rel = _on_outline(node[nid]["type"], side, 0.0 if side == "L" else 1.0,
                              round((along - by) / bh, 6))
            return rel, (round(bx + bw * rel[0]), along)
        along = round(bx + bw * r)
        rel = _on_outline(node[nid]["type"], side, round((along - bx) / bw, 6),
                          0.0 if side == "T" else 1.0)
        return rel, (along, round(by + bh * rel[1]))

    def build(ratio):
        """Steps 3–4 for one assignment of ports: every path, then every track."""
        # ---- 3. paths, with every corridor run left as a _Track
        clearance = corridor_w(theme) // 2              # what a lone run in a baseline corridor keeps
        shortcuts = []
        raw = []
        for i, (e, (ex, en)) in enumerate(zip(spec["edges"], sides)):
            s, t = e["from"], e["to"]
            exit_r, E = port(s, ex, ratio[(i, "out")])
            entry_r, N = port(t, en, ratio[(i, "in")])
            clear = others(s, t)

            # straight shot — the common left-to-right hop needs no waypoints at all
            if ((ex in "RL" and en in "RL" and E[1] == N[1]) or (ex in "TB" and en in "TB" and E[0] == N[0])) \
                    and not _crosses(clear, E, N):
                raw.append((e, s, t, exit_r, entry_r, ex, en, E, N, []))
                continue

            # shortcut — one bend, when the faces point at each other's quadrant
            corner = None
            if ex in "RL" and en in "TB" and (N[0] > E[0]) == (ex == "R") and (N[1] > E[1]) == (en == "T"):
                corner = (N[0], E[1])
            elif ex in "TB" and en in "RL" and (N[1] > E[1]) == (ex == "B") and (N[0] > E[0]) == (en == "L"):
                corner = (E[0], N[1])
            if corner is not None:
                fat = [(bx - clearance, by - clearance, bw + 2 * clearance, bh + 2 * clearance)
                       for bx, by, bw, bh in clear]
                legs = [(E, corner), (corner, N)]
                if not any(_crosses(fat, p, q) for p, q in legs) and \
                        not any(_parallel_close(p, q, a, b, g["TRACK_PITCH"]) for p, q in legs for a, b in shortcuts):
                    shortcuts.extend(legs)
                    raw.append((e, s, t, exit_r, entry_r, ex, en, E, N, [corner]))
                    continue

            a_kind = "x" if ex in ("R", "L") else "y"
            b_kind = "x" if en in ("L", "R") else "y"
            a_val = col_edge(s, ex) if a_kind == "x" else band(s, ex)
            b_val = col_edge(t, en) if b_kind == "x" else band(t, en)
            if a_val.key == b_val.key:                  # one shared corridor, one run
                b_val = a_val
            A = (a_val, E[1]) if a_kind == "x" else (E[0], a_val)
            B = (b_val, N[1]) if b_kind == "x" else (N[0], b_val)

            if a_kind == "x" and b_kind == "x":
                if a_val is b_val or (A[1] == B[1] and not _crosses(clear, (_at(A[0]), A[1]), (_at(B[0]), B[1]))):
                    pts = [A, B]
                else:                                    # detour through a lane's road
                    near = _near_band(lane_i, lane_of, node, s, t, (A[1] + B[1]) / 2)
                    cy = band(t, near)
                    pts = [A, (A[0], cy), (B[0], cy), B]
            elif a_kind == "y" and b_kind == "x":
                pts = [A, (B[0], A[1]), B]
            elif a_kind == "x" and b_kind == "y":
                pts = [A, (A[0], B[1]), B]
            elif a_val is b_val:
                pts = [A, B]
            else:
                vx = col_edge(t, "R" if node[t]["col"] < node[s]["col"] else "L")
                pts = [A, (vx, A[1]), (vx, B[1]), B]
            raw.append((e, s, t, exit_r, entry_r, ex, en, E, N, pts))

        # ---- 4. tracks: every corridor run gets an offset from the runs it actually overlaps
        uses = defaultdict(list)
        for order, r in enumerate(raw):
            path = [r[7]] + r[9] + [r[8]]
            seen = set()
            for p in path:
                for ax in (0, 1):
                    tk = p[ax]
                    if not isinstance(tk, _Track) or id(tk) in seen:
                        continue
                    seen.add(id(tk))
                    idx = [k for k, q in enumerate(path) if q[ax] is tk]
                    along = [_at(path[k][1 - ax]) for k in idx]
                    ends = []
                    for k_end, k_nb in ((idx[0], idx[0] - 1), (idx[-1], idx[-1] + 1)):
                        if 0 <= k_nb < len(path):
                            ends.append((_at(path[k_end][1 - ax]), -1 if _at(path[k_nb][ax]) < tk.base else 1))
                    uses[tk.key].append({"track": tk, "lo": min(along), "hi": max(along),
                                         "ends": ends, "order": order})
        depth = _assign_tracks(uses, g["TRACK_PITCH"])

        def resolve(p):
            return tuple(v.val if isinstance(v, _Track) else v for v in p)

        edges_out = []
        for e, s, t, exit_r, entry_r, ex, en, E, N, pts in raw:
            path = [E]
            for p in [resolve(p) for p in pts] + [N]:
                if p != path[-1]:                       # a run on its corridor's axis can leave a zero-length leg
                    path.append(p)
            edges_out.append(_edge(e, s, t, exit_r, entry_r, ex, en, path[0], path[-1], path[1:-1], None))
        return edges_out, depth

    # ---- 5. port order is searched, not configured: where several edges share a face,
    # every order of their ports is tried and the one with the fewest crossings kept. A
    # run's far end does not say where it arrives from — a feedback loop that wraps round
    # through a gutter arrives from the opposite side — so the order is judged on the
    # routed paths themselves. Ties keep the (column, lane, id) order.
    edges_out, depth = build(ratios(order))
    best = _crossings(edges_out)
    for key in sorted(order, key=repr):
        members = order[key]
        if not 2 <= len(members) <= FAN_SEARCH_MAX or best == 0:
            continue
        for perm in _orders(len(members)):
            trial = {**order, key: [members[j] for j in perm]}
            if trial[key] == order[key]:
                continue
            cand, cand_depth = build(ratios(trial))
            n = _crossings(cand)
            if n < best:
                best, order, edges_out, depth = n, trial, cand, cand_depth

    def free_side(nid):
        return "T" if not blocked(nid, "T") else "B"

    return _place_labels(edges_out, boxes, node, theme, free_side), depth


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
            # a stub leaving by the top or bottom has its label on that side; a label on the
            # far side of the node from its own line reads as belonging to another edge
            first = e["exit_side"] if e["exit_side"] in ("T", "B") else free_side(e["from"])
            cands += [(0, (0.0, up if first == "T" else down)),
                      (0, (0.0, down if first == "T" else up))]
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
    """Full layout. All coordinates are ints; node x/y are lane-relative.

    Corridors are sized by their traffic, and traffic is only known once edges
    are routed, so placement and routing run until the corridor widths stop growing.
    Widths only ever grow, by at least one `TRACK_PITCH` per round, and no corridor can
    need more tracks than there are edges, so the loop ends; on the shipped examples it
    settles on the second round.
    """
    g = theme["geometry"]
    cols = assign_columns(spec)
    n_cols = max(cols.values()) + 1

    # sizing precedes the column table, because a column is as wide as its widest node,
    # and both precede routing, because a corridor's x is a column boundary
    sizes = {n["id"]: node_size(n["type"], n["label"], theme) for n in spec["nodes"]}
    widest = [0] * n_cols
    for n in spec["nodes"]:
        widest[cols[n["id"]]] = max(widest[cols[n["id"]]], sizes[n["id"]][0])

    stacks = defaultdict(list)  # (lane, col) -> nodes in spec order
    for n in spec["nodes"]:
        stacks[(n["lane"], cols[n["id"]])].append(n)
    depth_of = {lane["id"]: max((len(grp) for (lid, _), grp in stacks.items() if lid == lane["id"]), default=0)
                for lane in spec["lanes"]}
    lane_order = {l["id"]: i for i, l in enumerate(spec["lanes"])}

    def stack_h(group):
        return sum(sizes[n["id"]][1] for n in group) + g["V_GAP"] * (len(group) - 1)

    gutter_need, road_need = {}, {}
    while True:
        columns = column_table(theme, widest, gutter_need)
        canvas_w = canvas_width(theme, columns)

        # lane heights — one pass, because H_NODE is an input. The band follows
        # from the lane's deepest cell and its roads; a deeper cell grows the lane, it
        # never shrinks the shapes.
        lanes_out = []
        y = g["TITLE_H"] + g["LEGEND_H"]
        for lane in spec["lanes"]:
            road = max(corridor_w(theme), road_need.get(lane["id"], 0))
            h = lane_height(theme, lane["label"], depth_of[lane["id"]], road)
            lanes_out.append({"id": lane["id"], "label": lane["label"],
                              "y": y, "h": h, "w": canvas_w, "road": road})
            y += h + g["LANE_GAP"]
        y -= g["LANE_GAP"]
        lane_h = {l["id"]: l["h"] for l in lanes_out}

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

        edges, depth = _route_edges(spec, nodes_out, lanes_out, cols, columns, theme)
        grew = False
        for key, k in depth.items():
            need = corridor_need(theme, k)
            store, at = (gutter_need, key[1]) if key[0] == "gutter" else (road_need, key[1])
            if need > store.get(at, 0):
                store[at] = need
                grew = True
        if not grew:
            break

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
            "page_w": page_w, "page_h": page_h, "edges": edges,
            "legend": {"y": g["TITLE_H"], "h": g["LEGEND_H"], "items": items}}
