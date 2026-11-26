"""The Custom CSS validator (docs/theming.md, "Custom CSS"): a tokenizer and parser, not a pattern match.

The input is tokenized by the CSS Syntax Level 3 rules (escapes are decoded, comments and strings are real tokens), grouped
into blocks and rules, and every rule, selector, property and value is checked against `public/js/wk_css_rules.json`. The
browser editor runs a JavaScript twin of this module (`public/js/wk_css_validator.js`) over the same rules file; both are tested
against the shared corpus `tests/css_corpus.json`, so they cannot drift.

The module fails closed: whatever it does not understand is an error, nothing is repaired, and it never raises for any input
(a bug inside it is reported as an error too). It does not import Frappe.

`validate(css)` returns a `Result`: `errors` block the save, `warnings` are shown only. Each message has `line`, `column`
(both start at 1, counted in code points), `code` (the key of the rules file `messages`) and the English `message`.
"""

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from .theme import contrast

RULES_FILE = Path(__file__).resolve().parent / "public" / "js" / "wk_css_rules.json"
RULES = json.loads(RULES_FILE.read_text(encoding="utf-8"))
LIMITS = RULES["limits"]
MESSAGES = RULES["messages"]

_SETS = {
	key: frozenset(RULES[key])
	for key in (
		"at_rules",
		"media_idents",
		"media_features",
		"properties",
		"font_face_properties",
		"functions",
		"font_face_functions",
		"url_properties",
		"url_capable_properties",
		"pseudo_classes",
		"pseudo_legacy_elements",
		"pseudo_elements",
		"pseudo_selector_functions",
		"pseudo_nth_functions",
		"forbidden_classes",
		"forbidden_attributes",
		"hook_classes",
		"known_classes",
		"known_custom_properties",
	)
}
WHITESPACE = " \t\n"
INVISIBLE = frozenset(
	[0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2028, 0x2029, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E]
	+ [0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF, 0xFFF9, 0xFFFA, 0xFFFB]
)
DATA_URL = re.compile(r"data:image/(png|jpeg|webp|gif|svg\+xml);", re.ASCII)
SAME_ORIGIN = ("/files/", "/assets/")
PUNCT = ":;,{}()[]"
SELECTOR_DELIMS = frozenset("*>+~|")
HEX_COLOUR = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", re.ASCII)


@dataclass
class Message:
	line: int
	column: int
	code: str
	message: str
	level: str  # "error" or "warning"
	args: tuple = ()

	def __str__(self) -> str:
		return f"{self.line}:{self.column}: {self.message}"

	def key(self) -> tuple:
		return (self.level, self.line, self.column, self.code)

	def as_dict(self, translate=None) -> dict:
		text = self.localized(translate) if translate else self.message
		return {
			"line": self.line,
			"column": self.column,
			"code": self.code,
			"message": text,
			"level": self.level,
			"args": list(self.args),
		}

	def localized(self, translate) -> str:
		"""The message text through a translation function such as `frappe._` (the English template is the key)."""
		return format_message(self.code, *self.args, translate=translate)


@dataclass
class Result:
	errors: list[Message] = field(default_factory=list)
	warnings: list[Message] = field(default_factory=list)

	@property
	def ok(self) -> bool:
		return not self.errors

	def as_dict(self, translate=None) -> dict:
		return {
			"ok": self.ok,
			"errors": [m.as_dict(translate) for m in self.errors],
			"warnings": [m.as_dict(translate) for m in self.warnings],
		}


def format_message(code: str, *args, translate=None) -> str:
	text = translate(MESSAGES[code]) if translate else MESSAGES[code]
	for index, value in enumerate(args):
		text = text.replace("{" + str(index) + "}", str(value))
	return text


def _short(text, limit=40) -> str:
	text = str(text)
	return text if len(text) <= limit else text[:limit] + "..."


# ---------------------------------------------------------------- tokenizer


class Tok:
	"""A token: `type` is ws, ident, function, at, hash, string, url, num, pct, dim, delim or punct."""

	__slots__ = ("type", "value", "unit", "line", "col")

	def __init__(self, type_, value, line, col, unit=""):
		self.type = type_
		self.value = value
		self.unit = unit
		self.line = line
		self.col = col


class Node:
	"""A block of the token tree: a function, `(...)`, `[...]` or `{...}` with its child nodes and tokens."""

	__slots__ = ("kind", "name", "children", "line", "col")

	def __init__(self, kind, name, line, col):
		self.kind = kind  # fn, paren, bracket, brace
		self.name = name
		self.children = []
		self.line = line
		self.col = col


