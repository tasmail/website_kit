// Validates a JSON list of CSS strings with the client twin and prints the verdicts, for the fuzz parity test.
// Usage: node tests/js/run_batch.mjs <inputs.json>
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const require = createRequire(import.meta.url);
const twin = require(join(root, "website_kit/public/js/wk_css_validator.js"));
const rules = JSON.parse(readFileSync(join(root, "website_kit/public/js/wk_css_rules.json"), "utf8"));
const validator = twin.createValidator(rules);
const inputs = JSON.parse(readFileSync(process.argv[2], "utf8"));
const triples = (list) => list.map((m) => [m.line, m.column, m.code]);
console.log(JSON.stringify(inputs.map((css) => {
	const result = validator.validate(css);
	return [triples(result.errors), triples(result.warnings)];
})));
