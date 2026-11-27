#!/usr/bin/env python3
"""Fail when the shipped content changed (the pinned hash differs from the base) but the version did not move forward.

    python scripts/check_version_bump.py origin/main     # in CI: the base of the pull request

Exit code 1 and one line of text on a problem; 0 otherwise (also when the base has no lock yet).
"""

import json
import subprocess
import sys
from pathlib import Path

LOCK = "website_kit/content_lock.json"
ROOT = Path(__file__).resolve().parent.parent


def version_tuple(text: str) -> tuple:
	return tuple(int(part) for part in text.split("."))


def problem(base: dict, head: dict) -> str | None:
	"""What is wrong with moving from the `base` lock to the `head` lock, or None."""
	if version_tuple(head["version"]) < version_tuple(base["version"]):
		return f"the version went back: {base['version']} -> {head['version']} (older)"
	if head["hash"] != base["hash"] and head["version"] == base["version"]:
		return f"the shipped content changed but the version is still {head['version']}: bump website_kit.__version__"
	return None


def main(ref: str) -> int:
	head = json.loads((ROOT / LOCK).read_text(encoding="utf-8"))
	shown = subprocess.run(["git", "show", f"{ref}:{LOCK}"], capture_output=True, text=True, cwd=ROOT)
	if shown.returncode != 0:
		print(f"no lock at {ref}: nothing to compare")
		return 0
	message = problem(json.loads(shown.stdout), head)
	if message:
		print(message)
		return 1
	print("version and content agree with", ref)
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "origin/main"))
