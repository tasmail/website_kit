"""The setup-wizard stage and the "Personalize" action for sites that existed before the kit.

Both end in `fill`, which writes only what is still empty, so running it twice changes nothing and a value the customer
set is never overwritten. The stage adds no slide to the wizard (decision O14).
"""

import frappe
from frappe import _

from . import apply as kit_apply

SETTINGS = kit_apply.SETTINGS
CONTACT = "Contact Us Settings"


def stages(args) -> list[dict]:
	"""Hook `setup_wizard_stages`: one stage that copies the company name and the contact data once."""
	return [
		{
			"status": _("Setting up the website"),
			"fail_msg": _("Failed to set up the website"),
			"tasks": [{"fn": from_wizard, "args": args, "fail_msg": _("Failed to set up the website")}],
		}
	]


def from_wizard(args) -> dict:
	"""The wizard task. It copies only the company name: the wizard's `email` is the administrator's login address, which must
	never reach the public contact page. A failure is logged and never stops the wizard from finishing."""
	try:
		return fill((args or {}).get("company_name"))
	except Exception:
		frappe.log_error(title="Website Kit: the setup-wizard stage failed, setup continues")
		return {}


def fill(company_name=None, email=None, phone=None) -> dict:
	"""Copy the company name into the brand name, and the e-mail and phone into Contact Us Settings, where those are empty.

	Pass an e-mail or phone only when it is a public contact of the company, never a user's login address.
	"""
	changes = {}
	company_name = (company_name or "").strip()
	if company_name and not (frappe.db.get_single_value(SETTINGS, "brand_name") or "").strip():
		settings = frappe.get_doc(SETTINGS)
		settings.brand_name = company_name[:140]
		settings.save(ignore_permissions=True)  # on_update applies the settings
		changes["brand_name"] = settings.brand_name
	for field, value in (("email_id", email), ("phone", phone), ("address_title", company_name)):
		value = (value or "").strip()
		if value and not frappe.db.get_single_value(CONTACT, field):
			frappe.db.set_single_value(CONTACT, field, value[:140])
			changes[f"contact.{field}"] = value[:140]
	if changes:
		from frappe.website.utils import clear_website_cache

		clear_website_cache()  # cached pages carry the brand name and the contact page
	return changes


def personalize() -> dict:
	"""Opt-in action of the settings page for a site that has a company already: the stage's logic plus the e-mail and phone
	that the Company record names as the company's contact (the administrator presses the button on purpose)."""
	company = frappe.defaults.get_global_default("company")
	if not company and frappe.db.exists("DocType", "Company"):
		company = frappe.db.get_value("Company", {}, "name", order_by="creation asc")
	email = phone = ""
	if company:
		email, phone = frappe.db.get_value("Company", company, ["email", "phone_no"]) or ("", "")
	changes = fill(company, email, phone)
	changes.update(kit_apply.apply())
	return changes
