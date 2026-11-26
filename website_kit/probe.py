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
		"pages": {
			row.name: [str(row.modified), row.route, row.published]
			for row in frappe.get_all(
				"Builder Page", fields=["name", "modified", "route", "published"], order_by="name"
			)
		}
		if frappe.db.exists("DocType", "Builder Page")
		else {},
		"pages_state": settings.pages_state,
		"pages_note": settings.pages_note,
		"contact_us": {
			field: frappe.db.get_single_value("Contact Us Settings", field)
			for field in ("forward_to_email", "is_disabled", "send_acknowledgement_email")
		},
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
	# an edit of a standard page, which a migrate must keep
	frappe.db.set_value("Builder Page", "wk-about-uk", "page_title", "CI own title")
	frappe.db.commit()


def assert_customized() -> None:
	settings = frappe.get_doc(SETTINGS)
	assert (settings.preset, settings.brand_name) == ("market", "CI Brand"), "customer data was overwritten"
	assert "#112233" in settings.token_overrides, "token overrides were overwritten"
	assert frappe.db.get_value("Builder Page", "wk-about-uk", "page_title") == "CI own title", (
		"a page edit was overwritten"
	)
	print("customer data kept")


def contact_demo() -> None:
	"""CI only: a recipient and syntactically valid, fake reCAPTCHA keys, so that the Contact page renders its form."""
	settings = frappe.get_doc(SETTINGS)
	settings.contact_email = "ci@example.com"
	settings.recaptcha_site_key = "6Lc" + "a" * 37
	settings.recaptcha_secret = "s" * 40
	settings.save(ignore_permissions=True)
	frappe.db.commit()


def contact_demo_off() -> None:
	settings = frappe.get_doc(SETTINGS)
	settings.contact_email = ""
	settings.recaptcha_site_key = ""
	settings.recaptcha_secret = ""
	settings.save(ignore_permissions=True)
	frappe.db.commit()
