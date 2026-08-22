# Teardown after a stalled playback episode

This local A18 procedure stages the same browser-boundary non-fatal stall used by `nonfatal-stall.js`, waits until the application has exhausted recovery and shows the existing `Повторить` terminal notice, then leaves the player through the application's normal Back handling.

It exists to exercise the **application-side teardown path while a recovery episode is active**. Browser Sentry is deliberately disabled, so this procedure does not and cannot prove that the teardown episode is delivered to Sentry. That remains A2 television evidence.

## Prerequisites

1. Start the local app with `yarn start`.
2. Use an environment with Playwright and Chromium available as described in `README.md`.
3. Obtain the hostname serving HLS media plus a **non-secret path fragment that uniquely distinguishes media segments**. Do not use a full URL, query parameter, signed token, viewing identifier, encryption-key path, or subtitle path.

The scenario uses the same persistent browser profile as the other browser procedures, so sign-in may survive between runs without storing credentials in the repository or command line.

## Run

```sh
KINO_BROWSER_CDN_HOST=<cdn-hostname> \
KINO_BROWSER_FRAGMENT_PATH_HINT=<non-secret-segment-path-fragment> \
node docs/browser-scenarios/teardown.js
```

Optional settings:

- `KINO_BROWSER_URL` — local/preview URL; defaults to `http://localhost:3000`.
- `KINO_BROWSER_TIMEOUT_MS` — maximum wait for recovery exhaustion / terminal notice; defaults to 120 seconds.
- `KINO_BROWSER_LEAVE_TIMEOUT_MS` — maximum wait for the player-left state after Back; defaults to 10 seconds.
- `KINO_BROWSER_PROFILE_DIR` and `KINO_PLAYWRIGHT_MODULE` — same local overrides as the other browser procedures.

After Chromium opens:

1. Sign in if needed, start normal HLS playback, and wait until video is visibly progressing.
2. Return to the terminal and press Enter to arm the scenario.
3. Matching media-fragment requests are held pending at Playwright's routing boundary. Other traffic continues normally.
4. Wait for the application's existing terminal failure notice with `Повторить`. This is the precondition for leaving: the player has exhausted its applicable recovery path, and the recovery episode is active in application state.
5. The script sends one `Escape` key, which the application recognises as Back. Do not click around or manually remove the player DOM.
6. Success requires both the route to change away from the player route and the `<video>` element to be removed within the bounded leave timeout. The script reports the named `player-left` outcome and only a count of held matching requests.

If the terminal notice appears without any matching media-fragment request after arming, the run fails closed. If Back is consumed by another UI layer or the application does not leave the player within the timeout, the run also fails rather than inferring teardown.

## What this scenario establishes

A successful run establishes that, after a browser-boundary staged stall reaches terminal recovery exhaustion, the normal application Back path leaves the player and unmounts its media element. Code evidence ties that unmount to `episode.reset(..., 'teardown')` in `media.new.tsx`, so the browser procedure exercises the application-side teardown path without inventing a separate test-only hook.

It does **not** establish that a Sentry event was sent or delivered. HTTP/HTTPS browser sessions intentionally do not initialise Sentry. It also does not establish LG remote/focus behaviour, webOS MSE/decoder behaviour, the cause of CDN `HTTP 0`, or any A2/A5/A6/A11 device acceptance result.

## Privacy and cleanup

The configured path discriminator stays local to the process and is never printed. The script prints no full media/API URLs, query strings, tokens, cookies, subtitle content, title names, playback identifiers, or exact playback positions.

On success or failure the script releases/cancels held routes and closes the browser context. Delete the persistent browser profile when it is no longer useful.
