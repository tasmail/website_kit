"""Guards for the stock-theme change and the header menu: each one fails when the thing it names is taken out."""

import re
from pathlib import Path

from website_kit import __version__

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "website_kit"
BASE_CSS = (PKG / "public/css/wk.css").read_text(encoding="utf-8")
HEADER_SRC = (PKG / "pages/header.py").read_text(encoding="utf-8")
NAVBAR = (PKG / "website_kit/web_template/wk_navbar/wk_navbar.html").read_text(encoding="utf-8")


def version_tuple(text):
	return tuple(int(part) for part in text.split("."))


def test_the_release_that_moves_sites_to_the_stock_theme_is_at_least_0_3_0():
	assert version_tuple(__version__) >= (0, 3, 0)


def test_the_patch_is_listed_and_runs_after_the_models_sync():
	lines = [line.split("#")[0].strip() for line in (PKG / "patches.txt").read_text(encoding="utf-8").splitlines()]
	post = lines[lines.index("[post_model_sync]") :]
	assert "website_kit.patches.v0_3.use_stock_website_theme" in post


def test_the_header_menu_is_a_native_disclosure_not_a_checkbox():
	assert "wk-header__toggle" not in BASE_CSS and "wk-header__toggle" not in NAVBAR
	assert "<details" in HEADER_SRC and "<summary" in HEADER_SRC and "checkbox" not in HEADER_SRC


def test_the_menu_is_collapsed_on_narrow_screens_and_open_on_wide_ones():
	assert re.search(r"\.wk-header__menu\s*\{\s*display:\s*none", BASE_CSS), "the disclosure is hidden on wide screens"
	narrow = BASE_CSS[BASE_CSS.index("@media (max-width: 48em)") :]
	assert re.search(r"\.wk-header__menu\s*\{[^}]*display:\s*block", narrow), "the disclosure shows on narrow screens"
	assert re.search(r"\.wk-header__nav--wide\s*\{[^}]*display:\s*none", narrow), (
		"the wide menu goes away on narrow screens"
	)
	assert re.search(r"\.wk-header__nav--narrow\s*\{[^}]*display:\s*flex", BASE_CSS), (
		"the menu inside the open disclosure"
	)
	assert re.search(r"\.wk-header__burger\s*\{[^}]*list-style:\s*none", BASE_CSS)
	assert "::-webkit-details-marker" in BASE_CSS, "no default triangle"
	assert re.search(r"\.wk-header__burger\s*\{[^}]*block-size:\s*44px", BASE_CSS) or re.search(
		r"\.wk-header__burger\s*\{[^}]*min-block-size:\s*44px", BASE_CSS
	)


def test_primary_buttons_give_visible_feedback_on_hover_and_focus():
	rules = re.findall(r"\.btn-primary:hover,\s*\.btn-primary:focus\s*\{([^}]*)\}", BASE_CSS)
	assert any("filter" in body for body in rules)
	shop = (PKG / "public/css/wk-shop.css").read_text(encoding="utf-8")
	assert re.search(r"\.wk-shop \.btn-primary:hover[^{]*\{[^}]*filter", shop)


def test_inputs_have_a_visible_focus_ring():
	assert re.search(r"\.form-control:focus\s*\{[^}]*outline:\s*max\(2px", BASE_CSS)
