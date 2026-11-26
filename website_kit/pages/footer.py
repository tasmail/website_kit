"""The footer content for the pages that are not made of blocks: the not-found page (Builder's own 404 template has no footer).

Pure: the same four links, the contact facts and the copyright line as the footer component of the standard pages.
`brand_html` and `facts_html` are already escaped by their callers (`jinja_api`).
"""

from ..theme.escape import esc
from .content import TEXT, URLS

LINKS = (("home", "menu_home"), ("about", "menu_about"), ("contact", "menu_contact"), ("privacy", "footer_privacy"))


def inner(*, lang, brand_html, facts_html) -> str:
	"""The markup inside `<footer class="wk-footer">`."""
	lang = lang if lang in TEXT else "en"
	text = TEXT[lang]
	items = "".join(f'<li><a href="{esc(URLS[key][lang])}">{esc(text[label])}</a></li>' for key, label in LINKS)
	return (
		'<div class="wk-container wk-footer__inner">'
		f'<nav aria-label="{esc(text["footer_nav"])}"><ul class="wk-footer__links">{items}</ul></nav>'
		f'{facts_html}<p class="wk-footer__copy">&copy; {brand_html}</p></div>'
	)
