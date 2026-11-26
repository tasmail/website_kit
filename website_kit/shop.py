"""Enable the shop, load and remove sample products.

Everything here needs ERPNext and Webshop and is called only from the whitelisted methods of `api.py` (System Manager or Website
Manager). Sample records are non-stock items, so they leave no stock ledger or GL entries, and every record is tagged with the
custom field `website_kit_sample`; removal deletes exactly the tagged records.
"""

import frappe
from frappe import _

from . import samples, shop_menu

TAGGED = ("Item", "Item Group", "Item Price", "Website Item")
CACHE_KEY = "wk_shop_has_products"
CACHE_SECONDS = 300
WEBSHOP_SETTINGS = "Webshop Settings"


def shop_installed() -> bool:
	return bool(frappe.db.exists("DocType", "Website Item")) and bool(frappe.db.exists("DocType", WEBSHOP_SETTINGS))


def _require_shop() -> None:
	if not shop_installed():
		frappe.throw(_("The shop needs the ERPNext and Webshop apps on this site."))


def ensure_tag_fields() -> None:
	"""Create the hidden tag field on the records the samples use (idempotent)."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	field = {
		"fieldname": samples.TAG_FIELD,
		"fieldtype": "Check",
		"label": "Website Kit sample",
		"default": "0",
		"hidden": 1,
		"read_only": 1,
		"no_copy": 1,
		"print_hide": 1,
		"report_hide": 1,
	}
	create_custom_fields({doctype: [dict(field)] for doctype in TAGGED}, ignore_validate=True)


def tagged(doctype: str) -> list[str]:
	if not frappe.get_meta(doctype).has_field(samples.TAG_FIELD):
		return []
	return frappe.get_all(doctype, filters={samples.TAG_FIELD: 1}, pluck="name")


def sample_files() -> list[str]:
	return frappe.get_all("File", filters={"file_name": ["like", samples.FILE_PREFIX + "%"]}, pluck="name")


def status() -> dict:
	"""What the settings page shows: whether the shop is on, how many products are published, how many samples exist."""
	data = {"installed": shop_installed(), "enabled": 0, "published": 0, "samples": 0, "company": "", "price_list": ""}
	if not data["installed"]:
		return data
	settings = frappe.get_cached_doc(WEBSHOP_SETTINGS)
	data.update(
		enabled=int(bool(settings.enabled)),
		company=settings.company or "",
		price_list=settings.price_list or "",
		published=frappe.db.count("Website Item", {"published": 1}),
		samples=len(tagged("Item")),
	)
	return data


# ---------------------------------------------------------------- the menu rule


def has_products() -> bool:
	"""True when at least one Website Item is published; cached for a few minutes and cleared when a Website Item changes."""
	cached = frappe.cache.get_value(CACHE_KEY)
	if cached is not None:
		return bool(cached)
	value = 0
	if frappe.db.exists("DocType", "Website Item"):
		value = 1 if frappe.db.exists("Website Item", {"published": 1}) else 0
	frappe.cache.set_value(CACHE_KEY, value, expires_in_sec=CACHE_SECONDS)
	return bool(value)


def clear_cache(doc=None, method=None) -> None:
	"""`doc_events` hook of Website Item: the menu follows the data.

	The cached page HTML carries the menu, so the website cache is cleared when "there are products" flips.
	"""
	before = frappe.cache.get_value(CACHE_KEY)
	frappe.cache.delete_value(CACHE_KEY)
	if before is not None and bool(before) != has_products():
		clear_website_pages()


def clear_website_pages() -> None:
	from frappe.website.utils import clear_website_cache

	clear_website_cache()


def visible_menu(items):
	return shop_menu.visible_items(items, has_products())


# ---------------------------------------------------------------- enable the shop


def default_company() -> str:
	company = frappe.defaults.get_global_default("company") or frappe.db.get_value(
		"Company", {}, "name", order_by="creation asc"
	)
	if not company:
		frappe.throw(_("There is no company yet. Finish the setup wizard, then enable the shop."))
	return company


def default_price_list(currency: str) -> str:
	filters = {"selling": 1, "enabled": 1}
	name = frappe.db.get_value(
		"Price List", {**filters, "currency": currency, "name": "Standard Selling"}
	) or frappe.db.get_value("Price List", {**filters, "currency": currency}, "name", order_by="creation asc")
	if not name:
		frappe.throw(_("There is no enabled selling price list in {0}.").format(currency))
	return name


def default_customer_group() -> str:
	for name in ("Individual", "All Customer Groups"):
		if frappe.db.exists("Customer Group", name):
			return name
	return frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups"


def enable_shop() -> dict:
	"""Switch Webshop on with the company and price list of the site, and add the shop link to the menu; returns what changed.

	A company, price list or customer group the customer already chose is kept. Repeating the action changes nothing.
	"""
	_require_shop()
	settings = frappe.get_doc(WEBSHOP_SETTINGS)
	company = settings.company or default_company()
	currency = frappe.get_cached_value("Company", company, "default_currency")
	wanted = {
		"enabled": 1,
		"company": company,
		"price_list": settings.price_list or default_price_list(currency),
		"default_customer_group": settings.default_customer_group or default_customer_group(),
		"show_price": 1,
		"products_per_page": 12,
	}
	changes = {
		field: value
		for field, value in wanted.items()
		if settings.get(field) != value
		and (field in ("enabled", "show_price", "products_per_page") or not settings.get(field))
	}
	if not settings.enable_field_filters:
		changes["enable_field_filters"] = 1
	if changes:
		settings.update(changes)
		if not settings.filter_fields:
			settings.append("filter_fields", {"fieldname": "item_group"})
		settings.save(ignore_permissions=True)
	menu = add_menu_entry()
	if changes or menu:
		clear_website_pages()  # cached pages still lack the shop stylesheet and the menu entry
	return {**{f"webshop.{field}": value for field, value in changes.items()}, **menu}


def add_menu_entry() -> dict:
	"""Add the shop link to the top bar of Website Settings when it is not there."""
	website_settings = frappe.get_doc("Website Settings")
	if any(shop_menu.is_shop_entry(row) for row in website_settings.top_bar_items):
		return {}
	website_settings.append("top_bar_items", {"label": _("Shop"), "url": shop_menu.SHOP_URLS[0]})
	website_settings.save(ignore_permissions=True)
	return {"menu": "shop link added"}


# ---------------------------------------------------------------- samples


def load_samples() -> dict:
	"""Create the sample products (idempotent: an existing sample item is left as it is); returns the counts."""
	_require_shop()
	enable_info = enable_shop() if not frappe.db.get_single_value(WEBSHOP_SETTINGS, "enabled") else {}
	ensure_tag_fields()
	settings = frappe.get_doc(WEBSHOP_SETTINGS)
	tag = {samples.TAG_FIELD: 1}
	if not frappe.db.exists("Item Group", samples.ITEM_GROUP):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": samples.ITEM_GROUP,
				"parent_item_group": "All Item Groups",
				"is_group": 0,
				**tag,
			}
		).insert(ignore_permissions=True)
	lang = frappe.local.lang or "en"
	created = 0
	for entry in samples.ITEMS:
		code = samples.item_code(entry[0])
		if frappe.db.exists("Item", code):
			continue
		name, description = samples.text_for(entry, lang)
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": name,
				"item_group": samples.ITEM_GROUP,
				"stock_uom": "Nos",
				"is_stock_item": 0,
				"is_sales_item": 1,
				"is_purchase_item": 0,
				"maintain_stock": 0,
				"description": description,
				**tag,
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": item.name,
				"price_list": settings.price_list,
				"price_list_rate": entry[5],
				"selling": 1,
				**tag,
			}
		).insert(ignore_permissions=True)
		image = _picture(entry, lang, item.name)
		frappe.get_doc(
			{
				"doctype": "Website Item",
				"item_code": item.name,
				"web_item_name": name,
				"item_group": samples.ITEM_GROUP,
				"published": 1,
				"website_image": image,
				"thumbnail": image,  # an SVG has no raster thumbnail; naming one keeps Webshop from trying to make it
				"website_image_alt": name,
				"short_description": description,
				"web_long_description": description,
				**tag,
			}
		).insert(ignore_permissions=True)
		created += 1
	clear_cache()
	return {"created": created, "samples": len(tagged("Item")), **enable_info}


def _picture(entry: tuple, lang: str, item_name: str) -> str:
	"""Write the generated SVG as a public File attached to the sample item; returns its URL."""
	doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": samples.file_name(entry[0]),
			"content": samples.svg_for(entry, lang),
			"is_private": 0,
			"attached_to_doctype": "Item",
			"attached_to_name": item_name,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.file_url


def remove_samples() -> dict:
	"""Delete exactly the tagged records and the sample pictures; an item that a document already uses is kept and named."""
	_require_shop()
	removed = {"Website Item": 0, "Item Price": 0, "Item": 0, "Item Group": 0, "File": 0}
	kept = []
	for doctype in ("Website Item", "Item Price"):
		for name in tagged(doctype):
			frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
			removed[doctype] += 1
	for name in tagged("Item"):
		try:
			frappe.delete_doc("Item", name, ignore_permissions=True)
			removed["Item"] += 1
		except frappe.LinkExistsError:
			kept.append(name)
	if not kept:
		for name in tagged("Item Group"):
			if not frappe.db.exists("Item", {"item_group": name}):
				frappe.delete_doc("Item Group", name, ignore_permissions=True, force=True)
				removed["Item Group"] += 1
		for name in sample_files():
			frappe.delete_doc("File", name, ignore_permissions=True, force=True)
			removed["File"] += 1
	clear_cache()
	return {"removed": removed, "kept": kept}


def leftovers() -> dict:
	"""What a clean removal leaves: tagged records, sample files, stock ledger entries and GL entries of sample items."""
	codes = [samples.item_code(entry[0]) for entry in samples.ITEMS]
	return {
		"tagged": {doctype: len(tagged(doctype)) for doctype in TAGGED},
		"files": len(sample_files()),
		"stock_ledger_entries": frappe.db.count("Stock Ledger Entry", {"item_code": ["in", codes]}),
		"bins": frappe.db.count("Bin", {"item_code": ["in", codes]}),
		"gl_entries": frappe.db.sql("select count(*) from `tabGL Entry` where remarks like %s", ("%WK-SAMPLE-%",))[0][
			0
		],
	}
