// Run axe-core on the standard pages of a running site; exit 1 on a serious or critical violation.
//
//   npm install --no-save puppeteer-core@23.11.1 axe-core@4.10.2
//   CHROME=/usr/bin/google-chrome node scripts/axe_check.mjs http://test.localhost:8000
//
// Chrome resolves `*.localhost` to the loopback address itself. Extra browser flags go in CHROME_ARGS (separated by |).
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
const axeSource = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");

const [base = "http://test.localhost:8000"] = process.argv.slice(2);
const pages = ["/", "/about", "/contact", "/privacy", "/en", "/en/about", "/en/contact", "/en/privacy"];
const failing = new Set(["serious", "critical"]);

const browser = await puppeteer.launch({
	executablePath: process.env.CHROME || "/usr/bin/google-chrome",
	// `--headless=new` by flag: current Chrome has no other headless mode.
	headless: false,
	args: ["--headless=new", "--no-sandbox", "--disable-gpu", ...(process.env.CHROME_ARGS || "").split("|").filter(Boolean)],
});
let failed = false;
try {
	for (const sizes of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
		for (const path of pages) {
			const page = await browser.newPage();
			await page.setViewport(sizes);
			await page.goto(new URL(path, base).href, { waitUntil: "networkidle0" });
			await page.evaluate(axeSource);
			const result = await page.evaluate(async () => {
				const run = await window.axe.run(document, { resultTypes: ["violations"] });
				return run.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help }));
			});
			const bad = result.filter((v) => failing.has(v.impact));
			failed = failed || bad.length > 0;
			console.log(`${sizes.width}px ${path}: ${result.length} violations, ${bad.length} serious or critical`);
			for (const v of result) console.log(`   ${v.impact} ${v.id} (${v.nodes}): ${v.help}`);
			await page.close();
		}
	}
} finally {
	await browser.close();
}
process.exit(failed ? 1 : 0);
