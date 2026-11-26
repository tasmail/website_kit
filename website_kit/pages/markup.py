"""Markup that a page cannot hold as a plain block: the contact form, the contact list and the head tags.

Pure functions: every value is escaped here (`esc`: HTML escape plus brace encoding, so the output is inert even if Jinja
renders it again), and nothing from the site is concatenated into a template source. The Jinja functions that expose these to
Builder blocks are in `website_kit.jinja_api`.
"""

import json
import re

from ..theme.escape import esc, safe_url

FORM_ID = "wk-contact-form"
GUARD_SCRIPT = "/assets/frappe_guard/js/guard.js"
UNDERLINE = "text-decoration:underline"  # a link inside a line of text must not rely on colour alone
LIST_STYLE = "list-style:none;margin:0;padding:0;display:grid;gap:var(--wk-space-unit)"
PHONE_PATTERN = re.compile(r"[^0-9+]")


def tel_href(phone) -> str:
	"""A `tel:` link target made of digits and a leading plus, or an empty string."""
	digits = PHONE_PATTERN.sub("", phone or "")
	digits = digits[:1] + digits[1:].replace("+", "") if digits else ""
	return f"tel:{digits}" if len(digits.lstrip("+")) >= 5 else ""


def contact_items(text, info) -> list[tuple[str, str]]:
	"""`(label, html)` for each contact fact the customer filled in."""
	items = []
	email = (info.get("email") or "").strip()
	if email and "@" in email:
		items.append((text["label_email"], f'<a href="mailto:{esc(email)}" style="{UNDERLINE}">{esc(email)}</a>'))
	phone = (info.get("phone") or "").strip()
	if phone:
		href = tel_href(phone)
		body = f'<a href="{esc(href)}" style="{UNDERLINE}">{esc(phone)}</a>' if href else esc(phone)
		items.append((text["label_phone"], body))
	address = (info.get("address") or "").strip()
	if address:
		lines = "<br>".join(esc(line.strip()) for line in address.splitlines() if line.strip())
		items.append((text["label_address"], lines))
	return items


def contact_list(text, info, variant="card") -> str:
	"""The contact facts as a list; an empty string when nothing is filled in and the variant is `footer`."""
	items = contact_items(text, info)
	if not items:
		return "" if variant == "footer" else f"<p>{esc(text['fallback_empty'])}</p>"
	rows = "".join(f"<li><strong>{esc(label)}:</strong> {body}</li>" for label, body in items)
	return f'<ul style="{LIST_STYLE}">{rows}</ul>'


def contact_aside(text, info) -> str:
	"""The card of contact facts that sits next to the form; the fallback block lists them itself, so it is not repeated."""
	return (
		'<div class="wk-card" style="display:grid;gap:calc(var(--wk-space-unit) * 2)">'
		f'<h2 style="margin:0">{esc(text["contact_info_title"])}</h2>{contact_list(text, info, "card")}</div>'
	)


def fallback(text, info) -> str:
	"""What replaces the form while it cannot be shown: a short text and the contact facts."""
	return (
		'<div data-wk-contact-fallback style="display:grid;gap:calc(var(--wk-space-unit) * 2)">'
		f'<h2 style="margin:0">{esc(text["fallback_title"])}</h2><p style="margin:0">{esc(text["fallback_text"])}</p>'
		f"{contact_list(text, info, 'card')}</div>"
	)


def privacy_sentence(text, privacy_url) -> str:
	"""The consent line: `form_privacy` with `{link}` replaced by a link to the privacy page.

	Empty without a URL: the privacy page is linked only once the customer filled in the data controller (until then it
	holds placeholders, and a consent to unwritten terms must not be asked for).
	"""
	if not privacy_url:
		return ""
	before, _, after = text["form_privacy"].partition("{link}")
	link = f'<a href="{esc(privacy_url)}" style="{UNDERLINE}">{esc(text["form_privacy_link"])}</a>'
	return f"{esc(before)}{link}{esc(after)}"


