#!/usr/bin/env node
'use strict';

const os = require('os');
const path = require('path');
const readline = require('readline');

const APP_URL = process.env.KINO_BROWSER_URL || 'http://localhost:3000';
const CDN_HOST = (process.env.KINO_BROWSER_CDN_HOST || '').trim().toLowerCase();
const PATH_HINT = (process.env.KINO_BROWSER_FRAGMENT_PATH_HINT || '').trim();
const TIMEOUT_MS = Number(process.env.KINO_BROWSER_TIMEOUT_MS || 60000);
const MIN_SEEK_SECONDS = Number(process.env.KINO_BROWSER_MIN_SEEK_SECONDS || 45);
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

function boundedFailureName(errorText) {
  const value = String(errorText || '').toLowerCase();

  if (value.includes('timed')) return 'timeout';
  if (value.includes('reset')) return 'reset';
  if (value.includes('refused')) return 'refused';
  if (value.includes('abort')) return 'aborted';
  if (value.includes('name_not_resolved')) return 'dns';
  if (value.includes('internet_disconnected')) return 'offline';
  return 'other';
}

async function loadPlaywright() {
  const moduleName = process.env.KINO_PLAYWRIGHT_MODULE || 'playwright';

  try {
    return require(moduleName);
  } catch (_) {
    throw new Error('PLAYWRIGHT_MODULE_UNAVAILABLE');
  }
}

async function chooseUnbufferedTarget(page) {
  return page.evaluate((minSeekSeconds) => {
    const video = document.querySelector('video');
    if (!video) return { error: 'NO_VIDEO' };

    const duration = Number(video.duration);
    const currentTime = Number(video.currentTime);
    if (!Number.isFinite(duration) || duration <= 0) return { error: 'NO_FINITE_DURATION' };
    if (!Number.isFinite(currentTime)) return { error: 'NO_CURRENT_TIME' };

    const ranges = [];
    for (let i = 0; i < video.buffered.length; i += 1) {
      ranges.push({ start: video.buffered.start(i), end: video.buffered.end(i) });
    }

    const bufferedAt = (time) => ranges.some((range) => time >= range.start - 0.25 && time <= range.end + 0.25);
    const lastCandidate = Math.max(0, duration - 2);
    const firstCandidate = Math.min(lastCandidate, currentTime + Math.max(5, minSeekSeconds));

    for (let candidate = firstCandidate; candidate <= lastCandidate; candidate += 5) {
      if (!bufferedAt(candidate)) {
        return { target: candidate, currentTime, duration, ranges };
      }
    }

    return { error: 'NO_FORWARD_UNBUFFERED_TARGET', currentTime, duration, ranges };
  }, MIN_SEEK_SECONDS);
}

async function main() {
  if (!CDN_HOST) {
    fail('KINO_BROWSER_CDN_HOST is required. Use only the CDN hostname, never a full media URL.');
    return;
  }

  if (!PATH_HINT) {
    fail(
      'KINO_BROWSER_FRAGMENT_PATH_HINT is required so the scenario fails closed instead of observing unrelated CDN traffic.',
    );
    return;
  }

  if (!Number.isFinite(TIMEOUT_MS) || TIMEOUT_MS <= 0) {
    fail('KINO_BROWSER_TIMEOUT_MS must be a positive number.');
    return;
  }

  if (!Number.isFinite(MIN_SEEK_SECONDS) || MIN_SEEK_SECONDS < 5) {
    fail('KINO_BROWSER_MIN_SEEK_SECONDS must be at least 5 seconds.');
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

  let observing = false;
  let matchingRequests = 0;
  let matchingResponses = 0;
  let matchingFailures = 0;
  const responseStatuses = new Map();
  const failureNames = new Map();

  page.on('request', (request) => {
    if (observing && requestMatches(request)) matchingRequests += 1;
  });

  page.on('response', (response) => {
    if (!observing || !requestMatches(response.request())) return;
    matchingResponses += 1;
    const status = response.status();
    responseStatuses.set(status, (responseStatuses.get(status) || 0) + 1);
  });

  page.on('requestfailed', (request) => {
    if (!observing || !requestMatches(request)) return;
    matchingFailures += 1;
    const name = boundedFailureName(request.failure() && request.failure().errorText);
    failureNames.set(name, (failureNames.get(name) || 0) + 1);
  });

  console.log(`Opening ${appOrigin}. Browser Sentry is expected to stay disabled by A18's runtime gate.`);
  await page.goto(APP_URL, { waitUntil: 'domcontentloaded' });

  await waitForEnter(
    'Sign in if needed, start normal HLS playback, open the in-app diagnostics overlay, and wait until video is visibly progressing.',
  );

  const target = await chooseUnbufferedTarget(page);
  if (target.error) {
    fail(
      `Could not choose a forward unbuffered seek target (${target.error}). Start earlier in a longer title or reduce KINO_BROWSER_MIN_SEEK_SECONDS.`,
    );
    await context.close();
    return;
  }

  console.log(
    `Selected an unbuffered target approximately ${Math.round(target.target - target.currentTime)} seconds ahead. Buffered ranges and media URLs will not be printed.`,
  );

  observing = true;
  await page.evaluate((seekTarget) => {
    const video = document.querySelector('video');
    if (!video) throw new Error('VIDEO_DISAPPEARED');
    video.currentTime = seekTarget;
  }, target.target);

  let outcome = 'timeout';
  try {
    outcome = await Promise.race([
      page
        .waitForFunction(
          (seekTarget) => {
            const video = document.querySelector('video');
            return Boolean(
              video &&
                !video.paused &&
                video.readyState >= 2 &&
                Math.abs(video.currentTime - seekTarget) <= 5,
            );
          },
          target.target,
          { timeout: TIMEOUT_MS },
        )
        .then(() => 'resumed'),
      page
        .waitForSelector('text=Повторить', { state: 'visible', timeout: TIMEOUT_MS })
        .then(() => 'terminal-failure'),
    ]);
  } catch (_) {
    outcome = 'timeout';
  }

  observing = false;

  const statuses = Array.from(responseStatuses.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([status, count]) => `${status}:${count}`)
    .join(', ');
  const failures = Array.from(failureNames.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([name, count]) => `${name}:${count}`)
    .join(', ');

  console.log(`Application outcome after the unbuffered seek: ${outcome}.`);
  console.log(
    `Matching media-fragment traffic: requests=${matchingRequests}, responses=${matchingResponses}, failures=${matchingFailures}.`,
  );
  if (statuses) console.log(`Response status counts: ${statuses}.`);
  if (failures) console.log(`Bounded request-failure categories: ${failures}.`);

  if (matchingRequests === 0) {
    fail(
      'No media-fragment request matched after the seek. Do not count this run as unbuffered-seek evidence; verify the non-secret fragment discriminator.',
    );
  }

  await waitForEnter(
    'Inspect diagnostics now. Record whether playback resumed, recovery engaged, or the terminal notice appeared; browser observations do not establish the LG G5 cause of HTTP 0.',
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
