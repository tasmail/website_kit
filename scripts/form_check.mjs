// Drive the contact form of a running site in a real browser with a stand-in for the guard client (no network to Google).
//
//   CHROME=/usr/bin/google-chrome node scripts/form_check.mjs http://test.localhost:8000
//
// The site must show the form (a recipient and reCAPTCHA keys set, the guard app installed: `probe.contact_demo`).
// It checks: nothing is sent before 3 seconds, nothing when the trap field is filled, nothing without the guard client, and
// that a normal submission calls `FrappeGuard.request` once with the action `contact` and the three stock fields.
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
const [base = "http://test.localhost:8000"] = process.argv.slice(2);
const results = [];
const check = (name, ok, detail = "") => {
	results.push(ok);
	console.log(`${ok ? "ok  " : "FAIL"} ${name}${ok ? "" : " " + detail}`);
};

const browser = await puppeteer.launch({
	executablePath: process.env.CHROME || "/usr/bin/google-chrome",
	headless: false,
	args: ["--headless=new", "--no-sandbox", "--disable-gpu", ...(process.env.CHROME_ARGS || "").split("|").filter(Boolean)],
});

async function open(path, stub) {
	const page = await browser.newPage();
	if (stub) {
		await page.evaluateOnNewDocument(() => {
			window.__calls = [];
			window.FrappeGuard = {
				request(url, options) {
					window.__calls.push({ url, action: options.action, method: options.method, body: options.body.toString() });
					return Promise.resolve(new Response("{}", { status: 200 }));
				},
			};
		});
	} else {
		// the guard client is blocked: the form must refuse to send
		await page.setRequestInterception(true);
		page.on("request", (request) => (request.url().includes("guard.js") ? request.abort() : request.continue()));
	}
	await page.goto(new URL(path, base).href, { waitUntil: "networkidle0" });
	return page;
}

async function fill(page, { trap = "" } = {}) {
	await page.type("#wk-contact-form [name=sender_name]", "Ірина");
	await page.type("#wk-contact-form [name=sender]", "visitor@example.com");
	await page.type("#wk-contact-form [name=message]", "Добрий день");
	if (trap) await page.evaluate((value) => (document.querySelector("#wk-contact-form [name=website]").value = value), trap);
}
const status = (page) => page.$eval("[data-wk-status]", (el) => ({ text: el.textContent, hidden: el.hidden }));
const calls = (page) => page.evaluate(() => window.__calls || []);

try {
	let page = await open("/contact", true);
	check("the form is on the page", Boolean(await page.$("#wk-contact-form")));
	await fill(page);
	await page.click("#wk-contact-form button[type=submit]");
	check("nothing is sent before 3 seconds", (await calls(page)).length === 0);
	check("an error is shown for it", (await status(page)).hidden === false);
	await new Promise((resolve) => setTimeout(resolve, 3200));
	await page.click("#wk-contact-form button[type=submit]");
	await page.waitForFunction(() => window.__calls.length === 1, { timeout: 5000 });
	const [call] = await calls(page);
	const body = new URLSearchParams(call.body);
	check("one guarded request", call.url === "/api/method/frappe.www.contact.send_message" && call.action === "contact" && call.method === "POST");
	check("the stock fields", body.get("sender") === "visitor@example.com" && body.get("message") === "Ірина\n\nДобрий день" && Boolean(body.get("subject")));
	check("the trap field and the script fields are not sent", !body.has("website") && !body.has("guard_token"));
	await page.waitForFunction(() => document.querySelector("[data-wk-status]").textContent.includes("Дякуємо"), { timeout: 5000 });
	check("the success text is shown and the form is reset", (await page.$eval("#wk-contact-form [name=message]", (el) => el.value)) === "");
	await page.close();

	page = await open("/en/contact", true);
	await new Promise((resolve) => setTimeout(resolve, 3200));
	await fill(page, { trap: "http://spam.example" });
	await page.click("#wk-contact-form button[type=submit]");
	check("nothing is sent when the trap field is filled", (await calls(page)).length === 0 && (await status(page)).hidden === false);
	await page.close();

	page = await open("/contact", false);
	await new Promise((resolve) => setTimeout(resolve, 3200));
	await fill(page);
	await page.click("#wk-contact-form button[type=submit]");
	check("nothing is sent without the guard client", (await status(page)).hidden === false);
	await page.close();
} finally {
	await browser.close();
}
process.exit(results.every(Boolean) ? 0 : 1);
