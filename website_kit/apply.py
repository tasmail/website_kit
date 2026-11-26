"""`apply()`: make a site match its Website Kit Settings, idempotently.

It compiles the theme CSS, writes it as one public File with a stable name, sets the Website Theme, the Navbar and Footer
templates and the robots text where the customer has not chosen otherwise, and records what was applied. It writes nothing
when nothing differs (a save of Website Settings clears the page cache) and returns what it changed, so a second run
returns an empty dict.
"""

import hashlib
import os

import frappe

from . import WK_THEME_API, __version__, settings_sync
from .theme import compiler

SETTINGS = "Website Kit Settings"
THEME_FILE = "wk-theme.css"


def apply(settings=None) -> dict:
	"""Apply the settings (the saved Single by default); returns a dict of the changes made, empty if none."""
	settings = settings or frappe.get_doc(SETTINGS)
	css, digest = compiler.build(settings.preset, settings.token_overrides)
	changes = {}
	url, file_change = write_theme_file(css)
	if file_change:
		changes["theme_file"] = file_change
	recorded = {"theme_hash": digest, "theme_file_url": url, "kit_version": f"{__version__}+api{WK_THEME_API}"}
	changes.update(record(settings, recorded))
	changes.update(sync_website_settings(bool(settings.allow_search_engines)))
	return changes


def write_theme_file(css: str) -> tuple[str, str | None]:
	"""Write the CSS as the public File `wk-theme.css`; returns `(file_url, change)` with change None when equal."""
	rows = frappe.get_all(
		"File", filters={"file_name": THEME_FILE, "is_private": 0}, fields=["name"], order_by="creation asc", limit=1
	)
	if not rows:
		_remove_orphan_file()
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
	doc = frappe.get_doc("File", rows[0].name)
	if _digest(_on_disk(doc)) == _digest(css):
		return doc.file_url, None
	doc.save_file(content=css, overwrite=True)
	doc.save(ignore_permissions=True)
	return doc.file_url, "updated"


def _remove_orphan_file() -> None:
	"""Delete a leftover `wk-theme.css` on disk that has no File record (for example after an uninstall), because Frappe
	would otherwise save the new file under a suffixed name and the stable name would be lost."""
	path = frappe.get_site_path("public", "files", THEME_FILE)
	if os.path.isfile(path):
		os.remove(path)


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
