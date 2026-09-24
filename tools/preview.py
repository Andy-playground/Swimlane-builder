#!/usr/bin/env python3
"""Dev-only preview renderer: .drawio (mxGraph XML) -> SVG -> PNG screenshot.

Not part of the runtime pipeline. It exists so a change to layout/xmlgen can be
checked visually without opening draw.io by hand: it re-reads the
emitted XML exactly as draw.io would, resolves lane-relative coordinates, and
draws the shapes, ports and edge paths the generator asked for.

It approximates draw.io's renderer; it is evidence about *our* geometry, not a
substitute for the manual draw.io check before regenerating a golden.

    python3 tools/preview.py out.drawio -o shots/out.png
    python3 tools/preview.py out.drawio -o shots/out.svg --no-png
"""
import argparse
import html
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from swimlane_builder import layout, themes  # noqa: E402  — dev tool, after the path fix-up

THEME = themes.load()

CHROMIUM_CANDIDATES = [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome",
    "chromium", "chromium-browser", "google-chrome",
]
JETTY = 20
CORNER = 8


# ---------------------------------------------------------------- model

def parse_style(s):
    st = {}
    for part in (s or "").split(";"):
        if not part:
            continue
        k, _, v = part.partition("=")
        st[k.strip()] = v.strip() if _ else "1"
    return st


def load(path):
    root = ET.parse(path).getroot().find(".//root")
    cells = {}
    order = []
    for c in root.findall("mxCell"):
        geo = c.find("mxGeometry")
        cell = {
            "id": c.get("id"), "parent": c.get("parent"), "value": c.get("value") or "",
            "style": parse_style(c.get("style")), "raw_style": c.get("style") or "",
            "vertex": c.get("vertex") == "1", "edge": c.get("edge") == "1",
            "x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0, "points": [],
            "source": c.get("source"), "target": c.get("target"),
            "src_pt": None, "dst_pt": None, "offset": (0.0, 0.0),
        }
        if geo is not None:
            for k in ("x", "y", "width", "height"):
                if geo.get(k) is not None:
                    cell[{"width": "w", "height": "h"}.get(k, k)] = float(geo.get(k))
            for pt in geo.findall("mxPoint"):
                p = (float(pt.get("x", 0)), float(pt.get("y", 0)))
                if pt.get("as") == "sourcePoint":
                    cell["src_pt"] = p
                elif pt.get("as") == "targetPoint":
                    cell["dst_pt"] = p
                elif pt.get("as") == "offset":
                    cell["offset"] = p              # the label's perpendicular kick
            arr = geo.find("Array")
            if arr is not None:
                cell["points"] = [(float(p.get("x", 0)), float(p.get("y", 0)))
                                  for p in arr.findall("mxPoint")]
        cells[cell["id"]] = cell
        order.append(cell["id"])

    def origin(cid):
        c = cells.get(cid)
        if c is None or not c["vertex"]:
            return (0.0, 0.0)
        ox, oy = origin(c["parent"])
        return (ox + c["x"], oy + c["y"])

    for cid in order:
        c = cells[cid]
        ox, oy = origin(c["parent"])
        c["ax"], c["ay"] = ox + c["x"], oy + c["y"]
        c["origin"] = (ox, oy)
    return [cells[i] for i in order], cells


# ---------------------------------------------------------------- text

def text_width(s, size):
    """The text-width metric, read from theme data — never a second copy of it.

    A preview that measures text differently from the generator reports "no difference"
    for a sizing fix that works, and hides one that does not. The table lives in
    `themes/default.json` (`classic` inherits it, pinning the same family), so reading the
    default theme is reading the metric every shipped theme is sized by.
    """
    return layout.text_width(s, THEME, size)


def wrap(text, size, max_w):
    return layout.wrap_lines(text, max_w, THEME, size)


def draw_text(sv, cell, cx, cy, box_w, align="center", bold=False, color="#000000", size=None):
    txt = html.unescape(cell["value"] if isinstance(cell, dict) else cell)
    if not txt:
        return
    st = cell["style"] if isinstance(cell, dict) else {}
    size = size or float(st.get("fontSize", 12))
    bold = bold or st.get("fontStyle") in ("1", "3")
    lines = wrap(txt, size, box_w - 12)
    total = len(lines) * (size + 3)
    y = cy - total / 2 + size
    anchor = {"center": "middle", "left": "start"}[align]
    weight = ' font-weight="bold"' if bold else ""
    for ln in lines:
        sv.append(f'<text x="{cx:.1f}" y="{y:.1f}" font-family="Helvetica,Arial,sans-serif" '
                  f'font-size="{size:.0f}" fill="{color}" text-anchor="{anchor}"{weight}'
                  f'>{html.escape(ln)}</text>')
        y += size + 3


