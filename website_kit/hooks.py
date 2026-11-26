app_name = "website_kit"
app_title = "Website Kit"
app_publisher = "FOSS-On-Line"
app_description = "A default theme for Frappe sites: design tokens, five presets and self-hosted fonts"
app_email = "foss@foss.ua"
app_license = "mit"

required_apps = ["frappe"]

after_install = ["website_kit.install.after_install"]
after_migrate = ["website_kit.install.after_migrate"]

# The stylesheet links and the robots tag are added to public website pages only, never to the Desk.
update_website_context = ["website_kit.runtime.update_website_context"]
before_request = ["website_kit.runtime.before_request"]
after_request = ["website_kit.runtime.after_request"]

# The filter `wk_esc` of the standard templates: HTML escape plus brace encoding.
jinja = {"filters": ["website_kit.theme.escape.wk_esc"]}

# The setup wizard fills the brand name and the contact data once; the cache of the shop menu rule follows the Website Items.
setup_wizard_stages = "website_kit.setup.stages"
doc_events = {
	"Website Item": {
		"on_update": "website_kit.shop.clear_cache",
		"after_insert": "website_kit.shop.clear_cache",
		"on_trash": "website_kit.shop.clear_cache",
	}
}
