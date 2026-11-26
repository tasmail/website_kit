// The theme settings page: preset cards, the live preview, the `custom` theme editor and the Custom CSS editor.
// Everything it shows comes from the server (`website_kit.api`): the preview is compiled by the same code that a save runs.
// The client twin of the CSS validator (public/js/wk_css_validator.js) only gives feedback while typing; the server decides.

(function () {
	const API = "website_kit.api.";
	const ASSET = "/assets/website_kit/js/";
	const COLOUR_LABELS = {
		"color-primary": __("Primary (buttons)"),
		"color-primary-contrast": __("Text on primary"),
		"color-accent": __("Accent (focus, badges)"),
		"color-bg": __("Page background"),
		"color-surface": __("Cards and bands"),
		"color-text": __("Text"),
		"color-muted": __("Secondary text"),
		"color-border": __("Borders"),
		"color-link": __("Links"),
		"color-danger": __("Errors"),
		"color-inverse": __("Dark band"),
		"color-inverse-contrast": __("Text on dark band"),
	};
	// Words of the option lists; written out so that the translation check finds them.
	const WORDS = {
		light: __("light"),
		dark: __("dark"),
		tinted: __("tinted"),
		flat: __("flat"),
		outlined: __("outlined"),
		raised: __("raised"),
		solid: __("solid"),
		pill: __("pill"),
		square: __("square"),
		none: __("none"),
		small: __("small"),
		medium: __("medium"),
		large: __("large"),
		compact: __("compact"),
		comfortable: __("comfortable"),
		spacious: __("spacious"),
	};
	const word = (key) => WORDS[key] || key;
	const MOCK = {
		services: __("Services"),
		contacts: __("Contacts"),
		welcome: __("Welcome"),
		what_we_do: __("What we do"),
		a_short_text_of_the_page_with_a: __("A short text of the page, with a"),
		link: __("link"),
		secondary_text: __("Secondary text."),
		call_to_action: __("Call to action"),
		secondary: __("Secondary"),
		card: __("Card"),
		cards_follow_the_card_style: __("Cards follow the card style."),
		sale: __("Sale"),
		product: __("Product"),
		name: __("Name"),
		your_name: __("Your name"),
		an_error_looks_like_this: __("An error looks like this."),
	};
	const VARIANT_LABELS = {
		header: __("Header"),
		footer: __("Footer"),
		card: __("Cards"),
		button: __("Buttons"),
	};
	const wk = {
		data: null,
		validator: null,
		rules: null,
		timer: null,
		css_timer: null,
		frame_width: "100%",
	};
	window.wk_settings = wk;

	// ---------------------------------------------------------------- helpers
	function esc(text) {
		return frappe.utils.escape_html(String(text == null ? "" : text));
	}

	function parse_overrides(frm) {
		try {
			const value = JSON.parse(frm.doc.token_overrides || "{}");
			return { tokens: value.tokens || {}, variants: value.variants || {} };
		} catch (error) {
			return { tokens: {}, variants: {} };
		}
	}

	function write_overrides(frm, overrides) {
		const empty = !Object.keys(overrides.tokens).length && !Object.keys(overrides.variants).length;
		return frm.set_value("token_overrides", empty ? "" : JSON.stringify(overrides, null, "\t"));
	}

	function preset_data(name) {
		return wk.data.presets.find((p) => p.name === name);
	}

	function effective(frm) {
		const base_name = frm.doc.preset === "custom" ? frm.doc.custom_base || "clear" : frm.doc.preset;
		const base = preset_data(base_name) || wk.data.presets[0];
		const overrides = parse_overrides(frm);
		return {
			tokens: Object.assign({}, base.tokens, overrides.tokens),
			variants: Object.assign({}, base.variants, overrides.variants),
		};
	}

	function message_text(message) {
		const template = wk.rules.messages[message.code];
		if (!template) return message.message;
		let text = __(template);
		(message.args || []).forEach((value, index) => {
			text = text.split("{" + index + "}").join(value);
		});
		return text;
	}

	// ---------------------------------------------------------------- loading
	async function load(frm) {
		if (wk.data) return;
		const [data, rules] = await Promise.all([
			frappe.xcall(API + "theme_data"),
			fetch(ASSET + "wk_css_rules.json").then((r) => r.json()),
		]);
		await new Promise((resolve) => frappe.require(ASSET + "wk_css_validator.js", resolve));
		wk.data = data;
		wk.rules = rules;
		wk.validator = window.WkCssValidator.createValidator(rules);
	}

	// ---------------------------------------------------------------- preset cards
	function card_html(preset, selected) {
		const t = preset.tokens;
		const style = [
			`--c-bg:${t["color-bg"]}`,
			`--c-surface:${t["color-surface"]}`,
			`--c-text:${t["color-text"]}`,
			`--c-muted:${t["color-muted"]}`,
			`--c-primary:${t["color-primary"]}`,
			`--c-on-primary:${t["color-primary-contrast"]}`,
			`--c-border:${t["color-border"]}`,
			`--c-head:${preset.variants.header === "dark" ? t["color-inverse"] : t["color-bg"]}`,
			`--c-radius:${t["radius-md"]}`,
		].join(";");
		return `<button type="button" class="wk-pick${selected ? " is-selected" : ""}" data-preset="${esc(preset.name)}"
			aria-pressed="${selected ? "true" : "false"}" style="${style}">
			<span class="wk-mini" aria-hidden="true"><i class="wk-mini-bar"></i><b>Aa</b><u></u><u class="short"></u><s>${__("Button")}</s></span>
			<strong>${esc(__(preset.label))}</strong>
			<small>${esc(__(preset.description))}</small>
		</button>`;
	}

	function custom_card_html(selected) {
		return `<button type="button" class="wk-pick wk-pick-custom${selected ? " is-selected" : ""}" data-preset="custom"
			aria-pressed="${selected ? "true" : "false"}">
			<span class="wk-mini wk-mini-custom" aria-hidden="true"><b>+</b></span>
			<strong>${__("Custom")}</strong>
			<small>${__("Start from any theme and change its colours, font, corners and spacing.")}</small>
		</button>`;
	}

	function render_cards(frm) {
		const wrapper = frm.fields_dict.preset_cards.$wrapper;
		const html = wk.data.presets.map((p) => card_html(p, frm.doc.preset === p.name)).join("") + custom_card_html(frm.doc.preset === "custom");
		wrapper.html(`<style>
			.wk-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:12px;margin:8px 0}
			.wk-pick{text-align:start;border:2px solid var(--border-color);border-radius:var(--border-radius-md);background:var(--card-bg);padding:10px;display:flex;flex-direction:column;gap:6px;cursor:pointer}
			.wk-pick:hover{border-color:var(--gray-500)}
			.wk-pick.is-selected{border-color:var(--primary);box-shadow:0 0 0 1px var(--primary)}
			.wk-pick small{color:var(--text-muted);line-height:1.35}
			.wk-mini{display:flex;flex-direction:column;gap:5px;padding:8px;background:var(--c-bg);border:1px solid var(--c-border);border-radius:var(--c-radius);height:104px;overflow:hidden}
			.wk-mini-bar{display:block;height:10px;margin:-8px -8px 0;background:var(--c-head);border-bottom:1px solid var(--c-border)}
			.wk-mini b{color:var(--c-text);font-size:16px;line-height:1}
			.wk-mini u{display:block;height:5px;background:var(--c-surface);border-radius:3px;box-shadow:inset 0 0 0 1px var(--c-border)}
			.wk-mini u.short{width:60%}
			.wk-mini s{text-decoration:none;align-self:flex-start;font-size:10px;padding:2px 8px;background:var(--c-primary);color:var(--c-on-primary);border-radius:var(--c-radius)}
			.wk-mini-custom{align-items:center;justify-content:center;border-style:dashed;--c-bg:var(--card-bg);--c-border:var(--gray-500);--c-text:var(--text-muted)}
			.wk-mini-custom b{font-size:34px}
		</style><div class="wk-cards" role="group" aria-label="${esc(__("Themes"))}">${html}</div>`);
		wrapper.find(".wk-pick").on("click", function () {
			choose_preset(frm, $(this).data("preset"));
		});
	}

	async function choose_preset(frm, name) {
		if (name === frm.doc.preset) return;
		if (name === "custom") {
			const values = await frappe.xcall(API + "duplicate_as_custom", {
				preset: frm.doc.preset,
				token_overrides: frm.doc.token_overrides || "",
				custom_base: frm.doc.custom_base || "",
			});
			await frm.set_value(values);
		} else {
			const switch_to = async () => {
				await frm.set_value({ preset: name, custom_base: "", token_overrides: "" });
			};
			if (frm.doc.token_overrides && frm.doc.token_overrides.trim()) {
				frappe.confirm(__("Your own colours and sizes are dropped when you pick a ready-made theme. Continue?"), switch_to);
				return;
			}
			await switch_to();
		}
	}

	// ---------------------------------------------------------------- preview
	function mock_page(frm, css) {
		const brand = esc(frm.doc.brand_name || __("Your company"));
		const t = (text) => esc(MOCK[text]);
		return `<!doctype html><html lang="${esc(frappe.boot.lang || "en")}"><head><meta charset="utf-8">
			<meta name="viewport" content="width=device-width, initial-scale=1">
			<link rel="stylesheet" href="/assets/website_kit/css/wk.css"><style>${css}</style>
			<style>body{margin:0}.m-hero{padding:calc(var(--wk-space-unit)*4) 0}.m-row{display:flex;flex-wrap:wrap;gap:calc(var(--wk-space-unit)*2)}.m-row>*{flex:1 1 200px}.m-nav{display:flex;gap:16px;align-items:center;justify-content:space-between;padding:12px 0}</style></head>
			<body><header class="wk-header"><div class="wk-container m-nav"><strong>${brand}</strong><nav><a href="#">${t("services")}</a> &nbsp; <a href="#">${t("contacts")}</a></nav></div></header>
			<main class="wk-container"><section class="m-hero"><h1>${t("welcome")}</h1><h2>${t("what_we_do")}</h2><p>${t("a_short_text_of_the_page_with_a")} <a href="#">${t("link")}</a>. <span style="color:var(--wk-color-muted)">${t("secondary_text")}</span></p>
			<p><a class="wk-button" href="#">${t("call_to_action")}</a> <a class="wk-button wk-button--secondary" href="#">${t("secondary")}</a></p></section>
			<section class="m-row"><div class="wk-card" style="padding:16px"><h3>${t("card")}</h3><p>${t("cards_follow_the_card_style")}</p></div>
			<div class="wk-product-card" style="padding:16px"><span class="wk-badge">${t("sale")}</span><h3>${t("product")}</h3><p class="wk-price">1 200 UAH</p></div>
			<form onsubmit="return false" style="padding:16px"><label>${t("name")}<br><input class="wk-field" value="${t("your_name")}"></label><p style="color:var(--wk-color-danger)">${t("an_error_looks_like_this")}</p></form></section></main>
			<footer class="wk-footer"><div class="wk-container" style="padding-block:24px">${brand}</div></footer></body></html>`;
	}

	function render_preview_shell(frm) {
		const wrapper = frm.fields_dict.preview_html.$wrapper;
		wrapper.html(`<div class="wk-preview-tools" style="margin-bottom:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
			<div class="btn-group" role="group" aria-label="${esc(__("Preview width"))}">
				<button type="button" class="btn btn-default btn-xs" data-width="100%">${__("Desktop")}</button>
				<button type="button" class="btn btn-default btn-xs" data-width="390px">${__("Phone")}</button>
			</div>
			<span class="text-muted small">${__("Saving publishes this look to the site. Use Save as draft to see it on the real pages first.")}</span></div>
			<div style="overflow:auto;border:1px solid var(--border-color);border-radius:var(--border-radius-md);background:var(--gray-100)">
			<iframe class="wk-preview-frame" title="${esc(__("Preview of the theme"))}" sandbox="allow-same-origin"
				style="display:block;margin:0 auto;border:0;width:${wk.frame_width};height:520px;background:#fff"></iframe></div>
			<div class="wk-contrast" aria-live="polite" style="margin-top:8px"></div>`);
		wrapper.find("[data-width]").on("click", function () {
			wk.frame_width = $(this).data("width");
			wrapper.find("iframe").css("width", wk.frame_width);
		});
	}

	function schedule_preview(frm) {
		clearTimeout(wk.timer);
		wk.timer = setTimeout(() => run_preview(frm), 250);
	}

	async function run_preview(frm) {
		if (!wk.data || !frm.fields_dict.preview_html) return;
		const result = await frappe.xcall(API + "preview", {
			preset: frm.doc.preset,
			token_overrides: frm.doc.token_overrides || "",
			custom_css: frm.doc.custom_css || "",
			custom_base: frm.doc.custom_base || "",
		});
		const wrapper = frm.fields_dict.preview_html.$wrapper;
		if (result.css) {
			wrapper.find("iframe").attr("srcdoc", mock_page(frm, result.css));
		}
		render_contrast(frm, result);
		show_messages(frm, result.errors, result.warnings, result.token_error);
	}

	function render_contrast(frm, result) {
		const box = frm.fields_dict.preview_html.$wrapper.find(".wk-contrast");
		const bad = (result.contrast || []).filter((c) => !c.passed);
		if (!bad.length) {
			box.html(`<span class="indicator-pill green">${__("All colour pairs are readable")}</span>`);
			return;
		}
		const rows = bad
			.map((c) => `<li>${esc(__(c.label))}: <b>${c.ratio}:1</b> (${__("needs")} ${c.minimum}:1)</li>`)
			.join("");
		box.html(`<span class="indicator-pill orange">${__("Low contrast")}</span><ul style="margin:6px 0 0;padding-inline-start:20px">${rows}</ul>`);
	}

	// ---------------------------------------------------------------- custom theme editor
	function render_editor(frm) {
		if (frm.doc.preset !== "custom" || !frm.fields_dict.editor_html) return;
		const eff = effective(frm);
		const colours = Object.keys(COLOUR_LABELS)
			.map((name) => {
				const value = eff.tokens[name];
				return `<div class="wk-ed-row"><label for="wk-c-${name}">${esc(COLOUR_LABELS[name])}</label>
					<input type="color" id="wk-c-${name}" data-colour="${name}" value="${esc(value)}">
					<input type="text" class="form-control input-xs" data-colour-text="${name}" value="${esc(value)}" maxlength="7" pattern="#[0-9a-fA-F]{6}" aria-label="${esc(COLOUR_LABELS[name])}"></div>`;
			})
			.join("");
		const font_options = (current) =>
			wk.data.fonts.map((f) => `<option value="${f.slug}"${f.slug === current ? " selected" : ""}>${esc(f.family)}</option>`).join("");
		const sizes = ["14px", "15px", "16px", "17px", "18px"];
		const radius_now = Object.entries(wk.data.radius_choices).find(([, v]) => v[1] === eff.tokens["radius-md"]);
		const density_now = Object.entries(wk.data.density_choices).find(([, v]) => v[0] === eff.tokens["space-unit"]);
		const variants = Object.keys(wk.data.meta.variants)
			.map(
				(name) => `<div class="wk-ed-row"><label for="wk-v-${name}">${esc(VARIANT_LABELS[name] || name)}</label>
				<select class="form-control input-xs" id="wk-v-${name}" data-variant="${name}">${wk.data.meta.variants[name]
					.map((o) => `<option value="${o}"${eff.variants[name] === o ? " selected" : ""}>${esc(word(o))}</option>`)
					.join("")}</select></div>`
			)
			.join("");
		const sel = (id, label, options) => `<div class="wk-ed-row"><label for="${id}">${label}</label><select class="form-control input-xs" id="${id}">${options}</select></div>`;
		const wrapper = frm.fields_dict.editor_html.$wrapper;
		wrapper.html(`<style>
			.wk-ed{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:4px 32px}
			.wk-ed h6{margin:14px 0 6px;text-transform:uppercase;font-size:11px;color:var(--text-muted)}
			.wk-ed-row{display:flex;align-items:center;gap:8px;margin:4px 0}
			.wk-ed-row label{flex:1;margin:0;font-weight:normal}
			.wk-ed-row input[type=color]{width:36px;height:28px;padding:0;border:1px solid var(--border-color);border-radius:4px;background:none}
			.wk-ed-row input[type=text]{width:84px}.wk-ed-row select{width:160px}
		</style>
		<div class="wk-ed"><div><h6>${__("Colours")}</h6>${colours}</div>
		<div><h6>${__("Type")}</h6>
			${sel("wk-font-body", __("Body font"), font_options(eff.tokens["font-body"]))}
			${sel("wk-font-heading", __("Heading font"), font_options(eff.tokens["font-heading"]))}
			${sel("wk-size", __("Base text size"), sizes.map((s) => `<option${s === eff.tokens["font-size-base"] ? " selected" : ""}>${s}</option>`).join(""))}
			<h6>${__("Shape and space")}</h6>
			${sel("wk-radius", __("Corner radius"), Object.keys(wk.data.radius_choices).map((k) => `<option value="${k}"${radius_now && radius_now[0] === k ? " selected" : ""}>${esc(word(k))}</option>`).join(""))}
			${sel("wk-density", __("Density"), Object.keys(wk.data.density_choices).map((k) => `<option value="${k}"${density_now && density_now[0] === k ? " selected" : ""}>${esc(word(k))}</option>`).join(""))}
			<h6>${__("Page parts")}</h6>${variants}
			<h6>${__("Start again from")}</h6>
			${sel("wk-restart", __("Copy a ready-made theme"), `<option value="">-</option>` + wk.data.presets.map((p) => `<option value="${p.name}">${esc(__(p.label))}</option>`).join(""))}
		</div></div>`);
		bind_editor(frm, wrapper);
	}

	function bind_editor(frm, wrapper) {
		const set_tokens = (values) => {
			const overrides = parse_overrides(frm);
			Object.assign(overrides.tokens, values);
			return write_overrides(frm, overrides);
		};
		wrapper.find("[data-colour]").on("input", function () {
			const name = $(this).data("colour");
			wrapper.find(`[data-colour-text="${name}"]`).val(this.value);
			set_tokens({ [name]: this.value });
		});
		wrapper.find("[data-colour-text]").on("change", function () {
			const name = $(this).data("colour-text");
			const value = this.value.trim();
			if (!/^#[0-9a-fA-F]{6}$/.test(value)) {
				frappe.show_alert({ message: __("A colour is written as #rrggbb."), indicator: "orange" });
				this.value = effective(frm).tokens[name];
				return;
			}
			wrapper.find(`[data-colour="${name}"]`).val(value.toLowerCase());
			set_tokens({ [name]: value.toLowerCase() });
		});
		wrapper.find("#wk-font-body").on("change", function () {
			set_tokens({ "font-body": this.value });
		});
		wrapper.find("#wk-font-heading").on("change", function () {
			set_tokens({ "font-heading": this.value });
		});
		wrapper.find("#wk-size").on("change", function () {
			set_tokens({ "font-size-base": this.value });
		});
		wrapper.find("#wk-radius").on("change", function () {
			const [sm, md, lg] = wk.data.radius_choices[this.value];
			set_tokens({ "radius-sm": sm, "radius-md": md, "radius-lg": lg });
		});
		wrapper.find("#wk-density").on("change", function () {
			const [unit, gap] = wk.data.density_choices[this.value];
			set_tokens({ "space-unit": unit, "section-gap": gap });
		});
		wrapper.find("[data-variant]").on("change", function () {
			const overrides = parse_overrides(frm);
			overrides.variants[$(this).data("variant")] = this.value;
			write_overrides(frm, overrides);
		});
		wrapper.find("#wk-restart").on("change", async function () {
			if (!this.value) return;
			const values = await frappe.xcall(API + "duplicate_as_custom", { preset: this.value, token_overrides: "", custom_base: "" });
			await frm.set_value(values);
			render_editor(frm);
		});
	}

	// ---------------------------------------------------------------- Custom CSS
	function render_css_help(frm) {
		const enabled = wk.data.custom_css_enabled;
		const limits = wk.data.limits;
		frm.fields_dict.css_help.$wrapper.html(
			`<p class="text-muted small" style="margin:0 0 8px">${__("Written after the theme and linked only from the public pages, never from the Desk. Allowed: @media, @supports, @font-face (local fonts), @keyframes cx-*, most layout, colour and type properties, custom properties --wk-* and --cx-*, and url() to /files/ and /assets/ only. Selectors on internal classes or on Frappe and Webshop markup are outside the theming contract and may change in a release.")}
			(${__("At most {0} KB.").replace("{0}", Math.floor(limits.max_bytes / 1024))})</p>` +
				(enabled ? "" : `<p class="text-danger small">${__("Custom CSS is switched off for this site by the operator; it is saved but not applied.")}</p>`)
		);
		frm.set_df_property("custom_css", "read_only", enabled ? 0 : 1);
	}

	function check_css(frm) {
		clearTimeout(wk.css_timer);
		wk.css_timer = setTimeout(() => {
			const result = wk.validator.validate(frm.doc.custom_css || "");
			show_messages(frm, result.errors, result.warnings, "");
			schedule_preview(frm);
		}, 400);
	}

	function show_messages(frm, errors, warnings, token_error) {
		const box = frm.fields_dict.css_messages && frm.fields_dict.css_messages.$wrapper;
		if (!box) return;
		const item = (m, cls) =>
			`<li class="${cls}"><a href="#" data-line="${m.line}" data-col="${m.column}"><code>${m.line}:${m.column}</code></a> ${esc(message_text(m))}</li>`;
		let html = "";
		if (token_error) html += `<div class="text-danger">${esc(token_error)}</div>`;
		if (errors && errors.length) {
			html += `<div class="text-danger" role="alert"><strong>${__("This CSS will not be saved")}</strong></div><ul class="list-unstyled">${errors.map((m) => item(m, "text-danger")).join("")}</ul>`;
		} else if ((frm.doc.custom_css || "").trim()) {
			html += `<span class="indicator-pill green">${__("The CSS is valid")}</span>`;
		}
		if (warnings && warnings.length) {
			html += `<div class="text-warning" style="margin-top:6px"><strong>${__("Warnings")}</strong></div><ul class="list-unstyled">${warnings.map((m) => item(m, "text-warning")).join("")}</ul>`;
		}
		box.html(html);
		box.find("a[data-line]").on("click", function (event) {
			event.preventDefault();
			const editor = frm.fields_dict.custom_css.editor;
			if (editor && editor.gotoLine) {
				editor.gotoLine(Number($(this).data("line")), Math.max(0, Number($(this).data("col")) - 1), true);
				editor.focus();
			}
		});
	}

	// ---------------------------------------------------------------- toolbar
	function add_buttons(frm) {
		const group = __("Theme");
		const note = (r) => {
			frappe.msgprint({
				title: __("Draft saved"),
				message: __("The draft is ready. Open the site while you are logged in as a Website Manager to see it; visitors do not see it.") +
					`<br><a href="${r.preview_url}" target="_blank" rel="noopener">${__("Open the site with the draft")}</a>`,
				indicator: "green",
			});
		};
		frm.add_custom_button(__("Save as draft"), async () => {
			const r = await frappe.xcall(API + "save_draft", {
				preset: frm.doc.preset,
				token_overrides: frm.doc.token_overrides || "",
				custom_css: frm.doc.custom_css || "",
				custom_base: frm.doc.custom_base || "",
			});
			note(r);
		}, group);
		if (frm.doc.draft_file_url) {
			frm.add_custom_button(__("Open the draft on the site"), () => window.open("/?wk_preview=1", "_blank", "noopener"), group);
			frm.add_custom_button(__("Discard the draft"), async () => {
				await frappe.xcall(API + "discard_draft");
				frm.reload_doc();
			}, group);
		}
		frm.add_custom_button(__("View without Custom CSS"), () => window.open("/?wk_safe=1", "_blank", "noopener"), group);
		frm.add_custom_button(__("Leave safe mode"), () => window.open("/?wk_safe=0", "_blank", "noopener"), group);
		frm.add_custom_button(__("Check the CSS on the server"), async () => {
			const result = await frappe.xcall(API + "check_css", { custom_css: frm.doc.custom_css || "" });
			show_messages(frm, result.errors, result.warnings, "");
			if (result.ok) frappe.show_alert({ message: __("The CSS is valid"), indicator: "green" });
		}, group);
		frm.add_custom_button(__("Restore a version"), () => restore_dialog(frm), group);
		frm.add_custom_button(__("Reset Custom CSS"), () => reset(frm, "reset_custom_css", __("Remove the Custom CSS and save? The old CSS stays in the versions.")), group);
		frm.add_custom_button(__("Reset to preset"), () => reset(frm, "reset_to_preset", __("Drop your own colours, sizes and Custom CSS and save? They stay in the versions.")), group);
	}

	function reset(frm, method, question) {
		frappe.confirm(question, async () => {
			await frappe.xcall(API + method);
			frm.reload_doc();
		});
	}

	function restore_dialog(frm) {
		const rows = (frm.doc.versions || []).slice().reverse();
		if (!rows.length) {
			frappe.show_alert({ message: __("There are no saved versions yet."), indicator: "orange" });
			return;
		}
		const dialog = new frappe.ui.Dialog({
			title: __("Restore a version"),
			fields: [
				{
					fieldname: "version",
					fieldtype: "Select",
					label: __("Version"),
					reqd: 1,
					options: rows.map((r) => ({ value: r.name, label: `${r.saved_at} - ${r.reason || ""} - ${r.preset} - ${r.hash}` })),
					default: rows.length > 1 ? rows[1].name : rows[0].name,
				},
			],
			primary_action_label: __("Restore"),
			primary_action: async (values) => {
				dialog.hide();
				await frappe.xcall(API + "restore_version", { version: values.version });
				frm.reload_doc();
			},
		});
		dialog.show();
	}

	// ---------------------------------------------------------------- the form
	frappe.ui.form.on("Website Kit Settings", {
		async refresh(frm) {
			if (frm.is_new()) return;
			await load(frm);
			render_cards(frm);
			render_preview_shell(frm);
			render_editor(frm);
			render_css_help(frm);
			add_buttons(frm);
			check_css(frm);
			schedule_preview(frm);
			if (frm.doc.draft_file_url) {
				frm.dashboard.add_comment(__("A draft is waiting. Saving this page publishes the values on the page, not the draft."), "yellow", true);
			}
		},
		preset(frm) {
			if (!wk.data) return;
			render_cards(frm);
			render_editor(frm);
			schedule_preview(frm);
		},
		custom_base(frm) {
			if (wk.data) schedule_preview(frm);
		},
		token_overrides(frm) {
			if (wk.data) schedule_preview(frm);
		},
		custom_css(frm) {
			if (wk.data) check_css(frm);
		},
		brand_name(frm) {
			if (wk.data) schedule_preview(frm);
		},
	});
})();
