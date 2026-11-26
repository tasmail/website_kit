"""Which reCAPTCHA keys the contact form uses, and when the form may exist at all."""

import pytest

from website_kit import guard_keys

KEY = "6Lc" + "a" * 37
OTHER = "6Ld" + "b" * 37
SECRET = "s" * 40


def conf(**values):
	return {"guard_recaptcha_site_key": KEY, "guard_recaptcha_secret": SECRET, **values}


def test_the_customers_own_keys_win_and_use_the_request_host():
	keys = guard_keys.resolve(OTHER, "own-secret", conf(), "Shop.Example.com:443", "x.erp-crm.org")
	assert (keys.site_key, keys.secret, keys.hosts, keys.source) == (OTHER, "own-secret", ("shop.example.com",), "own")


def test_platform_keys_are_used_when_the_guard_lists_the_host():
	keys = guard_keys.resolve(
		"", "", conf(guard_hosts=["a.example.org", "b.example.org"]), "b.example.org", "b.example.org"
	)
	assert keys.source == "platform" and keys.hosts == ("a.example.org", "b.example.org")


def test_a_host_list_given_as_a_string_works():
	assert guard_keys.resolve("", "", conf(guard_hosts="a.example.org"), "a.example.org", "a").source == "platform"


def test_the_shared_keys_serve_only_the_sites_own_erp_crm_name():
	keys = guard_keys.resolve("", "", conf(), "acme.erp-crm.org", "acme.erp-crm.org")
	assert keys.source == "shared" and keys.hosts == ("acme.erp-crm.org",)
	# a custom domain of that site, or a host that only looks similar: no shared keys
	assert guard_keys.resolve("", "", conf(), "www.acme.com", "acme.erp-crm.org") is None
	assert guard_keys.resolve("", "", conf(), "evilerp-crm.org", "evilerp-crm.org") is None
	assert guard_keys.resolve("", "", conf(), "erp-crm.org", "erp-crm.org") is None
	assert guard_keys.resolve("", "", conf(), "other.erp-crm.org", "acme.erp-crm.org") is None


@pytest.mark.parametrize(
	"own_key, own_secret, site_conf",
	[
		("", "", {}),  # nothing at all
		(KEY, "", {}),  # an own key without its secret
		("short", "secret", {}),  # a malformed own key
		("", "", {"guard_recaptcha_site_key": KEY}),  # platform key without a secret
		("", "", {"guard_recaptcha_secret": SECRET}),  # platform secret without a key
		("", "", {"guard_recaptcha_site_key": "bad key", "guard_recaptcha_secret": SECRET}),
		("", "", {"guard_recaptcha_site_key": 5, "guard_recaptcha_secret": ["x"]}),
	],
)
def test_no_usable_keys_means_none(own_key, own_secret, site_conf):
	assert guard_keys.resolve(own_key, own_secret, site_conf, "acme.erp-crm.org", "acme.erp-crm.org") is None


def test_an_unusable_host_means_none():
	for host in ("", None, "bad host", "a b.example.org", 7):
		assert guard_keys.resolve(OTHER, "secret", conf(), host, "x") is None


def test_normalize_host():
	assert guard_keys.normalize_host(" Acme.ERP-CRM.org.:8000 ") == "acme.erp-crm.org"
	assert guard_keys.normalize_host("a_b.com") == "" and guard_keys.normalize_host(None) == ""


def test_overrides_only_list_what_the_config_lacks():
	keys = guard_keys.Keys(KEY, SECRET, ("a.erp-crm.org",), "shared")
	assert guard_keys.config_overrides(keys, {}) == {
		"guard_recaptcha_site_key": KEY,
		"guard_recaptcha_secret": SECRET,
		"guard_hosts": ["a.erp-crm.org"],
	}
	assert guard_keys.config_overrides(keys, conf(guard_hosts=["a.erp-crm.org"])) == {}
	assert guard_keys.config_overrides(keys, conf(guard_hosts=["z.erp-crm.org"])) == {"guard_hosts": ["a.erp-crm.org"]}


def test_forbidden_recipients():
	assert guard_keys.is_forbidden_recipient("a@foss.ua") and guard_keys.is_forbidden_recipient("A@Mail.FOSS.UA")
	assert not guard_keys.is_forbidden_recipient("a@notfoss.ua") and not guard_keys.is_forbidden_recipient(
		"a@foss.ua.example.com"
	)
	assert not guard_keys.is_forbidden_recipient("") and not guard_keys.is_forbidden_recipient(None)


KEYS = guard_keys.Keys(KEY, SECRET, ("h",), "own")


def test_the_form_needs_the_guard_keys_a_recipient_and_an_enabled_page():
	assert guard_keys.form_state(KEYS, True, 0, "me@example.com") == guard_keys.FormState(True, "ok", KEY)
	assert not guard_keys.form_state(KEYS, False, 0, "me@example.com").render  # no guard app: the form must not exist
	assert not guard_keys.form_state(None, True, 0, "me@example.com").render  # no keys
	assert not guard_keys.form_state(KEYS, True, 1, "me@example.com").render  # Contact Us Settings disabled
	assert not guard_keys.form_state(KEYS, True, 0, "").render and not guard_keys.form_state(KEYS, True, 0, None).render
	assert not guard_keys.form_state(KEYS, True, 0, "x@foss.ua").render  # never a foss.ua recipient
	for state in (
		guard_keys.form_state(KEYS, False, 0, "a@b.c"),
		guard_keys.form_state(None, True, 0, "a@b.c"),
	):
		assert state.reason != "ok" and state.site_key == ""


def test_constants_match_the_guard_defaults():
	assert guard_keys.SEND_MESSAGE == "frappe.www.contact.send_message" and guard_keys.GUARD_ACTION == "contact"
