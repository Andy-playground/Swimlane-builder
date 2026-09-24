"""Schema check + semantic lint. Stdlib only (the schema is fixed, so the check is hand-rolled)."""
import re
from collections import defaultdict

from . import layout

IDENT = re.compile(r"^[a-z][a-z0-9_]*$")
NODE_TYPES = ("start", "end", "task", "decision", "subprocess", "document")
EDGE_KINDS = ("normal", "feedback")
EDGE_CHANNELS = ("offline", "system", "user")


def lint(spec, theme=None):
    """Return [(code, message)]. Codes starting with 'E' are fatal, 'W' are warnings."""
    issues = []
    if not _shape(spec, issues):
        return issues

    lanes, nodes, edges = spec["lanes"], spec["nodes"], spec["edges"]
    lane_ids = [l["id"] for l in lanes]
    node_ids = [n["id"] for n in nodes]

    seen = set()
    for i in lane_ids + node_ids:
        if i in seen:
            issues.append(("E001", f"duplicate id '{i}' — ids must be unique across lanes and nodes"))
        seen.add(i)

    seen_steps = {}
    for n in nodes:
        st = n.get("step")
        if st is None:
            continue
        if st in seen_steps:
            issues.append(("E001", f"duplicate step '{st}' on '{seen_steps[st]}' and '{n['id']}' — step numbers must be unique"))
        else:
            seen_steps[st] = n["id"]

    refs_ok = True
    lane_set, node_set = set(lane_ids), set(node_ids)
    for n in nodes:
        if n["lane"] not in lane_set:
            issues.append(("E101", f"node '{n['id']}' references unknown lane '{n['lane']}'"))
            refs_ok = False
    for e in edges:
        for end in ("from", "to"):
            if e[end] not in node_set:
                issues.append(("E101", f"edge {e['from']}->{e['to']}: unknown node id '{e[end]}'"))
                refs_ok = False

    starts = [n["id"] for n in nodes if n["type"] == "start"]
    if len(starts) != 1:
        issues.append(("E001", f"exactly one start node required, found {len(starts)}"))
    else:
        start_lane = next(n["lane"] for n in nodes if n["type"] == "start")
        if lanes[0]["id"] != start_lane:
            issues.append(("W203", "start node is not in the first lane — put the initiator's lane first"))
    if not any(n["type"] == "end" for n in nodes):
        issues.append(("E001", "at least one end node required"))

    outgoing = defaultdict(list)
    for e in edges:
        outgoing[e["from"]].append(e)
    for n in nodes:
        if n["type"] != "decision":
            continue
        outs = outgoing[n["id"]]
        if len(outs) < 2:
            issues.append(("E103", f"decision '{n['id']}' has {len(outs)} outgoing edge(s), needs >= 2"))
        for e in outs:
            if not e.get("label"):
                issues.append(("E103", f"decision branch {e['from']}->{e['to']} is unlabeled"))

    if refs_ok:
        if len(starts) == 1:
            nxt = defaultdict(list)
            for e in edges:
                if e.get("kind", "normal") == "normal":
                    nxt[e["from"]].append(e["to"])
            reachable, frontier = {starts[0]}, [starts[0]]
            while frontier:
                for t in nxt[frontier.pop()]:
                    if t not in reachable:
                        reachable.add(t)
                        frontier.append(t)
            for i in node_ids:
                if i not in reachable:
                    issues.append(("E104", f"node '{i}' unreachable from start via normal edges"))
        try:
            cols = layout.assign_columns(spec)
        except layout.CycleError as exc:
            u, v = exc.edge
            issues.append(("E102", f"cycle among normal edges via {u}->{v} — declare that edge kind:'feedback' if it is a rework loop"))
        else:
            # an explicit 'col' is a floor (layout.assign_columns), so a normal edge can no longer point
            # backward — but a floor below the layered minimum has no effect, and
            # silently discarding what the author wrote would be worse than saying so
            for n in nodes:
                if "col" in n and cols[n["id"]] != n["col"]:
                    issues.append(("W206", f"node '{n['id']}' asks for column {n['col']} but its predecessors "
                                           f"force column {cols[n['id']]} — 'col' raises a node, it cannot pull one back"))
            if max(cols.values()) + 1 > 14:
                issues.append(("W202", f"{max(cols.values()) + 1} columns after layering — consider splitting the flow"))
            stacked = defaultdict(list)
            for n in nodes:
                if n["type"] == "decision":
                    stacked[(n["lane"], cols[n["id"]])].append(n["id"])
            for (lane, col), ids in sorted(stacked.items()):
                if len(ids) > 1:
                    issues.append(("W204", f"decisions {sorted(ids)} share lane '{lane}' column {col} — "
                                           f"give one an explicit 'col' so their branches do not compete for the same corridors"))

    # badges fall back to a computed ordinal where no 'step' is given, so a
    # partly-numbered spec prints two numbering systems side by side and the same
    # number can appear twice
    badged = [n for n in nodes if n["type"] not in ("start", "end")]
    with_step = [n["id"] for n in badged if n.get("step")]
    if badged and 0 < len(with_step) < len(badged):
        missing = sorted(n["id"] for n in badged if not n.get("step"))
        issues.append(("W205", f"{len(with_step)} of {len(badged)} numbered nodes carry a 'step' — "
                               f"badges will mix SOP steps with computed ordinals; add 'step' to {missing}"))

    # The bound is the box, not a word count. A label that will not wrap into the lines
    # H_NODE offers even at NODE_W_MAX is drawn at the maximum width and overflows; the
    # generator never truncates it, so the spec is told instead.
    if theme:
        g = theme["geometry"]
        budget = layout.lines_available(theme)
        usable = g["NODE_W_MAX"] - 2 * g["PAD_TEXT_X"]
        # Boxes only. A start/end terminal is a fixed circle sized by the theme's
        # TERMINAL_D, not by its label, so a long terminal label is currently unreported
        # (a known limitation, listed in the README).
        for n in nodes:
            if n["type"] in ("start", "end"):
                continue
            widest_word = max((layout.text_width(w, theme) for w in n["label"].split()), default=0)
            if widest_word > usable or len(layout.wrap_lines(n["label"], usable, theme)) > budget:
                issues.append(("W201", f"node '{n['id']}' label '{n['label']}' does not wrap into "
                                       f"{budget} lines even at {g['NODE_W_MAX']} px — it will overflow "
                                       f"the shape; shorten it"))

    # A branch label states the condition and nothing else. The consequence is a step,
    # so it belongs on the target node — and the 24 px corridors leave a sentence-length
    # label nowhere to sit, which is why this is a rule and not a preference.
    if theme:
        max_words = theme["geometry"]["LABEL_MAX_WORDS"]
        types = {n["id"]: n["type"] for n in nodes}
        for e in edges:
            lab = e.get("label", "")
            if types.get(e["from"]) == "decision" and len(lab.split()) > max_words:
                issues.append(("W207", f"branch label {e['from']}->{e['to']} '{lab}' is longer than "
                                       f"{max_words} words — state the condition only and move the "
                                       f"consequence into the target node (or its 'note')"))

    return issues


