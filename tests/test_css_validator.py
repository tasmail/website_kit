"""The Custom CSS validator: the shared corpus, the documented vectors, the rules file, the fuzz run and the client twin."""

import json
import random
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from website_kit import css_validator as v
from website_kit.theme import tokens

ROOT = Path(__file__).resolve().parent.parent
CORPUS = json.loads((ROOT / "tests" / "css_corpus.json").read_text(encoding="utf-8"))
RULES = json.loads((ROOT / "website_kit/public/js/wk_css_rules.json").read_text(encoding="utf-8"))
NODE = shutil.which("node")


def triples(messages):
	return [[m.line, m.column, m.code] for m in messages]


def codes(css):
	return [m.code for m in v.validate(css).errors]


@pytest.mark.parametrize("entry", CORPUS, ids=[entry["id"] for entry in CORPUS])
def test_the_shared_corpus(entry):
	result = v.validate(entry["css"])
	assert triples(result.errors) == entry["errors"]
	assert triples(result.warnings) == entry["warnings"]
	assert result.ok == (not entry["errors"])


def test_the_corpus_covers_the_known_injection_vectors():
	ids = {entry["id"] for entry in CORPUS}
	required = {
		"unclosed-block", "unclosed-string", "unclosed-comment", "unclosed-url", "style-breakout", "html-comment-open",
		"import", "import-escaped", "charset", "layer", "unknown-at-rule", "url-protocol-relative", "url-https",
		"url-escaped-scheme", "url-function-escaped", "string-javascript-escaped", "string-javascript-fullwidth",
		"expression", "expression-escaped", "behavior", "behavior-escaped", "moz-binding", "desk-class", "desk-escaped",
		"page-id", "data-route", "too-large", "image-set-external", "font-face-external", "url-via-var-fallback",
		"url-in-custom-property", "nested-rule", "too-deep", "control-bidi", "zero-width-in-scheme",
	}  # fmt: skip
	assert required <= ids
	assert sum(1 for entry in CORPUS if not entry["errors"]) >= 40, "the corpus needs known-good inputs"
	assert sum(1 for entry in CORPUS if entry["errors"]) >= 100


def test_every_error_code_of_the_rules_is_exercised_by_the_corpus():
	seen = {code for entry in CORPUS for _, _, code in entry["errors"] + entry["warnings"]}
	assert set(RULES["messages"]) - seen == {"not-utf8"}, "add a corpus entry for the code"


def test_rules_file_matches_the_token_layer():
	custom = {tokens.css_name(name) for name in tokens.TOKENS}
	custom |= {prop for options in tokens.VARIANTS.values() for props in options.values() for prop in props}
	assert set(RULES["known_custom_properties"]) == custom


def test_rules_file_knows_every_class_of_the_contract_and_the_stylesheet():
	base = (ROOT / "website_kit/public/css/wk.css").read_text(encoding="utf-8")
	used = set(re.findall(r"\.(wk-[a-z0-9_-]+)", base))
	assert used <= set(RULES["known_classes"]), used - set(RULES["known_classes"])
	assert set(RULES["hook_classes"]) <= set(RULES["known_classes"])


def test_every_stylesheet_the_kit_generates_passes():
	"""The base stylesheet and the generated token file are valid under the validator's own value rules."""
	from website_kit.theme import compiler

	for name in ("clear", "market", "night"):
		generated = compiler.build(name)[0]
		# the generated file loads the kit's own font files, which the Custom CSS rules deliberately do not allow
		assert "@font-face" in generated
		assert not [
			e for e in v.validate(re.sub(r"@font-face\{[^}]*\}\n?", "", generated)).errors if e.code != "unknown-token"
		]


def test_bytes_input_and_bad_utf8():
	assert v.validate(b"a{color:red}").ok
	result = v.validate(b"a{color:\xff}")
	assert [m.code for m in result.errors] == ["not-utf8"]


def test_messages_have_line_and_column_and_text():
	result = v.validate("a {\n  behavior: x }")
	assert str(result.errors[0]) == "2:3: The property 'behavior' is not allowed."
	assert result.as_dict()["errors"][0] == {
		"line": 2, "column": 3, "code": "property-not-allowed",
		"message": "The property 'behavior' is not allowed.", "level": "error", "args": ["behavior"],
	}  # fmt: skip
	assert result.as_dict()["ok"] is False


def test_the_error_count_is_capped():
	css = "a{speak:x}\n" * 200
	assert len(v.validate(css).errors) == RULES["limits"]["max_errors"]


def test_it_fails_closed_on_an_internal_bug(monkeypatch):
	monkeypatch.setattr(v, "_run", lambda css, checker: 1 / 0)
	assert not v.validate("a{color:red}").ok


def test_a_rule_without_a_block_and_stray_input():
	assert "missing-block" in codes("a { color: red } b")
	assert "unbalanced" in codes("}")
	assert "bad-selector" in codes("a . b { color: red }")
	assert "bad-selector" in codes("a:%b { color: red }")
	assert "pseudo-not-allowed" in codes("a:b, { }")


def test_font_face_options():
	assert v.validate("@font-face{font-family:x;src:local(x);font-display:swap}").ok
	assert "font-face-src" in codes("@font-face{src:url(/files/f.woff2)}")
	assert "missing-block" in codes("@font-face;")


def test_url_target_rules():
	assert v.validate("a{background:url('/files/a b.png')}").ok
	assert "url-external" in codes("a{background:url(/files/\\2e\\2e/x)}")
	assert v.validate("a{background:url(data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=)}").ok