def _name_start(c: str) -> bool:
	return c.isascii() and (c.isalpha() or c == "_") or ord(c) >= 0x80


def _name_char(c: str) -> bool:
	return _name_start(c) or (c.isascii() and c.isdigit()) or c == "-"


def _hex(c: str) -> bool:
	return c != "" and c in "0123456789abcdefABCDEF"


class Tokenizer:
	def __init__(self, text: str, sink):
		self.cs = list(text)
		self.n = len(self.cs)
		self.sink = sink
		self.line_of = []
		self.col_of = []
		line = col = 1
		for c in self.cs:
			self.line_of.append(line)
			self.col_of.append(col)
			if c == "\n":
				line += 1
				col = 1
			else:
				col += 1

	def at(self, i):
		return self.cs[i] if 0 <= i < self.n else ""

	def error(self, code, i, *args):
		i = min(i, self.n - 1) if self.n else 0
		self.sink(code, self.line_of[i] if self.n else 1, self.col_of[i] if self.n else 1, *args)

	def valid_escape(self, i) -> bool:
		return self.at(i) == "\\" and self.at(i + 1) not in ("", "\n")

	def starts_ident(self, i) -> bool:
		c = self.at(i)
		if c == "-":
			d = self.at(i + 1)
			return d != "" and (_name_start(d) or d == "-" or self.valid_escape(i + 1))
		if c == "\\":
			return self.valid_escape(i)
		return c != "" and _name_start(c)

	def starts_number(self, i) -> bool:
		c, d = self.at(i), self.at(i + 1)
		if c.isascii() and c.isdigit():
			return True
		if c in ("+", "-"):
			return (d.isascii() and d.isdigit() and d != "") or (
				d == "." and self.at(i + 2).isascii() and self.at(i + 2).isdigit() and self.at(i + 2) != ""
			)
		return c == "." and d != "" and d.isascii() and d.isdigit()

	def escape(self, i):
		"""Decode the escape whose backslash is at `i`; returns `(char, next index)`."""
		i += 1
		c = self.at(i)
		if c == "":
			return "\ufffd", i
		if _hex(c):
			j = i
			while j < i + 6 and _hex(self.at(j)):
				j += 1
			code = int(self.cs_text(i, j), 16)
			if self.at(j) in (" ", "\t", "\n") and self.at(j) != "":
				j += 1
			if code == 0 or code > 0x10FFFF or 0xD800 <= code <= 0xDFFF:
				code = 0xFFFD
			return chr(code), j
		return c, i + 1

	def cs_text(self, i, j) -> str:
		return "".join(self.cs[i:j])

	def name(self, i):
		out = []
		while i < self.n:
			c = self.cs[i]
			if _name_char(c):
				out.append(c)
				i += 1
			elif self.valid_escape(i):
				char, i = self.escape(i)
				out.append(char)
			else:
				break
		return "".join(out), i

	def number(self, i):
		j = i
		if self.at(j) in ("+", "-") and self.at(j) != "":
			j += 1
		while self.at(j).isascii() and self.at(j).isdigit() and self.at(j) != "":
			j += 1
		if self.at(j) == "." and self.at(j + 1) != "" and self.at(j + 1).isascii() and self.at(j + 1).isdigit():
			j += 1
			while self.at(j) != "" and self.at(j).isascii() and self.at(j).isdigit():
				j += 1
		if self.at(j) in ("e", "E") and self.at(j) != "":
			k = j + 1
			if self.at(k) in ("+", "-") and self.at(k) != "":
				k += 1
			if self.at(k) != "" and self.at(k).isascii() and self.at(k).isdigit():
				while self.at(k) != "" and self.at(k).isascii() and self.at(k).isdigit():
					k += 1
				j = k
		return self.cs_text(i, j), j

	def string(self, i):
		"""Consume a string starting at the quote `i`; returns `(token or None, next index)`."""
		quote = self.cs[i]
		j = i + 1
		out = []
		while True:
			if j >= self.n:
				self.error("unclosed-string", i)
				return None, j
			c = self.cs[j]
			if c == quote:
				return Tok("string", "".join(out), self.line_of[i], self.col_of[i]), j + 1
			if c == "\n":
				self.error("unclosed-string", i)
				return None, j
			if c == "\\":
				if j + 1 >= self.n:
					j += 1
				elif self.cs[j + 1] == "\n":
					j += 2
				else:
					char, j = self.escape(j)
					out.append(char)
			else:
				out.append(c)
				j += 1

	def url(self, i, start):
		"""Consume an unquoted url token; `i` is after the opening parenthesis."""
		while self.at(i) != "" and self.at(i) in WHITESPACE:
			i += 1
		out = []
		while True:
			if i >= self.n:
				self.error("unclosed-url", start)
				return None, i
			c = self.cs[i]
			if c == ")":
				return Tok("url", "".join(out), self.line_of[start], self.col_of[start]), i + 1
			if c in WHITESPACE:
				while self.at(i) != "" and self.at(i) in WHITESPACE:
					i += 1
				if self.at(i) == ")":
					continue
				if i >= self.n:
					self.error("unclosed-url", start)
					return None, i
				return self.bad_url(i, start)
			if c in "\"'(" or ord(c) < 0x20 or ord(c) == 0x7F:
				return self.bad_url(i, start)
			if c == "\\":
				if self.valid_escape(i):
					char, i = self.escape(i)
					out.append(char)
					continue
				return self.bad_url(i, start)
			out.append(c)
			i += 1

	def bad_url(self, i, start):
		self.error("bad-url", start)
		while i < self.n and self.cs[i] != ")":
			i += 2 if self.valid_escape(i) else 1
		return None, min(i + 1, self.n)

	def tokens(self) -> list[Tok]:
		out = []
		i = 0
		while i < self.n:
			c = self.cs[i]
			start = i
			line, col = self.line_of[i], self.col_of[i]
			if c in WHITESPACE:
				while i < self.n and self.cs[i] in WHITESPACE:
					i += 1
				out.append(Tok("ws", " ", line, col))
			elif c == "/" and self.at(i + 1) == "*":
				end = self._find_comment_end(i + 2)
				if end < 0:
					self.error("unclosed-comment", i)
					i = self.n
				else:
					i = end + 2
			elif c in "\"'":
				token, i = self.string(i)
				if token:
					out.append(token)
			elif c == "#":
				if self.at(i + 1) != "" and (_name_char(self.at(i + 1)) or self.valid_escape(i + 1)):
					value, i = self.name(i + 1)
					out.append(Tok("hash", value, line, col))
				else:
					out.append(Tok("delim", c, line, col))
					i += 1
			elif c in PUNCT:
				out.append(Tok("punct", c, line, col))
				i += 1
			elif c == "@":
				if self.starts_ident(i + 1):
					value, i = self.name(i + 1)
					out.append(Tok("at", value, line, col))
				else:
					out.append(Tok("delim", c, line, col))
					i += 1
			elif c == "\\" and not self.valid_escape(i):
				out.append(Tok("delim", c, line, col))
				i += 1
			elif self.starts_number(i):
				text, i = self.number(i)
				if self.starts_ident(i):
					unit, i = self.name(i)
					out.append(Tok("dim", text, line, col, unit))
				elif self.at(i) == "%":
					i += 1
					out.append(Tok("pct", text, line, col))
				else:
					out.append(Tok("num", text, line, col))
			elif self.starts_ident(i):
				value, i = self.name(i)
				if self.at(i) == "(":
					i += 1
					if value.lower() == "url":
						j = i
						while self.at(j) != "" and self.at(j) in WHITESPACE:
							j += 1
						if self.at(j) in ('"', "'") and self.at(j) != "":
							out.append(Tok("function", value, line, col))
						else:
							token, i = self.url(i, start)
							if token:
								out.append(token)
					else:
						out.append(Tok("function", value, line, col))
				else:
					out.append(Tok("ident", value, line, col))
			else:
				out.append(Tok("delim", c, line, col))
				i += 1
		return out

	def _find_comment_end(self, i) -> int:
		while i + 1 < self.n:
			if self.cs[i] == "*" and self.cs[i + 1] == "/":
				return i
			i += 1
		return -1


