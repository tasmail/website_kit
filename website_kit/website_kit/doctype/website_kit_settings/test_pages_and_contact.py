"""Frappe integration tests of the standard pages, the upgrade policy and the contact form (they need Builder and frappe_guard)."""

import json
import re
import unittest
from unittest import mock

import frappe
import frappe.app
from werkzeug.test import Client
from werkzeug.wrappers import Response

try:  # Frappe 16
	from frappe.tests import IntegrationTestCase as TestCase
except ImportError:  # Frappe 15
	from frappe.tests.utils import FrappeTestCase as TestCase

from website_kit import contact, install
from website_kit.pages import blocks, policy, specs, sync

SETTINGS = "Website Kit Settings"
PAGE = "Builder Page"
EMAIL = "owner@example.com"
SITE_KEY = "6Lc" + "a" * 37
SECRET = "s" * 40
UK_PAGES = ("/", "/about", "/contact", "/privacy")


V15_ONLY = unittest.skipIf(
	not frappe.__version__.startswith("15."),
	"these tests change the guard's configuration through site_config.json, which Frappe 16 caches for 60 s (and frappe_guard is v15 only)",
)


def fetch(path, method="GET", headers=None, data=None, host=None):
	"""One request through the real Frappe application; the connection of the test is rebuilt afterwards (the app destroys it)."""
	site, sites_path = frappe.local.site, frappe.local.sites_path
	frappe.db.commit()
	from frappe.website.utils import clear_website_cache

	clear_website_cache()
	try:
		client = Client(frappe.app.application, Response)
		# the site is named by a header, so that the Host header can be any name the test wants to try
		headers = {"Host": host or site, "X-Frappe-Site-Name": site, **(headers or {})}
		response = client.open(path, method=method, headers=headers, data=data)
		return response.status_code, response.get_data(as_text=True), response.headers
	finally:
		frappe.init(site=site, sites_path=sites_path, force=True)
		frappe.connect()
		frappe.flags.in_test = True
		frappe.set_user("Administrator")


def visible_text(html):
	html = re.sub(r"<(script|style|svg)\b.*?</\1>", " ", html, flags=re.S)
	return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def prose(html):
	"""The visible words of a page without the customer's own data (an e-mail address is data, not English text)."""
	return re.sub(r"\S+@\S+", " ", visible_text(html))


def set_site_config(key, value):
	path = frappe.get_site_path("site_config.json")
	with open(path, encoding="utf-8") as handle:
		config = json.load(handle)
	if value is None:
		config.pop(key, None)
	else:
		config[key] = value
	with open(path, "w", encoding="utf-8") as handle:
		json.dump(config, handle, indent=1)
	try:  # Frappe 16 keeps the site config in a cache that a file write does not reset
		from frappe.config import clear_site_config_cache
	except ImportError:  # Frappe 15 reads the file again for each request
		return
	clear_site_config_cache()


