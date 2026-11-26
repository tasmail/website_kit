import re

import pytest

from website_kit import WK_THEME_API
from website_kit.theme import compiler, presets, tokens


@pytest.mark.parametrize("name", presets.PRESET_NAMES)
def test_every_preset_compiles_to_a_small_plain_css(name):
	css, digest = compiler.build(name)
	assert css.startswith(f"/* Website Kit theme API {WK_THEME_API}, preset {name}.")
	assert len(css.encode()) < 5000
	assert len(digest) == 16
	for token in tokens.TOKENS:
		assert f"{tokens.css_name(token)}:" in css
	assert "@import" not in css and "<" not in css and "url(//" not in css


def test_output_is_deterministic():
	first = compiler.build("market", '{"tokens": {"color-link": "#123456"}}')
	again = compiler.build("market", '{"tokens": {"color-link": "#123456"}}')
	assert first == again
	assert compiler.build("clear")[1] != compiler.build("night")[1]


def test_overrides_change_the_output():
	css, _ = compiler.build("clear", '{"tokens": {"color-primary": "#00ff00"}, "variants": {"card": "raised"}}')
	assert "--wk-color-primary:#00ff00;" in css
	assert "--wk-card-shadow:var(--wk-shadow-2);" in css.split(":root{")[1].split("\n}")[0]


def test_only_the_used_fonts_are_requested():
	css, _ = compiler.build("market")
	assert "Source Sans 3 Variable" in css and "Lora Variable" in css
	assert "Inter Variable" not in css
	assert css.count("@font-face") == 4  # two families, Latin and Cyrillic each
	assert 'font-family:"Inter Variable"' in compiler.build("clear")[0]
	assert css.count("/assets/website_kit/fonts/") == 4


def test_system_font_needs_no_font_face():
	css, _ = compiler.build("clear", '{"tokens": {"font-body": "system", "font-heading": "system"}}')
	assert "@font-face" not in css
	assert "--wk-font-body:system-ui" in css


def test_serif_families_have_a_serif_fallback():
	assert "Georgia" in compiler.build("market")[0]


def test_variant_blocks_for_local_overrides():
	css, _ = compiler.build("clear")
	for variant, options in tokens.VARIANTS.items():
		for option in options:
			assert f'[data-wk-{variant}="{option}"]{{' in css


def test_root_block_holds_the_chosen_variants():
	css, _ = compiler.build("night")
	root = css.split(":root{")[1].split("}")[0]
	assert "--wk-header-bg:var(--wk-color-inverse);" in root
	assert "--wk-button-radius:var(--wk-radius-sm);" in root


def test_bad_input_raises():
	with pytest.raises(tokens.TokenError):
		compiler.build("clear", '{"tokens": {"color-primary": "x"}}')
	with pytest.raises(tokens.TokenError):
		compiler.build("nope")


def test_no_stray_braces_or_semicolons_in_values():
	css, _ = compiler.build("ledger")
	root = css.split(":root{")[1].split("\n}")[0]
	for line in root.strip().splitlines():
		assert re.fullmatch(r"--wk-[a-z0-9-]+:[^;{}]+;", line), line
