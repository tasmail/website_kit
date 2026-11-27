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

	def page(client, target):
		return client.get(target, base_url=f"http://{site}", buffered=True).get_data(as_text=True)

	def header_of(body):
		match = re.search(r'<header class="wk-header">.*?</header>', body, re.S)
		assert match, "the page has no kit header"
		return match.group(0)

	def sheets(body):
		return re.findall(
			r'<link[^>]*rel="stylesheet"[^>]*href="([^"]+)"|<link[^>]*href="([^"]+)"[^>]*rel="stylesheet"', body
		)

	fetch(guest, path)  # warm the cache
	response, links = fetch(guest, path)
	assert response.headers.get("X-From-Cache") == "True", "the page cache is off: set developer_mode to 0"
	assert links == [theme_url], links
	# Every kit stylesheet is linked once (the navbar must not repeat what head_include already carries), and the header is the
	# same for a guest, for the cached copy and for a signed-in user: Frappe caches a page by path and language only.
	cached_body = page(guest, path)
	hrefs = [a or b for a, b in sheets(cached_body)]
	assert len(hrefs) == len(set(hrefs)), f"a stylesheet is linked twice: {hrefs}"
	admin_body = page(admin, path)
	assert header_of(admin_body) == header_of(cached_body), "the header differs between a guest and a signed-in user"
	assert header_of(page(guest, path)) == header_of(cached_body), "the cached header changed after a signed-in visit"
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


def shop_demo() -> None:
	"""CI and local check: switch the shop on and load the ten sample products (needs ERPNext, Webshop and a company)."""
	from . import shop

	shop.enable_shop()
	shop.load_samples()
	frappe.db.commit()
	print("shop demo ready")


def set_preset(name: str = "clear") -> None:
	"""CI and local check: save a preset the way the settings page does (`custom` is a copy of `market` with two changes)."""
	import json

	from .theme import editor

	settings = frappe.get_doc(SETTINGS)
	if name == "custom":
		values = editor.duplicate_as_custom("market", "", "")
		overrides = json.loads(values["token_overrides"])
		overrides["tokens"].update({"color-primary": "#7c3aed", "radius-md": "16px"})
		settings.update({**values, "token_overrides": json.dumps(overrides)})
	else:
		settings.update({"preset": name, "custom_base": "", "token_overrides": ""})
	settings.save(ignore_permissions=True)
	frappe.db.commit()
	print(name, settings.theme_hash)


def retire_theme() -> None:
	"""CI only: put a site in the state of a site that was installed by a release before 0.3: the Website Theme `Website Kit` exists
	(a copy of it, compiled by node on save) and is the active theme."""
	if not frappe.db.exists("Website Theme", "Website Kit"):
		doc = frappe.get_doc(
			{
				"doctype": "Website Theme",
				"theme": "Website Kit",
				"module": "Website Kit",
				"custom": 1,
				"ignored_apps": [],
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
	frappe.db.set_single_value("Website Settings", "website_theme", "Website Kit")
	# A fresh install records every listed patch as run; a site installed by an older release has not run this one.
	frappe.db.delete("Patch Log", {"patch": "website_kit.patches.v0_3.use_stock_website_theme"})
	frappe.db.commit()
	print("retired theme in place:", frappe.db.get_single_value("Website Settings", "website_theme"))


def assert_stock_theme() -> None:
	"""CI only: after `bench migrate` the site is on the stock theme, the retired record and its files are gone."""
	import os

	assert frappe.db.get_single_value("Website Settings", "website_theme") == "Standard", (
		"the site was not moved to the stock theme"
	)
	assert not frappe.db.exists("Website Theme", "Website Kit"), "the retired theme record is still there"
	folder = frappe.utils.get_files_path("website_theme", is_private=False)
	left = [name for name in (os.listdir(folder) if os.path.isdir(folder) else []) if name.startswith("website_kit_")]
	assert not left, f"generated theme files are left: {left}"
	print("stock theme ok")


def assert_upgraded() -> None:
	"""CI only, after `bench migrate` on a site that was installed from the previous release: every shipped Builder object exists in
	the shipped form (an unedited object is updated in place), the sync recorded its run, and real requests show the new header on a
	Builder page and the kit header and footer on the not-found page."""
	import json
	import re

	from frappe.app import application
	from werkzeug.test import Client

	from . import __version__
	from .pages import specs as shipped
	from .pages import sync
	from .pages.blocks import digest

	site = frappe.local.site
	state = json.loads(frappe.db.get_single_value(SETTINGS, "pages_state") or "{}")
	assert state.get("_sync") == {"version": __version__, "builder": True}, (
		f"the sync did not run in this release: {state.get('_sync')}"
	)
	assert frappe.db.get_single_value(SETTINGS, "kit_version").startswith(__version__), (
		"the theme was not applied by this release"
	)
	stale = []
	for spec in shipped.all_specs():
		if not frappe.db.exists(spec["kind"], spec["name"]):
			stale.append(f"{spec['name']}: missing")
		elif digest(sync.current_fields(spec["kind"], spec["name"])) != spec["hash"]:
			stale.append(f"{spec['name']}: not the shipped version")
	assert not stale, f"migrate did not bring the shipped pages in: {stale}"
	assert frappe.db.exists("Builder Page", {"route": "404", "published": 1}), "no published not-found page"
	frappe.db.commit()
	frappe.destroy()
	client = Client(application)  # the WSGI application opens its own connection per request

	def get(path):
		response = client.get(path, base_url=f"http://{site}", buffered=True)
		return response, response.get_data(as_text=True)

	response, body = get("/about")
	assert response.status_code == 200 and "redirect-to=/me" in body, "a Builder page does not show the new header"
	assert len(re.findall(r'class="wk-header__nav ', body)) == 2, "the header is not the new one"
	response, body = get("/wk-upgrade-check-no-such-page")
	assert response.status_code == 404, f"a miss answered {response.status_code}"
	assert 'class="wk-header"' in body and 'class="wk-footer"' in body, (
		"the not-found page has no kit header and footer"
	)
	frappe.init(site=site)
	frappe.connect()
	print("upgrade ok")
