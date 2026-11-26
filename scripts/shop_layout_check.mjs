// Render the stock Webshop pages, the login page and the 404 page of a running site in headless Chrome and assert layout facts.
// It guards against the unstyled shop pages (a Website Theme without a usable stylesheet): no `href="None"`, Frappe's base
// stylesheet present, every stylesheet really served as CSS, the kit tokens applied to the page, the product list and grid
// laid out the same for every card (also after scrolling and after the grid/list toggle), the toggle buttons clear of the
// cards, images inside their cards, no horizontal scroll, and the narrow-screen menu collapsed.
//
//   npm install --no-save puppeteer-core@23.11.1
//   CHROME=/usr/bin/google-chrome node scripts/shop_layout_check.mjs http://shop.localhost:8000 [outdir]
//
// The site needs Webshop on with the ten sample products (`bench execute website_kit.probe.shop_demo`). LABEL names the
// screenshots. Exit code 1 on any failure.
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
const [base = "http://shop.localhost:8000", outDir = ""] = process.argv.slice(2);
const label = process.env.LABEL || "check";
if (outDir) mkdirSync(outDir, { recursive: true });

const problems = [];
const check = (ok, text) => {
	if (!ok) problems.push(text);
};
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const browser = await puppeteer.launch({
	executablePath: process.env.CHROME || "/usr/bin/google-chrome",
	headless: false,
	args: ["--headless=new", "--no-sandbox", "--disable-gpu", ...(process.env.CHROME_ARGS || "").split("|").filter(Boolean)],
});

// The route of a product page is made from the item name and a random suffix: ask the catalogue API for the first one.
const catalogue = await fetch(new URL("/api/method/webshop.webshop.api.get_product_filter_data", base), {
	method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query_args: { start: 0 } }),
}).then((r) => r.json());
const productRoute = "/" + catalogue.message.items[0].route;

const PAGES = [
	["/all-products", "list"],
	[productRoute, "page"],
	["/search?search=mug", "page"],
	["/cart", "page"],
	["/login", "page"],
	["/no-such-page-for-the-check", "page"],
];

async function common(page, where, themed) {
	const info = await page.evaluate(async () => {
		const sheets = [...document.querySelectorAll('link[rel="stylesheet"]')].map((l) => l.getAttribute("href"));
		const served = [];
		for (const href of sheets) {
			if (!href || href === "None") continue;
			const r = await fetch(href);
			served.push({ href, status: r.status, type: r.headers.get("content-type") || "" });
		}
		const root = getComputedStyle(document.documentElement);
		const probe = document.createElement("div");
		probe.style.color = root.getPropertyValue("--wk-color-bg").trim();
		document.body.appendChild(probe);
		const tokenBg = getComputedStyle(probe).color;
		probe.remove();
		return {
			sheets, served, tokenBg, bodyBg: getComputedStyle(document.body).backgroundColor,
			hscroll: document.documentElement.scrollWidth > innerWidth + 1, scrollW: document.documentElement.scrollWidth,
		};
	});
	check(!info.sheets.some((h) => !h || h === "None" || h.endsWith("/None")), `${where}: a stylesheet link points at None`);
	check(info.sheets.some((h) => /website\.bundle/.test(h || "")), `${where}: Frappe's website.bundle.css is not linked`);
	if (themed) check(info.sheets.some((h) => /wk-theme/.test(h || "")), `${where}: the kit token file is not linked`);
	for (const s of info.served) check(s.status === 200 && /text\/css/.test(s.type), `${where}: ${s.href} is ${s.status} ${s.type}`);
	// The login page replaces Frappe's head block: the kit sheets reach it through the navbar, so it is themed like the rest.
	check(!themed || (info.tokenBg !== "" && info.bodyBg === info.tokenBg), `${where}: body background ${info.bodyBg} is not the token --wk-color-bg ${info.tokenBg}`);
	check(!info.hscroll, `${where}: horizontal scroll (${info.scrollW}px)`);
}

async function listFacts(page, mode) {
	await page.mouse.move(2, 2); // a hovered card has its own shadow
	return page.evaluate((mode) => {
		const r = (e) => {
			const b = e.getBoundingClientRect();
			return { x: b.x, y: b.y + scrollY, w: b.width, h: b.height };
		};
		const sel = mode === "grid" ? ".products-list .card" : ".products-list .list-row";
		const items = [...document.querySelectorAll(sel)];
		const toggles = [...document.querySelectorAll(".toggle-container button")].map(r);
		return {
			items: items.map((i) => {
				const img = i.querySelector("img");
				const cs = getComputedStyle(i);
				return {
					box: r(i), img: img ? r(img) : null, radius: cs.borderTopLeftRadius, border: cs.borderTopWidth + cs.borderTopStyle,
					bg: cs.backgroundColor, pad: cs.paddingLeft, shadow: cs.boxShadow,
				};
			}),
			toggles, vw: innerWidth,
		};
	}, mode);
}

