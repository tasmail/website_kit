# Standard pages

Website Kit ships four Builder pages in two languages, built from real block trees, three shared Builder Components and one
client script. Ukrainian is the default language and lives at the root; English lives under `/en`.

| Page | Ukrainian | English | Notes |
| --- | --- | --- | --- |
| Home | `/` (route `home`) | `/en` | hero, three cards, the live catalogue strip, the call to action |
| About | `/about` | `/en/about` | text, the contact facts, the call to action |
| Contact | `/contact` | `/en/contact` | the form, or the mail-to and phone block (see below) |
| Privacy | `/privacy` | `/en/privacy` | a template with placeholders, closed to indexing as shipped |

The object names are fixed: Builder Pages `wk-<page>-<lang>`, Builder Components `wk-header-<lang>`, `wk-footer-<lang>` and
`wk-cta-<lang>`, and the Builder Client Script `WK Contact` (loaded by the two Contact pages only). The pages are written only
when Builder is installed; without Builder the kit still themes the site and nothing fails.

## How the pages are styled

Blocks carry layout only, and every value is a `--wk-*` custom property of the theming contract (`docs/theming.md`) or one of
its documented classes, so a preset change restyles all pages at once and no page holds a literal colour. Each page links the
kit's two stylesheets (`wk.css` and the generated `wk-theme*.css`) from its `head_html` through the Jinja function `wk_head`;
the Frappe Website Theme bundle is not loaded, which is why the pages are light. The illustrations are inline SVG made for the
kit, painted with the tokens; there is no image file, no photo and no web font request of their own.

Builder Tokens are not seeded: the generated theme file already defines every `--wk-*` property, and a second source of the
same values (Builder's `tokens.css`) would only have to be kept in step. In the editor use the custom value `var(--wk-color-primary)`.

## Jinja functions

Builder renders block text, attributes and `head_html` through Jinja. The pages call these functions (registered in `hooks.py`,
defined in `website_kit/jinja_api.py`); each escapes what it returns, never raises, and returns an empty string on an error:

| Call | Returns |
| --- | --- |
| `wk_head(lang, page)` | stylesheet links, `noindex` while the site is closed, hreflang pairs, Organization JSON-LD when the site is open, the guard client on the Contact page when the form is shown |
| `wk_brand(lang)` | the brand name (Settings, else the app name of Website Settings, else the site name) |
| `wk_contact_list(lang, variant)` | the e-mail, phone and address entered in Website Kit Settings, as a list |
| `wk_contact_form(lang)` | the form, or the fallback block |
| `wk_contact_aside(lang)` | the contacts card next to the form (empty while the fallback shows them) |
| `wk_controller(lang)` | the data controller of the Privacy page, or its placeholder |
| `wk_privacy_captcha(lang)` | the reCAPTCHA paragraph of the Privacy page, only while the form exists |

## The catalogue strip

The Home page has a data script (`website_kit/pages/catalogue.py`) that reads the published Website Items: one query, at most 8
rows, no price lookup, ordered by ranking. The section is hidden (`wk_has_products` false) when Webshop is absent, the shop is
switched off in Webshop Settings, or no item is published, and a database error also renders nothing. Names, descriptions and
paths are escaped in the script, braces included, because Builder inserts a bound value as raw HTML. A page with a data script is
not page-cached by Frappe, so the strip always shows the current items.

## The contact form

The form posts to the stock `frappe.www.contact.send_message`, which validates the address, escapes the message, stores a
`Communication` and mails the address in Contact Us Settings. There is no new guest endpoint. It always goes through
`frappe_guard` (action `contact`): the markup is marked for the guard, the page script (`website_kit/pages/wk_contact.js`)
calls `FrappeGuard.request` and refuses to send when the guard client is missing, before 3 seconds have passed since the page
opened, or when the hidden trap field is filled.

**A form that posts without the guard does not exist.** The form is rendered only when all of these hold, otherwise the page
shows the e-mail and phone from Website Kit Settings instead (and the privacy page leaves out the reCAPTCHA paragraph):

- the `frappe_guard` app is installed;
- the guard **refuses** a failed check for the `contact` action: `guard_mode` (or `guard_actions.contact.mode`) in the site
  config is `enforce`. In `monitor`, the guard's default, it only logs and a post without a token would be stored, so the kit
  shows no form and makes no claim of protection (the privacy page leaves out the reCAPTCHA paragraph);
- usable reCAPTCHA v3 keys exist for the host the page is served on (below);
- Contact Us Settings is enabled and has one plain recipient address (`forward_to_email`; no list, no display name, never
  `foss.ua` or a subdomain, in any spelling).

Contact Us Settings follows Website Kit Settings: saving a contact e-mail there sets `forward_to_email` (only while it is empty
or still the address the kit wrote before). The stock contact page is reachable by anyone once enabled, so the kit enables it
only while the form is usable (guard installed, enforce, keys, a valid address) and disables it again on the next save or
migrate when that stops being true; `Contact form status` in Website Kit Settings says whether the form is shown and why not.
The acknowledgement e-mail, a mail to a stranger, is switched off when the kit takes the page over. An address at `foss.ua` or a
subdomain of it, a list of addresses or an address with a display name is refused.

**Platform requirement:** `guard_mode` `enforce` (or `guard_actions.contact.mode`) in the site config, and `guard_trusted_hops`
(otherwise the guard cannot tell the client address). The kit does not set them.

### Where the keys come from

1. **The customer's own keys**, entered in Website Kit Settings (a site key and a secret key, stored encrypted; both or neither).
   The customer registers their own domain with Google. Tokens are accepted from the host the request came to.
2. **Keys the platform put in the site config** (`guard_recaptcha_site_key`, `guard_recaptcha_secret`) when the guard's
   `guard_hosts` already names the host.
3. **The shared erp-crm.org keys** (the same site config names, provided by the platform) while the customer has entered none,
   on a host that ends in `.erp-crm.org` and equals the site's own name. A custom domain of the site does not get them (a token
   made on another host would be refused), so it shows the fallback.

