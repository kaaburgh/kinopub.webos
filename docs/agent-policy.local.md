## Kinopub webOS project policy

### Project sources and environment

Treat [`ROADMAP.md`](./ROADMAP.md) as the live product status and sequencing document. [`TECHNICAL_REVIEW.md`](./TECHNICAL_REVIEW.md) is a historical review snapshot: do not implement a finding from it merely because it exists there; reconcile it with the current roadmap and code first.

Use Node.js 14 from [`.nvmrc`](./.nvmrc) and Yarn Classic 1.x. Install dependencies with `yarn install --frozen-lockfile`. Do not hide the webpack/OpenSSL incompatibility behind an untracked runtime flag, and never commit `node_modules/`, `build/`, or `out/`.

Common repository checks are:

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

Playback scenarios can be run independently with:

```sh
yarn test --watchAll=false --testPathPattern=media.scenarios
HLS_DEBUG=1 yarn test --watchAll=false --testPathPattern=media.scenarios
```

### Chrome 35 and webOS compatibility

The shipped browser target is `chrome 35`. Modern TypeScript syntax compiling successfully is not evidence that a modern runtime or DOM API exists on the television; require an existing polyfill or a guarded fallback. Any change that can affect emitted JavaScript, dependencies, bundling, or browser APIs must include `yarn build` and `yarn check:es5` validation.

Treat dependency upgrades—especially hls.js, React, Enact, Create React App, webpack, TypeScript, and webOS tooling—as migrations rather than opportunistic edits. Do not combine them with unrelated feature work. Preserve TV remote-control behaviour and focus. Back-button handling is ordered through the global handler stack, so do not assume DOM-style propagation or that an awaited handler is harmless.

### Playback and HLS invariants

The active playback implementation is reached through `src/components/media/index.ts`; verify the export before editing similarly named legacy files. Before changing recovery, quality selection, audio-track restoration, diagnostics, or the playback harness, read the playback scenario guide, diagnostics specification, and diagnostics manual test under `docs/`.

Keep these established rules unless new evidence and regression coverage justify replacing them:

- hls.js owns its non-fatal retry policy; application recovery must not fight it;
- an init segment buffering is not proof that normal media playback recovered;
- `currentLevel` and `nextLevel` have materially different buffer behaviour and are not interchangeable;
- audio fragments and main fragments do not interpret every level/index field identically;
- scenario tests stage external conditions at the loader/CDN boundary rather than manufacturing hls.js events or controller state;
- prefer behavioural assertions over exact retry counts or timings except for explicitly documented upgrade tripwires.

For a playback defect, reproduce the failure in a focused unit test or playback scenario before changing production code whenever the harness can honestly represent it. Device-only failures remain device-only.

### Evidence and device claims

Use the repository evidence vocabulary precisely:

- `code` — established by reading this repository;
- `runtime` — checked against the pinned runtime or an executable test;
- `device` — observed on an LG television;
- `assumed` — plausible but not established.

Tests and jsdom cannot establish decoder behaviour, HDR/compositor behaviour, remote focus, Developer Mode installation, or final TV playback. Do not mark device acceptance complete without actual LG-TV evidence supplied or collected by the maintainer.

### Diagnostics, telemetry, privacy, and lifecycle

Never log or expose full media/API URLs, query strings, access tokens, cookies, credentials, subtitle text, or personal viewing data. Keep endpoint/path cardinality bounded, diagnostic histories bounded and scoped to the relevant playback session, and preserve the repository's existing identifier scrubbing. Every listener, timer, observer, loader, and global style/handler added by a component needs matching cleanup unless its process-wide lifetime is deliberate and documented.

Do not add a public deployment or a new telemetry destination without an explicit maintainer decision.

### Product and documentation discipline

Make the smallest coherent change that addresses the demonstrated problem and avoid opportunistic rewrites of old React/Enact code. Add regression coverage for a bug fix whenever the failure is representable in tests. Preserve existing user-facing language unless the task is explicitly about copy or localisation. When observable facts change, update the corresponding source of truth in the same change: `ROADMAP.md` for product state/evidence/sequencing; the diagnostics spec/manual test for observable playback behaviour; the scenario-test guide for harness semantics; and build/CI docs for commands or workflows. Do not rewrite `TECHNICAL_REVIEW.md` as a live backlog; make only narrowly justified historical corrections.