def contact_form(text, privacy_url) -> str:
	"""The contact form. It posts to the stock `send_message` through the guard (action `contact`); the script of the page
	(`website_kit/pages/wk_contact.js`) sends it and refuses to send when the guard client is missing."""
	data = (
		f'data-guard-action="contact" data-subject="{esc(text["form_subject"])}" '
		f'data-sending="{esc(text["form_sending"])}" data-success="{esc(text["form_success"])}" '
		f'data-error="{esc(text["form_error"])}"'
	)
	star = '<span aria-hidden="true"> *</span>'
	trap = (
		'<div style="position:absolute;inset-inline-start:-10000px" aria-hidden="true">'
		'<input type="text" name="website" tabindex="-1" autocomplete="off"></div>'
	)
	label = "display:grid;gap:calc(var(--wk-space-unit) / 2);font-weight:600"
	return (
		f'<form id="{FORM_ID}" method="post" action="#" {data} style="display:grid;gap:calc(var(--wk-space-unit) * 2)">'
		f'<h2 style="margin:0">{esc(text["form_title"])}</h2>'
		f'<label style="{label}"><span>{esc(text["form_name"])}</span>'
		'<input class="wk-field" type="text" name="sender_name" autocomplete="name" maxlength="140"></label>'
		f'<label style="{label}"><span>{esc(text["form_email"])}{star}</span>'
		'<input class="wk-field" type="email" name="sender" autocomplete="email" required maxlength="140"></label>'
		f'<label style="{label}"><span>{esc(text["form_message"])}{star}</span>'
		'<textarea class="wk-field" name="message" rows="6" required maxlength="5000"></textarea></label>'
		f"{trap}"
		f'<p style="margin:0;font-size:.9em">{privacy_sentence(text, privacy_url)} {esc(text["form_captcha"])}</p>'
		f'<button class="wk-button" type="submit">{esc(text["form_send"])}</button>'
		'<p role="status" aria-live="polite" data-wk-status style="margin:0" hidden></p>'
		"</form>"
	)


def head_tags(*, base_css, theme_css, robots_closed, alternates, organization, guard_site_key) -> str:
	"""The `<head>` additions of a standard page: stylesheets, robots, hreflang pairs, Organization data, guard client.

	Stylesheet URLs go through `safe_url`; the JSON-LD and the guard key are JSON with `<` escaped, so no value can close the tag.
	"""
	parts = [f'<link rel="stylesheet" href="{esc(base_css)}">']
	theme = safe_url(theme_css)
	if theme:
		parts.append(f'<link rel="stylesheet" href="{esc(theme)}">')
	if robots_closed:
		parts.append('<meta name="robots" content="noindex, nofollow">')
	for lang, url in alternates:
		parts.append(f'<link rel="alternate" hreflang="{esc(lang)}" href="{esc(url)}">')
	if organization:
		parts.append(f'<script type="application/ld+json">{json_script(organization)}</script>')
	if guard_site_key:
		parts.append(f"<script>window.FRAPPE_GUARD={json_script({'siteKey': guard_site_key})};</script>")
		parts.append(f'<script src="{GUARD_SCRIPT}" defer></script>')
	return "".join(parts)


def _protect(value):
	"""Braces in a string value become placeholders, so that no `{{` survives in the JSON text (see `json_script`)."""
	if isinstance(value, str):
		return value.replace("{", "\u0000L").replace("}", "\u0000R")
	if isinstance(value, dict):
		return {key: _protect(item) for key, item in value.items()}
	if isinstance(value, list):
		return [_protect(item) for item in value]
	return value


def json_script(value) -> str:
	"""JSON for a `<script>` element: `<`, `>` and `&` are escaped so the text cannot end the element or start a comment, and a
	brace inside a string value is written as `\\u007b` or `\\u007d` (still the same text for a JSON parser), so no `{{` of a
	value can ever be read as a template."""
	text = json.dumps(_protect(value), ensure_ascii=False, separators=(",", ":"))
	text = text.replace("\\u0000L", "\\u007b").replace("\\u0000R", "\\u007d")
	return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def organization_data(name, url, email, phone) -> dict:
	"""schema.org Organization of the site; only facts the customer entered."""
	data = {"@context": "https://schema.org", "@type": "Organization", "name": name, "url": url}
	if email:
		data["email"] = email
	if phone:
		data["telephone"] = phone
	return data