def build_tree(tokens: list[Tok], sink) -> list:
	"""Group the flat tokens into nodes; unbalanced brackets are errors (a closer without an opener is dropped)."""
	closers = {"(": ")", "[": "]", "{": "}"}
	kinds = {"(": "paren", "[": "bracket", "{": "brace"}
	root = []
	stack = []  # (node, closer)
	current = root
	for tok in tokens:
		if tok.type == "function" or (tok.type == "punct" and tok.value in "([{"):
			if len(stack) >= LIMITS["max_nesting"]:
				sink(
					"too-nested", tok.line, tok.col, LIMITS["max_nesting"]
				)  # the opener is dropped, so the stack stays bounded
				continue
			if tok.type == "function":
				node = Node("fn", tok.value, tok.line, tok.col)
				closer = ")"
			else:
				node = Node(kinds[tok.value], tok.value, tok.line, tok.col)
				closer = closers[tok.value]
			current.append(node)
			stack.append((node, closer, current))
			current = node.children
		elif tok.type == "punct" and tok.value in ")]}":
			if stack and stack[-1][1] == tok.value:
				_, _, current = stack.pop()
			else:
				sink("unbalanced", tok.line, tok.col, tok.value)
		else:
			current.append(tok)
	for node, _closer, _ in stack:
		sink("unclosed-block", node.line, node.col, "(" if node.kind in ("fn", "paren") else node.name)
	return root


