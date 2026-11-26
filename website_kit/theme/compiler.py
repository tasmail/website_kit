"""Compile a preset plus the overrides into the plain CSS file of a site.

The output is deterministic (no time, no random name): the same input gives the same bytes, so the apply step can compare
hashes and write nothing when nothing changed. There is no SCSS and no node step; per-site variation is only CSS custom
properties. The static `public/css/wk.css` reads them.
"""

import hashlib

from .. import WK_THEME_API, css_validator
from . import fonts, presets, tokens

CUSTOM_MARKER = "/* Custom CSS */"


class CustomCssError(ValueError):
	"""The Custom CSS did not pass the validator; `result` holds its messages."""

	def __init__(self, result):
		self.result = result
		super().__init__("; ".join(str(message) for message in result.errors))


def effective(preset: str, overrides_text=None, base: str | None = None) -> dict:
	"""Resolve a preset name and the overrides JSON text; raises `tokens.TokenError` for bad input."""
	return presets.resolve(preset, presets.parse_overrides(overrides_text), base)


def compile_css(resolved: dict, custom_css: str = "") -> str:
	"""The generated stylesheet of an effective token set (see `effective`), then the validated Custom CSS."""
	token_values = resolved["tokens"]
	variants = resolved["variants"]
	lines = [f"/* Website Kit theme API {WK_THEME_API}, preset {resolved['preset']}. Generated: do not edit. */"]
	used = dict.fromkeys((token_values["font-body"], token_values["font-heading"]))
	lines.extend(rule for rule in (fonts.font_face_css(slug) for slug in used) if rule)
	lines.append(":root{")
	for name in tokens.TOKENS:
		value = token_values[name]
		if tokens.TOKENS[name] == "font":
			value = fonts.stack(value)
		lines.append(f"{tokens.css_name(name)}:{value};")
	for variant in tokens.VARIANTS:
		for prop, value in tokens.VARIANTS[variant][variants[variant]].items():
			lines.append(f"{prop}:{value};")
	lines.append("}")
	for variant, options in tokens.VARIANTS.items():
		for option, props in options.items():
			body = ";".join(f"{prop}:{value}" for prop, value in props.items())
			lines.append(f'[data-wk-{variant}="{option}"]{{{body}}}')
	custom_css = (custom_css or "").strip()
	if custom_css:
		result = css_validator.validate(custom_css)
		if not result.ok:
			raise CustomCssError(result)
		lines.extend((CUSTOM_MARKER, custom_css))
	return "\n".join(lines) + "\n"


def content_hash(css: str) -> str:
	return hashlib.sha256(css.encode("utf-8")).hexdigest()[:16]


def build(preset: str, overrides_text=None, custom_css: str = "", base: str | None = None) -> tuple[str, str]:
	"""Compile and return `(css, hash)` for a preset name, an overrides JSON text and the Custom CSS.

	The one compile path of the kit: the save, the apply step, the draft and the preview all end here, so the validator
	runs on every route. Raises `tokens.TokenError` or `CustomCssError`.
	"""
	css = compile_css(effective(preset, overrides_text, base), custom_css)
	return css, content_hash(css)
