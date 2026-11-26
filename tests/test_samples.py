"""Sample products, their drawings and the shop menu rule (pure parts)."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from website_kit import samples, shop_menu

ROOT = Path(__file__).resolve().parent.parent
KINDS = {entry[1] for entry in samples.ITEMS}


def test_there_are_ten_distinct_items_with_both_languages():
	assert len(samples.ITEMS) == 10
	assert len({entry[0] for entry in samples.ITEMS}) == 10
	assert len({samples.item_code(entry[0]) for entry in samples.ITEMS}) == 10
	for entry in samples.ITEMS:
		assert set(entry[6]) == {"en", "uk"} and entry[5] > 0
		assert re.search(r"[а-яіїє]", entry[6]["uk"][0], re.I)


def test_text_follows_the_language_with_english_fallback():
	entry = samples.ITEMS[0]
	assert samples.text_for(entry, "uk") == entry[6]["uk"]
	assert samples.text_for(entry, "uk-UA") == entry[6]["uk"]
	assert samples.text_for(entry, "de") == entry[6]["en"]
	assert samples.text_for(entry, "") == entry[6]["en"]


@pytest.mark.parametrize("entry", samples.ITEMS, ids=[e[0] for e in samples.ITEMS])
def test_every_drawing_is_a_small_self_contained_svg(entry):
	svg = samples.svg_for(entry, "en")
	root = ET.fromstring(svg)  # well-formed
	assert root.tag.endswith("svg")
	assert len(svg.encode()) < 2500
	for forbidden in ("http://", "https://", "<script", "<image", "href", "xlink", "url(", "@import", "javascript:"):
		assert forbidden not in svg.replace('xmlns="http://www.w3.org/2000/svg"', ""), forbidden
	assert "<title>" in svg


def test_drawings_differ_and_the_label_is_escaped():
	assert len({samples.svg_for(entry) for entry in samples.ITEMS}) == 10
	assert "&lt;b&gt;" in samples.illustration("mug", "#fff", "#000", "#ccc", "<b>")
	assert "<title>" not in samples.illustration("mug", "#fff", "#000", "#ccc")
	assert {entry[1] for entry in samples.ITEMS} == KINDS and len(KINDS) == 10


def test_file_names_share_one_prefix():
	assert all(samples.file_name(entry[0]).startswith(samples.FILE_PREFIX) for entry in samples.ITEMS)


def test_the_menu_hides_only_the_shop_entry_while_the_shop_is_empty():
	items = [
		{"label": "Home", "url": "/"},
		{"label": "Shop", "url": "/all-products"},
		{"label": "About", "url": "/about"},
	]
	assert [i["label"] for i in shop_menu.visible_items(items, False)] == ["Home", "About"]
	assert shop_menu.visible_items(items, True) == items
	assert shop_menu.visible_items(None, False) == []
	assert shop_menu.is_shop_entry({"url": "/all-products/"})
	assert shop_menu.is_shop_entry(type("Row", (), {"url": "/all-products"})())
	assert not shop_menu.is_shop_entry({"url": "/products"}) and not shop_menu.is_shop_entry({})


def test_the_shop_entry_is_matched_by_path_whatever_the_spelling():
	for url in (
		"/all-products",
		"/all-products/",
		"all-products",
		"/All-Products?x=1",
		"https://shop.example.com/all-products#top",
		"/uk/all-products",
	):
		assert shop_menu.is_shop_entry({"url": url}), url
	assert shop_menu.is_shop_entry({"route": "all-products"})
	for url in ("/all-products-old", "/products", "https://all-products.example.com/", ""):
		assert not shop_menu.is_shop_entry({"url": url}), url


def test_the_shop_stylesheet_is_scoped_to_the_shop_pages():
	"""Every rule is under the body class `wk-shop`, which the kit adds only on the Webshop pages, so no other page is restyled."""
	css = (ROOT / "website_kit/public/css/wk-shop.css").read_text(encoding="utf-8")
	body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
	selectors = [s.strip() for block in re.findall(r"([^{}]+)\{", body) for s in block.split(",")]
	assert selectors and all(s.startswith((".wk-shop ", "body.wk-shop")) for s in selectors), selectors
	assert "url(" not in body and "@import" not in body and "@font-face" not in body
	# the main job is to point Frappe's design variables at the kit tokens, so inline `var(--gray-800)` in Webshop's markup follows the preset
	for variable in ("--text-color", "--gray-800", "--border-color", "--bg-color", "--primary"):
		assert re.search(rf"{variable}:\s*var\(--wk-", body), variable
