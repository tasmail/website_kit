"""What the stock navbar emits besides the menu: stylesheet links, the file-uploader guard and the Webshop strings."""

import json
import re
import shutil
import subprocess
import textwrap

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
	assert (
		html.count("</script>") == 2 and "<b>" not in html
	)  # the closing tags of the two elements, nothing from the data


def test_the_strings_block_round_trips_as_json_and_fills_frappe_messages():
	messages = {"Add to Cart": "Додати в кошик", "{0} items found.": "Знайдено позицій: {0}."}
	html = stockpage.i18n(messages)
	body = re.search(r'<script type="application/json" id="wk-webshop-i18n">(.*?)</script>', html, re.S).group(1)
	assert json.loads(body) == messages
	assert "_messages" in html and "wk-webshop-i18n" in html
	assert stockpage.i18n({}) == ""


def test_the_guard_script_is_inline_and_small():
	html = stockpage.scripts(guard=True, messages={})
	assert html.startswith("<script>") and html.endswith("</script>") and len(html) < 1200


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
