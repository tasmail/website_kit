"""The validator against a real browser: nothing it accepts may make Chromium request an address outside the allow-list.

Needs `playwright` and its Chromium (`pip install playwright && playwright install chromium`); skipped otherwise.
"""

import json
import random
from pathlib import Path

import pytest

from website_kit import css_validator as v

playwright = pytest.importorskip("playwright.sync_api")
import browser_oracle  # noqa: E402  (tests/ is on the path through rootdir conftest-less import mode)
import test_css_validator as fuzz  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BLOCKER = '.a{--cx-a:"//evil.example/x.png";background-image:image-set(var(--cx-a) 1x)}'
LEAKS = [
	BLOCKER,
	'.a{--cx-a:"//evil.example/l.png";list-style-image:image-set(var(--cx-a) 1x)}',
	'.a{--cx-a:"//evil.example/b.png";border-image-source:image-set(var(--cx-a) 1x);border-style:solid;border-image-slice:1}',
	".a{background:url(//evil.example/u.png)}",
	".a{background-image:image-set('//evil.example/s.png' 1x)}",
]


@pytest.fixture(scope="module")
def browser():
	with playwright.sync_playwright() as p:
		try:
			instance = p.chromium.launch()
		except Exception as error:  # browser binaries not installed
			pytest.skip(f"Chromium is not available: {error}")
		yield instance
		instance.close()


def test_the_oracle_sees_a_real_leak(browser):
	"""Without this the oracle could pass because it is blind: the known bypasses must be requested by Chromium."""
	for css, leaked in zip(LEAKS, browser_oracle.violations(browser, LEAKS), strict=True):
		assert leaked, css
		assert all("evil.example" in url for url in leaked)


def test_the_validator_rejects_every_known_leak():
	for css in LEAKS:
		assert not v.validate(css).ok, css


def accepted_mutations(count, seed=77):
	rng = random.Random(seed)
	seeds = [entry["css"] for entry in fuzz.CORPUS if len(entry["css"]) < 400]
	extra = [
		'--cx-a:"//evil.example/x.png";', "image-set(", "var(--cx-a)", "list-style-image:", "border-image-source:", "cursor:",
		"background-image:", "content:", "url(/files/a.png)", "'//evil.example/q.png'",
	]  # fmt: skip
	out = []
	while len(out) < count:
		css = fuzz.mutate(rng, rng.choice(seeds))
		if rng.random() < 0.3:
			css = css.replace("}", rng.choice(extra) + "}", 1)
		if v.validate(css).ok:
			out.append(css)
	return out


def test_nothing_the_validator_accepts_leaves_the_allow_list(browser):
	inputs = [entry["css"] for entry in fuzz.CORPUS if not entry["errors"]] + accepted_mutations(300)
	for css, leaked in zip(inputs, browser_oracle.violations(browser, inputs), strict=True):
		assert not leaked, (css, leaked)


def test_the_corpus_entries_that_use_the_allowed_urls_do_load_them(browser):
	css = ".a{background:url(/files/bg.png)}"
	assert browser_oracle.violations(browser, [css]) == [[]]
	assert json.dumps(v.validate(css).as_dict())
