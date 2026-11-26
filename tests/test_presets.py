import json

import pytest

from website_kit.theme import presets, tokens


def test_five_presets_and_the_default():
	assert presets.PRESET_NAMES == ("clear", "market", "contrast", "night", "ledger")
	assert presets.DEFAULT_PRESET == "clear"
	assert sorted(path.stem for path in presets.PRESETS_DIR.glob("*.json")) == sorted(presets.PRESET_NAMES)


@pytest.mark.parametrize("name", presets.PRESET_NAMES)
def test_every_preset_is_complete(name):
	data = presets.load(name)
	assert data["name"] == name
	assert list(data["tokens"]) and set(data["tokens"]) == set(tokens.TOKENS)
	assert set(data["variants"]) == set(tokens.VARIANTS)
	assert data["label"] and data["description"]


def test_load_returns_a_copy():
	data = presets.load("clear")
	data["tokens"]["color-primary"] = "#000000"
	assert presets.load("clear")["tokens"]["color-primary"] != "#000000"


def test_unknown_preset():
	with pytest.raises(tokens.TokenError):
		presets.load("neon")


def test_incomplete_preset_is_rejected():
	data = presets.load("clear")
	del data["tokens"]["color-bg"]
	with pytest.raises(tokens.TokenError):
		presets._check_complete(data)
	data = presets.load("clear")
	data["tokens"]["made-up"] = "1"
	with pytest.raises(tokens.TokenError):
		presets._check_complete(data)
	data = presets.load("clear")
	del data["variants"]["card"]
	with pytest.raises(tokens.TokenError):
		presets._check_complete(data)


def test_parse_overrides_empty():
	empty = {"tokens": {}, "variants": {}}
	assert presets.parse_overrides(None) == empty
	assert presets.parse_overrides("  ") == empty
	assert presets.parse_overrides("{}") == empty


def test_parse_overrides_valid():
	text = json.dumps({"tokens": {"color-primary": "#ABCDEF"}, "variants": {"card": "flat"}})
	assert presets.parse_overrides(text) == {"tokens": {"color-primary": "#abcdef"}, "variants": {"card": "flat"}}


@pytest.mark.parametrize(
	"text",
	[
		"not json",
		"[]",
		'{"colors": {}}',
		'{"tokens": []}',
		'{"variants": "x"}',
		'{"tokens": {"color-primary": "blue"}}',
		'{"tokens": {"nope": "#ffffff"}}',
		'{"variants": {"card": "glass"}}',
	],
)
def test_parse_overrides_rejects(text):
	with pytest.raises(tokens.TokenError):
		presets.parse_overrides(text)


def test_resolve_applies_overrides_over_the_preset():
	resolved = presets.resolve("clear", {"tokens": {"color-primary": "#112233"}, "variants": {"button": "pill"}})
	assert resolved["tokens"]["color-primary"] == "#112233"
	assert resolved["tokens"]["color-bg"] == presets.load("clear")["tokens"]["color-bg"]
	assert resolved["variants"]["button"] == "pill"
	assert resolved["variants"]["card"] == "outlined"
	assert presets.resolve("night")["preset"] == "night"
