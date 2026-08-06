#!/usr/bin/env node

import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const root = process.cwd();
const currentDist = path.resolve(process.env.CURRENT_DIST || path.join(root, "dist"));
const baselineDist = process.env.BASELINE_DIST ? path.resolve(process.env.BASELINE_DIST) : null;
const outputDir = path.resolve(process.env.PERFORMANCE_OUTPUT || path.join(root, "performance-results"));
const lighthouseBinary = path.resolve(
  root,
  "node_modules",
  ".bin",
  process.platform === "win32" ? "lighthouse.cmd" : "lighthouse",
);

function spawnProcess(command, args, options = {}) {
  return spawn(command, args, {
    stdio: options.stdio || "inherit",
    env: { ...process.env, ...options.env },
    cwd: options.cwd || root,
  });
}

async function waitForServer(url, attempts = 80) {
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (response.ok) return;
      lastError = new Error(`Server returned HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw lastError || new Error(`Server did not become ready: ${url}`);
}

async function stopProcess(child) {
  if (!child || child.killed) return;
  child.kill("SIGTERM");
  await Promise.race([
    new Promise((resolve) => child.once("exit", resolve)),
    new Promise((resolve) => setTimeout(resolve, 2000)),
  ]);
  if (!child.killed) child.kill("SIGKILL");
}

async function runCommand(command, args) {
  await new Promise((resolve, reject) => {
    const child = spawnProcess(command, args);
    child.once("error", reject);
    child.once("exit", (code, signal) => {
      if (code === 0) resolve();
      else reject(new Error(`${command} exited with ${code ?? signal}`));
    });
  });
}

function auditValue(lhr, id) {
  const audit = lhr.audits?.[id];
  return audit?.numericValue ?? null;
}

function summarize(lhr) {
  const longTasks = lhr.audits?.["long-tasks"]?.details?.items || [];
  return {
    lighthouse_version: lhr.lighthouseVersion,
    fetch_time: lhr.fetchTime,
    performance_score: Math.round((lhr.categories?.performance?.score || 0) * 100),
    first_contentful_paint_ms: auditValue(lhr, "first-contentful-paint"),
    largest_contentful_paint_ms: auditValue(lhr, "largest-contentful-paint"),
    speed_index_ms: auditValue(lhr, "speed-index"),
    total_blocking_time_ms: auditValue(lhr, "total-blocking-time"),
    max_potential_fid_ms: auditValue(lhr, "max-potential-fid"),
    main_thread_work_ms: auditValue(lhr, "mainthread-work-breakdown"),
    javascript_execution_ms: auditValue(lhr, "bootup-time"),
    long_task_count: longTasks.length,
    longest_tasks: longTasks
      .map((item) => ({ url: item.url || null, duration_ms: item.duration || null, start_time_ms: item.startTime || null }))
      .sort((left, right) => (right.duration_ms || 0) - (left.duration_ms || 0))
      .slice(0, 10),
  };
}

async function auditSite(label, distDirectory, port) {
  const server = spawnProcess(
    "python",
    ["-m", "http.server", String(port), "--bind", "127.0.0.1", "--directory", distDirectory],
    { stdio: "ignore" },
  );
  const url = `http://127.0.0.1:${port}/`;
  const outputPath = path.join(outputDir, `${label}-lighthouse.json`);

  try {
    await waitForServer(url);
    await runCommand(lighthouseBinary, [
      url,
      "--output=json",
      `--output-path=${outputPath}`,
      `--chrome-path=${chromium.executablePath()}`,
      "--chrome-flags=--headless=new --no-sandbox --disable-gpu",
      "--only-categories=performance",
      "--form-factor=mobile",
      "--throttling-method=simulate",
      "--screenEmulation.mobile=true",
      "--screenEmulation.width=412",
      "--screenEmulation.height=823",
      "--screenEmulation.deviceScaleFactor=1.75",
      "--max-wait-for-load=45000",
      "--quiet",
    ]);
    const lhr = JSON.parse(await readFile(outputPath, "utf8"));
    return summarize(lhr);
  } finally {
    await stopProcess(server);
  }
}

function formatMetric(value, suffix = " ms") {
  return value === null || value === undefined ? "n/a" : `${Math.round(value)}${suffix}`;
}

await mkdir(outputDir, { recursive: true });

const baseline = baselineDist ? await auditSite("baseline", baselineDist, 4174) : null;
const current = await auditSite("current", currentDist, 4175);
const tbtReduction = baseline?.total_blocking_time_ms > 0
  ? ((baseline.total_blocking_time_ms - current.total_blocking_time_ms) / baseline.total_blocking_time_ms) * 100
  : null;
const result = {
  profile: {
    lighthouse_version: "13.4.0",
    form_factor: "mobile",
    throttling_method: "simulate",
    screen: { width: 412, height: 823, device_scale_factor: 1.75 },
    chrome: chromium.executablePath(),
  },
  baseline,
  current,
  comparison: {
    total_blocking_time_reduction_percent: tbtReduction,
    performance_score_change: baseline ? current.performance_score - baseline.performance_score : null,
    main_thread_work_change_ms: baseline
      ? current.main_thread_work_ms - baseline.main_thread_work_ms
      : null,
  },
};

await writeFile(path.join(outputDir, "comparison.json"), `${JSON.stringify(result, null, 2)}\n`, "utf8");

const lines = [
  "# Lighthouse mobile performance comparison",
  "",
  "| Metric | Baseline | Current |",
  "| --- | ---: | ---: |",
  `| Performance score | ${baseline?.performance_score ?? "n/a"} | ${current.performance_score} |`,
  `| Total Blocking Time | ${formatMetric(baseline?.total_blocking_time_ms)} | ${formatMetric(current.total_blocking_time_ms)} |`,
  `| Main-thread work | ${formatMetric(baseline?.main_thread_work_ms)} | ${formatMetric(current.main_thread_work_ms)} |`,
  `| JavaScript execution | ${formatMetric(baseline?.javascript_execution_ms)} | ${formatMetric(current.javascript_execution_ms)} |`,
  `| Long tasks | ${baseline?.long_task_count ?? "n/a"} | ${current.long_task_count} |`,
  `| FCP | ${formatMetric(baseline?.first_contentful_paint_ms)} | ${formatMetric(current.first_contentful_paint_ms)} |`,
  `| LCP | ${formatMetric(baseline?.largest_contentful_paint_ms)} | ${formatMetric(current.largest_contentful_paint_ms)} |`,
  "",
  tbtReduction === null
    ? "No baseline was supplied."
    : `Total Blocking Time changed by ${tbtReduction.toFixed(1)}%.`,
];
await writeFile(path.join(outputDir, "comparison.md"), `${lines.join("\n")}\n`, "utf8");

console.log(lines.join("\n"));

if (baseline && current.total_blocking_time_ms > baseline.total_blocking_time_ms) {
  throw new Error(
    `Total Blocking Time regressed from ${baseline.total_blocking_time_ms} ms to ${current.total_blocking_time_ms} ms`,
  );
}
