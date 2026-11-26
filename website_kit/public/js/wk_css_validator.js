/* The client twin of website_kit/css_validator.py: the same tokenizer, parser and rules (wk_css_rules.json), for the editor and
 * the preview only. It gives feedback; the server validates again on every save and never trusts this file. Both are tested
 * against the shared corpus tests/css_corpus.json (tests/js/run_corpus.mjs), so a change of one without the other fails CI.
 * Usage: WkCssValidator.validate(cssText, rules) -> {ok, errors: [{line, column, code, message, level}], warnings: [...]}.
 */
(function (root, factory) {
	if (typeof module === "object" && module.exports) {
		module.exports = factory();
	} else {
		root.WkCssValidator = factory();
	}
})(typeof self !== "undefined" ? self : this, function () {
	"use strict";

	const WHITESPACE = " \t\n";
	const PUNCT = ":;,{}()[]";
	const SELECTOR_DELIMS = "*>+~|";
	const SAME_ORIGIN = ["/files/", "/assets/"];
	const DATA_URL = /^data:image\/(png|jpeg|webp|gif|svg\+xml);/;
	const HEX_COLOUR = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
	const INVISIBLE = new Set([
		0x200b, 0x200c, 0x200d, 0x200e, 0x200f, 0x2028, 0x2029, 0x202a, 0x202b, 0x202c, 0x202d, 0x202e, 0x2060, 0x2061,
		0x2062, 0x2063, 0x2064, 0x2066, 0x2067, 0x2068, 0x2069, 0xfeff, 0xfff9, 0xfffa, 0xfffb,
	]);

	const isDigit = (c) => c !== "" && c >= "0" && c <= "9";
	const isAlpha = (c) => c !== "" && ((c >= "a" && c <= "z") || (c >= "A" && c <= "Z"));
	const nameStart = (c) => c !== "" && (isAlpha(c) || c === "_" || c.codePointAt(0) >= 0x80);
	const nameChar = (c) => nameStart(c) || isDigit(c) || c === "-";
	const isHex = (c) => c !== "" && /^[0-9a-fA-F]$/.test(c);
	const inWs = (c) => c !== "" && WHITESPACE.includes(c);

	class Tok {
		constructor(type, value, line, col, unit) {
			this.type = type;
			this.value = value;
			this.unit = unit || "";
			this.line = line;
			this.col = col;
		}
	}

	class Node {
		constructor(kind, name, line, col) {
			this.kind = kind;
			this.name = name;
			this.children = [];
			this.line = line;
			this.col = col;
		}
	}

	const isTok = (item) => item instanceof Tok;
	const isNode = (item) => item instanceof Node;
	const isWs = (item) => isTok(item) && item.type === "ws";
	const significant = (nodes) => nodes.filter((n) => !isWs(n));

	function short(text, limit) {
		text = String(text);
		limit = limit || 40;
		const cps = Array.from(text);
		return cps.length <= limit ? text : cps.slice(0, limit).join("") + "...";
	}

	function normTarget(text) {
		text = text.normalize("NFKC");
		return Array.from(text)
			.filter((c) => c.codePointAt(0) > 0x20 && c.codePointAt(0) !== 0x7f && !INVISIBLE.has(c.codePointAt(0)))
			.join("")
			.toLowerCase();
	}

	function isScriptUrl(text) {
		return [text, text.replace(/^\s+/, "")].some((v) => {
			const n = normTarget(v);
			return n.startsWith("javascript:") || n.startsWith("vbscript:");
		});
	}

	function sameOrigin(text) {
		if (!SAME_ORIGIN.some((p) => text.startsWith(p))) return false;
		if (text.includes("..") || text.includes("\\")) return false;
		if (Array.from(text).some((c) => c.codePointAt(0) < 0x20 || c.codePointAt(0) === 0x7f)) return false;
		return !/%(2e|2f|5c|00)/i.test(text);
	}

	function createValidator(rules) {
		const LIMITS = rules.limits;
		const MESSAGES = rules.messages;
		const S = {};
		[
			"at_rules", "media_idents", "media_features", "properties", "font_face_properties", "functions",
			"font_face_functions", "url_properties", "url_capable_properties", "pseudo_classes", "pseudo_legacy_elements", "pseudo_elements",
			"pseudo_selector_functions", "pseudo_nth_functions", "forbidden_classes", "forbidden_attributes", "hook_classes",
			"known_classes", "known_custom_properties",
		].forEach((key) => {
			S[key] = new Set(rules[key]);
		});

		function formatMessage(code, args) {
			let text = MESSAGES[code];
			(args || []).forEach((value, index) => {
				text = text.split("{" + index + "}").join(String(value));
			});
			return text;
		}

		// ------------------------------------------------------------ tokenizer
		class Tokenizer {
			constructor(text, sink) {
				this.cs = Array.from(text);
				this.n = this.cs.length;
				this.sink = sink;
				this.lineOf = [];
				this.colOf = [];
				let line = 1;
				let col = 1;
				for (const c of this.cs) {
					this.lineOf.push(line);
					this.colOf.push(col);
					if (c === "\n") {
						line += 1;
						col = 1;
					} else {
						col += 1;
					}
				}
			}

			at(i) {
				return i >= 0 && i < this.n ? this.cs[i] : "";
			}

			error(code, i, ...args) {
				if (this.n === 0) return this.sink(code, 1, 1, ...args);
				i = Math.min(i, this.n - 1);
				return this.sink(code, this.lineOf[i], this.colOf[i], ...args);
			}

			validEscape(i) {
				return this.at(i) === "\\" && this.at(i + 1) !== "" && this.at(i + 1) !== "\n";
			}

			startsIdent(i) {
				const c = this.at(i);
				if (c === "-") {
					const d = this.at(i + 1);
					return d !== "" && (nameStart(d) || d === "-" || this.validEscape(i + 1));
				}
				if (c === "\\") return this.validEscape(i);
				return c !== "" && nameStart(c);
			}

			startsNumber(i) {
				const c = this.at(i);
				const d = this.at(i + 1);
				if (isDigit(c)) return true;
				if (c === "+" || c === "-") return isDigit(d) || (d === "." && isDigit(this.at(i + 2)));
				return c === "." && isDigit(d);
			}

			text(i, j) {
				return this.cs.slice(i, j).join("");
			}

			escape(i) {
				i += 1;
				const c = this.at(i);
				if (c === "") return ["�", i];
				if (isHex(c)) {
					let j = i;
					while (j < i + 6 && isHex(this.at(j))) j += 1;
					let code = parseInt(this.text(i, j), 16);
					if (inWs(this.at(j))) j += 1;
					if (code === 0 || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff)) code = 0xfffd;
					return [String.fromCodePoint(code), j];
				}
				return [c, i + 1];
			}

			name(i) {
				let out = "";
				while (i < this.n) {
					const c = this.cs[i];
					if (nameChar(c)) {
						out += c;
						i += 1;
					} else if (this.validEscape(i)) {
						const [char, next] = this.escape(i);
						out += char;
						i = next;
					} else {
						break;
					}
				}
				return [out, i];
			}

			number(i) {
				let j = i;
				if (this.at(j) === "+" || this.at(j) === "-") j += 1;
				while (isDigit(this.at(j))) j += 1;
				if (this.at(j) === "." && isDigit(this.at(j + 1))) {
					j += 1;
					while (isDigit(this.at(j))) j += 1;
				}
				if (this.at(j) === "e" || this.at(j) === "E") {
					let k = j + 1;
					if (this.at(k) === "+" || this.at(k) === "-") k += 1;
					if (isDigit(this.at(k))) {
						while (isDigit(this.at(k))) k += 1;
						j = k;
					}
				}
				return [this.text(i, j), j];
			}

			string(i) {
				const quote = this.cs[i];
				let j = i + 1;
				let out = "";
				for (;;) {
					if (j >= this.n) {
						this.error("unclosed-string", i);
						return [null, j];
					}
					const c = this.cs[j];
					if (c === quote) return [new Tok("string", out, this.lineOf[i], this.colOf[i]), j + 1];
					if (c === "\n") {
						this.error("unclosed-string", i);
						return [null, j];
					}
					if (c === "\\") {
						if (j + 1 >= this.n) {
							j += 1;
						} else if (this.cs[j + 1] === "\n") {
							j += 2;
						} else {
							const [char, next] = this.escape(j);
							out += char;
							j = next;
						}
					} else {
						out += c;
						j += 1;
					}
				}
			}

			url(i, start) {
				while (inWs(this.at(i))) i += 1;
				let out = "";
				for (;;) {
					if (i >= this.n) {
						this.error("unclosed-url", start);
						return [null, i];
					}
					const c = this.cs[i];
					if (c === ")") return [new Tok("url", out, this.lineOf[start], this.colOf[start]), i + 1];
					if (inWs(c)) {
						while (inWs(this.at(i))) i += 1;
						if (this.at(i) === ")") continue;
						if (i >= this.n) {
							this.error("unclosed-url", start);
							return [null, i];
						}
						return this.badUrl(i, start);
					}
					const code = c.codePointAt(0);
					if ("\"'(".includes(c) || code < 0x20 || code === 0x7f) return this.badUrl(i, start);
					if (c === "\\") {
						if (this.validEscape(i)) {
							const [char, next] = this.escape(i);
							out += char;
							i = next;
							continue;
						}
						return this.badUrl(i, start);
					}
					out += c;
					i += 1;
				}
			}

			badUrl(i, start) {
				this.error("bad-url", start);
				while (i < this.n && this.cs[i] !== ")") i += this.validEscape(i) ? 2 : 1;
				return [null, Math.min(i + 1, this.n)];
			}

			findCommentEnd(i) {
				while (i + 1 < this.n) {
					if (this.cs[i] === "*" && this.cs[i + 1] === "/") return i;
					i += 1;
				}
				return -1;
			}

			tokens() {
				const out = [];
				let i = 0;
				while (i < this.n) {
					const c = this.cs[i];
					const start = i;
					const line = this.lineOf[i];
					const col = this.colOf[i];
					if (inWs(c)) {
						while (i < this.n && inWs(this.cs[i])) i += 1;
						out.push(new Tok("ws", " ", line, col));
					} else if (c === "/" && this.at(i + 1) === "*") {
						const end = this.findCommentEnd(i + 2);
						if (end < 0) {
							this.error("unclosed-comment", i);
							i = this.n;
						} else {
							i = end + 2;
						}
					} else if (c === '"' || c === "'") {
						const [token, next] = this.string(i);
						i = next;
						if (token) out.push(token);
					} else if (c === "#") {
						if (this.at(i + 1) !== "" && (nameChar(this.at(i + 1)) || this.validEscape(i + 1))) {
							const [value, next] = this.name(i + 1);
							i = next;
							out.push(new Tok("hash", value, line, col));
						} else {
							out.push(new Tok("delim", c, line, col));
							i += 1;
						}
					} else if (PUNCT.includes(c)) {
						out.push(new Tok("punct", c, line, col));
						i += 1;
					} else if (c === "@") {
						if (this.startsIdent(i + 1)) {
							const [value, next] = this.name(i + 1);
							i = next;
							out.push(new Tok("at", value, line, col));
						} else {
							out.push(new Tok("delim", c, line, col));
							i += 1;
						}
					} else if (c === "\\" && !this.validEscape(i)) {
						out.push(new Tok("delim", c, line, col));
						i += 1;
					} else if (this.startsNumber(i)) {
						const [text, next] = this.number(i);
						i = next;
						if (this.startsIdent(i)) {
							const [unit, after] = this.name(i);
							i = after;
							out.push(new Tok("dim", text, line, col, unit));
						} else if (this.at(i) === "%") {
							i += 1;
							out.push(new Tok("pct", text, line, col));
						} else {
							out.push(new Tok("num", text, line, col));
						}
					} else if (this.startsIdent(i)) {
						const [value, next] = this.name(i);
						i = next;
						if (this.at(i) === "(") {
							i += 1;
							if (value.toLowerCase() === "url") {
								let j = i;
								while (inWs(this.at(j))) j += 1;
								if (this.at(j) === '"' || this.at(j) === "'") {
									out.push(new Tok("function", value, line, col));
								} else {
									const [token, after] = this.url(i, start);
									i = after;
									if (token) out.push(token);
								}
							} else {
								out.push(new Tok("function", value, line, col));
							}
						} else {
							out.push(new Tok("ident", value, line, col));
						}
					} else {
						out.push(new Tok("delim", c, line, col));
						i += 1;
					}
				}
				return out;
			}
		}

		function buildTree(tokens, sink) {
			const closers = { "(": ")", "[": "]", "{": "}" };
			const kinds = { "(": "paren", "[": "bracket", "{": "brace" };
			const root = [];
			const stack = [];
			let current = root;
			for (const tok of tokens) {
				if (tok.type === "function" || (tok.type === "punct" && "([{".includes(tok.value))) {
					if (stack.length >= LIMITS.max_nesting) {
						sink("too-nested", tok.line, tok.col, LIMITS.max_nesting);
						continue;
					}
					let node;
					let closer;
					if (tok.type === "function") {
						node = new Node("fn", tok.value, tok.line, tok.col);
						closer = ")";
					} else {
						node = new Node(kinds[tok.value], tok.value, tok.line, tok.col);
						closer = closers[tok.value];
					}
					current.push(node);
					stack.push([node, closer, current]);
					current = node.children;
				} else if (tok.type === "punct" && ")]}".includes(tok.value)) {
					if (stack.length && stack[stack.length - 1][1] === tok.value) {
						current = stack.pop()[2];
					} else {
						sink("unbalanced", tok.line, tok.col, tok.value);
					}
				} else {
					current.push(tok);
				}
			}
			for (const [node] of stack) {
				sink("unclosed-block", node.line, node.col, node.kind === "fn" || node.kind === "paren" ? "(" : node.name);
			}
			return root;
		}

		// ------------------------------------------------------------ helpers on nodes
		function text(item) {
			if (isNode(item)) {
				const inner = textList(item.children);
				if (item.kind === "fn") return item.name + "(" + inner;
				return { paren: "(", bracket: "[", brace: "{" }[item.kind] + inner;
			}
			if (item.type === "at") return "@" + item.value;
			if (item.type === "hash") return "#" + item.value;
			if (item.type === "dim") return item.value + item.unit;
			if (item.type === "pct") return item.value + "%";
			if (item.type === "function") return item.value + "(";
			return short(item.value);
		}

		function textList(nodes) {
			return short(significant(nodes).map(text).join(" "), 30);
		}

		function first(nodes, fallback) {
			for (const node of nodes) if (!isWs(node)) return node;
			return fallback;
		}

		function last(nodes, fallback) {
			const parts = significant(nodes);
			return parts.length ? parts[parts.length - 1] : fallback;
		}

		function stripImportant(value) {
			const parts = [];
			value.forEach((n, i) => {
				if (!isWs(n)) parts.push(i);
			});
			if (parts.length >= 2) {
				const lastItem = value[parts[parts.length - 1]];
				const bang = value[parts[parts.length - 2]];
				if (
					isTok(lastItem) && lastItem.type === "ident" && lastItem.value.toLowerCase() === "important" &&
					isTok(bang) && bang.type === "delim" && bang.value === "!"
				) {
					return [value.slice(0, parts[parts.length - 2]), bang];
				}
			}
			return [value, null];
		}

		function hexOf(value) {
			for (const item of significant(value || [])) {
				if (isTok(item) && item.type === "hash" && HEX_COLOUR.test("#" + item.value)) return "#" + item.value;
			}
			return null;
		}

		function single(value) {
			const parts = significant(value);
			return parts.length === 1 && isTok(parts[0]) ? parts[0] : null;
		}

		function hides(prop, value) {
			const item = single(value);
			if (item === null) return false;
			const word = item.type === "ident" ? item.value.toLowerCase() : "";
			if (prop === "display") return word === "none";
			if (prop === "visibility") return word === "hidden" || word === "collapse";
			if (prop === "opacity") return item.type === "num" && parseFloat(item.value) === 0;
			if (prop === "font-size") {
				return (
					((item.type === "num" || item.type === "dim") && parseFloat(item.value) === 0) ||
					(item.type === "dim" && item.unit.toLowerCase() === "px" && parseFloat(item.value) < 12)
				);
			}
			if (prop === "height" || prop === "max-height") {
				return (item.type === "num" || item.type === "dim") && parseFloat(item.value) === 0;
			}
			return false;
		}

		function luminance(hex) {
			let t = hex.replace("#", "");
			if (t.length === 3) t = t.split("").map((c) => c + c).join("");
			const lin = (v) => {
				v = v / 255;
				return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
			};
			const [r, g, b] = [0, 2, 4].map((k) => lin(parseInt(t.slice(k, k + 2), 16)));
			return 0.2126 * r + 0.7152 * g + 0.0722 * b;
		}

		function ratio(a, b) {
			const one = luminance(a);
			const two = luminance(b);
			return (Math.max(one, two) + 0.05) / (Math.min(one, two) + 0.05);
		}

		// ------------------------------------------------------------ checker
		class Checker {
			constructor(result) {
				this.result = result;
				this.rules = 0;
				this.seen = new Set();
			}

			add(level, code, line, col, ...args) {
				const message = { line, column: col, code, message: formatMessage(code, args), level, args: args.map(String) };
				const key = [level, line, col, code].join("\u0000");
				if (this.seen.has(key)) return;
				this.seen.add(key);
				const target = level === "error" ? this.result.errors : this.result.warnings;
				if (target.length < LIMITS.max_errors) target.push(message);
			}

			addError(code, line, col, ...args) {
				this.add("error", code, line, col, ...args);
			}

			error(code, item, ...args) {
				this.add("error", code, item.line, item.col, ...args);
			}

			warn(code, item, ...args) {
				this.add("warning", code, item.line, item.col, ...args);
			}

			ruleList(nodes, depth) {
				let i = 0;
				const n = nodes.length;
				while (i < n) {
					const item = nodes[i];
					if (isWs(item) || (isTok(item) && item.type === "punct" && item.value === ";")) {
						i += 1;
						continue;
					}
					if (isTok(item) && item.type === "at") {
						const prelude = [];
						let block = null;
						i += 1;
						while (i < n) {
							const current = nodes[i];
							if (isNode(current) && current.kind === "brace") {
								block = current;
								i += 1;
								break;
							}
							if (isTok(current) && current.type === "punct" && current.value === ";") {
								i += 1;
								break;
							}
							prelude.push(current);
							i += 1;
						}
						this.atRule(item, prelude, block, depth);
						continue;
					}
					const prelude = [];
					let block = null;
					while (i < n) {
						const current = nodes[i];
						if (isNode(current) && current.kind === "brace") {
							block = current;
							i += 1;
							break;
						}
						prelude.push(current);
						i += 1;
					}
					this.styleRule(item, prelude, block, depth);
				}
			}

			countRule(at) {
				this.rules += 1;
				if (this.rules === LIMITS.max_rules + 1) this.error("too-many-rules", at, LIMITS.max_rules);
				return this.rules <= LIMITS.max_rules;
			}

			depthOk(at, depth) {
				if (depth > LIMITS.max_depth) {
					this.error("too-deep", at, LIMITS.max_depth);
					return false;
				}
				return true;
			}

			atRule(at, prelude, block, depth) {
				const name = at.value.toLowerCase();
				if (!S.at_rules.has(name)) {
					this.error("at-rule-not-allowed", at, at.value);
					return;
				}
				if (!this.depthOk(at, depth) || !this.countRule(at)) return;
				if (block === null) {
					this.error("missing-block", at);
					return;
				}
				if (name === "media") {
					this.mediaPrelude(prelude);
					this.ruleList(block.children, depth + 1);
				} else if (name === "supports") {
					this.supportsPrelude(prelude);
					this.ruleList(block.children, depth + 1);
				} else if (name === "font-face") {
					const parts = significant(prelude);
					if (parts.length) this.error("bad-selector", parts[0], text(parts[0]));
					this.fontFace(at, block);
				} else {
					this.keyframes(at, prelude, block, depth);
				}
			}

			keyframes(at, prelude, block, depth) {
				const parts = significant(prelude);
				const firstPart = parts.length ? parts[0] : at;
				if (parts.length !== 1 || !isTok(firstPart) || firstPart.type !== "ident" || !firstPart.value.startsWith("cx-")) {
					this.error("keyframes-name", firstPart);
				}
				const inner = block.children;
				let i = 0;
				while (i < inner.length) {
					const item = inner[i];
					if (isWs(item)) {
						i += 1;
						continue;
					}
					const framePrelude = [];
					let frame = null;
					while (i < inner.length) {
						const current = inner[i];
						i += 1;
						if (isNode(current) && current.kind === "brace") {
							frame = current;
							break;
						}
						framePrelude.push(current);
					}
					if (!this.depthOk(item, depth + 1) || !this.countRule(item)) continue;
					for (const part of significant(framePrelude)) {
						const ok =
							isTok(part) &&
							(part.type === "pct" ||
								(part.type === "ident" && ["from", "to"].includes(part.value.toLowerCase())) ||
								(part.type === "punct" && part.value === ","));
						if (!ok) this.error("bad-selector", part, text(part));
					}
					if (frame === null) this.error("missing-block", item);
					else this.declarations(frame.children, null, false);
				}
			}

			fontFace(at, block) {
				const seen = this.declarations(block.children, null, true);
				if (!seen.has("font-display")) this.warn("font-display-missing", at);
			}

			styleRule(firstItem, prelude, block, depth) {
				if (!this.depthOk(firstItem, depth) || !this.countRule(firstItem)) return;
				const classes = this.selector(prelude, firstItem);
				if (block === null) {
					this.error("missing-block", last(prelude, firstItem));
					return;
				}
				this.declarations(block.children, classes, false);
			}

			mediaPrelude(prelude) {
				for (const item of significant(prelude)) {
					if (
						isTok(item) &&
						((item.type === "ident" && S.media_idents.has(item.value.toLowerCase())) ||
							(item.type === "punct" && item.value === ","))
					) {
						continue;
					}
					if (isNode(item) && item.kind === "paren") {
						this.mediaFeature(item);
						continue;
					}
					this.error("media-not-allowed", item, text(item));
				}
			}

			mediaFeature(node) {
				const parts = significant(node.children);
				let ok = parts.length >= 1 && isTok(parts[0]) && parts[0].type === "ident" && S.media_features.has(parts[0].value.toLowerCase());
				if (ok && parts.length > 1) {
					ok =
						parts.length === 3 &&
						isTok(parts[1]) &&
						parts[1].value === ":" &&
						isTok(parts[2]) &&
						["num", "dim", "ident"].includes(parts[2].type) &&
						(parts[2].type !== "ident" || S.media_idents.has(parts[2].value.toLowerCase()));
				}
				if (!ok) this.error("media-not-allowed", node, "(" + textList(node.children));
			}

			supportsPrelude(prelude) {
				for (const item of significant(prelude)) {
					if (isTok(item) && item.type === "ident" && ["and", "or", "not"].includes(item.value.toLowerCase())) continue;
					if (isNode(item) && item.kind === "paren") {
						this.supportsCondition(item);
						continue;
					}
					this.error("supports-not-allowed", item, text(item));
				}
			}

			supportsCondition(node) {
				const parts = significant(node.children);
				if (parts.length && isNode(parts[0])) {
					this.supportsPrelude(node.children);
					return;
				}
				if (parts.length >= 3 && isTok(parts[0]) && parts[0].type === "ident" && isTok(parts[1]) && parts[1].value === ":") {
					const name = parts[0].value.toLowerCase();
					if (S.properties.has(name) || name.startsWith("--wk-") || name.startsWith("--cx-")) {
						this.value(node.children.slice(node.children.indexOf(parts[1]) + 1), name, {});
						return;
					}
				}
				this.error("supports-not-allowed", node, "(" + textList(node.children));
			}

			selector(prelude, firstItem) {
				const classes = new Set();
				if (!significant(prelude).length) {
					this.error("empty-selector", firstItem);
					return classes;
				}
				let hasPart = false;
				let lastComma = null;
				for (const item of significant(prelude)) {
					if (isTok(item) && item.type === "punct" && item.value === ",") {
						if (!hasPart) this.error("empty-selector", item);
						hasPart = false;
						lastComma = item;
					} else {
						hasPart = true;
					}
				}
				if (!hasPart && lastComma !== null) this.error("empty-selector", lastComma);
				this.selectorNodes(prelude, classes);
				return classes;
			}

			selectorNodes(nodes, classes) {
				let i = 0;
				const n = nodes.length;
				while (i < n) {
					const item = nodes[i];
					i += 1;
					if (isNode(item)) {
						if (item.kind === "bracket") this.attribute(item);
						else this.error("bad-selector", item, item.kind === "fn" || item.kind === "paren" ? "(" : item.name);
						continue;
					}
					const kind = item.type;
					const value = item.value;
					if (kind === "ws" || (kind === "punct" && value === ",")) continue;
					if (kind === "ident") continue;
					if (kind === "delim" && value === ".") {
						const follower = i < n ? nodes[i] : null;
						if (isTok(follower) && follower.type === "ident") {
							i += 1;
							this.className(follower, classes);
						} else {
							this.error("bad-selector", item, ".");
						}
						continue;
					}
					if (kind === "delim" && SELECTOR_DELIMS.includes(value)) continue;
					if (kind === "hash") {
						if (rules.forbidden_id_prefixes.some((p) => value.toLowerCase().startsWith(p))) {
							this.error("selector-not-allowed", item, "#" + value);
						}
						continue;
					}
					if (kind === "punct" && value === ":") {
						i = this.pseudo(nodes, i, item, classes);
						continue;
					}
					this.error("bad-selector", item, text(item));
				}
			}

			className(tok, classes) {
				const name = tok.value;
				const lower = name.toLowerCase();
				if (S.forbidden_classes.has(lower) || rules.forbidden_class_prefixes.some((p) => lower.startsWith(p))) {
					this.error("selector-not-allowed", tok, "." + name);
					return;
				}
				classes.add(name);
				if (lower.startsWith("wk-") && !S.known_classes.has(name)) this.warn("unknown-class", tok, name);
			}

			pseudo(nodes, i, colon, classes) {
				const n = nodes.length;
				const double = i < n && isTok(nodes[i]) && nodes[i].type === "punct" && nodes[i].value === ":";
				if (double) i += 1;
				const target = i < n ? nodes[i] : null;
				const prefix = double ? "::" : ":";
				if (isTok(target) && target.type === "ident") {
					const name = target.value.toLowerCase();
					const allowed = double
						? S.pseudo_elements.has(name)
						: S.pseudo_classes.has(name) || S.pseudo_legacy_elements.has(name);
					if (!allowed) this.error("pseudo-not-allowed", target, prefix + target.value);
					return i + 1;
				}
				if (isNode(target) && target.kind === "fn" && !double) {
					const name = target.name.toLowerCase();
					if (S.pseudo_selector_functions.has(name)) this.selectorNodes(target.children, classes);
					else if (S.pseudo_nth_functions.has(name)) this.nthArguments(target);
					else this.error("pseudo-not-allowed", target, ":" + target.name + "()");
					return i + 1;
				}
				this.error("bad-selector", target || colon, ":");
				return i;
			}

			nthArguments(node) {
				for (const part of significant(node.children)) {
					const ok =
						isTok(part) &&
						(part.type === "num" ||
							part.type === "dim" ||
							(part.type === "ident" && ["n", "even", "odd", "-n"].includes(part.value.toLowerCase())) ||
							(part.type === "delim" && "+-".includes(part.value)));
					if (!ok) this.error("bad-selector", part, text(part));
				}
			}

			attribute(node) {
				const parts = significant(node.children);
				if (!parts.length || !(isTok(parts[0]) && parts[0].type === "ident")) {
					this.error("bad-selector", node, "[");
					return;
				}
				const name = parts[0].value.toLowerCase();
				if (S.forbidden_attributes.has(name)) {
					this.error("selector-not-allowed", node, "[" + parts[0].value + "]");
					return;
				}
				const rest = parts.slice(1);
				if (!rest.length) return;
				let i = 0;
				if (isTok(rest[0]) && rest[0].type === "delim" && "~|^$*".includes(rest[0].value)) i = 1;
				const operator = i < rest.length ? rest[i] : null;
				const value = i + 1 < rest.length ? rest[i + 1] : null;
				const flag = i + 2 < rest.length ? rest[i + 2] : null;
				const ok =
					isTok(operator) &&
					operator.type === "delim" &&
					operator.value === "=" &&
					isTok(value) &&
					["ident", "string", "num", "dim"].includes(value.type) &&
					(flag === null || (isTok(flag) && flag.type === "ident" && ["i", "s"].includes(flag.value.toLowerCase()))) &&
					rest.length <= i + 3;
				if (!ok) {
					this.error("bad-selector", rest[0], text(rest[0]));
					return;
				}
				if ((name === "class" || name === "id") && (value.type === "ident" || value.type === "string")) {
					const lowered = value.value.toLowerCase();
					if (rules.forbidden_attribute_values.some((word) => lowered.includes(word))) {
						this.error("selector-not-allowed", node, "[" + parts[0].value + "]");
					}
				}
			}

			declarations(nodes, classes, fontFace) {
				const seen = new Set();
				const segments = [[]];
				for (const item of nodes) {
					if (isTok(item) && item.type === "punct" && item.value === ";") segments.push([]);
					else segments[segments.length - 1].push(item);
				}
				const declared = new Map();
				for (const segment of segments) {
					const parts = significant(segment);
					if (!parts.length) continue;
					const brace = segment.find((p) => isNode(p) && p.kind === "brace");
					if (brace) {
						this.error("nested-rule", brace);
						continue;
					}
					const head = parts[0];
					if (!(isTok(head) && head.type === "ident" && parts.length >= 2 && isTok(parts[1]) && parts[1].type === "punct" && parts[1].value === ":")) {
						this.error("bad-declaration", head);
						continue;
					}
					seen.add(head.value.toLowerCase());
					const value = segment.slice(segment.indexOf(parts[1]) + 1);
					this.declaration(head, head.value, value, fontFace, declared);
				}
				this.hookWarnings(classes, declared);
				return seen;
			}

			declaration(head, name, value, fontFace, declared) {
				const lower = name.toLowerCase();
				const custom = name.startsWith("--");
				if (custom) {
					if (!(name.startsWith("--wk-") || name.startsWith("--cx-"))) {
						this.error("custom-property", head);
						return;
					}
					if (name.startsWith("--wk-") && !S.known_custom_properties.has(name)) this.warn("unknown-token", head, name);
				} else if (fontFace) {
					if (!S.font_face_properties.has(lower)) {
						this.error("property-not-allowed", head, name);
						return;
					}
				} else if (!S.properties.has(lower)) {
					this.error("property-not-allowed", head, name);
					return;
				}
				const [stripped, important] = stripImportant(value);
				if (important !== null && !name.startsWith("--wk-")) this.warn("important", important);
				const context = { font_face: fontFace, src: fontFace && lower === "src" };
				this.value(stripped, lower, context);
				if (!custom) declared.set(lower, stripped);
			}

			value(nodes, prop, context) {
				for (const item of nodes) {
					if (isNode(item)) {
						this.valueNode(item, prop, context);
						continue;
					}
					if (item.type === "string") {
						if (isScriptUrl(item.value)) this.error("script-url", item);
						if (context.in_image_set) this.urlTarget(item.value, item, prop, context);
					} else if (item.type === "url") {
						this.urlTarget(item.value, item, prop, context);
					} else if (item.type === "delim" && item.value === "!") {
						this.error("bad-important", item);
					} else if (item.type === "at") {
						this.error("bad-selector", item, "@" + item.value);
					}
				}
			}

			valueNode(node, prop, context) {
				if (node.kind === "brace") {
					this.error("nested-rule", node);
					return;
				}
				if (node.kind !== "fn") {
					this.value(node.children, prop, context);
					return;
				}
				const name = node.name.toLowerCase();
				if (name === "expression") {
					this.error("expression", node);
				} else if (name === "url") {
					const parts = significant(node.children);
					if (parts.length === 1 && isTok(parts[0]) && parts[0].type === "string") this.urlTarget(parts[0].value, node, prop, context);
					else this.error("bad-url", node);
				} else if (name === "var" && S.url_capable_properties.has(prop)) {
					this.error("var-in-url-property", node, prop);
				} else if (name === "image-set") {
					if (!S.url_properties.has(prop)) this.error("url-not-allowed", node, prop);
					this.value(node.children, prop, Object.assign({}, context, { in_image_set: true }));
				} else if (S.functions.has(name) || (context.src && S.font_face_functions.has(name))) {
					this.value(node.children, prop, context);
				} else {
					this.error("function-not-allowed", node, node.name);
				}
			}

			urlTarget(target, at, prop, context) {
				if (context.font_face) this.error("font-face-src", at);
				else if (isScriptUrl(target)) this.error("script-url", at);
				else if (!S.url_properties.has(prop)) this.error("url-not-allowed", at, prop);
				else if (DATA_URL.test(target)) {
					if (Array.from(target).length > LIMITS.max_data_url) this.error("url-external", at, short(target));
				} else if (!sameOrigin(target)) this.error("url-external", at, short(target));
			}

			hookWarnings(classes, declared) {
				if (classes && classes.size) {
					const hooks = [...classes].filter((c) => S.hook_classes.has(c)).sort();
					if (hooks.length) {
						for (const [prop, value] of declared) {
							const node = first(value, null);
							if (node !== null && hides(prop, value)) this.warn("hides-hook", node, "." + hooks[0]);
						}
					}
				}
				const foreground = hexOf(declared.get("color"));
				const background = hexOf(declared.get("background-color")) || hexOf(declared.get("background"));
				if (foreground && background) {
					const value = ratio(foreground, background);
					if (value < 4.5) {
						const at = first(declared.get("color") || [], null);
						if (at !== null) this.warn("contrast", at, value.toFixed(1));
					}
				}
			}
		}

		function scanCharacters(tokenizer, source, sink) {
			tokenizer.cs.forEach((c, i) => {
				const code = c.codePointAt(0);
				const line = tokenizer.lineOf[i];
				const col = tokenizer.colOf[i];
				if ((code < 0x20 && c !== "\t" && c !== "\n") || code === 0x7f || (code >= 0x80 && code <= 0x9f) || INVISIBLE.has(code) || (code >= 0xd800 && code <= 0xdfff)) {
					sink("control-char", line, col, code.toString(16).toUpperCase().padStart(4, "0"));
				} else if (c === "<") {
					sink("markup", line, col, "<");
				} else if (c === "-" && tokenizer.cs[i + 1] === "-" && tokenizer.cs[i + 2] === ">") {
					sink("markup", line, col, "-->");
				}
			});
		}

		function run(css, checker) {
			if (new TextEncoder().encode(css).length > LIMITS.max_bytes) {
				checker.add("error", "too-large", 1, 1, Math.floor(LIMITS.max_bytes / 1024));
				return;
			}
			const source = css.replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/\f/g, "\n");
			const sink = (code, line, col, ...args) => checker.addError(code, line, col, ...args);
			const tokenizer = new Tokenizer(source, sink);
			scanCharacters(tokenizer, source, sink);
			const tree = buildTree(tokenizer.tokens(), sink);
			checker.ruleList(tree, 1);
		}

		function validate(css) {
			const result = { ok: true, errors: [], warnings: [] };
			const checker = new Checker(result);
			try {
				run(String(css), checker);
			} catch (error) {
				checker.add("error", "bad-declaration", 1, 1);
			}
			const order = (a, b) =>
				a.line - b.line || a.column - b.column || (a.code < b.code ? -1 : a.code > b.code ? 1 : 0);
			result.errors.sort(order);
			result.warnings.sort(order);
			result.ok = result.errors.length === 0;
			return result;
		}

		return { validate, formatMessage };
	}

	return { createValidator, validate: (css, rules) => createValidator(rules).validate(css) };
});
