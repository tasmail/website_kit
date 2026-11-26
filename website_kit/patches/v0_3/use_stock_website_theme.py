"""Move a site off the retired `Website Kit` Website Theme and drop the unused record.

Releases before 0.3 assigned a kit-owned Website Theme that needed a per-site node/sass compile. Where the compile left no file,
Frappe printed `href="None"` and omitted its base stylesheet, so the stock pages (the Webshop catalogue, the 404 page) came out
unstyled. This patch runs before the `after_migrate` hooks (Frappe's own re-saves, and so re-compiles, the active theme there),
switches only the exact value `Website Kit` to `Standard`, and deletes the retired record when nothing selects it. Idempotent.
"""

import frappe

from website_kit import apply


def execute():
	apply.ensure_stock_theme()
	if (
		frappe.db.exists("Website Theme", "Website Kit")
		and frappe.db.get_single_value("Website Settings", "website_theme") != "Website Kit"
	):
		frappe.db.delete(
			"Website Theme", {"name": "Website Kit"}
		)  # a standard record cannot be deleted through the document API
