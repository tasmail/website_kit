# Fonts

Self-hosted only: the generated stylesheet requests files from `/assets/website_kit/fonts/`, never from a third-party origin.
Only the families a site chose (`--wk-font-body`, `--wk-font-heading`) get `@font-face` rules, and the browser downloads a
subset file only when a page uses a character of its `unicode-range`.

## Origin

Variable `woff2` files (weight axis) of the Latin and Cyrillic subsets, taken unchanged from the Fontsource packages
`@fontsource-variable/<family>` (version 5.3.x, built from the upstream OFL sources of google/fonts). Each directory in
`website_kit/public/fonts/<family>/` holds the licence text of the family (`LICENSE.txt`, copied from the package) next to
the font files. `tests/test_fonts.py` fails if a font file has no licence text beside it.

| Family | Licence | Weights (variable) | Latin | Cyrillic |
| --- | --- | --- | --- | --- |
| Inter | OFL-1.1 | 100-900 | 48 KB | 19 KB |
| Source Sans 3 | OFL-1.1 | 200-900 | 29 KB | 18 KB |
| Manrope | OFL-1.1 | 200-800 | 25 KB | 15 KB |
| Lora | OFL-1.1 | 400-700 | 38 KB | 21 KB |
| Playfair Display | OFL-1.1 | 400-900 | 38 KB | 21 KB |
| Roboto | OFL-1.1 | 100-900 | 43 KB | 24 KB |

Total in the repository: about 340 KB for six families. A page loads at most two families, and for a Ukrainian page about
50 to 70 KB (Latin and Cyrillic file of the body font, plus those of a different heading font). The `contrast`, `clear`, `night`
and `ledger` presets use one family each.

Note: the approved font list called Roboto Apache-2.0. The current Roboto release (v3, the one Fontsource ships) is
licensed under the SIL Open Font License 1.1, and the licence text shipped here says so.

## The OFL conditions the kit relies on

The fonts are bundled and redistributed unmodified with their licence text, and are not sold on their own. Do not rename a
file or edit one: some of these families carry a Reserved Font Name.

## Adding a font

Add the files and a licence text under `public/fonts/<slug>/`, register the family in `website_kit/theme/fonts.py`, and run
the tests. A family without Latin and Cyrillic files, or without its licence file, fails them.