# ---------------------------------------------------------------- the checks


def _norm_target(text: str) -> str:
	text = unicodedata.normalize("NFKC", text)
	return "".join(c for c in text if ord(c) > 0x20 and ord(c) != 0x7F and ord(c) not in INVISIBLE).lower()


def _is_script_url(text: str) -> bool:
	return any(_norm_target(variant).startswith(("javascript:", "vbscript:")) for variant in (text, text.lstrip()))


def _same_origin(text: str) -> bool:
	if not text.startswith(SAME_ORIGIN):
		return False
	if ".." in text or "\\" in text or any(ord(c) < 0x20 or ord(c) == 0x7F for c in text):
		return False
	return not re.search(r"%(2e|2f|5c|00)", text, re.IGNORECASE)


def _position(item):
	return item.line, item.col


class Checker:
	def __init__(self, result: Result):
		self.result = result
		self.rules = 0
		self.seen = set()

	# messages
	def add(self, level, code, line, col, *args):
		message = Message(line, col, code, format_message(code, *args), level, tuple(str(a) for a in args))
		if message.key() in self.seen:
			return
		self.seen.add(message.key())
		target = self.result.errors if level == "error" else self.result.warnings
		if len(target) < LIMITS["max_errors"]:
			target.append(message)

	def add_error(self, code, line, col, *args):
		self.add("error", code, line, col, *args)

	def error(self, code, item, *args):
		self.add("error", code, item.line, item.col, *args)

	def warn(self, code, item, *args):
		self.add("warning", code, item.line, item.col, *args)

	# stylesheet and blocks
	def rule_list(self, nodes: list, depth: int):
		i = 0
		n = len(nodes)
		while i < n:
			item = nodes[i]
			if isinstance(item, Tok) and item.type == "ws":
				i += 1
				continue
			if isinstance(item, Tok) and item.type == "punct" and item.value == ";":
				i += 1
				continue
			if isinstance(item, Tok) and item.type == "at":
				prelude = []
				i += 1
				block = None
				while i < n:
					current = nodes[i]
					if isinstance(current, Node) and current.kind == "brace":
						block = current
						i += 1
						break
					if isinstance(current, Tok) and current.type == "punct" and current.value == ";":
						i += 1
						break
					prelude.append(current)
					i += 1
				self.at_rule(item, prelude, block, depth)
				continue
			prelude = []
			block = None
			while i < n:
				current = nodes[i]
				if isinstance(current, Node) and current.kind == "brace":
					block = current
					i += 1
					break
				prelude.append(current)
				i += 1
			self.style_rule(item, prelude, block, depth)

	def count_rule(self, at) -> bool:
		self.rules += 1
		if self.rules == LIMITS["max_rules"] + 1:
			self.error("too-many-rules", at, LIMITS["max_rules"])
		return self.rules <= LIMITS["max_rules"]

	def depth_ok(self, at, depth) -> bool:
		if depth > LIMITS["max_depth"]:
			self.error("too-deep", at, LIMITS["max_depth"])
			return False
		return True

	def at_rule(self, at, prelude, block, depth):
		name = at.value.lower()
		if name not in _SETS["at_rules"]:
			self.error("at-rule-not-allowed", at, at.value)
			return
		if not self.depth_ok(at, depth) or not self.count_rule(at):
			return
		if block is None:
			self.error("missing-block", at)
			return
		if name == "media":
			self.media_prelude(prelude)
			self.rule_list(block.children, depth + 1)
		elif name == "supports":
			self.supports_prelude(prelude)
			self.rule_list(block.children, depth + 1)
		elif name == "font-face":
			if _significant(prelude):
				self.error("bad-selector", _first(prelude, at), _text(_significant(prelude)[0]))
			self.font_face(at, block)
		else:
			self.keyframes(at, prelude, block, depth)

	def keyframes(self, at, prelude, block, depth):
		parts = _significant(prelude)
		first = parts[0] if parts else at
		if len(parts) != 1 or not isinstance(first, Tok) or first.type != "ident" or not first.value.startswith("cx-"):
			self.error("keyframes-name", first)
		inner = block.children
		i = 0
		while i < len(inner):
			item = inner[i]
			if isinstance(item, Tok) and item.type == "ws":
				i += 1
				continue
			frame_prelude = []
			frame = None
			while i < len(inner):
				current = inner[i]
				i += 1
				if isinstance(current, Node) and current.kind == "brace":
					frame = current
					break
				frame_prelude.append(current)
			if not self.depth_ok(item, depth + 1) or not self.count_rule(item):
				continue
			for part in _significant(frame_prelude):
				ok = isinstance(part, Tok) and (
					part.type == "pct"
					or (part.type == "ident" and part.value.lower() in ("from", "to"))
					or (part.type == "punct" and part.value == ",")
				)
				if not ok:
					self.error("bad-selector", part, _text(part))
			if frame is None:
				self.error("missing-block", item)
			else:
				self.declarations(frame.children, "")

	def font_face(self, at, block):
		seen = self.declarations(block.children, "", font_face=True)
		if "font-display" not in seen:
			self.warn("font-display-missing", at)

	def style_rule(self, first, prelude, block, depth):
		if not self.depth_ok(first, depth) or not self.count_rule(first):
			return
		classes = self.selector(prelude, first)
		if block is None:
			self.error("missing-block", _last(prelude, first))
			return
		self.declarations(block.children, classes)

	# preludes
	def media_prelude(self, prelude):
		for item in _significant(prelude):
			if isinstance(item, Tok) and (
				(item.type == "ident" and item.value.lower() in _SETS["media_idents"])
				or (item.type == "punct" and item.value == ",")
			):
				continue
			if isinstance(item, Node) and item.kind == "paren":
				self.media_feature(item)
				continue
			self.error("media-not-allowed", (item), _text(item))

	def media_feature(self, node):
		parts = _significant(node.children)
		ok = (
			len(parts) >= 1
			and isinstance(parts[0], Tok)
			and parts[0].type == "ident"
			and parts[0].value.lower() in _SETS["media_features"]
		)
		if ok and len(parts) > 1:
			ok = (
				len(parts) == 3
				and isinstance(parts[1], Tok)
				and parts[1].value == ":"
				and isinstance(parts[2], Tok)
				and (
					parts[2].type in ("num", "dim", "ident")
					and (parts[2].type != "ident" or parts[2].value.lower() in _SETS["media_idents"])
				)
			)
		if not ok:
			self.error("media-not-allowed", node, "(" + _text_list(node.children) + ")")

	def supports_prelude(self, prelude):
		for item in _significant(prelude):
			if isinstance(item, Tok) and item.type == "ident" and item.value.lower() in ("and", "or", "not"):
				continue
			if isinstance(item, Node) and item.kind == "paren":
				self.supports_condition(item)
				continue
			self.error("supports-not-allowed", (item), _text(item))

	def supports_condition(self, node):
		parts = _significant(node.children)
		if parts and isinstance(parts[0], Node):  # nested conditions
			self.supports_prelude(node.children)
			return
		if (
			len(parts) >= 3
			and isinstance(parts[0], Tok)
			and parts[0].type == "ident"
			and isinstance(parts[1], Tok)
			and parts[1].value == ":"
		):
			name = parts[0].value.lower()
			if name in _SETS["properties"] or name.startswith(("--wk-", "--cx-")):
				self.value(node.children[node.children.index(parts[1]) + 1 :], name, {})
				return
		self.error("supports-not-allowed", node, "(" + _text_list(node.children) + ")")

	# selectors
	def selector(self, prelude, first) -> set:
		classes = set()
		if not _significant(prelude):
			self.error("empty-selector", first)
			return classes
		has_part = False
		last_comma = None
		for item in _significant(prelude):
			if isinstance(item, Tok) and item.type == "punct" and item.value == ",":
				if not has_part:
					self.error("empty-selector", item)
				has_part = False
				last_comma = item
			else:
				has_part = True
		if not has_part and last_comma is not None:
			self.error("empty-selector", last_comma)
		self.selector_nodes(prelude, classes, nth=False)
		return classes

	def selector_nodes(self, nodes, classes, nth):
		i = 0
		n = len(nodes)
		while i < n:
			item = nodes[i]
			i += 1
			if isinstance(item, Node):
				if item.kind == "bracket":
					self.attribute(item)
				else:
					self.error("bad-selector", item, "(" if item.kind in ("fn", "paren") else item.name)
				continue
			kind, value = item.type, item.value
			if kind == "ws" or (kind == "punct" and value == ","):
				continue
			if kind == "ident":
				continue
			if kind == "delim" and value == ".":
				follower = nodes[i] if i < n else None
				if isinstance(follower, Tok) and follower.type == "ident":
					i += 1
					self.class_name(follower, classes)
				else:
					self.error("bad-selector", item, ".")
				continue
			if kind == "delim" and value in SELECTOR_DELIMS:
				continue
			if kind == "hash":
				if any(value.lower().startswith(prefix) for prefix in RULES["forbidden_id_prefixes"]):
					self.error("selector-not-allowed", item, "#" + value)
				continue
			if kind == "punct" and value == ":":
				i = self.pseudo(nodes, i, item, classes)
				continue
			self.error("bad-selector", item, _text(item))

	def class_name(self, tok, classes):
		name = tok.value
		lower = name.lower()
		if lower in _SETS["forbidden_classes"] or any(lower.startswith(p) for p in RULES["forbidden_class_prefixes"]):
			self.error("selector-not-allowed", tok, "." + name)
			return
		classes.add(name)
		if lower.startswith("wk-") and name not in _SETS["known_classes"]:
			self.warn("unknown-class", tok, name)

	def pseudo(self, nodes, i, colon, classes) -> int:
		n = len(nodes)
		double = i < n and isinstance(nodes[i], Tok) and nodes[i].type == "punct" and nodes[i].value == ":"
		if double:
			i += 1
		target = nodes[i] if i < n else None
		prefix = "::" if double else ":"
		if isinstance(target, Tok) and target.type == "ident":
			name = target.value.lower()
			allowed = (
				name in _SETS["pseudo_elements"]
				if double
				else name in _SETS["pseudo_classes"] or name in _SETS["pseudo_legacy_elements"]
			)
			if not allowed:
				self.error("pseudo-not-allowed", target, prefix + target.value)
			return i + 1
		if isinstance(target, Node) and target.kind == "fn" and not double:
			name = target.name.lower()
			if name in _SETS["pseudo_selector_functions"]:
				self.selector_nodes(target.children, classes, nth=False)
			elif name in _SETS["pseudo_nth_functions"]:
				self.nth_arguments(target)
			else:
				self.error("pseudo-not-allowed", target, ":" + target.name + "()")
			return i + 1
		self.error("bad-selector", target or colon, ":")
		return i

	def nth_arguments(self, node):
		for part in _significant(node.children):
			ok = isinstance(part, Tok) and (
				part.type in ("num", "dim")
				or (part.type == "ident" and part.value.lower() in ("n", "even", "odd", "-n"))
				or (part.type == "delim" and part.value in "+-")
			)
			if not ok:
				self.error("bad-selector", (part), _text(part))

	def attribute(self, node):
		parts = _significant(node.children)
		if not parts or not (isinstance(parts[0], Tok) and parts[0].type == "ident"):
			self.error("bad-selector", node, "[")
			return
		name = parts[0].value.lower()
		if name in _SETS["forbidden_attributes"]:
			self.error("selector-not-allowed", node, "[" + parts[0].value + "]")
			return
		rest = parts[1:]
		if not rest:
			return
		i = 0
		if isinstance(rest[0], Tok) and rest[0].type == "delim" and rest[0].value in "~|^$*":
			i = 1
		operator = rest[i] if i < len(rest) else None
		value = rest[i + 1] if i + 1 < len(rest) else None
		flag = rest[i + 2] if i + 2 < len(rest) else None
		ok = (
			isinstance(operator, Tok)
			and operator.type == "delim"
			and operator.value == "="
			and isinstance(value, Tok)
			and value.type in ("ident", "string", "num", "dim")
			and (flag is None or (isinstance(flag, Tok) and flag.type == "ident" and flag.value.lower() in ("i", "s")))
			and len(rest) <= i + 3
		)
		if not ok:
			self.error("bad-selector", rest[0], _text(rest[0]))
			return
		if name in ("class", "id") and value.type in ("ident", "string"):
			lowered = value.value.lower()
			if any(word in lowered for word in RULES["forbidden_attribute_values"]):
				self.error("selector-not-allowed", node, "[" + parts[0].value + "]")

	# declarations
	def declarations(self, nodes, classes, font_face=False) -> set:
		"""Check a declaration list; returns the set of property names seen."""
		seen = set()
		segments = [[]]
		for item in nodes:
			if isinstance(item, Tok) and item.type == "punct" and item.value == ";":
				segments.append([])
			else:
				segments[-1].append(item)
		declared = {}
		for segment in segments:
			parts = _significant(segment)
			if not parts:
				continue
			brace = next((p for p in segment if isinstance(p, Node) and p.kind == "brace"), None)
			if brace is not None:
				self.error("nested-rule", brace)
				continue
			head = parts[0]
			if not (
				isinstance(head, Tok)
				and head.type == "ident"
				and len(parts) >= 2
				and isinstance(parts[1], Tok)
				and parts[1].type == "punct"
				and parts[1].value == ":"
			):
				self.error("bad-declaration", (head))
				continue
			name = head.value
			seen.add(name.lower())
			value = segment[segment.index(parts[1]) + 1 :]
			self.declaration(head, name, value, classes, font_face, declared)
		self.hook_warnings(classes, declared)
		return seen

	def declaration(self, head, name, value, classes, font_face, declared):
		lower = name.lower()
		custom = name.startswith("--")
		if custom:
			if not name.startswith(("--wk-", "--cx-")):
				self.error("custom-property", head)
				return
			if name.startswith("--wk-") and name not in _SETS["known_custom_properties"]:
				self.warn("unknown-token", head, name)
		elif font_face:
			if lower not in _SETS["font_face_properties"]:
				self.error("property-not-allowed", head, name)
				return
		elif lower not in _SETS["properties"]:
			self.error("property-not-allowed", head, name)
			return
		value, important = _strip_important(value)
		if important is not None and not name.startswith("--wk-"):
			self.warn("important", important)
		context = {"property": lower, "font_face": font_face, "src": font_face and lower == "src"}
		self.value(value, lower, context)
		if not custom:
			declared[lower] = value

	def value(self, nodes, prop, context):
		for item in nodes:
			if isinstance(item, Node):
				self.value_node(item, prop, context)
				continue
			if item.type == "string":
				if _is_script_url(item.value):
					self.error("script-url", item)
				if context.get("in_image_set"):
					self.url_target(item.value, item, prop, context)
			elif item.type == "url":
				self.url_target(item.value, item, prop, context)
			elif item.type == "delim" and item.value == "!":
				self.error("bad-important", item)
			elif item.type == "at":
				self.error("bad-selector", item, "@" + item.value)

	def value_node(self, node, prop, context):
		if node.kind == "brace":
			self.error("nested-rule", node)
			return
		if node.kind != "fn":
			self.value(node.children, prop, context)
			return
		name = node.name.lower()
		if name == "expression":
			self.error("expression", node)
		elif name == "url":
			parts = _significant(node.children)
			if len(parts) == 1 and isinstance(parts[0], Tok) and parts[0].type == "string":
				self.url_target(parts[0].value, node, prop, context)
			else:
				self.error("bad-url", node)
		elif name == "var" and prop in _SETS["url_capable_properties"]:
			# A custom property may hold a string, and in an image context a string is an address: never resolve one here.
			self.error("var-in-url-property", node, prop)
		elif name == "image-set":
			if prop not in _SETS["url_properties"]:
				self.error("url-not-allowed", node, prop)
			self.value(node.children, prop, {**context, "in_image_set": True})
		elif name in _SETS["functions"] or (context.get("src") and name in _SETS["font_face_functions"]):
			self.value(node.children, prop, context)
		else:
			self.error("function-not-allowed", node, node.name)

	def url_target(self, target, at, prop, context):
		if context.get("font_face"):
			self.error("font-face-src", at)
		elif _is_script_url(target):
			self.error("script-url", at)
		elif prop not in _SETS["url_properties"]:
			self.error("url-not-allowed", at, prop)
		elif DATA_URL.match(target):
			if len(target) > LIMITS["max_data_url"]:
				self.error("url-external", at, _short(target))
		elif not _same_origin(target):
			self.error("url-external", at, _short(target))

	# warnings
	def hook_warnings(self, classes, declared):
		if classes:
			hooks = sorted(classes & _SETS["hook_classes"])
			if hooks:
				for prop, value in declared.items():
					node = _first(value, None)
					if node is not None and _hides(prop, value):
						self.warn("hides-hook", node, "." + hooks[0])
		self.contrast_warning(declared)

	def contrast_warning(self, declared):
		foreground = _hex_of(declared.get("color"))
		background = _hex_of(declared.get("background-color")) or _hex_of(declared.get("background"))
		if foreground and background:
			ratio = contrast.ratio(foreground, background)
			if ratio < contrast.TEXT_MIN:
				at = _first(declared.get("color"), None)
				if at is not None:
					self.warn("contrast", at, f"{ratio:.1f}")


