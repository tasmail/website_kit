"""The shipped objects as data: Builder Pages, Components and the client script, with a content hash for each.

`page_specs()` and friends are pure and deterministic: the same release always gives the same bytes. The sync step
(`website_kit/pages/sync.py`) compares these hashes with what it recorded to decide, object by object, what may be written
(policy 5.8 of the analysis, in `website_kit/pages/policy.py`).
"""

from pathlib import Path

from . import catalogue, sections
from .blocks import call, digest, dump
from .content import LANGUAGES, ROUTES, TEXT

PAGE_KEYS = ("home", "about", "contact", "privacy")
SCRIPT_NAME = "WK Contact"
SCRIPT_FILE = Path(__file__).with_name("wk_contact.js")
# Which page of which kind lives in a Builder Page of this name.
PAGE_NAME = "wk-{key}-{lang}"
COMPONENT_KINDS = tuple(sections.COMPONENTS)
ROUTES_HOME = ROUTES["home"]["uk"]


def component_definitions() -> dict:
	"""`{component_id: root block}` for the shared header, footer and call to action in both languages."""
	return {
		sections.component_id(kind, lang): build(lang)
		for kind, build in sections.COMPONENTS.items()
		for lang in LANGUAGES
	}


def component_specs() -> list[dict]:
	specs = []
	for component_id, definition in component_definitions().items():
		fields = {"component_id": component_id, "component_name": definition["blockName"], "block": dump(definition)}
		specs.append({"kind": "Builder Component", "name": component_id, "fields": fields, "hash": digest(fields)})
	return specs


def script_text() -> str:
	return SCRIPT_FILE.read_text(encoding="utf-8")


def script_spec() -> dict:
	fields = {"script_type": "JavaScript", "script": script_text()}
	return {"kind": "Builder Client Script", "name": SCRIPT_NAME, "fields": fields, "hash": digest(fields)}


def page_specs() -> list[dict]:
	definitions = component_definitions()
	specs = []
	for key in PAGE_KEYS:
		for lang in LANGUAGES:
			t = TEXT[lang]
			tree = sections.page_tree(lang, key, definitions)
			fields = {
				"page_title": t[f"{key}_title"],
				"route": ROUTES[key][lang],
				"language": lang,
				"meta_description": t[f"{key}_description"],
				"blocks": dump(tree),
				"head_html": call("wk_head", lang, key),
				"published": 1,
				# The privacy text holds placeholders until the customer fills them in: never indexed as shipped.
				"disable_indexing": 1 if key == "privacy" else 0,
				"page_data_script": {
					"home": catalogue.DATA_SCRIPT,
					"contact": catalogue.CONTACT_SCRIPT,
					"privacy": catalogue.CONTACT_SCRIPT,
				}.get(key, ""),
				"client_scripts": [SCRIPT_NAME] if key == "contact" else [],
			}
			name = PAGE_NAME.format(key=key, lang=lang)
			specs.append(
				{
					"kind": "Builder Page",
					"name": name,
					"fields": fields,
					"hash": digest(fields),
					"key": key,
					"lang": lang,
				}
			)
	return specs


def all_specs() -> list[dict]:
	"""Dependencies first: the script and the components, then the pages that use them."""
	return [script_spec(), *component_specs(), *page_specs()]
