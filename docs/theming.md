# Theming contract

This file is the public theming API of Website Kit (`WK_THEME_API = 1`). Everything named here is stable:

- A name is never changed or removed inside a major version.
- A rename keeps the old name as an alias for two minor releases.
- `tests/test_contract.py` fails when a name documented here disappears from the code, or when the code gains a token,
  variant or class that is not documented here.

Anything not listed here (internal classes such as `.wk-header__inner`, Frappe or Webshop markup, the order of the rules in
`wk.css`) is outside the contract and may change in any release.

## How a site is themed

1. The site stores a preset name and only the values the customer changed (`Website Kit Settings`: `preset` and
   `token_overrides`).
2. `apply()` compiles them into one plain CSS file, `/files/wk-theme.css` (custom properties and `@font-face` rules, no
   SCSS, no node step). The result is deterministic: the same settings give the same bytes.
3. The Website Theme stays the stock `Standard` one, so Frappe serves its prebuilt `website.bundle.css` (Bootstrap and the Frappe
   website styles); the kit never compiles a theme on a site (no node, no sass). On top of it public pages load two kit
   stylesheets, the shared `/assets/website_kit/css/wk.css` and the generated `/files/wk-theme.css`, and while Webshop is on, on
   the shop pages, `/assets/website_kit/css/wk-shop.css`. The kit files are never linked from the Desk. Releases before 0.3 assigned
   a kit-owned Website Theme named `Website Kit`; `apply()` and `bench migrate` move a site that holds exactly that value back to
   `Standard` (any other theme is the customer's and is left alone). On the Frappe 15.128.0 CI bench `wk.css` measures
   7.5 KB / 1.8 KB and `wk-theme.css` of the `clear` preset 3.2 KB / 1.0 KB (raw / gzip); CI prints them on every run.
4. `wk.css` reads only the custom properties below, so a preset change never needs a new stylesheet.

## Tokens

Every token is a CSS custom property with the prefix `--wk-`. The preset files in `website_kit/theme/presets/` set all of
them. Overrides use the token name without the prefix, for example `{"tokens": {"color-primary": "#1d4ed8"}}`.

### Colour (a `#rrggbb` value)

| Token | Use |
| --- | --- |
| `--wk-color-primary` | buttons and the main accent fill |
| `--wk-color-primary-contrast` | text on `--wk-color-primary` |
| `--wk-color-accent` | focus ring, badges of secondary weight, small highlights |
| `--wk-color-bg` | page background |
| `--wk-color-surface` | cards, bands and the footer on a light preset |
| `--wk-color-text` | body text |
| `--wk-color-muted` | secondary text |
| `--wk-color-border` | rules and field borders |
| `--wk-color-link` | links |
| `--wk-color-danger` | errors |
| `--wk-color-inverse` | background of dark bands (a header or footer with the variant `dark`) |
| `--wk-color-inverse-contrast` | text on `--wk-color-inverse` |

### Type

| Token | Value |
| --- | --- |
| `--wk-font-body` | a font family of the font set (the override value is the slug, for example `inter`, or `system`) |
| `--wk-font-heading` | the same, for headings |
| `--wk-font-size-base` | a length, for example `16px` |
| `--wk-line-height` | a number, for example `1.6` |
| `--wk-heading-weight` | `100` to `900` in steps of 100 |
| `--wk-heading-scale` | the ratio between heading sizes, a number |

### Shape

| Token | Value |
| --- | --- |
| `--wk-radius-sm` | a length |
| `--wk-radius-md` | a length |
| `--wk-radius-lg` | a length |
| `--wk-shadow-1` | `none` or a box-shadow made of numbers, colours and `rgb()/rgba()/hsl()/hsla()` |
| `--wk-shadow-2` | the same, stronger |
| `--wk-border-width` | a length |

### Space

| Token | Value |
| --- | --- |
| `--wk-space-unit` | a length, the base of all spacing |
| `--wk-container-width` | a length, the width of `.wk-container` |
| `--wk-section-gap` | a length, the space between page sections |

## Variants

A variant is a small set of custom properties that follow the tokens. The site's choice is written to `:root`. The attribute
`data-wk-<variant>="<value>"` on any element applies the value to that element and its descendants, for example one section
of a page can be `data-wk-card="raised"`. The kit does not place these attributes on `<html>`; use them on your own elements.

| Attribute | Values | Custom properties it sets |
| --- | --- | --- |
| `data-wk-header` | `light`, `dark`, `tinted` | `--wk-header-bg`, `--wk-header-fg`, `--wk-header-border` |
| `data-wk-footer` | `light`, `dark` | `--wk-footer-bg`, `--wk-footer-fg` |
| `data-wk-card` | `flat`, `outlined`, `raised` | `--wk-card-bg`, `--wk-card-border`, `--wk-card-shadow` |
| `data-wk-button` | `solid`, `pill`, `square` | `--wk-button-radius` |

## Classes

| Class | Element |
| --- | --- |
| `.wk-container` | centred wrapper with the width of `--wk-container-width` |
| `.wk-skip-link` | the skip-to-content link, visible on focus |
| `.wk-header` | the site header |
| `.wk-footer` | the site footer |
| `.wk-card` | a card |
| `.wk-button` | a button or a link that looks like one (solid) |
| `.wk-button--secondary` | the outlined variant of `.wk-button` |
| `.wk-field` | a text input, select or textarea |
| `.wk-product-card` | a product card of the shop |
| `.wk-price` | a price |
| `.wk-badge` | a small label such as "Sale" |

## Presets

`clear` (default), `market`, `contrast`, `night`, `ledger`. Each is a JSON file of tokens and variants. CI checks the contrast
of every preset: 4.5:1 for text and 3:1 for interface parts on the surfaces the preset defines (`night` is checked on its dark
surfaces), and 7:1 for everything in `contrast`. Colours of a custom override are not checked in this release.

## Fonts

`inter`, `source-sans-3`, `manrope`, `lora`, `playfair-display`, `roboto`, and `system` (the system font stack). Details,
sizes and licences are in `docs/fonts.md`.

## The settings page

`Website Kit Settings` (Desk, `/app/website-kit-settings`) shows the ready-made themes as cards with a live preview. The
`custom` card copies the current theme once (every token is written out, so a later change of the base preset never moves it)
and opens an editor: colour pickers with contrast warnings, one of the six fonts, base size, corner radius, density and the
four variants. The preview is compiled on the server by the same code that a save runs; saving publishes.

## Custom CSS

Custom CSS is available on every plan. It is written after the generated theme and linked only from public pages, never from
the Desk, so a broken rule cannot lock anyone out of the settings page. The operator can switch it off for one site with the
site config key `website_kit_custom_css_enabled` set to `0`.

**Validation.** A parser-based validator (`website_kit/css_validator.py`, no Frappe import) checks the text on every save and in
the same compile path as the tokens (the draft, the preview and the migrate re-apply all use it). It tokenizes the CSS by the
CSS Syntax Level 3 rules, decodes escapes before it checks anything, and rejects what it does not understand; nothing is repaired.
A rejection names every problem as `line:column: reason`. The rules are one data file, `public/js/wk_css_rules.json`, which a
JavaScript twin (`public/js/wk_css_validator.js`) reads in the editor to show the same messages while you type. The server never
trusts the twin. Both are tested against one corpus of known-bad and known-good inputs (`tests/css_corpus.json`).

| Rule | Limit or list |
| --- | --- |
| Size and shape | at most 32 KB, 1500 rules, block depth 3, brackets, functions and the braces of the rules together nested at most 32 levels deep; no control or invisible characters; no `<` and no `-->` anywhere |
| At-rules | `@media` (width, height, orientation, `prefers-color-scheme`, `prefers-reduced-motion`, `screen`, `print`), `@supports`, `@font-face` (local sources only; a missing `font-display` is a warning, not changed for you), `@keyframes` named `cx-...`; everything else, `@import` included, is rejected |
| Properties | layout, box, type, colour, background, border, shadow, flex, grid, transform, transition and animation properties; custom properties only as `--wk-...` or `--cx-...` |
| Values | no `expression()`, no script URLs, no `src()` or `attr()`; `url()` and `image-set()` only to `/files/` or `/assets/` on the same site, or to a `data:image/` of at most 4 KB; `url()` only in background, list-style and border-image properties; `var()` is not allowed in any property that can load an address (background, list-style, border-image, cursor, content, filter, clip-path), because a custom property could carry a string that an image function turns into an external request |
| Selectors | no class, id or attribute that can match the Desk or the system UI (the classes `desk`, `navbar-desk` and `modal`, ids starting with `page-`, `data-route`); pseudo-classes from a list, no `:has()` |
| Nesting | no nested style rules |

Warnings do not block a save: `!important` outside `--wk-` properties, text and background below 4.5:1 in one rule, a rule that
hides one of the documented hooks (`wk-contact-form`, `wk-footer-legal`, `wk-price`, `wk-cart`, `wk-login-link`) with `display:none`,
`visibility:hidden`, `opacity:0`, a font under 12 px or zero height (an `overflow:hidden` box of zero size is not detected), and `--wk-` tokens or `wk-` classes this kit version does not know.
Valid CSS can still make a page unusable; the backstops below exist for that.

**Draft, safe mode, versions.**

- *Save as draft* writes the private file `wk-draft.css` (it honours the operator switch, like a save). A logged-in Website Manager sees it on the real pages with `?wk_preview=1`; nobody else does
  (such pages are not cached and are marked `noindex`). Saving the settings publishes the form values and drops the draft.
- *Safe mode*, `?wk_safe=1` (a cookie keeps it for 8 hours, `?wk_safe=0` leaves it), renders the public pages for a Website Manager
  with the token layer only and no Custom CSS. It is a view, not a fix. A visitor cannot switch it on.
- *Versions*: the last 20 saved looks (author, time, hash, preset, token overrides, Custom CSS, API version). *Restore a version*,
  *Reset Custom CSS* and *Reset to preset* each save a new version, so nothing is lost. The settings page is in the Desk and
  outside the Custom CSS, so these buttons always work.
- After an upgrade the stored Custom CSS is checked again. If the new rules reject it, the site fails closed: the theme file is
  rebuilt from the preset and tokens without any Custom CSS, so the rejected CSS stops being served, and the notes of the settings page say
  why. The stored text is never edited or deleted; fix it and save. A failure of the apply step for another reason (a busy lock, a full disk) is logged and the previous theme file stays, so in that case an older file is served until the next successful apply. A draft file is dropped on every migrate and whenever the kit version changes.
- The methods that change something (draft, discard, restore, resets) accept POST only.

Selectors on internal classes (such as the parts of the header) or on Frappe and Webshop markup are outside the contract above.

## Shop styling

While Webshop is on, the kit adds the body class `wk-shop` and one more stylesheet, `/assets/website_kit/css/wk-shop.css`, on the Webshop
pages only: the catalogue and its sub-routes, search, cart, orders, wishlist, checkout and the product pages. Webshop's markup is written
against Frappe's design variables (`var(--gray-800)` even in inline styles), so `wk.css` points those variables (`--text-color`,
`--text-muted`, `--gray-*`, `--border-color`, `--bg-color`, `--primary`, ...) at the kit tokens on `:root`, on every page that loads the
kit: the login page, the 404 page and the breadcrumb read them too, and Bootstrap's `!important` `.text-muted` takes the muted token. A
preset, including the dark one, therefore re-skins the stock markup without light text on a white card or grey text under 4.5:1.
`wk-shop.css` adds a few rules for the card variant, radii, fonts and the 44 px grid/list toggles. It adds no layout rules: Frappe's
`website.bundle.css` and Webshop's bundle stay in charge of the layout, which is why the kit keeps the stock `Standard` Website Theme. That
markup is outside the contract above, so a Webshop release can change it; CI renders the pages in Chrome under every preset
(`scripts/shop_layout_check.mjs`: layout, contrast, the header on every page) and fails on a change.

