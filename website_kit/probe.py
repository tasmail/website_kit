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


def customize() -> None:
	"""Set customer data (preset, brand, overrides) the way a customer would, to prove that migrate keeps it."""
	settings = frappe.get_doc(SETTINGS)
	settings.preset = "market"
	settings.brand_name = "CI Brand"
	settings.token_overrides = '{"tokens": {"color-primary": "#112233"}}'
	settings.save(ignore_permissions=True)
	frappe.db.commit()


def assert_customized() -> None:
	settings = frappe.get_doc(SETTINGS)
	assert (settings.preset, settings.brand_name) == ("market", "CI Brand"), "customer data was overwritten"
	assert "#112233" in settings.token_overrides, "token overrides were overwritten"
	print("customer data kept")


def complete_setup() -> None:
	"""CI only: run the setup wizard on a site that has ERPNext, so that a Company exists for the shop tests."""
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	setup_complete(
		{
			"language": "en",
			"country": "Ukraine",
			"timezone": "Europe/Kiev",
			"currency": "UAH",
			"company_name": "CI Company",
			"company_abbr": "CI",
			"chart_of_accounts": "Standard",
			"fy_start_date": "2026-01-01",
			"fy_end_date": "2026-12-31",
			"full_name": "CI Admin",
			"email": "ci-admin@example.com",
			"password": "ci-admin-pass-12345",
			"domains": [],
		}
	)
	frappe.db.commit()
	print("setup complete")
