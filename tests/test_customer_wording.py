"""The screens of the app are read by the owner of a site, not by a programmer: no technical names in what they see.

The few places where a technical name is needed (the Custom CSS rules, the advanced overrides) are listed here on purpose."""

import json
import re
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "website_kit"
SETTINGS = PKG / "website_kit/doctype/website_kit_settings"
RULES = json.loads((PKG / "public/js/wk_css_rules.json").read_text(encoding="utf-8"))["messages"]

# Words an owner must not meet in a label, a help text or a message.
TECHNICAL = (
	"X-Robots-Tag",
	"robots.txt",
	"noindex",
	"frappe_guard",
	"guard_mode",
	"site config",
	"Contact Us Settings",
	"wk-theme",
	"wk-safe",
	"/files/",
	"/assets/",
	"--wk-",
	"--cx-",
	"the Desk",
	"system UI",
	"style element",
	"this kit version",
	"new kit version",
	"token",
	"placeholder",
	"JSON",
	"Frappe",
	"Webshop markup",
	"hash",
)
# Field name -> the technical words its text may keep (an advanced field written for people who edit the format by hand).
ADVANCED_FIELDS = {"token_overrides": {"token"}}
# Validator message code -> the technical words it may keep (the CSS rules are written for people who write CSS).
CSS_MESSAGES = {
	"custom-property": {"--wk-", "--cx-"},
	"keyframes-name": set(),
}


def fields():
	for path in sorted((PKG / "website_kit/doctype").glob("*/*.json")):
		yield from json.loads(path.read_text(encoding="utf-8"))["fields"]


def found(text, allowed=frozenset()):
	return sorted(word for word in TECHNICAL if word.lower() in text.lower() and word not in allowed)


def test_labels_and_help_of_the_fields_have_no_technical_names():
	problems = []
	for field in fields():
		for key in ("label", "description"):
			text = field.get(key) or ""
			words = found(text, ADVANCED_FIELDS.get(field["fieldname"], set()) if key == "description" else set())
			if words:
				problems.append((field["fieldname"], key, words))
	assert problems == []


def test_the_internals_of_the_status_section_are_not_shown():
	hidden = {f["fieldname"] for f in fields() if f.get("hidden")}
	assert {"theme_hash", "theme_file_url", "safe_file_url", "pages_state"} <= hidden


def test_the_css_messages_have_no_technical_names_except_the_listed_ones():
	problems = {code: found(text, CSS_MESSAGES.get(code, set())) for code, text in RULES.items()}
	problems = {code: words for code, words in problems.items() if words}
	assert problems == {}


def test_the_rules_that_explain_a_variable_name_name_it():
	assert "--cx-" in RULES["custom-property"]
	assert "cx-" in RULES["keyframes-name"]


def test_the_help_of_the_settings_page_keeps_the_technical_part_in_a_collapsed_block():
	script = (SETTINGS / "website_kit_settings.js").read_text(encoding="utf-8")
	help_part = re.search(r"function render_css_help.*?\n\t}\n", script, re.S).group(0)
	main, _, advanced = help_part.partition("<details")
	assert advanced and "For advanced readers" in advanced
	for word in ("--wk-", "--cx-", "/files/", "/assets/", "Frappe and Webshop"):
		assert word in advanced
		assert word not in main
	assert "<details" in help_part and "open" not in help_part.split("<details")[1].split(">")[0]


def test_the_texts_of_the_buttons_and_messages_of_the_script_have_no_technical_names():
	script = (SETTINGS / "website_kit_settings.js").read_text(encoding="utf-8")
	strings = re.findall(r'__\(\s*"((?:[^"\\]|\\.)*)"', script)
	allowed = {"Allowed: @media"}  # the text of the collapsed advanced block
	problems = [(text, found(text)) for text in strings if found(text) and not any(text.startswith(a) for a in allowed)]
	assert problems == []