The keyboard focus ring (`:focus-visible`) is `!important`: Webshop's `.btn:focus { outline: none }` would otherwise hide it.

## Stock pages and the navbar

Frappe's own pages (login, update-password, signup, 404, search, orders, `/me`) are not Builder pages. Some of them (login) replace the
whole `head_include` block, so the kit's stylesheet links never reach them from the head. The WK Navbar template therefore emits the links
itself (`wk.css`, the generated token file and, on shop pages, `wk-shop.css`) together with two small inline scripts:

- the **file-uploader guard**: Frappe's website bundle calls `frappe.require("file_uploader.bundle.js")` on every page, and
  `frappe.boot.assets_json` does not exist on a website page, so the call ended in an uncaught promise rejection. The guard skips exactly
  that one call while the asset map is missing; every other `frappe.require` goes through;
- the **Webshop strings** (shop pages in a language other than English only): Frappe 15 loads no translations into website pages, so the
  `__("Add to Cart")` calls of Webshop's scripts stayed English. The server translates the strings listed in
  `translations/webshop_js_sources.txt` and the inline script merges them into `frappe._messages` as one JSON object (Frappe drops the
  attributes of script tags in a web template, so a separate `application/json` block is not possible). A `uk.csv` row with the context
  `Webshop page` wins over Frappe's translation of the same word on a shop page only ("Submit" is "Провести" in the Desk). Strings that
  nobody translates stay English.

