# Repository instructions for coding agents

These instructions apply to the entire repository. Read this file before planning or changing code, then read the task-specific sources named below.

## Start with the right sources

Use this order when sources disagree:

1. The current task or issue and explicit maintainer decisions.
2. Current code and tests.
3. [`ROADMAP.md`](./ROADMAP.md), which is the live status and sequencing document.
4. Behavioural documentation under [`docs/`](./docs/), especially the diagnostics spec and test guides.
5. [`TECHNICAL_REVIEW.md`](./TECHNICAL_REVIEW.md), which is a historical review snapshot, not a live backlog.

Do not implement an item from `TECHNICAL_REVIEW.md` merely because it is listed there. Check its current status in `ROADMAP.md`; many findings have already been completed, superseded, corrected, or dropped.

For a detailed repository map, change workflow, and validation matrix, read [`docs/agent-playbook.md`](./docs/agent-playbook.md).

## Environment and commands

- Use Node.js 14 from [`.nvmrc`](./.nvmrc) and Yarn Classic 1.x. Do not paper over the webpack/OpenSSL incompatibility with an untracked runtime flag.
- Install dependencies with `yarn install --frozen-lockfile`.
- Prefer focused tests while iterating, then run the checks appropriate to the diff.
- Never commit `node_modules/`, `build/`, or `out/`.

Common checks:

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

Playback scenarios can be run independently:

```sh
yarn test --watchAll=false --testPathPattern=media.scenarios
HLS_DEBUG=1 yarn test --watchAll=false --testPathPattern=media.scenarios
```

Do not claim a command passed unless you ran it. State exactly what was not run and why.

## Non-negotiable compatibility rules

- The shipped browser target is `chrome 35`. Modern TypeScript syntax may compile, but modern runtime and DOM APIs still require an existing polyfill or a guarded fallback. A successful type check is not compatibility evidence.
- Any change that can affect emitted JavaScript, dependencies, bundling, or browser APIs must be validated with `yarn build` and `yarn check:es5`.
- Treat dependency upgrades, especially `hls.js`, React, Enact, Create React App, webpack, TypeScript, and webOS tooling, as migrations. Do not combine them with unrelated feature work.
- Preserve TV remote-control behaviour and focus. Back-button handling is ordered through a global handler stack; do not assume DOM-style event propagation or harmless async waits.

## Playback and HLS invariants

The active playback implementation is reached through `src/components/media/index.ts`; verify the export before editing any similarly named legacy file.

Before changing recovery, quality selection, audio-track restoration, diagnostics, or the test harness, read:

- [`docs/playback-scenario-tests.md`](./docs/playback-scenario-tests.md)
- [`docs/playback-diagnostics-spec.md`](./docs/playback-diagnostics-spec.md)
- [`docs/playback-diagnostics-manual-test.md`](./docs/playback-diagnostics-manual-test.md)

Keep these established rules unless new evidence and tests justify replacing them:

- hls.js owns its non-fatal retry policy; application recovery should not fight it.
- An init segment buffering is not proof that normal media playback recovered.
- `currentLevel` and `nextLevel` have materially different buffer behaviour. Do not substitute one for the other casually.
- Audio fragments and main fragments do not interpret every level/index field identically.
- A scenario test should stage the external condition at the loader/CDN boundary, not mock hls.js events or internal controllers.
- Prefer behavioural assertions over exact retry counts or timings, except for explicitly documented upgrade tripwires.

For playback defects, reproduce the failure in a focused test or scenario before changing production code whenever the harness can represent it. Device-only failures must remain labelled as device-only.

## Evidence and device claims

Use the repository's evidence vocabulary precisely:

- `code`: established by reading this repository;
- `runtime`: checked against the pinned runtime or an executable test;
- `device`: observed on an LG television;
- `assumed`: plausible but not established.

Tests and jsdom cannot validate decoder behaviour, HDR/compositor behaviour, remote focus, Developer Mode installation, or the final TV playback experience. Do not mark device acceptance criteria complete without actual device evidence supplied or collected by the maintainer.

## Diagnostics, telemetry, and privacy

- Never log or expose full media/API URLs, query strings, access tokens, cookies, credentials, subtitle text, or personal viewing data.
- Keep endpoint/path cardinality bounded and scrub numeric identifiers where the existing code does so.
- Keep histories bounded and scoped to the relevant playback session.
- Every listener, timer, observer, and global style or handler added by a component needs a matching cleanup unless its process-wide lifetime is deliberate and documented.
- Do not add a public deployment or a new telemetry destination without an explicit maintainer decision.

## Scope and documentation discipline

- Make the smallest coherent change that addresses the demonstrated problem. Avoid opportunistic rewrites of old React/Enact code.
- Preserve existing user-facing language unless the task is explicitly about copy or localisation.
- Add regression coverage for a bug fix when the failure is representable in tests.
- Update the source of truth in the same change:
  - `ROADMAP.md` when an item status, evidence, sequencing, or decision changes;
  - the diagnostics spec/manual test when observable playback behaviour changes;
  - the scenario-test guide when the harness contract or scenarios change;
  - build/CI docs when commands or workflows change.
- Do not rewrite `TECHNICAL_REVIEW.md` as a live status document. Add a narrowly scoped correction only when preserving the historical record requires it.

## Pull requests

Use a focused branch and a conventional/imperative title that the repository labeler can classify, for example `fix: preserve audio selection after recovery` or `docs: add agent workflow guidance`.

A useful PR description states:

- the demonstrated problem or goal;
- why the chosen change addresses it;
- tests and checks actually run;
- device validation performed, still required, or not applicable;
- documentation or roadmap updates;
- known limits and follow-ups that were deliberately left out.
