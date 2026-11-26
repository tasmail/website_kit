"""Frappe integration tests of the shop actions; they need ERPNext, Webshop and a finished setup wizard (else they skip)."""

from unittest import mock

import frappe

try:  # Frappe 16
	from frappe.tests import IntegrationTestCase as TestCase
except ImportError:  # Frappe 15
	from frappe.tests.utils import FrappeTestCase as TestCase

from website_kit import api, runtime, samples, setup, shop

SETTINGS = "Website Kit Settings"


class TestShop(TestCase):
	def setUp(self):
		if not (shop.shop_installed() and frappe.db.count("Company")):
			self.skipTest("ERPNext, Webshop and a company are needed")
		frappe.set_user("Administrator")
		shop.remove_samples()
		self.reset_webshop()
		frappe.defaults.clear_default(shop.MENU_MARKER)
		website_settings = frappe.get_doc("Website Settings")
		website_settings.set("top_bar_items", [r for r in website_settings.top_bar_items if r.url != "/all-products"])
		website_settings.save(ignore_permissions=True)

	def tearDown(self):
		if shop.shop_installed():
			shop.remove_samples()
		frappe.db.commit()

	def test_enable_shop_sets_company_price_list_and_menu_and_is_idempotent(self):
		first = shop.enable_shop()
		settings = frappe.get_doc("Webshop Settings")
		self.assertEqual(settings.enabled, 1)
		self.assertTrue(settings.company and settings.price_list and settings.default_customer_group)
		self.assertEqual((settings.show_price, settings.products_per_page), (1, 12))
		self.assertTrue(any(row.url == "/all-products" for row in frappe.get_doc("Website Settings").top_bar_items))
		self.assertIsInstance(first, dict)
		self.assertEqual(shop.enable_shop(), {})
		self.assertEqual(
			len([r for r in frappe.get_doc("Website Settings").top_bar_items if r.url == "/all-products"]), 1
		)

	def test_a_chosen_price_list_is_kept(self):
		shop.enable_shop()
		other = self.other_price_list()
		frappe.db.set_single_value("Webshop Settings", "price_list", other)
		frappe.clear_document_cache("Webshop Settings", "Webshop Settings")
		shop.enable_shop()
		self.assertEqual(frappe.get_doc("Webshop Settings").price_list, other)

	def other_price_list(self):
		currency = frappe.get_cached_value("Company", shop.default_company(), "default_currency")
		current = frappe.db.get_single_value("Webshop Settings", "price_list")
		name = "WK Other Price List"
		if not frappe.db.exists("Price List", name):
			frappe.get_doc(
				{"doctype": "Price List", "price_list_name": name, "currency": currency, "selling": 1, "enabled": 1}
			).insert(ignore_permissions=True)
		self.assertNotEqual(name, current)
		return name

	def reset_webshop(self, **values):
		frappe.db.set_single_value(
			"Webshop Settings",
			{
				"enabled": 0,
				"show_price": 0,
				"products_per_page": 6,
				"enable_field_filters": 0,
				"price_list": "",
				**values,
			},
		)
		frappe.clear_document_cache("Webshop Settings", "Webshop Settings")

	def test_customer_display_choices_are_kept(self):
		self.reset_webshop(products_per_page=24)  # the customer set a page size before the first enable
		shop.enable_shop()
		settings = frappe.get_doc("Webshop Settings")
		self.assertEqual((settings.enabled, settings.products_per_page, settings.show_price), (1, 24, 1))
		# a shop that already runs, with its own price list
		self.reset_webshop(
			enabled=1, show_price=0, products_per_page=9, enable_field_filters=0, price_list=self.other_price_list()
		)
		self.assertEqual(shop.enable_shop(), {})
		settings = frappe.get_doc("Webshop Settings")
		self.assertEqual((settings.show_price, settings.products_per_page, settings.enable_field_filters), (0, 9, 0))

	def test_loading_samples_does_not_switch_the_shop_on_or_change_its_settings(self):
		self.reset_webshop(products_per_page=24)
		shop.load_samples()
		settings = frappe.get_doc("Webshop Settings")
		self.assertEqual(
			(settings.enabled, settings.products_per_page, settings.show_price, settings.price_list), (0, 24, 0, "")
		)
		self.assertEqual(len(shop.tagged("Item Price")), len(samples.ITEMS))

	def test_loading_samples_with_the_shop_on_and_no_price_list_uses_the_default_list(self):
		self.reset_webshop(enabled=1)
		self.assertEqual(shop.load_samples()["created"], len(samples.ITEMS))
		self.assertTrue(frappe.db.get_value("Item Price", {"item_code": samples.item_code("mug")}, "price_list"))

	def test_a_customers_own_files_named_like_samples_are_never_deleted(self):
		shop.load_samples()
		mine = []
		for name, private, attach in (
			("wk-sample-price-list.txt", 0, None),
			("wk-sample-own.svg", 0, None),
			("wk-sample-private.svg", 1, None),
		):
			doc = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": name,
					"content": "<svg xmlns='http://www.w3.org/2000/svg'/>" if name.endswith("svg") else "prices",
					"is_private": private,
					"attached_to_doctype": attach[0] if attach else None,
					"attached_to_name": attach[1] if attach else None,
				}
			).insert(ignore_permissions=True)
			mine.append(doc.name)
		shop.remove_samples()
		for name in mine:
			self.assertTrue(frappe.db.exists("File", name), name)
			frappe.delete_doc("File", name, force=True, ignore_permissions=True)
		self.assertEqual(shop.leftovers()["files"], 0)

	def test_a_failed_load_removes_the_pictures_it_wrote(self):
		import os

		folder = frappe.get_site_path("public", "files")
		before = {f for f in os.listdir(folder) if f.startswith("wk-sample-")}
		original = frappe.get_doc
		calls = {"n": 0}

		def broken(*args, **kwargs):
			doc = original(*args, **kwargs)
			if args and isinstance(args[0], dict) and args[0].get("doctype") == "Website Item":
				calls["n"] += 1
				if calls["n"] == 3:
					raise RuntimeError("boom")
			return doc

		with mock.patch("frappe.get_doc", broken), self.assertRaises(RuntimeError):
			shop.load_samples()
		frappe.db.rollback()
		self.assertEqual({f for f in os.listdir(folder) if f.startswith("wk-sample-")}, before)
		self.assertEqual(sum(shop.leftovers()["tagged"].values()), 0)

	def test_samples_load_and_remove_cleanly(self):
		loaded = shop.load_samples()
		self.assertEqual(loaded["created"], len(samples.ITEMS))
		self.assertEqual(shop.load_samples()["created"], 0)  # idempotent
		for doctype in ("Item", "Website Item", "Item Price"):
			self.assertEqual(len(shop.tagged(doctype)), len(samples.ITEMS), doctype)
		self.assertTrue(frappe.db.exists("Item Group", samples.ITEM_GROUP))
		item = frappe.get_doc("Item", samples.item_code("mug"))
		self.assertEqual((item.is_stock_item, item.is_sales_item), (0, 1))
		website_item = frappe.get_doc("Website Item", {"item_code": item.name})
		self.assertEqual(website_item.published, 1)
		self.assertTrue(website_item.website_image.startswith("/files/wk-sample-"))
		# Webshop attaches a second File record to the Website Item for the same picture
		self.assertEqual(
			len({frappe.db.get_value("File", name, "file_url") for name in shop.sample_files()}), len(samples.ITEMS)
		)
		self.assertEqual(frappe.get_doc("File", shop.sample_files()[0]).is_private, 0)
		rate = frappe.db.get_value("Item Price", {"item_code": item.name}, "price_list_rate")
		self.assertEqual(rate, samples.ITEMS[0][5])
		result = shop.remove_samples()
		self.assertEqual(result["kept"], [])
		after = shop.leftovers()
		self.assertEqual(after["tagged"], {"Item": 0, "Item Group": 0, "Item Price": 0, "Website Item": 0})
		self.assertEqual(
			(after["files"], after["stock_ledger_entries"], after["bins"], after["gl_entries"]), (0, 0, 0, 0)
		)
		self.assertFalse(frappe.db.exists("Item", samples.item_code("mug")))

	def test_loading_samples_never_creates_stock_or_accounting_entries(self):
		before = (frappe.db.count("Stock Ledger Entry"), frappe.db.count("GL Entry"), frappe.db.count("Bin"))
		shop.load_samples()
		self.assertEqual(
			(frappe.db.count("Stock Ledger Entry"), frappe.db.count("GL Entry"), frappe.db.count("Bin")), before
		)

	def test_removal_leaves_a_customers_own_products_alone(self):
		shop.ensure_tag_fields()
		own = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "WK-OWN-ITEM",
				"item_name": "Own",
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(lambda: frappe.delete_doc("Item", own.name, force=True, ignore_permissions=True))
		shop.load_samples()
		shop.remove_samples()
		self.assertTrue(frappe.db.exists("Item", "WK-OWN-ITEM"))

	def test_an_item_that_a_document_uses_is_kept_and_named(self):
		shop.load_samples()
		code = samples.item_code("mug")
		customer = frappe.db.get_value("Customer", {}, "name")
		if not customer:
			customer = (
				frappe.get_doc(
					{
						"doctype": "Customer",
						"customer_name": "WK test customer",
						"customer_group": shop.default_customer_group(),
						"territory": "All Territories",
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		order = frappe.get_doc(
			{
				"doctype": "Quotation",
				"quotation_to": "Customer",
				"party_name": customer,
				"order_type": "Shopping Cart",
				"items": [{"item_code": code, "qty": 1}],
			}
		).insert(ignore_permissions=True)
		result = shop.remove_samples()
		self.assertEqual(result["kept"], [code])
		self.assertTrue(frappe.db.exists("Item", code))
		self.assertTrue(shop.sample_files())  # the pictures stay while an item stays
		frappe.delete_doc("Quotation", order.name, force=True, ignore_permissions=True)
		self.assertEqual(shop.remove_samples()["kept"], [])
		self.assertEqual(sum(shop.leftovers()["tagged"].values()), 0)

	def menu_items(self):
		return [frappe._dict(label="Shop", url="/all-products"), frappe._dict(label="About", url="/about")]

	def test_the_shop_menu_entry_follows_the_published_products(self):
		shop.enable_shop()
		items = self.menu_items()
		self.assertFalse(shop.has_products())
		self.assertEqual([i.label for i in shop.visible_menu(items)], ["About"])
		context = runtime.update_website_context(frappe._dict(top_bar_items=items))
		self.assertEqual([i.label for i in context["top_bar_items"]], ["About"])
		shop.load_samples()
		self.assertTrue(shop.has_products())
		self.assertEqual([i.label for i in shop.visible_menu(items)], ["Shop", "About"])
		shop.remove_samples()
		self.assertFalse(shop.has_products())

	def test_deleting_the_last_published_item_from_the_desk_hides_the_entry(self):
		shop.enable_shop()
		shop.load_samples()
		names = frappe.get_all("Website Item", filters={"published": 1}, pluck="name")
		for name in names[:-1]:
			frappe.delete_doc("Website Item", name, ignore_permissions=True, force=True)
		self.assertTrue(shop.has_products())
		self.assertEqual(len(shop.visible_menu(self.menu_items())), 2)
		with (
			mock.patch.object(shop, "clear_website_pages") as cleared,
			mock.patch.object(frappe.db, "after_commit", mock.Mock(add=lambda fn: fn())),
		):
			frappe.delete_doc("Website Item", names[-1], ignore_permissions=True, force=True)
		cleared.assert_called_once()
		self.assertFalse(shop.has_products())
		self.assertEqual([i.label for i in shop.visible_menu(self.menu_items())], ["About"])

	def test_the_answer_is_never_cached_across_a_rollback(self):
		shop.enable_shop()
		frappe.db.savepoint("wk_menu")
		shop.load_samples()
		self.assertTrue(shop.has_products())
		frappe.db.rollback(save_point="wk_menu")
		self.assertFalse(shop.has_products())  # a cold or warm cache gives the same answer: there is none

	def test_a_page_cache_flush_is_queued_only_when_the_answer_flips(self):
		shop.enable_shop()
		shop.load_samples()
		queued = []
		with mock.patch.object(frappe.db, "after_commit", mock.Mock(add=queued.append)):
			item = frappe.get_doc("Website Item", {"item_code": samples.item_code("mug")})
			item.short_description = "changed"
			item.save(ignore_permissions=True)  # many published items: no flip
		self.assertNotIn(shop.clear_website_pages, queued)

	def test_the_menu_entry_needs_the_shop_to_be_on_and_is_not_added_again_after_the_customer_removed_it(self):
		shop.load_samples()
		self.reset_webshop(enabled=0)
		self.assertEqual(len(shop.visible_menu(self.menu_items())), 1)  # products exist but the shop is off
		self.reset_webshop(enabled=1)
		self.assertEqual(len(shop.visible_menu(self.menu_items())), 2)
		frappe.defaults.clear_default(shop.MENU_MARKER)
		shop.add_menu_entry()
		website_settings = frappe.get_doc("Website Settings")
		website_settings.set("top_bar_items", [r for r in website_settings.top_bar_items if r.url != "/all-products"])
		website_settings.save(ignore_permissions=True)
		self.assertEqual(shop.add_menu_entry(), {})
		self.assertFalse(any(r.url == "/all-products" for r in frappe.get_doc("Website Settings").top_bar_items))

	def test_the_context_links_the_shop_css_and_body_class_only_on_shop_pages_while_the_shop_is_on(self):
		self.reset_webshop(enabled=0)
		self.assertNotIn(
			"wk-shop.css", runtime.update_website_context(frappe._dict(route="all-products"))["head_include"]
		)
		shop.enable_shop()
		frappe.clear_document_cache("Webshop Settings", "Webshop Settings")
		values = runtime.update_website_context(frappe._dict(route="all-products", body_class="x"))
		self.assertIn("wk-shop.css", values["head_include"])
		self.assertEqual(values["body_class"], "x wk-shop")
		for context in (frappe._dict(route="about"), frappe._dict(route="")):
			other = runtime.update_website_context(context)
			self.assertNotIn("wk-shop.css", other["head_include"])
			self.assertNotIn("body_class", other)
		self.assertIn("wk-shop.css", runtime.update_website_context(frappe._dict(route="cart"))["head_include"])
		self.assertIn(
			"wk-shop.css",
			runtime.update_website_context(frappe._dict(route="x", doctype="Website Item"))["head_include"],
		)

	def test_status_and_methods(self):
		self.assertEqual(api.shop_status()["samples"], 0)
		api.load_samples()
		self.assertEqual(api.shop_status()["samples"], len(samples.ITEMS))
		self.assertEqual(api.shop_status()["published"], len(samples.ITEMS))
		api.remove_samples()
		for name in ("enable_shop", "load_samples", "remove_samples", "personalize"):
			self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[getattr(api, name)], ["POST"], name)
		for name in ("shop_status", "enable_shop", "load_samples", "remove_samples", "personalize"):
			self.assertIn(getattr(api, name), frappe.whitelisted)
			self.assertNotIn(getattr(api, name), frappe.guest_methods)


class TestSetupStage(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.brand = frappe.db.get_single_value(SETTINGS, "brand_name")
		self.contact = {
			f: frappe.db.get_single_value("Contact Us Settings", f) for f in ("email_id", "phone", "address_title")
		}
		frappe.db.set_single_value(SETTINGS, "brand_name", "")
		for field in self.contact:
			frappe.db.set_single_value("Contact Us Settings", field, "")

	def tearDown(self):
		settings = frappe.get_doc(SETTINGS)
		settings.brand_name = self.brand or ""
		settings.save(ignore_permissions=True)
		for field, value in self.contact.items():
			frappe.db.set_single_value("Contact Us Settings", field, value or "")
		frappe.db.commit()

	def test_the_stage_fills_empty_values_once(self):
		args = {"company_name": "Ромашка ТОВ", "email": "admin-login@example.com", "phone": "+380441234567"}
		first = setup.from_wizard(args)
		self.assertEqual(first["brand_name"], "Ромашка ТОВ")
		self.assertEqual(frappe.db.get_single_value(SETTINGS, "brand_name"), "Ромашка ТОВ")
		# the administrator's login address and any phone of the wizard never reach the public contact page
		self.assertFalse(frappe.db.get_single_value("Contact Us Settings", "email_id"))
		self.assertFalse(frappe.db.get_single_value("Contact Us Settings", "phone"))
		self.assertEqual(setup.from_wizard(args), {})  # idempotent
		self.assertEqual(setup.from_wizard({"company_name": "Other"}), {})  # nothing is overwritten
		self.assertEqual(frappe.db.get_single_value(SETTINGS, "brand_name"), "Ромашка ТОВ")

	def test_a_failing_stage_is_logged_and_never_raises(self):
		with mock.patch.object(setup, "fill", side_effect=RuntimeError("boom")):
			self.assertEqual(setup.from_wizard({"company_name": "A"}), {})
		self.assertTrue(frappe.db.exists("Error Log", {"error": ["like", "%boom%"]}))

	def test_fill_clears_the_website_cache_when_it_writes(self):
		with mock.patch("frappe.website.utils.clear_website_cache") as cleared:
			setup.fill("Brand", "info@example.com")
			cleared.assert_called()
			cleared.reset_mock()
			setup.fill("Brand", "info@example.com")
			cleared.assert_not_called()
		self.assertEqual(frappe.db.get_single_value("Contact Us Settings", "email_id"), "info@example.com")

	def test_the_hook_returns_a_stage_with_one_task(self):
		self.assertIn("website_kit.setup.stages", frappe.get_hooks("setup_wizard_stages"))
		stages = setup.stages({"company_name": "A"})
		self.assertEqual(len(stages), 1)
		self.assertIs(stages[0]["tasks"][0]["fn"], setup.from_wizard)
		self.assertEqual(setup.from_wizard(None), {})

	def test_personalize_is_the_same_logic_and_applies_the_theme(self):
		result = setup.personalize()
		self.assertIsInstance(result, dict)
		self.assertEqual(setup.personalize(), {})
