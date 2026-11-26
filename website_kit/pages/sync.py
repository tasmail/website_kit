"""Write the shipped Builder objects into a site, following the upgrade policy (`policy.py`).

Builder's own import of `builder_files` overwrites a record whenever the shipped file is newer, which would replace a
customer's edit on the next release. So the kit does not use that folder: it builds its objects from `specs.py` and applies
policy 5.8 itself. The step needs Builder; without it nothing is written and nothing fails (the theme works alone).

It returns what it changed (empty on a repeat), writes nothing when nothing differs, and never raises into the caller's
install or migrate: the callers wrap it.
"""

import json

import frappe

from . import policy, specs
from .blocks import digest, dump

SETTINGS = "Website Kit Settings"
STATE_FIELD = "pages_state"
NOTE_FIELD = "pages_note"
PAGE = "Builder Page"


def builder_ready() -> bool:
	return "builder" in frappe.get_installed_apps() and bool(frappe.db.exists("DocType", PAGE))


def _load_state() -> dict:
	raw = frappe.db.get_single_value(SETTINGS, STATE_FIELD)
	try:
		value = json.loads(raw) if raw else {}
	except ValueError:
		return {}
	return value if isinstance(value, dict) else {}


def _save(field: str, value: str) -> bool:
	if (frappe.db.get_single_value(SETTINGS, field) or "") == value:
		return False
	frappe.db.set_single_value(SETTINGS, field, value)
	frappe.clear_document_cache(SETTINGS, SETTINGS)
	return True


def _modified(kind: str, name: str) -> str:
	return str(frappe.db.get_value(kind, name, "modified") or "")


def current_fields(kind: str, name: str) -> dict:
	"""The fields of a record in the shape of the shipped spec (to tell an identical record from a changed one)."""
	doc = frappe.get_doc(kind, name)
	if kind == PAGE:
		return {
			"page_title": doc.page_title,
			"route": doc.route,
			"language": doc.language,
			"meta_description": doc.meta_description,
			"blocks": _normalized(doc.blocks),
			"head_html": doc.head_html or "",
			"published": int(doc.published or 0),
			"disable_indexing": int(doc.disable_indexing or 0),
			"page_data_script": doc.page_data_script or "",
			"client_scripts": [row.builder_script for row in doc.client_scripts],
		}
	if kind == "Builder Component":
		return {"component_id": doc.component_id, "component_name": doc.component_name, "block": _normalized(doc.block)}
	return {"script_type": doc.script_type, "script": doc.script}


def _normalized(text):
	try:
		return dump(json.loads(text or "[]"))
	except ValueError:
		return text or ""


def _write(kind: str, name: str, fields: dict, create: bool) -> None:
	values = dict(fields)
	scripts = values.pop("client_scripts", None)
	if create:
		doc = frappe.get_doc({"doctype": kind, "name": name, **values})
		if kind == "Builder Client Script":
			doc.name = name
		if scripts is not None:
			doc.set("client_scripts", [{"builder_script": script} for script in scripts])
		# Frappe discards a given name unless the insert is an import: the pages have fixed names so they can be found again.
		frappe.flags.in_import = True
		try:
			doc.insert(ignore_permissions=True)
		finally:
			frappe.flags.in_import = False
		return
	doc = frappe.get_doc(kind, name)
	doc.update(values)
	if scripts is not None:
		doc.set("client_scripts", [{"builder_script": script} for script in scripts])
	doc.save(ignore_permissions=True)


def _draft_fields(spec: dict, shipped: str) -> dict:
	fields = dict(spec["fields"])
	fields["route"] = policy.draft_route(fields["route"], shipped)
	fields["published"] = 0
	fields["disable_indexing"] = 1
	fields["page_title"] = f"{fields['page_title']} (new kit version)"
	return fields


def sync() -> dict:
	"""Apply the shipped objects; returns `{object: action}` for what was written, `{}` when nothing was."""
	if not builder_ready():
		frappe.logger("website_kit").info("Builder is not installed: the standard pages were not written")
		return {}
	state = _load_state()
	changes, notes = {}, []
	for spec in specs.all_specs():
		kind, name, shipped = spec["kind"], spec["name"], spec["hash"]
		key = f"{kind}:{name}"
		exists = bool(frappe.db.exists(kind, name))
		is_page = kind == PAGE
		decision = policy.decide(
			exists=exists,
			state=state.get(key),
			modified=_modified(kind, name) if exists else None,
			shipped_hash=shipped,
			current_hash=digest(current_fields(kind, name)) if exists and not state.get(key) else None,
			route_taken=bool(
				is_page
				and not exists
				and frappe.db.exists(PAGE, {"route": spec["fields"]["route"], "name": ["!=", name]})
			),
			has_draft=is_page,
		)
		draft = None
		if decision.action == policy.CREATE:
			_write(kind, name, spec["fields"], create=True)
		elif decision.action == policy.UPDATE:
			_write(kind, name, spec["fields"], create=False)
		elif decision.action == policy.DRAFT:
			draft = policy.draft_name(name, shipped)
			if not frappe.db.exists(kind, draft):
				_write(kind, draft, _draft_fields(spec, shipped), create=True)
		if decision.action not in (policy.KEEP, policy.ADOPT, policy.DELETED):
			line = policy.note_line(name, decision, draft)
			if line:
				notes.append(line)
		if decision.action in (policy.CREATE, policy.UPDATE, policy.DRAFT):
			changes[key] = decision.action
		new_state = policy.next_state(
			state.get(key),
			decision,
			shipped,
			_modified(kind, name) if exists or decision.action == policy.CREATE else None,
		)
		if new_state is None:
			state.pop(key, None)
		else:
			state[key] = new_state
	if _save(STATE_FIELD, json.dumps(state, sort_keys=True)):
		changes["pages_state"] = "recorded"
	merged = policy.merge_notes(frappe.db.get_single_value(SETTINGS, NOTE_FIELD), notes)
	if _save(NOTE_FIELD, merged):
		changes["pages_note"] = "updated"
	changes.update(set_home_page())
	if changes:
		from frappe.website.utils import clear_website_cache

		clear_website_cache()
	return changes


def set_home_page() -> dict:
	"""Point `/` at the Ukrainian home page where the customer has not chosen a home page."""
	home = specs.ROUTES_HOME
	if not frappe.db.exists(PAGE, {"route": home, "published": 1}):
		return {}
	changes = policy.home_page_changes(
		frappe.db.get_single_value("Website Settings", "home_page"),
		frappe.db.get_single_value("Builder Settings", "home_page"),
		home,
	)
	if "website_settings.home_page" in changes:
		website_settings = frappe.get_doc("Website Settings")
		website_settings.home_page = home
		website_settings.save(ignore_permissions=True)
	if "builder_settings.home_page" in changes:
		frappe.db.set_single_value("Builder Settings", "home_page", home)
	return changes
