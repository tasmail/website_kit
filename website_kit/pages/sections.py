"""The sections of the standard pages as block trees, one function per section, shared by Home, About and Contact.

Layout uses `--wk-*` tokens only (docs/theming.md) and the documented classes (`wk-container`, `wk-card`, `wk-button`,
`wk-product-card`, `wk-header`, `wk-footer`). Grids use `auto-fit` columns, so no breakpoint rules are needed.
"""

from . import art
from .blocks import Ids, block, call, instance, raw, root, space
from .content import TEXT, URLS


def link(ids, label, href, *, classes=None, attrs=None, styles=None, name=None):
	return block(
		ids,
		"a",
		name=name,
		html=label,
		classes=classes,
		attrs={"href": href, **(attrs or {})},
		styles=styles,
	)


def heading(ids, level, html, *, styles=None, name=None):
	return block(ids, f"h{level}", name=name, html=html, styles={"margin": "0", **(styles or {})})


def paragraph(ids, html, *, styles=None, name=None):
	return block(ids, "p", name=name, html=html, styles={"margin": "0", **(styles or {})})


def container(ids, children, *, styles=None, name=None):
	return block(
		ids,
		"div",
		name=name,
		classes=["wk-container"],
		styles={"inlineSize": "100%", **(styles or {})},
		children=children,
	)


def section(ids, children, *, name=None, band=False, styles=None):
	"""A full-width band: vertical rhythm from `--wk-section-gap`, optionally on the surface colour."""
	base = {"paddingBlock": "var(--wk-section-gap)"}
	if band:
		base["backgroundColor"] = "var(--wk-color-surface)"
	base.update(styles or {})
	return block(ids, "section", name=name, styles=base, children=[container(ids, children)])


def stack(ids, children, *, gap=2, styles=None, name=None):
	return block(
		ids,
		"div",
		name=name,
		styles={"display": "flex", "flexDirection": "column", "gap": space(gap), **(styles or {})},
		children=children,
	)


def grid(ids, children, *, min_width="260px", gap=3, styles=None, name=None, **extra):
	return block(
		ids,
		"div",
		name=name,
		styles={
			"display": "grid",
			"gridTemplateColumns": f"repeat(auto-fit, minmax(min({min_width}, 100%), 1fr))",
			"gap": space(gap),
			**(styles or {}),
		},
		children=children,
		**extra,
	)


def buttons(ids, items):
	"""A row of buttons: `(label, href, secondary)` tuples."""
	links = [
		link(ids, label, href, classes=["wk-button", "wk-button--secondary"] if secondary else ["wk-button"])
		for label, href, secondary in items
	]
	return block(ids, "div", styles={"display": "flex", "flexWrap": "wrap", "gap": space(1.5)}, children=links)


def card(ids, title, text):
	return block(
		ids,
		"div",
		classes=["wk-card"],
		styles={"display": "flex", "flexDirection": "column", "gap": space(1)},
		children=[heading(ids, 3, title), paragraph(ids, text, styles={"color": "var(--wk-color-muted)"})],
	)


# --- shared components -------------------------------------------------------------------------------------------------


def header_definition(lang):
	"""The shared header: one raw block whose markup comes from `jinja_api.wk_header`, the function that the stock navbar of
	the standard pages calls too, so a Builder page and a stock page (login, shop, 404) always show the same menu."""
	ids = Ids(f"header-{lang}")
	menu = raw(ids, call("wk_header", lang), name="menu")
	return block(ids, "header", name=f"WK Header {lang}", classes=["wk-header"], children=[menu])


def footer_definition(lang):
	"""The shared footer: four links, the contact facts the customer entered, the copyright line."""
	t, ids = TEXT[lang], Ids(f"footer-{lang}")
	links = [
		(t["menu_home"], URLS["home"][lang]),
		(t["menu_about"], URLS["about"][lang]),
		(t["menu_contact"], URLS["contact"][lang]),
		(t["footer_privacy"], URLS["privacy"][lang]),
	]
	nav = block(
		ids,
		"nav",
		custom={"aria-label": t["footer_nav"]},
		children=[
			block(
				ids,
				"ul",
				classes=["wk-footer__links"],
				children=[block(ids, "li", children=[link(ids, label, href)]) for label, href in links],
			)
		],
	)
	facts = raw(ids, call("wk_contact_list", lang, "footer"), name="facts")
	copy = block(ids, "p", name="copyright", classes=["wk-footer__copy"], html="&copy; " + call("wk_brand", lang))
	inner = block(ids, "div", classes=["wk-container", "wk-footer__inner"], children=[nav, facts, copy])
	return block(ids, "footer", name=f"WK Footer {lang}", classes=["wk-footer"], children=[inner])


