"""Static checks of the shipped files: no literal colours outside the presets, valid JSON, module layout."""

import json
import re
from pathlib import Path

from website_kit import __version__
from website_kit.theme import presets

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "website_kit"
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")


def test_no_literal_colours_in_the_stylesheet_or_templates():
	"""Every colour comes from a token, so every preset (the dark one included) restyles the whole page."""
	files = [PKG / "public" / "css" / "wk.css", *(PKG / "website_kit" / "web_template").rglob("*.html")]
	for path in files:
		text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
		assert not COLOUR.search(text), path.name


def test_templates_do_not_use_the_safe_filter():
	for path in (PKG / "website_kit" / "web_template").rglob("*.html"):
		assert "| safe" not in path.read_text(encoding="utf-8"), path.name


def test_templates_never_render_site_data_without_escaping():
	"""A `{{ name }}` of Website Settings data must carry `| wk_esc`; the `wk` values are escaped in Python."""
	for path in (PKG / "website_kit" / "web_template").rglob("*.html"):
		text = re.sub(r"\{#.*?#\}", "", path.read_text(encoding="utf-8"), flags=re.S)
		for expression in re.findall(r"\{\{(.*?)\}\}", text):
			expression = expression.strip()
			ok = (
				"| wk_esc" in expression
				or expression.startswith(("_(", "wk.", "url_prefix"))
				or "wk.brand_name" in expression
			)
			assert ok, (path.name, expression)


def test_json_files_are_valid_and_name_the_module():
	files = [path for folder in ("doctype", "web_template") for path in (PKG / "website_kit" / folder).rglob("*.json")]
	assert len(files) >= 4
	for path in files:
		assert json.loads(path.read_text(encoding="utf-8"))["module"] == "Website Kit", path


def test_the_module_is_listed():
	assert (PKG / "modules.txt").read_text(encoding="utf-8").strip() == "Website Kit"


def test_the_default_settings_match_the_presets():
	doctype = json.loads(
		(PKG / "website_kit/doctype/website_kit_settings/website_kit_settings.json").read_text(encoding="utf-8")
	)
	fields = {field["fieldname"]: field for field in doctype["fields"]}
	assert fields["preset"]["options"].split("\n") == list(presets.CHOICES)
	assert fields["preset"]["default"] == presets.DEFAULT_PRESET
	assert fields["allow_search_engines"]["default"] == "0"
	assert doctype["issingle"] == 1
	assert fields["custom_css"]["fieldtype"] == "Code" and not fields["custom_css"].get("read_only")
	assert fields["versions"]["options"] == "Website Kit Theme Version"
	assert {"token_overrides", "brand_name"} <= set(fields)
	assert fields["recaptcha_secret"]["fieldtype"] == "Password" and fields["contact_email"]["options"] == "Email"
	assert fields["pages_state"]["read_only"] == 1 and fields["pages_note"]["read_only"] == 1


def test_the_version_is_semver():
	assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_hooks_name_existing_functions():
	text = (PKG / "hooks.py").read_text(encoding="utf-8")
	for dotted in re.findall(r'"(website_kit\.[a-z_.]+)"', text):
		module, _, function = dotted.rpartition(".")
		if (ROOT / (dotted.replace(".", "/") + ".py")).is_file():
			continue  # a module: `jinja.methods` registers every function it defines
		source = (ROOT / (module.replace(".", "/") + ".py")).read_text(encoding="utf-8")
		assert f"def {function}(" in source, dotted
	assert 'app_license = "mit"' in text


def test_hooks_register_every_before_request_function_in_one_assignment():
	"""A second `before_request = [...]` line in hooks.py would silently replace the first (the contact guard hook and the kit's cache hook)."""
	text = (PKG / "hooks.py").read_text(encoding="utf-8")
	assert len(re.findall(r"^before_request\s*=", text, flags=re.M)) == 1
	assert "website_kit.runtime.before_request" in text and "website_kit.contact.before_request" in text
	for name in ("after_request", "update_website_context", "after_install", "after_migrate"):
		assert len(re.findall(rf"^{name}\s*=", text, flags=re.M)) == 1, name
