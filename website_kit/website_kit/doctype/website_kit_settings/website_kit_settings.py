import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from website_kit import apply
from website_kit.theme import compiler, editor, presets, tokens


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

	def on_update(self):
		apply.apply(self)
		if not self.flags.keep_draft:
			apply.discard_draft()
