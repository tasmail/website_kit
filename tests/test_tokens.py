import pytest

from website_kit.theme import fonts, tokens

SLUGS = fonts.font_slugs()


@pytest.mark.parametrize(
	("name", "value", "expected"),
	[
		("color-primary", "#1D4ED8", "#1d4ed8"),
		("font-body", "inter", "inter"),
		("font-body", "system", "system"),
		("font-size-base", "16px", "16px"),
		("radius-sm", "0", "0"),
		("radius-sm", "0.5rem", "0.5rem"),
		("line-height", "1.6", "1.6"),
		("heading-weight", "700", "700"),
		("shadow-1", "none", "none"),
		("shadow-1", "0 1px 2px rgba(15,23,42,.06)", "0 1px 2px rgba(15,23,42,.06)"),
	],
)
def test_valid_values_are_normalised(name, value, expected):
	assert tokens.validate_value(name, value, SLUGS) == expected


@pytest.mark.parametrize(
	("name", "value"),
	[
		("color-primary", "red"),
		("color-primary", "#fff"),
		("color-primary", "#1d4ed8; background:url(//evil)"),
		("font-body", "comic-sans"),
		("font-body", "inter, serif"),
		("font-size-base", "16"),
		("font-size-base", "16px}"),
		("line-height", "1.6;"),
		("heading-weight", "650"),
		("shadow-1", "0 0 0 url(//evil/x)"),
		("shadow-1", "0 0 0 var(--x)"),
		("shadow-1", "0 0 5px red;}"),
		("shadow-1", "</style>"),
		("shadow-1", "x" * 200),
		("unknown-token", "1"),
	],
)
def test_bad_values_are_rejected(name, value):
	with pytest.raises(tokens.TokenError):
		tokens.validate_value(name, value, SLUGS)


def test_variants():
	assert tokens.validate_variant("card", "raised") == "raised"
	with pytest.raises(tokens.TokenError):
		tokens.validate_variant("card", "glass")
	with pytest.raises(tokens.TokenError):
		tokens.validate_variant("sidebar", "light")


def test_every_variant_value_sets_the_same_properties():
	for options in tokens.VARIANTS.values():
		assert len({frozenset(props) for props in options.values()}) == 1


def test_css_name():
	assert tokens.css_name("color-bg") == "--wk-color-bg"