def test_media_and_supports_edge_cases():
	assert v.validate("@media (min-width: 600px), print { a { color: red } }").ok
	assert "media-not-allowed" in codes("@media (min-width) and (width: bogus) { a { color: red } }")
	assert "supports-not-allowed" in codes("@supports (color) { a { color: red } }")
	assert "supports-not-allowed" in codes("@supports (nothing: 1) { a { color: red } }")
	assert v.validate("@supports ((display: grid) and (--wk-x: 1)) { a { color: red } }").ok


def test_selector_edge_cases():
	assert v.validate("a:not(.wk-card):nth-child(odd), a::before, a:hover { color: red }").ok
	assert "selector-not-allowed" in codes("[id^='page-'] { color: red }")
	assert "bad-selector" in codes("[ ] { color: red }")
	assert "pseudo-not-allowed" in codes("a:nth-bogus(1) { color: red }")
	assert "bad-selector" in codes("a: { color: red }")
	assert v.validate("a[b] { color: red }").ok
	assert "bad-selector" in codes("a[b=url(x)] { color: red }")
	assert "bad-selector" in codes(".1 { color: red }")


def test_declaration_edge_cases():
	assert "bad-declaration" in codes("a { 1: red }")
	assert "bad-declaration" in codes("a { color }")
	assert v.validate("a { color: red; }").ok
	assert v.validate("@keyframes cx-a { 0%, 50% { top: 0 } }").ok
	assert "bad-selector" in codes("@keyframes cx-a { bogus { top: 0 } }")
	assert "missing-block" in codes("@keyframes cx-a { from }")


# ---------------------------------------------------------------- fuzz

ALPHABET = [
	"\\", "/*", "*/", '"', "'", "(", ")", "{", "}", ";", ":", "@import ", "@charset ", "url(", "url('", "javascript:",
	"vbscript:", "<", "-->", "<!--", "​", "‮", "\x00", "expression(", "behavior:", "-moz-binding:", "!important",
	"//evil.example/x", "https://evil.example/", "\\6a ", "\\000000", "image-set(", "src(", "attr(", "var(--x,", ".desk",
	"#page-x", "[data-route^='app']", "@media ", "@font-face", " ", "\n", "}", "{", "data:text/html,",
]  # fmt: skip


def mutate(rng, text):
	for _ in range(rng.randint(1, 4)):
		position = rng.randint(0, len(text))
		kind = rng.random()
		if kind < 0.5:
			text = text[:position] + rng.choice(ALPHABET) + text[position:]
		elif kind < 0.75:
			text = text[:position] + text[position + rng.randint(1, 8) :]
		else:
			other = rng.choice(CORPUS)["css"][:200]
			text = text[:position] + other + text[position:]
	return text


def fuzz_inputs(count=10000):
	rng = random.Random(20261126)
	seeds = [entry["css"] for entry in CORPUS if len(entry["css"]) < 400]
	return [mutate(rng, rng.choice(seeds)) for _ in range(count)]


COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
ESCAPE = re.compile(r"\\([0-9a-fA-F]{1,6}[ \t\n]?|[^\n])")
STRING = re.compile(r"\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*'", re.DOTALL)


def decode_escape(match):
	token = match.group(1)
	if len(token) > 1 or token[0] in "0123456789abcdefABCDEF":
		code = int(token.strip(), 16)
		return chr(code) if 0 < code <= 0x10FFFF and not 0xD800 <= code <= 0xDFFF else "�"
	return token


def oracle_violations(css):
	"""An independent, deliberately crude check of CSS that the validator accepted; returns what slipped through."""
	text = css.replace("\r\n", "\n")
	problems = []
	if "<" in text or "-->" in text:
		problems.append("markup")
	text = COMMENT.sub(" ", text)
	text = ESCAPE.sub(decode_escape, text)
	strings = STRING.findall(text)
	for item in strings:
		squeezed = re.sub(r"[\s\x00-\x20​-‏﻿]", "", item[1:-1]).lower()
		if squeezed.startswith(("javascript:", "vbscript:")):
			problems.append("script string")
	bare = re.sub(r"\s+", "", STRING.sub('""', text)).lower()
	for needle in ("@import", "@charset", "expression("):
		if needle in bare:
			problems.append(needle)
	if re.search(r"[{;](behavior|-moz-binding|-ms-filter):", "{" + bare):
		problems.append("legacy property")
	spaced = STRING.sub('""', text).lower()
	for match in re.finditer(r"(?<![\w-])url\(\s*(.{0,12})", spaced):
		target = match.group(1)
		if not target.startswith(("/files/", "/assets/", "data:image/", '""', "'")):
			problems.append("url " + target)
	return problems


def test_fuzz_never_raises_and_never_lets_a_rejected_construct_through():
	accepted = 0
	for css in fuzz_inputs():
		result = v.validate(css)  # must not raise
		if result.ok:
			accepted += 1
			assert not oracle_violations(css), (css, oracle_violations(css))
	assert accepted > 100, "the fuzz run must also exercise accepted input"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_client_twin_gives_the_same_verdicts_on_the_corpus():
	run = subprocess.run([NODE, str(ROOT / "tests/js/run_corpus.mjs")], capture_output=True, text=True, timeout=120)
	assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_client_twin_gives_the_same_verdicts_on_the_fuzz_inputs(tmp_path):
	inputs = fuzz_inputs(3000)
	path = tmp_path / "inputs.json"
	path.write_text(json.dumps(inputs), encoding="utf-8")
	run = subprocess.run(
		[NODE, str(ROOT / "tests/js/run_batch.mjs"), str(path)], capture_output=True, text=True, timeout=300
	)
	assert run.returncode == 0, run.stderr
	twin = json.loads(run.stdout)
	for css, (errors, warnings) in zip(inputs, twin, strict=True):
		result = v.validate(css)
		assert (triples(result.errors), triples(result.warnings)) == (errors, warnings), css
