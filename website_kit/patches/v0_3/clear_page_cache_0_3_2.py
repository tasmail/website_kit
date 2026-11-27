"""Release 0.3.2: a Builder page now remembers its language in a cookie and the menu labels follow the language of the header.
Frappe keeps a rendered page in its cache by path and language, so the pages rendered by 0.3.1 would keep the old head until they
expire; the cache is cleared once. The patch also is the reason a migrate runs for this release (see `docs/releasing.md`).
Idempotent."""

from frappe.website.utils import clear_website_cache


def execute():
	clear_website_cache()
