# Coding-agent playbook

This document expands the repository-wide rules in [`AGENTS.md`](../AGENTS.md). It is intended for agents that need to orient themselves, investigate a defect, implement a change, and prepare a reviewable pull request without rediscovering the repository's sharp edges.

## Repository map

### Application shell

- `src/index.tsx` loads polyfills and starts the application.
- `src/App/App.tsx` configures Enact/Moonstone, React Query, and lazy-loaded routes.
- `src/components/router/` and `src/containers/views/` provide navigation and view composition.
- `src/utils/keyboard.ts` and its hooks coordinate global remote-key handlers.

### Backend and persistence

- `src/api/base.ts` contains the shared request path.
- `src/api/kinopub.ts` exposes KinoPub API operations.
- `src/api/typings.ts` defines API response shapes.
- `src/storage.ts` and `src/hooks/useStorageState.ts` manage the namespaced local-storage state.
- `src/utils/logging.ts` owns Sentry initialisation and shared reporting helpers.

### Playback

- `src/components/player/player.tsx`: player shell, controls, badges, overlays, and remote interaction.
- `src/components/player/settings.tsx`: in-player settings.
- `src/components/media/media.new.tsx`: video element, HLS lifecycle, recovery, watchdog, and decode sampling.
- `src/components/player/playbackDiagnostics.tsx`: diagnostics collection and overlay.
- `src/components/player/diagnosticsExport.ts` and `diagnosticsQr.tsx`: compact capture and QR export.
- `src/utils/hlsFailures.ts`: failure taxonomy.
- `src/utils/hlsLevels.ts`: level-to-quality normalisation.
- `src/utils/hlsRecovery.ts`, `decodeHealth.ts`, and `playbackEpisode.ts`: pure, heavily tested rules.

### Playback test infrastructure

- `src/components/media/media.scenarios.test.tsx`: end-to-end-ish playback scenarios using the real player and hls.js.
- `src/testing/hlsCdn.ts`: scripted loader/CDN boundary.
- `src/testing/mediaSource.ts`: Media Source Extensions stub.
- `src/testing/playbackHarness.tsx`: simulated playback and virtual time.
- `scripts/decode-diagnostics.js`: reference decoder for exported captures.

## Choosing the next source to read

| Change area | Read before editing | Minimum focused validation |
| --- | --- | --- |
| Playback recovery, stalls, hls.js | `ROADMAP.md`, playback scenario guide, relevant scenario and pure-rule tests | focused unit tests + `media.scenarios` |
| Diagnostics or QR export | diagnostics spec, manual test, decoder script | diagnostics/export tests + `yarn check:docs` |
| Quality or audio selection | roadmap history for the item, `hlsLevels`, scenarios covering switches/recovery | unit tests + relevant scenarios |
| Subtitle/HDR behaviour | roadmap evidence and manual test; distinguish manifest evidence from codec guesses | unit tests where possible; TV validation remains explicit |
| API/reporting | API failure rules, logging privacy rules, OAuth call sites | focused tests + typecheck |
| Remote keys/navigation | `utils/keyboard.ts`, registration hooks, all handlers for the same key | focused tests if present + manual interaction plan |
| Build, dependencies, browser APIs | build/install guide, CI guide, browserslist, polyfills | build + ES5 check; package when packaging can change |
| Documentation only | linked source docs and `scripts/check-docs-links.js` expectations | format check + docs link check |

## Investigation workflow

### 1. Establish the current state

Read the relevant active roadmap item and inspect the current code before proposing a solution. The roadmap often records earlier failed approaches, device observations, and completed follow-ups that are easy to accidentally reimplement.

When a report comes from a TV capture or Sentry event, separate observations from interpretations. Record the observable facts first: event type/detail, HTTP status, buffer range, ready state, selected/current level, timestamps, and user action. A bandwidth estimate or a codec name is not by itself proof of the root cause.

