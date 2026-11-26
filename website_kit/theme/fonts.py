"""The self-hosted font set.

Every family is a variable `woff2` file per subset (Latin and Cyrillic), taken from the Fontsource packages
`@fontsource-variable/<slug>` (the OFL sources of google/fonts). `docs/fonts.md` lists the sizes and the origin. The files
live in `public/fonts/<slug>/` next to the licence text of the family; `tests/test_fonts.py` fails when a file has no licence.
"""

from dataclasses import dataclass
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parent.parent / "public" / "fonts"
ASSET_URL = "/assets/website_kit/fonts"
LICENSE_FILE = "LICENSE.txt"

UNICODE_RANGES = {
	"latin": (
		"U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,"
		"U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD"
	),
	"cyrillic": "U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116",
}
SYSTEM_STACK = 'system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
SERIF_FALLBACK = 'Georgia,"Times New Roman",serif'


@dataclass(frozen=True)
class Font:
	slug: str
	family: str  # the CSS family name of the @font-face rule
	weights: str  # the range of the variable axis, for `font-weight`
	license: str  # SPDX identifier
	serif: bool = False

	def files(self) -> dict[str, str]:
		return {subset: f"{self.slug}-{subset}-wght-normal.woff2" for subset in UNICODE_RANGES}

	def stack(self) -> str:
		return f'"{self.family}",{SERIF_FALLBACK if self.serif else SYSTEM_STACK}'


FONTS: dict[str, Font] = {
	font.slug: font
	for font in (
		Font("inter", "Inter Variable", "100 900", "OFL-1.1"),
		Font("source-sans-3", "Source Sans 3 Variable", "200 900", "OFL-1.1"),
		Font("manrope", "Manrope Variable", "200 800", "OFL-1.1"),
		Font("lora", "Lora Variable", "400 700", "OFL-1.1", serif=True),
		Font("playfair-display", "Playfair Display Variable", "400 900", "OFL-1.1", serif=True),
		Font("roboto", "Roboto Variable", "100 900", "OFL-1.1"),
	)
}
SYSTEM = "system"


def font_slugs() -> set[str]:
	return {SYSTEM, *FONTS}


def stack(slug: str) -> str:
	return SYSTEM_STACK if slug == SYSTEM else FONTS[slug].stack()


def font_face_css(slug: str) -> str:
	"""The @font-face rules (one per subset) of a family; empty for the system stack."""
	if slug == SYSTEM:
		return ""
	font = FONTS[slug]
	rules = []
	for subset, file_name in font.files().items():
		rules.append(
			f'@font-face{{font-family:"{font.family}";font-style:normal;font-weight:{font.weights};'
			f'font-display:swap;src:url({ASSET_URL}/{slug}/{file_name}) format("woff2");'
			f"unicode-range:{UNICODE_RANGES[subset]}}}"
		)
	return "\n".join(rules)