def _significant(nodes) -> list:
	return [n for n in nodes if not (isinstance(n, Tok) and n.type == "ws")]


def _first(nodes, default):
	for node in nodes:
		if not (isinstance(node, Tok) and node.type == "ws"):
			return node
	return default


def _last(nodes, default):
	parts = _significant(nodes)
	return parts[-1] if parts else default


def _text(item) -> str:
	if isinstance(item, Node):
		inner = _text_list(item.children)
		if item.kind == "fn":
			return f"{item.name}({inner})"
		return {"paren": "(", "bracket": "[", "brace": "{"}[item.kind] + inner
	if item.type == "at":
		return "@" + item.value
	if item.type == "hash":
		return "#" + item.value
	if item.type == "dim":
		return item.value + item.unit
	if item.type == "pct":
		return item.value + "%"
	if item.type == "function":
		return item.value + "("
	return _short(item.value)


def _text_list(nodes) -> str:
	return _short(" ".join(_text(n) for n in _significant(nodes)), 30)


def _strip_important(value):
	"""Split a trailing `!important` off; returns `(value, the ! token or None)`."""
	parts = [i for i, n in enumerate(value) if not (isinstance(n, Tok) and n.type == "ws")]
	if len(parts) >= 2:
		last, bang = value[parts[-1]], value[parts[-2]]
		if (
			isinstance(last, Tok)
			and last.type == "ident"
			and last.value.lower() == "important"
			and isinstance(bang, Tok)
			and bang.type == "delim"
			and bang.value == "!"
		):
			return value[: parts[-2]], bang
	return value, None


