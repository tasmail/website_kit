import frappe
from frappe import _
from frappe.model.document import Document

from website_kit import apply
from website_kit.theme import compiler, tokens


class WebsiteKitSettings(Document):
	def validate(self):
		self.brand_name = (self.brand_name or "").strip()
		if len(self.brand_name) > 140:
			frappe.throw(_("The brand name is too long (at most 140 characters)."))
		try:
			compiler.build(self.preset, self.token_overrides)
		except tokens.TokenError as error:
			frappe.throw(_("Invalid theme settings: {0}").format(str(error)))

	def on_update(self):
		apply.apply(self)
