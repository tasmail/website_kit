"""Every user-visible string of the kit has a Ukrainian translation in translations/uk.csv."""

import csv
import json
import re
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "website_kit"
DOCTYPE = PKG / "website_kit/doctype/website_kit_settings/website_kit_settings.json"
UK = {row[0]: row[1] for row in csv.reader((PKG / "translations" / "uk.csv").open(encoding="utf-8"))}
CALL = re.compile(r"""\b_\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')\s*\)""")


def sources_in_code():
	found = set()
	for path in [*PKG.rglob("*.py"), *PKG.rglob("*.html")]:
		if path.name.startswith("test_"):
			continue
		for double, single in CALL.findall(path.read_text(encoding="utf-8")):
			found.add((double or single).replace('\\"', '"').replace("\\'", "'"))
	return found


def sources_in_doctype():
	data = json.loads(DOCTYPE.read_text(encoding="utf-8"))
	found = {data["name"], data["module"]}
	for field in data["fields"]:
		found.add(field["label"])
		if field.get("description"):
			found.add(field["description"])
	return found  # the Select options are the preset names, which stay as the product names


def test_every_string_is_translated():
	needed = sources_in_code() | sources_in_doctype()
	assert needed, "no strings found"
	assert sorted(needed - set(UK)) == []


def test_no_dead_rows():
	assert sorted(set(UK) - (sources_in_code() | sources_in_doctype())) == []


def test_translations_are_ukrainian_and_keep_placeholders():
	for source, target in UK.items():
		assert target.strip()
		assert re.findall(r"\{\d*\}", source) == re.findall(r"\{\d*\}", target), source
		if source not in {"Website Kit"}:
			assert re.search(r"[а-яіїєґА-ЯІЇЄҐ]", target), source


def test_the_extractor_finds_the_template_strings():
	found = sources_in_code()
	assert {"Skip to content", "Login", "My Account", "Main menu", "Home"} <= found