class KitTestCase(TestCase):
	"""Puts the settings, the pages and the site config back after each test."""

	def setUp(self):
		frappe.set_user("Administrator")
		settings = frappe.get_doc(SETTINGS)
		self.saved = {
			field: settings.get(field)
			for field in (
				"brand_name",
				"contact_email",
				"contact_phone",
				"address",
				"controller_name",
				"recaptcha_site_key",
			)
		}
		self.saved_contact_us = frappe.db.get_value(
			"Contact Us Settings",
			"Contact Us Settings",
			["forward_to_email", "is_disabled", "send_acknowledgement_email"],
			as_dict=True,
		)
		self.saved_home = frappe.db.get_single_value("Website Settings", "home_page")
		self.config_keys = []

	def tearDown(self):
		for key in self.config_keys:
			set_site_config(key, None)
			frappe.conf.pop(key, None)
		settings = frappe.get_doc(SETTINGS)
		settings.update({**self.saved, "recaptcha_site_key": "", "recaptcha_secret": ""})
		settings.allow_search_engines = 0
		settings.save(ignore_permissions=True)
		frappe.db.set_value("Contact Us Settings", "Contact Us Settings", self.saved_contact_us)
		frappe.db.delete("Communication", {"subject": "New Message from Website Contact Page"})
		self.reset_pages()
		frappe.db.set_single_value("Website Settings", "home_page", self.saved_home)
		frappe.db.commit()

	def reset_pages(self):
		"""Back to a pristine install: the kit's objects and their state are removed and written again."""
		for doctype, filters in (
			(PAGE, {"name": ["like", "wk-%"]}),
			("Builder Component", {"name": ["like", "wk-%"]}),
			("Builder Client Script", {"name": specs.SCRIPT_NAME}),
		):
			for name in frappe.get_all(doctype, filters=filters, pluck="name"):
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
		frappe.db.set_single_value(SETTINGS, "pages_state", "")
		frappe.db.set_single_value(SETTINGS, "pages_note", "")
		frappe.db.commit()
		install.write_pages()
		frappe.db.commit()

	def configure(self, **values):
		settings = frappe.get_doc(SETTINGS)
		settings.update(values)
		settings.save(ignore_permissions=True)
		frappe.db.commit()

	def config(self, key, value):
		"""A site config value for the requests (the file) and for this process (`frappe.conf`, read by `apply`)."""
		set_site_config(key, value)
		frappe.conf[key] = value
		self.config_keys.append(key)

	def enable_form(self):
		self.config("guard_mode", "enforce")
		self.configure(contact_email=EMAIL, recaptcha_site_key=SITE_KEY, recaptcha_secret=SECRET)

	def page_state(self):
		return json.loads(frappe.db.get_single_value(SETTINGS, "pages_state") or "{}")

	def release(self, name, **changes):
		"""A new kit release: the shipped version of one page changes."""
		real = specs.all_specs

		def shipped():
			result = []
			for spec in real():
				if spec["name"] == name:
					fields = {**spec["fields"], **changes}
					spec = {**spec, "fields": fields, "hash": blocks.digest(fields)}
				result.append(spec)
			return result

		return mock.patch.object(specs, "all_specs", shipped)


