"""Every user-visible string of the kit has a Ukrainian translation in translations/uk.csv."""

import csv
import json
import re
from pathlib import Path

from website_kit.theme import contrast

PKG = Path(__file__).resolve().parent.parent / "website_kit"
DOCTYPES = sorted((PKG / "website_kit/doctype").glob("*/*.json"))
RULES = PKG / "public/js/wk_css_rules.json"
UK = {row[0]: row[1] for row in csv.reader((PKG / "translations" / "uk.csv").open(encoding="utf-8"))}
CALL = re.compile(r"""\b_\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')\s*\)""")
JS_CALL = re.compile(r"""\b__\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')\s*\)""")


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
	assert sorted(needed - set(UK)) == []


def test_no_dead_rows():
	assert (
		sorted(set(UK) - (sources_in_code() | sources_in_doctype() | sources_in_data() | sources_of_stock_pages()))
		== []
	)


def test_every_stock_page_string_has_a_translation():
	assert sorted(sources_of_stock_pages() - set(UK)) == []


def test_translations_are_ukrainian_and_keep_placeholders():
	for source, target in UK.items():
		assert target.strip()
		assert re.findall(r"\{\d*\}", source) == re.findall(r"\{\d*\}", target), source
		if source not in {"Website Kit"}:
			assert re.search(r"[а-яіїєґА-ЯІЇЄҐ]", target), source


def test_the_extractor_finds_the_template_strings():
	found = sources_in_code()
	assert {"Skip to content", "Login", "My Account", "Main menu", "Home"} <= found
