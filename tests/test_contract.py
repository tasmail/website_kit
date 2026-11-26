"""The documented public names (docs/theming.md) and the code must agree in both directions."""

import re
from pathlib import Path

from website_kit import WK_THEME_API
from website_kit.theme import compiler, fonts, presets, tokens

ROOT = Path(__file__).resolve().parent.parent
DOC = (ROOT / "docs" / "theming.md").read_text(encoding="utf-8")
BASE_CSS = (ROOT / "website_kit" / "public" / "css" / "wk.css").read_text(encoding="utf-8")
BACKTICKED = set(re.findall(r"`([^`]+)`", DOC))

CLASSES = {
	".wk-container",
	".wk-skip-link",
	".wk-header",
	".wk-footer",
	".wk-card",
	".wk-button",
	".wk-button--secondary",
	".wk-field",
	".wk-product-card",
	".wk-price",
	".wk-badge",
}


def variant_properties():
	return {prop for options in tokens.VARIANTS.values() for props in options.values() for prop in props}


def documented_custom_properties():
	return {name for name in BACKTICKED if re.fullmatch(r"--wk-[a-z0-9-]+", name)}


def test_the_api_version_is_stated():
	assert f"`WK_THEME_API = {WK_THEME_API}`" in DOC


def test_every_token_is_documented():
	for token in tokens.TOKENS:
		assert f"`{tokens.css_name(token)}`" in DOC, token


def test_every_variant_and_value_is_documented():
	for variant, options in tokens.VARIANTS.items():
		assert f"`data-wk-{variant}`" in DOC, variant
		for option in options:
			assert f"`{option}`" in DOC, (variant, option)


def test_every_variant_property_is_documented():
	for prop in variant_properties():
		assert f"`{prop}`" in DOC, prop


def test_nothing_undocumented_is_public():
	"""A documented custom property must exist in the code, so a removed or renamed name fails here."""
	known = {tokens.css_name(token) for token in tokens.TOKENS} | variant_properties()
	assert documented_custom_properties() == known


def test_every_documented_class_exists_in_the_stylesheet():
	documented = {name for name in BACKTICKED if re.fullmatch(r"\.wk-[a-z0-9-]+", name)}
	public = documented & CLASSES
	assert public == CLASSES, "a public class is missing from docs/theming.md"
	for class_name in CLASSES:
		assert re.search(re.escape(class_name) + r"(?![\w-])", BASE_CSS), f"{class_name} is gone from wk.css"


def test_documented_classes_are_all_in_the_contract_list():
	documented = {name for name in BACKTICKED if re.fullmatch(r"\.wk-[a-z0-9-]+", name)}
	assert documented == CLASSES


def test_the_stylesheet_reads_only_documented_properties():
	used = set(re.findall(r"var\((--wk-[a-z0-9-]+)\)", BASE_CSS))
	assert used <= documented_custom_properties(), used - documented_custom_properties()


def test_generated_css_defines_every_documented_property():
	css, _ = compiler.build(presets.DEFAULT_PRESET)
	defined = set(re.findall(r"(--wk-[a-z0-9-]+):", css))
	assert documented_custom_properties() <= defined


def test_documented_variant_attributes_are_in_the_generated_css():
	css, _ = compiler.build(presets.DEFAULT_PRESET)
	for variant, options in tokens.VARIANTS.items():
		for option in options:
			assert f'[data-wk-{variant}="{option}"]' in css


def test_documented_presets_and_fonts_exist():
	for name in presets.PRESET_NAMES:
		assert f"`{name}`" in DOC
	for slug in fonts.font_slugs():
		assert f"`{slug}`" in DOC


def test_templates_use_only_documented_classes():
	templates = (ROOT / "website_kit" / "website_kit" / "web_template").rglob("*.html")
	internal = re.compile(r"^wk-(header|menu|footer)(__|$)")
	for template in templates:
		for classes in re.findall(r'class="([^"]+)"', template.read_text(encoding="utf-8")):
			for name in classes.split():
				if name.startswith("wk-"):
					assert f".{name}" in CLASSES or internal.match(name), (template.name, name)


def test_every_class_of_the_stylesheet_is_documented_or_internal():
	"""The other direction: a new public-looking class in wk.css must be added to the contract or be internal."""
	internal = re.compile(r"^wk-(header__|footer__|menu)")
	found = {f".{name}" for name in re.findall(r"\.(wk-[a-z0-9_-]+)", BASE_CSS) if not internal.match(name)}
	assert found == CLASSES


def test_the_documented_variant_values_are_exactly_the_code_values():
	rows = dict(re.findall(r"^\| `data-wk-([a-z]+)` \| ([^|]+) \|", DOC, flags=re.M))
	assert set(rows) == set(tokens.VARIANTS)
	for variant, cell in rows.items():
		assert set(re.findall(r"`([a-z]+)`", cell)) == set(tokens.VARIANTS[variant]), variant
