// The header of the Builder pages and of the stock pages (login, the shop, the 404 page) of a running site, in headless Chrome at a
// phone width and a desktop width. It guards the one-header rule: the same menu everywhere, behind a native disclosure on a phone
// that the keyboard can open and walk.
//
//   npm install --no-save puppeteer-core@23.11.1
//   CHROME=/usr/bin/google-chrome node scripts/header_check.mjs http://test.localhost:8000 [outdir]
//
// The site needs the Builder pages of the kit (Ukrainian at the root, English under /en); the shop entry is expected only when
// Webshop is on with a published product. LOGIN_NAVBAR=0 leaves the login page out (Frappe 16's login page has no navbar).
// Exit code 1 on any failure.
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
const [base = "http://test.localhost:8000", outDir = ""] = process.argv.slice(2);
if (outDir) mkdirSync(outDir, { recursive: true });

const problems = [];
const check = (ok, text) => {
	if (!ok) problems.push(text);
};

// A Builder page and the stock pages that must show its menu, per language.
const withLogin = process.env.LOGIN_NAVBAR !== "0";
const SETS = [
	{ lang: "uk", builder: "/about", stock: [...(withLogin ? ["/login"] : []), "/all-products", "/no-such-page-for-the-check"] },
	{ lang: "en", builder: "/en/about", stock: [...(withLogin ? ["/login"] : []), "/all-products", "/no-such-page-for-the-check"] },
];

const browser = await puppeteer.launch({
	executablePath: process.env.CHROME || "/usr/bin/google-chrome",
	headless: false,
	args: ["--headless=new", "--no-sandbox", "--disable-gpu", ...(process.env.CHROME_ARGS || "").split("|").filter(Boolean)],
});

// The links of the menu that is reachable (visible, or inside the open disclosure), in document order.
const menuLinks = (page) =>
	page.evaluate(() => {
		const nav = [...document.querySelectorAll(".wk-header__nav")].find((n) => n.getBoundingClientRect().width > 0 && !n.closest("details:not([open])"));
		return nav ? [...nav.querySelectorAll("a")].map((a) => [a.getAttribute("href"), a.textContent.trim()]) : null;
	});

// Focus the burger and press Enter; false (and a recorded problem) when the page has none.
async function openMenu(page, where) {
	if (!(await page.$(".wk-header__burger"))) {
		check(false, `${where}: no burger on a phone`);
		return false;
	}
	await page.focus(".wk-header__burger");
	await page.keyboard.press("Enter");
	return true;
}

async function open(size, lang, path) {
	const page = await browser.newPage();
	await page.setViewport(size);
	await page.setExtraHTTPHeaders({ "Accept-Language": lang });
	await page.goto(new URL(path, base).href, { waitUntil: "networkidle0" });
	return page;
}

// The language button leads to the same page in the other language, so its address differs from page to page: the menus are compared
// with it left out, and its address is checked on its own below.
const isSwitch = ([, text]) => text === "EN" || text === "UK";
const withoutSwitch = (menu) => menu.filter((link) => !isSwitch(link));

try {
	for (const size of [{ width: 390, height: 844 }, { width: 1440, height: 900 }]) {
		const phone = size.width < 800;
		const refs = {};
		for (const { lang, builder } of SETS) {
			const reference = await open(size, lang, builder);
			let expected;
			if (phone) {
				check(await menuLinks(reference) === null, `${size.width}px ${builder}: the menu is not collapsed on a phone`);
				await openMenu(reference, `${size.width}px ${builder}`);
			}
			expected = await menuLinks(reference);
			check(expected && expected.length >= 4, `${size.width}px ${builder}: the menu has ${expected ? expected.length : 0} links (home, about, contact, language, account expected)`);
			check(expected && expected.some(([href]) => href === "/login?redirect-to=/me"), `${size.width}px ${builder}: no account link`);
			if (phone && expected && (await reference.$(".wk-header__burger"))) {
				// Keyboard: Tab from the burger visits every link of the open menu, in order.
				await reference.focus(".wk-header__burger");
				const visited = [];
				for (let n = 0; n < expected.length; n++) {
					await reference.keyboard.press("Tab");
					visited.push(await reference.evaluate(() => document.activeElement.getAttribute("href")));
				}
				check(JSON.stringify(visited) === JSON.stringify(expected.map(([href]) => href)), `${size.width}px ${builder}: Tab visits ${JSON.stringify(visited)}, the menu is ${JSON.stringify(expected.map(([href]) => href))}`);
			}
			if (outDir) await reference.screenshot({ path: `${outDir}/header-${lang}-${size.width}.png` });
			await reference.close();
			refs[lang] = expected;
		}
		for (const { lang, stock } of SETS) {
			for (const path of stock) {
				const page = await open(size, lang, path);
				if (phone) await openMenu(page, `${size.width}px ${path} (${lang})`);
				const got = await menuLinks(page);
				// The stock page shows the language Frappe picked for the request (Frappe 16 ignores Accept-Language for a guest, and
				// `<html lang>` is the site language on 15): it must equal the Builder menu of one of the two languages, link for link.
				// The login page itself has no account link (Frappe's `hide_login`); everything else must match.
				const wanted = Object.values(refs).map((menu) => withoutSwitch(path === "/login" ? menu.filter(([href]) => href !== "/login?redirect-to=/me") : menu));
				check(wanted.some((menu) => JSON.stringify(menu) === JSON.stringify(withoutSwitch(got))), `${size.width}px ${path} (${lang}): menu ${JSON.stringify(got)} matches no Builder menu ${JSON.stringify(wanted)}`);
				const button = got.filter(isSwitch);
				check(button.length === 1 && /^\?_lang=(uk|en)$/.test(button[0][0]), `${size.width}px ${path} (${lang}): the language button leads to ${JSON.stringify(button)}, not to ?_lang= of the same page`);
				if (outDir) await page.screenshot({ path: `${outDir}/header-${lang}-${path.replace(/[^a-z]+/g, "_")}-${size.width}.png` });
				await page.close();
			}
		}
	}
} finally {
	await browser.close();
}
if (problems.length) {
	console.log(`${problems.length} problems`);
	for (const p of problems.slice(0, 40)) console.log(" - " + p);
	process.exit(1);
}
console.log("header ok");
