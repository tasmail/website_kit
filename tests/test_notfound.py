"""The not-found page: Builder replaces Frappe's 404 template and drops its navbar and footer, so the kit ships its own page."""

import json
import re

import pytest

from website_kit.pages import blocks, content, footer, specs


def spec():
	return next(item for item in specs.all_specs() if item["name"] == specs.NOTFOUND_NAME)


def test_the_page_is_shipped_after_the_components_with_the_route_builder_looks_up():
	names = [item["name"] for item in specs.all_specs()]
	assert names.index(specs.NOTFOUND_NAME) > max(i for i, n in enumerate(names) if n.startswith("wk-header-"))
	fields = spec()["fields"]
	assert fields["route"] == "404" and fields["published"] == 1 and fields["disable_indexing"] == 1
	assert spec()["kind"] == "Builder Page"


def test_it_has_the_shared_header_and_a_footer_in_the_request_language_and_no_literal_text():
	tree = json.loads(spec()["fields"]["blocks"])
	text = json.dumps(tree, ensure_ascii=False)
	assert blocks.call("wk_header", "") in text and blocks.call("wk_footer", "") in text
	assert not re.search(r"[А-Яа-яІіЇїЄєҐґ]", text)  # every word comes from `wk_text`, in the language of the request
	for key in ("notfound_title", "notfound_lead", "notfound_home", "skip"):
		assert blocks.call("wk_text", key) in text, key
	tags = [item["element"] for item in blocks.walk(tree)]
	assert {"header", "main", "footer"} <= set(tags)


def test_the_texts_exist_in_both_languages_and_the_head_is_the_kit_head():
	for lang in content.LANGUAGES:
		for key in ("notfound_title", "notfound_lead", "notfound_home"):
			assert content.TEXT[lang][key].strip(), (lang, key)
	assert spec()["fields"]["head_html"] == blocks.call("wk_head", "uk", "notfound")


@pytest.mark.parametrize("lang", content.LANGUAGES)
def test_the_footer_function_lists_the_four_links_the_contacts_and_the_brand(lang):
	t = content.TEXT[lang]
	html = footer.inner(lang=lang, brand_html="Shop &amp; Co", facts_html="<ul><li>x</li></ul>")
	hrefs = re.findall(r'<a href="([^"]+)">([^<]+)</a>', html)
	assert hrefs == [
		(content.URLS["home"][lang], t["menu_home"]),
		(content.URLS["about"][lang], t["menu_about"]),
		(content.URLS["contact"][lang], t["menu_contact"]),
		(content.URLS["privacy"][lang], t["footer_privacy"]),
	]
	assert "<ul><li>x</li></ul>" in html and "&copy; Shop &amp; Co" in html
	assert html.startswith('<div class="wk-container wk-footer__inner">')
