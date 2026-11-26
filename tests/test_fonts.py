from pathlib import Path

import pytest

from website_kit.theme import fonts

FONTS_DIR = fonts.FONTS_DIR
MAX_FILE = 60 * 1024
MAX_TOTAL = 450 * 1024
WOFF2_FILES = sorted(FONTS_DIR.rglob("*.woff2"))


def test_font_files_exist():
	assert len(WOFF2_FILES) == len(fonts.FONTS) * 2


@pytest.mark.parametrize("path", WOFF2_FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_every_font_file_has_its_licence_file(path: Path):
	licence = path.parent / fonts.LICENSE_FILE
	assert licence.is_file(), f"{path.name}: no {fonts.LICENSE_FILE} in {path.parent.name}/"
	text = licence.read_text(encoding="utf-8")
	assert "SIL OPEN FONT LICENSE" in text.upper() or "Apache License" in text
	assert "Copyright" in text or "Google Inc." in text


@pytest.mark.parametrize("path", WOFF2_FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_font_files_are_woff2_and_not_heavy(path: Path):
	data = path.read_bytes()
	assert data[:4] == b"wOF2"
	assert len(data) <= MAX_FILE


def test_total_weight_is_sensible():
	assert sum(path.stat().st_size for path in WOFF2_FILES) <= MAX_TOTAL


def test_every_registered_family_ships_latin_and_cyrillic():
	for slug, font in fonts.FONTS.items():
		assert set(font.files()) == {"latin", "cyrillic"}
		for file_name in font.files().values():
			assert (FONTS_DIR / slug / file_name).is_file(), file_name
		assert (FONTS_DIR / slug / fonts.LICENSE_FILE).is_file()
		assert font.license in {"OFL-1.1", "Apache-2.0"}


def test_no_unregistered_font_directory():
	directories = {path.name for path in FONTS_DIR.iterdir() if path.is_dir()}
	assert directories == set(fonts.FONTS)


def test_the_approved_set():
	assert set(fonts.FONTS) == {"inter", "source-sans-3", "manrope", "lora", "playfair-display", "roboto"}
	assert fonts.font_slugs() == {*fonts.FONTS, "system"}


def test_font_face_rules():
	rule = fonts.font_face_css("inter")
	assert rule.count("@font-face") == 2
	assert "font-display:swap" in rule and "unicode-range:U+0301,U+0400-045F" in rule
	assert "/assets/website_kit/fonts/inter/inter-cyrillic-wght-normal.woff2" in rule
	assert fonts.font_face_css("system") == ""
	assert fonts.stack("system") == fonts.SYSTEM_STACK
	assert fonts.stack("lora").endswith("serif")


def test_the_docs_list_every_family_and_the_real_total():
	docs = (FONTS_DIR.parent.parent.parent / "docs" / "fonts.md").read_text(encoding="utf-8")
	for font in fonts.FONTS.values():
		assert font.family.replace(" Variable", "") in docs
