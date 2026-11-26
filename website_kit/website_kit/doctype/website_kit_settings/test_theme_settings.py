"""Frappe integration tests of the theme settings: Custom CSS, versions, draft, safe mode and the whitelisted methods."""

import json
from unittest import mock

import frappe
from werkzeug.wrappers import Response

try:  # Frappe 16
	from frappe.tests import IntegrationTestCase as TestCase
except ImportError:  # Frappe 15
	from frappe.tests.utils import FrappeTestCase as TestCase

from website_kit import api, apply, install, runtime
from website_kit.theme import compiler, editor

SETTINGS = "Website Kit Settings"
CSS = ".wk-card { color: #111; border-radius: 6px; }"


def read(file_name, private=False):
	doc = frappe.get_doc("File", apply.find_theme_file(file_name, private))
	content = doc.get_content()
	return content.decode() if isinstance(content, bytes) else content


def settings():
	return frappe.get_doc(SETTINGS)


def save(**values):
	doc = settings()
	doc.update(values)
	doc.save()
	return doc


class TestThemeSettings(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.form_dict.pop("wk_safe", None)
		frappe.form_dict.pop("wk_preview", None)
		self.reset()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.form_dict.pop("wk_safe", None)
		frappe.form_dict.pop("wk_preview", None)
		self.reset()
		frappe.db.commit()

	def reset(self):
		doc = settings()
		doc.update({"preset": "clear", "custom_base": "", "token_overrides": "", "custom_css": ""})
		doc.save(ignore_permissions=True)
		apply.discard_draft()

	# Custom CSS and the files
	def test_custom_css_follows_the_tokens_in_the_theme_file_and_safe_mode_has_none(self):
		doc = save(custom_css=CSS)
		theme = read(apply.THEME_FILE)
		self.assertTrue(theme.rstrip().endswith(CSS))
		self.assertIn(compiler.CUSTOM_MARKER, theme)
		self.assertEqual(doc.theme_hash, compiler.build("clear", "", CSS)[1])
		safe = read(apply.SAFE_FILE)
		self.assertNotIn("wk-card { color", safe)
		self.assertEqual(safe, compiler.build("clear")[0])
		self.assertRegex(doc.safe_file_url, r"^/files/wk-safe[0-9a-f]*\.css$")

	def test_without_custom_css_there_is_no_safe_file(self):
		save(custom_css=CSS)
		self.assertTrue(apply.find_theme_file(apply.SAFE_FILE))
		doc = save(custom_css="")
		self.assertIsNone(apply.find_theme_file(apply.SAFE_FILE))
		self.assertFalse(doc.safe_file_url)

	def test_apply_stays_idempotent_with_custom_css(self):
		save(custom_css=CSS)
		self.assertEqual(apply.apply(), {})
		self.assertEqual(apply.apply(), {})

	def test_rejected_css_blocks_the_save_and_keeps_the_file(self):
		save(custom_css=CSS)
		before = read(apply.THEME_FILE)
		doc = settings()
		doc.custom_css = "a { color: red }\n@import url(https://evil.example/x.css);"
		with self.assertRaises(frappe.ValidationError) as caught:
			doc.save()
		self.assertIn("2:1:", str(caught.exception))
		self.assertEqual(read(apply.THEME_FILE), before)
		self.assertEqual(settings().custom_css, CSS)

	def test_every_save_path_runs_the_validator(self):
		bad = "a { background: url(//evil.example/x.png) }"
		with self.assertRaises(frappe.ValidationError):
			save(custom_css=bad)
		with self.assertRaises(frappe.ValidationError):
			api.save_draft("clear", "", bad, "")
		self.assertFalse(api.preview("clear", "", bad)["ok"])
		with self.assertRaises(compiler.CustomCssError):
			compiler.build("clear", "", bad)

	def test_a_stored_css_that_no_longer_passes_fails_closed(self):
		save(custom_css=CSS)
		self.assertIn(CSS, read(apply.THEME_FILE))
		frappe.db.set_single_value(
			SETTINGS, "custom_css", ".a{--cx-a:'//evil.example/x.png';background-image:image-set(var(--cx-a) 1x)}"
		)
		frappe.clear_document_cache(SETTINGS, SETTINGS)
		install.after_migrate()  # what `bench migrate` runs after a release with stricter rules
		served = read(apply.THEME_FILE)
		self.assertNotIn("evil.example", served)
		self.assertNotIn(compiler.CUSTOM_MARKER, served)
		self.assertEqual(served, compiler.build("clear")[0])
		doc = settings()
		self.assertIn("evil.example", doc.custom_css)  # the stored text is untouched
		self.assertIn("Not applied", doc.css_notes)
		self.assertIn("1:", doc.css_notes)
		self.assertFalse(doc.safe_file_url)
		self.assertEqual(apply.apply(), {})  # stable

	def test_the_operator_switch_turns_custom_css_off(self):
		doc = save(custom_css=CSS)
		with mock.patch.dict(frappe.conf, {"website_kit_custom_css_enabled": 0}):
			self.assertFalse(apply.custom_css_enabled())
			apply.apply()
			self.assertNotIn(compiler.CUSTOM_MARKER, read(apply.THEME_FILE))
		apply.apply()
		self.assertIn(compiler.CUSTOM_MARKER, read(apply.THEME_FILE))
		self.assertTrue(doc.theme_hash)

	def test_notes_name_what_a_new_release_no_longer_knows(self):
		doc = save(custom_css=".wk-gone { color: red } :root { --wk-removed: 1px }")
		self.assertIn("wk-gone", doc.css_notes)
		self.assertIn("--wk-removed", doc.css_notes)
		self.assertFalse(save(custom_css=CSS).css_notes)

	# versions and rollback
	def test_publish_break_restore_gives_equal_bytes(self):
		save(custom_css=CSS)
		good = read(apply.THEME_FILE)
		good_hash = settings().theme_hash
		version = settings().versions[-1].name
		save(preset="night", custom_css=".wk-card { color: #eee }")
		self.assertNotEqual(read(apply.THEME_FILE), good)
		api.restore_version(version)
		self.assertEqual(read(apply.THEME_FILE).encode(), good.encode())
		self.assertEqual(settings().theme_hash, good_hash)
		self.assertEqual(settings().versions[-1].reason, "Restored a version")

	def test_versions_are_recorded_once_per_look_and_capped(self):
		save(custom_css=".wk-card { margin: 99px }")
		count = len(settings().versions)
		save(custom_css=".wk-card { margin: 99px }")  # the same look is not recorded twice
		self.assertEqual(len(settings().versions), count)
		for number in range(25):
			save(custom_css=f".wk-card {{ margin: {number}px }}")
		rows = settings().versions
		self.assertEqual(len(rows), editor.MAX_VERSIONS)
		self.assertEqual([row.idx for row in rows], list(range(1, editor.MAX_VERSIONS + 1)))
		self.assertEqual(rows[-1].hash, settings().theme_hash)
		self.assertEqual(rows[-1].author, "Administrator")
		self.assertIn("margin: 24px", rows[-1].custom_css)

	def test_reset_custom_css_and_reset_to_preset(self):
		save(preset="market", token_overrides=json.dumps({"tokens": {"color-primary": "#112233"}}), custom_css=CSS)
		api.reset_custom_css()
		doc = settings()
		self.assertEqual((doc.custom_css, doc.preset), ("", "market"))
		self.assertIn("#112233", doc.token_overrides)
		save(custom_css=CSS)
		api.reset_to_preset()
		doc = settings()
		self.assertEqual((doc.preset, doc.token_overrides, doc.custom_css), ("market", "", ""))
		self.assertEqual(doc.theme_hash, compiler.build("market")[1])
		self.assertEqual(doc.versions[-1].reason, "Reset to the preset")

	def test_the_custom_theme_keeps_its_base_and_is_frozen(self):
		values = api.duplicate_as_custom("night", "", "")
		doc = save(**values)
		self.assertEqual((doc.preset, doc.custom_base), ("custom", "night"))
		self.assertEqual(doc.theme_hash, compiler.build("custom", doc.token_overrides, "", "night")[1])
		self.assertIn("--wk-color-bg:#", read(apply.THEME_FILE).replace(" ", ""))
		doc = save(preset="clear")
		self.assertEqual(doc.custom_base, "")

	# draft and modes
	def test_draft_is_a_private_file_linked_only_for_a_manager_in_preview_mode(self):
		save(custom_css=CSS)
		result = api.save_draft("market", "", ".wk-card { color: #222 }", "")
		self.assertRegex(result["url"], r"^/private/files/wk-draft[0-9a-f]*\.css$")
		self.assertIn("preset market", read(apply.DRAFT_FILE, private=True))
		self.assertEqual(frappe.db.get_value("File", apply.find_theme_file(apply.DRAFT_FILE, True), "is_private"), 1)
		published = read(apply.THEME_FILE)
		self.assertIn("preset clear", published)
		head = runtime.update_website_context(frappe._dict())["head_include"]
		self.assertNotIn("wk-draft", head)
		frappe.form_dict["wk_preview"] = "1"
		values = runtime.update_website_context(frappe._dict())
		self.assertIn(result["url"] + "?v=" + result["hash"], values["head_include"])
		self.assertNotIn("no_cache", values)  # the cache bypass is `frappe.local.no_cache`, set by before_request
		self.assertEqual(values["metatags"]["robots"], "noindex, nofollow")
		frappe.set_user("Guest")
		self.assertNotIn("wk-draft", runtime.update_website_context(frappe._dict())["head_include"])

	def test_saving_the_settings_publishes_and_drops_the_draft(self):
		api.save_draft("market", "", "", "")
		self.assertTrue(settings().draft_file_url)
		save(custom_css=CSS)
		self.assertFalse(settings().draft_file_url)
		self.assertIsNone(apply.find_theme_file(apply.DRAFT_FILE, True))
		self.assertFalse(apply.discard_draft())

	def test_safe_mode_links_the_file_without_custom_css_for_a_manager_only(self):
		doc = save(custom_css=CSS)
		normal = runtime.update_website_context(frappe._dict())
		self.assertIn(doc.theme_file_url, normal["head_include"])
		self.assertNotIn("no_cache", normal)
		frappe.form_dict["wk_safe"] = "1"
		safe = runtime.update_website_context(frappe._dict())
		self.assertIn(doc.safe_file_url + "?v=", safe["head_include"])
		self.assertNotIn(doc.theme_file_url, safe["head_include"])
		self.assertEqual(safe["wk"]["mode"], "safe")
		self.assertEqual(safe["metatags"]["robots"], "noindex, nofollow")
		frappe.set_user("Guest")
		guest = runtime.update_website_context(frappe._dict())
		self.assertIn(doc.theme_file_url, guest["head_include"])
		self.assertNotIn("no_cache", guest)

	def test_safe_mode_without_custom_css_links_the_normal_file(self):
		doc = save(custom_css="")
		frappe.form_dict["wk_safe"] = "1"
		self.assertIn(doc.theme_file_url, runtime.update_website_context(frappe._dict())["head_include"])

	def page(self, path="/about", scheme="http", forwarded=None):
		headers = {"X-Forwarded-Proto": forwarded} if forwarded else {}
		return Response("x", mimetype="text/html"), mock.Mock(path=path, scheme=scheme, headers=headers)

	def test_the_safe_cookie_is_secure_over_https_and_no_store_stays_on_public_pages(self):
		save(custom_css=CSS)
		frappe.form_dict["wk_safe"] = "1"
		response, request = self.page(scheme="https")
		runtime.after_request(response=response, request=request)
		cookie = response.headers["Set-Cookie"]
		for part in ("wk_safe=1", "Secure", "HttpOnly", "SameSite=Lax"):
			self.assertIn(part, cookie)
		self.assertEqual(response.headers["Cache-Control"], "private, no-store")
		response, request = self.page(forwarded="https")
		runtime.after_request(response=response, request=request)
		self.assertIn("Secure", response.headers["Set-Cookie"])
		response, request = self.page()
		runtime.after_request(response=response, request=request)
		self.assertNotIn("Secure", response.headers["Set-Cookie"])
		for path, mimetype in (
			("/app/website-kit-settings", "text/html"),
			("/api/method/ping", "application/json"),
			("/files/x.pdf", "application/pdf"),
			("/assets/x.js", "text/html"),
		):
			response, request = self.page(path)
			response.mimetype = mimetype
			runtime.after_request(response=response, request=request)
			self.assertNotIn("Cache-Control", response.headers, path)

	def test_no_store_matches_whole_path_segments(self):
		save(custom_css=CSS)
		frappe.form_dict["wk_safe"] = "1"
		for path, expected in (
			("/apple", True),
			("/apiary/x", True),
			("/application-form", True),
			("/app", False),
			("/app/x", False),
			("/api/method/ping", False),
			("/api", False),
			("/files", False),
		):
			response, request = self.page(path)
			runtime.after_request(response=response, request=request)
			self.assertEqual("Cache-Control" in response.headers, expected, path)

	def test_a_stale_draft_does_not_survive_a_migrate_or_a_new_kit_version(self):
		api.save_draft("market", "", CSS, "")
		self.assertTrue(apply.find_theme_file(apply.DRAFT_FILE, True))
		install.after_migrate()
		self.assertIsNone(apply.find_theme_file(apply.DRAFT_FILE, True))
		self.assertFalse(settings().draft_file_url)
		api.save_draft("market", "", CSS, "")
		frappe.db.set_single_value(SETTINGS, "kit_version", "0.0.0+api1")  # what an older release recorded
		frappe.clear_document_cache(SETTINGS, SETTINGS)
		self.assertEqual(apply.apply().get("draft"), "discarded")
		self.assertIsNone(apply.find_theme_file(apply.DRAFT_FILE, True))
		self.assertEqual(apply.apply(), {})

	def test_safe_mode_cookie_and_cache_bypass(self):
		save(custom_css=CSS)
		frappe.form_dict["wk_safe"] = "1"
		response, request = self.page()
		runtime.after_request(response=response, request=request)
		self.assertIn("wk_safe=1", response.headers["Set-Cookie"])
		self.assertEqual(response.headers["Cache-Control"], "private, no-store")
		frappe.local.no_cache = 0
		runtime.before_request()
		self.assertEqual(frappe.local.no_cache, 1)
		frappe.local.no_cache = 0
		frappe.form_dict["wk_safe"] = "0"
		response, request = self.page()
		runtime.after_request(response=response, request=request)
		self.assertIn("wk_safe=;", response.headers["Set-Cookie"])
		runtime.before_request()
		self.assertEqual(frappe.local.no_cache, 0)
		frappe.set_user("Guest")
		frappe.form_dict["wk_safe"] = "1"
		runtime.before_request()
		self.assertEqual(frappe.local.no_cache, 0)

	def test_a_cookie_alone_turns_safe_mode_on(self):
		save(custom_css=CSS)
		request = mock.Mock(cookies={"wk_safe": "1"})
		with mock.patch.object(frappe.local, "request", request, create=True):
			self.assertEqual(runtime.update_website_context(frappe._dict())["wk"]["mode"], "safe")

	# the whitelisted methods
	def test_the_mutating_methods_accept_post_only(self):
		allowed = frappe.allowed_http_methods_for_whitelisted_func
		for name in ("save_draft", "discard_draft", "restore_version", "reset_custom_css", "reset_to_preset"):
			self.assertEqual(allowed[getattr(api, name)], ["POST"], name)
		for name in ("theme_data", "preview", "check_css", "duplicate_as_custom"):
			self.assertIn("GET", allowed[getattr(api, name)], name)

	def test_a_draft_honours_the_operator_switch_and_takes_the_lock(self):
		with mock.patch.dict(frappe.conf, {"website_kit_custom_css_enabled": 0}):
			api.save_draft("clear", "", CSS, "")
		self.assertNotIn(compiler.CUSTOM_MARKER, read(apply.DRAFT_FILE, private=True))
		api.save_draft("clear", "", CSS, "")
		self.assertIn(compiler.CUSTOM_MARKER, read(apply.DRAFT_FILE, private=True))
		with mock.patch.object(apply, "apply_lock", wraps=apply.apply_lock) as lock:
			api.save_draft("clear", "", CSS, "")
			api.discard_draft()
		self.assertEqual(lock.call_count, 2)
		self.assertEqual(frappe.db.count("File", {"file_name": ["like", "wk-draft%"]}), 0)

	def test_the_methods_need_a_website_manager_and_none_is_open_to_guests(self):
		for name in (
			"theme_data",
			"preview",
			"check_css",
			"duplicate_as_custom",
			"save_draft",
			"discard_draft",
			"restore_version",
			"reset_custom_css",
			"reset_to_preset",
		):
			method = getattr(api, name)
			self.assertIn(method, frappe.whitelisted)
			self.assertNotIn(method, frappe.guest_methods)
		user = "wk-plain-user@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc({"doctype": "User", "email": user, "first_name": "Plain", "send_welcome_email": 0}).insert(
				ignore_permissions=True
			)
		frappe.set_user(user)
		frappe.flags.in_test = False  # `only_for` lets everyone through while the test flag is set
		try:
			with self.assertRaises(frappe.PermissionError):
				api.theme_data()
			with self.assertRaises(frappe.PermissionError):
				api.reset_to_preset()
		finally:
			frappe.flags.in_test = True
		frappe.set_user("Administrator")
		self.assertIn("presets", api.theme_data())

	def test_preview_and_check_css(self):
		data = api.preview(
			"custom", json.dumps({"tokens": {"color-text": "#fafafa"}}), ".wk-card { color: red }", "clear"
		)
		self.assertTrue(data["ok"])
		self.assertTrue(any(not check["passed"] for check in data["contrast"]))
		self.assertIn("preset custom", data["css"])
		bad = api.check_css("a { behavior: x }")
		self.assertEqual(bad["errors"][0]["code"], "property-not-allowed")
		self.assertTrue(api.preview("clear", '{"tokens": {"color-primary": "red"}}')["token_error"])

	def test_the_message_is_translated(self):
		frappe.local.lang = "uk"
		try:
			frappe.local.lang_full_dict = None
			result = api.check_css("a { behavior: x }")
			self.assertIn("behavior", result["errors"][0]["message"])
			self.assertNotIn("is not allowed", result["errors"][0]["message"])
		finally:
			frappe.local.lang = "en"
			frappe.local.lang_full_dict = None
