#!/usr/bin/env python3
"""Dev-only: render the 30-second overview film to docs/media/.

The film is tools/showreel/film.html, a page whose picture is a pure function of time.
This script fills it with the layout the generator computes for the PO-confirmation
example, then steps a headless Chromium through it frame by frame and encodes the
frames with ffmpeg, together with the soundtrack that music.py synthesizes. Needs Node
with Playwright, Chromium, ffmpeg, numpy, Pillow (for --hero) and the Inter font; none of this is part of the
runtime.

    python3 tools/showreel/render.py                    # → docs/media/swimlane-builder-showreel.mp4
    python3 tools/showreel/render.py --hero             # → docs/media/hero.webp, the README's loop
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
HERO = (25, 9.7, 18.1)      # fps, from, to: the layout scene, from black to the finished diagram


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


def hero(cmd, frames_dir):
    """The README's loop: the layout scene, fading to black at the end so it restarts cleanly."""
    from PIL import Image  # dev-only, and only this mode needs it
    fps, start, end = HERO
    rc = subprocess.run(cmd + ["--hero", str(frames_dir), str(fps), str(start), str(end)]).returncode
    if rc:
        return rc
    frames = [Image.open(f).convert("RGB") for f in sorted(frames_dir.glob("*.png"))]
    size = (960, round(960 * frames[0].height / frames[0].width))
    black, fade = Image.new("RGB", size), round(0.5 * fps)
    out = []
    for i, im in enumerate(frames):
        im = im.resize(size, Image.LANCZOS)
        left = len(frames) - 1 - i
        out.append(Image.blend(black, im, left / fade) if left < fade else im)
    target = ROOT / "docs" / "media" / "hero.webp"
    out[0].save(target, save_all=True, append_images=out[1:], duration=round(1000 / fps), loop=0,
                quality=88, method=6)
    print(target)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="render the overview film")
    p.add_argument("-o", "--out", default=str(ROOT / "docs" / "media" / "swimlane-builder-showreel.mp4"))
    p.add_argument("--hero", action="store_true", help="write the README's looping animation instead of the video")
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
        elif a.hero:
            return hero(cmd, Path(tmp) / "hero")
        else:
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            track = Path(tmp) / "soundtrack.wav"
            subprocess.run([sys.executable, str(HERE / "music.py"), str(track)], check=True,
                           stdout=subprocess.DEVNULL)
            cmd += ["--video", a.out, str(FPS), str(track)]
        return subprocess.run(cmd).returncode


if __name__ == "__main__":
    raise SystemExit(main())
