"""Theme loading: style strings and geometry constants are data, not code."""
import json
from pathlib import Path

THEME_DIR = Path(__file__).resolve().parents[2] / "themes"


def load(name="default"):
    theme = json.loads((THEME_DIR / "default.json").read_text("utf-8"))
    if name != "default":
        override = json.loads((THEME_DIR / f"{name}.json").read_text("utf-8"))
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(theme.get(k), dict):
                theme[k] = {**theme[k], **v}
            else:
                theme[k] = v
    return theme
