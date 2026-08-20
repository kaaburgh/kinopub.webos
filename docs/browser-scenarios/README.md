# Browser playback scenarios

These procedures are local/preview-only A18 tools for reproducing application-level playback failures against the real KinoPub backend and CDN. They are deliberately not CI jobs and must not be published as a permanent web surface.

A browser run is **not LG-device evidence**. Chromium has a different MSE/decoder implementation, user agent, networking stack and frame pacing. A browser reproduction can prove that application logic reaches an expected state; failure to reproduce does not disprove a television problem. Sentry is intentionally disabled for HTTP/HTTPS browser sessions, so real Sentry delivery remains a TV acceptance check under A2.

## Prerequisites

Use the repository's normal dependencies and start the local web build:

```sh
yarn start
```

Run the scenario from an environment where the Playwright Node module and Chromium are available. The development container described by the roadmap provides them. If Playwright is installed somewhere that Node does not resolve automatically, point `KINO_PLAYWRIGHT_MODULE` at that local module path; do not add credentials or machine-specific paths to the repository.

The script launches a persistent Chromium profile under the operating system temp directory by default. This lets a local login survive between runs without copying access or refresh tokens into scripts, command lines, fixtures or committed files. Override the location with `KINO_BROWSER_PROFILE_DIR` if needed and delete that local profile when it is no longer useful.

## Refuse one fragment and observe terminal failure

`refused-segment.js` leaves normal traffic on the real backend/CDN alone until you arm it. It selects only a request that matches both the configured CDN hostname and a required non-secret fragment-path discriminator, then refuses that exact URL plus its retries at Playwright's network boundary. The selected URL is held only in memory and is never printed. The discriminator is mandatory so the scenario fails closed instead of accidentally treating a key, subtitle, or unrelated XHR as media-fragment evidence.

1. Start the app with `yarn start`.
2. From browser developer tools or existing diagnostics, obtain the hostname serving HLS media and a **non-secret path fragment that distinguishes media segments** on that CDN. Do not use a query parameter, signed token, full asset URL, viewing identifier, encryption-key path, or subtitle path as the discriminator.
3. Run:

   ```sh
   KINO_BROWSER_CDN_HOST=<cdn-hostname> \
   KINO_BROWSER_FRAGMENT_PATH_HINT=<non-secret-segment-path-fragment> \
   node docs/browser-scenarios/refused-segment.js
   ```

4. In the opened browser, sign in if necessary, start normal HLS playback, and wait until video is visibly progressing.
5. Return to the terminal and press Enter. The next CDN request matching the required fragment discriminator becomes the refused target. The script reports only the hostname, retry count and elapsed time.
6. The expected application end state is the existing terminal failure notice with the `Повторить` action. The default observation window is 180 seconds; override it with `KINO_BROWSER_TIMEOUT_MS` when investigating a deliberately longer recovery policy.
7. Inspect the in-app diagnostics or try the local retry action if useful, then return to the terminal and press Enter to close the browser context.

The path hint is used only for matching in the local process and is not printed. If you cannot identify a non-secret path discriminator that uniquely distinguishes media segments from keys, subtitles, and other CDN requests, **do not run this scenario as refused-segment evidence**; tighten the discriminator first.

### What this scenario establishes

A successful run establishes only that the browser build, using the real backend/CDN for otherwise normal traffic, can drive the application's fatal/recovery path to the terminal notice when one fragment URL is repeatedly refused. It is useful for inspecting retry/backoff behaviour with browser developer tools and for comparing application behaviour across isolated hls.js candidates.

It does **not** establish why the real CDN returns `HTTP 0` on the LG G5, whether the TV decoder/MSE path behaves the same way, whether remote focus works, or whether a Sentry event is delivered. Those remain device evidence under their roadmap items.
