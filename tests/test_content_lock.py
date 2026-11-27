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


def test_the_bump_rule():
	same = {"version": "0.3.1", "hash": "aa"}
	assert check_version_bump.problem(same, same) is None
	assert check_version_bump.problem({"version": "0.3.0", "hash": "aa"}, {"version": "0.3.1", "hash": "bb"}) is None
	assert "bump" in check_version_bump.problem({"version": "0.3.0", "hash": "aa"}, {"version": "0.3.0", "hash": "bb"})
	assert "older" in check_version_bump.problem({"version": "0.3.1", "hash": "aa"}, {"version": "0.3.0", "hash": "bb"})
	# a version bump without a content change is allowed (a release can be only a bump)
	assert check_version_bump.problem({"version": "0.3.0", "hash": "aa"}, {"version": "0.3.1", "hash": "aa"}) is None


def test_the_script_runs_against_a_git_ref():
	result = subprocess.run(
		[sys.executable, str(ROOT / "scripts" / "check_version_bump.py"), "HEAD"],
		capture_output=True,
		text=True,
		cwd=ROOT,
	)
	assert result.returncode in (0, 1), result.stderr