class TestStandardPages(KitTestCase):
	def test_the_pages_components_and_script_exist(self):
		for spec in specs.all_specs():
			self.assertTrue(frappe.db.exists(spec["kind"], spec["name"]), spec["name"])
		self.assertEqual(frappe.db.count(PAGE, {"name": ["like", "wk-%"]}), 9)
		self.assertEqual(frappe.db.get_value(PAGE, "wk-contact-en", "language"), "en")
		self.assertEqual(frappe.db.get_value(PAGE, "wk-home-uk", "route"), "home")
		self.assertEqual(frappe.db.get_value(PAGE, "wk-privacy-uk", "disable_indexing"), 1)

	def test_the_site_root_serves_the_home_page(self):
		self.assertEqual(frappe.db.get_single_value("Website Settings", "home_page"), "home")
		for path in ("/", "/en"):
			status, html, _ = fetch(path)
			self.assertEqual(status, 200, path)
			self.assertIn('id="wk-main"', html)
			self.assertIn("wk-theme", html)
			self.assertIn("/assets/website_kit/css/wk.css", html)

	def test_a_closed_site_has_exactly_one_robots_meta_tag_on_every_standard_page(self):
		for path in ("/", "/about", "/contact", "/en", "/en/about"):
			html = fetch(path)[1]
			self.assertEqual(len(re.findall(r'<meta[^>]+name="robots"', html)), 1, path)
			self.assertIn("noindex", html)

	def test_a_pair_of_pages_in_the_two_languages_is_served(self):
		for path in UK_PAGES[1:]:
			for prefix, lang in (("", "uk"), ("/en", "en")):
				status, html, _ = fetch(prefix + path)
				self.assertEqual(status, 200, prefix + path)
				self.assertIn(f'<html lang="{lang}"', html)
		self.assertIn("Contact", fetch("/en/contact")[1])
		self.assertIn("Контакти", fetch("/contact")[1])

	def test_no_english_is_left_on_the_ukrainian_pages(self):
		self.configure(brand_name="Ромашка")
		allowed = {"English", "reCAPTCHA", "Google"}
		for path in UK_PAGES:
			text = prose(fetch(path)[1])
			words = set(re.findall(r"[A-Za-z]{2,}", text)) - allowed
			self.assertEqual(words, set(), path)

	def test_the_pages_have_no_script_file_except_the_contact_script(self):
		for path in ("/", "/about", "/en", "/en/about", "/privacy"):
			html = fetch(path)[1]
			self.assertEqual(re.findall(r"<script[^>]+src=", html), [], path)
		self.assertEqual(len(re.findall(r"<script[^>]+src=", fetch("/contact")[1])), 1)

	def test_site_data_is_escaped_in_the_pages(self):
		self.configure(brand_name="<b>{{ 7*7 }}</b>", address="<i>{{ 7*7 }}</i>", contact_email=EMAIL)
		for path in ("/", "/about", "/contact"):
			html = fetch(path)[1]
			self.assertNotIn("<b>{{", html)
			self.assertNotIn("<i>{{", html)
			self.assertNotIn(">49<", html)
			self.assertIn("&lt;b&gt;&#123;&#123; 7*7 &#125;&#125;&lt;/b&gt;", html, path)

	def test_closed_to_search_engines_until_the_owner_opens_the_site(self):
		status, html, headers = fetch("/about")
		self.assertEqual(headers.get("X-Robots-Tag"), "noindex, nofollow")
		self.assertIn('<meta name="robots" content="noindex, nofollow">', html)
		self.assertNotIn("application/ld+json", html)
		self.configure(allow_search_engines=1, contact_email=EMAIL)
		status, html, headers = fetch("/")
		self.assertIsNone(headers.get("X-Robots-Tag"))
		self.assertNotIn(
			"noindex",
			html.split("</head>")[0].split('<link rel="stylesheet" href="/builder_assets')[0].split("wk-theme")[-1],
		)
		self.assertIn('"@type":"Organization"', html)
		self.assertIn('hreflang="en"', html)
		self.assertIn('hreflang="x-default"', html)

	def test_the_privacy_page_names_no_controller_until_it_is_entered(self):
		self.configure(controller_name="")
		text = visible_text(fetch("/privacy")[1])
		self.assertIn("[повна назва власника даних]", text)
		self.assertIn("[строки зберігання", text)
		self.assertIn("[full name of the data controller]", visible_text(fetch("/en/privacy")[1]))
		self.configure(controller_name="ТОВ «Ромашка»")
		self.assertIn("ТОВ «Ромашка»", visible_text(fetch("/privacy")[1]))
		self.assertNotIn("[повна назва власника даних]", visible_text(fetch("/privacy")[1]))

	def test_json_ld_never_carries_a_template(self):
		self.configure(allow_search_engines=1, brand_name="{{ 7*7 }}", contact_email=EMAIL)
		html = fetch("/")[1]
		self.assertIn('"name":"\\u007b\\u007b 7*7 \\u007d\\u007d"', html)
		self.assertNotIn('"name":"{{', html)

	def test_install_twice_changes_nothing(self):
		before = (self.page_state(), frappe.get_all(PAGE, pluck="modified"))
		self.assertEqual(install.after_install(), {})
		self.assertEqual(install.after_install(), {})
		self.assertEqual(sync.sync(), {})
		self.assertEqual((self.page_state(), frappe.get_all(PAGE, pluck="modified")), before)

	def test_the_after_request_hook_survives_a_missing_response(self):
		from website_kit import runtime

		self.assertIsNone(runtime.after_request(None, None))

	def test_without_builder_nothing_is_written_and_nothing_fails(self):
		with mock.patch.object(sync, "builder_ready", return_value=False):
			self.assertEqual(sync.sync(), {})
			self.assertIsNone(install.after_migrate())

	def test_a_failing_page_sync_never_stops_the_install(self):
		with mock.patch.object(sync, "sync", side_effect=RuntimeError("builder broke")):
			self.assertIn("pages", install.write_pages())
		self.assertTrue(frappe.db.exists("Error Log", {"error": ["like", "%builder broke%"]}))


