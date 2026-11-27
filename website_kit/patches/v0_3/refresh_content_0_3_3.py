"""Release 0.3.3 changes the language button (a short code with the language name as tooltip, leading to the same page in the other
language) and the stylesheet; Press runs `bench migrate` for a site update only when `patches.txt` (or `hooks.py`, fixtures,
DocType files) changed, so this patch is the reason a migrate runs: it applies the theme, syncs the pages (an edited page is never
overwritten) and clears the page cache. Idempotent."""

from frappe.website.utils import clear_website_cache

from website_kit import install


def execute():
	install.after_migrate()
	clear_website_cache()