# ---------------------------------------------------------------- shapes

def shape_svg(sv, c):
    st = c["style"]
    x, y, w, h = c["ax"], c["ay"], c["w"], c["h"]
    fill = st.get("fillColor", "#ffffff")
    stroke = st.get("strokeColor", "#000000")
    dash = ' stroke-dasharray="6 4"' if st.get("dashed") == "1" else ""
    # the emitted strokeWidth, not a width of preview's own: a preview that draws every
    # outline at 1.4 reports "no difference" for a line-weight change that landed
    sw = st.get("strokeWidth", "1.4")
    common = f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dash}'
    shape = st.get("shape")

    if "swimlane" in st:
        band = float(st.get("startSize", 40))
        sv.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" {common}/>')
        sv.append(f'<line x1="{x + band}" y1="{y}" x2="{x + band}" y2="{y + h}" stroke="{stroke}" stroke-width="{sw}"/>')
        # The title is rotated, so it runs along the lane's *height* inside a band
        # `startSize` wide — which makes the band the title's line budget (see
        # layout.lane_height), and `whiteSpace=wrap` on the lane style is what makes
        # draw.io honour it. Drawing it on one line here would hide exactly the clipping
        # lane_height's title term exists to prevent.
        size = float(st.get("fontSize", 12))
        lines = wrap(html.unescape(c["value"]), size, h - 2 * 8) if st.get("whiteSpace") == "wrap" \
            else [html.unescape(c["value"])]
        span = len(lines) * (size + 3)
        sv.append(f'<g transform="translate({x + band / 2},{y + h / 2}) rotate(-90)">')
        for i, ln in enumerate(lines):
            dy = (i - (len(lines) - 1) / 2) * (size + 3) + size / 3
            sv.append(f'<text x="0" y="{dy:.1f}" font-family="Helvetica,Arial,sans-serif" '
                      f'font-size="{size:.0f}" font-weight="bold" text-anchor="middle"'
                      f'>{html.escape(ln)}</text>')
        sv.append("</g>")
        if span > band:                             # the band cannot hold the lines it needs
            print(f"  preview: lane title {c['value']!r} needs {span:.0f} px of band, has {band:.0f}",
                  file=sys.stderr)
        return
    if "ellipse" in st:
        sv.append(f'<ellipse cx="{x + w / 2}" cy="{y + h / 2}" rx="{w / 2}" ry="{h / 2}" {common}/>')
    elif "rhombus" in st:
        sv.append(f'<polygon points="{x + w / 2},{y} {x + w},{y + h / 2} {x + w / 2},{y + h} {x},{y + h / 2}" {common}/>')
    elif shape == "process":
        inset = w * 0.1
        sv.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" {common}/>')
        for dx in (inset, w - inset):
            sv.append(f'<line x1="{x + dx}" y1="{y}" x2="{x + dx}" y2="{y + h}" stroke="{stroke}" stroke-width="{sw}"/>')
    elif shape == "document":
        k = h * 0.2
        sv.append(f'<path d="M {x} {y} L {x + w} {y} L {x + w} {y + h - k} '
                  f'C {x + w * 0.75} {y + h - k * 2.2} {x + w * 0.25} {y + h + k * 1.2} {x} {y + h - k} Z" {common}/>')
    elif shape == "note":
        k = min(w, h) * 0.22
        sv.append(f'<path d="M {x} {y} L {x + w - k} {y} L {x + w} {y + k} L {x + w} {y + h} L {x} {y + h} Z" {common}/>')
        sv.append(f'<path d="M {x + w - k} {y} L {x + w - k} {y + k} L {x + w} {y + k}" fill="none" stroke="{stroke}"/>')
    else:
        rx = 10 if st.get("rounded") == "1" else 0
        sv.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" {common}/>')

    align = "left" if st.get("align") == "left" else "center"
    cx = x + float(st.get("spacingLeft", 0)) if align == "left" else x + w / 2
    draw_text(sv, c, cx, y + h / 2, w, align=align)


# ---------------------------------------------------------------- edges

def port(cell, px, py):
    return (cell["ax"] + cell["w"] * px, cell["ay"] + cell["h"] * py)


