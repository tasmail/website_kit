app_name = "website_kit"
app_title = "Website Kit"
app_publisher = "FOSS-On-Line"
app_description = "A default theme for Frappe sites: design tokens, five presets and self-hosted fonts"
app_email = "foss@foss.ua"
app_license = "mit"

required_apps = ["frappe"]

after_install = ["website_kit.install.after_install"]
after_migrate = ["website_kit.install.after_migrate"]
after_app_install = ["website_kit.install.after_app_install"]

# The stylesheet links and the robots tag are added to public website pages only, never to the Desk.
update_website_context = ["website_kit.runtime.update_website_context"]
after_request = ["website_kit.runtime.after_request"]
# Hands the site's reCAPTCHA keys to the guard for the request that posts the contact form (before the guard's auth hook).
# Both are listed in one assignment: a second `before_request = ...` line would replace the first.
# The kit's runtime hook keeps a manager's preview or safe-mode request out of the website page cache.
before_request = ["website_kit.contact.before_request", "website_kit.runtime.before_request"]

# The filter `wk_esc` of the standard templates: HTML escape plus brace encoding.
# The functions of `website_kit.jinja_api` are the globals the standard Builder pages call (`wk_brand`, `wk_head`, ...).
jinja = {"filters": ["website_kit.theme.escape.wk_esc"], "methods": ["website_kit.jinja_api"]}

# The setup wizard fills the brand name and the contact data once; the cache of the shop menu rule follows the Website Items.
setup_wizard_stages = "website_kit.setup.stages"
doc_events = {
	"Website Item": {
		"on_update": "website_kit.shop.clear_cache",
		"after_insert": "website_kit.shop.clear_cache",
		"on_trash": "website_kit.shop.clear_cache",
	}
}
