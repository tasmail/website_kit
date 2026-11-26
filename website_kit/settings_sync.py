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
