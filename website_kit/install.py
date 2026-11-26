"""Install and migrate hooks. Both are idempotent and need no Company, no user and no network."""

import frappe

from . import apply as kit_apply
from .theme import presets, tokens

SETTINGS = kit_apply.SETTINGS


def after_install() -> dict:
	"""Seed the defaults on the first install of a site, then apply; returns what changed (empty on a repeat).

	A site whose settings were applied before (`kit_version` is set) keeps its preset, overrides, brand name and search
	engine choice: a re-install never overwrites customer data.
	"""
	settings = frappe.get_doc(SETTINGS)
	if settings.kit_version:
		return kit_apply.apply(settings)
	settings.preset = presets.DEFAULT_PRESET
	settings.allow_search_engines = 0
	settings.save(ignore_permissions=True)  # on_update applies the settings
	return {"seeded": presets.DEFAULT_PRESET}


def after_migrate() -> None:
	"""Re-apply after a migrate so that a new kit release reaches the site's file. Stored tokens and CSS stay as they are."""
	try:
		kit_apply.apply()
	except tokens.TokenError:
		# Keep the previous good file; the settings page reports the bad value on the next save.
		frappe.log_error(title="Website Kit: the stored theme overrides are invalid, the previous file is kept")
