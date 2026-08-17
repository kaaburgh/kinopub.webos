## Kinopub repository map and validation

### Repository map

Application shell:

- `src/index.tsx` loads polyfills and starts the application.
- `src/App/App.tsx` configures Enact/Moonstone, React Query, and lazy-loaded routes.
- `src/components/router/` and `src/containers/views/` provide navigation and view composition.
- `src/utils/keyboard.ts` and its hooks coordinate global remote-key handlers.

Backend and persistence:

- `src/api/base.ts` contains the shared request path; `src/api/kinopub.ts` exposes KinoPub operations; `src/api/typings.ts` defines response shapes.
- `src/storage.ts` and `src/hooks/useStorageState.ts` manage namespaced local storage.
- `src/utils/logging.ts` owns Sentry initialisation and shared reporting helpers.

Playback:

- `src/components/player/player.tsx`: player shell, controls, badges, overlays, and remote interaction.
- `src/components/player/settings.tsx`: in-player settings.
- `src/components/media/media.new.tsx`: video element, HLS lifecycle, recovery, watchdog, and decode sampling.
- `src/components/player/playbackDiagnostics.tsx`: diagnostics collection and overlay.
- `src/components/player/diagnosticsExport.ts` and `diagnosticsQr.tsx`: compact capture and QR export.
- `src/utils/hlsFailures.ts`, `hlsLevels.ts`, `hlsRecovery.ts`, `decodeHealth.ts`, and `playbackEpisode.ts`: failure, quality, recovery, decode, and episode rules.

Playback test infrastructure:

- `src/components/media/media.scenarios.test.tsx`: player/hls.js scenarios.
- `src/testing/hlsCdn.ts`: scripted loader/CDN boundary.
- `src/testing/mediaSource.ts`: Media Source Extensions stub.
- `src/testing/playbackHarness.tsx`: simulated playback and virtual time.
- `scripts/decode-diagnostics.js`: reference decoder for exported captures.

### Change-area reading and validation

- Playback recovery, stalls, or hls.js: read `ROADMAP.md`, [`playback-scenario-tests.md`](./playback-scenario-tests.md), the relevant scenario, and pure-rule tests; run focused tests plus `media.scenarios`.
- Diagnostics or QR export: read [`playback-diagnostics-spec.md`](./playback-diagnostics-spec.md), [`playback-diagnostics-manual-test.md`](./playback-diagnostics-manual-test.md), and the decoder; run diagnostics/export tests plus `yarn check:docs`.
- Quality or audio selection: read roadmap evidence, `hlsLevels`, and switch/recovery scenarios; run unit tests plus the relevant scenarios.
- Subtitle/HDR behaviour: read roadmap/device evidence and the manual test; separate manifest/runtime facts from codec guesses; TV validation remains explicit.
- API/reporting: inspect API failure rules, logging privacy rules, and OAuth call sites; run focused tests plus typecheck.
- Remote keys/navigation: inspect `utils/keyboard.ts`, registration hooks, and all handlers for the same key; add focused tests where representable and preserve a manual interaction plan.
- Build, dependencies, or browser APIs: read build/install and CI docs plus browser targets/polyfills; run build + ES5 validation and package when packaging can change.
- Documentation-only changes: run format and docs-link validation.

### Investigation workflow

Establish current roadmap/code facts before proposing a change. For a TV capture or Sentry event, record observations before interpretation: error type/detail, HTTP status, buffer state, ready state, selected/current level, timestamps, and user action. A bandwidth estimate or codec name alone is not a root cause.

Reproduce at the lowest honest boundary: pure unit test for a pure rule; playback scenario when behaviour depends on player + hls.js + network. Stage network failures at the loader/CDN seam rather than mocking hls.js events. The scenario harness cannot establish decoder, HDR, compositor, focus, installation, or real TV-network behaviour; for those, add or update a manual test plan and keep the roadmap item at validation incomplete or blocked on device evidence as appropriate.

Make one causal change. Keep the implementation tied to the reproduced or otherwise demonstrated failure. Avoid combining cleanup, dependency upgrades, broad typing changes, and behavioural changes unless they are inseparable.

Validate in layers. TypeScript/React changes normally require lint, format, typecheck, and focused tests. Playback logic adds scenarios. Documentation adds docs-link validation. Dependencies/output syntax/browser APIs/build configuration add build and ES5 checks. Packaging changes add `yarn package` and verification of the unsuffixed `out/kinopub.webos_v<version>.ipk`. Do not run expensive unrelated checks merely to make the checklist longer, but never omit a compatibility check that can catch a Chrome 35 black-screen regression.

### Playback review checklist

For relevant changes, verify that the diff preserves deliberate fixed-quality selection versus ABR; does not flush buffered media unintentionally; restores selected audio/subtitle state after source/manifest changes; resets retry budgets only on real recovery; leaves hls.js non-fatal retry policy alone; makes terminal failure visible only after active recovery ends; keeps diagnostics bounded/session-scoped/private; cleans up timers/listeners/loaders/observers; preserves Back/focus behaviour; and stages scenario conditions externally rather than asserting implementation details.

### hls.js upgrades

Treat an hls.js upgrade as an investigation. Change the dependency/lockfile without unrelated behaviour changes; run pure rules and all playback scenarios; separate hls.js assertions from player assertions; inspect loader configuration received by `src/testing/hlsCdn.ts`; read the matching upstream controller tests/source for the pinned version; remove a workaround only when the scenarios preserve the required user outcome without it; then run build and ES5 validation and record changed assumptions plus remaining TV validation.
