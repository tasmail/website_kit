"""Request-time hooks: link the theme files into public pages and close the site to crawlers while it is closed."""

import frappe

from . import WK_THEME_API, __version__, seo
from .theme.escape import esc, safe_url

SETTINGS = "Website Kit Settings"
BASE_CSS = "/assets/website_kit/css/wk.css"


def _settings():
	"""The cached settings, or None when the site has no table for them yet (before the first migrate)."""
	try:
		return frappe.get_cached_doc(SETTINGS)
	except Exception:
		return None


def update_website_context(context):
	"""Hook `update_website_context`: the stylesheet links, the `wk` template values and the robots meta tag."""
	settings = _settings()
	allow = bool(settings and settings.allow_search_engines)
	links = f'<link rel="stylesheet" href="{BASE_CSS}?v={__version__}">'
	theme_url = safe_url(settings.theme_file_url) if settings else ""
	if theme_url:
		links += f'<link rel="stylesheet" href="{esc(theme_url)}?v={esc(settings.theme_hash)}">'
	brand = (settings.brand_name if settings else "") or frappe.get_website_settings("app_name") or ""
	return {
		"head_include": (context.get("head_include") or "") + links,
		"metatags": seo.metatags(context.get("metatags"), allow),
		# Strings for the standard templates: already escaped, braces encoded, so they are inert even in a second Jinja pass.
		"wk": {"brand_name": esc(brand), "theme_api": WK_THEME_API},
	}


def after_request(response, request):
	"""Hook `after_request`: `X-Robots-Tag: noindex, nofollow` while the site is closed to search engines."""
	settings = _settings()
	for name, value in seo.response_headers(bool(settings and settings.allow_search_engines)).items():
		response.headers.setdefault(name, value)