def direction(px, py):
    """Outward normal at a port — the axis the router leaves or approaches on.

    Ports that sit exactly on a bounding-box face keep their original precedence.
    A port projected onto a rhombus or ellipse outline has a fractional
    px *and* py, and used to fall through to (1, 0): for every such port on a
    shape's left half that normal points *into* the body, so the jetty stub and the
    arrowhead were drawn inside the node and the approach came out diagonal. The
    emitted file was right and only this renderer disagreed with it. Off a face,
    take the dominant offset from the centre instead."""
    if py == 0:
        return (0, -1)
    if py == 1:
        return (0, 1)
    if px == 0:
        return (-1, 0)
    if px == 1:
        return (1, 0)
    dx, dy = px - 0.5, py - 0.5
    if abs(dx) >= abs(dy):
        return (1, 0) if dx > 0 else (-1, 0)
    return (0, 1) if dy > 0 else (0, -1)


def floating(src, dst):
    sx, sy = src["ax"] + src["w"] / 2, src["ay"] + src["h"] / 2
    dx, dy = dst["ax"] + dst["w"] / 2, dst["ay"] + dst["h"] / 2
    if abs(dx - sx) >= abs(dy - sy):
        return (1.0, 0.5) if dx >= sx else (0.0, 0.5)
    return (0.5, 1.0) if dy >= sy else (0.5, 0.0)


def route(p_exit, d_exit, p_entry, d_entry, waypoints):
    """Orthogonal path. Explicit waypoints are honoured; otherwise approximate
    draw.io's router with a single mid-corridor jog."""
    pts = [p_exit]
    p1 = (p_exit[0] + d_exit[0] * JETTY, p_exit[1] + d_exit[1] * JETTY)
    p2 = (p_entry[0] + d_entry[0] * JETTY, p_entry[1] + d_entry[1] * JETTY)
    pts.append(p1)
    if waypoints:
        cur = p1
        for wp in waypoints:
            if abs(wp[0] - cur[0]) > 0.5 and abs(wp[1] - cur[1]) > 0.5:
                pts.append((wp[0], cur[1]) if abs(d_exit[0]) or len(pts) > 2 else (cur[0], wp[1]))
            pts.append(wp)
            cur = wp
        if abs(cur[0] - p2[0]) > 0.5 and abs(cur[1] - p2[1]) > 0.5:
            pts.append((p2[0], cur[1]) if abs(d_entry[1]) else (cur[0], p2[1]))
    elif abs(p1[0] - p2[0]) > 0.5 and abs(p1[1] - p2[1]) > 0.5:
        if d_exit[0] and d_entry[0]:
            mid = (p1[0] + p2[0]) / 2
            pts += [(mid, p1[1]), (mid, p2[1])]
        elif d_exit[1] and d_entry[1]:
            mid = (p1[1] + p2[1]) / 2
            pts += [(p1[0], mid), (p2[0], mid)]
        elif d_exit[0]:
            pts.append((p2[0], p1[1]))
        else:
            pts.append((p1[0], p2[1]))
    pts += [p2, p_entry]
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > 0.4 or abs(p[1] - out[-1][1]) > 0.4:
            out.append(p)
    return out


def path_d(pts):
    d = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        r = min(CORNER, abs(b[0] - a[0]) / 2 + abs(b[1] - a[1]) / 2, abs(c[0] - b[0]) / 2 + abs(c[1] - b[1]) / 2)
        ax = b[0] - (r if b[0] > a[0] else -r if b[0] < a[0] else 0)
        ay = b[1] - (r if b[1] > a[1] else -r if b[1] < a[1] else 0)
        cx = b[0] + (r if c[0] > b[0] else -r if c[0] < b[0] else 0)
        cy = b[1] + (r if c[1] > b[1] else -r if c[1] < b[1] else 0)
        d.append(f"L {ax:.1f} {ay:.1f} Q {b[0]:.1f} {b[1]:.1f} {cx:.1f} {cy:.1f}")
    d.append(f"L {pts[-1][0]:.1f} {pts[-1][1]:.1f}")
    return " ".join(d)


