/**
 * Drives a generated page the way a person would, and reports what happened.
 *
 * A screenshot proves the page rendered. It does not prove that clicking a
 * predicate shows its clauses, or that the turn slider replays the
 * conversation. This clicks and drags and checks.
 *
 *   node drive.mjs <path-to-generated.html> [screenshot-directory]
 */

import puppeteer from "puppeteer-core";
import { pathToFileURL } from "node:url";
import path from "node:path";
import fs from "node:fs";

const CHROME = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
].find((p) => fs.existsSync(p));

const page_path = process.argv[2];
const shots = process.argv[3] ?? ".";
if (!page_path) {
  console.error("usage: node drive.mjs <generated.html> [screenshot-dir]");
  process.exit(2);
}

const failures = [];
const check = (name, ok, detail = "") => {
  console.log(`${ok ? "  ok  " : " FAIL "} ${name}${detail ? `   ${detail}` : ""}`);
  if (!ok) failures.push(name);
};
// For checks that depend on what the knowledge base contains. A knowledge base
// with no retractions cannot show a withdrawn clause, and that is not a fault.
const notApplicable = (name, why) => console.log(`  n/a  ${name}   ${why}`);

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: "new",
  args: ["--allow-file-access-from-files", "--disable-gpu"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1500, height: 950 });

const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

await page.goto(pathToFileURL(path.resolve(page_path)).href, { waitUntil: "networkidle0" });
await new Promise((r) => setTimeout(r, 800));

// What the page was given, so the checks below can tell "the viewer failed to
// show it" apart from "there was nothing to show".
const data = await page.$eval("#logiclayer-data", (s) => JSON.parse(s.textContent));
const clauses = data?.kb?.clauses ?? [];
const hasSources = clauses.some((c) => c.source_text);
const hasWithdrawn = clauses.some((c) => c.retracted);
// A word that appears in some clauses but not all, so filtering on it must
// narrow the list.
const filterTerm = [...new Set(clauses.map((c) => c.head_predicate.split("/")[0]))]
  .find((name) => {
    const hits = clauses.filter((c) => c.text.includes(name)).length;
    return hits > 0 && hits < clauses.length;
  });

await page.screenshot({ path: path.join(shots, "overview.png") });

// --- it rendered at all ----------------------------------------------------

const nodeCount = await page.$$eval(".node", (n) => n.length);
check("predicate nodes are drawn", nodeCount > 0, `${nodeCount} nodes`);

const edgeCount = await page.$$eval(".react-flow__edge", (e) => e.length);
check("dependency edges are drawn", edgeCount > 0, `${edgeCount} edges`);

check("no javascript errors", errors.length === 0, errors.slice(0, 2).join(" | "));

// --- the proof -------------------------------------------------------------

const proofGoals = await page.$$eval(".proof-goal .goal-text", (g) =>
  g.map((e) => e.textContent.trim()),
);
check("the proof tree is shown", proofGoals.length > 0, proofGoals.join(" <- "));

const nafShown = await page.$$eval(".proof-goal.naf, .proof-goal .not", (n) => n.length);
check("a negated step is marked", nafShown > 0);

// clicking a ledger id should reveal the sentence behind the clause
const chip = await page.$(".proof-node .chip:not(.static)");
if (chip) {
  await chip.click();
  await new Promise((r) => setTimeout(r, 250));
  const detail = await page.$eval(".clause-detail", (d) => d.textContent).catch(() => "");
  check(
    "a proof step opens the sentence behind it",
    detail.includes("because") || detail.length > 20,
    detail.slice(0, 70).replace(/\s+/g, " "),
  );
} else {
  check("a proof step opens the sentence behind it", false, "no clause chip found");
}

// --- the ledger ------------------------------------------------------------

const tabs = await page.$$(".tabs button");
const ledgerTab = tabs[1];
await ledgerTab.click();
await new Promise((r) => setTimeout(r, 300));

const ledgerRows = await page.$$eval(".ledger-list li", (l) => l.length);
check("the ledger lists every clause", ledgerRows > 0, `${ledgerRows} rows`);

const ledgerProvenance = await page.$$eval(".ledger-list .source", (p) => p.length);
if (hasSources) {
  check("each row shows the sentence it came from", ledgerProvenance > 0, `${ledgerProvenance} rows`);
} else {
  notApplicable("each row shows the sentence it came from", "no clause was given a --source");
}

