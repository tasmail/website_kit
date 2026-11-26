import pytest

from website_kit.theme import escape


@pytest.mark.parametrize(
	("text", "expected"),
	[
		("plain", "plain"),
		("{{ 7*7 }}", "&#123;&#123; 7*7 &#125;&#125;"),
		("{% if x %}", "&#123;% if x %&#125;"),
		("{# note #}", "&#123;# note #&#125;"),
		("<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;"),
		("a \"quoted\" 'value'", "a &quot;quoted&quot; &#x27;value&#x27;"),
		("Ромашка & Ко", "Ромашка &amp; Ко"),
		(None, ""),
		(5, "5"),
	],
)
def test_esc(text, expected):
	assert escape.esc(text) == expected


def test_escaped_text_has_no_jinja_delimiters():
	out = escape.esc("{{ config }}{%- x -%}{# y #}")
	assert "{" not in out and "}" not in out


def test_the_escaped_text_is_inert_in_jinja():
	jinja2 = pytest.importorskip("jinja2")
	payload = "{{ 7*7 }} {% set a = 1 %}"
	template = jinja2.Environment().from_string("<b>" + escape.esc(payload) + "</b>")
	assert "49" not in template.render()


@pytest.mark.parametrize(
	"url",
	["/files/wk-theme.css", "/assets/website_kit/x.css", "https://example.com/a.png"],
)
def test_safe_url_accepts(url):
	assert escape.safe_url(url) == url


@pytest.mark.parametrize(
	"url",
	[
		"",
		None,
		"javascript:alert(1)",
		"//evil.example/x",
		"http://example.com/a",
		"/files/a b.css",
		'/files/a".css',
		"/files/<x>.css",
		"/files/{{x}}.css",
		"/etc/passwd",
		"data:text/css,a{}",
	],
)
def test_safe_url_rejects(url):
	assert escape.safe_url(url) == ""


def test_the_jinja_filter_is_esc():
	assert escape.wk_esc("{{ x }}<") == escape.esc("{{ x }}<")