Both scripts are inline, so the number of script files of the Builder pages stays at zero.

## One header

The header is one function (`wk_header`, `website_kit/pages/header.py`) that both the Builder pages and the stock navbar call, so a visitor
sees the same menu on the home page, the shop, the login page and the 404 page: the kit pages that exist (Home, About, Contact), the
top bar items of Website Settings (the shop entry only while the shop has a published product), the other language when its home page
exists, and one account link to `/me`, which sends a guest on to the login page (a static link: Frappe caches pages by path and language only, so the header cannot depend on who is signed in). On a stock page the language is the request language when the kit has texts for it, else English.

On the Builder pages the header is a single raw block; its markup is the function's, so the menu there is no longer edited block by
block in Builder: change the menu in Website Settings, the labels of the kit pages in `pages/content.py`.

## Header on narrow screens

Below 48 em the header menu is collapsed behind a burger button. It is a native `<details>` element with a `<summary>` (no JavaScript, no
checkbox): Enter and Space open and close it, the open state is exposed to assistive technology, the burger has an accessible name
("Menu") and a visible focus ring, and the open menu is a panel under the bar. The menu is written twice in the markup, once inside the
disclosure and once as a plain `<nav>`; the stylesheet shows exactly one of them at any width, so a screen reader never meets it twice.
At 48 em and wider the menu is always open. Escape does not close the disclosure: that would need a script, and the kit's budget for
the Builder pages is zero script files. Activating the burger again closes it.

