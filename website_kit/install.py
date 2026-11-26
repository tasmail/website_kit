"""Install and migrate hooks. Both are idempotent and need no Company, no user and no network."""

import frappe

from . import apply as kit_apply
from .pages import sync as pages_sync
from .theme import presets

SETTINGS = kit_apply.SETTINGS


def after_install() -> dict:
	"""Seed the defaults on the first install of a site, then apply; returns what changed (empty on a repeat).

	A site whose settings were applied before (`kit_version` is set) keeps its preset, overrides, brand name and search
	engine choice: a re-install never overwrites customer data. A failure of the theme step is logged, never raised: the
	app stays installed and the next migrate or save applies the theme again.
	"""
	try:
		settings = frappe.get_doc(SETTINGS)
		if settings.kit_version:
			changes = kit_apply.apply(settings)
		else:
			settings.preset = presets.DEFAULT_PRESET
			settings.allow_search_engines = 0
			settings.save(ignore_permissions=True)  # on_update applies the settings
			changes = {"seeded": presets.DEFAULT_PRESET}
	except Exception:
		frappe.log_error(title="Website Kit: the theme could not be applied at install")
		return {"error": "apply failed, see the Error Log"}
	return {**changes, **write_pages()}


def write_pages() -> dict:
	"""Write the standard pages (needs Builder; a failure is logged and never stops the install, migrate or app install)."""
	try:
		return pages_sync.sync()
	except Exception:
		frappe.log_error(title="Website Kit: the standard pages could not be written")
		return {"pages": "failed, see the Error Log"}


def after_app_install(app_name=None) -> None:
	"""Hook `after_app_install`: Builder installed after the kit brings the pages in."""
	if app_name == "builder":
		write_pages()


def after_migrate() -> None:
	"""Re-apply after a migrate so that a new kit release reaches the site's file. Stored tokens and CSS stay as they are.

	A failure (bad stored overrides, a busy lock, a disk error) is logged and never aborts `bench migrate`; the previous
	good file stays in place.
	"""
	try:
		kit_apply.apply()
	except Exception:
		frappe.log_error(title="Website Kit: the theme could not be applied after migrate, the previous file is kept")
	write_pages()
