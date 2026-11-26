"""Guards for the stock-theme change and the header menu: each one fails when the thing it names is taken out."""

import re
from pathlib import Path

from website_kit import __version__

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "website_kit"
BASE_CSS = (PKG / "public/css/wk.css").read_text(encoding="utf-8")
NAVBAR = (PKG / "website_kit/web_template/wk_navbar/wk_navbar.html").read_text(encoding="utf-8")


def version_tuple(text):
	return tuple(int(part) for part in text.split("."))


def test_the_release_that_moves_sites_to_the_stock_theme_is_at_least_0_3_0():
	assert version_tuple(__version__) >= (0, 3, 0)


def test_the_patch_is_listed_and_runs_after_the_models_sync():
	lines = [line.split("#")[0].strip() for line in (PKG / "patches.txt").read_text(encoding="utf-8").splitlines()]
	post = lines[lines.index("[post_model_sync]") :]
	assert "website_kit.patches.v0_3.use_stock_website_theme" in post


def test_the_header_menu_is_a_labelled_checkbox_with_a_label_for_it():
	toggle = re.search(r'<input[^>]*class="wk-header__toggle"[^>]*>', NAVBAR)
	assert toggle, "the menu checkbox is gone"
	assert 'type="checkbox"' in toggle.group(0) and "aria-label=" in toggle.group(0)
	toggle_id = re.search(r'id="([^"]+)"', toggle.group(0)).group(1)
	assert re.search(rf'<label[^>]*class="wk-header__burger"[^>]*for="{toggle_id}"', NAVBAR)
	assert NAVBAR.index("wk-header__toggle") < NAVBAR.index('<nav class="wk-header__nav"'), (
		"the checkbox must come before the nav (sibling selector)"
	)


def test_the_menu_is_collapsed_on_narrow_screens_and_open_on_wide_ones():
	assert re.search(r"\.wk-header__toggle,\s*\.wk-header__burger\s*\{\s*display:\s*none", BASE_CSS), (
		"hidden by default (wide screens)"
	)
	narrow = BASE_CSS[BASE_CSS.index("@media (max-width: 48em)") :]
	assert re.search(r"\.wk-header__nav\s*\{[^}]*display:\s*none", narrow), "the nav collapses on narrow screens"
	assert re.search(r"\.wk-header__toggle:checked\s*~\s*\.wk-header__nav\s*\{[^}]*display:\s*flex", narrow), (
		"the checkbox opens it"
	)
	assert re.search(r"\.wk-header__burger\s*\{[^}]*display:\s*inline-flex", narrow)
	assert re.search(r"\.wk-header__toggle:focus-visible\s*\+\s*\.wk-header__burger\s*\{[^}]*outline", narrow), (
		"a visible focus ring"
	)


def test_the_invisible_checkbox_is_positioned_against_the_header():
	assert re.search(r"\.wk-header__inner\s*\{[^}]*position:\s*relative", BASE_CSS)
	assert re.search(r"\.wk-header__toggle\s*\{[^}]*position:\s*absolute", BASE_CSS)


def test_primary_buttons_give_visible_feedback_on_hover_and_focus():
	rules = re.findall(r"\.btn-primary:hover,\s*\.btn-primary:focus\s*\{([^}]*)\}", BASE_CSS)
	assert any("filter" in body for body in rules)
	shop = (PKG / "public/css/wk-shop.css").read_text(encoding="utf-8")
	assert re.search(r"\.wk-shop \.btn-primary:hover[^{]*\{[^}]*filter", shop)


def test_inputs_have_a_visible_focus_ring():
	assert re.search(r"\.form-control:focus\s*\{[^}]*outline:\s*max\(2px", BASE_CSS)
