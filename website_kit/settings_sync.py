"""What the kit may write into `Website Settings`, as pure decisions.

The kit sets its theme, its Navbar and Footer templates and the robots text only while the field holds nothing, the Frappe
default or the kit's own value. A choice of the customer is never overwritten (also not on a re-install).
"""

from . import seo

THEME = "Website Kit"
NAVBAR = "WK Navbar"
FOOTER = "WK Footer"

# field -> (value the kit wants, values it may replace)
OWNED = {
	"website_theme": (THEME, (None, "", "Standard", THEME)),
	"navbar_template": (NAVBAR, (None, "", "Standard Navbar", NAVBAR)),
	"footer_template": (FOOTER, (None, "", "Standard Footer", FOOTER)),
}
FIELDS = (*OWNED, "robots_txt")


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


def contact_us_changes(current: dict, contact_email, previous_email=None) -> dict:
	"""What the kit may write into `Contact Us Settings`.

	`forward_to_email` follows the customer's address while it is empty or still the address the kit wrote last time; an address
	the customer typed there is kept. Stock Frappe ships Contact Us Settings disabled, so the page is switched on at the moment the
	kit first writes the customer's address (`is_disabled` is not touched afterwards: switching it off later is the customer's
	choice). The acknowledgement e-mail (a mail to a stranger, the abuse vector the guard describes) is always off.
	"""
	changes = {}
	email = (contact_email or "").strip()
	forward = (current.get("forward_to_email") or "").strip()
	if email and forward != email and forward in ("", (previous_email or "").strip()):
		changes["forward_to_email"] = email
		if current.get("is_disabled"):
			changes["is_disabled"] = 0
	if current.get("send_acknowledgement_email"):
		changes["send_acknowledgement_email"] = 0
	return changes
