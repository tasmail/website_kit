from website_kit import seo, settings_sync


def test_closed_by_default_texts():
	assert seo.robots_txt(False) == "User-agent: *\nDisallow: /\n"
	assert "Disallow: /app" in seo.robots_txt(True)
	assert "Disallow: /\n" not in seo.robots_txt(True).replace("Disallow: /app", "")


def test_headers_and_metatags():
	assert seo.response_headers(False) == {"X-Robots-Tag": "noindex, nofollow"}
	assert seo.response_headers(True) == {}
	assert seo.metatags(None, False) == {"robots": "noindex, nofollow"}
	assert seo.metatags({"description": "d"}, True) == {"description": "d"}
	assert seo.metatags({"robots": "index"}, False) == {"robots": "index"}


def test_generated_robots_detection():
	assert seo.is_generated(None) and seo.is_generated("  \n")
	assert seo.is_generated(seo.ROBOTS_CLOSED) and seo.is_generated(seo.ROBOTS_OPEN)
	assert seo.is_generated(seo.ROBOTS_CLOSED.replace("\n", "\r\n"))
	assert not seo.is_generated("User-agent: *\nDisallow: /private\n")


def test_robots_change_never_replaces_the_customers_text():
	custom = "User-agent: *\nDisallow: /private\n"
	assert seo.robots_change(custom, False) is None
	assert seo.robots_change(custom, True) is None
	assert seo.robots_change(None, False) == seo.ROBOTS_CLOSED
	assert seo.robots_change(seo.ROBOTS_CLOSED, False) is None
	assert seo.robots_change(seo.ROBOTS_CLOSED, True) == seo.ROBOTS_OPEN
	assert seo.robots_change(seo.ROBOTS_OPEN, False) == seo.ROBOTS_CLOSED


def test_website_settings_changes_on_a_fresh_site():
	changes = settings_sync.website_settings_changes({}, False)
	assert changes == {
		"website_theme": "Website Kit",
		"navbar_template": "WK Navbar",
		"footer_template": "WK Footer",
		"robots_txt": seo.ROBOTS_CLOSED,
	}


def test_website_settings_changes_is_empty_when_applied():
	current = {**settings_sync.website_settings_changes({}, False)}
	assert settings_sync.website_settings_changes(current, False) == {}


def test_customer_choices_are_kept():
	current = {
		"website_theme": "My Theme",
		"navbar_template": "My Navbar",
		"footer_template": "Standard Footer",
		"robots_txt": "User-agent: Googlebot\nDisallow:\n",
	}
	assert settings_sync.website_settings_changes(current, False) == {"footer_template": "WK Footer"}


def test_the_stock_defaults_may_be_replaced():
	current = {"website_theme": "Standard", "navbar_template": "Standard Navbar"}
	changes = settings_sync.website_settings_changes(current, True)
	assert changes["website_theme"] == "Website Kit"
	assert changes["navbar_template"] == "WK Navbar"
