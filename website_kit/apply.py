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

from . import WK_THEME_API, __version__, contact, settings_sync
from .theme import compiler, editor

SETTINGS = "Website Kit Settings"
THEME_FILE = "wk-theme.css"  # public: tokens, then the validated Custom CSS
SAFE_FILE = "wk-safe.css"  # public, written only while Custom CSS exists: the tokens alone, for safe mode
DRAFT_FILE = "wk-draft.css"  # private: the draft, linked only for a Website Manager who asks for the preview


def custom_css_enabled() -> bool:
	"""The operator switch `website_kit_custom_css_enabled` of the site config (default on); no plan gating."""
	value = frappe.conf.get("website_kit_custom_css_enabled", 1)
	return str(value).strip().lower() not in ("0", "false", "no", "off", "")


def apply(settings=None, previous_email=None) -> dict:
	"""Apply the settings (the saved Single by default); returns a dict of the changes made, empty if none.

	Runs under a database lock, so two concurrent applies (a save and a migrate) never write the file at the same time.
	Custom CSS is validated again inside `compiler.build`. If the stored CSS no longer passes (a stricter rule in a new
	release) the site fails closed: the file is rebuilt from the preset and the tokens without any Custom CSS, so the
	forbidden CSS stops being served. The stored text is never touched; `css_notes` says why it is not applied.
	"""
	with apply_lock():
		settings = settings or frappe.get_doc(SETTINGS)
		custom = (settings.custom_css or "") if custom_css_enabled() else ""
		notes = None
		try:
			css, digest = compiler.build(settings.preset, settings.token_overrides, custom, settings.custom_base)
		except compiler.CustomCssError as error:
			notes = rejection_notes(error.result)
			custom = ""
			css, digest = compiler.build(settings.preset, settings.token_overrides, "", settings.custom_base)
		changes = {}
		url, file_change = write_file(THEME_FILE, css)
		if file_change:
			changes["theme_file"] = file_change
		safe_url = ""
		if custom.strip():
			safe_css = compiler.build(settings.preset, settings.token_overrides, "", settings.custom_base)[0]
			safe_url, safe_change = write_file(SAFE_FILE, safe_css)
			if safe_change:
				changes["safe_file"] = safe_change
		elif remove_file(SAFE_FILE):
			changes["safe_file"] = "removed"
		recorded = {
			"theme_hash": digest,
			"theme_file_url": url,
			"safe_file_url": safe_url,
			"css_notes": notes if notes is not None else stale_notes(custom),
			"kit_version": f"{__version__}+api{WK_THEME_API}",
		}
		changes.update(record(settings, recorded))
		if "kit_version" in changes and discard_draft():
			changes["draft"] = "discarded"  # a draft written by an older release was checked by older rules
		changes.update(sync_website_settings(bool(settings.allow_search_engines)))
		changes.update(contact.sync_contact_settings(settings.contact_email, previous_email))
		if {"theme_file", "safe_file", "theme_hash"} & set(changes):
			# Cached pages still link the old ?v=<hash>.
			from frappe.website.utils import clear_website_cache

			clear_website_cache()
		return changes


def rejection_notes(result) -> str:
	"""Notes text for Custom CSS that the rules of a new release reject (shown on the settings page, English)."""
	lines = (f"{m.line}:{m.column}: {m.message}" for m in result.errors)
	return "\n".join(
		["Not applied: the rules of this release reject the stored Custom CSS (it is kept as it is):", *lines]
	)


def stale_notes(custom_css: str) -> str:
	"""The notes of the settings page about names in the Custom CSS that this kit version no longer knows."""
	return "\n".join(f"{m['line']}:{m['column']}: {m['message']}" for m in editor.stale_names(custom_css))


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


def find_theme_file(file_name: str = THEME_FILE, private: bool = False):
	"""The File record of the kit named `file_name`: attached to the settings, never a file that only has the same name."""
	stem = file_name.removesuffix(".css")
	rows = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": SETTINGS,
			"attached_to_name": SETTINGS,
			"is_private": 1 if private else 0,
			"file_name": ["like", f"{stem}%.css"],
		},
		fields=["name"],
		order_by="creation asc",
		limit=1,
	)
	return rows[0].name if rows else None


def write_file(file_name: str, css: str, private: bool = False) -> tuple[str, str | None]:
	"""Write the CSS as a File of the kit; returns `(file_url, change)` with change None when equal.

	A new file is named `file_name`; if some other file already uses that name, Frappe picks a suffixed name for ours and
	the other file is left alone. An existing file is replaced atomically (temp file, then rename).
	"""
	name = find_theme_file(file_name, private)
	if not name:
		doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name,
				"content": css,
				"is_private": 1 if private else 0,
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


def remove_file(file_name: str, private: bool = False) -> bool:
	"""Delete the kit's File of that name (record and file on disk); True when there was one."""
	name = find_theme_file(file_name, private)
	if not name:
		return False
	frappe.delete_doc("File", name, ignore_permissions=True, force=True)
	return True


def discard_draft() -> bool:
	"""Remove the draft file and forget the draft; True when there was one."""
	removed = remove_file(DRAFT_FILE, private=True)
	remembered = frappe.db.get_single_value(SETTINGS, "draft_file_url") or frappe.db.get_single_value(
		SETTINGS, "draft_state"
	)
	if remembered:
		frappe.db.set_single_value(SETTINGS, {"draft_state": "", "draft_file_url": ""})
		frappe.clear_document_cache(SETTINGS, SETTINGS)
	return bool(removed or remembered)


def write_draft(css: str) -> str:
	"""Write the draft CSS as a private File (only users who may read the settings can fetch it); returns its URL."""
	return write_file(DRAFT_FILE, css, private=True)[0]


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
