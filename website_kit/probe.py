"""State probe for the idempotence check of CI (`bench execute website_kit.probe.state`).

It prints one JSON line with everything a second install or migrate must leave unchanged.
"""

import json

import frappe

from .apply import SETTINGS, THEME_FILE


def state() -> None:
	files = frappe.get_all(
		"File",
		filters={"file_name": ["like", "wk-theme%"]},
		fields=["name", "file_name", "file_url", "content_hash", "modified"],
	)
	settings = frappe.get_doc(SETTINGS)
	website_settings = frappe.get_doc("Website Settings")
	data = {
		"files": [{**row, "modified": str(row.modified)} for row in files],
		"settings_modified": str(settings.modified),
		"settings": {
			field: settings.get(field)
			for field in (
				"preset",
				"brand_name",
				"allow_search_engines",
				"token_overrides",
				"kit_version",
				"theme_hash",
			)
		},
		"website_settings_modified": str(website_settings.modified),
		"website_settings": {
			field: website_settings.get(field)
			for field in ("website_theme", "navbar_template", "footer_template", "robots_txt")
		},
		"theme_file_count": len([row for row in files if row.file_name == THEME_FILE]),
	}
	print(json.dumps(data, sort_keys=True))


def reapply() -> None:
	"""Run the install hook and `apply` again; print what they changed (must be `{}` and `{}`)."""
	from .apply import apply
	from .install import after_install

	print(json.dumps({"after_install": after_install(), "apply": apply()}, sort_keys=True))
