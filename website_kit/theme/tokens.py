"""The design tokens: the names, the value types and the checks of every value.

This module is the single source of the public token names (`docs/theming.md` documents them and a test compares the two).
It does not import Frappe, so the unit tests run without a bench. Every value that reaches the generated CSS file passes
through `validate_value`: a value is accepted only if it matches the strict pattern of its type.
"""

import re

PREFIX = "--wk-"

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
LENGTH = re.compile(r"^(0|\d{1,4}(\.\d{1,3})?(px|rem|em))$")
NUMBER = re.compile(r"^\d{1,2}(\.\d{1,3})?$")
WEIGHT = re.compile(r"^[1-9]00$")
SHADOW = re.compile(r"^[0-9a-zA-Z#(),.% -]{1,120}$")
SHADOW_FUNCTIONS = {"rgb", "rgba", "hsl", "hsla"}

# name -> value type, in the order of the generated file
TOKENS: dict[str, str] = {
	# colour
	"color-primary": "color",
	"color-primary-contrast": "color",
	"color-accent": "color",
	"color-bg": "color",
	"color-surface": "color",
	"color-text": "color",
	"color-muted": "color",
	"color-border": "color",
	"color-link": "color",
	"color-danger": "color",
	"color-inverse": "color",
	"color-inverse-contrast": "color",
	# type
	"font-body": "font",
	"font-heading": "font",
	"font-size-base": "length",
	"line-height": "number",
	"heading-weight": "weight",
	"heading-scale": "number",
	# shape
	"radius-sm": "length",
	"radius-md": "length",
	"radius-lg": "length",
	"shadow-1": "shadow",
	"shadow-2": "shadow",
	"border-width": "length",
	# space
	"space-unit": "length",
	"container-width": "length",
	"section-gap": "length",
}

# Variant name -> value -> the custom properties it sets. The values are references to tokens, so a variant follows
# the preset and the overrides. The attribute `data-wk-<name>="<value>"` on any element applies the properties to
# that element and its descendants.
VARIANTS: dict[str, dict[str, dict[str, str]]] = {
	"header": {
		"light": {
			"--wk-header-bg": "var(--wk-color-bg)",
			"--wk-header-fg": "var(--wk-color-text)",
			"--wk-header-border": "var(--wk-color-border)",
		},
		"dark": {
			"--wk-header-bg": "var(--wk-color-inverse)",
			"--wk-header-fg": "var(--wk-color-inverse-contrast)",
			"--wk-header-border": "var(--wk-color-inverse)",
		},
		"tinted": {
			"--wk-header-bg": "var(--wk-color-surface)",
			"--wk-header-fg": "var(--wk-color-text)",
			"--wk-header-border": "var(--wk-color-border)",
		},
	},
	"footer": {
		"light": {
			"--wk-footer-bg": "var(--wk-color-surface)",
			"--wk-footer-fg": "var(--wk-color-text)",
		},
		"dark": {
			"--wk-footer-bg": "var(--wk-color-inverse)",
			"--wk-footer-fg": "var(--wk-color-inverse-contrast)",
		},
	},
	"card": {
		"flat": {
			"--wk-card-bg": "var(--wk-color-surface)",
			"--wk-card-border": "0 solid transparent",
			"--wk-card-shadow": "none",
		},
		"outlined": {
			"--wk-card-bg": "var(--wk-color-bg)",
			"--wk-card-border": "var(--wk-border-width) solid var(--wk-color-border)",
			"--wk-card-shadow": "none",
		},
		"raised": {
			"--wk-card-bg": "var(--wk-color-bg)",
			"--wk-card-border": "0 solid transparent",
			"--wk-card-shadow": "var(--wk-shadow-2)",
		},
	},
	"button": {
		"solid": {"--wk-button-radius": "var(--wk-radius-sm)"},
		"pill": {"--wk-button-radius": "999px"},
		"square": {"--wk-button-radius": "0"},
	},
}

COLOR_TOKENS = tuple(name for name, kind in TOKENS.items() if kind == "color")


class TokenError(ValueError):
	"""A token name or a token value that the kit does not accept."""


def css_name(token: str) -> str:
	return PREFIX + token


def validate_value(name: str, value, font_slugs: set[str]) -> str:
	"""Return the normalised value of the token `name`, or raise `TokenError`."""
	kind = TOKENS.get(name)
	if kind is None:
		raise TokenError(f"unknown token '{name}'")
	text = str(value).strip()
	ok = {
		"color": lambda: bool(HEX.match(text)),
		"font": lambda: text in font_slugs,
		"length": lambda: bool(LENGTH.match(text)),
		"number": lambda: bool(NUMBER.match(text)),
		"weight": lambda: bool(WEIGHT.match(text)),
		"shadow": lambda: _shadow_ok(text),
	}[kind]()
	if not ok:
		raise TokenError(f"invalid {kind} value for '{name}'")
	return text.lower() if kind == "color" else text


def _shadow_ok(text: str) -> bool:
	if text == "none":
		return True
	if not SHADOW.match(text):
		return False
	return all(fn.lower() in SHADOW_FUNCTIONS for fn in re.findall(r"([A-Za-z-]+)\(", text))


def validate_variant(name: str, value) -> str:
	options = VARIANTS.get(name)
	if options is None:
		raise TokenError(f"unknown variant '{name}'")
	if value not in options:
		raise TokenError(f"invalid value for variant '{name}'")
	return value