### How the guard gets the keys without a change in the guard

`frappe_guard` reads `guard_recaptcha_site_key`, `guard_recaptcha_secret` and `guard_hosts` from `frappe.conf`, with an exact
host list. The kit's `before_request` hook (`website_kit.contact.before_request`) runs before the guard's `auth_hooks`, and for
the one request that posts to `send_message` it adds the keys of the site to the **request's own copy** of the config. Nothing
is written to the site config, the database or a log, and an error leaves the config as it was, so the guard decides with what
the platform configured. The page needs only the public key; the secret is decrypted only for that request (Frappe forbids
reading a password while a page renders).

Follow-up for `frappe_guard` (not done here, the guard repository is not changed by this pull request): a supported way to give
it per-site keys and suffix hosts would remove the dependency on the hook order. Either a hook (for example `guard_key_providers`)
consulted before the site config, or a rule "when `guard_hosts` is empty, accept the request's own host" together with a suffix
list (`.erp-crm.org`) that is matched against the site name, and per-site keys in `Guard Settings`. Also: the guard's mode is
the platform's (a new site starts in `monitor`, which logs and never refuses; the kit does not force `enforce`), and
`guard_trusted_hops` must be set on the platform, otherwise the guard cannot tell the client address.

## Privacy page

A template with placeholders. It names no controller until `Data controller name` is filled in Website Kit Settings, is not linked from the form until then, and shows
`[full name of the data controller]` and a bracketed line for the retention period, the legal basis and the contact for requests,
which the customer writes in the Builder editor. It claims only what the site does: the form data goes to the owner's e-mail and
is kept as an incoming message, and (only while the form is shown) that the form uses Google reCAPTCHA. The page is closed to
indexing as shipped; the legal text is the customer's.

## Upgrades and the customer's edits (policy 5.8)

Builder's own import of `builder_files` would overwrite an edited record whenever a newer file ships, so the kit does not use
that folder. It builds its objects from `website_kit/pages/specs.py` and writes them itself (`website_kit/pages/sync.py`), on
install, on migrate and when Builder is installed after the kit. It remembers per object what it shipped last
(`Website Kit Settings.pages_state`) and decides by `website_kit/pages/policy.py`:

| Situation | Action |
| --- | --- |
| the record is missing and was never shipped | create it |
| the record was deleted by the customer | leave it deleted |
| another page already uses the route | do not create, say so in the note |
| the shipped version did not change | nothing |
| it changed and the record is unedited (`modified` is the recorded one) | update in place |
| it changed and the record was edited, a page | write the new version as an unpublished draft `wk-<page>-<lang>-new-<hash>` on the route `kit-drafts/...`, once, and say so in the note |
| it changed and the record was edited, a component or the script | leave it and say so in the note |

The note is `Website Kit Settings.pages_note`. A page or component is edited as soon as it is saved in Builder, whatever the
change. Keep the block ids of a component stable across releases: the instances in pages point at them.

The home route is written to `Website Settings.home_page` and `Builder Settings.home_page` once, only where they are empty; a
customer who clears the field later is not overruled.

## Measured (Frappe 15.128.0, Builder 1.36.6, preset `clear`)

`scripts/check_pages.py` fetches each page and the stylesheets and scripts it links, and sums the gzip size of the documents.
CI runs it, and `scripts/axe_check.mjs` (axe-core in headless Chrome at 1440 and 390 px) and `scripts/form_check.mjs`. The
numbers of the run that produced this pull request are in its description. Web fonts are woff2 and are not in the sum: the
default preset names Inter, whose Latin and Cyrillic files are about 66 KB together, fetched by the browser only for the glyphs
the page uses.
