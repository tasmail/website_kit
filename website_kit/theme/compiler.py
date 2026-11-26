"""Compile a preset plus the overrides into the plain CSS file of a site.

The output is deterministic (no time, no random name): the same input gives the same bytes, so the apply step can compare
hashes and write nothing when nothing changed. There is no SCSS and no node step; per-site variation is only CSS custom
properties. The static `public/css/wk.css` reads them.
"""

import hashlib

from .. import WK_THEME_API
from . import fonts, presets, tokens


def effective(preset: str, overrides_text=None) -> dict:
	"""Resolve a preset name and the overrides JSON text; raises `tokens.TokenError` for bad input."""
	return presets.resolve(preset, presets.parse_overrides(overrides_text))


def compile_css(resolved: dict) -> str:
	"""The generated stylesheet of an effective token set (see `effective`)."""
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
	return "\n".join(lines) + "\n"


def content_hash(css: str) -> str:
	return hashlib.sha256(css.encode("utf-8")).hexdigest()[:16]


def build(preset: str, overrides_text=None) -> tuple[str, str]:
	"""Compile and return `(css, hash)` for a preset name and an overrides JSON text."""
	css = compile_css(effective(preset, overrides_text))
	return css, content_hash(css)
