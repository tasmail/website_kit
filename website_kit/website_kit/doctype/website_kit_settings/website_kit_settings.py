import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, validate_email_address

from website_kit import apply, guard_keys
from website_kit.theme import compiler, editor, presets, tokens

# Fields whose value appears on the public pages: a change must reach pages that Frappe cached.
PUBLIC_FIELDS = ("brand_name", "contact_email", "contact_phone", "address", "controller_name")


class WebsiteKitSettings(Document):
	def validate(self):
		self.brand_name = (self.brand_name or "").strip()
		if len(self.brand_name) > 140:
			frappe.throw(_("The brand name is too long (at most 140 characters)."))
		if self.preset == presets.CUSTOM:
			self.custom_base = self.custom_base or presets.DEFAULT_PRESET
		else:
			self.custom_base = ""
		try:
			_css, digest = compiler.build(self.preset, self.token_overrides, self.custom_css, self.custom_base)
		except tokens.TokenError as error:
			frappe.throw(_("Invalid theme settings: {0}").format(str(error)))
		except compiler.CustomCssError as error:
			frappe.throw(editor.rejection_html(error.result, _), title=_("The Custom CSS was rejected"))
		self.record_version(digest)
		self.validate_contacts()
		self.validate_recaptcha()

	def record_version(self, digest: str) -> None:
		"""Add a row to the version list when the compiled look differs from the newest version; keep the last 20."""
		rows = [row.as_dict() for row in self.versions]
		if not editor.should_record(rows, digest):
			return
		snap = editor.snapshot(self.preset, self.custom_base, self.token_overrides, self.custom_css, digest)
		snap.update(
			saved_at=now_datetime(),
			author=frappe.session.user,
			reason=self.flags.version_reason or _("Saved"),
		)
		self.append("versions", snap)
		for row in list(self.versions)[: -editor.MAX_VERSIONS]:
			self.remove(row)  # also renumbers the rows that stay

	def validate_contacts(self):
		self.contact_email = (self.contact_email or "").strip()
		if self.contact_email:
			validate_email_address(self.contact_email, throw=True)
			if guard_keys.is_forbidden_recipient(self.contact_email):
				frappe.throw(_("Use your own e-mail address: the contact form never sends to this domain."))
			single = guard_keys.single_recipient(self.contact_email)
			if not single:
				frappe.throw(_("Enter one plain e-mail address, without a name or a list."))
			self.contact_email = single
		self.contact_phone = (self.contact_phone or "").strip()
		self.address = (self.address or "").strip()
		self.controller_name = (self.controller_name or "").strip()
		if len(self.controller_name) > 140:
			frappe.throw(_("The data controller name is too long (at most 140 characters)."))

	def validate_recaptcha(self):
		self.recaptcha_site_key = (self.recaptcha_site_key or "").strip()
		if self.recaptcha_site_key and not guard_keys.valid_key(self.recaptcha_site_key):
			frappe.throw(_("The reCAPTCHA site key looks wrong. Copy it again from your reCAPTCHA page."))
		if bool(self.recaptcha_site_key) != bool(self.recaptcha_secret):
			frappe.throw(_("Enter both reCAPTCHA keys, or leave both empty."))

	def on_update(self):
		# The render path cannot read a password, so whether the pair is readable is recorded here.
		ok = int(bool(self.recaptcha_site_key and self.get_password("recaptcha_secret", raise_exception=False)))
		if self.recaptcha_keys_ok != ok:
			frappe.db.set_single_value(self.doctype, "recaptcha_keys_ok", ok)
			self.recaptcha_keys_ok = ok
			frappe.clear_document_cache(self.doctype, self.name)
		previous = self.get_doc_before_save()
		apply.apply(self, previous_email=previous.contact_email if previous else None)
		if not self.flags.keep_draft:
			apply.discard_draft()
		if previous is None or any(previous.get(field) != self.get(field) for field in PUBLIC_FIELDS):
			from frappe.website.utils import clear_website_cache

			clear_website_cache()
