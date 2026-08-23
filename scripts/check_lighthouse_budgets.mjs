#!/usr/bin/env node

import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const budgetPath = path.resolve(process.env.PERFORMANCE_BUDGETS || "config/performance-budgets.json");
const lighthousePath = path.resolve(process.env.LIGHTHOUSE_REPORT || "performance-results/current-lighthouse.json");
const outputDir = path.resolve(process.env.PERFORMANCE_OUTPUT || "performance-results");
const budgets = JSON.parse(await readFile(budgetPath, "utf8")).lighthouse;
const lhr = JSON.parse(await readFile(lighthousePath, "utf8"));

function audit(id) {
  return lhr.audits?.[id]?.numericValue ?? null;
}

const current = {
  performance_score: Math.round((lhr.categories?.performance?.score || 0) * 100),
  largest_contentful_paint_ms: audit("largest-contentful-paint"),
  cumulative_layout_shift: audit("cumulative-layout-shift"),
  total_blocking_time_ms: audit("total-blocking-time"),
};
const checks = [
  ["performance_score", current.performance_score, budgets.performance_score_min, ">="],
  ["largest_contentful_paint_ms", current.largest_contentful_paint_ms, budgets.largest_contentful_paint_ms_max, "<="],
  ["cumulative_layout_shift", current.cumulative_layout_shift, budgets.cumulative_layout_shift_max, "<="],
  ["total_blocking_time_ms", current.total_blocking_time_ms, budgets.total_blocking_time_ms_max, "<="],
];
const failures = checks.filter(([, value, limit, operator]) => value === null || (operator === ">=" ? value < limit : value > limit));
const report = {
  budgets,
  current,
  failures: failures.map(([name, value, limit, operator]) => ({ name, value, limit, operator })),
  status: failures.length ? "fail" : "pass",
};
await mkdir(outputDir, { recursive: true });
await writeFile(path.join(outputDir, "lighthouse-budget.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8");

const lines = [
  "# Lighthouse performance budgets",
  "",
  `Status: **${report.status.toUpperCase()}**`,
  "",
  "| Metric | Current | Budget |",
  "| --- | ---: | ---: |",
  `| Performance score | ${current.performance_score} | ≥ ${budgets.performance_score_min} |`,
  `| LCP | ${Math.round(current.largest_contentful_paint_ms ?? 0)} ms | ≤ ${budgets.largest_contentful_paint_ms_max} ms |`,
  `| CLS | ${current.cumulative_layout_shift ?? "n/a"} | ≤ ${budgets.cumulative_layout_shift_max} |`,
  `| TBT | ${Math.round(current.total_blocking_time_ms ?? 0)} ms | ≤ ${budgets.total_blocking_time_ms_max} ms |`,
];
await writeFile(path.join(outputDir, "lighthouse-budget.md"), `${lines.join("\n")}\n`, "utf8");
console.log(lines.join("\n"));
if (failures.length) process.exitCode = 1;
