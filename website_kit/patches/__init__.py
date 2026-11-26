"""Patches of Website Kit (listed in `patches.txt`, run by `bench migrate`).

Rules:

1. A patch never writes `token_overrides` or `custom_css` of Website Kit Settings, and never deletes them. Those two fields
   are the customer's data. A patch may read them (for example to report a token that no longer exists) and report.
2. Standard objects (the Website Theme, the Web Templates, the presets, the stylesheets, `uk.csv`) move with the app code
   and need no patch.
3. A patch is idempotent: running it twice changes nothing the second time.
4. A patch that changes a data object the customer can edit writes the new version next to it and leaves the customer's
   version alone.
5. Name a patch by the release that adds it: `website_kit.patches.v0_2.<what_it_does>`.

`tests/test_patches.py` enforces rule 1 by scanning the patch modules.
"""
