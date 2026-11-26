"""The contact form on a site: which keys apply, whether the form may be shown, and the guard hand-over.

Frappe-facing glue; the decisions are pure and live in `guard_keys.py` and `settings_sync.py`.
"""

import frappe

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


def current_keys(with_secret: bool = False):
	"""The reCAPTCHA keys for this request (own, platform or shared), or None.

	Rendering a page needs only the public key and to know that a secret exists, and a password cannot be read while a page
	renders (Frappe refuses it inside its script sandbox). So the secret is decrypted only when `with_secret` is set, which the
	request that posts the form does.
	"""
	settings = kit_settings()
	own_key = (settings.recaptcha_site_key if settings else "") or ""
	if own_key and with_secret:
		own_secret = settings.get_password("recaptcha_secret", raise_exception=False)
	else:
		own_secret = "x" if own_key and settings.recaptcha_secret else ""
	return guard_keys.resolve(own_key, own_secret, frappe.conf, request_host(), frappe.local.site)


def form_state() -> guard_keys.FormState:
	"""Whether the contact form may be rendered on this request. Any error means "no form"."""
	try:
		disabled = frappe.db.get_single_value(CONTACT_US, "is_disabled")
		forward = frappe.db.get_single_value(CONTACT_US, "forward_to_email")
		return guard_keys.form_state(current_keys(), guard_installed(), disabled, forward)
	except Exception:
		frappe.log_error(title="Website Kit: the state of the contact form could not be read")
		return guard_keys.FormState(False, "error")


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


def sync_contact_settings(contact_email, previous_email=None) -> dict:
	"""Make Contact Us Settings follow the customer's address; returns what changed (empty on a repeat)."""
	doc = frappe.get_doc(CONTACT_US)
	changes = settings_sync.contact_us_changes(
		{field: doc.get(field) for field in ("forward_to_email", "send_acknowledgement_email", "is_disabled")},
		contact_email,
		previous_email,
	)
	if changes:
		doc.update(changes)
		doc.save(ignore_permissions=True)
	return {f"contact_us_settings.{field}": "set" for field in changes}
