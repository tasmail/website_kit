"""The shipped pages as data: deterministic, complete in both languages, themed only by tokens, with sound component instances."""

import json
import re

import pytest

from website_kit.pages import blocks, catalogue, content, header, specs

LANG_PAGES = [(spec["key"], spec["lang"]) for spec in specs.page_specs()]
TEXT_TAG = re.compile(r"<[^>]+>")
JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
LITERAL_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|\bhsla?\(")


def trees():
	for spec in specs.page_specs():
		yield spec["name"], json.loads(spec["fields"]["blocks"])
	for spec in specs.component_specs():
		yield spec["name"], json.loads(spec["fields"]["block"])


def test_the_two_languages_have_the_same_keys():
	assert content.TEXT["uk"].keys() == content.TEXT["en"].keys()


def test_every_text_key_is_used():
	package = specs.Path(specs.__file__).parent.parent
	source = "".join(path.read_text(encoding="utf-8") for path in package.rglob("*.py") if path.name != "content.py")
	built = re.compile(
		r"feature\d_(title|text)|(home|about|contact|privacy)_(title|description)"
	)  # keys made by f-strings
	for key in content.TEXT["uk"]:
		assert f'"{key}"' in source or f"'{key}'" in source or built.fullmatch(key), key


def test_the_build_is_deterministic():
	assert [s["hash"] for s in specs.all_specs()] == [s["hash"] for s in specs.all_specs()]
	assert json.dumps(specs.all_specs()) == json.dumps(specs.all_specs())


def test_every_page_exists_in_both_languages_with_distinct_routes():
	assert sorted(LANG_PAGES) == sorted((key, lang) for key in specs.PAGE_KEYS for lang in content.LANGUAGES)
	routes = [spec["fields"]["route"] for spec in specs.page_specs()]
	assert len(routes) == len(set(routes))
	assert {"home", "contact", "about", "en", "en/contact", "en/about"} <= set(routes)


def test_names_are_stable_and_unique():
	names = [spec["name"] for spec in specs.all_specs()]
	assert len(names) == len(set(names))
	assert "wk-home-uk" in names and "wk-contact-en" in names


def test_block_ids_are_unique_in_each_tree():
	for name, tree in trees():
		ids = [item["blockId"] for item in blocks.walk(tree)]
		assert len(ids) == len(set(ids)), name


def test_a_page_root_is_a_body():
	for spec in specs.page_specs():
		tree = json.loads(spec["fields"]["blocks"])
		assert len(tree) == 1 and tree[0]["originalElement"] == "body", spec["name"]


def test_pages_are_real_block_trees_not_one_html_block():
	for spec in specs.page_specs():
		tree = json.loads(spec["fields"]["blocks"])
		count = sum(1 for _ in blocks.walk(tree))
		raw_blocks = [item for item in blocks.walk(tree) if item.get("originalElement") == "__raw_html__"]
		assert count > 25, spec["name"]
		assert len(raw_blocks) < count / 3, spec["name"]


def test_no_literal_colour_anywhere():
	"""Colours are tokens, so a preset (the dark one too) restyles every page and every illustration."""
	for name, tree in trees():
		assert not LITERAL_COLOUR.search(blocks.dump(tree)), name


def test_styles_use_only_documented_properties():
	documented = set(
		re.findall(
			r"`(--wk-[a-z0-9-]+)`",
			(specs.Path(__file__).parent.parent / "docs" / "theming.md").read_text(encoding="utf-8"),
		)
	)
	for name, tree in trees():
		for custom in re.findall(r"var\((--[a-z0-9-]+)", blocks.dump(tree)):
			assert custom in documented, (name, custom)


def test_only_documented_classes_are_used():
	doc = (specs.Path(__file__).parent.parent / "docs" / "theming.md").read_text(encoding="utf-8")
	internal = re.compile(r"^wk-(header__|footer__|menu)")
	for name, tree in trees():
		for item in blocks.walk(tree):
			for class_name in item.get("classes") or []:
				assert f".{class_name}" in doc or internal.match(class_name), (name, class_name)


def test_text_is_plain_or_calls_a_kit_function():
	"""A block's text holds no script, no event handler and only the Jinja calls of the kit."""
	allowed = re.compile(r"\{\{ (wk_[a-z_]+)\('[a-z]+'(, '[a-z]+')?\) \}\}")
	for name, tree in trees():
		for item in blocks.walk(tree):
			html = item.get("innerHTML") or ""
			for expression in JINJA.findall(html):
				assert allowed.fullmatch(expression), (name, expression)
			assert "<script" not in html and not re.search(r"\son[a-z]+\s*=", html, flags=re.I), (name, html[:80])
			for value in (item.get("attributes") or {}).values():
				assert "{{" not in str(value) and "javascript:" not in str(value).lower()


def test_no_external_resource_in_any_block():
	"""Own illustrations only: no hotlink, no external image, no font or script from another origin."""
	for name, tree in trees():
		text = blocks.dump(tree)
		assert not re.search(r"https?://(?!www\.w3\.org/2000/svg)", text), name
		assert "//fonts." not in text and "fontFamily" not in text, name


def test_every_image_has_alt_text_or_is_decorative_svg():
	for name, tree in trees():
		for item in blocks.walk(tree):
			if item.get("element") == "img":
				assert "alt" in (item.get("attributes") or {}), name
			html = item.get("innerHTML") or ""
			if "<svg" in html:
				assert 'aria-hidden="true"' in html, name


def test_each_page_has_one_h1_and_a_main_landmark():
	for spec in specs.page_specs():
		tree = json.loads(spec["fields"]["blocks"])
		walked = list(blocks.walk(tree))
		assert [item.get("element") for item in walked].count("h1") == 1, spec["name"]
		mains = [item for item in walked if item.get("element") == "main"]
		assert len(mains) == 1 and mains[0]["customAttributes"]["id"] == "wk-main", spec["name"]
		skip = [item for item in walked if "wk-skip-link" in (item.get("classes") or [])]
		assert skip and skip[0]["attributes"]["href"] == "#wk-main"


def test_no_english_on_the_ukrainian_pages():
	"""All visible text of a Ukrainian page is Ukrainian: no Latin word is left once Jinja calls and markup are removed."""
	for spec in specs.page_specs() + specs.component_specs():
		if not spec["name"].endswith("-uk"):
			continue
		tree = json.loads(spec["fields"].get("blocks") or spec["fields"].get("block"))
		for item in blocks.walk(tree):
			html = item.get("innerHTML") or ""
			if item.get("originalElement") == "__raw_html__":
				continue
			visible = TEXT_TAG.sub(" ", JINJA.sub(" ", html)).replace("&copy;", "")
			# A language is named in its own language: the link to the English pages reads "English".
			assert not re.search(r"[A-Za-z]{2,}", visible.replace("English", "")), (spec["name"], visible)
		for value in content.TEXT["uk"].values():
			assert not re.search(r"\b(?:the|and|your|please|click|submit|send|name)\b", value, flags=re.I), value


def test_the_english_pages_have_no_cyrillic_text():
	for spec in specs.page_specs():
		if spec["lang"] == "en":
			assert not re.search(r"[А-Яа-яІіЇїЄєҐґ]", spec["fields"]["blocks"]), spec["name"]


def test_pages_point_at_each_other_in_both_languages():
	for key in specs.PAGE_KEYS:
		for lang in content.LANGUAGES:
			assert content.URLS[key][lang].startswith("/")
	for lang, other in (("uk", "en"), ("en", "uk")):
		html = header.inner(
			lang=lang,
			published={"home"},
			other_available=True,
			site_items=[],
			hide_login=False,
			brand_html="x",
			logo_url="",
		)
		assert f'href="{content.URLS["home"][other]}"' in html


def test_components_are_shared_by_all_pages():
	definitions = specs.component_definitions()
	assert set(definitions) == {f"{kind}-{lang}" for kind in specs.COMPONENT_KINDS for lang in content.LANGUAGES}
	for spec in specs.page_specs():
		tree = json.loads(spec["fields"]["blocks"])
		used = {item["extendedFromComponent"] for item in blocks.walk(tree) if item.get("extendedFromComponent")}
		assert {f"wk-header-{spec['lang']}", f"wk-footer-{spec['lang']}"} <= used, spec["name"]


def test_an_instance_mirrors_its_definition():
	definitions = specs.component_definitions()
	for spec in specs.page_specs():
		tree = json.loads(spec["fields"]["blocks"])
		for item in blocks.walk(tree):
			component = item.get("extendedFromComponent")
			if not component:
				continue
			defined = {block_item["blockId"] for block_item in blocks.walk(definitions[component])}
			refs = [ref for ref in blocks.walk(item["children"]) if ref.get("isChildOfComponent") == component]
			assert {ref["referenceBlockId"] for ref in refs} == defined - {definitions[component]["blockId"]}, spec[
				"name"
			]


def test_the_catalogue_strip_is_bound_to_data_and_hidden_when_empty():
	tree = json.loads(next(s for s in specs.page_specs() if s["name"] == "wk-home-uk")["fields"]["blocks"])
	strip = next(item for item in blocks.walk(tree) if item.get("blockName") == "catalogue")
	assert strip["visibilityCondition"] == {"key": "wk_has_products", "comesFrom": "dataScript"}
	repeater = next(item for item in blocks.walk(strip) if item.get("isRepeaterBlock"))
	assert repeater["dataKey"]["key"] == "wk_products" and len(repeater["children"]) == 1


def test_the_data_script_is_bounded_and_uses_only_the_safe_api():
	script = catalogue.DATA_SCRIPT
	compile(script, "data_script", "exec")
	assert f"limit={catalogue.LIMIT}" in script and catalogue.LIMIT <= 8
	assert script.count("frappe.db.get_all") == 1
	assert "import " not in script and not re.search(r"(?<![A-Za-z0-9])_[A-Za-z]", script)
	for forbidden in (
		"frappe.get_all",
		"frappe.get_list",
		"frappe.db.sql",
		"frappe.db.get_value",
		"frappe.utils",
		"__",
	):
		assert forbidden not in script, forbidden
	assert "wk_has_products" in script and "except Exception" in script


def test_the_catalogue_script_escapes_what_it_binds(tmp_path):
	"""Run the script with a stub: markup and braces in a product name never reach the page raw."""

	class Db:
		def exists(self, *_):
			return True

		def get_single_value(self, *_):
			return 1

		def get_all(self, *_, **__):
			return [
				{
					"web_item_name": "<b>{{ 7*7 }}</b>",
					"route": "shop/x",
					"website_image": "/files/a.png",
					"website_image_alt": 'a"b',
					"short_description": "<i>t</i>",
				},
				{"web_item_name": "Hidden", "route": "", "website_image": "", "short_description": ""},
			]

	class Frappe:
		db = Db()

	data = type("Data", (), {})()
	exec(catalogue.DATA_SCRIPT, {"frappe": Frappe(), "data": data})
	assert len(data.wk_products) == 1 and data.wk_has_products is True
	item = data.wk_products[0]
	assert "<" not in item["name"] and "{" not in item["name"] and "&#123;" in item["name"]
	assert item["url"] == "/shop/x" and item["has_image"] is True and "<" not in item["description"]
	assert '"' not in item["image_alt"]


def test_the_catalogue_script_renders_nothing_without_webshop():
	class Db:
		def exists(self, *_):
			return False

	class Frappe:
		db = Db()

	data = type("Data", (), {})()
	exec(catalogue.DATA_SCRIPT, {"frappe": Frappe(), "data": data})
	assert data.wk_products == [] and data.wk_has_products is False


def test_the_catalogue_script_swallows_a_database_error():
	class Db:
		def exists(self, *_):
			raise RuntimeError("boom")

	class Frappe:
		db = Db()

	data = type("Data", (), {})()
	exec(catalogue.DATA_SCRIPT, {"frappe": Frappe(), "data": data})
	assert data.wk_has_products is False


@pytest.mark.parametrize("key", ["home", "about", "contact", "privacy"])
def test_the_head_html_calls_the_kit_for_each_language(key):
	for spec in specs.page_specs():
		if spec["key"] == key:
			assert spec["fields"]["head_html"] == blocks.call("wk_head", spec["lang"], key)


def test_only_the_contact_pages_load_a_script_and_never_a_remote_one():
	for spec in specs.page_specs():
		assert spec["fields"]["client_scripts"] == ([specs.SCRIPT_NAME] if spec["key"] == "contact" else [])
	script = specs.script_text()
	assert not re.search(r"https?://", script)
	assert "FrappeGuard" in script and "data-wk-status" in script and "3000" in script and "website" in script


def test_the_contact_script_never_posts_without_the_guard():
	script = specs.script_text()
	assert "!window.FrappeGuard" in script
	assert "fetch(" not in script  # the only request goes through FrappeGuard.request


def test_the_privacy_page_is_closed_to_indexing_and_has_placeholders():
	for spec in specs.page_specs():
		if spec["key"] == "privacy":
			assert spec["fields"]["disable_indexing"] == 1
			text = spec["fields"]["blocks"]
			assert "wk_controller" in text
			assert "[" in content.TEXT[spec["lang"]]["privacy_placeholder_rights"]


def test_the_pages_that_depend_on_the_request_have_a_data_script():
	by_key = {spec["key"]: spec["fields"]["page_data_script"] for spec in specs.page_specs()}
	assert by_key["home"] == catalogue.DATA_SCRIPT and by_key["contact"] == catalogue.CONTACT_SCRIPT
	assert by_key["about"] == ""
	assert by_key["privacy"] == catalogue.CONTACT_SCRIPT  # uncached: its reCAPTCHA paragraph follows the guard state


def test_a_page_stays_small():
	"""The block JSON of a page is the main part of its weight: keep each tree well under the budget."""
	for spec in specs.page_specs():
		assert len(spec["fields"]["blocks"].encode()) < 20_000, spec["name"]


def test_instance_helper_applies_overrides():
	ids = blocks.Ids("t")
	definition = blocks.block(ids, "div", name="x", children=[blocks.block(ids, "span", html="a")])
	child = definition["children"][0]["blockId"]
	result = blocks.instance(blocks.Ids("p"), "comp", definition, overrides={child: {"innerHTML": "b"}})
	assert result["extendedFromComponent"] == "comp" and result["children"][0]["innerHTML"] == "b"
	assert result["children"][0]["referenceBlockId"] == child


def test_digest_depends_on_content_only():
	assert blocks.digest({"a": 1}) == blocks.digest({"a": 1}) != blocks.digest({"a": 2})
	assert blocks.clone({"a": [1]}) == {"a": [1]}
