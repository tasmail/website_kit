"""Release 0.3.1 changed what a site ships (the header, the not-found page, the stylesheets, the navbar), and Press moves a site to a new
release without `bench migrate` unless `patches.txt` (or `hooks.py`, fixtures, DocType files) changed. This patch is the reason a
migrate runs; it does what the migrate hook does: apply the theme and sync the pages (policy 5.8: an edited page is never overwritten).
Idempotent."""

from website_kit import install


def execute():
	install.after_migrate()