def label_point(pts, rel=0.0):
    """Where draw.io prints an edge's value. `rel` is the edge geometry's x: -1 at the
    source, 0 at the midpoint, 1 at the target. Without it this renderer always drew the
    midpoint and could not show a label the generator had deliberately moved."""
    segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in segs)
    target = total * (max(-1.0, min(1.0, rel)) + 1) / 2
    walk = 0.0
    for a, b in segs:
        ln = abs(b[0] - a[0]) + abs(b[1] - a[1])
        if walk + ln >= target and ln:
            t = (target - walk) / ln
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        walk += ln
    return pts[len(pts) // 2]


def edge_svg(sv, c, cells):
    st = c["style"]
    stroke = st.get("strokeColor", "#000000")
    dash = ' stroke-dasharray="6 4"' if st.get("dashed") == "1" else ""
    src, dst = cells.get(c["source"] or ""), cells.get(c["target"] or "")

    if src is None or dst is None:              # legend line samples
        ox, oy = c["origin"]
        p_exit = (c["src_pt"][0] + ox, c["src_pt"][1] + oy)
        p_entry = (c["dst_pt"][0] + ox, c["dst_pt"][1] + oy)
        pts = [p_exit, p_entry]
    else:
        ex, ey = (float(st["exitX"]), float(st["exitY"])) if "exitX" in st else floating(src, dst)
        ax, ay = (float(st["entryX"]), float(st["entryY"])) if "entryX" in st else floating(dst, src)
        pts = route(port(src, ex, ey), direction(ex, ey), port(dst, ax, ay), direction(ax, ay), c["points"])

    sv.append(f'<path d="{path_d(pts)}" fill="none" stroke="{stroke}" '
              f'stroke-width="{st.get("strokeWidth", "1.6")}"{dash}/>')
    a, b = pts[-2], pts[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = (dx * dx + dy * dy) ** 0.5 or 1
    ux, uy = dx / ln, dy / ln
    sv.append(f'<polygon points="{b[0]:.1f},{b[1]:.1f} '
              f'{b[0] - 9 * ux + 4 * uy:.1f},{b[1] - 9 * uy - 4 * ux:.1f} '
              f'{b[0] - 9 * ux - 4 * uy:.1f},{b[1] - 9 * uy + 4 * ux:.1f}" fill="{stroke}"/>')
    if c["value"]:
        mx, my = label_point(pts, c["x"])
        mx, my = mx + c["offset"][0], my + c["offset"][1]
        label = html.escape(html.unescape(c["value"]))
        size = float(st.get("fontSize", 11))
        w = text_width(label, size) + 8
        sv.append(f'<rect x="{mx - w / 2:.1f}" y="{my - size / 2 - 3:.1f}" width="{w:.1f}" '
                  f'height="{size + 6:.1f}" fill="#ffffff" fill-opacity="0.92"/>')
        sv.append(f'<text x="{mx:.1f}" y="{my + size / 3:.1f}" font-family="Helvetica,Arial,sans-serif" '
                  f'font-size="{size:.0f}" text-anchor="middle">{label}</text>')


# ---------------------------------------------------------------- driver

def render_svg(path):
    cells, by_id = load(path)
    vertices = [c for c in cells if c["vertex"]]
    w = max((c["ax"] + c["w"] for c in vertices), default=800) + 20
    h = max((c["ay"] + c["h"] for c in vertices), default=600) + 20
    sv = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
          f'viewBox="0 0 {w:.0f} {h:.0f}"><rect width="100%" height="100%" fill="#ffffff"/>']
    for c in cells:
        if c["vertex"]:
            shape_svg(sv, c)
    for c in cells:
        if c["edge"]:
            edge_svg(sv, c, by_id)
    # canvas frame: if all four edges are visible, the screenshot is not truncated
    sv.append(f'<rect x="1" y="1" width="{w - 2:.0f}" height="{h - 2:.0f}" fill="none" '
              f'stroke="#ff00ff" stroke-width="2" stroke-dasharray="10 6"/>')
    sv.append("</svg>")
    return "\n".join(sv), int(w), int(h)


def to_png(svg, out, w, h, scale=1.0):
    chrome = next((c for c in CHROMIUM_CANDIDATES if Path(c).exists() or shutil.which(c)), None)
    if not chrome:
        print("no chromium found; wrote SVG only", file=sys.stderr)
        return False
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "page.html"
        page.write_text(f'<body style="margin:0;background:#fff">{svg}</body>', "utf-8")
        # headless chromium clips the last ~15% when the window is exactly the content
        # height; pad the viewport so the whole canvas (incl. its magenta frame) lands.
        cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
               f"--force-device-scale-factor={scale}", f"--window-size={w + 20},{h + 160}",
               f"--screenshot={out}", f"--user-data-dir={tmp}/profile", page.as_uri()]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if not Path(out).exists():
            print(r.stderr[-2000:], file=sys.stderr)
            return False
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description="render a .drawio file to SVG/PNG for visual checks")
    p.add_argument("drawio")
    p.add_argument("-o", "--out", required=True, help="output .png (an .svg is written alongside)")
    p.add_argument("--scale", type=float, default=1.0)
    p.add_argument("--no-png", action="store_true")
    a = p.parse_args(argv)

    svg, w, h = render_svg(a.drawio)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    svg_path = out.with_suffix(".svg")
    svg_path.write_text(svg, "utf-8")
    print(svg_path)
    if not a.no_png and out.suffix == ".png":
        if to_png(svg, out.resolve(), w, h, a.scale):
            print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
