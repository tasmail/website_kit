"""Enable the shop, load and remove sample products.

Everything here needs ERPNext and Webshop and is called only from the whitelisted methods of `api.py` (System Manager or Website
Manager). Sample records are non-stock items, so they leave no stock ledger or GL entries, and every record is tagged with the
custom field `website_kit_sample`; removal deletes exactly the tagged records.
"""

import os

import frappe
from frappe import _

from . import samples, shop_menu

TAGGED = ("Item", "Item Group", "Item Price", "Website Item", "UOM")
MENU_MARKER = "website_kit_shop_menu_added"
# What Webshop Settings holds on a fresh site; the kit sets its own values only where the customer has not changed them.
WEBSHOP_DEFAULTS = {"show_price": 0, "products_per_page": 6, "enable_field_filters": 0}
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
	"""The File records that the kit made for its samples, and only those.

	A file qualifies when it is public, an SVG named like the generated pictures, and attached to a tagged Item or to the Website
	Item of a tagged Item. A customer's own file, even one named `wk-sample-...`, never matches.
	"""
	item_names = tagged("Item")
	if not item_names:
		return []
	website_items = frappe.get_all("Website Item", filters={"item_code": ["in", item_names]}, pluck="name")
	names = []
	for doctype, parents in (("Item", item_names), ("Website Item", website_items)):
		if not parents:
			continue
		names += frappe.get_all(
			"File",
			filters={
				"attached_to_doctype": doctype,
				"attached_to_name": ["in", parents],
				"is_private": 0,
				"file_name": ["like", samples.FILE_PREFIX + "%.svg"],
			},
			pluck="name",
		)
	return names


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


def has_products(excluding: str | None = None) -> bool:
	"""True when a Website Item is published (not counting `excluding`). Never cached: one indexed lookup per uncached page."""
	if not frappe.db.exists("DocType", "Website Item"):
		return False
	filters = {"published": 1}
	if excluding:
		filters["name"] = ["!=", excluding]
	return bool(frappe.db.exists("Website Item", filters))


def menu_flips(doc, method) -> bool:
	"""Would this change of a Website Item switch "the shop has products" on or off?"""
	others = has_products(excluding=doc.name)
	if others:
		return False
	if method == "on_trash":
		return bool(doc.published)
	if method == "after_insert":
		return bool(doc.published)
	return bool(doc.has_value_changed("published"))


def clear_cache(doc=None, method=None) -> None:
	"""`doc_events` hook of Website Item. The cached page HTML carries the menu, so the website cache is cleared when the
	answer to "does the shop have products" flips. The check excludes the item being deleted and the clearing waits for the
	commit, so a rollback leaves the cache alone."""
	if doc is None or menu_flips(doc, method):
		frappe.db.after_commit.add(clear_website_pages)


def clear_website_pages() -> None:
	from frappe.website.utils import clear_website_cache

	clear_website_cache()


def webshop_enabled() -> bool:
	try:
		return bool(frappe.db.get_single_value(WEBSHOP_SETTINGS, "enabled"))
	except Exception:
		return False


