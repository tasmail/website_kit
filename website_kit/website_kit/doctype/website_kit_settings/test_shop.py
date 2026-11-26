"""Frappe integration tests of the shop actions; they need ERPNext, Webshop and a finished setup wizard (else they skip)."""

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
		settings = frappe.get_doc("Webshop Settings")
		price_list = settings.price_list
		shop.enable_shop()
		self.assertEqual(frappe.get_doc("Webshop Settings").price_list, price_list)

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

	def test_the_shop_menu_entry_follows_the_published_products(self):
		shop.enable_shop()
		items = [frappe._dict(label="Shop", url="/all-products"), frappe._dict(label="About", url="/about")]
		self.assertFalse(shop.has_products())
		self.assertEqual([i.label for i in shop.visible_menu(items)], ["About"])
		context = runtime.update_website_context(frappe._dict(top_bar_items=items))
		self.assertEqual([i.label for i in context["top_bar_items"]], ["About"])
		shop.load_samples()
		self.assertTrue(shop.has_products())  # the Website Item hook cleared the cache
		self.assertEqual([i.label for i in shop.visible_menu(items)], ["Shop", "About"])
		shop.remove_samples()
		self.assertFalse(shop.has_products())

	def test_the_context_links_the_shop_css_and_body_class_only_while_the_shop_is_on(self):
		frappe.db.set_single_value("Webshop Settings", "enabled", 0)
		frappe.clear_document_cache("Webshop Settings", "Webshop Settings")
		self.assertNotIn("wk-shop.css", runtime.update_website_context(frappe._dict())["head_include"])
		shop.enable_shop()
		frappe.clear_document_cache("Webshop Settings", "Webshop Settings")
		values = runtime.update_website_context(frappe._dict(body_class="x"))
		self.assertIn("wk-shop.css", values["head_include"])
		self.assertEqual(values["body_class"], "x wk-shop")

	def test_status_and_methods(self):
		self.assertEqual(api.shop_status()["samples"], 0)
		api.load_samples()
		self.assertEqual(api.shop_status()["samples"], len(samples.ITEMS))
		self.assertEqual(api.shop_status()["published"], len(samples.ITEMS))
		api.remove_samples()
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
		args = {"company_name": "Ромашка ТОВ", "email": "info@example.com", "phone": "+380441234567"}
		first = setup.from_wizard(args)
		self.assertEqual(first["brand_name"], "Ромашка ТОВ")
		self.assertEqual(frappe.db.get_single_value(SETTINGS, "brand_name"), "Ромашка ТОВ")
		self.assertEqual(frappe.db.get_single_value("Contact Us Settings", "email_id"), "info@example.com")
		self.assertEqual(frappe.db.get_single_value("Contact Us Settings", "phone"), "+380441234567")
		self.assertEqual(setup.from_wizard(args), {})  # idempotent
		self.assertEqual(
			setup.from_wizard({"company_name": "Other", "email": "x@example.com"}), {}
		)  # nothing is overwritten
		self.assertEqual(frappe.db.get_single_value(SETTINGS, "brand_name"), "Ромашка ТОВ")

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