def lint_layout(spec, theme, lay):
    """The lint checks only the placed geometry can answer (W208, W209).

    Kept separate from `lint` because it costs a full layout: `cli` already computes one
    and passes it in, so the check is free where it runs.
    """
    issues = []
    g = theme["geometry"]

    # W209 — the one-screen budget. One screen is a budget the author is *told* about,
    # never a constraint the layout chases: the generator reports the achieved read size
    # and does not reshape the flow to improve it. A hard constraint would force
    # multi-sheet output for most real SOPs, against the rule of one flow, one page.
    zoom = min(g["FIT_W"] / lay["canvas_w"], g["FIT_H"] / lay["canvas_h"])
    read = theme["text_metric"]["FONT_SIZE"] * zoom
    if read < g["READ_MIN_PX"]:
        fits = int(g["FIT_W"] / (g["READ_MIN_PX"] / theme["text_metric"]["FONT_SIZE"])
                   // (lay["canvas_w"] / len(lay["columns"])))
        issues.append(("W209", f"fitted to {g['FIT_W']}x{g['FIT_H']} the body text reads at "
                               f"{read:.1f} px ({zoom * 100:.0f}% zoom), below the {g['READ_MIN_PX']} px "
                               f"floor — about {fits} of this flow's {len(lay['columns'])} columns fit "
                               f"one screen. Shorten the SOP or split it into two flows; the diagram "
                               f"is not reshaped to chase the budget"))

    wide = g["LABEL_W_MAX"]
    for e in lay["edges"]:
        if not e["label"]:
            continue
        if not e.get("label_clear", True):
            issues.append(("W208", f"no clear anchor on the path of {e['from']}->{e['to']} for label "
                                   f"'{e['label']}' — it is drawn over a node or another label; shorten it "
                                   f"or give the flow more room"))
        elif e.get("label_wide"):
            issues.append(("W208", f"label '{e['label']}' on {e['from']}->{e['to']} is wider than "
                                   f"{wide} px — shorten it"))
    return issues


def _shape(spec, issues):
    """Structural check mirroring schema/spec.schema.json. Returns False on any E001."""
    before = len(issues)

    def err(msg):
        issues.append(("E001", msg))

    if not isinstance(spec, dict):
        err("spec must be a JSON object")
        return False
    shapes = {"meta": dict, "lanes": list, "nodes": list, "edges": list}
    for key, typ in shapes.items():
        if not isinstance(spec.get(key), typ):
            err(f"'{key}' missing or not a {typ.__name__}")
    if unknown := set(spec) - set(shapes):
        err(f"unknown top-level keys {sorted(unknown)}")
    if len(issues) > before:
        return False

    def s(v):
        return isinstance(v, str) and len(v) > 0

    def ident(v):
        return s(v) and bool(IDENT.match(v))

    meta = spec["meta"]
    if not s(meta.get("sop_id")) or not s(meta.get("title")):
        err("meta.sop_id and meta.title are required non-empty strings")
    if unknown := set(meta) - {"sop_id", "title", "version", "theme"}:
        err(f"unknown meta keys {sorted(unknown)}")

    if len(spec["lanes"]) < 1:
        err("at least 1 lane required")
    if len(spec["nodes"]) < 2:
        err("at least 2 nodes required")
    if len(spec["edges"]) < 1:
        err("at least 1 edge required")

    for i, l in enumerate(spec["lanes"]):
        if not isinstance(l, dict) or not ident(l.get("id")) or not s(l.get("label")):
            err(f"lanes[{i}]: needs ident 'id' and non-empty 'label'")
            continue
        if unknown := set(l) - {"id", "label"}:
            err(f"lanes[{i}] ('{l['id']}'): unknown keys {sorted(unknown)}")

    for i, n in enumerate(spec["nodes"]):
        if not isinstance(n, dict) or not ident(n.get("id")) or not ident(n.get("lane")) \
                or n.get("type") not in NODE_TYPES or not s(n.get("label")):
            err(f"nodes[{i}]: needs ident 'id'/'lane', type in {NODE_TYPES}, non-empty 'label'")
            continue
        if "col" in n and not (isinstance(n["col"], int) and not isinstance(n["col"], bool) and n["col"] >= 0):
            err(f"nodes[{i}] ('{n['id']}'): 'col' must be an integer >= 0")
        if "step" in n and not s(n.get("step")):
            err(f"nodes[{i}] ('{n['id']}'): 'step' must be a non-empty string")
        if "note" in n and not isinstance(n["note"], str):
            err(f"nodes[{i}] ('{n['id']}'): 'note' must be a string")
        if unknown := set(n) - {"id", "lane", "type", "label", "col", "step", "note"}:
            err(f"nodes[{i}] ('{n['id']}'): unknown keys {sorted(unknown)}")

    for i, e in enumerate(spec["edges"]):
        if not isinstance(e, dict) or not ident(e.get("from")) or not ident(e.get("to")):
            err(f"edges[{i}]: needs ident 'from' and 'to'")
            continue
        if "kind" in e and e["kind"] not in EDGE_KINDS:
            err(f"edges[{i}] ({e['from']}->{e['to']}): kind must be one of {EDGE_KINDS}")
        if "channel" in e and e["channel"] not in EDGE_CHANNELS:
            err(f"edges[{i}] ({e['from']}->{e['to']}): channel must be one of {EDGE_CHANNELS}")
        if "label" in e and not isinstance(e["label"], str):
            err(f"edges[{i}] ({e['from']}->{e['to']}): 'label' must be a string")
        if unknown := set(e) - {"from", "to", "label", "kind", "channel"}:
            err(f"edges[{i}] ({e['from']}->{e['to']}): unknown keys {sorted(unknown)}")

    return len(issues) == before
