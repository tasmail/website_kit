"""Jinja functions for the Builder pages (registered in hooks.py as methods; every function of this module is a global).

Builder renders block text, `head_html` and attributes through Jinja, so a page asks for site data with a call such as
`{{ wk_brand('uk') }}` and never has the data written into its source. Every function escapes what it returns, never raises
(a failing call would turn the page into a 500; the error is logged and an empty string returned) and does at most a few
cached reads, so a cached page costs nothing at request time.
"""

import frappe
import frappe.utils

from . import __version__, contact, runtime
from .pages import markup
from .pages.content import ROUTES, TEXT, URLS
from .safe import never_raises
from .theme.escape import esc, safe_url


def _text(lang):
	return TEXT.get(lang) or TEXT["uk"]


def _brand_text() -> str:
	settings = contact.kit_settings()
	return (
		(settings.brand_name if settings else "") or frappe.get_website_settings("app_name") or frappe.local.site or ""
	)


@never_raises
def wk_brand(lang="uk"):
	return esc(_brand_text())


@never_raises
def wk_controller(lang="uk"):
	settings = contact.kit_settings()
	name = (settings.controller_name if settings else "") or ""
	return esc(name or _text(lang)["privacy_placeholder_controller"])


@never_raises
def wk_contact_list(lang="uk", variant="card"):
	return markup.contact_list(_text(lang), contact.contact_info(), variant)


@never_raises
def wk_contact_form(lang="uk"):
	"""The form while it may be shown, else the mail-to and phone block. A form that posts without the guard never exists."""
	text = _text(lang)
	if contact.form_state().render:
		privacy = URLS["privacy"].get(lang, URLS["privacy"]["uk"]) if contact.privacy_ready() else ""
		return markup.contact_form(text, privacy)
	return markup.fallback(text, contact.contact_info())


@never_raises
def wk_contact_aside(lang="uk"):
	"""The contact facts card next to the form; empty while the fallback block (which lists the facts) is shown."""
	if not contact.form_state().render:
		return ""
	return markup.contact_aside(_text(lang), contact.contact_info())


@never_raises
def wk_privacy_captcha(lang="uk"):
	"""The reCAPTCHA paragraph of the privacy page, only while the form that uses it is shown."""
	if not contact.form_state().render:
		return ""
	text = _text(lang)
	style = 'style="margin:0"'
	return (
		f'<div style="display:grid;gap:calc(var(--wk-space-unit) * 1.5)"><h2 {style}>{esc(text["privacy3_title"])}</h2>'
		f"<p {style}>{esc(text['privacy3_text'])}</p></div>"
	)


@never_raises
def wk_head(lang="uk", key="home"):
	"""The `<head>` additions of a standard page: the kit stylesheets, robots, hreflang pairs, Organization data, guard client."""
	settings = contact.kit_settings()
	allow = bool(settings and settings.allow_search_engines)
	theme = safe_url(settings.theme_file_url) if settings else ""
	theme_css = f"{theme}?v={settings.theme_hash}" if theme else ""
	alternates = []
	if all(frappe.db.exists("Builder Page", {"route": route, "published": 1}) for route in ROUTES[key].values()):
		alternates = [(code, frappe.utils.get_url(URLS[key][code])) for code in URLS[key]]
		alternates.append(("x-default", frappe.utils.get_url(URLS[key]["uk"])))
	info = contact.contact_info()
	organization = (
		markup.organization_data(_brand_text(), frappe.utils.get_url(), info.get("email"), info.get("phone"))
		if key == "home" and allow
		else None
	)
	guard_key = contact.form_state().site_key if key == "contact" else ""
	return markup.head_tags(
		base_css=f"{runtime.BASE_CSS}?v={__version__}",
		theme_css=theme_css,
		robots_closed=False,  # the robots meta tag comes from the page context (runtime.update_website_context): once, not twice
		alternates=alternates,
		organization=organization,
		guard_site_key=guard_key,
	)
