"""A release that changes what a site ships must change the version string (PR #7 changed the pages, templates and CSS and kept 0.3.0,
so the deployed sites could not be told from the old ones). The pinned hash fails the build until the lock and the version move
together; `scripts/check_version_bump.py` compares the lock with the base branch in CI, so the lock cannot be edited without a bump."""

import json
import subprocess
import sys
from pathlib import Path

from website_kit import __version__, contenthash

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "website_kit" / "content_lock.json"
sys.path.insert(0, str(ROOT / "scripts"))

import check_version_bump  # noqa: E402


def lock():
	return json.loads(LOCK.read_text(encoding="utf-8"))


def test_the_shipped_content_matches_the_pinned_hash():
	"""Fails when a page, component, template, stylesheet or guard script changed: run `python scripts/update_content_lock.py` and bump
	`__version__` in the same commit."""
	assert contenthash.shipped_hash() == lock()["hash"], (
		"shipped content changed: bump website_kit.__version__ and run scripts/update_content_lock.py"
	)


def test_the_lock_names_the_current_version():
	assert lock()["version"] == __version__


def test_the_hash_covers_every_kind_of_shipped_content():
	parts = contenthash.parts()
	assert any(name.startswith("Builder Page:wk-notfound") for name in parts)
	assert any(name.startswith("Builder Component:wk-header-uk") for name in parts)
	assert "file:website_kit/web_template/wk_navbar/wk_navbar.html" in parts
	assert "file:public/css/wk.css" in parts and "file:public/css/wk-shop.css" in parts
	assert "stockpage.guard" in parts


def test_the_hash_changes_with_the_content_and_ignores_line_endings(tmp_path):
	base = contenthash.shipped_hash()
	assert contenthash.shipped_hash(extra={"x": "y"}) != base
	assert contenthash.normalise(b"a\r\nb\n") == contenthash.normalise(b"a\nb\n")


OLD = ["website_kit.patches.v0_3.use_stock_website_theme"]
NEW = [*OLD, "website_kit.patches.v0_3.refresh_content_0_3_1"]


def test_the_bump_rule():
	same = {"version": "0.3.1", "hash": "aa"}
	assert check_version_bump.problem(same, same, OLD, OLD) is None
	moved = {"version": "0.3.1", "hash": "bb"}
	assert check_version_bump.problem({"version": "0.3.0", "hash": "aa"}, moved, OLD, NEW) is None
	assert "bump" in check_version_bump.problem({"version": "0.3.1", "hash": "aa"}, moved, OLD, NEW)
	assert "older" in check_version_bump.problem(
		{"version": "0.3.1", "hash": "aa"}, {"version": "0.3.0", "hash": "bb"}, OLD, NEW
	)
	# a version bump without a content change is allowed (a release can be only a bump)
	assert (
		check_version_bump.problem({"version": "0.3.0", "hash": "aa"}, {"version": "0.3.1", "hash": "aa"}, OLD, OLD)
		is None
	)


def test_changed_content_needs_a_new_patch_so_that_press_runs_migrate():
	"""Press runs `bench migrate` for a site update only when patches.txt, hooks.py, fixtures or DocType files changed; a release of only
	pages, templates and CSS is a plain "Pull" and nothing syncs (kitdemo stayed on the old pages after PR #7)."""
	base, head = {"version": "0.3.0", "hash": "aa"}, {"version": "0.3.1", "hash": "bb"}
	message = check_version_bump.problem(base, head, OLD, OLD)
	assert message and "patches.txt" in message and "migrate" in message
	assert check_version_bump.problem(base, head, OLD, NEW) is None
	assert check_version_bump.new_patches(OLD, NEW) == ["website_kit.patches.v0_3.refresh_content_0_3_1"]
	assert check_version_bump.patch_lines("# c\n[pre_model_sync]\n\n[post_model_sync]\na.b  # x\n") == ["a.b"]


def test_the_release_patch_is_listed_and_syncs_the_content():
	listed = check_version_bump.patch_lines((ROOT / "website_kit" / "patches.txt").read_text(encoding="utf-8"))
	assert "website_kit.patches.v0_3.refresh_content_0_3_1" in listed
	source = (ROOT / "website_kit" / "patches" / "v0_3" / "refresh_content_0_3_1.py").read_text(encoding="utf-8")
	assert "after_migrate" in source or ("apply" in source and "write_pages" in source)


def test_the_script_runs_against_a_git_ref():
	result = subprocess.run(
		[sys.executable, str(ROOT / "scripts" / "check_version_bump.py"), "HEAD"],
		capture_output=True,
		text=True,
		cwd=ROOT,
	)
	assert result.returncode in (0, 1), result.stderr
