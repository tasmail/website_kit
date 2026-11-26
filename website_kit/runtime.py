"""Request-time hooks: link the theme files into public pages and close the site to crawlers while it is closed."""

import json

import frappe

from . import WK_THEME_API, __version__, seo, stockpage
from .theme.escape import esc, safe_url

SETTINGS = "Website Kit Settings"
BASE_CSS = "/assets/website_kit/css/wk.css"
SHOP_CSS = "/assets/website_kit/css/wk-shop.css"
MANAGER_ROLES = frozenset({"System Manager", "Website Manager"})
SAFE_COOKIE = "wk_safe"
SAFE_COOKIE_SECONDS = 8 * 3600


def _settings():
	"""The cached settings, or None when the site has no table for them yet (before the first migrate)."""
	try:
		return frappe.get_cached_doc(SETTINGS)
	except Exception:
		return None


def _shop_enabled() -> bool:
	"""True while Webshop is installed and switched on (cached document)."""
	if "webshop" not in frappe.get_installed_apps():
		return False
	try:
		return bool(frappe.get_cached_doc("Webshop Settings").enabled)
	except Exception:
		return False


SHOP_ROUTES = ("/all-products", "/cart", "/orders", "/search", "/wishlist", "/checkout")


def is_shop_page(context) -> bool:
	"""True for the Webshop pages: the catalogue and its sub-routes, search, cart, orders, wishlist and product pages."""
	route = "/" + str(context.get("route") or "").strip("/")
	if not context.get("route"):
		request = getattr(frappe.local, "request", None)
		route = (getattr(request, "path", "") or "").rstrip("/")
	if any(route == shop or route.startswith(shop + "/") for shop in SHOP_ROUTES):
		return True
	return context.get("doctype") == "Website Item" or "product-page" in str(context.get("body_class") or "")


def is_manager() -> bool:
	"""A logged-in user who may edit the website (the roles that can already put script into `head_html`)."""
	user = frappe.session.user
	return user != "Guest" and bool(MANAGER_ROLES & set(frappe.get_roles(user)))


def _flag(name: str):
	value = (frappe.form_dict or {}).get(name)
	if value is None:
		request = getattr(frappe.local, "request", None)
		value = request.cookies.get(name) if request is not None and name == SAFE_COOKIE else None
	return value


def render_mode(settings) -> str:
	"""`preview` (the draft file, `?wk_preview=1`), `safe` (no Custom CSS, `?wk_safe=1` or the cookie) or `normal`.

	Only for a logged-in Website Manager or System Manager; a visitor can never switch the look of the page, so a
	cached page of the public site is never one of these.
	"""
	if not settings or not is_manager():
		return "normal"
	if str(_flag("wk_preview")) == "1" and settings.draft_file_url:
		return "preview"
	if str(_flag(SAFE_COOKIE)) == "1":
		return "safe"
	return "normal"


def theme_link(settings, mode: str) -> str:
	"""The URL (with its cache-busting hash) of the stylesheet a page of that mode links."""
	if mode == "preview":
		try:
			digest = json.loads(settings.draft_state or "{}").get("hash", "")
		except ValueError:
			digest = ""
		url = settings.draft_file_url or ""
		# The draft is a private file: only its own path shape is linked.
		return f"{url}?v={digest}" if url.startswith("/private/files/wk-draft") and url.endswith(".css") else ""
	url = (
		safe_url(settings.safe_file_url)
		if mode == "safe" and settings.safe_file_url
		else safe_url(settings.theme_file_url)
	)
	return f"{url}?v={settings.theme_hash}" if url else ""


def before_request():
	"""Hook `before_request`: a preview or safe-mode request of a manager skips the website page cache.

	Frappe keys that cache by path and language only, so without this a warm cache would show the public look to the
	manager, and a manager's page could be stored for the public.
	"""
	if frappe.session.user == "Guest":
		return
	if render_mode(_settings()) != "normal":
		frappe.local.no_cache = 1


