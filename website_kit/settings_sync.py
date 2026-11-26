"""What the kit may write into `Website Settings`, as pure decisions.

The kit sets its Navbar and Footer templates and the robots text only while the field holds nothing, the Frappe default or the
kit's own value. A choice of the customer is never overwritten (also not on a re-install).

The Website Theme stays the stock `Standard` one: Frappe serves it from the prebuilt `website.bundle.css` (Bootstrap and the website
styles) and the kit adds `wk.css` and the generated token file on top. A kit release before 0.3 assigned its own theme `Website Kit`
(a per-site node/sass compile); a site that still holds exactly that value is moved back to `Standard`. Any other value is the
customer's own theme and is never touched.
"""

import re

from . import guard_keys, seo

OLD_THEME = "Website Kit"  # assigned by releases before 0.3; the only value the kit ever replaces
STOCK_THEME = "Standard"
# The CSS files the retired theme compiled: `website_kit_<8 hex>.css` and `website_kit_style.css`. Nothing else matches, so the
# files of a customer's own theme (for example "Website Kit 2" -> `website_kit_2_<hash>.css`) are never removed.
RETIRED_THEME_FILE = re.compile(r"website_kit_(?:[0-9a-f]{8}|style)\.css")
NAVBAR = "WK Navbar"
FOOTER = "WK Footer"

# field -> (value the kit wants, values it may replace)
OWNED = {
	"website_theme": (STOCK_THEME, (None, "", OLD_THEME)),
	"navbar_template": (NAVBAR, (None, "", "Standard Navbar", NAVBAR)),
	"footer_template": (FOOTER, (None, "", "Standard Footer", FOOTER)),
}
FIELDS = (*OWNED, "robots_txt")


def is_retired_theme_file(name: str) -> bool:
	"""True for a file name that only the retired `Website Kit` theme produced."""
	return RETIRED_THEME_FILE.fullmatch(name) is not None


def website_settings_changes(current: dict, allow_search_engines) -> dict:
	"""The fields of Website Settings to write, given the current values; empty when nothing differs."""
	changes = {}
	for field, (wanted, replaceable) in OWNED.items():
		value = current.get(field)
		if value in replaceable and value != wanted:
			changes[field] = wanted
	robots = seo.robots_change(current.get("robots_txt"), allow_search_engines)
	if robots is not None:
		changes["robots_txt"] = robots
	return changes


def contact_us_changes(current: dict, contact_email, previous_email=None, usable=False) -> dict:
	"""What the kit may write into `Contact Us Settings`.

	The stock `send_message` is reachable by anyone once the contact page is enabled, so the kit enables it only while the form
	is usable (`usable`: the guard app, reCAPTCHA keys and the `enforce` mode are in place) and disables it again when that
	stops being true. `forward_to_email` follows the customer's single plain address while it is empty or still the address the
	kit wrote last time; an address the customer typed there is kept. The acknowledgement e-mail (a mail to a stranger, the abuse
	vector the guard describes) is switched off when the kit takes the page over.
	"""
	changes = {}
	email = guard_keys.single_recipient(contact_email)
	forward = (current.get("forward_to_email") or "").strip()
	if email and forward != email and forward in ("", (previous_email or "").strip()):
		changes["forward_to_email"] = email
		forward = email
	ours = bool(email) and forward == email
	if ours and usable and current.get("is_disabled"):
		changes["is_disabled"] = 0
	if (not usable or not ours) and not current.get("is_disabled") and (ours or not forward):
		changes["is_disabled"] = 1
	# Switched off when the kit takes the page over, not on every apply: a later choice of the customer is not overwritten.
	if current.get("send_acknowledgement_email") and ("forward_to_email" in changes or "is_disabled" in changes):
		changes["send_acknowledgement_email"] = 0
	return changes
