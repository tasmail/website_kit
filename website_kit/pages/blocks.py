"""Builder block trees as plain data: small constructors, deterministic ids and the component instance skeleton.

A Builder page stores its tree as JSON (`blocks`). Everything here is pure Python so the trees can be unit-tested, hashed and
compared without a site. Ids are derived from a stable path, never from a random value, so building a page twice gives the
same bytes (the sync step decides by hash whether a page changed).

Styles use only the documented `--wk-*` custom properties (docs/theming.md) and never a literal colour, so every preset
restyles every page. Text goes into `innerHTML`; Builder renders it through Jinja, so a value from the site is only ever put
there by a Jinja function that escapes it (`website_kit.jinja_api`), never by string concatenation here.
"""

import copy
import hashlib
import json

PX = "var(--wk-space-unit)"


def space(factor) -> str:
	"""A length in units of `--wk-space-unit`."""
	return f"calc(var(--wk-space-unit) * {factor})"


class Ids:
	"""Deterministic block ids: `<scope>-<n>` per scope, so a change in one page never renumbers another."""

	def __init__(self, scope: str):
		self.scope = scope
		self.count = 0

	def next(self) -> str:
		self.count += 1
		digest = hashlib.sha256(f"{self.scope}:{self.count}".encode()).hexdigest()[:8]
		return digest


def block(
	ids: Ids,
	element: str = "div",
	*,
	name: str | None = None,
	html: str | None = None,
	styles: dict | None = None,
	tablet: dict | None = None,
	mobile: dict | None = None,
	classes: list | None = None,
	attrs: dict | None = None,
	custom: dict | None = None,
	children: list | None = None,
	**extra,
) -> dict:
	"""One block. Only the keys that are set are present, so the stored JSON stays small."""
	result = {"blockId": ids.next(), "element": element}
	if name:
		result["blockName"] = name
	if styles:
		result["baseStyles"] = dict(styles)
	if tablet:
		result["tabletStyles"] = dict(tablet)
	if mobile:
		result["mobileStyles"] = dict(mobile)
	if classes:
		result["classes"] = list(classes)
	if attrs:
		result["attributes"] = dict(attrs)
	if custom:
		result["customAttributes"] = dict(custom)
	if html is not None:
		result["innerHTML"] = html
	result["children"] = list(children or [])
	result.update(extra)
	return result


def raw(
	ids: Ids, html: str, *, name: str | None = None, styles: dict | None = None, custom: dict | None = None
) -> dict:
	"""A raw HTML block (inline SVG, or a Jinja call that returns markup). Not editable as text in the canvas."""
	return block(ids, "div", name=name, html=html, styles=styles, custom=custom, originalElement="__raw_html__")


def root(ids: Ids, children: list, *, styles: dict | None = None) -> dict:
	"""The root of a page. `originalElement: body` is load-bearing: without it Builder drops the page scripts."""
	base = {"display": "flex", "flexDirection": "column", "minHeight": "100vh"}
	base.update(styles or {})
	return block(ids, "div", name="body", styles=base, children=children, originalElement="body")


def component_definition(ids: Ids, component_id: str, element: str, **kwargs) -> dict:
	"""The root block of a component definition; its blockId stays the same across releases (instances point at ids)."""
	return block(ids, element, name=component_id, **kwargs)


def instance(ids: Ids, component_id: str, definition: dict, *, overrides: dict | None = None) -> dict:
	"""A page-side instance of a component: the root and a skeleton of refs that mirror the definition.

	`overrides` maps a definition blockId to the fields to override on this page (styles merge per key, text replaces).
	"""
	result = {
		"blockId": ids.next(),
		"element": definition.get("element") or "div",
		"blockName": definition.get("blockName") or component_id,
		"extendedFromComponent": component_id,
		"children": _skeleton(ids, definition.get("children"), component_id, overrides or {}),
	}
	if definition["blockId"] in (overrides or {}):
		result.update(overrides[definition["blockId"]])
	return result


def _skeleton(ids: Ids, children, owner: str, overrides: dict) -> list:
	refs = []
	for child in children or []:
		ref = {"blockId": ids.next(), "referenceBlockId": child["blockId"], "isChildOfComponent": owner}
		if child.get("isRepeaterBlock"):
			ref["isRepeaterBlock"] = True
		ref.update(overrides.get(child["blockId"], {}))
		ref["children"] = _skeleton(ids, child.get("children"), owner, overrides)
		refs.append(ref)
	return refs


def call(name: str, *args: str) -> str:
	"""A Jinja call of a kit function, as block text: `call("wk_head", "uk", "home")` is `{{ wk_head('uk', 'home') }}`."""
	return "{{ " + name + "(" + ", ".join(f"'{arg}'" for arg in args) + ") }}"


def dump(tree) -> str:
	"""The compact, key-sorted JSON that is stored and hashed."""
	return json.dumps(tree, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def digest(*parts) -> str:
	"""A short stable hash of JSON-able parts: the identity of a shipped page version."""
	return hashlib.sha256("\x1f".join(dump(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def walk(tree):
	"""Every block of a tree, depth first."""
	stack = [tree] if isinstance(tree, dict) else list(reversed(tree))
	while stack:
		item = stack.pop()
		yield item
		stack.extend(reversed(item.get("children") or []))


def clone(tree):
	return copy.deepcopy(tree)