def webshop_messages() -> dict:
	"""The Webshop script strings in the language of the request; empty for English, where nothing needs translating."""
	if (getattr(frappe.local, "lang", "") or "en").startswith("en"):
		return {}
	return stockpage.translated(lambda text, context: frappe._(text, context=context))


def update_website_context(context):
	"""Hook `update_website_context`: the stylesheet links, the `wk` template values and the robots meta tag."""
	settings = _settings()
	mode = render_mode(settings)
	allow = bool(settings and settings.allow_search_engines) and mode == "normal"
	links = f'<link rel="stylesheet" href="{BASE_CSS}?v={__version__}">'
	link = theme_link(settings, mode) if settings else ""
	if link:
		links += f'<link rel="stylesheet" href="{esc(link)}">'
	shop_on = _shop_enabled() and is_shop_page(context)
	shop_link = f"{SHOP_CSS}?v={__version__}" if shop_on else ""
	if shop_on:
		links += f'<link rel="stylesheet" href="{shop_link}">'
	brand = (settings.brand_name if settings else "") or frappe.get_website_settings("app_name") or ""
	values = {
		"head_include": (context.get("head_include") or "") + links,
		"metatags": seo.metatags(context.get("metatags"), allow),
		# Strings for the standard templates: already escaped, braces encoded, so they are inert even in a second Jinja pass.
		"wk": {
			"brand_name": esc(brand),
			"theme_api": WK_THEME_API,
			"mode": mode,
			# What the navbar emits itself: Frappe's login page replaces the whole head_include block (see stockpage.py).
			"links": stockpage.links(f"{BASE_CSS}?v={__version__}", link, shop_link),
			"scripts": stockpage.scripts(guard=True, messages=webshop_messages() if shop_on else {}),
		},
	}
	if shop_on:
		values["body_class"] = f"{context.get('body_class') or ''} wk-shop".strip()
	if context.get("top_bar_items"):
		from . import shop

		values["top_bar_items"] = shop.visible_menu(context.get("top_bar_items"))
	return values


NOT_PUBLIC_PREFIXES = ("/app", "/api", "/assets", "/files", "/private", "/socket.io", "/desk")


def is_public_html(response, request) -> bool:
	"""True for an HTML page of the public website: not the Desk, the API, assets or file downloads."""
	path = getattr(request, "path", "") or ""
	not_public = any(
		path == prefix or path.startswith(prefix + "/") for prefix in NOT_PUBLIC_PREFIXES
	)  # whole segments
	return response.mimetype == "text/html" and not not_public


def is_https(request) -> bool:
	"""True when the visitor reached the site over https, also behind a proxy that says so."""
	if request is None:
		return False
	forwarded = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip().lower()
	return request.scheme == "https" or forwarded == "https"


def after_request(response, request):
	"""Hook `after_request`: `X-Robots-Tag: noindex, nofollow` while the site is closed to search engines.

	Also keeps the safe-mode cookie: `?wk_safe=1` sets it for a manager, `?wk_safe=0` clears it.
	"""
	if response is None:  # an error page that could not be built
		return
	settings = _settings()
	mode = render_mode(settings)
	allow = bool(settings and settings.allow_search_engines) and mode == "normal"
	for name, value in seo.response_headers(allow).items():
		response.headers.setdefault(name, value)
	request = request or getattr(frappe.local, "request", None)
	if mode != "normal" and is_public_html(response, request):
		response.headers["Cache-Control"] = "private, no-store"
	flag = (frappe.form_dict or {}).get(SAFE_COOKIE)
	if flag is not None and is_manager():
		if str(flag) == "1":
			response.set_cookie(
				SAFE_COOKIE,
				"1",
				max_age=SAFE_COOKIE_SECONDS,
				httponly=True,
				samesite="Lax",
				secure=is_https(request),
			)
		else:
			response.delete_cookie(SAFE_COOKIE)
