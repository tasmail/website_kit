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
from .content import ROUTES, TEXT, URLS

KIT_PAGES = (("home", "menu_home"), ("about", "menu_about"), ("contact", "menu_contact"))
# One link for every visitor: a guest gets the login form, a signed-in user is sent on to `/me` by Frappe (verified on 15.128.0).
ACCOUNT_URL = "/login?redirect-to=/me"
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


def switch_target(path, lang, published_routes) -> str:
	"""Where the language button of the page at `path` leads: the same page in the other language.

	A kit page goes to its twin when the twin is published (else to the other home page); any other page (the shop, the
	login, the 404) stays where it is and asks for the language with `?_lang=`, which Frappe reads before the cookie. The
	address carries no query of its own: Frappe caches a page by path and language, so a link with the visitor's
	query would be served to the next visitor."""
	other = TEXT[lang]["lang_switch_code"]
	path = "/" + (path or "").strip().strip("/")
	if path == "/" + ROUTES["home"]["uk"]:  # the route name of the home page; its public address is `/`
		path = URLS["home"]["uk"]
	for key, by_lang in URLS.items():
		if by_lang.get(lang) == path:
			return by_lang[other] if ROUTES[key][other] in published_routes else URLS["home"][other]
	return f"{path}?_lang={other}"


def _switch(item) -> str:
	"""The language button: the short code is the text, the name of the language is the tooltip and the accessible name."""
	code = item["code"]
	url = (
		link_url(item["url"]) or URLS["home"][code]
	)  # a path `link_url` refuses leads to the other home page, never to `""`
	name, short = esc(item["label"]), esc(item["short"])
	# The accessible name starts with the visible text (WCAG 2.5.3) and adds the language name; `lang` makes a reader say it right.
	return (
		f'<li class="wk-menu__item"><a class="wk-menu__lang" href="{esc(url)}" hreflang="{esc(code)}" lang="{esc(code)}" '
		f'title="{name}" aria-label="{short}, {name}">{short}</a></li>'
	)


def _nav(variant, label, items, switch, login) -> str:
	rows = "".join(_item(item) for item in items)
	if switch:
		rows += _switch(switch)
	return (
		f'<nav class="wk-header__nav wk-header__nav--{variant}" aria-label="{esc(label)}">'
		f'<ul class="wk-menu">{rows}</ul>{login}</nav>'
	)


def inner(
	*, lang, published, other_available, site_items, hide_login, brand_html, logo_url, switch_url="", **_ignored
) -> str:
	"""The markup inside `<header class="wk-header">`.

	`published` is the set of kit page keys that exist (`home`, `about`, `contact`); `other_available` is true when the home
	page of the other language exists; `site_items` are the Website Settings top bar items as `{label, url, new_tab, children}`
	(the shop entry already filtered); `switch_url` is where the language button leads (`switch_target`; the other home page when
	empty); `brand_html` is already escaped, `logo_url` is a trusted site file URL or empty.
	"""
	text = TEXT.get(lang) or TEXT["en"]
	lang = lang if lang in TEXT else "en"
	items = merge(kit_items(text, lang, published), site_items)
	switch = None
	if other_available:
		code = text["lang_switch_code"]
		switch = {
			"label": text["lang_switch"],
			"short": text["lang_switch_short"],
			"url": switch_url or URLS["home"][code],
			"code": code,
		}
	login = ""
	if not hide_login:
		# Static: Frappe caches a page by path and language only, so the link cannot depend on who is signed in.
		login = (
			f'<a class="wk-button wk-button--secondary" href="{ACCOUNT_URL}" rel="nofollow">{esc(text["account"])}</a>'
		)
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
