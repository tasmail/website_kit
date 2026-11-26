"""WCAG 2.2 contrast maths and the checks that every preset must pass.

Text pairs need 4.5:1 (success criterion 1.4.3) and interface parts 3:1 (1.4.11). The `contrast` preset needs 7:1 for all of
them. The module does not import Frappe; CI runs `check_preset` for every preset (`tests/test_contrast.py`) and the settings
page can reuse `check_tokens` to warn about a pair of custom colours.
"""

from dataclasses import dataclass

TEXT_MIN = 4.5
UI_MIN = 3.0
ENHANCED_MIN = 7.0

# (label, foreground token, background token, kind): "text" needs 4.5:1, "ui" needs 3:1.
PAIRS = (
	("text on background", "color-text", "color-bg", "text"),
	("text on surface", "color-text", "color-surface", "text"),
	("muted text on background", "color-muted", "color-bg", "text"),
	("muted text on surface", "color-muted", "color-surface", "text"),
	("link on background", "color-link", "color-bg", "text"),
	("link on surface", "color-link", "color-surface", "text"),
	("danger text on background", "color-danger", "color-bg", "text"),
	("danger text on surface", "color-danger", "color-surface", "text"),
	("button text on primary", "color-primary-contrast", "color-primary", "text"),
	("text on inverse (dark header and footer)", "color-inverse-contrast", "color-inverse", "text"),
	("primary on background", "color-primary", "color-bg", "ui"),
	("primary on surface", "color-primary", "color-surface", "ui"),
	("accent on background", "color-accent", "color-bg", "ui"),
	("accent on surface", "color-accent", "color-surface", "ui"),
)


@dataclass(frozen=True)
class Check:
	label: str
	foreground: str
	background: str
	ratio: float
	minimum: float

	@property
	def passed(self) -> bool:
		return self.ratio >= self.minimum


def parse_hex(value: str) -> tuple[int, int, int]:
	text = value.strip().lstrip("#")
	if len(text) == 3:
		text = "".join(char * 2 for char in text)
	if len(text) != 6:
		raise ValueError(f"not a hex colour: {value!r}")
	return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def _linear(channel: int) -> float:
	value = channel / 255
	return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def luminance(value: str) -> float:
	red, green, blue = (_linear(channel) for channel in parse_hex(value))
	return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def ratio(foreground: str, background: str) -> float:
	"""The WCAG contrast ratio of two colours, from 1 to 21."""
	one, two = luminance(foreground), luminance(background)
	lighter, darker = max(one, two), min(one, two)
	return (lighter + 0.05) / (darker + 0.05)


def check_tokens(tokens: dict[str, str], enhanced: bool = False) -> list[Check]:
	"""Check every pair of `PAIRS` for a full token set; `enhanced` requires 7:1 everywhere."""
	checks = []
	for label, fg, bg, kind in PAIRS:
		minimum = ENHANCED_MIN if enhanced else (TEXT_MIN if kind == "text" else UI_MIN)
		checks.append(Check(label, fg, bg, ratio(tokens[fg], tokens[bg]), minimum))
	return checks


def failures(tokens: dict[str, str], enhanced: bool = False) -> list[Check]:
	return [check for check in check_tokens(tokens, enhanced) if not check.passed]