class TestUpgradePolicy(KitTestCase):
	"""Policy 5.8: a release updates an unedited page, and never overwrites an edited one."""

	NAME = "wk-about-uk"

	def test_an_unedited_page_is_updated_in_place(self):
		with self.release(self.NAME, meta_description="A new description"):
			result = sync.sync()
			self.assertEqual(result.get(f"{PAGE}:{self.NAME}"), "update")
			self.assertEqual(frappe.db.get_value(PAGE, self.NAME, "meta_description"), "A new description")
			self.assertEqual(sync.sync(), {})  # and stable
		self.assertEqual(frappe.db.count(PAGE, {"name": ["like", "wk-%"]}), 9)

	def test_an_edited_page_is_kept_and_the_new_version_becomes_a_draft(self):
		page = frappe.get_doc(PAGE, self.NAME)
		page.page_title = "Our own title"
		page.save(ignore_permissions=True)
		frappe.db.commit()
		with self.release(self.NAME, meta_description="A new description"):
			result = sync.sync()
			draft = policy.draft_name(self.NAME, specs_hash(self.NAME, meta_description="A new description"))
			self.assertEqual(result.get(f"{PAGE}:{self.NAME}"), "draft")
			self.assertEqual(frappe.db.get_value(PAGE, self.NAME, "page_title"), "Our own title")
			self.assertNotEqual(frappe.db.get_value(PAGE, self.NAME, "meta_description"), "A new description")
			self.assertEqual(
				frappe.db.get_value(PAGE, draft, ["published", "meta_description", "disable_indexing"]),
				(0, "A new description", 1),
			)
			self.assertTrue(frappe.db.get_value(PAGE, draft, "route").startswith("kit-drafts/"))
			self.assertIn(draft, frappe.db.get_single_value(SETTINGS, "pages_note"))
			self.assertEqual(fetch("/about")[0], 200)  # the live page still serves the customer's version
			self.assertEqual(sync.sync(), {})  # the draft is written once, not on every migrate
			self.assertEqual(frappe.db.count(PAGE, {"name": ["like", f"{self.NAME}-new-%"]}), 1)

	def test_a_page_deleted_by_the_customer_is_not_brought_back(self):
		frappe.delete_doc(PAGE, self.NAME, force=True, ignore_permissions=True)
		frappe.db.commit()
		self.assertEqual(sync.sync(), {})
		self.assertFalse(frappe.db.exists(PAGE, self.NAME))
		with self.release(self.NAME, meta_description="A new description"):
			self.assertEqual(sync.sync(), {})
		self.assertFalse(frappe.db.exists(PAGE, self.NAME))

	def test_an_edited_component_is_left_alone_and_a_note_is_written(self):
		name = "wk-cta-uk"
		component = frappe.get_doc("Builder Component", name)
		component.component_name = "My own CTA"
		component.save(ignore_permissions=True)
		frappe.db.commit()
		real = specs.all_specs

		def shipped():
			result = []
			for spec in real():
				if spec["name"] == name:
					fields = {**spec["fields"], "component_name": "WK CTA changed"}
					spec = {**spec, "fields": fields, "hash": blocks.digest(fields)}
				result.append(spec)
			return result

		with mock.patch.object(specs, "all_specs", shipped):
			sync.sync()
			self.assertEqual(frappe.db.get_value("Builder Component", name, "component_name"), "My own CTA")
			self.assertIn(name, frappe.db.get_single_value(SETTINGS, "pages_note"))
			self.assertEqual(sync.sync(), {})

	def test_a_foreign_page_on_the_same_route_is_never_replaced(self):
		frappe.delete_doc(PAGE, self.NAME, force=True, ignore_permissions=True)
		frappe.db.set_single_value(
			SETTINGS, "pages_state", json.dumps({k: v for k, v in self.page_state().items() if self.NAME not in k})
		)
		foreign = frappe.get_doc(
			{"doctype": PAGE, "page_title": "Mine", "route": "about", "published": 1, "blocks": "[]"}
		).insert(ignore_permissions=True)
		self.addCleanup(
			lambda: (frappe.delete_doc(PAGE, foreign.name, force=True, ignore_permissions=True), frappe.db.commit())
		)
		frappe.db.commit()
		sync.sync()
		self.assertFalse(frappe.db.exists(PAGE, self.NAME))
		self.assertEqual(frappe.db.get_value(PAGE, foreign.name, "page_title"), "Mine")
		self.assertIn("route", frappe.db.get_single_value(SETTINGS, "pages_note"))
		frappe.delete_doc(PAGE, foreign.name, force=True, ignore_permissions=True)
		frappe.db.commit()
		self.assertEqual(sync.sync().get(f"{PAGE}:{self.NAME}"), "create")  # the route is free again

	def test_the_home_route_is_set_once_and_a_cleared_field_stays_cleared(self):
		frappe.db.set_single_value("Website Settings", "home_page", "")
		frappe.db.commit()
		self.assertEqual(sync.sync(), {})  # already done at install: the marker is in the state
		self.assertEqual(frappe.db.get_single_value("Website Settings", "home_page") or "", "")

	def test_the_home_route_is_not_taken_over_when_the_customer_has_a_home_page(self):
		frappe.db.set_single_value("Website Settings", "home_page", "my-home")
		frappe.db.set_single_value("Builder Settings", "home_page", "my-home")
		self.assertNotIn("website_settings.home_page", sync.set_home_page())
		self.assertEqual(frappe.db.get_single_value("Website Settings", "home_page"), "my-home")
		frappe.db.set_single_value("Website Settings", "home_page", "home")
		frappe.db.set_single_value("Builder Settings", "home_page", "home")


