# Unbuffered-seek browser procedure

This is the third local/preview-only A18 browser procedure. It reproduces the condition that preceded the LG G5 `HTTP 0` capture: playback is already under way, then the player seeks forward to a point that is not present in the current `<video>.buffered` ranges.

The script does **not** manufacture a CDN failure. It keeps backend/CDN traffic real and observes only media-fragment requests that match both the configured CDN hostname and a mandatory non-secret fragment-path discriminator. Full request URLs, query strings, credentials, tokens, buffered ranges, and viewing identifiers are not printed.

A browser run is **not LG-device evidence**. Chromium has a different MSE implementation, network stack, user agent, and CDN path from the television. Reproducing or failing to reproduce `HTTP 0` in Chromium therefore does not establish its cause on the LG G5.

## Prerequisites

Start the local web build with the repository's normal dependencies:

```sh
yarn start
```

Run the procedure where the Playwright Node module and Chromium are available. If Node does not resolve Playwright automatically, set `KINO_PLAYWRIGHT_MODULE` to the local module path. Authentication stays in the same persistent temporary browser-profile convention as the other A18 browser procedures; do not put credentials or tokens in scripts, fixtures, environment variables, or committed files.

Before running, identify from browser developer tools or the existing diagnostics:

- the hostname serving HLS media; and
- a **non-secret path fragment that distinguishes media segments** on that host.

Do not use a query parameter, signed token, full asset URL, viewing identifier, encryption-key path, or subtitle path as the discriminator. If the discriminator cannot separate media segments from keys, subtitles, and unrelated CDN requests, do not count the run as this scenario.

## Run

```sh
KINO_BROWSER_CDN_HOST=<cdn-hostname> \
KINO_BROWSER_FRAGMENT_PATH_HINT=<non-secret-segment-path-fragment> \
node docs/browser-scenarios/unbuffered-seek.js
```

`KINO_BROWSER_URL` defaults to `http://localhost:3000`. `KINO_BROWSER_PROFILE_DIR` keeps the same purpose as in the other browser procedures. `KINO_BROWSER_TIMEOUT_MS` defaults to 60 seconds. `KINO_BROWSER_MIN_SEEK_SECONDS` defaults to 45 seconds and controls how far forward the script begins looking for an unbuffered target.

1. In the opened browser, sign in if needed and start normal HLS playback.
2. Open the in-app playback diagnostics and wait until playback is visibly progressing.
3. Return to the terminal and press Enter. The script reads the current duration/time and buffered ranges inside the page, then chooses a forward target that is actually outside every current buffered range. It prints only the approximate seek distance, not the ranges or target URL.
4. The script assigns that target to the existing `<video>.currentTime`; it does not call `play()` or otherwise force a recovery path. From that moment it counts only matching media-fragment request outcomes.
5. The first named application outcome is reported as one of:
   - `resumed` — playback becomes playable and progresses near the new target;
   - `terminal-failure` — the existing `Повторить` notice appears; or
   - `timeout` — neither happened within the observation window.
6. The script prints bounded request evidence only: matching request/response/failure counts, HTTP response status counts, and coarse request-failure categories such as `timeout`, `reset`, `refused`, `aborted`, `dns`, `offline`, or `other`.
7. Before closing the browser, inspect the in-app diagnostics and record whether watchdog/fatal recovery engaged and whether a browser-side request failure coincided with the seek.

If no matching media-fragment request is observed after the seek, the script exits non-zero and the run must **not** be counted as unbuffered-seek evidence; first verify the non-secret fragment discriminator.

## What a successful run establishes

A successful run establishes that the browser procedure selected a genuinely unbuffered forward seek target, that the real application issued media-fragment traffic matching the fail-closed discriminator afterward, and which named application outcome occurred in Chromium.

If matching requests fail, that is useful browser/runtime evidence for comparing request timing and application recovery with the TV capture. If playback simply resumes, that is also a valid negative result: the same high-level seek condition did not reproduce the television's failure in Chromium.

Neither outcome establishes why the LG G5 CDN request surfaced as `HTTP 0`, whether the CDN treats the television's address/user agent differently, whether the TV MSE/network stack follows the same path, or whether Sentry receives an episode. Those remain television/device questions under their roadmap items.
