import pytest

from website_kit.theme import contrast, presets


def test_known_ratios():
	assert contrast.ratio("#000000", "#ffffff") == pytest.approx(21.0)
	assert contrast.ratio("#ffffff", "#ffffff") == pytest.approx(1.0)
	assert contrast.ratio("#777777", "#ffffff") == pytest.approx(4.478, abs=0.01)
	assert contrast.ratio("#767676", "#ffffff") >= 4.5
	assert contrast.ratio("#fff", "#000") == pytest.approx(21.0)


def test_ratio_is_symmetric():
	assert contrast.ratio("#1d4ed8", "#f8fafc") == contrast.ratio("#f8fafc", "#1d4ed8")


def test_luminance_edges():
	assert contrast.luminance("#000000") == 0
	assert contrast.luminance("#ffffff") == pytest.approx(1.0)


@pytest.mark.parametrize("bad", ["", "#12", "#1234567", "zzzzzz"])
def test_parse_hex_rejects(bad):
	with pytest.raises(ValueError):
		contrast.parse_hex(bad)


@pytest.mark.parametrize("name", presets.PRESET_NAMES)
def test_every_preset_passes_its_contrast_checks(name):
	tokens = presets.load(name)["tokens"]
	enhanced = name in presets.ENHANCED_PRESETS
	assert contrast.failures(tokens, enhanced) == [], name


def test_only_the_contrast_preset_is_enhanced():
	assert presets.ENHANCED_PRESETS == {"contrast"}


def test_the_contrast_preset_reaches_seven_to_one_on_every_pair():
	tokens = presets.load("contrast")["tokens"]
	assert all(check.ratio >= 7.0 for check in contrast.check_tokens(tokens))
	assert all(check.minimum == 7.0 for check in contrast.check_tokens(tokens, enhanced=True))


def test_night_is_checked_on_its_dark_surfaces():
	checks = {check.label: check for check in contrast.check_tokens(presets.load("night")["tokens"])}
	assert checks["text on background"].background == "color-bg"
	assert checks["muted text on surface"].ratio >= 4.5
	assert contrast.luminance(presets.load("night")["tokens"]["color-bg"]) < 0.05


def test_required_pairs_are_covered():
	labels = {pair[0] for pair in contrast.PAIRS}
	for needed in (
		"muted text on background",
		"muted text on surface",
		"link on background",
		"link on surface",
		"accent on background",
		"accent on surface",
		"button text on primary",
	):
		assert needed in labels


def test_minimums_by_kind():
	tokens = presets.load("clear")["tokens"]
	by_label = {check.label: check.minimum for check in contrast.check_tokens(tokens)}
	assert by_label["text on background"] == 4.5
	assert by_label["accent on surface"] == 3.0


def test_a_failing_pair_is_reported():
	tokens = presets.load("clear")["tokens"]
	tokens["color-muted"] = "#bbbbbb"
	failed = {check.label for check in contrast.failures(tokens)}
	assert {"muted text on background", "muted text on surface"} <= failed
	assert not contrast.failures(presets.load("clear")["tokens"])