def specs_hash(name, **changes):
	spec = next(s for s in specs.all_specs() if s["name"] == name)
	return blocks.digest({**spec["fields"], **changes})


class TestContactForm(KitTestCase):
	def test_without_keys_the_form_is_not_rendered_and_the_contacts_are_shown(self):
		self.configure(
			contact_email=EMAIL, contact_phone="+380 44 123-45-67", recaptcha_site_key="", recaptcha_secret=""
		)
		for path in ("/contact", "/en/contact"):
			status, html, _ = fetch(path)
			self.assertEqual(status, 200)
			self.assertNotIn("<form", html)
			self.assertNotIn("<textarea", html)
			self.assertNotIn("FRAPPE_GUARD", html)
			self.assertNotIn("guard.js", html)
			self.assertIn(f"mailto:{EMAIL}", html)
			self.assertIn("tel:+380441234567", html)

	def test_with_the_guard_missing_the_form_is_not_rendered_even_with_keys(self):
		self.enable_form()
		with mock.patch.object(contact, "guard_installed", return_value=False):
			html = fetch("/contact")[1]
		self.assertNotIn("<form", html)
		self.assertIn(f"mailto:{EMAIL}", html)

	def test_without_a_recipient_the_form_is_not_rendered(self):
		self.configure(contact_email="", recaptcha_site_key=SITE_KEY, recaptcha_secret=SECRET)
		frappe.db.set_value("Contact Us Settings", "Contact Us Settings", "forward_to_email", "")
		self.assertNotIn("<form", fetch("/contact")[1])

	def test_with_keys_the_form_is_rendered_and_marked_for_the_guard(self):
		self.enable_form()
		html = fetch("/contact")[1]
		self.assertIn('id="wk-contact-form"', html)
		self.assertIn('data-guard-action="contact"', html)
		self.assertIn(SITE_KEY, html)
		self.assertNotIn(SECRET, html)
		self.assertIn("/assets/frappe_guard/js/guard.js", html)
		self.assertIn('name="website"', html)  # the trap field
		contact_us = frappe.get_doc("Contact Us Settings")
		self.assertEqual(
			(contact_us.forward_to_email, contact_us.is_disabled, contact_us.send_acknowledgement_email), (EMAIL, 0, 0)
		)

	@V15_ONLY
	def test_platform_keys_need_the_host_in_the_guard_host_list_or_an_erp_crm_name(self):
		self.config("guard_mode", "enforce")
		self.config("guard_recaptcha_site_key", SITE_KEY)
		self.config("guard_recaptcha_secret", SECRET)
		self.configure(contact_email=EMAIL, recaptcha_site_key="", recaptcha_secret="")
		self.assertNotIn("<form", fetch("/contact")[1])  # a host the platform did not list, not an erp-crm.org name
		self.config("guard_hosts", [frappe.local.site])
		self.assertIn('data-guard-action="contact"', fetch("/contact")[1])

	def test_without_enforce_the_form_is_not_rendered_and_the_page_stays_disabled(self):
		"""The guard refuses only in enforce; in monitor (its default) a post without a token would be stored."""
		self.configure(contact_email=EMAIL, recaptcha_site_key=SITE_KEY, recaptcha_secret=SECRET)
		html = fetch("/contact")[1]
		self.assertNotIn("<form", html)
		self.assertIn(f"mailto:{EMAIL}", html)
		self.assertEqual(frappe.db.get_single_value("Contact Us Settings", "is_disabled"), 1)
		self.assertIn("enforce", frappe.db.get_single_value(SETTINGS, "contact_form_status"))
		self.assertNotIn("reCAPTCHA", visible_text(fetch("/privacy")[1]).replace("[", ""))

	def test_the_contact_page_is_enabled_only_while_the_form_is_usable_and_disabled_again(self):
		self.configure(contact_email=EMAIL)  # no keys, not enforced
		self.assertEqual(frappe.db.get_single_value("Contact Us Settings", "is_disabled"), 1)
		self.enable_form()
		self.assertEqual(frappe.db.get_single_value("Contact Us Settings", "is_disabled"), 0)
		self.assertIn("available", frappe.db.get_single_value(SETTINGS, "contact_form_status"))
		frappe.conf["guard_mode"] = "monitor"  # the guard state changes, a migrate or save notices
		from website_kit import apply

		apply.apply()
		self.assertEqual(frappe.db.get_single_value("Contact Us Settings", "is_disabled"), 1)

	def test_a_page_already_pointing_at_the_address_is_enabled_when_it_becomes_usable(self):
		frappe.db.set_value("Contact Us Settings", "Contact Us Settings", {"forward_to_email": EMAIL, "is_disabled": 1})
		self.enable_form()
		self.assertEqual(frappe.db.get_single_value("Contact Us Settings", "is_disabled"), 0)

	def test_a_privacy_page_with_placeholders_is_not_linked_from_the_form(self):
		self.enable_form()
		self.configure(controller_name="")
		self.assertNotIn("/privacy", fetch("/contact")[1].split("<footer")[0])
		self.configure(controller_name="ТОВ «Ромашка»")
		self.assertIn('href="/privacy"', fetch("/contact")[1].split("<footer")[0])

	def test_unreadable_own_keys_count_as_no_own_keys_everywhere(self):
		self.enable_form()
		frappe.db.set_single_value(SETTINGS, "recaptcha_keys_ok", 0)
		frappe.clear_document_cache(SETTINGS, SETTINGS)
		self.assertNotIn("<form", fetch("/contact")[1])

	def test_a_foss_ua_address_is_refused(self):
		settings = frappe.get_doc(SETTINGS)
		for email in (
			"someone@foss.ua",
			"a@mail.foss.ua",
			"a@foss.ua,b@example.com",
			"Evil <a@foss.ua>",
			"a@FOSS.UA.",
			"b@example.com, c@example.com",
		):
			settings.contact_email = email
			with self.assertRaises(frappe.ValidationError):
				settings.save(ignore_permissions=True)

	def test_one_key_without_the_other_is_refused(self):
		settings = frappe.get_doc(SETTINGS)
		settings.recaptcha_site_key, settings.recaptcha_secret = SITE_KEY, ""
		with self.assertRaises(frappe.ValidationError):
			settings.save(ignore_permissions=True)
		settings.recaptcha_site_key = "not a key!"
		settings.recaptcha_secret = "x"
		with self.assertRaises(frappe.ValidationError):
			settings.save(ignore_permissions=True)

	def test_the_secret_is_stored_encrypted_and_never_shown(self):
		self.enable_form()
		self.assertNotEqual(frappe.get_doc(SETTINGS).recaptcha_secret, SECRET)
		self.assertEqual(frappe.get_doc(SETTINGS).get_password("recaptcha_secret"), SECRET)
		for path in ("/contact", "/en/contact", "/privacy", "/"):
			self.assertNotIn(SECRET, fetch(path)[1])

	def test_the_acknowledgement_mail_is_switched_off(self):
		frappe.db.set_value("Contact Us Settings", "Contact Us Settings", "send_acknowledgement_email", 1)
		self.configure(contact_email=EMAIL)
		self.assertEqual(frappe.db.get_single_value("Contact Us Settings", "send_acknowledgement_email"), 0)

	def test_a_customers_own_forward_address_is_kept(self):
		frappe.db.set_value("Contact Us Settings", "Contact Us Settings", "forward_to_email", "keep@example.org")
		self.configure(contact_email=EMAIL)
		self.assertEqual(frappe.db.get_single_value("Contact Us Settings", "forward_to_email"), "keep@example.org")


