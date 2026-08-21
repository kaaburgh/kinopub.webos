#!/usr/bin/env node
'use strict';

const os = require('os');
const path = require('path');
const readline = require('readline');

const APP_URL = process.env.KINO_BROWSER_URL || 'http://localhost:3000';
const CDN_HOST = (process.env.KINO_BROWSER_CDN_HOST || '').trim().toLowerCase();
const PATH_HINT = (process.env.KINO_BROWSER_FRAGMENT_PATH_HINT || '').trim();
const TIMEOUT_MS = Number(process.env.KINO_BROWSER_TIMEOUT_MS || 120000);
const PROFILE_DIR =
  process.env.KINO_BROWSER_PROFILE_DIR || path.join(os.tmpdir(), 'kinopub-webos-playwright-profile');

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

function requestMatches(request) {
  let parsed;

  try {
    parsed = new URL(request.url());
  } catch (_) {
    return false;
  }

  if (parsed.hostname.toLowerCase() !== CDN_HOST) {
    return false;
  }

  if (parsed.pathname.toLowerCase().endsWith('.m3u8')) {
    return false;
  }

  if (!parsed.pathname.includes(PATH_HINT)) {
    return false;
  }

  return ['fetch', 'media', 'xhr'].includes(request.resourceType());
}

async function loadPlaywright() {
  const moduleName = process.env.KINO_PLAYWRIGHT_MODULE || 'playwright';

  try {
    return require(moduleName);
  } catch (_) {
    throw new Error('PLAYWRIGHT_MODULE_UNAVAILABLE');
  }
}

async function main() {
  if (!CDN_HOST) {
    fail('KINO_BROWSER_CDN_HOST is required. Use only the CDN hostname, never a full media URL.');
    return;
  }

  if (!PATH_HINT) {
    fail(
      'KINO_BROWSER_FRAGMENT_PATH_HINT is required so the scenario fails closed instead of blocking unrelated CDN traffic.',
    );
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

  let armed = false;
  let heldAttempts = 0;
  let firstHeldAt = 0;
  const heldRoutes = new Set();

  await page.route('**/*', async (route) => {
    const request = route.request();

    if (!armed || !requestMatches(request)) {
      await route.continue();
      return;
    }

    heldAttempts += 1;
    if (!firstHeldAt) {
      firstHeldAt = Date.now();
      console.log(`Holding media-fragment requests on ${CDN_HOST}; request URLs will not be printed.`);
    }
    console.log(`Holding matching media-fragment request ${heldAttempts}.`);

    await new Promise((resolve) => {
      heldRoutes.add({ route, resolve });
    });
  });

  console.log(`Opening ${appOrigin}. Browser Sentry is expected to stay disabled by A18's runtime gate.`);
  await page.goto(APP_URL, { waitUntil: 'domcontentloaded' });

  await waitForEnter(
    'Sign in if needed, start normal HLS playback, open the in-app diagnostics overlay, and wait until video is visibly progressing.',
  );

  armed = true;
  console.log(
    'Scenario armed. Matching media-fragment requests will remain pending at the browser boundary instead of being deliberately failed.',
  );

  try {
    await page.waitForSelector('text=Повторить', { state: 'visible', timeout: TIMEOUT_MS });
  } catch (_) {
    fail(`Terminal failure notice was not observed within ${TIMEOUT_MS} ms; held requests: ${heldAttempts}.`);
  }

  if (process.exitCode !== 1) {
    const elapsed = firstHeldAt ? Date.now() - firstHeldAt : 0;
    console.log(
      `Observed the terminal failure notice after holding ${heldAttempts} matching request(s)` +
        (elapsed ? ` for approximately ${elapsed} ms.` : '.'),
    );
    console.log(
      'Count this run as non-fatal-stall evidence only if diagnostics show watchdog restart/reload progression and no fatal recovery before the notice.',
    );
  }

  await waitForEnter(
    'Inspect the diagnostics before cleanup. If fatal recovery engaged before the notice, do not count this run as the non-fatal-stall scenario.',
  );

  const pending = Array.from(heldRoutes);
  heldRoutes.clear();
  await Promise.all(
    pending.map(async (entry) => {
      try {
        await entry.route.abort('aborted');
      } catch (_) {
        // hls.js or Chromium may already have cancelled a pending request while it was being held.
      } finally {
        entry.resolve();
      }
    }),
  );

  await context.close();
}

main().catch((error) => {
  if (error && error.message === 'PLAYWRIGHT_MODULE_UNAVAILABLE') {
    fail(
      'Playwright could not be loaded. Run this procedure in the development container or set KINO_PLAYWRIGHT_MODULE to the local Playwright module path.',
    );
    return;
  }

  fail(`Browser scenario failed before completion (${(error && error.name) || 'unknown error'}).`);
});
