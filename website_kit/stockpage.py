"""What the stock navbar adds besides the menu, as pure functions (no Frappe).

Frappe's own pages (login, update-password, signup) replace the whole `head_include` block, so the kit's stylesheet links would never
reach them; the WK Navbar template therefore emits the links itself, and the two scripts below with them:

* the file-uploader guard: Frappe's website bundle calls `frappe.require("file_uploader.bundle.js")` on every page, and on a website
  page `frappe.boot.assets_json` does not exist, so the call fails with an uncaught promise rejection. The guard wraps
  `frappe.require` the moment the bundle assigns it and skips only that one call while the asset map is missing;
* the Webshop strings: Frappe loads no translations into website pages, so the JavaScript of Webshop (`__("Add to Cart")`) stays
  English. The server translates the strings that Webshop's scripts use and hands them over as one JSON block.
"""

import functools
from pathlib import Path

from .pages.markup import json_script
from .theme.escape import esc

I18N_ID = "wk-webshop-i18n"
# Rows of uk.csv with this context are the shop wording where Frappe's translation of the same word means something else on a shop
# page ("Submit" is "Провести", a posting, in the Desk). Only `translated()` asks for the context, so the Desk is not affected.
CONTEXT = "Webshop page"
JS_SOURCES = Path(__file__).resolve().parent / "translations" / "webshop_js_sources.txt"

# Installed in the navbar, i.e. after `window.frappe = {}` of the page head and before the website bundle.
GUARD_SCRIPT = """(function (f) {
	var wrapped;
	var guard = function (original) {
		return function (links) {
			if (links === "file_uploader.bundle.js" && !(f.boot && f.boot.assets_json)) return Promise.resolve();
			return original.apply(this, arguments);
		};
	};
	if (typeof f.require === "function") wrapped = guard(f.require);
	Object.defineProperty(f, "require", {
		configurable: true,
		enumerable: true,
		get: function () { return wrapped; },
		set: function (fn) { wrapped = typeof fn === "function" ? guard(fn) : fn; }
	});
})(window.frappe);"""

LOADER_SCRIPT = (
	"(function (f) {"
	f'var e = document.getElementById("{I18N_ID}");'
	"if (!e) return;"
	"try { f._messages = Object.assign(f._messages || {}, JSON.parse(e.textContent)); } catch (x) {}"
	"})(window.frappe);"
)


def links(base_css: str, theme_css: str = "", shop_css: str = "") -> str:
	"""The stylesheet links: the base sheet, the generated token file, and the shop sheet on shop pages.

	The caller passes URLs it has already validated (`runtime.theme_link`); they are escaped here as attribute values."""
	hrefs = [base_css, theme_css, shop_css]
	return "".join(f'<link rel="stylesheet" href="{esc(href)}">' for href in hrefs if href)


def i18n(messages: dict) -> str:
	"""The JSON block of translated Webshop strings and the script that merges it into `frappe._messages`; empty for no strings."""
	if not messages:
		return ""
	return f'<script type="application/json" id="{I18N_ID}">{json_script(messages)}</script><script>{LOADER_SCRIPT}</script>'


def scripts(*, guard: bool, messages: dict) -> str:
	"""Both scripts, in the order they must run."""
	return (f"<script>{GUARD_SCRIPT}</script>" if guard else "") + i18n(messages)


@functools.cache
def js_sources() -> tuple[str, ...]:
	"""The source strings that Webshop's browser scripts translate (translations/webshop_js_sources.txt)."""
	lines = JS_SOURCES.read_text(encoding="utf-8").splitlines()
	return tuple(line for line in lines if line and not line.startswith("#"))


def translated(translate) -> dict:
	"""`{source: translation}` for the Webshop script strings; `translate(source, context)` is `frappe._` with the context as the
	second argument. A row with the context `CONTEXT` wins, else the ordinary translation; strings without one are left out."""
	found = {source: translate(source, CONTEXT) for source in js_sources()}
	return {source: text for source, text in found.items() if text and text != source}
