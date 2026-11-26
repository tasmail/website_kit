"""Patch rules (website_kit/patches/__init__.py): a patch never writes the customer's tokens or Custom CSS."""

import re
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "website_kit"
FORBIDDEN = re.compile(r"token_overrides|custom_css")


def patch_modules():
	return [path for path in (PKG / "patches").rglob("*.py") if path.name != "__init__.py"]


def test_patches_txt_has_both_sections():
	lines = [line.strip() for line in (PKG / "patches.txt").read_text(encoding="utf-8").splitlines()]
	assert "[pre_model_sync]" in lines and "[post_model_sync]" in lines


def test_listed_patches_exist():
	lines = (PKG / "patches.txt").read_text(encoding="utf-8").splitlines()
	for line in lines:
		line = line.split("#")[0].strip()
		if line and not line.startswith("["):
			module = line.split()[0]
			assert (PKG.parent / (module.replace(".", "/") + ".py")).is_file(), module


def test_no_patch_touches_the_customers_data():
	for path in patch_modules():
		assert not FORBIDDEN.search(path.read_text(encoding="utf-8")), path.name


def test_the_rule_is_written_down():
	doc = (PKG / "patches" / "__init__.py").read_text(encoding="utf-8")
	assert "never writes `token_overrides` or `custom_css`" in doc


def test_the_runtime_and_apply_never_write_the_customers_fields():
	"""`apply` records only the status fields; the two customer fields are read, never set."""
	for name in ("apply.py", "install.py"):
		source = (PKG / name).read_text(encoding="utf-8")
		assert not re.search(r"(token_overrides|custom_css)\s*=(?!=)", source), name
		assert not re.search(r"set_single_value\([^)]*(token_overrides|custom_css)", source), name


def test_only_the_files_the_retired_theme_generated_are_removed():
	"""`website_kit_<8 hex>.css` and `website_kit_style.css`; a customer theme named "Website Kit 2" keeps its files."""
	from website_kit import settings_sync

	for name in ("website_kit_0a1b2c3d.css", "website_kit_style.css"):
		assert settings_sync.is_retired_theme_file(name), name
	for name in (
		"website_kit_2_0a1b2c3d.css",  # theme "Website Kit 2"
		"website_kit_extra.css",
		"website_kit_0a1b2c3.css",  # seven characters
		"website_kit_0A1B2C3D.css",
		"website_kit_0a1b2c3d.css.bak",
		"my_website_kit_0a1b2c3d.css",
		"website_kit_.css",
		"website_kit_style.css\n",
	):
		assert not settings_sync.is_retired_theme_file(name), name


def test_the_patch_uses_that_rule_and_not_a_prefix_match():
	source = (PKG / "patches" / "v0_3" / "use_stock_website_theme.py").read_text(encoding="utf-8")
	assert "is_retired_theme_file" in source and "startswith" not in source
