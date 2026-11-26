"""Whitelisted methods of the theme settings page. None is `allow_guest`: every one needs System Manager or Website Manager.

The logic lives in pure modules (`theme/editor.py`, `css_validator.py`) and in `apply.py`; this file only checks the role,
translates the messages and calls them, so a save, a draft, a preview and a restore all pass through `compiler.build`.
"""

import json

import frappe
from frappe import _

from . import apply as kit_apply
from . import css_validator
from .theme import compiler, editor, presets, tokens

SETTINGS = kit_apply.SETTINGS
ROLES = ("System Manager", "Website Manager")


def _guard() -> None:
	frappe.only_for(ROLES)


def _build(preset, token_overrides, custom_css, custom_base):
	"""Compile unsaved values, or raise a translated validation error."""
	base = (custom_base or "") or None
	try:
		return compiler.build(preset, token_overrides, custom_css or "", base)
	except tokens.TokenError as error:
		frappe.throw(_("Invalid theme settings: {0}").format(str(error)))
	except compiler.CustomCssError as error:
		frappe.throw(editor.rejection_html(error.result, _), title=_("The Custom CSS was rejected"))


@frappe.whitelist()
def theme_data() -> dict:
	"""The presets, fonts, token types and limits that the settings page draws its cards and editor from."""
	_guard()
	data = editor.theme_data()
	data["custom_css_enabled"] = kit_apply.custom_css_enabled()
	return data


@frappe.whitelist()
def preview(preset, token_overrides=None, custom_css="", custom_base=None) -> dict:
	"""The CSS of unsaved values, with contrast checks and the (translated) messages of the Custom CSS validator."""
	_guard()
	if not kit_apply.custom_css_enabled():
		custom_css = ""
	return editor.preview(preset, token_overrides, custom_css or "", (custom_base or "") or None, translate=_)


@frappe.whitelist()
def check_css(custom_css="") -> dict:
	"""Run the authoritative server validator on Custom CSS (the editor's "Check" button)."""
	_guard()
	return css_validator.validate(custom_css or "").as_dict(_)


@frappe.whitelist()
def duplicate_as_custom(preset, token_overrides=None, custom_base=None) -> dict:
	_guard()
	try:
		return editor.duplicate_as_custom(preset, token_overrides, (custom_base or "") or None)
	except tokens.TokenError as error:
		frappe.throw(_("Invalid theme settings: {0}").format(str(error)))


@frappe.whitelist(methods=["POST"])
def save_draft(preset, token_overrides=None, custom_css="", custom_base=None) -> dict:
	"""Write the unsaved look as a private draft file; only a Website Manager who opens `?wk_preview=1` sees it."""
	_guard()
	if not kit_apply.custom_css_enabled():
		custom_css = ""  # the same rule as `apply` and `preview`: the draft shows what a save would serve
	css, digest = _build(preset, token_overrides, custom_css, custom_base)
	state = json.dumps(
		{
			"preset": preset,
			"custom_base": custom_base or "",
			"token_overrides": token_overrides or "",
			"custom_css": custom_css or "",
			"hash": digest,
		}
	)
	with kit_apply.apply_lock():  # two drafts at once must not create two draft files
		url = kit_apply.write_draft(css)
		frappe.db.set_single_value(SETTINGS, {"draft_state": state, "draft_file_url": url})
		frappe.clear_document_cache(SETTINGS, SETTINGS)
	return {"url": url, "hash": digest, "preview_url": "/?wk_preview=1", "safe_url": "/?wk_safe=1"}


@frappe.whitelist(methods=["POST"])
def discard_draft() -> bool:
	_guard()
	with kit_apply.apply_lock():
		return kit_apply.discard_draft()


def _save(values: dict, reason: str):
	settings = frappe.get_doc(SETTINGS)
	settings.update(values)
	settings.flags.version_reason = reason
	settings.save()
	return settings


@frappe.whitelist(methods=["POST"])
def restore_version(version) -> dict:
	"""Make a saved version the current look; this saves it as a new version, so nothing is lost."""
	_guard()
	settings = frappe.get_doc(SETTINGS)
	row = next((r for r in settings.versions if r.name == version), None)
	if row is None:
		frappe.throw(_("This version does not exist any more."))
	_save(
		{
			"preset": row.preset,
			"custom_base": row.custom_base,
			"token_overrides": row.token_overrides,
			"custom_css": row.custom_css,
		},
		_("Restored a version"),
	)
	return {"theme_hash": frappe.db.get_single_value(SETTINGS, "theme_hash")}


@frappe.whitelist(methods=["POST"])
def reset_custom_css() -> dict:
	_guard()
	_save({"custom_css": ""}, _("Custom CSS reset"))
	return {"theme_hash": frappe.db.get_single_value(SETTINGS, "theme_hash")}


@frappe.whitelist(methods=["POST"])
def reset_to_preset() -> dict:
	"""Back to the plain ready-made look: no token overrides and no Custom CSS (a `custom` theme returns to its base)."""
	_guard()
	settings = frappe.get_doc(SETTINGS)
	preset = settings.custom_base or presets.DEFAULT_PRESET if settings.preset == presets.CUSTOM else settings.preset
	_save({"preset": preset, "custom_base": "", "token_overrides": "", "custom_css": ""}, _("Reset to the preset"))
	return {"theme_hash": frappe.db.get_single_value(SETTINGS, "theme_hash")}


# ---------------------------------------------------------------- the shop and the existing sites


@frappe.whitelist()
def shop_status() -> dict:
	_guard()
	from . import shop

	return shop.status()


@frappe.whitelist(methods=["POST"])
def enable_shop() -> dict:
	_guard()
	from . import shop

	return shop.enable_shop()


@frappe.whitelist(methods=["POST"])
def load_samples() -> dict:
	_guard()
	from . import shop

	return shop.load_samples()


@frappe.whitelist(methods=["POST"])
def remove_samples() -> dict:
	_guard()
	from . import shop

	return shop.remove_samples()


@frappe.whitelist(methods=["POST"])
def personalize() -> dict:
	"""Opt-in: copy the company name and contact data into the kit settings on a site that never ran the wizard stage."""
	_guard()
	from . import setup

	return setup.personalize()
