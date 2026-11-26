# Licensing

Website Kit is licensed under the MIT licence (`LICENSE`). Every source file of the kit is covered by it without a per-file
header: the licence of the repository applies, and `pyproject.toml` and `hooks.py` state `mit`.

## Files that are not MIT

- **Fonts** in `website_kit/public/fonts/` keep their own licence (SIL Open Font License 1.1), stored beside each family.
- **Derived files stay GPL-3.0.** Any file copied or derived from the Webshop app or ERPNext (both GPL-3.0) keeps the GPL-3.0
  licence and a header that says so, and lives in its own directory `website_kit/gpl/` with a `LICENSE` file. The kit has no such
  file today. The decision O5 of the analysis (MIT for the kit, GPL-3.0 for derived files in a separate directory) is
  pending a legal read; do not copy a Webshop or ERPNext file before that read.
- Frappe itself is MIT. The kit calls it through hooks and does not copy its files.

## Header policy

- No header in MIT files of the kit.
- A GPL-3.0 derived file starts with `SPDX-License-Identifier: GPL-3.0-or-later`, the name of the original file and its
  repository.
- A font file carries no header; its licence text sits in the same directory.
