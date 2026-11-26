import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address

from website_kit import apply, guard_keys
from website_kit.theme import compiler, tokens

# Fields whose value appears on the public pages: a change must reach pages that Frappe cached.
PUBLIC_FIELDS = ("brand_name", "contact_email", "contact_phone", "address", "controller_name")


class WebsiteKitSettings(Document):
	def validate(self):
		self.brand_name = (self.brand_name or "").strip()
		if len(self.brand_name) > 140:
			frappe.throw(_("The brand name is too long (at most 140 characters)."))
		try:
			compiler.build(self.preset, self.token_overrides)
		except tokens.TokenError as error:
			frappe.throw(_("Invalid theme settings: {0}").format(str(error)))
		self.validate_contacts()
		self.validate_recaptcha()

	def validate_contacts(self):
		self.contact_email = (self.contact_email or "").strip()
		if self.contact_email:
			validate_email_address(self.contact_email, throw=True)
			if guard_keys.is_forbidden_recipient(self.contact_email):
				frappe.throw(_("Use your own e-mail address: the contact form never sends to this domain."))
		self.contact_phone = (self.contact_phone or "").strip()
		self.address = (self.address or "").strip()
		self.controller_name = (self.controller_name or "").strip()
		if len(self.controller_name) > 140:
			frappe.throw(_("The data controller name is too long (at most 140 characters)."))

	def validate_recaptcha(self):
		self.recaptcha_site_key = (self.recaptcha_site_key or "").strip()
		if self.recaptcha_site_key and not guard_keys.valid_key(self.recaptcha_site_key):
			frappe.throw(_("The reCAPTCHA site key looks wrong: it has letters, digits, - and _ only."))
		if bool(self.recaptcha_site_key) != bool(self.recaptcha_secret):
			frappe.throw(_("Enter both reCAPTCHA keys of the pair, or neither."))

	def on_update(self):
		previous = self.get_doc_before_save()
		apply.apply(self, previous_email=previous.contact_email if previous else None)
		if previous is None or any(previous.get(field) != self.get(field) for field in PUBLIC_FIELDS):
			from frappe.website.utils import clear_website_cache

			clear_website_cache()
