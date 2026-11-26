"""The one header of the site: the same markup on Builder pages and on stock pages (login, shop, 404)."""

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from jinja2 import Environment

from website_kit.pages import blocks, content, header, sections

PKG = Path(__file__).resolve().parent.parent / "website_kit"
NAVBAR = (PKG / "website_kit/web_template/wk_navbar/wk_navbar.html").read_text(encoding="utf-8")
ALL_PAGES = {"home", "about", "contact"}


def build(lang="uk", published=ALL_PAGES, other=True, site_items=(), logged_in=False, hide_login=False, logo_url=""):
	return header.inner(
		lang=lang,
		published=published,
		other_available=other,
		site_items=list(site_items),
		logged_in=logged_in,
		hide_login=hide_login,
		brand_html="Shop &amp; Co",
		logo_url=logo_url,
	)


class Links(HTMLParser):
	"""The links of every `<nav>` of the header, in document order."""

	def __init__(self, html):
		super().__init__()
		self.navs, self.current, self.href = [], None, None
		self.feed(html)

	def handle_starttag(self, tag, attrs):
		attrs = dict(attrs)
		if tag == "nav":
			self.current = []
			self.navs.append((attrs, self.current))
		elif tag == "a" and self.current is not None:
			self.href = attrs.get("href")
			self.current.append([attrs.get("href"), ""])

	def handle_data(self, data):
		if self.href is not None and self.current:
			self.current[-1][1] += data

	def handle_endtag(self, tag):
		if tag == "nav":
			self.current = None
		if tag == "a":
			self.href = None


def labels(html, which=0):
	return [(href, text.strip()) for href, text in Links(html).navs[which][1]]


@pytest.mark.parametrize("lang", content.LANGUAGES)
def test_kit_pages_come_first_then_the_other_language_then_login(lang):
	t = content.TEXT[lang]
	other = t["lang_switch_code"]
	got = labels(build(lang))
	assert got == [
		(content.URLS["home"][lang], t["menu_home"]),
		(content.URLS["about"][lang], t["menu_about"]),
		(content.URLS["contact"][lang], t["menu_contact"]),
		(content.URLS["home"][other], t["lang_switch"]),
		("/login", t["login"]),
	]


def test_site_items_sit_between_the_kit_pages_and_the_language_switch():
	html = build("en", site_items=[{"label": "Shop", "url": "/all-products"}])
	assert [text for _, text in labels(html)] == ["Home", "About", "Contact", "Shop", "Українська", "Log in"]


def test_a_site_item_that_repeats_a_kit_page_is_dropped():
	items = [
		{"label": "Home", "url": "/"},
		{"label": "Contact us", "url": "/contact/"},
		{"label": "Blog", "url": "/blog"},
	]
	got = [text for _, text in labels(build("uk", site_items=items))]
	assert got.count("Home") == 0 and "Contact us" not in got and "Blog" in got


def test_a_page_that_is_not_published_is_not_linked():
	got = [href for href, _ in labels(build("uk", published={"home"}))]
	assert content.URLS["about"]["uk"] not in got and content.URLS["contact"]["uk"] not in got
	assert content.URLS["home"]["uk"] in got


def test_the_language_switch_needs_the_other_home_page():
	assert content.URLS["home"]["en"] not in [href for href, _ in labels(build("uk", other=False))]


def test_login_becomes_the_account_link_for_a_signed_in_user_and_can_be_hidden():
	t = content.TEXT["uk"]
	assert labels(build("uk", logged_in=True))[-1] == ("/me", t["account"])
	assert "/login" not in [href for href, _ in labels(build("uk", hide_login=True))]
	assert "/me" not in [href for href, _ in labels(build("uk", hide_login=True, logged_in=True))]


def test_children_of_a_site_item_are_a_details_group():
	items = [{"label": "More", "url": "", "children": [{"label": "Docs", "url": "/docs"}]}]
	html = build("en", site_items=items)
	assert '<details class="wk-menu__group">' in html and "<summary" in html
	assert ("/docs", "Docs") in labels(html)


