#!/usr/bin/env python3
"""Write `website_kit/content_lock.json` for the current content and version (run it after bumping `__version__`)."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from website_kit import __version__, contenthash  # noqa: E402

LOCK = ROOT / "website_kit" / "content_lock.json"
LOCK.write_text(
	json.dumps({"version": __version__, "hash": contenthash.shipped_hash()}, indent="\t") + "\n", encoding="utf-8"
)
print(f"{LOCK.name}: {__version__} {contenthash.shipped_hash()}")
