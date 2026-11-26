"""Frappe integration tests: they run on a bench site (`bench --site <site> run-tests --app website_kit`)."""

import json

import frappe
from werkzeug.wrappers import Response

try:  # Frappe 16
	from frappe.tests import IntegrationTestCase as TestCase
except ImportError:  # Frappe 15
	from frappe.tests.utils import FrappeTestCase as TestCase

from website_kit import apply, install, runtime, seo
from website_kit.theme import compiler, escape

SETTINGS = "Website Kit Settings"


def theme_files():
	return frappe.get_all("File", filters={"file_name": apply.THEME_FILE, "is_private": 0}, fields=["name", "file_url"])


def website_settings_state():
	doc = frappe.get_doc("Website Settings")
	return doc.modified, {f: doc.get(f) for f in ("website_theme", "navbar_template", "footer_template", "robots_txt")}


class TestWebsiteKitSettings(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.settings = frappe.get_doc(SETTINGS)
		self.original = {
			f: self.settings.get(f) for f in ("preset", "brand_name", "allow_search_engines", "token_overrides")
		}
		self.robots = frappe.db.get_single_value("Website Settings", "robots_txt")

	def tearDown(self):
		# No rollback: a File write is a disk write, so each test puts the settings and the file back by saving them.
		settings = frappe.get_doc(SETTINGS)
		settings.update(self.original)
		settings.save(ignore_permissions=True)
		frappe.db.set_single_value("Website Settings", "robots_txt", self.robots)
		frappe.db.commit()

	def test_install_state(self):
		doc = frappe.get_doc(SETTINGS)
		self.assertEqual(doc.preset, "clear")
		self.assertFalse(doc.allow_search_engines)
		self.assertTrue(doc.kit_version)
		self.assertEqual(website_settings_state()[1]["website_theme"], "Website Kit")
		self.assertTrue(frappe.db.exists("Website Theme", "Website Kit"))
		for name, kind in (("WK Navbar", "Navbar"), ("WK Footer", "Footer")):
			template = frappe.get_doc("Web Template", name)
			self.assertEqual((template.type, template.standard), (kind, 1))
		self.assertEqual(len(theme_files()), 1)

	def test_the_theme_file_holds_the_compiled_css(self):
		doc = frappe.get_doc(SETTINGS)
		css, digest = compiler.build(doc.preset, doc.token_overrides)
		file_doc = frappe.get_doc("File", theme_files()[0].name)
		self.assertEqual(
			file_doc.get_content().decode() if isinstance(file_doc.get_content(), bytes) else file_doc.get_content(),
			css,
		)
		self.assertEqual(doc.theme_hash, digest)
		self.assertEqual(doc.theme_file_url, "/files/wk-theme.css")
		self.assertEqual(file_doc.is_private, 0)

	def test_apply_is_idempotent(self):
		before = (website_settings_state(), frappe.get_doc(SETTINGS).modified, theme_files())
		self.assertEqual(apply.apply(), {})
		self.assertEqual(apply.apply(), {})
		self.assertEqual((website_settings_state(), frappe.get_doc(SETTINGS).modified, theme_files()), before)

	def test_after_install_twice_changes_nothing(self):
		self.assertEqual(install.after_install(), {})
		self.assertEqual(install.after_install(), {})
		self.assertEqual(len(theme_files()), 1)

	def test_reinstall_keeps_customer_data(self):
		doc = frappe.get_doc(SETTINGS)
		doc.preset = "market"
		doc.brand_name = "Ромашка"
		doc.allow_search_engines = 1
		doc.token_overrides = json.dumps({"tokens": {"color-primary": "#112233"}})
		doc.save()
		install.after_install()
		doc = frappe.get_doc(SETTINGS)
		self.assertEqual((doc.preset, doc.brand_name, doc.allow_search_engines), ("market", "Ромашка", 1))
		self.assertIn("#112233", doc.token_overrides)

	def test_changing_the_preset_updates_the_same_file(self):
		first = theme_files()
		doc = frappe.get_doc(SETTINGS)
		doc.preset = "night"
		doc.save()
		after = theme_files()
		self.assertEqual([f.name for f in after], [f.name for f in first])
		file_doc = frappe.get_doc("File", after[0].name)
		content = file_doc.get_content()
		content = content.decode() if isinstance(content, bytes) else content
		self.assertIn("preset night", content)
		self.assertEqual(frappe.get_doc(SETTINGS).theme_hash, compiler.build("night")[1])

	def test_an_orphan_file_on_disk_does_not_change_the_stable_name(self):
		frappe.db.delete("File", {"file_name": apply.THEME_FILE})
		self.assertEqual(theme_files(), [])
		self.assertEqual(apply.apply().get("theme_file"), "created")
		files = theme_files()
		self.assertEqual([f.file_url for f in files], ["/files/wk-theme.css"])

	def test_invalid_overrides_are_rejected(self):
		doc = frappe.get_doc(SETTINGS)
		doc.token_overrides = json.dumps({"tokens": {"color-primary": "red"}})
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_a_customers_robots_text_is_kept(self):
		frappe.db.set_single_value("Website Settings", "robots_txt", "User-agent: *\nDisallow: /private\n")
		doc = frappe.get_doc(SETTINGS)
		doc.allow_search_engines = 1
		doc.save()
		self.assertEqual(
			frappe.db.get_single_value("Website Settings", "robots_txt"), "User-agent: *\nDisallow: /private\n"
		)

	def test_robots_follow_the_switch(self):
		frappe.db.set_single_value("Website Settings", "robots_txt", seo.ROBOTS_CLOSED)
		doc = frappe.get_doc(SETTINGS)
		doc.allow_search_engines = 1
		doc.save()
		self.assertEqual(frappe.db.get_single_value("Website Settings", "robots_txt"), seo.ROBOTS_OPEN)
		doc.allow_search_engines = 0
		doc.save()
		self.assertEqual(frappe.db.get_single_value("Website Settings", "robots_txt"), seo.ROBOTS_CLOSED)

	def test_noindex_header_while_closed(self):
		response = Response("x")
		runtime.after_request(response=response, request=None)
		self.assertEqual(response.headers.get("X-Robots-Tag"), "noindex, nofollow")
		doc = frappe.get_doc(SETTINGS)
		doc.allow_search_engines = 1
		doc.save()
		response = Response("x")
		runtime.after_request(response=response, request=None)
		self.assertNotIn("X-Robots-Tag", response.headers)

	def test_the_hooks_are_registered(self):
		self.assertIn("website_kit.runtime.after_request", frappe.get_hooks("after_request"))
		self.assertIn("website_kit.runtime.update_website_context", frappe.get_hooks("update_website_context"))

	def test_context_links_the_stylesheets_and_closes_the_page(self):
		values = runtime.update_website_context(frappe._dict())
		self.assertIn("/assets/website_kit/css/wk.css", values["head_include"])
		self.assertIn("/files/wk-theme.css?v=", values["head_include"])
		self.assertEqual(values["metatags"]["robots"], "noindex, nofollow")

	def test_templates_render_site_data_inert(self):
		brand = "{{ 7*7 }} <b>"
		context = {
			"wk": {"brand_name": escape.esc(brand)},
			"top_bar_items": [frappe._dict(label="{{ 7*7 }}", url="/about")],
			"footer_items": [frappe._dict(label="<i>", url="/x")],
			"copyright": "{{ 7*7 }} & Co",
			"footer_address": "{% if 1 %}x{% endif %}",
			"url_prefix": "",
		}
		for name in ("WK Navbar", "WK Footer"):
			html = frappe.get_doc("Web Template", name).render(context)
			self.assertNotIn("49", html)
			self.assertNotIn("<b>", html)
			self.assertNotIn("{{", html)
		self.assertIn("wk-header", frappe.get_doc("Web Template", "WK Navbar").render(context))

	def test_ukrainian_strings(self):
		frappe.local.lang = "uk"
		try:
			frappe.local.lang_full_dict = None
			self.assertEqual(frappe._("Skip to content"), "Перейти до вмісту")
		finally:
			frappe.local.lang = "en"
			frappe.local.lang_full_dict = None
