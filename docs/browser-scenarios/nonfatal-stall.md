# Non-fatal stall browser procedure

This is the second local/preview-only A18 browser procedure. It is intentionally separate from `refused-segment.js`: instead of returning a synthetic HTTP or network failure, it leaves matching media-fragment requests pending at Playwright's routing boundary so the application can be observed while playback stops making progress.

A browser run is **not LG-device evidence**. Chromium has a different MSE/decoder implementation, user agent, networking stack, and frame pacing. Sentry is intentionally disabled for HTTP/HTTPS browser sessions, so this procedure cannot establish A2 delivery or any A5/A6/A11 television result.

## Prerequisites

Use the repository's normal dependencies and start the local web build:

```sh
yarn start
```

Run the procedure from an environment where the Playwright Node module and Chromium are available. If Node does not resolve Playwright automatically, set `KINO_PLAYWRIGHT_MODULE` to the local module path. The script uses the same persistent browser-profile convention as `refused-segment.js`: authentication stays in a profile under the operating-system temporary directory by default rather than in scripts, fixtures, command-line tokens, or committed files.

Before running, identify from browser developer tools or the existing diagnostics:

- the hostname serving HLS media; and
- a **non-secret path fragment that distinguishes media segments** on that host.

Do not use a query parameter, signed token, full asset URL, viewing identifier, encryption-key path, or subtitle path as the discriminator. If a path discriminator cannot distinguish media segments from keys, subtitles, and unrelated CDN requests, do not count the run as this scenario.

## Run

```sh
KINO_BROWSER_CDN_HOST=<cdn-hostname> \
KINO_BROWSER_FRAGMENT_PATH_HINT=<non-secret-segment-path-fragment> \
node docs/browser-scenarios/nonfatal-stall.js
```

`KINO_BROWSER_URL` defaults to `http://localhost:3000`. `KINO_BROWSER_PROFILE_DIR` and `KINO_BROWSER_TIMEOUT_MS` have the same purposes as in the refused-segment procedure; the default observation window here is 120 seconds.

1. In the opened browser, sign in if needed and start normal HLS playback.
2. Open the in-app playback diagnostics before arming the scenario, then wait until playback is visibly progressing.
3. Return to the terminal and press Enter. From that point onward, requests matching both the configured CDN hostname and the required fragment-path discriminator remain pending at the browser boundary. Full request URLs are never printed.
4. Observe the diagnostics while the current buffer drains. The intended application path is watchdog recovery: `recovery` should progress through `stall / restart` and `stall / reload` actions until the terminal `Повторить` notice appears.
5. Before cleanup, confirm that fatal recovery did **not** engage before the notice. If diagnostics show a fatal HLS recovery path first, the browser/network stack turned the pending request into a different failure mode; record that as a negative result, but do not count it as non-fatal-stall evidence.
6. Return to the terminal and press Enter to release/cancel held routes and close the browser context.

## What a successful run establishes

A successful run establishes only that, in Chromium against otherwise real backend/CDN traffic, keeping proven media-fragment requests pending can leave playback non-progressing long enough for the application's stall watchdog to restart/reload and eventually surface the existing terminal failure notice **without fatal recovery becoming the causal path first**.

It does not establish why the LG G5 sees `HTTP 0`, whether the television's hls.js/XHR implementation keeps the same request pending, whether TV playback recovers from a playlist reload, whether remote focus works, or whether Sentry receives an episode. Failure to reproduce in Chromium also does not disprove a television problem.
