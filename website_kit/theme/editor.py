"""The data behind the theme settings page, as pure functions (no Frappe): what the preset cards and the `custom` editor show,
the preview of unsaved values, and the rules for the saved versions.

Every function ends in `compiler.build`, the one compile path, so the preview shows exactly what a save would write and the
validator runs on it.
"""

import html
import json

from .. import WK_THEME_API, css_validator
from . import compiler, contrast, fonts, presets, tokens

MAX_VERSIONS = 20
# The `custom` editor edits these groups; the sizes are the choices of the "radius" and "density" controls.
RADIUS_CHOICES = {
	"none": ("0", "0", "0"),
	"small": ("2px", "4px", "6px"),
	"medium": ("4px", "8px", "12px"),
	"large": ("8px", "16px", "24px"),
}
DENSITY_CHOICES = {"compact": ("6px", "40px"), "comfortable": ("8px", "64px"), "spacious": ("10px", "88px")}


def presets_payload() -> list[dict]:
	"""The five presets with their tokens and variants, for the cards and the live preview."""
	out = []
	for name in presets.PRESET_NAMES:
		data = presets.load(name)
		data["enhanced"] = name in presets.ENHANCED_PRESETS
		out.append(data)
	return out


def fonts_payload() -> list[dict]:
	return [{"slug": fonts.SYSTEM, "family": "System"}] + [
		{"slug": font.slug, "family": font.family.replace(" Variable", "")} for font in fonts.FONTS.values()
	]


def token_meta() -> dict:
	"""The type of every token, so the editor can pick a control; and the groups of the editor."""
	return {
		"types": dict(tokens.TOKENS),
		"variants": {name: list(options) for name, options in tokens.VARIANTS.items()},
	}


def theme_data() -> dict:
	return {
		"api_version": WK_THEME_API,
		"presets": presets_payload(),
		"fonts": fonts_payload(),
		"meta": token_meta(),
		"radius_choices": {name: list(values) for name, values in RADIUS_CHOICES.items()},
		"density_choices": {name: list(values) for name, values in DENSITY_CHOICES.items()},
		"limits": css_validator.LIMITS,
	}


def contrast_payload(resolved: dict, base: str) -> list[dict]:
	enhanced = (base if resolved["preset"] == presets.CUSTOM else resolved["preset"]) in presets.ENHANCED_PRESETS
	return [
		{
			"label": check.label,
			"foreground": check.foreground,
			"background": check.background,
			"ratio": round(check.ratio, 2),
			"minimum": check.minimum,
			"passed": check.passed,
		}
		for check in contrast.check_tokens(resolved["tokens"], enhanced)
	]


def preview(preset: str, overrides_text=None, custom_css: str = "", base: str | None = None, translate=None) -> dict:
	"""What a save of these values would produce, without saving: the CSS, its hash, contrast checks and CSS messages.

	Never raises for bad input; a bad value comes back as `token_error`, bad Custom CSS as `errors` (and no `css`).
	"""
	out = {"css": "", "hash": "", "contrast": [], "token_error": "", **_css_report(custom_css, translate)}
	try:
		resolved = compiler.effective(preset, overrides_text, base)
	except tokens.TokenError as error:
		out["token_error"] = str(error)
		return out
	out["contrast"] = contrast_payload(resolved, base or presets.DEFAULT_PRESET)
	if not out["ok"]:
		return out
	css, digest = compiler.build(preset, overrides_text, custom_css, base)
	out.update(css=css, hash=digest)
	return out


def _css_report(custom_css: str, translate=None) -> dict:
	return css_validator.validate(custom_css or "").as_dict(translate)


def duplicate_as_custom(preset: str, overrides_text=None, base: str | None = None) -> dict:
	"""The values that turn the current look into an editable `custom` theme: every token written out, base remembered."""
	resolved = compiler.effective(preset, overrides_text, base)
	start = (base or presets.DEFAULT_PRESET) if preset == presets.CUSTOM else preset
	return {
		"preset": presets.CUSTOM,
		"custom_base": start,
		"token_overrides": json.dumps({"tokens": resolved["tokens"], "variants": resolved["variants"]}, indent="\t"),
	}


def rejection_html(result, translate=None) -> str:
	"""The text of a rejected save: one `line:column: reason` per error, HTML-escaped, joined by `<br>`."""
	return "<br>".join(
		html.escape(f"{m.line}:{m.column}: {m.localized(translate) if translate else m.message}") for m in result.errors
	)


# ---------------------------------------------------------------- versions


def snapshot(preset: str, base: str | None, overrides_text, custom_css: str, digest: str) -> dict:
	return {
		"hash": digest,
		"preset": preset,
		"custom_base": base or "",
		"token_overrides": overrides_text or "",
		"custom_css": custom_css or "",
		"api_version": WK_THEME_API,
	}


def should_record(rows: list, digest: str) -> bool:
	"""A new version is recorded when the compiled file differs from the newest version."""
	return not rows or rows[-1]["hash"] != digest


def trimmed(rows: list) -> list:
	"""The newest `MAX_VERSIONS` rows, oldest first."""
	return rows[-MAX_VERSIONS:]


def stale_names(custom_css: str) -> list[dict]:
	"""Warnings of stored Custom CSS about `--wk-*` tokens and `.wk-*` classes that this kit version does not know.

	Used after an upgrade to show a note on the settings page; the stored CSS is never rewritten.
	"""
	result = css_validator.validate(custom_css or "")
	return [m.as_dict() for m in result.warnings if m.code in ("unknown-token", "unknown-class")]
