#!/usr/bin/env python3
"""Measure the standard pages of a running site: weight on the wire (gzip), script files, external resources.

    python scripts/check_pages.py --base http://127.0.0.1:8000 --host test.localhost

For each page it fetches the HTML and every same-origin stylesheet and script the HTML links, and sums the gzip size of the
documents (HTML, CSS, JS). The budget of the analysis is 40 KB for that sum, and no script file on Home and About (Contact has
one small script of its own, plus the guard client when the form is shown). Web fonts are woff2 (already compressed) and are
listed apart: they are a Setting of the preset, not part of the page. Exit code 1 when a budget or a rule is broken.
"""

import argparse
import gzip
import re
import sys
import urllib.request
from urllib.parse import quote, urljoin, urlparse

PAGES = ("/", "/about", "/contact", "/privacy", "/en", "/en/about", "/en/contact", "/en/privacy")
NO_SCRIPT_FILES = {"/", "/about", "/privacy", "/en", "/en/about", "/en/privacy"}
MAX_SCRIPT_FILES_CONTACT = 2  # the kit's contact script and, when the form is shown, the guard client
LINK = re.compile(r"<link\b[^>]*>", re.I)
SCRIPT_SRC = re.compile(r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.I)
HREF = re.compile(r"\bhref=[\"']([^\"']+)[\"']", re.I)
REL = re.compile(r"\brel=[\"']([^\"']+)[\"']", re.I)
FONT_URL = re.compile(r"url\(([^)]+\.woff2[^)]*)\)", re.I)


def get(base: str, host: str, path: str) -> bytes:
	url = urljoin(base, quote(path, safe="/:?=&%"))
	request = urllib.request.Request(url, headers={"Host": host, "Accept-Encoding": "identity"})
	with urllib.request.urlopen(request, timeout=30) as response:
		return response.read()


def gzipped(data: bytes) -> int:
	return len(gzip.compress(data, 9))


def measure(base: str, host: str, path: str) -> dict:
	html = get(base, host, path + ("?fresh=1" if "?" not in path else "")).decode("utf-8")
	styles, scripts, external = [], SCRIPT_SRC.findall(html), []
	for tag in LINK.findall(html):
		rel = (REL.search(tag) or [None, ""])[1].lower()
		href = (HREF.search(tag) or [None, ""])[1]
		if "stylesheet" in rel:
			styles.append(href)
		if rel == "preconnect" and href.startswith("http"):
			external.append(f"preconnect {href}")
	total = gzipped(html.encode())
	sizes = {"html": total}
	fonts = {}
	for resource in [*styles, *scripts]:
		if urlparse(resource).netloc:
			external.append(resource)
			continue
		data = get(base, host, resource)
		sizes[resource.split("?")[0]] = gzipped(data)
		total += gzipped(data)
		if (
			resource in styles and "wk-theme" in resource
		):  # the fonts the kit's preset names (Builder's reset.css declares its own, unused)
			for font in FONT_URL.findall(data.decode("utf-8", "replace")):
				font = font.strip("'\" ")
				fonts[font.split("?")[0]] = len(get(base, host, font))
	return {"path": path, "total": total, "sizes": sizes, "scripts": scripts, "external": external, "fonts": fonts}


STOCK_PAGES = ("/login", "/no-such-page-for-the-check")


def stock_page_problems(base: str, host: str, path: str) -> list[str]:
	"""A stock Frappe page (login, the 404 page) must keep Frappe's own base stylesheet and never link `None`.

	The kit once assigned a Website Theme that had no compiled file: Frappe then printed `href="None"` and dropped website.bundle.css,
	which left the stock pages (the Webshop list included) without Bootstrap and the Frappe styles.
	"""
	import urllib.error

	url = urljoin(base, path)
	request = urllib.request.Request(url, headers={"Host": host, "Accept-Encoding": "identity"})
	try:
		html = urllib.request.urlopen(request, timeout=30).read().decode("utf-8", "replace")
	except urllib.error.HTTPError as error:  # the 404 page is a page too
		html = error.read().decode("utf-8", "replace")
	hrefs = [(HREF.search(tag) or [None, ""])[1] for tag in LINK.findall(html) if "stylesheet" in tag]
	problems = []
	if any(href in ("None", "", "/None") or href.endswith("/None") for href in hrefs):
		problems.append("a stylesheet link points at None")
	if not any("website.bundle" in href for href in hrefs):
		problems.append("Frappe's website.bundle.css is not linked")
	return problems


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument("--base", default="http://127.0.0.1:8000")
	parser.add_argument("--host", default="test.localhost")
	parser.add_argument("--budget-kb", type=float, default=40)
	args = parser.parse_args()
	failed = False
	for path in PAGES:
		result = measure(args.base, args.host, path)
		kb = result["total"] / 1024
		problems = []
		if kb > args.budget_kb:
			problems.append(f"over the budget of {args.budget_kb:g} KB")
		limit = 0 if path in NO_SCRIPT_FILES else MAX_SCRIPT_FILES_CONTACT
		if len(result["scripts"]) > limit:
			problems.append(f"{len(result['scripts'])} script files (allowed {limit}): {result['scripts']}")
		resources = [item for item in result["external"] if not item.startswith("preconnect")]
		if resources:
			problems.append(f"external resources: {resources}")
		print(
			f"{path:14} {kb:6.1f} KB gzip  scripts={len(result['scripts'])}  "
			+ ("FAIL " + "; ".join(problems) if problems else "ok")
		)
		for name, size in result["sizes"].items():
			print(f"    {name:60} {size / 1024:6.1f} KB")
		notes = [item for item in result["external"] if item.startswith("preconnect")]
		if notes:
			print(
				f"    note: the Builder template opens {', '.join(sorted(set(notes)))} (no request is made unless a font is used)"
			)
		if result["fonts"]:
			print(
				"    web fonts (woff2, not in the sum): "
				+ ", ".join(f"{name.rsplit('/', 1)[-1]} {size / 1024:.1f} KB" for name, size in result["fonts"].items())
			)
		failed = failed or bool(problems)
	for path in STOCK_PAGES:
		problems = stock_page_problems(args.base, args.host, path)
		print(f"{path:14} stock page  " + ("FAIL " + "; ".join(problems) if problems else "ok"))
		failed = failed or bool(problems)
	return 1 if failed else 0


if __name__ == "__main__":
	sys.exit(main())
