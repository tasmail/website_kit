"""The presets: standard token sets stored as data (`presets/<name>.json`), never as code.

A site stores the name of a preset and only the values that the customer changed (the overrides), so an improvement of a
preset reaches every site that did not override that value.
"""

import json
from functools import cache
from pathlib import Path

from . import fonts, tokens

PRESETS_DIR = Path(__file__).resolve().parent / "presets"
PRESET_NAMES = ("clear", "market", "contrast", "night", "ledger")
DEFAULT_PRESET = "clear"
ENHANCED_PRESETS = frozenset({"contrast"})  # presets that must reach 7:1


@cache
def _read(name: str) -> dict:
	if name not in PRESET_NAMES:
		raise tokens.TokenError(f"unknown preset '{name}'")
	data = json.loads((PRESETS_DIR / f"{name}.json").read_text(encoding="utf-8"))
	_check_complete(data)
	return data


def _check_complete(data: dict) -> None:
	name = data["name"]
	slugs = fonts.font_slugs()
	missing = [token for token in tokens.TOKENS if token not in data["tokens"]]
	extra = [token for token in data["tokens"] if token not in tokens.TOKENS]
	if missing or extra:
		raise tokens.TokenError(f"preset '{name}': missing {missing}, unknown {extra}")
	for token, value in data["tokens"].items():
		tokens.validate_value(token, value, slugs)
	if set(data["variants"]) != set(tokens.VARIANTS):
		raise tokens.TokenError(f"preset '{name}': the variants must be exactly {sorted(tokens.VARIANTS)}")
	for variant, value in data["variants"].items():
		tokens.validate_variant(variant, value)


def load(name: str) -> dict:
	"""A copy of the preset: `name`, `label`, `description`, `tokens` and `variants`."""
	return json.loads(json.dumps(_read(name)))


def parse_overrides(text) -> dict:
	"""Parse and validate the overrides JSON of the settings: `{"tokens": {...}, "variants": {...}}`.

	Empty text means no overrides. Returns a normalised dict with both keys; raises `tokens.TokenError`.
	"""
	if text is None or not str(text).strip():
		return {"tokens": {}, "variants": {}}
	try:
		data = json.loads(text)
	except ValueError as error:
		raise tokens.TokenError(f"the overrides are not valid JSON: {error}") from None
	if not isinstance(data, dict) or set(data) - {"tokens", "variants"}:
		raise tokens.TokenError('the overrides must be an object with the keys "tokens" and "variants"')
	slugs = fonts.font_slugs()
	token_values = data.get("tokens", {})
	variant_values = data.get("variants", {})
	if not isinstance(token_values, dict) or not isinstance(variant_values, dict):
		raise tokens.TokenError('"tokens" and "variants" must be objects')
	return {
		"tokens": {name: tokens.validate_value(name, value, slugs) for name, value in token_values.items()},
		"variants": {name: tokens.validate_variant(name, value) for name, value in variant_values.items()},
	}


def resolve(name: str, overrides: dict | None = None) -> dict:
	"""The effective tokens and variants: the preset with the validated overrides on top."""
	preset = load(name)
	overrides = overrides or {"tokens": {}, "variants": {}}
	return {
		"preset": name,
		"tokens": {**preset["tokens"], **overrides.get("tokens", {})},
		"variants": {**preset["variants"], **overrides.get("variants", {})},
	}
