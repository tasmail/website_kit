"""Release 0.3.4 rewrites the texts of the settings screen (DocType files and translations), changes the language button target for
alias addresses and adds a sentence about the language to the Privacy page. Press runs `bench migrate` for a site update only when
`patches.txt` (or `hooks.py`, fixtures, DocType files) changed, so this patch makes sure that a migrate runs and that the pages
catch up: it applies the theme, syncs the pages (a page the owner edited is never overwritten, a draft is written next to it) and
clears the page cache. Idempotent."""

from frappe.website.utils import clear_website_cache

from website_kit import install


def execute():
	install.after_migrate()
	clear_website_cache()
