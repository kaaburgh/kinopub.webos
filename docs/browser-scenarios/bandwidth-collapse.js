#!/usr/bin/env node
'use strict';

const os = require('os');
const path = require('path');
const readline = require('readline');

const APP_URL = process.env.KINO_BROWSER_URL || 'http://localhost:3000';
const PROFILE_DIR =
  process.env.KINO_BROWSER_PROFILE_DIR || path.join(os.tmpdir(), 'kinopub-webos-playwright-profile');
const SLOW_KBPS = Number(process.env.KINO_BROWSER_SLOW_KBPS || 900);
const SLOW_LATENCY_MS = Number(process.env.KINO_BROWSER_SLOW_LATENCY_MS || 180);
const SLOW_WINDOW_MS = Number(process.env.KINO_BROWSER_SLOW_WINDOW_MS || 60000);
const PROGRESS_SECONDS = Number(process.env.KINO_BROWSER_PROGRESS_SECONDS || 2);
const POLL_MS = 1000;

function fail(message) {
  console.error(message);
  process.exitCode = 1;
}

function waitForEnter(message) {
  return new Promise((resolve) => {
    const input = readline.createInterface({ input: process.stdin, output: process.stdout });
    input.question(`${message}\nPress Enter to continue.\n`, () => {
      input.close();
      resolve();
    });
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function loadPlaywright() {
  const moduleName = process.env.KINO_PLAYWRIGHT_MODULE || 'playwright';

  try {
    return require(moduleName);
  } catch (_) {
    throw new Error('PLAYWRIGHT_MODULE_UNAVAILABLE');
  }
}

function readNumber(text, label) {
  const match = text.match(new RegExp(`(?:^|\\n)${label}:\\s*(-?\\d+(?:\\.\\d+)?)`, 'm'));
  return match ? Number(match[1]) : undefined;
}

function readText(text, label) {
  const match = text.match(new RegExp(`(?:^|\\n)${label}:\\s*([^\\n]+)`, 'm'));
  return match ? match[1].trim() : undefined;
}

async function readDiagnostics(page) {
  const text = await page.locator('body').innerText();
  const currentLevel = readNumber(text, 'currentLevel');
  const levels = readNumber(text, 'levels');
  const bandwidthEstimate = readNumber(text, 'bandwidth estimate');
  const mode = readText(text, 'mode');

  return { currentLevel, levels, bandwidthEstimate, mode };
}

async function readVideoTime(page) {
  return page.locator('video').evaluate((video) => video.currentTime);
}

async function main() {
  if (!Number.isFinite(SLOW_KBPS) || SLOW_KBPS <= 0) {
    fail('KINO_BROWSER_SLOW_KBPS must be a positive number.');
    return;
  }

  if (!Number.isFinite(SLOW_LATENCY_MS) || SLOW_LATENCY_MS < 0) {
    fail('KINO_BROWSER_SLOW_LATENCY_MS must be zero or greater.');
    return;
  }

  let appOrigin;

  try {
    appOrigin = new URL(APP_URL).origin;
  } catch (_) {
    fail('KINO_BROWSER_URL must be a valid local or preview URL.');
    return;
  }

  const { chromium } = await loadPlaywright();
  const context = await chromium.launchPersistentContext(PROFILE_DIR, { headless: false });
  const pages = context.pages();
  const page = pages[0] || (await context.newPage());
  const cdp = await context.newCDPSession(page);

  await cdp.send('Network.enable');

  console.log(`Opening ${appOrigin}. Browser Sentry is expected to stay disabled by A18's runtime gate.`);
  await page.goto(APP_URL, { waitUntil: 'domcontentloaded' });

  await waitForEnter(
    'Sign in if needed, start a genuine multi-level HLS stream in Auto mode, open the playback diagnostics overlay, and wait until playback is visibly progressing.',
  );

  const baseline = await readDiagnostics(page);

  if (baseline.mode !== 'auto') {
    fail(`Diagnostics must show mode: auto; observed ${baseline.mode || 'no mode field'}.`);
    await context.close();
    return;
  }

  if (!Number.isFinite(baseline.levels) || baseline.levels < 2) {
    fail('Diagnostics must show at least two HLS levels.');
    await context.close();
    return;
  }

  if (!Number.isFinite(baseline.currentLevel) || baseline.currentLevel <= 0) {
    fail('Baseline currentLevel must be above level 0 so a downward ABR move can be demonstrated.');
    await context.close();
    return;
  }

  const baselineTime = await readVideoTime(page);
  const baselineLevel = baseline.currentLevel;
  console.log(
    `Baseline accepted: mode=auto, levels=${baseline.levels}, currentLevel=${baselineLevel}` +
      (Number.isFinite(baseline.bandwidthEstimate)
        ? `, bandwidthEstimate=${Math.round(baseline.bandwidthEstimate / 1000)} kbps.`
        : '.'),
  );

  const bytesPerSecond = (SLOW_KBPS * 1000) / 8;
  await cdp.send('Network.emulateNetworkConditions', {
    offline: false,
    latency: SLOW_LATENCY_MS,
    downloadThroughput: bytesPerSecond,
    uploadThroughput: bytesPerSecond,
  });

  console.log(
    `Applied Chromium network shaping: ${SLOW_KBPS} kbps, ${SLOW_LATENCY_MS} ms latency for up to ${SLOW_WINDOW_MS} ms.`,
  );

  let lowestLevel = baselineLevel;
  let finalTime = baselineTime;
  const deadline = Date.now() + SLOW_WINDOW_MS;

  try {
    while (Date.now() < deadline) {
      await sleep(POLL_MS);
      const snapshot = await readDiagnostics(page);
      finalTime = await readVideoTime(page);

      if (Number.isFinite(snapshot.currentLevel)) {
        lowestLevel = Math.min(lowestLevel, snapshot.currentLevel);
      }

      if (lowestLevel < baselineLevel && finalTime - baselineTime >= PROGRESS_SECONDS) {
        break;
      }
    }
  } finally {
    await cdp.send('Network.emulateNetworkConditions', {
      offline: false,
      latency: 0,
      downloadThroughput: -1,
      uploadThroughput: -1,
    });
  }

  const progressed = finalTime - baselineTime;

  if (lowestLevel >= baselineLevel) {
    fail(`No downward ABR move was observed; baseline=${baselineLevel}, lowest=${lowestLevel}.`);
  } else if (progressed < PROGRESS_SECONDS) {
    fail(
      `A lower level was observed, but playback did not progress enough to count as continued playback (${progressed.toFixed(
        1,
      )} s).`,
    );
  } else {
    console.log(
      `Observed downward ABR while playback continued: currentLevel ${baselineLevel} -> ${lowestLevel}; video advanced ${progressed.toFixed(
        1,
      )} s.`,
    );
  }

  await waitForEnter(
    'Network shaping is off. Inspect the diagnostics locally if useful; this browser result does not establish TV bandwidth thresholds or LG behaviour.',
  );
  await context.close();
}

main().catch((error) => {
  if (error && error.message === 'PLAYWRIGHT_MODULE_UNAVAILABLE') {
    fail(
      'Playwright could not be loaded. Run this procedure where the Playwright module and Chromium are available or set KINO_PLAYWRIGHT_MODULE.',
    );
    return;
  }

  fail(`Browser scenario failed before completion (${(error && error.name) || 'unknown error'}).`);
});
