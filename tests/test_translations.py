"""Every user-visible string of the kit has a Ukrainian translation in translations/uk.csv."""

import csv
import json
import re
from pathlib import Path

from website_kit import stockpage
from website_kit.theme import contrast

PKG = Path(__file__).resolve().parent.parent / "website_kit"
DOCTYPES = sorted((PKG / "website_kit/doctype").glob("*/*.json"))
RULES = PKG / "public/js/wk_css_rules.json"
ROWS = list(csv.reader((PKG / "translations" / "uk.csv").open(encoding="utf-8")))
UK = {row[0]: row[1] for row in ROWS}
# What Frappe, ERPNext and Payments already translate (a pinned snapshot; the bench test compares with the installed apps).
EXISTING = json.loads((Path(__file__).resolve().parent / "existing_uk_snapshot.json").read_text(encoding="utf-8"))[
	"translations"
]
CALL = re.compile(r"""\b_\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')\s*\)""")
JS_CALL = re.compile(r"""\b__\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')\s*(?:,[^()]*)?\)""")


def sources_in_code():
	found = set()
	for path in [*PKG.rglob("*.py"), *PKG.rglob("*.html")]:
		if path.name.startswith("test_"):
			continue
		for double, single in CALL.findall(path.read_text(encoding="utf-8")):
			found.add((double or single).replace('\\"', '"').replace("\\'", "'"))
	for path in PKG.rglob("*.js"):
		for double, single in JS_CALL.findall(path.read_text(encoding="utf-8")):
			found.add((double or single).replace('\\"', '"').replace("\\'", "'"))
	return found


def sources_of_stock_pages():
	"""Strings of the stock Webshop pages that the kit translates on purpose (Webshop ships no Ukrainian)."""
	lines = (PKG / "translations" / "webshop_sources.txt").read_text(encoding="utf-8").splitlines()
	return {line for line in lines if line and not line.startswith("#")}


def sources_of_webshop_scripts():
	"""Strings that Webshop's browser scripts translate; the kit hands them to the page (stockpage.js_sources)."""
	lines = (PKG / "translations" / "webshop_js_sources.txt").read_text(encoding="utf-8").splitlines()
	return {line for line in lines if line and not line.startswith("#")}


def sources_in_data():
	"""Strings that live in data files: the validator messages, the preset names and texts, the contrast pair labels."""
	found = set(json.loads(RULES.read_text(encoding="utf-8"))["messages"].values())
	for path in (PKG / "theme" / "presets").glob("*.json"):
		data = json.loads(path.read_text(encoding="utf-8"))
		found |= {data["label"], data["description"]}
	found |= {label for label, *_ in contrast.PAIRS}
	return found


def sources_in_doctype():
	found = set()
	for doctype in DOCTYPES:
		data = json.loads(doctype.read_text(encoding="utf-8"))
		found |= {data["name"], data["module"]}
		for field in data["fields"]:
			found.add(field["label"])
			if field.get("description"):
				found.add(field["description"])
	return found  # the Select options are the preset names, which stay as the product names


def test_every_string_is_translated():
	needed = sources_in_code() | sources_in_doctype() | sources_in_data()
	assert needed, "no strings found"
	# A string that Frappe or ERPNext already translate needs no row of ours (and must not get a different one, see below).
	assert sorted(needed - set(UK) - set(EXISTING)) == []


def test_no_dead_rows():
	assert (
		sorted(
			set(UK)
			- (
				sources_in_code()
				| sources_in_doctype()
				| sources_in_data()
				| sources_of_stock_pages()
				| sources_of_webshop_scripts()
			)
		)
		== []
	)


def test_every_stock_page_string_has_a_translation():
	assert sorted(sources_of_stock_pages() - set(UK)) == []


def test_every_webshop_script_string_has_a_translation():
	"""The browser scripts of the shop pages are Webshop's; Frappe loads no translations there, so the kit supplies them all."""
	assert sorted(sources_of_webshop_scripts() - set(UK) - set(EXISTING)) == []


