"""The site header as one pure function, so that Builder pages and stock pages (login, shop, 404) show the same menu.

`inner()` returns the content of `<header class="wk-header">`: the brand, a native `<details>` disclosure for narrow screens
and the menu for wide ones. The menu is written twice (inside the disclosure and as a plain `<nav>`); the stylesheet shows
exactly one of them, so a visitor and a screen reader meet one menu, and no script is needed. Escape does not close the
disclosure (that would need script); a second activation of the summary does.

Everything from the site goes through `esc` (HTML escape plus brace encoding), URLs through `link_url`.
"""

import re
from urllib.parse import urlsplit

from ..theme.escape import esc, safe_url
from .content import TEXT, URLS

KIT_PAGES = (("home", "menu_home"), ("about", "menu_about"), ("contact", "menu_contact"))
KIT_KEYS = tuple(key for key, _ in KIT_PAGES)
LINK_PREFIXES = ("http://", "https://", "mailto:", "tel:")
SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")


def link_url(url) -> str:
	"""A menu target that is safe to put into `href`, normalised like Frappe's `abs_url` for the forms the old navbar took.

	A route name such as `shop` becomes `/shop`; a path and an anchor stay; an http(s), mailto or tel link stays; spaces are
	encoded. Any other scheme (`javascript:`, `data:`, `vbscript:`, `file:`, ...), a control character or a backslash gives an empty
	string, which drops the item."""
	text = "" if url is None else str(url).strip()
	if not text or "\\" in text or any(ord(char) < 32 or ord(char) == 127 for char in text):
		return ""
	if SCHEME.match(text):
		if not text.lower().startswith(LINK_PREFIXES):
			return ""
	elif not text.startswith(("/", "#")):
		text = "/" + text
	return text.replace(" ", "%20")


def _path(url) -> str:
	"""The comparable path of a same-site URL (`/` for the home page); empty for an external link."""
	parts = urlsplit(link_url(url))
	if parts.netloc or parts.scheme:
		return ""
	return "/" + parts.path.strip().strip("/").lower() if parts.path.strip() else ""


def kit_items(text, lang, published) -> list[dict]:
	"""The kit's own pages that exist, in menu order."""
	return [{"label": text[label_key], "url": URLS[key][lang]} for key, label_key in KIT_PAGES if key in published]


def merge(kit, site_items) -> list[dict]:
	"""The kit pages first, then the site's own top bar items that do not repeat one of them."""
	taken = {_path(item["url"]) for item in kit}
	extra = []
	for item in site_items or []:
		children = item.get("children") or []
		if not children and _path(item.get("url")) in taken and _path(item.get("url")):
			continue
		extra.append(item)
	return kit + extra


def _anchor(item, classes="wk-menu__link", extra="") -> str:
	url = link_url(item.get("url"))
	if not url:
		return ""
	tab = ' target="_blank" rel="noopener"' if item.get("new_tab") else ""
	return f'<a class="{classes}" href="{esc(url)}"{extra}{tab}>{esc(item.get("label"))}</a>'


def _item(item) -> str:
	children = [anchor for anchor in (_anchor(child) for child in item.get("children") or []) if anchor]
	if children:
		subs = "".join(f"<li>{anchor}</li>" for anchor in children)
		return (
			'<li class="wk-menu__item"><details class="wk-menu__group">'
			f'<summary class="wk-menu__link">{esc(item.get("label"))}</summary>'
			f'<ul class="wk-menu__sub">{subs}</ul></details></li>'
		)
	anchor = _anchor(item)
	return f'<li class="wk-menu__item">{anchor}</li>' if anchor else ""


def _nav(variant, label, items, switch, login) -> str:
	rows = "".join(_item(item) for item in items)
	if switch:
		other = switch["code"]
		anchor = _anchor(switch, extra=f' hreflang="{esc(other)}" lang="{esc(other)}"')
		rows += f'<li class="wk-menu__item">{anchor}</li>'
	return (
		f'<nav class="wk-header__nav wk-header__nav--{variant}" aria-label="{esc(label)}">'
		f'<ul class="wk-menu">{rows}</ul>{login}</nav>'
	)


def inner(*, lang, published, other_available, site_items, hide_login, brand_html, logo_url, **_ignored) -> str:
	"""The markup inside `<header class="wk-header">`.

	`published` is the set of kit page keys that exist (`home`, `about`, `contact`); `other_available` is true when the home
	page of the other language exists; `site_items` are the Website Settings top bar items as `{label, url, new_tab, children}`
	(the shop entry already filtered); `brand_html` is already escaped, `logo_url` is a trusted site file URL or empty.
	"""
	text = TEXT.get(lang) or TEXT["en"]
	lang = lang if lang in TEXT else "en"
	items = merge(kit_items(text, lang, published), site_items)
	switch = None
	if other_available:
		code = text["lang_switch_code"]
		switch = {"label": text["lang_switch"], "url": URLS["home"][code], "code": code}
	login = ""
	if not hide_login:
		# One static link for every visitor: Frappe caches a page by path and language only, and `/me` sends a guest to the login page.
		login = f'<a class="wk-button wk-button--secondary" href="/me" rel="nofollow">{esc(text["account"])}</a>'
	logo = safe_url(logo_url)
	name = (
		f'<img class="wk-header__logo" src="{esc(logo)}" alt="{brand_html}">'
		if logo
		else f'<span class="wk-header__name">{brand_html}</span>'
	)
	brand = f'<a class="wk-header__brand" href="{esc(URLS["home"][lang])}">{name}</a>'
	label = text["menu_label"]
	return (
		'<div class="wk-container wk-header__inner">'
		f"{brand}"
		f'<details class="wk-header__menu"><summary class="wk-header__burger" aria-label="{esc(text["menu_button"])}">'
		f"<span></span></summary>{_nav('narrow', label, items, switch, login)}</details>"
		f"{_nav('wide', label, items, switch, login)}"
		"</div>"
	)
