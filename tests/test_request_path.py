"""`_request_path()` of the Jinja API: the page the language button belongs to, as Frappe resolved it."""

import importlib
import sys
import types
from types import SimpleNamespace

import pytest

from website_kit.pages import header
from website_kit.pages.content import ROUTES


@pytest.fixture
def jinja_api():
	"""`website_kit.jinja_api` imported against a stand-in `frappe` (the unit job has no Frappe); everything is put back after."""
	saved = {name: module for name, module in sys.modules.items() if name.split(".")[0] in ("frappe", "website_kit")}
	frappe = types.ModuleType("frappe")
	frappe.local = SimpleNamespace()
	frappe._ = lambda text, *args, **kwargs: text
	frappe.utils = types.ModuleType("frappe.utils")
	frappe.get_installed_apps = list
	for name in [name for name in saved if name.startswith("website_kit.") and name != "website_kit.pages"]:
		sys.modules.pop(name)
	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = frappe.utils
	try:
		yield importlib.import_module("website_kit.jinja_api")
	finally:
		for name in [name for name in sys.modules if name.split(".")[0] in ("frappe", "website_kit")]:
			sys.modules.pop(name)
		sys.modules.update(saved)
		package = sys.modules["website_kit"]
		for name in [*saved, "website_kit.jinja_api"]:
			child = name.removeprefix("website_kit.")
			if name.startswith("website_kit.") and "." not in child:
				if name in saved:
					setattr(package, child, saved[name])
				elif hasattr(package, child):
					delattr(package, child)


def test_the_resolved_path_comes_first(jinja_api):
	"""Frappe strips `.html`, turns `/index` into the home page and writes the result to `frappe.local.path`."""
	jinja_api.frappe.local.path = "about"
	jinja_api.frappe.local.request = SimpleNamespace(path="/about.html")
	assert jinja_api._request_path() == "about"


def test_the_request_path_is_the_fallback(jinja_api):
	jinja_api.frappe.local.request = SimpleNamespace(path="/en/about")
	assert jinja_api._request_path() == "/en/about"


def test_an_empty_resolved_path_falls_back_to_the_request(jinja_api):
	jinja_api.frappe.local.path = ""
	jinja_api.frappe.local.request = SimpleNamespace(path="/contact")
	assert jinja_api._request_path() == "/contact"


def test_outside_a_request_the_path_is_empty(jinja_api):
	assert jinja_api._request_path() == ""


ALL_ROUTES = {route for by_lang in ROUTES.values() for route in by_lang.values()}


@pytest.mark.parametrize(
	("resolved", "request_path", "lang", "target"),
	[
		("about", "/about.html", "uk", "/en/about"),
		("en/about", "/en/about.html", "en", "/about"),
		("home", "/index", "uk", "/en"),
		("home", "/index.html", "uk", "/en"),
		("en/privacy", "/en/privacy.html", "en", "/privacy"),
	],
)
def test_an_alias_leads_to_the_twin_of_the_page_it_stands_for(jinja_api, resolved, request_path, lang, target):
	jinja_api.frappe.local.path = resolved
	jinja_api.frappe.local.request = SimpleNamespace(path=request_path)
	assert header.switch_target(jinja_api._request_path(), lang, ALL_ROUTES) == target
