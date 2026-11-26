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


def http_cache_check() -> None:
	"""CI and local check, over real WSGI requests with the website page cache on: a manager's `?wk_safe=1` page is never served
	from the cache, a guest never receives it, and the cookie keeps safe mode for the manager only.

	It needs `developer_mode` off (else Frappe disables the cache) and the Administrator password `admin`.
	"""
	import re

	from frappe.app import application
	from werkzeug.test import Client

	site = frappe.local.site
	route = "wk-cache-probe"
	if not frappe.db.exists("Web Page", {"route": route}):
		frappe.get_doc(
			{
				"doctype": "Web Page",
				"title": "Website Kit cache probe",
				"route": route,
				"published": 1,
				"content_type": "Rich Text",
				"main_section": "<p>probe</p>",
			}
		).insert(ignore_permissions=True)
	settings = frappe.get_doc(SETTINGS)
	settings.custom_css = ".wk-card { color: #111 }"
	settings.save(ignore_permissions=True)
	frappe.db.commit()
	theme_url, safe_url = settings.theme_file_url, settings.safe_file_url
	assert theme_url and safe_url and theme_url != safe_url
	frappe.destroy()  # the WSGI application opens its own connection for each request

	def fetch(client, path):
		response = client.get(path, base_url=f"http://{site}", buffered=True)
		body = response.get_data(as_text=True)
		return response, re.findall(r'href="(/files/wk-(?:theme|safe)[^"?]*)', body)

	guest, admin = Client(application), Client(application)
	response = admin.post("/api/method/login", data={"usr": "Administrator", "pwd": "admin"}, base_url=f"http://{site}")
	assert response.status_code == 200, "login failed"
	path = "/" + route
	fetch(guest, path)  # warm the cache
	response, links = fetch(guest, path)
	assert response.headers.get("X-From-Cache") == "True", "the page cache is off: set developer_mode to 0"
	assert links == [theme_url], links
	response, links = fetch(admin, path + "?wk_safe=1")
	assert response.headers.get("X-From-Cache") in (None, "False"), "a safe-mode page came from the cache"
	assert links == [safe_url], links
	assert "wk_safe=1" in ",".join(response.headers.getlist("Set-Cookie"))
	response, links = fetch(admin, path)  # the cookie alone keeps safe mode
	assert links == [safe_url] and response.headers.get("X-From-Cache") in (None, "False")
	response, links = fetch(guest, path)
	assert links == [theme_url] and response.headers.get("X-From-Cache") == "True", (
		f"a safe-mode page reached the guests: {links} {response.headers.get('X-From-Cache')}"
	)
	response, links = fetch(guest, path + "?wk_safe=1")
	assert links == [theme_url], "a guest switched safe mode on"
	response = admin.get("/api/method/website_kit.api.reset_to_preset", base_url=f"http://{site}", buffered=True)
	assert response.status_code in (403, 405), f"a GET was not refused: {response.status_code}"
	frappe.init(site=site)
	frappe.connect()
	settings = frappe.get_doc(SETTINGS)
	settings.custom_css = ""
	settings.save(ignore_permissions=True)
	for name in frappe.get_all("Web Page", filters={"route": route}, pluck="name"):
		frappe.delete_doc("Web Page", name, force=True, ignore_permissions=True)
	frappe.db.commit()
	print("http cache check ok")