## Sample products

Sample products carry the hidden field `website_kit_sample`; "Remove sample products" deletes exactly the tagged records and the pictures
named `wk-sample-...svg`. They are created in the site language (System Settings), in Ukrainian or English, including the item group
(`Зразки` / `Sample`) and the unit (`шт` / `Nos`); a group or unit that already exists is used and left alone, and one the kit creates
is tagged and removed with the samples. Samples loaded by an earlier release keep their English group and unit: use *Remove sample
products*, then *Load sample products* to get the translated ones.

## Known limits of the stock pages

- Webshop's search is a JavaScript call and a POST. A link such as `/all-products?search=mug` is ignored by Webshop; the kit does not
  add that behaviour.
- A visitor sees no "Add to Cart" or "Add to Quote" button on a sample product. That is Webshop's rule: the button needs a price and
  either stock or the Webshop Settings option "Allow items not in stock", and the samples are non-stock items on purpose (they leave
  no stock or accounting entries). The kit does not switch that option on; enable it in Webshop Settings to let visitors add the
  samples to the cart.
- The catalogue opens in the grid or list view Webshop chooses (its setting, not the kit's).
- Page weight on a shop page is the sum of Frappe's and Webshop's own bundles and the kit's files; the kit's part (three stylesheets
  and the inline scripts) is listed in the README.
- Escape does not close the narrow-screen menu (see above).
- The Webshop strings are merged into `frappe._messages` by an inline script. The branches `version-15` and `version-16` of Frappe
  leave that object alone afterwards; on Frappe `develop` the base template resets it after the script, so the strings would be lost
  there (not supported by this release).
