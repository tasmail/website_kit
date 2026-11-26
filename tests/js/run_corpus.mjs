// Runs the client twin of the CSS validator over the shared corpus: the verdicts must equal the stored ones, which the
// Python validator is tested against too (tests/test_css_validator.py). Usage: node tests/js/run_corpus.mjs
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const require = createRequire(import.meta.url);
const twin = require(join(root, "website_kit/public/js/wk_css_validator.js"));
const rules = JSON.parse(readFileSync(join(root, "website_kit/public/js/wk_css_rules.json"), "utf8"));
const corpus = JSON.parse(readFileSync(join(root, "tests/css_corpus.json"), "utf8"));
const validator = twin.createValidator(rules);
const triples = (list) => list.map((m) => [m.line, m.column, m.code]);

let failed = 0;
for (const entry of corpus) {
	const result = validator.validate(entry.css);
	const gotErrors = JSON.stringify(triples(result.errors));
	const gotWarnings = JSON.stringify(triples(result.warnings));
	if (gotErrors !== JSON.stringify(entry.errors) || gotWarnings !== JSON.stringify(entry.warnings)) {
		failed += 1;
		console.log(`MISMATCH ${entry.id}\n  expected ${JSON.stringify(entry.errors)} ${JSON.stringify(entry.warnings)}\n  got      ${gotErrors} ${gotWarnings}`);
	}
	if (result.ok !== (entry.errors.length === 0)) {
		failed += 1;
		console.log(`MISMATCH ok flag ${entry.id}`);
	}
}
console.log(`${corpus.length} corpus entries, ${failed} mismatches`);
process.exit(failed ? 1 : 0);
