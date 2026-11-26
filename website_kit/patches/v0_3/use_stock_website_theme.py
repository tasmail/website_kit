"""Move a site off the retired `Website Kit` Website Theme and drop the unused record and its generated files.

Releases before 0.3 assigned a kit-owned Website Theme that needed a per-site node/sass compile. Where the compile left no file,
Frappe printed `href="None"` and omitted its base stylesheet, so the stock pages (the Webshop catalogue, the 404 page) came out
unstyled. This patch runs before the `after_migrate` hooks (Frappe's own re-saves, and so re-compiles, the active theme there),
switches only the exact value `Website Kit` to `Standard`, and deletes the retired record and the CSS files it generated
(`website_theme/website_kit_<8 hex>.css` and `website_kit_style.css`, nothing else) when nothing selects it. Idempotent.
"""

import os

import frappe

from website_kit import apply, settings_sync


def execute():
	apply.ensure_stock_theme()
	if (
		frappe.db.exists("Website Theme", "Website Kit")
		and frappe.db.get_single_value("Website Settings", "website_theme") != "Website Kit"
	):
		# A standard record cannot be deleted through the document API.
		frappe.db.delete("Website Theme", {"name": "Website Kit"})
	remove_generated_files()


def remove_generated_files() -> list[str]:
	"""Delete the CSS files that the retired theme compiled, unless the theme is still in use."""
	if frappe.db.exists("Website Theme", "Website Kit"):
		return []
	folder = frappe.utils.get_files_path("website_theme", is_private=False)
	removed = []
	if os.path.isdir(folder):
		for name in sorted(os.listdir(folder)):
			if settings_sync.is_retired_theme_file(name):
				os.remove(os.path.join(folder, name))
				removed.append(name)
	return removed