def _hex_of(value):
	for item in _significant(value or []):
		if isinstance(item, Tok) and item.type == "hash" and HEX_COLOUR.fullmatch("#" + item.value):
			return "#" + item.value
	return None


def _single(value):
	parts = _significant(value)
	return parts[0] if len(parts) == 1 and isinstance(parts[0], Tok) else None


def _hides(prop, value) -> bool:
	item = _single(value)
	if item is None:
		return False
	text = item.value.lower() if item.type == "ident" else ""
	if prop == "display":
		return text == "none"
	if prop == "visibility":
		return text in ("hidden", "collapse")
	if prop == "opacity":
		return item.type == "num" and float(item.value) == 0
	if prop == "font-size":
		return (
			item.type in ("num", "dim")
			and float(item.value) == 0
			or (item.type == "dim" and item.unit.lower() == "px" and float(item.value) < 12)
		)
	if prop in ("height", "max-height"):
		return item.type in ("num", "dim") and float(item.value) == 0
	return False


# ---------------------------------------------------------------- entry point


def validate(css) -> Result:
	"""Validate Custom CSS text; never raises."""
	result = Result()
	checker = Checker(result)
	try:
		_run(css, checker)
	except Exception:  # fail closed: a bug of the validator rejects the CSS, it never accepts it
		checker.add("error", "bad-declaration", 1, 1)
	result.errors.sort(key=Message.key)
	result.warnings.sort(key=Message.key)
	return result


