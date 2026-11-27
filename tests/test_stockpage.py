"""What the stock navbar emits besides the menu: stylesheet links, the file-uploader guard and the Webshop strings."""

import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from website_kit import stockpage


def test_links_are_the_base_sheet_the_theme_file_and_the_shop_sheet_in_that_order():
	html = stockpage.links(
		"/assets/website_kit/css/wk.css?v=1", "/files/wk-theme.css?v=abc", "/assets/website_kit/css/wk-shop.css?v=1"
	)
	hrefs = re.findall(r'<link rel="stylesheet" href="([^"]+)">', html)
	assert hrefs == [
		"/assets/website_kit/css/wk.css?v=1",
		"/files/wk-theme.css?v=abc",
		"/assets/website_kit/css/wk-shop.css?v=1",
	]


def test_links_skip_what_is_empty_and_escape_what_they_write():
	assert stockpage.links("/assets/website_kit/css/wk.css?v=1", "", "") == (
		'<link rel="stylesheet" href="/assets/website_kit/css/wk.css?v=1">'
	)
	assert '"><script>' not in stockpage.links("/a.css", '/x.css"><script>', "")


def test_the_guard_and_the_strings_hold_no_template_syntax_and_cannot_close_their_element():
	for text in (stockpage.GUARD_SCRIPT, stockpage.i18n({"a {{ 7*7 }}": "b {% x %} </script> {#"})):
		assert "{{" not in text and "{%" not in text and "{#" not in text
	html = stockpage.i18n({"x": "</script><b>"})
	assert html.count("</script>") == 1 and "<b>" not in html  # only its own closing tag, nothing from the data


def test_the_strings_round_trip_as_a_json_literal_inside_one_plain_script():
	"""Frappe drops the attributes of every script tag of a web template, so there is no `type="application/json"` block."""
	messages = {"Add to Cart": "Додати в кошик", "{0} items found.": "Знайдено: {0}.", "a</b>&c": "x"}
	html = stockpage.i18n(messages)
	assert html.startswith("<script>") and html.count("<script") == 1 and "type=" not in html
	body = re.search(r"Object\.assign\(f\._messages \|\| \{\}, (.*)\); \}\)\(window\.frappe\)", html, re.S).group(1)
	assert json.loads(body) == messages
	assert stockpage.i18n({}) == ""


def test_the_guard_script_is_inline_and_small():
	html = stockpage.scripts(guard=True, messages={})
	assert html.startswith("<script>") and html.endswith("</script>") and len(html) < 1200
	assert stockpage.scripts(guard=False, messages={}) == ""


def run_node(body):
	node = shutil.which("node")
	if not node:
		pytest.skip("node is not installed")
	code = textwrap.dedent(
		"""
		globalThis.window = globalThis;
		const frappe = (globalThis.frappe = {});
		const calls = [];
		%s
		"""
	) % (stockpage.GUARD_SCRIPT + ";\n" + body)
	out = subprocess.run([node, "-e", code], capture_output=True, text=True, check=True, timeout=20).stdout
	return json.loads(out)


def test_the_guard_skips_only_the_file_uploader_require_while_assets_json_is_missing():
	result = run_node(
		"""
		// what Frappe's website.js does: $.extend(frappe, {require: ...}) after the guard was installed
		frappe.require = async function (links) { calls.push(links); };
		(async () => {
			await frappe.require("file_uploader.bundle.js");        // no frappe.boot: skipped
			await frappe.require("other.bundle.js");                // passes through
			frappe.boot = {assets_json: {}};
			await frappe.require("file_uploader.bundle.js");        // assets are known: passes through
			console.log(JSON.stringify(calls));
		})();
		"""
	)
	assert result == ["other.bundle.js", "file_uploader.bundle.js"]


def test_the_shop_context_wins_and_untranslated_strings_are_left_out():
	table = {("Submit", stockpage.CONTEXT): "Надіслати", ("Add to Cart", None): "Додати в кошик"}

	def translate(text, context):
		return table.get((text, context)) or table.get((text, None)) or text

	found = stockpage.translated(translate)
	assert found["Submit"] == "Надіслати" and "Add to Cart" in found
	assert "Prev" not in found or found["Prev"] != "Prev"
	assert all(source != text for source, text in found.items())


@pytest.mark.parametrize("route", ["login", "/login", "login/", "update-password", "error", "shop-by-category"])
def test_the_pages_that_replace_the_head_block_get_their_links_from_the_navbar(route):
	assert stockpage.replaces_head(route)


@pytest.mark.parametrize("route", ["", None, "about", "all-products", "cart", "wk-cache-probe", "login-help", "me"])
def test_every_other_page_gets_the_links_from_head_include_only(route):
	"""Both places would link every sheet twice (page weight, and the cache probe of CI counts the links)."""
	assert not stockpage.replaces_head(route)


def test_the_runtime_hands_the_navbar_links_only_where_the_head_is_replaced_and_always_the_guard():
	source = (Path(__file__).resolve().parent.parent / "website_kit/runtime.py").read_text(encoding="utf-8")
	assert "stockpage.replaces_head(" in source
	assert re.search(r"stockpage\.scripts\(\s*guard=True,", source), (
		"the file-uploader guard must be on for every stock page"
	)


def test_a_stock_page_keeps_the_language_it_was_asked_for_in_the_cookie():
	html = stockpage.scripts(guard=True, messages={})
	assert "_lang=(uk|en)" in html and "preferred_language=" in html and html.count("<script") == 1
	assert "preferred_language" not in stockpage.scripts(guard=False, messages={})
	assert len(html) < 1200
