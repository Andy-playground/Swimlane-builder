#!/usr/bin/env python3
"""Zero-install launcher: python3 swimlane-builder.py generate examples/po-confirmation.spec.json"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from swimlane_builder.cli import main  # noqa: E402

sys.exit(main())