def _run(css, checker: Checker):
	if isinstance(css, bytes):
		try:
			css = css.decode("utf-8")
		except UnicodeDecodeError:
			checker.add("error", "not-utf8", 1, 1)
			return
	if len(css.encode("utf-8", "surrogatepass")) > LIMITS["max_bytes"]:
		checker.add("error", "too-large", 1, 1, LIMITS["max_bytes"] // 1024)
		return
	text = css.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
	sink = checker.add_error
	tokenizer = Tokenizer(text, sink)
	_scan_characters(tokenizer, text, sink)
	tokens = tokenizer.tokens()
	tree = build_tree(tokens, sink)
	checker.rule_list(tree, 1)


def _scan_characters(tokenizer: Tokenizer, text: str, sink):
	for i, c in enumerate(tokenizer.cs):
		code = ord(c)
		line, col = tokenizer.line_of[i], tokenizer.col_of[i]
		if (
			(code < 0x20 and c not in "\t\n")
			or code == 0x7F
			or 0x80 <= code <= 0x9F
			or code in INVISIBLE
			or 0xD800 <= code <= 0xDFFF
		):
			sink("control-char", line, col, f"{code:04X}")
		elif c == "<":
			sink("markup", line, col, "<")
		elif c == "-" and text.startswith("-->", i):
			sink("markup", line, col, "-->")
