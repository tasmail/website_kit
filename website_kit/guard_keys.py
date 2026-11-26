"""Which reCAPTCHA keys the contact form uses, as pure decisions (no Frappe import).

The guard app (`frappe_guard`) reads its keys from the site config: `guard_recaptcha_site_key`, `guard_recaptcha_secret` and
`guard_hosts` (an exact list of the host names it accepts tokens from). The kit decides per request which keys apply and, for
the one request that posts the form, hands them to the guard through the request's own copy of the config (see
`website_kit.contact.before_request`); nothing is written to the site config or to the database.

Order of the sources:

1. The customer's own keys from `Website Kit Settings` (the customer registers their own domain with Google). Tokens are
   accepted from the host the request came to.
2. Keys the platform put in the site config, when the guard's host list already names the request host.
3. The same platform keys on a host that ends in `erp-crm.org`: the shared keys of the platform, valid for the site's own
   name only (never for a custom domain: a token made on another host would be refused, so no form is shown there).

Anything else means "no keys": the form is not rendered and a mail-to and phone block is shown instead.
"""

import re
from dataclasses import dataclass
from email.utils import getaddresses

SITE_KEY = "guard_recaptcha_site_key"
SECRET = "guard_recaptcha_secret"
HOSTS = "guard_hosts"
SHARED_SUFFIX = ".erp-crm.org"
SEND_MESSAGE = "frappe.www.contact.send_message"
GUARD_ACTION = "contact"

# A reCAPTCHA key is 40 characters of letters, digits, `-` and `_`; the bounds keep a typo out without pinning Google's format.
KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,80}$")
HOST_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$")
# The platform's own mail domain: a customer's contact address must never point at it (the form would mail us, not the customer).
FORBIDDEN_RECIPIENT_DOMAINS = ("foss.ua",)


@dataclass(frozen=True)
class Keys:
	site_key: str
	secret: str
	hosts: tuple[str, ...]
	source: str  # "own", "platform" or "shared"


def normalize_host(host) -> str:
	"""A lower-case host name without port and trailing dot, or an empty string when it is not a plain host name."""
	text = (host or "").strip().lower() if isinstance(host, str) else ""
	text = text.split(":", 1)[0].rstrip(".")
	return text if HOST_PATTERN.match(text) else ""


def valid_key(value) -> bool:
	return isinstance(value, str) and bool(KEY_PATTERN.match(value.strip()))


def _addresses(text) -> list[tuple[str, str]]:
	"""`(display name, address)` pairs of a header-like value; the address lower-cased, without a trailing dot."""
	pairs = getaddresses([text if isinstance(text, str) else ""])
	return [(name.strip(), address.strip().lower().rstrip(".")) for name, address in pairs if address.strip()]


def is_forbidden_recipient(text) -> bool:
	"""True when ANY address of the value is at a domain the kit never mails (`foss.ua` and its subdomains).

	A list (`a@foss.ua, b@example.com`), a display name (`Name <a@foss.ua>`), upper case and a trailing dot are all looked
	through, so none of them hides a forbidden address.
	"""
	for _name, address in _addresses(text):
		domain = address.rpartition("@")[2].rstrip(".")
		if any(domain == blocked or domain.endswith("." + blocked) for blocked in FORBIDDEN_RECIPIENT_DOMAINS):
			return True
	return False


def single_recipient(text) -> str:
	"""The one plain address of the value, normalised, or an empty string (a list, a display name or no address is refused)."""
	pairs = _addresses(text)
	if len(pairs) != 1 or pairs[0][0] or "," in (text or "") or ";" in (text or ""):
		return ""
	address = pairs[0][1]
	return "" if is_forbidden_recipient(address) or address.count("@") != 1 else address


def contact_enforced(conf) -> bool:
	"""Whether the guard refuses a failed check for the `contact` action. In `monitor` (the guard's default) it only logs.

	Read from the site config the way the guard reads it: `guard_actions.contact.mode`, else `guard_actions["*"].mode`, else
	`guard_mode`.
	"""
	actions = conf.get("guard_actions")
	actions = actions if isinstance(actions, dict) else {}
	for key in ("contact", "*"):
		entry = actions.get(key)
		if isinstance(entry, dict) and entry.get("mode"):
			return entry["mode"] == "enforce"
	return conf.get("guard_mode") == "enforce"


def _conf_hosts(conf) -> list[str]:
	value = conf.get(HOSTS)
	if isinstance(value, str):
		value = [value]
	return [normalize_host(host) for host in value] if isinstance(value, (list, tuple)) else []


def resolve(own_site_key, own_secret, conf, request_host, site_name) -> Keys | None:
	"""The keys for this request, or None. `conf` is the site config (a mapping)."""
	host = normalize_host(request_host)
	if not host:
		return None
	if valid_key(own_site_key) and isinstance(own_secret, str) and own_secret.strip():
		return Keys(own_site_key.strip(), own_secret.strip(), (host,), "own")
	site_key, secret = conf.get(SITE_KEY), conf.get(SECRET)
	if not (valid_key(site_key) and isinstance(secret, str) and secret.strip()):
		return None
	listed = _conf_hosts(conf)
	if host in listed:
		return Keys(site_key.strip(), secret.strip(), tuple(h for h in listed if h), "platform")
	if host.endswith(SHARED_SUFFIX) and host == normalize_host(site_name):
		return Keys(site_key.strip(), secret.strip(), (host,), "shared")
	return None


@dataclass(frozen=True)
class FormState:
	render: bool
	reason: str  # why the form is not shown, or "ok"
	site_key: str = ""


def form_state(keys, guard_installed, contact_disabled, forward_to_email, enforced=True) -> FormState:
	"""Whether the contact form may be rendered. A form that posts without the guard must not exist."""
	if not guard_installed:
		return FormState(False, "guard app not installed")
	if not enforced:
		return FormState(False, "the guard is not in enforce mode for the contact action")
	if keys is None:
		return FormState(False, "no usable reCAPTCHA keys for this host")
	if contact_disabled:
		return FormState(False, "Contact Us Settings is disabled")
	if not (forward_to_email or "").strip():
		return FormState(False, "no recipient (Contact Us Settings forward_to_email)")
	if not single_recipient(forward_to_email):
		return FormState(False, "recipient is not one allowed address")
	return FormState(True, "ok", keys.site_key)


def config_overrides(keys: Keys, conf) -> dict:
	"""What the request's own config copy needs so that the guard accepts these keys; empty when it already has them."""
	wanted = {SITE_KEY: keys.site_key, SECRET: keys.secret, HOSTS: list(keys.hosts)}
	return {name: value for name, value in wanted.items() if conf.get(name) != value}