### 2. Reproduce at the lowest honest boundary

Prefer a pure unit test for a pure rule. Prefer a playback scenario when the behaviour depends on the interaction between the player, hls.js, and network delivery. Use the scripted loader/CDN boundary; do not manufacture the desired hls.js event directly.

The scenario harness cannot establish decoder, HDR, compositor, focus, installation, or real network-stack behaviour. For those, add or update a manual test plan and keep the roadmap item at `validation incomplete` or `blocked on device evidence` as appropriate.

### 3. Make one causal change

Keep the implementation tied to the reproduced failure. Avoid combining cleanup, dependency upgrades, broad typing changes, and behavioural changes unless they are inseparable.

When editing recovery code, inspect both the application state and hls.js's pinned behaviour. A workaround is valuable only while it handles a case hls.js does not already handle; scenario tripwires exist to reveal when that changes.

### 4. Validate in layers

Run focused checks first. Then select broader checks based on the diff:

- TypeScript/React logic: lint, format, typecheck, focused tests.
- Playback logic: the above plus playback scenarios.
- Documentation: format and docs-link check.
- Dependencies, output syntax, browser APIs, build config: build and ES5 check.
- Packaging or webOS metadata: package and verify the unsuffixed `out/kinopub.webos_v<version>.ipk` exists.

A full CI-equivalent local pass is:

```sh
yarn lint
yarn format:check
yarn typecheck
CI=true yarn test --watchAll=false
yarn check:docs
yarn build
yarn check:es5
yarn package
```

Do not run expensive unrelated checks merely to produce a long checklist, but do not omit a compatibility check that can catch a black-screen regression.

### 5. Reconcile documentation and evidence

Update docs with what the change actually proves. Examples:

- A passing scenario is `runtime` evidence, not `device` evidence.
- A UI component with tests is still `validation incomplete` when its focus and visibility must be checked on the TV.
- A corrected hypothesis should remain visible where future readers would otherwise repeat it.
- If an experiment shows a roadmap item is unnecessary, mark it dropped or superseded with the reason rather than silently deleting it.

## Review checklist for playback changes

Before opening a PR, check each relevant question:

- Does the change preserve the distinction between automatic ABR and deliberate fixed-quality selection?
- Can it flush or invalidate buffered media unexpectedly?
- Does it restore the selected audio/subtitle state after source or manifest changes?
- Does it reset a retry budget only on evidence of real recovery?
- Does it leave hls.js's non-fatal retry policy alone?
- Does terminal failure become visible and actionable without appearing during active recovery?
- Are diagnostic histories bounded, session-scoped, and free of sensitive URLs or tokens?
- Are all timers, listeners, loaders, and observers cleaned up?
- Is Back/focus behaviour still well-defined?
- Is the scenario describing an external condition rather than asserting an implementation detail?

## Handling an hls.js upgrade

An hls.js upgrade is an investigation, not a version-number edit.

1. Change the dependency and lockfile without unrelated behaviour changes.
2. Run pure-rule tests and all playback scenarios.
3. For changed scenarios, distinguish hls.js assertions from player assertions.
4. Inspect the loader config received by `src/testing/hlsCdn.ts`; timeout and retry policy fields have changed between 1.x releases while retaining a similar shape.
5. Read the matching upstream hls.js controller tests or source for the pinned version.
6. Remove an application workaround only when the scenario still reaches the desired user outcome without it.
7. Run build and ES5 validation.
8. Record changed assumptions and remaining TV validation in the roadmap/docs.

## Preparing the pull request

Keep the PR reviewable without conversation history. The description should let another engineer answer:

- What fact or user outcome motivated the change?
- What alternative explanation or approach was ruled out?
- Which part is proven by code/tests, and which still needs a TV?
- Which commands passed?
- What privacy, compatibility, or playback invariant was at risk?
- What was intentionally not changed?

Use the repository PR template rather than replacing its sections with a generic summary.