@V15_ONLY
class TestSendMessageThroughTheGuard(KitTestCase):
	"""The form posts to the stock `send_message`; the guard decides, with the keys of the site, before the method runs."""

	def setUp(self):
		super().setUp()
		self.enable_form()
		frappe.db.commit()

	def post(self, token="a-token", host=None, reply_host=None, success=True):
		reply = {
			"success": success,
			"score": 0.9,
			"action": "contact",
			"hostname": reply_host or host or frappe.local.site,
		}
		from frappe_guard.providers import recaptcha_v3

		answer = mock.Mock()
		answer.json.return_value = reply
		with (
			mock.patch.object(recaptcha_v3.SESSION, "post", return_value=answer) as verify,
			mock.patch("frappe.sendmail") as sendmail,
		):
			self.sendmail = sendmail
			headers = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
			if token:
				headers["X-Guard-Token"] = token
			result = fetch(
				"/api/method/frappe.www.contact.send_message",
				method="POST",
				headers=headers,
				data={"sender": "visitor@example.com", "subject": "Hello", "message": "A <b>message</b>"},
				host=host,
			)
		return result, verify

	def communications(self):
		return frappe.get_all(
			"Communication", filters={"sender": "visitor@example.com"}, fields=["name", "content", "status"]
		)

	def test_a_valid_token_creates_a_communication_and_mails_only_the_customer(self):
		(status, body, _), verify = self.post()
		self.assertEqual(status, 200, body)
		verify.assert_called_once()
		rows = self.communications()
		self.assertEqual(len(rows), 1)
		self.assertIn("&lt;b&gt;message&lt;/b&gt;", rows[0].content)  # the stock method escaped it
		# Formatting a mail needs the built assets of Frappe, which a test bench has not: the call is checked instead.
		self.sendmail.assert_called_once()  # one mail, so no acknowledgement to the visitor
		self.assertEqual(self.sendmail.call_args.kwargs["recipients"], EMAIL)  # the customer, never a foss.ua address
		self.assertEqual(self.sendmail.call_args.kwargs["reply_to"], "visitor@example.com")

	def test_no_token_is_refused_and_nothing_is_stored(self):
		(status, body, _), verify = self.post(token=None)
		self.assertGreaterEqual(status, 400, body)
		verify.assert_not_called()
		self.assertEqual(self.communications(), [])

	def test_a_token_made_on_another_host_is_refused(self):
		(status, body, _), _ = self.post(reply_host="other.example.com")
		self.assertGreaterEqual(status, 400, body)
		self.assertEqual(self.communications(), [])

	def test_a_rejected_token_is_refused(self):
		(status, body, _), _ = self.post(success=False)
		self.assertGreaterEqual(status, 400, body)
		self.assertEqual(self.communications(), [])

	def guard_sees(self, host=None, secret_in_conf=False):
		"""Post once with the guard's provider replaced by a recorder; returns `(status, [(secret, hosts), ...])`."""
		seen = []

		class Recorder:
			def __init__(self, secret, hosts, *args, **kwargs):
				seen.append((secret, sorted(hosts)))

			def verify(self, token, action, threshold):
				from frappe_guard.policy import Outcome, Verdict

				return Verdict(Outcome.PASS, 0.9)

		with mock.patch("frappe_guard.check.RecaptchaV3", Recorder):
			with mock.patch("frappe.sendmail"):
				status, body, _ = fetch(
					"/api/method/frappe.www.contact.send_message",
					method="POST",
					headers={"Accept": "application/json", "X-Guard-Token": "tok"},
					data={"sender": "visitor@example.com", "subject": "s", "message": "m"},
					host=host,
				)
		return status, seen

	def test_the_guard_receives_the_own_secret_and_exactly_the_request_host(self):
		for host, normalised in (
			("Shop.Example.COM:8000", "shop.example.com"),
			("shop.example.com.", "shop.example.com"),
			("shop.example.com", "shop.example.com"),
		):
			status, seen = self.guard_sees(host)
			self.assertEqual(status, 200, host)
			self.assertEqual(seen, [(SECRET, [normalised])], host)

	def test_the_platform_keys_reach_the_guard_only_for_a_listed_host(self):
		self.config("guard_recaptcha_site_key", SITE_KEY)
		self.config("guard_recaptcha_secret", "p" * 40)
		self.config("guard_hosts", [frappe.local.site])
		self.configure(recaptcha_site_key="", recaptcha_secret="")
		status, seen = self.guard_sees()
		self.assertEqual((status, seen), (200, [("p" * 40, [frappe.local.site])]))
		# a host the platform did not list, and the erp-crm.org tricks: the kit adds nothing, so the guard keeps the platform's
		# own host list and a token made on the trick host would not be accepted (the recorder here accepts any token)
		for host in ("evilerp-crm.org", "x.erp-crm.org.evil.com", "evil.erp-crm.org", frappe.local.site + ".evil.com"):
			status, seen = self.guard_sees(host)
			self.assertEqual(seen, [("p" * 40, [frappe.local.site])], host)

	def test_the_site_config_is_never_written_with_a_guard_key(self):
		with open(frappe.get_site_path("site_config.json"), encoding="utf-8") as handle:
			config = json.load(handle)
		for key in ("guard_recaptcha_secret", "guard_recaptcha_site_key", "guard_hosts"):
			self.assertNotIn(key, config)
		self.assertEqual(self.post()[0][0], 200)
		with open(frappe.get_site_path("site_config.json"), encoding="utf-8") as handle:
			self.assertEqual(json.load(handle), config)