function sameLayout(facts, where, expectColumns) {
	const items = facts.items;
	check(items.length >= 10, `${where}: ${items.length} product cards, 10 expected`);
	if (!items.length) return;
	const first = items[0];
	for (const [n, it] of items.entries()) {
		check(Math.abs(it.box.w - first.box.w) <= 1, `${where}: card ${n} is ${it.box.w}px wide, card 0 is ${first.box.w}px`);
		// A list row is as high as its text (a long name wraps); the cards of the grid share one height.
		if (expectColumns) check(Math.abs(it.box.h - first.box.h) <= 40, `${where}: card ${n} is ${it.box.h}px high, card 0 is ${first.box.h}px`);
		for (const key of ["radius", "border", "bg", "pad", "shadow"]) {
			check(it[key] === first[key], `${where}: card ${n} ${key} ${it[key]} differs from card 0 ${first[key]}`);
		}
		check(it.img !== null, `${where}: card ${n} has no image`);
		if (it.img) {
			check(it.img.w <= it.box.w + 1 && it.img.h <= it.box.h + 1, `${where}: card ${n} image ${Math.round(it.img.w)}x${Math.round(it.img.h)} is larger than its card`);
			check(it.img.x >= it.box.x - 1 && it.img.x + it.img.w <= it.box.x + it.box.w + 1, `${where}: card ${n} image sticks out of its card`);
			check(Math.abs(it.img.w - first.img.w) <= 1 && Math.abs(it.img.h - first.img.h) <= 1, `${where}: card ${n} image box differs from card 0`);
		}
		check(it.box.x >= -1 && it.box.x + it.box.w <= facts.vw + 1, `${where}: card ${n} is outside the viewport horizontally`);
	}
	if (expectColumns) {
		const columns = new Set(items.map((i) => Math.round(i.box.x))).size;
		check(columns === expectColumns, `${where}: ${columns} columns, ${expectColumns} expected`);
	}
	for (const [n, t] of facts.toggles.entries()) {
		check(t.w <= 80 && t.h <= 60, `${where}: toggle button ${n} is ${Math.round(t.w)}x${Math.round(t.h)}px`);
		if (facts.vw <= 768) check(t.w >= 43.5 && t.h >= 43.5, `${where}: toggle button ${n} is ${Math.round(t.w)}x${Math.round(t.h)}px, a touch target needs 44x44`);
		for (const [m, it] of items.entries()) {
			const overlap = t.x < it.box.x + it.box.w && t.x + t.w > it.box.x && t.y < it.box.y + it.box.h && t.y + t.h > it.box.y;
			check(!overlap, `${where}: toggle button ${n} overlaps card ${m}`);
		}
	}
}

// Text against the background it is drawn on (the nearest ancestor with a solid fill): WCAG 4.5:1, 3:1 for large text.
async function contrastProblems(page) {
	return page.evaluate(() => {
		const parse = (c) => (c.match(/[\d.]+/g) || []).map(Number);
		const lum = ([r, g, b]) => {
			const f = (v) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
			return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
		};
		const backdrop = (e) => {
			for (let n = e; n; n = n.parentElement) {
				const c = parse(getComputedStyle(n).backgroundColor);
				if (c.length >= 3 && (c.length === 3 || c[3] > 0.95)) return c.slice(0, 3);
			}
			return [255, 255, 255];
		};
		const selectors = "h1, h2, h3, h4, .page-breadcrumbs a, .page-breadcrumbs span, .page-breadcrumbs li, .breadcrumb-item, .breadcrumb a, .text-muted, .error-text, .back-to-home a, .page-card a, .page-card p, .page-card-head h4, .for-login .sign-up-message, .for-forgot a, label, .wk-header a, .wk-header summary, .filters-title, .filter-label, .clear-filters a, .list-row, .list-row a, .list-row p, .list-row div, .card .card-title, .card p, .card a, .product-container h1, .product-container h2, .product-container p, .product-container .product-title, .product-container .product-code, .cart-empty-message, .cart-empty-message a, .cart-container h6, .shopping-cart-header, body > div p";
		const out = [];
		const seen = new Set();
		for (const e of document.querySelectorAll(selectors)) {
			const own = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 1);
			const box = e.getBoundingClientRect();
			if (!own || seen.has(e) || box.width < 4 || box.height < 4) continue;
			seen.add(e);
			const cs = getComputedStyle(e);
			if (cs.visibility === "hidden" || cs.display === "none" || parseFloat(cs.opacity) < 0.1) continue;
			const fg = parse(cs.color).slice(0, 3);
			const bg = backdrop(e);
			const a = lum(fg), b = lum(bg);
			const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
			const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight, 10) >= 700;
			const need = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
			if (ratio < need) out.push(`${e.tagName.toLowerCase()}.${(e.className || "").toString().slice(0, 30)} "${e.textContent.trim().slice(0, 24)}" ${ratio.toFixed(2)}:1 (needs ${need})`);
		}
		return out;
	});
}

