"""The data behind the theme settings page, the `custom` preset and Custom CSS in the compile path."""

import json

import pytest

from website_kit import css_validator
from website_kit.theme import compiler, editor, presets, tokens

CSS = ".wk-card { color: #111; }"


def test_custom_css_comes_after_the_tokens_and_changes_the_hash():
	plain, plain_hash = compiler.build("clear")
	css, digest = compiler.build("clear", "", CSS)
	assert css.startswith(plain.rstrip("\n"))
	assert css.rstrip().endswith(CSS)
	assert css.index(compiler.CUSTOM_MARKER) > css.index("[data-wk-button")
	assert digest != plain_hash
	assert compiler.build("clear", "", "   \n") == (plain, plain_hash)


def test_invalid_custom_css_never_compiles():
	with pytest.raises(compiler.CustomCssError) as caught:
		compiler.build("clear", "", "a { b: c }\n@import 'x';")
	assert "2:1" in str(caught.value)
	assert [m.code for m in caught.value.result.errors] == ["property-not-allowed", "at-rule-not-allowed"]


def test_custom_preset_starts_from_its_base():
	base = presets.load("night")
	resolved = presets.resolve("custom", {"tokens": {"color-primary": "#112233"}, "variants": {}}, "night")
	assert resolved["preset"] == "custom"
	assert resolved["tokens"]["color-bg"] == base["tokens"]["color-bg"]
	assert resolved["tokens"]["color-primary"] == "#112233"
	assert presets.resolve("custom")["tokens"] == presets.load("clear")["tokens"]
	with pytest.raises(tokens.TokenError):
		presets.resolve("custom", None, "custom")
	with pytest.raises(tokens.TokenError):
		presets.resolve("custom", None, "nope")
	assert presets.CUSTOM in presets.CHOICES and set(presets.PRESET_NAMES) < set(presets.CHOICES)


def test_duplicate_as_custom_freezes_every_token():
	values = editor.duplicate_as_custom("market", '{"tokens": {"color-primary": "#112233"}}')
	assert values["preset"] == "custom" and values["custom_base"] == "market"
	stored = json.loads(values["token_overrides"])
	assert set(stored["tokens"]) == set(tokens.TOKENS) and set(stored["variants"]) == set(tokens.VARIANTS)
	assert stored["tokens"]["color-primary"] == "#112233"
	# the frozen copy compiles to the same CSS as the preset with that override
	assert (
		compiler.build("custom", values["token_overrides"], "", "market")[0].replace("preset custom", "preset market")
		== compiler.build("market", '{"tokens": {"color-primary": "#112233"}}')[0]
	)
	again = editor.duplicate_as_custom("custom", values["token_overrides"], "market")
	assert again["custom_base"] == "market"
	with pytest.raises(tokens.TokenError):
		editor.duplicate_as_custom("clear", '{"tokens": {"color-primary": "red"}}')


def test_preview_returns_css_contrast_and_messages():
	data = editor.preview("clear", "", CSS)
	assert data["ok"] and data["css"].rstrip().endswith(CSS) and len(data["hash"]) == 16
	assert data["contrast"] and all(check["passed"] for check in data["contrast"])
	assert data["errors"] == [] and data["token_error"] == ""


def test_preview_reports_low_contrast_of_a_custom_colour():
	overrides = json.dumps({"tokens": {"color-text": "#cccccc"}})
	data = editor.preview("custom", overrides, "", "clear")
	failed = [check for check in data["contrast"] if not check["passed"]]
	assert {"text on background", "text on surface"} <= {check["label"] for check in failed}
	assert data["css"]


def test_preview_with_the_enhanced_preset_asks_for_seven_to_one():
	data = editor.preview("contrast")
	assert {check["minimum"] for check in data["contrast"]} == {7.0}
	assert {check["minimum"] for check in editor.preview("custom", "", "", "contrast")["contrast"]} == {7.0}
	assert {check["minimum"] for check in editor.preview("clear")["contrast"]} == {4.5, 3.0}


def test_preview_never_raises_for_bad_input():
	bad_token = editor.preview("clear", '{"tokens": {"color-primary": "red"}}')
	assert bad_token["token_error"] and bad_token["css"] == "" and bad_token["contrast"] == []
	bad_css = editor.preview("clear", "", "a { behavior: x }")
	assert not bad_css["ok"] and bad_css["css"] == "" and bad_css["errors"][0]["line"] == 1
	assert editor.preview("nope")["token_error"]


def test_translated_messages_use_the_translation_of_the_template():
	translated = editor.preview(
		"clear", "", "a { behavior: x }", translate=lambda text: text.replace("not allowed", "FORBIDDEN")
	)
	assert translated["errors"][0]["message"] == "The property 'behavior' is FORBIDDEN."


def test_theme_data_is_plain_json():
	data = editor.theme_data()
	json.dumps(data)
	assert [p["name"] for p in data["presets"]] == list(presets.PRESET_NAMES)
	assert {f["slug"] for f in data["fonts"]} >= {"system", "inter", "roboto"}
	assert data["meta"]["types"]["color-bg"] == "color"
	assert data["limits"]["max_bytes"] == 32768
	assert next(p for p in data["presets"] if p["name"] == "contrast")["enhanced"] is True
	assert set(data["radius_choices"]) == {"none", "small", "medium", "large"}
	assert set(data["density_choices"]) == {"compact", "comfortable", "spacious"}


def test_editor_choices_are_valid_token_values():
	slugs = {f["slug"] for f in editor.fonts_payload()}
	for values in editor.RADIUS_CHOICES.values():
		for name, value in zip(("radius-sm", "radius-md", "radius-lg"), values, strict=True):
			tokens.validate_value(name, value, slugs)
	for unit, gap in editor.DENSITY_CHOICES.values():
		tokens.validate_value("space-unit", unit, slugs)
		tokens.validate_value("section-gap", gap, slugs)


def test_rejection_html_is_escaped_and_has_line_and_column():
	result = css_validator.validate("a { b: c }\n.x { content: '<b>' }")
	text = editor.rejection_html(result)
	assert text.startswith("1:5:") and "<br>2:" in text
	assert "<b>" not in text


def test_versions_are_recorded_by_hash_and_capped():
	rows = [{"hash": "a"}, {"hash": "b"}]
	assert editor.should_record([], "a")
	assert editor.should_record(rows, "a")
	assert not editor.should_record(rows, "b")
	many = [{"hash": str(i)} for i in range(30)]
	assert editor.trimmed(many) == many[-20:] and len(editor.trimmed(rows)) == 2
	snap = editor.snapshot("custom", "night", None, None, "h")
	assert snap == {
		"hash": "h", "preset": "custom", "custom_base": "night", "token_overrides": "", "custom_css": "", "api_version": 1,
	}  # fmt: skip


def test_stale_names_lists_unknown_tokens_and_classes_only():
	names = editor.stale_names(".wk-gone { color: red } .wk-card { --wk-removed: 1px; --cx-ok: 1; display: none }")
	assert sorted(item["code"] for item in names) == ["unknown-class", "unknown-token"]
	assert editor.stale_names("") == []