def visible_menu(items):
	"""The top bar items; the shop entry is shown only while Webshop is on and a Website Item is published."""
	return shop_menu.visible_items(items, webshop_enabled() and has_products())


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

	A company, price list, customer group, price display, page size or filter choice the customer already made is kept: the
	kit's values go only where the field still holds the Webshop default. Repeating the action changes nothing.
	"""
	_require_shop()
	settings = frappe.get_doc(WEBSHOP_SETTINGS)
	company = settings.company or default_company()
	currency = frappe.get_cached_value("Company", company, "default_currency")
	changes = {}
	if not settings.enabled:
		changes["enabled"] = 1
	for field, value in (
		("company", company),
		("price_list", settings.price_list or default_price_list(currency)),
		("default_customer_group", settings.default_customer_group or default_customer_group()),
	):
		if not settings.get(field):
			changes[field] = value
	fresh = not settings.enabled  # a shop that was already on keeps every display choice
	for field, value in (("show_price", 1), ("products_per_page", 12), ("enable_field_filters", 1)):
		if fresh and settings.get(field) == WEBSHOP_DEFAULTS[field]:
			changes[field] = value
	if changes:
		settings.update(changes)
		if changes.get("enable_field_filters") and not settings.filter_fields:
			settings.append("filter_fields", {"fieldname": "item_group"})
		settings.save(ignore_permissions=True)
	menu = add_menu_entry()
	if changes or menu:
		clear_website_pages()  # cached pages still lack the shop stylesheet and the menu entry
	return {**{f"webshop.{field}": value for field, value in changes.items()}, **menu}


def add_menu_entry() -> dict:
	"""Add the shop link to the top bar once. A link that the customer removed later is not added again."""
	if frappe.defaults.get_global_default(MENU_MARKER):
		return {}
	website_settings = frappe.get_doc("Website Settings")
	if not any(shop_menu.is_shop_entry(row) for row in website_settings.top_bar_items):
		website_settings.append("top_bar_items", {"label": _("Shop"), "url": shop_menu.SHOP_URLS[0]})
		website_settings.save(ignore_permissions=True)
	frappe.defaults.set_global_default(MENU_MARKER, "1")
	return {"menu": "shop link added"}


# ---------------------------------------------------------------- samples


def load_samples() -> dict:
	"""Create the sample products (idempotent: an existing sample item is left as it is); returns the counts.

	It does not switch the shop on and does not touch Webshop Settings; prices go into the shop's price list, or into the
	site's default selling price list while the shop has none yet. If anything fails, the picture files already written are
	removed from the disk (the database part rolls back).
	"""
	_require_shop()
	if not tag_fields_exist():
		ensure_tag_fields()  # DDL commits, so it runs before the first record is written (the migrate hook normally did it)
	company = frappe.db.get_single_value(WEBSHOP_SETTINGS, "company") or default_company()
	price_list = frappe.db.get_single_value(WEBSHOP_SETTINGS, "price_list") or default_price_list(
		frappe.get_cached_value("Company", company, "default_currency")
	)
	written = []
	try:
		created = _create_samples(price_list, written)
	except Exception:
		for path in written:
			try:
				os.remove(path)
			except OSError:
				pass
		raise
	clear_cache()
	return {"created": created, "samples": len(tagged("Item"))}


def site_language() -> str:
	"""The language of the site (System Settings), not of the user who presses the button: the samples are shown to visitors."""
	return (frappe.db.get_single_value("System Settings", "language") or "en")[:2]


def tag_fields_exist() -> bool:
	return all(frappe.get_meta(doctype).has_field(samples.TAG_FIELD) for doctype in TAGGED)


def _create_samples(price_list: str, written: list) -> int:
	tag = {samples.TAG_FIELD: 1}
	lang = site_language()
	group, uom = samples.group_name(lang), samples.uom_name(lang)
	# A group or unit that already exists (the customer's own, or ERPNext's) is used as it is and never tagged, so removal leaves it.
	if not frappe.db.exists("Item Group", group):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": group,
				"parent_item_group": "All Item Groups",
				"is_group": 0,
				**tag,
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("UOM", uom):
		frappe.get_doc({"doctype": "UOM", "uom_name": uom, "enabled": 1, "must_be_whole_number": 1, **tag}).insert(
			ignore_permissions=True
		)
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
				"item_group": group,
				"stock_uom": uom,
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
				"price_list": price_list,
				"price_list_rate": entry[5],
				"selling": 1,
				**tag,
			}
		).insert(ignore_permissions=True)
		image = _picture(entry, lang, item.name, written)
		frappe.get_doc(
			{
				"doctype": "Website Item",
				"item_code": item.name,
				"web_item_name": name,
				"item_group": group,
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
	return created


def _picture(entry: tuple, lang: str, item_name: str, written: list) -> str:
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
	written.append(doc.get_full_path())
	return doc.file_url


def remove_samples() -> dict:
	"""Delete exactly the tagged records and the files the kit made for them; an item, group or unit that a document uses is kept and named."""
	_require_shop()
	files = sample_files()  # chosen first: they are found through the records that are deleted below
	removed = {"Website Item": 0, "Item Price": 0, "Item": 0, "Item Group": 0, "UOM": 0, "File": 0}
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
	# The group and the unit are the kit's own only while nothing links to them. They are deleted without `force`, so Frappe's link
	# check runs over every link field (a customer's item, price, conversion factor, invoice line ...); one that is used is kept and named.
	for doctype in ("Item Group", "UOM"):
		for name in tagged(doctype):
			if kept:
				continue
			try:
				frappe.delete_doc(doctype, name, ignore_permissions=True)
				removed[doctype] += 1
			except frappe.LinkExistsError:
				kept.append(f"{doctype}: {name}")
	if kept:
		kept_files = set(sample_files())
		files = [name for name in files if name not in kept_files]
	for name in files:
		if frappe.db.exists("File", name):
			frappe.delete_doc("File", name, ignore_permissions=True, force=True)
			removed["File"] += 1
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