def cta_definition(lang):
	"""The shared call to action: a surface card with a heading, a line and a button to the contact page."""
	t, ids = TEXT[lang], Ids(f"cta-{lang}")
	inner = block(
		ids,
		"div",
		classes=["wk-card"],
		styles={
			"display": "flex",
			"flexWrap": "wrap",
			"alignItems": "center",
			"justifyContent": "space-between",
			"gap": space(3),
			"padding": space(5),
		},
		children=[
			stack(
				ids,
				[
					heading(ids, 2, t["cta_title"], name="cta-title"),
					paragraph(ids, t["cta_text"], styles={"color": "var(--wk-color-muted)"}, name="cta-text"),
				],
				gap=1,
			),
			link(ids, t["cta_button"], URLS["contact"][lang], classes=["wk-button"], name="cta-button"),
		],
	)
	return block(
		ids,
		"section",
		name=f"WK CTA {lang}",
		styles={"paddingBlock": "var(--wk-section-gap)"},
		children=[container(ids, [inner])],
	)


COMPONENTS = {
	"wk-header": header_definition,
	"wk-footer": footer_definition,
	"wk-cta": cta_definition,
}


def component_id(kind, lang):
	return f"{kind}-{lang}"


def uses(ids, lang, kind, definitions):
	"""A page-side instance of a shared component."""
	cid = component_id(kind, lang)
	return instance(ids, cid, definitions[cid])


# --- page sections -----------------------------------------------------------------------------------------------------


def skip_link(ids, lang):
	return link(ids, TEXT[lang]["skip"], "#wk-main", classes=["wk-skip-link"])


def main(ids, children):
	return block(
		ids,
		"main",
		custom={"id": "wk-main", "tabindex": "-1"},
		styles={"flex": "1 1 auto", "outline": "none"},
		children=children,
	)


def hero(ids, lang, *, title_html, lead, actions, art_html=None):
	"""Text on the left, an optional illustration on the right; the grid stacks them on a narrow screen."""
	left = stack(
		ids,
		[
			heading(ids, 1, title_html, name="title"),
			paragraph(ids, lead, styles={"fontSize": "1.15em", "color": "var(--wk-color-muted)"}, name="lead"),
		]
		+ ([buttons(ids, actions)] if actions else []),
		gap=3,
		styles={"justifyContent": "center"},
	)
	columns = [left]
	if art_html:
		columns.append(raw(ids, art_html, name="illustration", styles={"display": "flex", "justifyContent": "center"}))
	return section(
		ids, [grid(ids, columns, min_width="320px", styles={"alignItems": "center"})], band=True, name="hero"
	)


def features(ids, lang):
	t = TEXT[lang]
	cards = [card(ids, t[f"feature{n}_title"], t[f"feature{n}_text"]) for n in (1, 2, 3)]
	return section(ids, [stack(ids, [heading(ids, 2, t["features_title"]), grid(ids, cards)], gap=3)], name="features")


def catalogue(ids, lang):
	"""The live catalogue strip: a repeater over `wk_products` of the page data script; the section is hidden when empty."""
	t = TEXT[lang]
	data = {"comesFrom": "dataScript"}
	image = block(
		ids,
		"img",
		name="product-image",
		attrs={"alt": ""},
		styles={
			"inlineSize": "100%",
			"aspectRatio": "4 / 3",
			"objectFit": "cover",
			"borderRadius": "var(--wk-radius-sm)",
		},
		dataKey={**data, "key": "image", "type": "attribute", "property": "src"},
		dynamicValues=[{**data, "key": "image_alt", "type": "attribute", "property": "alt"}],
		visibilityCondition={**data, "key": "has_image"},
	)
	title = block(
		ids,
		"a",
		name="product-name",
		attrs={"href": "#"},
		styles={"fontWeight": "600", "textDecoration": "none"},
		dataKey={**data, "key": "name", "type": "key", "property": "innerHTML"},
		dynamicValues=[{**data, "key": "url", "type": "attribute", "property": "href"}],
	)
	text = block(
		ids,
		"div",
		name="product-text",
		styles={"color": "var(--wk-color-muted)"},
		dataKey={**data, "key": "description", "type": "key", "property": "innerHTML"},
	)
	product = block(ids, "div", name="product", classes=["wk-product-card"], children=[image, title, text])
	repeater = grid(
		ids,
		[product],
		min_width="220px",
		name="products",
		isRepeaterBlock=True,
		dataKey={**data, "key": "wk_products"},
	)
	all_link = link(
		ids,
		t["catalogue_all"],
		"/all-products",
		classes=["wk-button", "wk-button--secondary"],
		styles={"alignSelf": "flex-start"},
	)
	return block(
		ids,
		"section",
		name="catalogue",
		styles={"paddingBlock": "var(--wk-section-gap)", "backgroundColor": "var(--wk-color-surface)"},
		children=[container(ids, [stack(ids, [heading(ids, 2, t["catalogue_title"]), repeater, all_link], gap=3)])],
		visibilityCondition={**data, "key": "wk_has_products"},
	)


def about_text(ids, lang):
	t = TEXT[lang]
	blocks = [
		stack(ids, [heading(ids, 2, t["about1_title"]), paragraph(ids, t["about1_text"])], gap=1.5),
		stack(ids, [heading(ids, 2, t["about2_title"]), paragraph(ids, t["about2_text"])], gap=1.5),
	]
	return section(ids, [grid(ids, blocks, min_width="320px", gap=5)], name="about-text")


