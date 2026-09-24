"""draw.io XML emission. No geometry computed here; output is deterministic."""
from xml.sax.saxutils import escape

from . import __version__

# One version, one definition: the package version is the one every emitted file
# names, so the two cannot drift apart.
AGENT = f"swimlane-builder {__version__}"

LEGEND_LABELS = {"task": "Process", "decision": "Decision", "subprocess": "Subprocess",
                 "document": "Document", "offline": "Offline", "system": "System", "user": "User"}
LANE_STYLE = ("swimlane;horizontal=0;startSize={start_size};collapsible=0;html=1;rounded=1;"
              "whiteSpace=wrap;fontFamily=Helvetica;fillColor={fill};")


def _esc(s):
    return escape(s, {'"': "&quot;"})


def _num(v):
    """Port ratios are written with a fixed shape so the output stays byte-stable."""
    return f"{v:g}"


def _stroke_w(style):
    """The `strokeWidth` a style declares, or draw.io's default of 1.

    The legend's line samples are a *key* to the lines in the flow, so they are drawn at
    whatever width the edge style sets rather than at a width of their own — a key that
    disagrees with the thing it describes is worse than no key.
    """
    for part in style.split(";"):
        k, _, v = part.partition("=")
        if k == "strokeWidth":
            return v
    return "1"


def _ports(e):
    """Ports are geometry: layout.py picks the side and the fan-out offset."""
    (ex, ey), (nx, ny) = e["exit"], e["entry"]
    return (f"exitX={_num(ex)};exitY={_num(ey)};exitDx=0;exitDy=0;"
            f"entryX={_num(nx)};entryY={_num(ny)};entryDx=0;entryDy=0;")


def emit(spec, lay, theme):
    """Emit .drawio XML for a validated spec + computed layout. Identical inputs => identical bytes."""
    g = theme["geometry"]
    page_w, page_h = lay["page_w"], lay["page_h"]
    meta = spec["meta"]
    out = []
    a = out.append

    a(f'<mxfile host="app.diagrams.net" agent="{AGENT}">')
    a(f'  <diagram id="{_esc(meta["sop_id"])}" name="{_esc(meta["sop_id"])} Process Flow">')
    a(f'    <mxGraphModel dx="800" dy="600" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{page_w}" pageHeight="{page_h}" math="0" shadow="0">')
    a("      <root>")
    a('        <mxCell id="0"/>')
    a('        <mxCell id="1" parent="0"/>')

    a(f'        <mxCell id="title" value="{_esc(meta["sop_id"] + " – " + meta["title"])}" style="{theme["title_style"]}" vertex="1" parent="1">')
    a(f'          <mxGeometry x="0" y="0" width="{lay["canvas_w"]}" height="{lay["title_h"]}" as="geometry"/>')
    a("        </mxCell>")

    labels = {**LEGEND_LABELS, **theme.get("legend_labels", {})}
    leg = lay["legend"]
    a(f'        <mxCell id="legend" value="" style="{theme["legend_style"]}" vertex="1" parent="1">')
    a(f'          <mxGeometry x="0" y="{leg["y"]}" width="{lay["canvas_w"]}" height="{leg["h"]}" as="geometry"/>')
    a("        </mxCell>")
    for it in leg["items"]:
        if it["kind"] == "shape":
            a(f'        <mxCell id="legend_{it["key"]}" value="{_esc(labels[it["key"]])}" style="{theme["node_styles"][it["key"]]}fontSize=8;" vertex="1" parent="legend">')
            a(f'          <mxGeometry x="{it["x"] + 18}" y="17" width="64" height="36" as="geometry"/>')
            a("        </mxCell>")
        else:
            a(f'        <mxCell id="legend_line_{it["key"]}" value="{_esc(labels[it["key"]])}" style="html=1;fontSize=8;strokeWidth={_stroke_w(theme["edge_style"])};{theme["edge_channels"][it["key"]]}" edge="1" parent="legend">')
            a('          <mxGeometry relative="1" as="geometry">')
            a(f'            <mxPoint x="{it["x"] + 10}" y="45" as="sourcePoint"/>')
            a(f'            <mxPoint x="{it["x"] + 90}" y="45" as="targetPoint"/>')
            a("          </mxGeometry>")
            a("        </mxCell>")

    for i, lane in enumerate(lay["lanes"]):
        fill = theme["lane_fills"][i % len(theme["lane_fills"])]
        style = theme.get("lane_style", LANE_STYLE).format(start_size=g["LANE_TITLE_W"], fill=fill)
        a(f'        <mxCell id="lane_{lane["id"]}" value="{_esc(lane["label"])}" style="{style}" vertex="1" parent="1">')
        a(f'          <mxGeometry x="0" y="{lane["y"]}" width="{lane["w"]}" height="{lane["h"]}" as="geometry"/>')
        a("        </mxCell>")

    for n in lay["nodes"]:
        a(f'        <mxCell id="n_{n["id"]}" value="{_esc(n["label"])}" style="{theme["node_styles"][n["type"]]}" vertex="1" parent="lane_{n["lane"]}">')
        a(f'          <mxGeometry x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" as="geometry"/>')
        a("        </mxCell>")
        if "badge" in n:
            bx, by, bd = n["badge"]
            a(f'        <mxCell id="badge_{n["id"]}" value="{_esc(n["badge_text"])}" style="{theme["badge_style"]}" vertex="1" parent="lane_{n["lane"]}">')
            a(f'          <mxGeometry x="{bx}" y="{by}" width="{bd}" height="{bd}" as="geometry"/>')
            a("        </mxCell>")

    counts = {}
    for e in lay["edges"]:
        style = theme["edge_style"] + theme["edge_channels"][e["channel"]] + _ports(e)
        eid = f'e_{e["from"]}__{e["to"]}'
        counts[eid] = counts.get(eid, 0) + 1
        if counts[eid] > 1:
            eid = f"{eid}_{counts[eid]}"
        value = f' value="{_esc(e["label"])}"' if e["label"] else ""
        a(f'        <mxCell id="{eid}"{value} style="{style}" edge="1" parent="1" source="n_{e["from"]}" target="n_{e["to"]}">')
        # geometry x positions the label along the edge (-1 source .. 1 target); layout
        # decides it, this only writes it
        pos = f'x="{_num(e["label_pos"])}" ' if e["label_pos"] is not None else ""
        off = e.get("label_offset")
        if e["points"] or off:
            a(f'          <mxGeometry {pos}relative="1" as="geometry">')
            if e["points"]:
                a('            <Array as="points">')
                for px, py in e["points"]:
                    a(f'              <mxPoint x="{px}" y="{py}"/>')
                a("            </Array>")
            if off:
                a(f'            <mxPoint x="{off[0]}" y="{off[1]}" as="offset"/>')
            a("          </mxGeometry>")
        else:
            a(f'          <mxGeometry {pos}relative="1" as="geometry"/>')
        a("        </mxCell>")

    a("      </root>")
    a("    </mxGraphModel>")
    a("  </diagram>")
    a("</mxfile>")
    return "\n".join(out) + "\n"