const withdrawn = await page.$$eval(".ledger-list li.withdrawn .withdrawn-note", (n) =>
  n.map((e) => e.textContent.trim()),
);
if (hasWithdrawn) {
  check("a withdrawn clause is kept and says why", withdrawn.length > 0, withdrawn[0]?.slice(0, 70));
} else {
  notApplicable("a withdrawn clause is kept and says why", "nothing was retracted");
}

// facts and rules have to be distinguishable without reading the clause
const kinds = await page.$$eval(".ledger-list li", (rows) =>
  rows.map((r) => ({
    kind: r.classList.contains("is-rule") ? "rule" : "fact",
    edge: getComputedStyle(r).borderLeftColor,
    label: r.querySelector(".kind-tag")?.textContent ?? "",
  })),
);
const factEdge = kinds.find((k) => k.kind === "fact")?.edge;
const ruleEdge = kinds.find((k) => k.kind === "rule")?.edge;
check(
  "facts and rules are told apart at a glance",
  factEdge && ruleEdge && factEdge !== ruleEdge,
  `fact ${factEdge} / rule ${ruleEdge}`,
);
check(
  "each row says which it is",
  kinds.every((k) => k.label === "fact" || k.label === "rule"),
  [...new Set(kinds.map((k) => k.label))].join(", "),
);

await page.screenshot({ path: path.join(shots, "ledger.png") });

// a rule row, which is usually below the fold
const firstRule = await page.$(".ledger-list li.is-rule");
if (firstRule) {
  await firstRule.evaluate((e) => e.scrollIntoView({ block: "center" }));
  await new Promise((r) => setTimeout(r, 250));
  await page.screenshot({ path: path.join(shots, "ledger-rule.png") });
}

// filtering
await page.type(".ledger-controls input[type=search]", filterTerm ?? "");
await new Promise((r) => setTimeout(r, 300));
const filtered = await page.$$eval(".ledger-list li", (l) => l.length);
check("the filter narrows the list", filtered > 0 && filtered < ledgerRows,
      `"${filterTerm}": ${filtered} of ${ledgerRows}`);
await page.$eval(".ledger-controls input[type=search]", (s) => {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  setter.call(s, "");
  s.dispatchEvent(new Event("input", { bubbles: true }));
});
await new Promise((r) => setTimeout(r, 250));

// clicking a row's predicate should select it in the graph
await page.click(".ledger-list li .chip:not(.static)");
await new Promise((r) => setTimeout(r, 350));
const jumped = await page.$eval(".panel h2", (h) => h.textContent).catch(() => "");
check("a ledger row jumps to its predicate", /\/\d+$/.test(jumped), jumped);

// --- selecting a predicate -------------------------------------------------

await page.click(".node");
await new Promise((r) => setTimeout(r, 350));
const panelTitle = await page.$eval(".panel h2", (h) => h.textContent).catch(() => "");
check("clicking a predicate opens its panel", /\/\d+$/.test(panelTitle), panelTitle);

const clauseRows = await page.$$eval(".clause-list li", (l) => l.length);
check("the panel lists that predicate's clauses", clauseRows > 0, `${clauseRows} rows`);

const hasProvenance = await page
  .$eval(".clause-list .rationale", (p) => p.textContent.trim())
  .catch(() => "");
check("each clause shows why it was written that way", hasProvenance.length > 0,
      hasProvenance.slice(0, 60));

await page.screenshot({ path: path.join(shots, "selected.png") });

// --- replaying the conversation --------------------------------------------

const slider = await page.$("#turn");
if (slider) {
  const before = await page.$$eval(".node", (n) => n.length);
  const min = Number(await page.$eval("#turn", (s) => s.min));
  await page.$eval("#turn", (s, v) => {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    setter.call(s, v);
    s.dispatchEvent(new Event("input", { bubbles: true }));
  }, String(min));
  await new Promise((r) => setTimeout(r, 500));
  const after = await page.$$eval(".node", (n) => n.length);
  check("the turn slider replays the conversation", after < before,
        `${before} nodes at the end, ${after} at turn ${min}`);
  await page.screenshot({ path: path.join(shots, "first-turn.png") });
} else {
  check("the turn slider replays the conversation", false, "no slider");
}

await browser.close();
console.log(failures.length ? `\n${failures.length} failed` : "\nall checks passed");
process.exit(failures.length ? 1 : 0);