def test_translations_are_ukrainian_and_keep_placeholders():
	for source, target in UK.items():
		assert target.strip()
		assert re.findall(r"\{\d*\}", source) == re.findall(r"\{\d*\}", target), source
		if source not in {"Website Kit"}:
			assert re.search(r"[а-яіїєґА-ЯІЇЄҐ]", target), source


def test_the_extractor_finds_the_template_strings():
	found = sources_in_code()
	assert {"Skip to content"} <= found


def test_no_row_overrides_an_existing_translation_site_wide():
	"""The kit's uk.csv is merged last, so a row without a context replaces Frappe's or ERPNext's translation of the same source on
	the whole site, the Desk included ("Item" is "Номенклатура" in ERPNext). A kit-only wording needs a context (third column)."""
	rows = [row for row in ROWS if len(row) < 3 or not row[2]]
	overrides = [
		(row[0], row[1], EXISTING[row[0]]) for row in rows if row[0] in EXISTING and EXISTING[row[0]] != row[1]
	]
	assert overrides == []


def test_context_rows_are_the_kits_own_wordings_only():
	assert sorted((row[2], row[0]) for row in ROWS if len(row) > 2 and row[2]) == [
		("Webshop page", "Email"),
		("Webshop page", "Full Name"),
		("Webshop page", "Message"),
		("Webshop page", "Send"),
		("Webshop page", "Submit"),
		("Website Kit theme", "Borders"),
		("Website Kit theme", "Clear"),
		("Website Kit theme", "Custom"),
		("Website Kit theme", "Ledger"),
		("Website Kit theme", "Secondary"),
	]


def test_the_snapshot_only_holds_what_the_kit_uses():
	known = (
		sources_in_code()
		| sources_in_doctype()
		| sources_in_data()
		| sources_of_stock_pages()
		| sources_of_webshop_scripts()
		| set(UK)
	)
	assert set(EXISTING) <= known


SETTINGS_JS = PKG / "website_kit/doctype/website_kit_settings/website_kit_settings.js"
CONTEXT_CALL = re.compile(r"""__\(\s*"((?:[^"\\]|\\.)*)"\s*,\s*null\s*,\s*(THEME_CONTEXT|"[^"]+")\s*\)""")


def contexts_used_in_the_script():
	"""`(direct, presets)`: the `{(source, context)}` of the `__("text", null, CONTEXT)` calls of the settings script, and the same
	pairs for the preset labels that the script translates through `__(preset.label, null, THEME_CONTEXT)`."""
	script = SETTINGS_JS.read_text(encoding="utf-8")
	theme = re.search(r'const THEME_CONTEXT = "([^"]+)"', script).group(1)
	direct = {
		(source, theme if context == "THEME_CONTEXT" else context.strip('"'))
		for source, context in CONTEXT_CALL.findall(script)
	}
	presets = set()
	if re.search(r"__\(\s*preset\.label\s*,\s*null\s*,\s*THEME_CONTEXT\s*\)", script):
		for path in (PKG / "theme" / "presets").glob("*.json"):
			presets.add((json.loads(path.read_text(encoding="utf-8"))["label"], theme))
	return direct, presets


def test_every_context_row_is_asked_for_with_that_context_and_the_other_way_round():
	"""A row with a context is found only by a call that passes the same context, so a row nobody asks for is dead, and a call with
	a context but no row silently falls back to the English text. (A preset name without a row stays as the product name.)"""
	rows = {(row[0], row[2]) for row in ROWS if len(row) > 2 and row[2]}
	direct, presets = contexts_used_in_the_script()
	# The `Webshop page` rows are asked for by the server (stockpage.translated), for the strings of Webshop's scripts.
	shop = {(source, stockpage.CONTEXT) for source in sources_of_webshop_scripts()}
	assert {row for row in rows if row[1] == stockpage.CONTEXT} <= shop
	rows = {row for row in rows if row[1] != stockpage.CONTEXT}
	assert sorted(rows - (direct | presets)) == []
	assert sorted(direct - rows) == []
	assert direct, "the extractor found no context call"
