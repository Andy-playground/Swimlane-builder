#!/usr/bin/env python3
"""Dev-only: render the 30-second overview film to docs/media/.

The film is tools/showreel/film.html, a page whose picture is a pure function of time.
This script fills it with the layout the generator computes for the PO-confirmation
example, then steps a headless Chromium through it frame by frame and encodes the
frames with ffmpeg. Needs Node with Playwright, Chromium, ffmpeg and the Inter font;
none of this is part of the runtime.

    python3 tools/showreel/render.py                    # → docs/media/swimlane-builder-showreel.mp4
    python3 tools/showreel/render.py --stills 2 7 14    # PNG stills at those seconds, for review
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
from swimlane_builder import layout, themes  # noqa: E402  — dev tool, after the path fix-up

SPEC = ROOT / "examples" / "po-confirmation.spec.json"
FPS = 60


def film_data():
    theme = themes.load()
    lay = layout.compute(json.loads(SPEC.read_text("utf-8")), theme)
    g = theme["geometry"]
    for n in lay["nodes"]:
        # a terminal is a fixed circle, so its label wraps to the circle, not to a box
        usable = n["w"] - 2 * g["PAD_TEXT_X"]
        n["lines"] = layout.wrap_lines(n["label"], usable, theme)
    keep = ("canvas_w", "canvas_h", "lanes", "nodes", "edges")
    return {k: lay[k] for k in keep}


def main(argv=None):
    p = argparse.ArgumentParser(description="render the overview film")
    p.add_argument("-o", "--out", default=str(ROOT / "docs" / "media" / "swimlane-builder-showreel.mp4"))
    p.add_argument("--stills", nargs="*", type=float, help="write PNG stills at these seconds instead of the video")
    p.add_argument("--stills-dir", default="shots")
    a = p.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "film.html"
        page.write_text((HERE / "film.html").read_text("utf-8")
                        .replace("/*DATA*/null", json.dumps(film_data())), "utf-8")
        cmd = ["node", str(HERE / "frames.js"), str(page)]
        if a.stills is not None:
            cmd += ["--stills", a.stills_dir, *map(str, a.stills)]
        else:
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            cmd += ["--video", a.out, str(FPS)]
        return subprocess.run(cmd).returncode


if __name__ == "__main__":
    raise SystemExit(main())
