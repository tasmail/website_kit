"""Search engine defaults: a new site is closed to crawlers until its owner opens it.

Pure functions (no Frappe import). `runtime.py` applies them to every response, `apply.py` to `Website Settings.robots_txt`.
"""

NOINDEX = "noindex, nofollow"
ROBOTS_CLOSED = "User-agent: *\nDisallow: /\n"
# Service routes are never for a crawler, even when the owner opens the site.
SERVICE_PATHS = ("/app", "/api/", "/login", "/me", "/cart", "/orders", "/update-password")
ROBOTS_OPEN = "User-agent: *\n" + "".join(f"Disallow: {path}\n" for path in SERVICE_PATHS)
GENERATED_ROBOTS = (ROBOTS_CLOSED, ROBOTS_OPEN)


def robots_txt(allow_search_engines) -> str:
	return ROBOTS_OPEN if allow_search_engines else ROBOTS_CLOSED


def is_generated(text) -> bool:
	"""True when the text is empty or one of the two texts the kit writes; anything else was typed by the customer."""
	return not (text or "").strip() or (text or "").replace("\r\n", "\n") in GENERATED_ROBOTS


def robots_change(current, allow_search_engines) -> str | None:
	"""The new `robots_txt` if the kit may write it and it differs, else None. A customer's own text is never replaced."""
	wanted = robots_txt(allow_search_engines)
	if not is_generated(current) or (current or "").replace("\r\n", "\n") == wanted:
		return None
	return wanted


def response_headers(allow_search_engines) -> dict[str, str]:
	return {} if allow_search_engines else {"X-Robots-Tag": NOINDEX}


def metatags(existing, allow_search_engines) -> dict:
	"""The metatags of a page with `robots` added while the site is closed; a robots tag of the page itself wins."""
	tags = dict(existing or {})
	if not allow_search_engines:
		tags.setdefault("robots", NOINDEX)
	return tags
