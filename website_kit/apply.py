"""`apply()`: make a site match its Website Kit Settings, idempotently.

It compiles the theme CSS, writes it as one public File with a stable name, sets the Website Theme, the Navbar and Footer
templates and the robots text where the customer has not chosen otherwise, and records what was applied. It writes nothing
when nothing differs (a save of Website Settings clears the page cache) and returns what it changed, so a second run
returns an empty dict.
"""

import hashlib
import os
import zlib
from contextlib import contextmanager

import frappe

from . import WK_THEME_API, __version__, settings_sync
from .theme import compiler

SETTINGS = "Website Kit Settings"
THEME_FILE = "wk-theme.css"


def apply(settings=None) -> dict:
	"""Apply the settings (the saved Single by default); returns a dict of the changes made, empty if none.

	Runs under a database lock, so two concurrent applies (a save and a migrate) never write the file at the same time.
	"""
	with apply_lock():
		settings = settings or frappe.get_doc(SETTINGS)
		css, digest = compiler.build(settings.preset, settings.token_overrides)
		changes = {}
		url, file_change = write_theme_file(css)
		if file_change:
			changes["theme_file"] = file_change
		recorded = {"theme_hash": digest, "theme_file_url": url, "kit_version": f"{__version__}+api{WK_THEME_API}"}
		changes.update(record(settings, recorded))
		changes.update(sync_website_settings(bool(settings.allow_search_engines)))
		if "theme_file" in changes or "theme_hash" in changes:
			# Cached pages still link the old ?v=<hash>.
			from frappe.website.utils import clear_website_cache

			clear_website_cache()
		return changes


@contextmanager
def apply_lock(timeout: int = 10):
	"""A per-site database lock (MariaDB GET_LOCK, PostgreSQL advisory lock) around `apply`."""
	name = f"wk_apply_{frappe.conf.db_name or frappe.local.site}"[:60]
	if frappe.db.db_type == "postgres":
		key = zlib.crc32(name.encode())
		frappe.db.sql("select pg_advisory_lock(%s)", (key,))
		release = ("select pg_advisory_unlock(%s)", (key,))
	else:
		if frappe.db.sql("SELECT GET_LOCK(%s, %s)", (name, timeout))[0][0] != 1:
			raise RuntimeError("Website Kit: another apply is running")
		release = ("SELECT RELEASE_LOCK(%s)", (name,))
	try:
		yield
	finally:
		frappe.db.sql(*release)


def lock_is_free() -> bool:
	"""True when no connection holds the apply lock (MariaDB only; used by the tests)."""
	name = f"wk_apply_{frappe.conf.db_name or frappe.local.site}"[:60]
	return frappe.db.sql("SELECT IS_FREE_LOCK(%s)", (name,))[0][0] == 1


def find_theme_file():
	"""The File record of the kit: attached to the settings, never a file that only has the same name."""
	rows = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": SETTINGS,
			"attached_to_name": SETTINGS,
			"is_private": 0,
			"file_name": ["like", "wk-theme%.css"],
		},
		fields=["name"],
		order_by="creation asc",
		limit=1,
	)
	return rows[0].name if rows else None


def write_theme_file(css: str) -> tuple[str, str | None]:
	"""Write the CSS as the public File of the kit; returns `(file_url, change)` with change None when equal.

	A new file is named `wk-theme.css`; if some other file already uses that name, Frappe picks a suffixed name for ours and
	the other file is left alone. An existing file is replaced atomically (temp file, then rename).
	"""
	name = find_theme_file()
	if not name:
		doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": THEME_FILE,
				"content": css,
				"is_private": 0,
				"attached_to_doctype": SETTINGS,
				"attached_to_name": SETTINGS,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.file_url, "created"
	doc = frappe.get_doc("File", name)
	if _digest(_on_disk(doc)) == _digest(css):
		return doc.file_url, None
	_replace_atomically(doc, css)
	return doc.file_url, "updated"


def _replace_atomically(doc, css: str) -> None:
	path = doc.get_full_path()
	data = css.encode("utf-8")
	temp = f"{path}.{os.getpid()}.tmp"
	with open(temp, "wb") as handle:
		handle.write(data)
		handle.flush()
		os.fsync(handle.fileno())
	os.replace(temp, path)
	doc.db_set({"content_hash": hashlib.md5(data, usedforsecurity=False).hexdigest(), "file_size": len(data)})


def _on_disk(doc) -> bytes:
	try:
		content = doc.get_content()
	except (OSError, frappe.DoesNotExistError):
		return b""
	return content.encode("utf-8") if isinstance(content, str) else (content or b"")


def _digest(content) -> str:
	return hashlib.sha256(content.encode("utf-8") if isinstance(content, str) else content).hexdigest()


def record(settings, values: dict) -> dict:
	"""Store the read-only status fields of the Single; only the ones that differ, so `modified` stays put."""
	changed = {}
	for field, value in values.items():
		if (settings.get(field) or "") != value:
			frappe.db.set_single_value(SETTINGS, field, value)
			settings.set(field, value)
			changed[field] = value
	if changed:
		frappe.clear_document_cache(SETTINGS, SETTINGS)
	return changed


def sync_website_settings(allow_search_engines: bool) -> dict:
	website_settings = frappe.get_doc("Website Settings")
	changes = settings_sync.website_settings_changes(
		{field: website_settings.get(field) for field in settings_sync.FIELDS}, allow_search_engines
	)
	if changes:
		website_settings.update(changes)
		website_settings.save(ignore_permissions=True)
	return {f"website_settings.{field}": "set" for field in changes}