def about_facts(ids, lang):
	t = TEXT[lang]
	facts = block(
		ids,
		"div",
		classes=["wk-card"],
		children=[
			stack(
				ids,
				[
					heading(ids, 2, t["about_facts_title"]),
					raw(ids, call("wk_contact_list", lang, "card"), name="facts"),
				],
				gap=2,
			)
		],
	)
	return section(ids, [facts], name="about-facts")


def contact_columns(ids, lang):
	"""The form (or the fallback block) next to the contact facts. Both are produced by Jinja functions of the kit."""
	left = block(
		ids,
		"div",
		classes=["wk-card"],
		children=[raw(ids, call("wk_contact_form", lang), name="form")],
	)
	right = stack(
		ids,
		[
			raw(ids, call("wk_contact_aside", lang), name="facts"),
			raw(ids, art.contact(), name="illustration", styles={"display": "flex", "justifyContent": "center"}),
		],
		gap=3,
	)
	return section(
		ids, [grid(ids, [left, right], min_width="320px", gap=4, styles={"alignItems": "start"})], name="contact"
	)


def privacy_body(ids, lang):
	t = TEXT[lang]
	controller = call("wk_controller", lang)
	rights = t["privacy_placeholder_rights"]
	pieces = [
		stack(
			ids,
			[
				heading(ids, 2, t["privacy1_title"]),
				paragraph(ids, t["privacy1_text"]),
				paragraph(ids, controller, styles={"fontWeight": "600"}),
				raw(ids, call("wk_contact_list", lang, "footer")),
			],
			gap=1.5,
		),
		stack(ids, [heading(ids, 2, t["privacy2_title"]), paragraph(ids, t["privacy2_text"])], gap=1.5),
		raw(ids, call("wk_privacy_captcha", lang), name="captcha"),
		stack(
			ids,
			[
				heading(ids, 2, t["privacy4_title"]),
				paragraph(ids, t["privacy4_text"]),
				paragraph(ids, rights, styles={"fontWeight": "600"}),
			],
			gap=1.5,
		),
	]
	return section(ids, [stack(ids, pieces, gap=4, styles={"maxInlineSize": "720px"})], name="privacy")


def page_hero(ids, lang, title, lead, art_html=None):
	return hero(ids, lang, title_html=title, lead=lead, actions=None, art_html=art_html)


# --- whole pages -------------------------------------------------------------------------------------------------------


def notfound_tree():
	"""The not-found page (route `404`, the one Builder's 404 template looks up): the shared header and footer functions and a short
	message, every word through `wk_text` in the language of the request, because one page serves both languages."""
	ids = Ids("page-notfound")
	text = lambda key: call("wk_text", key)  # noqa: E731
	head = block(
		ids, "header", name="WK Header", classes=["wk-header"], children=[raw(ids, call("wk_header", ""), name="menu")]
	)
	foot = block(
		ids, "footer", name="WK Footer", classes=["wk-footer"], children=[raw(ids, call("wk_footer", ""), name="links")]
	)
	home = link(ids, text("notfound_home"), call("wk_url", "home"), classes=["wk-button"], name="home-link")
	body = hero(ids, "en", title_html=text("notfound_title"), lead=text("notfound_lead"), actions=None)
	skip = link(ids, text("skip"), "#wk-main", classes=["wk-skip-link"])
	return [root(ids, [skip, head, main(ids, [body, section(ids, [home], name="actions")]), foot])]


def page_tree(lang, key, definitions):
	"""The block tree of one page: skip link, header, main, footer."""
	t, ids = TEXT[lang], Ids(f"page-{key}-{lang}")
	if key == "home":
		body = [
			hero(
				ids,
				lang,
				title_html=call("wk_brand", lang),
				lead=t["home_lead"],
				actions=[
					(t["home_cta_primary"], URLS["contact"][lang], False),
					(t["home_cta_secondary"], URLS["about"][lang], True),
				],
				art_html=art.hero(),
			),
			features(ids, lang),
			catalogue(ids, lang),
			uses(ids, lang, "wk-cta", definitions),
		]
	elif key == "about":
		body = [
			page_hero(ids, lang, t["about_title"], t["about_lead"], art.about()),
			about_text(ids, lang),
			about_facts(ids, lang),
			uses(ids, lang, "wk-cta", definitions),
		]
	elif key == "contact":
		body = [page_hero(ids, lang, t["contact_title"], t["contact_lead"]), contact_columns(ids, lang)]
	elif key == "privacy":
		body = [
			page_hero(ids, lang, t["privacy_title"], t["privacy_lead"]),
			privacy_body(ids, lang),
		]
	else:
		raise KeyError(key)
	children = [
		skip_link(ids, lang),
		uses(ids, lang, "wk-header", definitions),
		main(ids, body),
		uses(ids, lang, "wk-footer", definitions),
	]
	return [root(ids, children)]