// The header on every page: the menu the visitor can reach is exactly one, open on a wide screen and behind a native disclosure on a
// narrow one; the disclosure works from the keyboard (Enter and Space on the summary).
async function menuChecks(page, where, wide) {
	const info = await page.evaluate(() => {
		const shown = (e) => e && getComputedStyle(e).display !== "none" && e.getBoundingClientRect().width > 0;
		const burger = document.querySelector(".wk-header__burger");
		const menu = document.querySelector(".wk-header__menu");
		const visibleNavs = [...document.querySelectorAll(".wk-header__nav")].filter(shown);
		return {
			header: !!document.querySelector(".wk-header"), burger: shown(burger), menu: shown(menu), navs: visibleNavs.length,
			checkbox: !!document.querySelector(".wk-header input[type=checkbox]"),
		};
	});
	check(info.header, `${where}: no kit header`);
	check(!info.checkbox, `${where}: the header still has a checkbox`);
	if (wide) {
		check(info.navs === 1 && !info.burger, `${where}: wide screen: ${info.navs} visible menus, burger ${info.burger} (one open menu, no burger expected)`);
		return;
	}
	check(info.burger && info.navs === 0, `${where}: narrow screen: burger ${info.burger}, ${info.navs} visible menus (the menu must be closed behind the burger)`);
	await page.evaluate(() => window.scrollTo(0, 0));
	await page.focus(".wk-header__burger");
	await page.keyboard.press("Enter");
	const opened = await page.evaluate(() => ({ open: document.querySelector(".wk-header__menu").open, navs: [...document.querySelectorAll(".wk-header__nav")].filter((n) => n.getBoundingClientRect().width > 0).length }));
	check(opened.open && opened.navs === 1, `${where}: Enter on the burger does not open exactly one menu (${JSON.stringify(opened)})`);
	await page.keyboard.press("Space");
	const closed = await page.evaluate(() => document.querySelector(".wk-header__menu").open);
	check(!closed, `${where}: Space on the burger does not close the menu`);
}

async function scrollBottom(page) {
	await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
	await pause(600);
}

try {
	for (const size of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
		const wide = size.width > 800;
		for (const [path, kind] of PAGES) {
			const page = await browser.newPage();
			await page.setViewport(size);
			await page.goto(new URL(path, base).href, { waitUntil: "networkidle0" });
			const where = `${size.width}px ${path}`;
			await common(page, where, true);
			for (const text of await contrastProblems(page)) check(false, `${where}: low contrast ${text}`);
			await menuChecks(page, where, wide);
			if (outDir) await page.screenshot({ path: `${outDir}/${label}-${path.replace(/[^a-z]+/g, "_")}-${size.width}.png`, fullPage: kind !== "list" });
			if (kind === "list") {
				await page.waitForSelector(".products-list .list-row");
				sameLayout(await listFacts(page, "list"), `${where} list`);
				await scrollBottom(page);
				sameLayout(await listFacts(page, "list"), `${where} list after scrolling`);
				await page.evaluate(() => window.scrollTo(0, 0));
				await page.click(".btn-grid-view");
				await page.waitForSelector(".products-list .card");
				await pause(600);
				sameLayout(await listFacts(page, "grid"), `${where} grid`, wide ? 3 : 1);
				if (outDir) await page.screenshot({ path: `${outDir}/${label}-grid-${size.width}.png` });
				await scrollBottom(page);
				sameLayout(await listFacts(page, "grid"), `${where} grid after scrolling`, wide ? 3 : 1);
				await page.evaluate(() => window.scrollTo(0, 0));
				await page.click(".btn-list-view");
				await page.waitForSelector(".products-list .list-row");
				await pause(600);
				sameLayout(await listFacts(page, "list"), `${where} list after the toggle`);
			}
			await page.close();
		}
	}
} finally {
	await browser.close();
}
if (problems.length) {
	console.log(`${problems.length} problems`);
	for (const p of problems.slice(0, 60)) console.log(" - " + p);
	process.exit(1);
}
console.log("shop layout ok");
