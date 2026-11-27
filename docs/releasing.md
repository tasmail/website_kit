# Releasing

A release that changes what a site ships (a Builder page or component, a Web Template, a stylesheet, the guard script, a translation
file) must do three things in the same pull request. CI fails otherwise.

1. **Raise `__version__`** in `website_kit/__init__.py`.
2. **Update the lock**: `python scripts/update_content_lock.py` writes `website_kit/content_lock.json` (the version and a hash of the
   shipped content). `tests/test_content_lock.py` fails when the content and the lock disagree.
3. **Add a patch** to `website_kit/patches.txt` (`website_kit.patches.vX_Y.<what>`); the usual body calls `install.after_migrate()`.

Why the patch: Press decides per app, from the files changed between two commits, whether a site update needs `bench migrate`. It does
only when `patches.txt`, `hooks.py`, fixtures, DocType files or similar change. A release of only pages, templates, CSS, Python modules
or translations is a plain "Pull": the site is moved to the new bench, no `after_migrate` runs and nothing syncs. That is what left
kitdemo on the old pages after 0.3.0 -> PR #7. `scripts/check_version_bump.py <base>` (a CI step on pull requests) compares the lock
and `patches.txt` with the base branch and fails with this explanation.

Safety net: an hourly scheduler job (`website_kit.install.heal`) compares `pages_state._sync.version` with `__version__` and, when they
differ on a site that has Builder, runs the same apply and sync once (policy 5.8: an edited page is never overwritten). It does not
replace the patch: it needs the scheduler, and it runs up to an hour late.

CI step "Upgrade from the previous release" installs the base commit with Builder, switches to the new code, runs `bench migrate` and
checks the shipped pages and the live header and 404 page.
