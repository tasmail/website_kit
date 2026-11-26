"""Escaping of site data that is written into HTML or into Jinja templates.

Frappe renders Web Templates, Builder blocks and Website Settings fields through Jinja. A name from the database such as
`{{ 7*7 }}` must never be read as a template, even when the output is rendered a second time. `esc` therefore encodes the
braces as HTML entities after the HTML escape (the rule of the parta pilot, `parta_site.pages.esc`).
"""

from html import escape

SAFE_URL_PREFIXES = ("/files/", "/assets/", "https://")


def esc(text) -> str:
	"""HTML-escaped text or attribute value with the braces encoded."""
	return escape("" if text is None else str(text), quote=True).replace("{", "&#123;").replace("}", "&#125;")


def wk_esc(text) -> str:
	"""The Jinja filter `wk_esc` (registered in hooks.py): `esc` for the standard templates."""
	return esc(text)


def safe_url(url) -> str:
	"""The URL if it is a same-site file or an https URL without markup characters, else an empty string."""
	text = "" if url is None else str(url).strip()
	if not text.startswith(SAFE_URL_PREFIXES) or text.startswith("//"):
		return ""
	if any(char in text for char in "<>\"'`{}\\ \t\r\n"):
		return ""
	return text
