# Website Kit

A default theme for Frappe sites (a standard Frappe app, module `Website Kit`): design tokens, five ready-made presets,
a self-hosted font set, a standard Website Theme with Navbar and Footer templates, and safe defaults (closed to search engines
until the owner opens the site). MIT licence.

## Status

Early. This is the first slice (the skeleton and the theme layer); it is not released, not installed on any production site,
and has not been looked at in a browser.

What exists:

- `Website Kit Settings` (a Single DocType): preset, token overrides (JSON), brand name, "Allow search engines" (off by default).
  The `custom_css` field is a read-only placeholder; nothing typed there is ever served.
- The token layer (`--wk-*` custom properties and `data-wk-*` variants) and five presets as data: `clear` (default), `market`,
  `contrast` (7:1), `night`, `ledger`. They compile into one small plain CSS file per site (`/files/wk-theme.css`); there is
  no SCSS or node step at runtime. The public names are documented in [docs/theming.md](docs/theming.md) and guarded by a
  contract test.
- Six self-hosted variable fonts (Inter, Source Sans 3, Manrope, Lora, Playfair Display, Roboto), Latin and Cyrillic, each with
  its licence file ([docs/fonts.md](docs/fonts.md)).
- A standard Website Theme and the standard Web Templates `WK Navbar` and `WK Footer`.
- `apply()` (idempotent: stable file name, content-hash check, no duplicate File), `after_install`, `after_migrate`, a patch
  skeleton with the rules for patches, Ukrainian strings (`translations/uk.csv`).
- Noindex defaults: `X-Robots-Tag: noindex, nofollow` on every response and `robots.txt` that disallows everything, until
  "Allow search engines" is switched on. A robots text the customer wrote is never overwritten.
- CI: lint, unit tests with a coverage gate, a contrast check of every preset, and a clean Frappe 15 bench built from source
  (install, install again, migrate, idempotence check, integration tests). A Frappe 16 job runs best effort.

What does not exist yet: Builder pages (home, contact, about), the settings page with preset cards and the Custom CSS editor and
validator, the shop (Webshop) styling and sample products, the guard integration for the contact form, the "Public website"
switch, and any deployment. These are planned in the analysis `docs/site-default-theme-analysis.md` of `tasmail/erpnext-infra`.

Not verified: how the pages look (no screenshots), behaviour with Webshop and Builder installed, Frappe 16.

## Install

```
bench get-app https://github.com/tasmail/website_kit
bench --site <site> install-app website_kit
```

Installing sets the `clear` preset, writes the theme file, assigns the Website Kit theme and templates in Website Settings (only
where the site has the Frappe defaults), and closes the site to search engines. Installing again, or running `bench migrate`,
changes nothing that the customer set.

## Development

```
pip install ruff pytest pytest-cov jinja2
ruff check . && ruff format --check .
pytest --cov
```

The unit tests do not need a bench. The integration tests (`website_kit/website_kit/doctype/website_kit_settings/test_*.py`)
run on a bench site: `bench --site <site> run-tests --app website_kit`; CI does this on a clean bench.

Indentation is tabs (as in Frappe); `ruff format` enforces it.

## Licence

MIT, see [LICENSE](LICENSE) and [docs/licensing.md](docs/licensing.md): the fonts keep their SIL OFL 1.1 licence, and any file
derived from Webshop or ERPNext stays GPL-3.0 in a separate directory (there is none today).
