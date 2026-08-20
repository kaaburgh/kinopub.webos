#!/usr/bin/env node
'use strict';

const os = require('os');
const path = require('path');
const readline = require('readline');

const APP_URL = process.env.KINO_BROWSER_URL || 'http://localhost:3000';
const CDN_HOST = (process.env.KINO_BROWSER_CDN_HOST || '').trim().toLowerCase();
const PATH_HINT = process.env.KINO_BROWSER_FRAGMENT_PATH_HINT || '';
const TIMEOUT_MS = Number(process.env.KINO_BROWSER_TIMEOUT_MS || 180000);
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

  if (PATH_HINT && !parsed.pathname.includes(PATH_HINT)) {
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
  let targetUrl;
  let refusedAttempts = 0;
  let targetChosenAt = 0;

  await page.route('**/*', async (route) => {
    const request = route.request();

    if (!armed || !requestMatches(request)) {
      await route.continue();
      return;
    }

    if (!targetUrl) {
      targetUrl = request.url();
      targetChosenAt = Date.now();
      console.log(`Selected one fragment request on ${CDN_HOST}; its URL will not be printed.`);
    }

    if (request.url() !== targetUrl) {
      await route.continue();
      return;
    }

    refusedAttempts += 1;
    console.log(`Refused target fragment attempt ${refusedAttempts}.`);
    await route.abort('connectionrefused');
  });

  console.log(`Opening ${appOrigin}. Browser Sentry is expected to stay disabled by A18's runtime gate.`);
  await page.goto(APP_URL, { waitUntil: 'domcontentloaded' });

  await waitForEnter(
    'Sign in if needed, start normal HLS playback, and wait until video is visibly progressing. The dedicated browser profile stays outside the repository.',
  );

  armed = true;
  console.log('Scenario armed. The next matching non-playlist CDN request becomes the refused target.');

  try {
    await page.waitForSelector('text=Повторить', { state: 'visible', timeout: TIMEOUT_MS });
  } catch (_) {
    fail(`Failure notice was not observed within ${TIMEOUT_MS} ms; refused attempts: ${refusedAttempts}.`);
  }

  if (process.exitCode !== 1) {
    const elapsed = targetChosenAt ? Date.now() - targetChosenAt : 0;
    console.log(
      `Observed the terminal failure notice after ${refusedAttempts} refused attempt(s)` +
        (elapsed ? ` over approximately ${elapsed} ms.` : '.'),
    );
  }

  await waitForEnter('Inspect diagnostics or retry locally if useful. The script will then close its browser context.');
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
