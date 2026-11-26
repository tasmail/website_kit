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
3. Public website pages load three stylesheets: the compiled Website Theme CSS of Frappe (`/files/website_theme/website_kit_style.css`,
   the Bootstrap and Frappe website styles, compiled once by node when the theme is imported; it is not minimal), the shared
   `/assets/website_kit/css/wk.css`, and the generated `/files/wk-theme.css`. The two kit files are never linked from the Desk.
   On the Frappe 15.128.0 CI bench the files measure 453 KB raw / 69 KB gzip (Website Theme CSS), 5.9 KB / 1.5 KB (`wk.css`) and 3.7 KB / 1.0 KB (`wk-theme.css`); CI prints them on every run. A browser measurement has not been made.
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
| Size and shape | at most 32 KB, 1500 rules, block depth 3; no control or invisible characters; no `<` and no `-->` anywhere |
| At-rules | `@media` (width, height, orientation, `prefers-color-scheme`, `prefers-reduced-motion`, `screen`, `print`), `@supports`, `@font-face` (local sources only), `@keyframes` named `cx-...`; everything else, `@import` included, is rejected |
| Properties | layout, box, type, colour, background, border, shadow, flex, grid, transform, transition and animation properties; custom properties only as `--wk-...` or `--cx-...` |
| Values | no `expression()`, no script URLs, no `src()` or `attr()`; `url()` and `image-set()` only to `/files/` or `/assets/` on the same site, or to a `data:image/` of at most 4 KB; `url()` only in background, list-style and border-image properties |
| Selectors | no class, id or attribute that can match the Desk or the system UI (the classes `desk`, `navbar-desk` and `modal`, ids starting with `page-`, `data-route`); pseudo-classes from a list, no `:has()` |
| Nesting | no nested style rules |

Warnings do not block a save: `!important` outside `--wk-` properties, text and background below 4.5:1 in one rule, a rule that
hides one of the documented hooks (`wk-contact-form`, `wk-footer-legal`, `wk-price`, `wk-cart`, `wk-login-link`) with `display:none`,
`visibility:hidden`, `opacity:0`, a tiny font or zero height, and `--wk-` tokens or `wk-` classes this kit version does not know.
Valid CSS can still make a page unusable; the backstops below exist for that.

**Draft, safe mode, versions.**

- *Save as draft* writes a private file. A logged-in Website Manager sees it on the real pages with `?wk_preview=1`; nobody else does
  (such pages are not cached and are marked `noindex`). Saving the settings publishes the form values and drops the draft.
- *Safe mode*, `?wk_safe=1` (a cookie keeps it for 8 hours, `?wk_safe=0` leaves it), renders the public pages for a Website Manager
  with the token layer only and no Custom CSS. It is a view, not a fix. A visitor cannot switch it on.
- *Versions*: the last 20 saved looks (author, time, hash, preset, token overrides, Custom CSS, API version). *Restore a version*,
  *Reset Custom CSS* and *Reset to preset* each save a new version, so nothing is lost. The settings page is in the Desk and
  outside the Custom CSS, so these buttons always work.
- After an upgrade the stored Custom CSS is checked again. A rule that the new release rejects keeps the previous file and is listed
  in the notes of the settings page; the CSS is never edited or deleted by a patch.

Selectors on internal classes (such as the parts of the header) or on Frappe and Webshop markup are outside the contract above.

## Shop styling

While Webshop is on, the kit adds the body class `wk-shop` and one more stylesheet, `/assets/website_kit/css/wk-shop.css` (under 1 KB
gzip), that lets the Webshop product cards, filters and cart follow the tokens. It targets Webshop's own markup under `wk-shop`; that
markup is outside the contract above, so a Webshop release can change it. Sample products carry the hidden field `website_kit_sample`;
"Remove sample products" deletes exactly the tagged records and the pictures named `wk-sample-...svg`.
