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
3. Public website pages link two stylesheets: the shared `/assets/website_kit/css/wk.css` and the generated file. Neither is
   ever linked from the Desk.
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

## Custom CSS

The field exists in `Website Kit Settings` but is not applied in this release. It will be served after a validator ships; until
then nothing the customer types there reaches a page.
