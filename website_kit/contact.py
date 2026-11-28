"""The contact form on a site: which keys apply, whether the form may be shown, and the guard hand-over.

Frappe-facing glue; the decisions are pure and live in `guard_keys.py` and `settings_sync.py`.
"""

import frappe
from frappe import _

from . import guard_keys, settings_sync

SETTINGS = "Website Kit Settings"
CONTACT_US = "Contact Us Settings"


def kit_settings():
	try:
		return frappe.get_cached_doc(SETTINGS)
	except Exception:
		return None


def request_host() -> str:
	request = getattr(frappe.local, "request", None)
	host = (request.host or request.headers.get("Host", "")) if request else ""
	return host or frappe.local.site


def guard_installed() -> bool:
	return "frappe_guard" in frappe.get_installed_apps()


def own_keys_ok() -> bool:
	"""Whether the customer's own key pair is complete and readable (checked when the settings were saved)."""
	settings = kit_settings()
	return bool(settings and settings.recaptcha_site_key and settings.recaptcha_keys_ok)


def current_keys(with_secret: bool = False):
	"""The reCAPTCHA keys for this request (own, platform or shared), or None.

	Rendering a page cannot read a password (Frappe refuses it inside its script sandbox), so the page relies on the flag
	`recaptcha_keys_ok` set when the settings were saved, and the request that posts the form decrypts the secret. An own pair
	that cannot be read counts as no own keys, in both places alike.
	"""
	settings = kit_settings()
	own_key, own_secret = "", ""
	if own_keys_ok():
		own_key = settings.recaptcha_site_key
		own_secret = (settings.get_password("recaptcha_secret", raise_exception=False) or "") if with_secret else "x"
		if not own_secret:
			own_key = ""
	return guard_keys.resolve(own_key, own_secret, frappe.conf, request_host(), frappe.local.site)


def form_state() -> guard_keys.FormState:
	"""Whether the contact form may be rendered on this request. Any error means "no form"."""
	try:
		disabled = frappe.db.get_single_value(CONTACT_US, "is_disabled")
		forward = frappe.db.get_single_value(CONTACT_US, "forward_to_email")
		return guard_keys.form_state(
			current_keys(), guard_installed(), disabled, forward, guard_keys.contact_enforced(frappe.conf)
		)
	except Exception:
		frappe.log_error(title="Website Kit: the state of the contact form could not be read")
		return guard_keys.FormState(False, "error")


def privacy_ready() -> bool:
	"""Whether the privacy page names its controller, so that the form may link to it."""
	settings = kit_settings()
	return bool(settings and (settings.controller_name or "").strip())


def contact_info() -> dict:
	settings = kit_settings()
	if not settings:
		return {}
	return {"email": settings.contact_email, "phone": settings.contact_phone, "address": settings.address}


def before_request() -> None:
	"""Hook `before_request`: give the guard the keys of this site for the one request that posts the contact form.

	The guard reads `guard_recaptcha_site_key`, `guard_recaptcha_secret` and `guard_hosts` from `frappe.conf`. This hook runs
	before the guard's `auth_hooks`, and changes only the config copy of the current request (Frappe builds a fresh one for
	every request): nothing is written to the site config, the database or the log. A failure leaves the config as it is, so
	the guard decides with what the platform configured.
	"""
	try:
		request = getattr(frappe.local, "request", None)
		if request is None or not guard_installed():
			return
		if (
			guard_keys.SEND_MESSAGE not in (request.path or "")
			and frappe.form_dict.get("cmd") != guard_keys.SEND_MESSAGE
		):
			return
		keys = current_keys(with_secret=True)
		if keys:
			frappe.conf.update(guard_keys.config_overrides(keys, frappe.conf))
	except Exception:
		frappe.logger("website_kit").error("the guard keys could not be prepared", exc_info=True)


def usable_without_host() -> tuple[bool, str]:
	"""Whether the form can work on this site at all (independent of the request host), and the reason when it cannot."""
	if not guard_installed():
		return False, _("spam protection is not installed on this site")
	if not guard_keys.contact_enforced(frappe.conf):
		return (
			False,
			_("spam protection is not switched on for the contact form on this site"),
		)
	settings = kit_settings()
	platform = frappe.conf.get(guard_keys.SITE_KEY) and frappe.conf.get(guard_keys.SECRET)
	if not (own_keys_ok() or platform):
		return False, _("there are no reCAPTCHA keys: enter your own keys in the fields above")
	if not guard_keys.single_recipient(settings.contact_email if settings else ""):
		return False, _("there is no valid contact e-mail")
	return True, ""


def sync_contact_settings(contact_email, previous_email=None) -> dict:
	"""Make Contact Us Settings follow the customer's address and the state of the guard; returns what changed."""
	usable, reason = usable_without_host()
	doc = frappe.get_doc(CONTACT_US)
	changes = settings_sync.contact_us_changes(
		{field: doc.get(field) for field in ("forward_to_email", "send_acknowledgement_email", "is_disabled")},
		contact_email,
		previous_email,
		usable,
	)
	if changes:
		doc.update(changes)
		doc.save(ignore_permissions=True)
	result = {f"contact_us_settings.{field}": "set" for field in changes}
	status = _("The contact form is available.") if usable else _("The contact form is not shown: {0}.").format(reason)
	if (frappe.db.get_single_value(SETTINGS, "contact_form_status") or "") != status:
		frappe.db.set_single_value(SETTINGS, "contact_form_status", status)
		frappe.clear_document_cache(SETTINGS, SETTINGS)
		result["contact_form_status"] = "set"
	return result