def test_external_items_open_in_a_new_tab_safely():
	html = build("en", site_items=[{"label": "Out", "url": "https://example.com/x", "new_tab": True}])
	assert re.search(r'href="https://example.com/x" target="_blank" rel="noopener"', html)


def test_site_data_is_escaped_and_braces_encoded():
	html = build("en", site_items=[{"label": "<b>{{ 7*7 }}</b>", "url": "/x?a=1&b=2"}])
	assert "<b>" not in html and "{{" not in html and "&#123;&#123;" in html and "a=1&amp;b=2" in html
	assert "<script>" not in build("en", site_items=[{"label": "x", "url": '/x"><script>'}])


def test_a_javascript_url_is_not_linked():
	html = build("en", site_items=[{"label": "Bad", "url": "javascript:alert(1)"}])
	assert "javascript:" not in html


def test_the_brand_links_home_and_a_logo_replaces_the_name():
	assert 'class="wk-header__brand" href="/"' in build("uk")
	html = build("uk", logo_url="/files/logo.png")
	assert '<img class="wk-header__logo" src="/files/logo.png"' in html


# --- the narrow-screen disclosure: native details/summary, no checkbox, no script ---------------------------------


def test_the_burger_is_a_native_disclosure_with_a_name():
	html = build("uk")
	assert re.search(r'<details class="wk-header__menu">\s*<summary class="wk-header__burger" aria-label="Меню">', html)
	assert "<input" not in html and "<label" not in html and "<script" not in html


def test_the_menu_exists_twice_with_the_same_links_one_for_each_width():
	navs = Links(build("uk")).navs
	assert len(navs) == 2
	assert navs[0][1] == navs[1][1]
	classes = [attrs.get("class") for attrs, _ in navs]
	assert any("wk-header__nav--wide" in c for c in classes) and any("wk-header__nav--narrow" in c for c in classes)
	assert all(attrs.get("aria-label") == content.TEXT["uk"]["menu_label"] for attrs, _ in navs)


def test_the_disclosure_comes_before_the_wide_nav_and_both_are_inside_the_inner_wrapper():
	html = build("en")
	assert html.startswith('<div class="wk-container wk-header__inner">')
	assert html.index("<details") < html.index("wk-header__nav--wide")


# --- Builder and stock pages share the function -------------------------------------------------------------------


@pytest.mark.parametrize("lang", content.LANGUAGES)
def test_the_builder_header_is_a_raw_call_of_the_shared_function(lang):
	tree = json.dumps(sections.header_definition(lang), ensure_ascii=False)
	assert blocks.call("wk_header", lang) in tree
	assert "wk-menu" not in tree  # the markup is not copied into the page tree


def _render_navbar(**context):
	env = Environment()
	env.filters.update(wk_esc=lambda value: value, abs_url=lambda value: value)
	env.globals.update(_=lambda text: text, wk_header=lambda *a, **k: "<!--INNER-->")
	values = {"wk": {"brand_name": "B", "links": "<!--LINKS-->", "scripts": "<!--SCRIPTS-->"}, "top_bar_items": []}
	values.update(context)
	return env.from_string(NAVBAR).render(**values)


def test_the_stock_navbar_calls_the_same_function_and_adds_no_menu_of_its_own():
	html = _render_navbar()
	assert "<!--INNER-->" in html and "wk-menu" not in html and "<nav" not in html and "<input" not in html
	assert '<header class="wk-header">' in html and 'id="wk-main"' in html


def test_the_stock_navbar_emits_the_stylesheets_and_scripts_itself():
	"""Frappe's login page replaces the whole head_include block, so the links must travel with the navbar."""
	html = _render_navbar()
	assert html.index("<!--LINKS-->") < html.index("<header") and "<!--SCRIPTS-->" in html


def test_the_stock_navbar_still_renders_when_the_context_has_no_links_or_scripts():
	"""A template render without the kit's context (a test, a preview) must not print Jinja's error text into the page."""
	html = _render_navbar(wk={"brand_name": "B"})
	assert "no such element" not in html and "<header" in html
