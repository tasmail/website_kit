"""Frappe integration tests: they run on a bench site (`bench --site <site> run-tests --app website_kit`)."""

import json
import os
import re
from unittest import mock

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
	"""The File records of the kit (attached to the settings)."""
	return frappe.get_all(
		"File",
		filters={"attached_to_doctype": SETTINGS, "attached_to_name": SETTINGS, "is_private": 0},
		fields=["name", "file_url"],
	)


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
		self.assertEqual(website_settings_state()[1]["website_theme"], "Standard")
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
		self.assertEqual(doc.theme_file_url, file_doc.file_url)
		self.assertRegex(doc.theme_file_url, r"^/files/wk-theme[0-9a-f]*\.css$")
		self.assertEqual(file_doc.is_private, 0)

	def test_a_site_on_the_retired_kit_theme_is_moved_to_the_stock_theme_even_if_the_file_step_fails(self):
		frappe.db.set_single_value("Website Settings", "website_theme", "Website Kit")
		with (
			mock.patch("website_kit.apply.write_file", side_effect=RuntimeError("disk full")),
			self.assertRaises(RuntimeError),
		):
			apply.apply()
		self.assertEqual(frappe.db.get_single_value("Website Settings", "website_theme"), "Standard")
		self.assertEqual(apply.apply(), {})

	def test_the_patch_moves_the_site_and_drops_the_unused_record(self):
		from website_kit.patches.v0_3 import use_stock_website_theme

		if not frappe.db.exists("Website Theme", "Website Kit"):
			frappe.db.sql(
				"insert into `tabWebsite Theme` (name, theme, module, custom, creation, modified, owner, modified_by) values ('Website Kit', 'Website Kit', 'Website Kit', 0, now(), now(), 'Administrator', 'Administrator')"
			)
		frappe.db.set_single_value("Website Settings", "website_theme", "Website Kit")
		use_stock_website_theme.execute()
		self.assertEqual(frappe.db.get_single_value("Website Settings", "website_theme"), "Standard")
		self.assertFalse(frappe.db.exists("Website Theme", "Website Kit"))
		use_stock_website_theme.execute()  # idempotent

	def test_the_patch_removes_the_files_the_retired_theme_compiled_and_nothing_else(self):
		from website_kit.patches.v0_3 import use_stock_website_theme

		folder = frappe.utils.get_files_path("website_theme", is_private=False)
		os.makedirs(folder, exist_ok=True)
		leftovers = [os.path.join(folder, "website_kit_style.css"), os.path.join(folder, "website_kit_abc12345.css")]
		customers = os.path.join(folder, "my_theme_style.css")
		for path in (*leftovers, customers):
			with open(path, "w", encoding="utf-8") as handle:
				handle.write("/* x */")
		self.addCleanup(lambda: os.path.exists(customers) and os.remove(customers))
		frappe.db.set_single_value("Website Settings", "website_theme", "Standard")
		frappe.db.delete("Website Theme", {"name": "Website Kit"})
		use_stock_website_theme.execute()
		self.assertFalse(any(os.path.exists(path) for path in leftovers))
		self.assertTrue(os.path.exists(customers))
		self.assertEqual(use_stock_website_theme.remove_generated_files(), [])  # idempotent

	def test_no_row_of_uk_csv_overrides_a_translation_of_an_installed_app(self):
		"""The kit's csv is merged last, so a plain row replaces the translation of Frappe, ERPNext or Webshop for the whole site."""
		import csv
		from pathlib import Path

		from frappe.translate import get_translations_from_apps

		apps = [app for app in frappe.get_installed_apps() if app != "website_kit"]
		existing = get_translations_from_apps("uk", apps)
		self.assertGreater(len(existing), 1000, "the translations of the installed apps could not be read")
		path = Path(frappe.get_app_path("website_kit", "translations", "uk.csv"))
		with path.open(encoding="utf-8") as handle:
			rows = [row for row in csv.reader(handle) if len(row) < 3 or not row[2]]
		clashes = [(row[0], row[1], existing[row[0]]) for row in rows if existing.get(row[0]) not in (None, row[1])]
		self.assertEqual(clashes, [])

	def test_a_customers_own_theme_is_never_replaced(self):
		for own in ("My Theme", "Website Kit 2"):
			frappe.db.set_single_value("Website Settings", "website_theme", own)
			self.assertEqual(apply.ensure_stock_theme(), {})
			apply.apply()
			self.assertEqual(frappe.db.get_single_value("Website Settings", "website_theme"), own)
		frappe.db.set_single_value("Website Settings", "website_theme", "Standard")

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

	def test_a_foreign_file_with_the_same_name_is_never_adopted_or_deleted(self):
		ours = frappe.get_doc("File", apply.find_theme_file())
		ours.delete()  # removes the record and the file on disk
		foreign = frappe.get_doc(
			{"doctype": "File", "file_name": apply.THEME_FILE, "content": "/* foreign */", "is_private": 0}
		).insert(ignore_permissions=True)
		self.addCleanup(lambda: frappe.delete_doc("File", foreign.name, force=True, ignore_permissions=True))
		self.assertEqual(apply.apply().get("theme_file"), "created")
		mine = frappe.get_doc("File", apply.find_theme_file())
		self.assertNotEqual(mine.name, foreign.name)
		self.assertNotEqual(mine.file_url, foreign.file_url)
		self.assertEqual(frappe.get_doc("File", foreign.name).get_content(), "/* foreign */")
		self.assertEqual(frappe.get_doc(SETTINGS).theme_file_url, mine.file_url)
		self.assertEqual(apply.apply(), {})  # stable afterwards, no new file
		self.assertEqual(frappe.db.count("File", {"attached_to_doctype": SETTINGS, "attached_to_name": SETTINGS}), 1)

	def test_the_update_leaves_no_temp_file_and_the_lock_is_released(self):
		doc = frappe.get_doc(SETTINGS)
		doc.preset = "ledger"
		doc.save()
		folder = os.path.dirname(frappe.get_doc("File", apply.find_theme_file()).get_full_path())
		self.assertEqual([f for f in os.listdir(folder) if f.endswith(".tmp")], [])
		if frappe.db.db_type != "postgres":
			self.assertTrue(apply.lock_is_free())
		with self.assertRaises(RuntimeError), apply.apply_lock():
			raise RuntimeError("boom")
		if frappe.db.db_type != "postgres":
			self.assertTrue(apply.lock_is_free())

	def test_the_website_cache_is_cleared_only_when_the_theme_changes(self):
		with mock.patch("frappe.website.utils.clear_website_cache") as clear:
			self.assertEqual(apply.apply(), {})
			clear.assert_not_called()
			doc = frappe.get_doc(SETTINGS)
			doc.preset = "night"
			doc.save()
			clear.assert_called()

	def test_pages_link_the_new_hash_after_a_preset_change(self):
		"""The context that feeds every public page follows the preset at once. (A full guest page render needs a request
		object and built assets, which a plain test site does not have; the cache clearing is tested above.)"""

		def linked_hash():
			head = runtime.update_website_context(frappe._dict())["head_include"]
			return re.search(r"wk-theme[0-9a-f]*\.css\?v=([0-9a-f]{16})", head).group(1)

		self.assertEqual(linked_hash(), compiler.build("clear")[1])
		doc = frappe.get_doc(SETTINGS)
		doc.preset = "night"
		doc.save()
		self.assertEqual(linked_hash(), compiler.build("night")[1])

	def test_a_failing_apply_does_not_abort_install_or_migrate(self):
		with mock.patch("website_kit.apply.apply", side_effect=RuntimeError("disk full")):
			self.assertIsNone(install.after_migrate())
			frappe.db.set_single_value(SETTINGS, "kit_version", "")
			frappe.clear_document_cache(SETTINGS, SETTINGS)
			self.assertIn("error", install.after_install())
		self.assertTrue(frappe.db.exists("Error Log", {"error": ["like", "%disk full%"]}))
		apply.apply()  # restores kit_version

	def with_top_bar(self, rows):
		"""Put these top bar rows into Website Settings for one test and restore the customer's rows afterwards."""
		website_settings = frappe.get_doc("Website Settings")
		keep = [
			{key: row.get(key) for key in ("label", "url", "parent_label", "open_in_new_tab", "right")}
			for row in website_settings.top_bar_items
		]

		def put(items):
			doc = frappe.get_doc("Website Settings")
			doc.set("top_bar_items", items)
			doc.save(ignore_permissions=True)
			if hasattr(frappe.local, "website_settings"):
				del frappe.local.website_settings

		self.addCleanup(put, keep)
		put(rows)

	def test_the_menus_render_one_level_of_children(self):
		from website_kit import jinja_api

		self.with_top_bar(
			[
				{"label": "Shop", "url": ""},
				{"label": "{{ 7*7 }}", "url": "/shop/a", "parent_label": "Shop"},
				{"label": "About us", "url": "/about-us"},
			]
		)
		nav = jinja_api.wk_header("en")
		self.assertIn("<details", nav)
		self.assertIn("<summary", nav)
		self.assertIn(">Shop</summary>", nav)
		self.assertIn("/shop/a", nav)
		self.assertIn(">About us</a>", nav)
		self.assertNotIn("49", nav)
		self.assertNotIn("{{", nav)
		context = {
			"wk": {"brand_name": "Brand"},
			"url_prefix": "",
			"footer_items": [
				frappe._dict(label="Legal", url="/legal", child_items=[frappe._dict(label="Terms", url="/terms")]),
			],
		}
		footer = frappe.get_doc("Web Template", "WK Footer").render(context)
		self.assertIn("Legal", footer)
		self.assertIn(">Terms</a>", footer)

	def test_the_header_function_escapes_the_brand(self):
		from website_kit import jinja_api

		doc = frappe.get_doc(SETTINGS)
		original = doc.brand_name
		self.addCleanup(lambda: frappe.db.set_single_value(SETTINGS, "brand_name", original or ""))
		frappe.db.set_single_value(SETTINGS, "brand_name", "{{ 7*7 }} <b>")
		frappe.clear_document_cache(SETTINGS, SETTINGS)
		html = jinja_api.wk_header("en")
		self.assertNotIn("49", html)
		self.assertNotIn("<b>", html)
		self.assertNotIn("{{", html)
		self.assertIn("&lt;b&gt;", html)

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
		self.assertIn(f"{frappe.get_doc(SETTINGS).theme_file_url}?v=", values["head_include"])
		self.assertEqual(values["metatags"]["robots"], "noindex, nofollow")

	def test_templates_render_site_data_inert(self):
		brand = "{{ 7*7 }} <b>"
		context = {
			"wk": {"brand_name": escape.esc(brand)},
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
