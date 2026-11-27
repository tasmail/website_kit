"""The contact form, the fallback block and the head tags."""

import json
import re

from website_kit.pages import markup
from website_kit.pages.content import TEXT

UK, EN = TEXT["uk"], TEXT["en"]


def test_the_form_is_marked_for_the_guard_and_has_a_trap_and_labels():
	html = markup.contact_form(UK, "/privacy")
	assert 'id="wk-contact-form"' in html and 'data-guard-action="contact"' in html
	assert 'name="website"' in html and 'tabindex="-1"' in html and 'autocomplete="off"' in html
	assert html.count("<label") == 3 and html.count("</label>") == 3
	assert 'type="email"' in html and "required" in html and 'role="status"' in html
	assert 'class="wk-field"' in html and 'class="wk-button"' in html
	assert '<a href="/privacy" style="text-decoration:underline">' in html and "reCAPTCHA" in html


def test_without_a_ready_privacy_page_the_form_does_not_ask_for_consent_to_it():
	html = markup.contact_form(UK, "")
	assert "/privacy" not in html and "політиці" not in html and "reCAPTCHA" in html


def test_braces_of_a_value_never_reach_the_json_as_a_template():
	text = markup.json_script({"name": "{{ 7*7 }} {% x %}", "n": [{"a": "}}"}]})
	assert "{{" not in text and "}}" not in text.replace('"}]}', "") and "{%" not in text
	assert json.loads(text) == {"name": "{{ 7*7 }} {% x %}", "n": [{"a": "}}"}]}


def test_the_form_has_no_script_and_no_remote_url():
	html = markup.contact_form(EN, "/en/privacy")
	assert "<script" not in html and not re.search(r"https?://", html) and 'action="#"' in html


def test_a_text_cannot_break_out_of_an_attribute():
	text = dict(UK, form_subject='x" onfocus="alert(1)', form_error="<b>{{ 7*7 }}</b>")
	html = markup.contact_form(text, '/p"><script>')
	assert 'onfocus="alert' not in html and "<b>" not in html and "{{" not in html and "<script>" not in html


def test_the_contact_list_shows_only_what_was_entered_and_escapes_it():
	info = {"email": "a@b.ua", "phone": "+38 (044) 123-45-67", "address": "Київ\n<x>"}
	html = markup.contact_list(UK, info)
	assert (
		'href="mailto:a@b.ua"' in html
		and 'href="tel:+380441234567"' in html
		and "&lt;x&gt;" in html
		and "<x>" not in html
	)
	assert markup.contact_list(UK, {}, "footer") == ""
	assert UK["fallback_empty"] in markup.contact_list(UK, {}, "card")
	assert "mailto" not in markup.contact_list(UK, {"email": "not-an-address"})


def test_tel_href():
	assert markup.tel_href("+380 44 123-45-67") == "tel:+380441234567"
	assert markup.tel_href("12") == "" and markup.tel_href("") == "" and markup.tel_href(None) == ""
	assert markup.tel_href("+38+0441234") == "tel:+380441234"


def test_the_fallback_has_no_form_and_lists_the_contacts():
	html = markup.fallback(UK, {"email": "me@example.com", "phone": "+380441234567"})
	assert "<form" not in html and "<input" not in html and "<textarea" not in html
	assert "mailto:me@example.com" in html and "tel:+380441234567" in html and UK["fallback_title"] in html


def test_the_aside_is_a_card_of_the_contacts():
	html = markup.contact_aside(UK, {"email": "me@example.com"})
	assert 'class="wk-card"' in html and "mailto:me@example.com" in html


def test_head_tags_are_closed_and_minimal_by_default():
	html = markup.head_tags(
		base_css="/assets/website_kit/css/wk.css?v=1",
		theme_css="/files/wk-theme.css?v=x",
		robots_closed=True,
		alternates=[],
		organization=None,
		guard_site_key="",
	)
	assert html.count("<link") == 2 and 'content="noindex, nofollow"' in html and "<script" not in html


def test_head_tags_when_open_add_alternates_and_organization():
	html = markup.head_tags(
		base_css="/b.css",
		theme_css="javascript:alert(1)",
		robots_closed=False,
		alternates=[("uk", "https://a.com/"), ("en", "https://a.com/en")],
		organization=markup.organization_data("A</script><b>", "https://a.com", "a@a.com", ""),
		guard_site_key="",
	)
	assert "robots" not in html and 'hreflang="uk"' in html and "javascript:" not in html
	data = json.loads(re.search(r'ld\+json">(.*?)</script>', html).group(1))
	assert data["@type"] == "Organization" and data["name"] == "A</script><b>" and "telephone" not in data
	assert html.count("</script>") == 1  # the name cannot close the element


def test_the_language_cookie_script_is_added_only_for_a_kit_language():
	args = dict(
		base_css="/b.css", theme_css="", robots_closed=True, alternates=[], organization=None, guard_site_key=""
	)
	assert "preferred_language" not in markup.head_tags(**args)
	html = markup.head_tags(**args, language="uk")
	assert 'document.cookie="preferred_language="+"uk"+";path=/;max-age=31536000;SameSite=Lax"' in html
	assert 'location.protocol==="https:"?";Secure"' in html and html.count("</script>") == 1


def test_the_language_value_cannot_close_the_script():
	script = markup.language_cookie_script('uk"</script><b>')
	assert "</script>" not in script and "\\u003c" in script


def test_the_guard_client_is_loaded_only_with_a_site_key():
	html = markup.head_tags(
		base_css="/b.css",
		theme_css="",
		robots_closed=True,
		alternates=[],
		organization=None,
		guard_site_key='k"</script>',
	)
	assert (
		"/assets/frappe_guard/js/guard.js" in html and "window.FRAPPE_GUARD=" in html and html.count("</script>") == 2
	)
	assert "</script><" not in html.split("guard.js")[0].replace("</script><script", "")


def test_json_script_escapes_angle_brackets_and_ampersands():
	assert "<" not in markup.json_script({"a": "<&>"}) and json.loads(markup.json_script({"a": "<&>"})) == {"a": "<&>"}
