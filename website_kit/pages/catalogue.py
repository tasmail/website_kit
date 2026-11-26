"""The data script of the home page: a bounded read of the published Website Items for the catalogue strip.

It runs in Builder's script executor (safe exec with or without server scripts), so it uses only what both allow: `frappe.db`
reads (`get_all`, `exists`, `get_single_value`), no imports, no names that start with an underscore, no tuple unpacking.
One query, at most `LIMIT` rows, no price lookup. It renders nothing (`wk_has_products` false) when Webshop is absent, the shop
is switched off or no item is published, and never raises. Values are escaped, braces included, because Builder inserts bound
values as raw HTML and renders the page through Jinja once more.
"""

LIMIT = 8

_TEMPLATE = """def clean(value):
	return (value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("{", "&#123;").replace("}", "&#125;")


products = []
try:
	if frappe.db.exists("DocType", "Website Item") and frappe.db.exists("DocType", "Webshop Settings"):
		if frappe.db.get_single_value("Webshop Settings", "enabled"):
			rows = frappe.db.get_all(
				"Website Item",
				filters={"published": 1},
				fields=["web_item_name", "route", "website_image", "website_image_alt", "short_description"],
				order_by="ranking desc, modified desc",
				limit=__LIMIT__,
			)
			for row in rows:
				name = row.get("web_item_name") or ""
				route = row.get("route") or ""
				if name and route:
					image = row.get("website_image") or ""
					if not image.startswith("/files/"):
						image = ""
					products.append({
						"name": clean(name),
						"url": "/" + clean(route.strip("/")),
						"image": clean(image),
						"has_image": bool(image),
						"image_alt": clean(row.get("website_image_alt")),
						"description": clean((row.get("short_description") or "")[:160]),
					})
except Exception:
	products = []
data.wk_products = products
data.wk_has_products = len(products) > 0
"""
DATA_SCRIPT = _TEMPLATE.replace("__LIMIT__", str(LIMIT))

# The contact and privacy pages carry a tiny script on purpose: a page with a data script is never page-cached, and what they
# show (the form, the reCAPTCHA paragraph) depends on the host of the request and the state of the guard.
CONTACT_SCRIPT = "data.wk_contact_page = 1\n"
