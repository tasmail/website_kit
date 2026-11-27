# Website Kit

A default theme and standard pages for Frappe sites (a standard Frappe app, module `Website Kit`): design tokens, five
ready-made presets, a self-hosted font set, Navbar and Footer templates on the stock Website Theme, Builder pages (Home,
About, Contact, Privacy) in Ukrainian and English, a guarded contact form, and safe defaults (closed to search engines until the
owner opens the site). MIT licence.

## Status

Early. This is the second slice (the theme layer and the standard pages); it is not released and not installed on any production
site. The pages were looked at in a browser on a test bench (see `docs/pages.md`), not on a platform site.

What exists:

- `Website Kit Settings` (a Single DocType): preset, token overrides (JSON), brand name, "Allow search engines" (off by default).
  The settings page has preset cards with a live preview, a `custom` theme editor (colours with contrast checks, fonts, corners,
  density, variants), Custom CSS with a parser-based validator and a client twin, draft preview, safe mode (`?wk_safe=1`),
  versions and "Reset to preset" (see [docs/theming.md](docs/theming.md)).
- The shop actions of the settings page (they need ERPNext and Webshop): "Enable shop" (company, price list, 12 products per page,
  the menu link), opt-in sample products (ten non-stock items with pictures the kit draws itself, every record tagged
  `website_kit_sample`) and their complete removal, `wk-shop.css` for the Webshop cards, filters and cart, the rule that an
  empty shop hides its menu entry, the setup-wizard stage (brand name and Contact Us Settings, filled once) and the opt-in
  "Personalize this site" action for sites that existed before the kit.
- The token layer (`--wk-*` custom properties and `data-wk-*` variants) and five presets as data: `clear` (default), `market`,
  `contrast` (7:1), `night`, `ledger`. They compile into one small plain CSS file per site (`/files/wk-theme.css`); there is
  no SCSS or node step at runtime. The public names are documented in [docs/theming.md](docs/theming.md) and guarded by a
  contract test.
- Six self-hosted variable fonts (Inter, Source Sans 3, Manrope, Lora, Playfair Display, Roboto), Latin and Cyrillic, each with
  its licence file ([docs/fonts.md](docs/fonts.md)).
- The standard Web Templates `WK Navbar` and `WK Footer`. The Website Theme stays the stock `Standard` one (no per-site compile).
- `apply()` (idempotent: stable file name, content-hash check, no duplicate File), `after_install`, `after_migrate`, a patch
  skeleton with the rules for patches, Ukrainian strings (`translations/uk.csv`).
- Noindex defaults: `X-Robots-Tag: noindex, nofollow` on every response and `robots.txt` that disallows everything, until
  "Allow search engines" is switched on. A robots text the customer wrote is never overwritten.
- CI: lint, unit tests with a coverage gate, a contrast check of every preset, and a clean Frappe 15 bench built from source
  (install, install again, migrate, idempotence check, integration tests). A Frappe 16 job runs best effort.

- Standard Builder pages Home, About, Contact and Privacy in `uk` and `en`, shared header, footer and call-to-action components, a
  live catalogue strip on Home (nothing is shown when the shop is empty or Webshop is absent), and a contact form that posts to
  the stock `send_message` only through `frappe_guard`; without the guard and usable keys the Contact page shows the e-mail and
  phone instead. A release updates a page the customer did not touch and writes a draft next to one that was edited.
  See [docs/pages.md](docs/pages.md).

What does not exist yet: the "Public website" switch, and any deployment. These are planned in the analysis `docs/site-default-theme-analysis.md` of `tasmail/erpnext-infra`.

Public pages keep Frappe's prebuilt `website.bundle.css` and add `wk.css` and the generated `wk-theme.css` (and `wk-shop.css` on shop pages). Measured on a Frappe 15.128.0 bench (raw / gzip): `wk.css` 10.6 KB / 2.7 KB, `wk-theme.css` of the `clear` preset 3.2 KB / 1.0 KB, `wk-shop.css` 4.6 KB / 1.7 KB; the three together are 5.4 KB gzip on a shop page (release 0.3.0: 4.4 KB). The stock navbar also writes two inline scripts into the page: the file-uploader guard (0.55 KB raw, 0.3 KB gzip, on every stock page) and, on shop pages in a language other than English, the Webshop strings (3.0 KB raw, 1.3 KB gzip for Ukrainian). The rest of a stock page, the 330 KB of HTML with its icon sprites included, is Frappe's and Webshop's own. The CI job prints the sizes of the first two files on every run.

Not verified: behaviour with the real Webshop (a stand-in of its two DocTypes is used in the tests), a real reCAPTCHA call,
Frappe 16, Builder newer than 1.36.6, Lighthouse.

## Install

```
bench get-app https://github.com/frappe/builder --branch v1.36.6
bench get-app https://github.com/tasmail/frappe-guard
bench get-app https://github.com/tasmail/website_kit
bench --site <site> install-app builder
bench --site <site> install-app frappe_guard
bench --site <site> install-app website_kit
```

Builder is needed for the pages and `frappe_guard` for the contact form; the theme alone needs neither. Install Builder (and the
guard) before the kit, or later: the kit writes its pages when Builder appears.

Installing sets the `clear` preset, writes the theme file, assigns the Navbar and Footer templates in Website Settings (only
where the site has the Frappe defaults; the Website Theme stays the stock `Standard` one, and a site that an older release had moved to the retired `Website Kit` theme is moved back by `bench migrate`), and closes the site to search engines. Installing again, or running `bench migrate`,
changes nothing that the customer set.

## Development

```
pip install ruff pytest pytest-cov jinja2 fonttools brotli
ruff check . && ruff format --check .
pytest --cov
```

The unit tests do not need a bench. The integration tests (`website_kit/website_kit/doctype/website_kit_settings/test_*.py`)
run on a bench site with Builder and `frappe_guard` installed: `bench --site <site> run-tests --app website_kit`; CI does this on
a clean bench, then measures the pages (`scripts/check_pages.py`), runs axe (`scripts/axe_check.mjs`) and drives the form in a
browser (`scripts/form_check.mjs`).

Indentation is tabs (as in Frappe); `ruff format` enforces it.

## Licence

MIT, see [LICENSE](LICENSE) and [docs/licensing.md](docs/licensing.md): the fonts keep their SIL OFL 1.1 licence, and any file
derived from Webshop or ERPNext stays GPL-3.0 in a separate directory (there is none today).
