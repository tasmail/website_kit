"""A browser oracle for the CSS validator: load CSS in headless Chromium and list every request that leaves the allow-list.

The page is served from a made-up origin and every request is intercepted (nothing reaches the network). The oracle applies
all declarations of the CSS to probe elements (a div, a list item, their ::before and ::after) so that images, list markers
and borders are really resolved, then reports each URL that is not a same-origin `/files/` or `/assets/` path or a `data:` URL.
It does not look at the source text at all, so it sees what a parser-based or pattern-based check can miss, such as a string in a
custom property that `image-set(var(...))` turns into an address.
"""

ORIGIN = "http://wk-probe.test"
ALLOWED_PREFIXES = (ORIGIN + "/files/", ORIGIN + "/assets/", "data:")
IGNORED = (ORIGIN + "/", ORIGIN + "/favicon.ico")

APPLY = """(css) => {
	const sheet = document.createElement('style');
	sheet.textContent = css;
	document.head.appendChild(sheet);
	const declarations = [];
	const walk = (rules) => {
		for (const rule of rules) {
			if (rule.style && rule.cssText && !rule.cssText.startsWith('@font-face')) declarations.push(rule.style.cssText);
			if (rule.cssRules) walk(rule.cssRules);
		}
	};
	if (sheet.sheet) walk(sheet.sheet.cssRules);
	const text = declarations.join(';');
	const probe = document.createElement('style');
	probe.textContent = '.wk-probe, .wk-probe::before, .wk-probe::after { ' + text + ' } li.wk-probe { display: list-item; }';
	document.head.appendChild(probe);
	for (const tag of ['div', 'li', 'p']) {
		const element = document.createElement(tag);
		element.className = 'wk-probe';
		element.textContent = 'x';
		document.body.appendChild(element);
		getComputedStyle(element).backgroundImage;
		getComputedStyle(element, '::before').content;
	}
	return text.length;
}"""


def violations(browser, css_list, settle_ms=150):
	"""For each CSS text, the list of requested URLs outside the allow-list."""
	results = []
	context = browser.new_context()
	for css in css_list:
		page = context.new_page()
		seen = []

		def handle(route, request, seen=seen):
			url = request.url
			if url == ORIGIN + "/":
				route.fulfill(status=200, content_type="text/html", body="<!doctype html><html><body></body></html>")
				return
			if url not in IGNORED:
				seen.append(url)
			route.fulfill(
				status=200,
				content_type="image/gif",
				body=b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
			)

		page.route("**/*", handle)
		page.goto(ORIGIN + "/")
		try:
			page.evaluate(APPLY, css)
		except Exception:
			pass  # CSS that the browser cannot even parse into rules requests nothing
		page.wait_for_timeout(settle_ms)
		results.append([url for url in seen if not url.startswith(ALLOWED_PREFIXES)])
		page.close()
	context.close()
	return results