class TestCatalogueStrip(KitTestCase):
	"""The strip reads Website Items. Webshop is not in the test bench, so stand-ins of its two DocTypes are made here."""

	def setUp(self):
		super().setUp()
		self.made = []

	def tearDown(self):
		if "Website Item" in self.made:
			frappe.db.delete("Website Item")
		for doctype in self.made:
			frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True)
		frappe.db.sql_ddl(
			"DROP TABLE IF EXISTS `tabWebsite Item`"
		)  # deleting the DocType leaves the table of a custom one
		frappe.db.commit()
		super().tearDown()

	def make_webshop(self, enabled=1):
		def field(name, kind="Data"):
			return {"fieldname": name, "fieldtype": kind, "label": name}

		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": "Website Item",
				"module": "Website Kit",
				"custom": 1,
				"autoname": "hash",
				"fields": [
					field("web_item_name"),
					field("route", "Small Text"),
					field("website_image"),
					field("website_image_alt"),
					field("short_description", "Small Text"),
					field("published", "Check"),
					field("ranking", "Int"),
				],
				"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": "Webshop Settings",
				"module": "Website Kit",
				"custom": 1,
				"issingle": 1,
				"fields": [field("enabled", "Check")],
				"permissions": [{"role": "System Manager", "read": 1, "write": 1}],
			}
		).insert(ignore_permissions=True)
		self.made = ["Website Item", "Webshop Settings"]
		frappe.db.set_single_value("Webshop Settings", "enabled", enabled)
		frappe.db.commit()

	def item(self, name, published=1, route=None, image="/files/p.png", description="Short"):
		frappe.get_doc(
			{
				"doctype": "Website Item",
				"web_item_name": name,
				"route": route or f"shop/{name.lower()}",
				"website_image": image,
				"published": published,
				"short_description": description,
			}
		).insert(ignore_permissions=True)

	def home(self):
		frappe.db.commit()
		return fetch("/")[1]

	def test_nothing_is_rendered_when_webshop_is_absent(self):
		html = self.home()
		self.assertNotIn("wk-product-card", html)
		self.assertNotIn("З каталогу", visible_text(html))

	def test_nothing_is_rendered_when_the_shop_is_empty_or_off(self):
		self.make_webshop(enabled=1)
		self.assertNotIn("З каталогу", visible_text(self.home()))
		self.item("Visible")
		self.assertIn("З каталогу", visible_text(self.home()))
		frappe.db.set_single_value("Webshop Settings", "enabled", 0)
		self.assertNotIn("З каталогу", visible_text(self.home()))

	def test_published_items_are_shown_with_a_link_and_unpublished_ones_are_not(self):
		self.make_webshop()
		self.item("Alpha", description="Short text")
		self.item("Beta", published=0)
		html = self.home()
		self.assertIn("З каталогу", visible_text(html))
		self.assertEqual(html.count("wk-product-card"), 1)
		self.assertIn('href="/shop/alpha"', html)
		self.assertIn('src="/files/p.png"', html)
		self.assertIn("Alpha", html)
		self.assertNotIn("Beta", html)
		self.assertIn('href="/all-products"', html)

	def test_the_strip_is_bounded_and_never_shows_a_price(self):
		self.make_webshop()
		for number in range(12):
			self.item(f"Item{number:02d}")
		html = self.home()
		self.assertEqual(html.count("wk-product-card"), 8)
		self.assertNotRegex(visible_text(html), r"\d+[.,]\d{2}\s*(UAH|USD|грн)")

	def test_an_item_without_an_image_has_no_broken_image(self):
		self.make_webshop()
		self.item("Plain", image="")
		html = self.home()
		self.assertEqual(html.count("wk-product-card"), 1)
		card = html[html.index("wk-product-card") :]
		self.assertNotIn("<img", card.split("</section>")[0])

	def test_markup_in_an_item_name_is_escaped(self):
		"""Builder inserts a bound value as raw HTML, so the data script must escape it: markup, quotes and braces."""
		self.make_webshop()
		self.item("placeholder")
		name = frappe.db.get_value("Website Item", {"web_item_name": "placeholder"})
		# a raw value, written the way an import would (the form of the Desk sanitizes it before it is saved)
		frappe.db.set_value("Website Item", name, "web_item_name", '<script>alert(1)</script> A & "B" {{ 7*7 }}')
		html = self.home()
		self.assertNotIn("<script>alert(1)", html)
		self.assertNotIn(">49<", html)
		self.assertNotIn("{{ 7*7 }}", html)
		self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; A &amp; &quot;B&quot; &#123;&#123; 7*7 &#125;&#125;", html)
