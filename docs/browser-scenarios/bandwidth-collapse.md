# Bandwidth-collapse / ABR browser scenario

This A18 procedure checks one narrow application/runtime question in Chromium: when a genuine multi-level HLS stream is already playing in Auto mode, does hls.js visibly move to a lower `currentLevel` after browser network throughput is collapsed while playback still makes progress?

It is a local/preview-only procedure. It does not publish a web surface and it does not change production playback code.

## Prerequisites

Start the repository's normal local web build:

```sh
yarn start
```

Run the procedure where the Playwright Node module and Chromium are available. The persistent browser profile defaults to the operating-system temp directory; override it with `KINO_BROWSER_PROFILE_DIR` when needed. Never put access/refresh tokens, cookies, signed media URLs, or machine-specific credentials into this script or a committed fixture.

Before arming the scenario in the opened browser:

1. Sign in if needed.
2. Start a genuine **multi-level** HLS stream.
3. Select the application's **Auto** quality mode.
4. Open the existing playback diagnostics overlay and leave it visible.
5. Wait for visibly progressing playback at a level above level 0.

The diagnostics preconditions are deliberate. A one-level stream, fixed-quality selection, or a baseline already at level 0 cannot demonstrate a downward ABR decision and therefore fails closed.

## Run

Default network shaping is 900 kbps with 180 ms latency for at most 60 seconds:

```sh
node docs/browser-scenarios/bandwidth-collapse.js
```

Useful local overrides are:

```sh
KINO_BROWSER_SLOW_KBPS=700 \
KINO_BROWSER_SLOW_LATENCY_MS=250 \
KINO_BROWSER_SLOW_WINDOW_MS=90000 \
node docs/browser-scenarios/bandwidth-collapse.js
```

Use these only to make the synthetic browser condition appropriate for the title under test. They are experiment inputs, not claimed real-world thresholds.

After you press Enter, the script reads only coarse numeric/text fields already visible in the diagnostics overlay: Auto/fixed mode, level count, `currentLevel`, and the bandwidth estimate. It also reads `<video>.currentTime` to distinguish a quality change during continued playback from a quality change followed by a frozen video.

The script then uses Chromium DevTools Protocol `Network.emulateNetworkConditions` to shape the browser's network stack. Backend and CDN requests are still genuine requests to their ordinary destinations; hls.js events, levels, controller state, and responses are not manufactured by the script. The shaping applies to the page's Chromium network traffic, not only media requests, which is why the condition is armed only after normal playback is established.

The synthetic condition is always removed in a `finally` path before the procedure reports its result.

## Acceptance for one run

A run counts as a browser **bandwidth-collapse / ABR downshift** observation only when all of these are true:

- diagnostics initially show `mode: auto`;
- diagnostics show at least two HLS levels;
- baseline `currentLevel` is above level 0;
- after network shaping, diagnostics show a `currentLevel` lower than the baseline;
- the video advances by at least 2 seconds during the shaped observation window.

If no lower level appears, report that as a negative browser result. Do not increase the shaping severity until a downshift occurs and then present that input as a measured network threshold; this procedure is for reproducibility and application-path inspection, not bandwidth benchmarking.

If a lower level appears but playback does not progress, the script fails the run rather than calling a stalled playback path successful ABR adaptation.

## Privacy and evidence limits

The script prints only the local app origin, configured shaping values, level indexes, a coarse bandwidth estimate in kbps when diagnostics provide one, and video progress duration. It does not print or persist media/API URLs, paths, query strings, cookies, tokens, subtitles, title names, viewing identifiers, or request bodies.

A successful run establishes only that Chromium plus the pinned browser hls.js path can react to this synthetic network condition by selecting a lower HLS level while playback continues.

It does **not** establish:

- a real connection-speed threshold at which hls.js will switch levels;
- that the KinoPub CDN or the user's real network behaves like Chromium's emulator;
- that the LG G5 performs the same ABR decision or timing;
- the cause of the LG `HTTP 0` observations;
- decoder, MSE, HDR/compositor, remote-focus, installation, or Sentry behaviour on the television.

Those remain separate runtime/device evidence questions under their roadmap items.
