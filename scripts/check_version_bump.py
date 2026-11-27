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
PATCHES = "website_kit/patches.txt"
ROOT = Path(__file__).resolve().parent.parent


def version_tuple(text: str) -> tuple:
	return tuple(int(part) for part in text.split("."))


def patch_lines(text: str) -> list[str]:
	"""The patch names of a patches.txt (no sections, comments or blank lines)."""
	lines = [line.split("#")[0].strip() for line in text.splitlines()]
	return [line for line in lines if line and not line.startswith("[")]


def new_patches(base: list[str], head: list[str]) -> list[str]:
	return [line for line in head if line not in base]


def problem(base: dict, head: dict, base_patches: list[str], head_patches: list[str]) -> str | None:
	"""What is wrong with moving from the `base` lock and patch list to the `head` ones, or None."""
	if version_tuple(head["version"]) < version_tuple(base["version"]):
		return f"the version went back: {base['version']} -> {head['version']} (older)"
	if head["hash"] == base["hash"]:
		return None
	if head["version"] == base["version"]:
		return f"the shipped content changed but the version is still {head['version']}: bump website_kit.__version__"
	if not new_patches(base_patches, head_patches):
		return (
			"the shipped content changed but patches.txt has no new patch line: Press runs `bench migrate` for a site update only when "
			"patches.txt, hooks.py, fixtures or DocType files changed, so without a patch the site is just moved and the new pages never "
			"sync. Add a patch for this release (see docs/releasing.md)"
		)
	return None


def show(ref: str, path: str) -> str | None:
	shown = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True, cwd=ROOT)
	return shown.stdout if shown.returncode == 0 else None


def main(ref: str) -> int:
	head = json.loads((ROOT / LOCK).read_text(encoding="utf-8"))
	base_lock = show(ref, LOCK)
	if base_lock is None:
		print(f"no lock at {ref}: nothing to compare")
		return 0
	message = problem(
		json.loads(base_lock),
		head,
		patch_lines(show(ref, PATCHES) or ""),
		patch_lines((ROOT / PATCHES).read_text(encoding="utf-8")),
	)
	if message:
		print(message)
		return 1
	print("version, patches and content agree with", ref)
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "origin/main"))
