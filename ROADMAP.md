# Kinopub webOS Roadmap

This roadmap tracks the work remaining after the playback-diagnostics baseline.

It was restructured after the repository-wide review in [`TECHNICAL_REVIEW.md`](./TECHNICAL_REVIEW.md).
The original priority list is preserved below with an audit verdict against each item, so the LG
device findings recorded against those items stay readable in their original context; work that is
still live has been consolidated into **Active roadmap**, where each item carries the full field set.

## How to read this roadmap

**Statuses**

| Status                           | Meaning                                                                        |
| -------------------------------- | ------------------------------------------------------------------------------ |
| Completed and verified           | Implemented, and checked by tests or by evidence beyond "it compiles"          |
| Completed, validation incomplete | Implemented, but nothing has confirmed it behaves as intended where it matters |
| Partially implemented            | Some of the described scope shipped; the rest is named explicitly              |
| Open                             | Not started                                                                    |
| Investigation first              | The next step is to learn something, not to build something                    |
| Blocked on device evidence       | Cannot be decided without a television                                         |
| Superseded                       | Replaced by a later item; kept for the reasoning                               |
| Dropped                          | No longer worth doing, with the reason                                         |

**Priority model**

| Priority | Meaning                                                                            |
| -------- | ---------------------------------------------------------------------------------- |
| Critical | Playback is broken or user data is exposed, with no workaround                     |
| High     | Users hit it, or it blocks understanding of the failure this project exists to fix |
| Medium   | Real but bounded: robustness, correctness of diagnosis, maintainability            |
| Low      | Cleanup, documentation, or work whose value is not yet established                 |

Nothing is currently Critical. Priorities describe consequences, not enthusiasm.

**Confidence** states what the item's premise rests on: `code` (read in this repository), `runtime`
(checked against the pinned `hls.js` build), `device` (observed on a TV), or `assumed`.

---

## Completed baseline

The first two commits of this fork already cover:

- [Playback diagnostics overlay](https://github.com/kaaburgh/kinopub.webos/commit/fc01289438057a42675ad6ab1c317d0ebe2582fe)
  - native video and HLS state;
  - buffered ranges and buffer-ahead time;
  - HLS levels, selected level, bandwidth estimate, and recent events;
  - fragment, error, and decode metrics;
  - bounded in-memory event history;
  - manual LG webOS test checklist and implementation spec.
- [TypeScript and void-return cleanup](https://github.com/kaaburgh/kinopub.webos/commit/8d1b17dac475ace6863c5858e9e520b8e72f52d9)
  - typed access to the Enact video node;
  - defensive handling when the video node is not available;
  - removal of misleading return values from void storage operations.

The remaining work should build on that baseline instead of reimplementing it.

---

## Audit of the original priority list

The six items below are the roadmap as it stood before the review. Their text is unchanged; each has
gained an **Audit** verdict. Live remainders are carried forward into **Active roadmap** and are not
restated here.

### 1. P0 — Validate the real failure on the LG G5

> **Audit: Completed and verified, in part.** The stall's mechanism was identified on the TV and the
> application defect behind it was fixed. Two things this item asked for were never done and are
> carried forward: the underlying cause of the CDN's `HTTP 0` (→ **A6**), and the fixed-quality /
> adaptive / 720p-vs-1080p comparison sweep, which is now folded into the on-device validation items
> **A5** and **A7**.

Run the checklist in `docs/playback-diagnostics-manual-test.md` on the TV with the stream that previously stalled while the same content continued playing on the laptop.

Capture at least:

- normal playback;
- the first visible stall;
- recovery after the stall;
- fixed-quality playback;
- an adaptive/master-playlist stream, if available;
- the same title at the available 720p and 1080p levels.

At each stall, record the last few overlay states:

- buffer ahead and whether the current position is buffered;
- time since the last successfully buffered fragment;
- HLS error and HTTP status, if any;
- native video events;
- current/next/load level;
- dropped-frame information, if supported.

The earlier working hypothesis was buffer starvation rather than an obvious decoder or raw-bandwidth failure. Treat that as a hypothesis to verify, not as an implementation assumption.

**Validated on the LG G5.** The hypothesis was wrong: this is not buffer starvation and not a bandwidth limit. Overlay captures show repeated `fragLoadError` / `HTTP 0` responses from the CDN host while `bandwidthEstimate` sat at 22-40 Mbps against a 2.1 Mbps top level. The freeze itself was an application defect rather than a network one: hls.js escalated to a _fatal_ network error, which permanently stops its loading engine, and the player had no `ERROR` handler, so nothing ever restarted it. The overlay showed the same fragment stuck `loading` for 100 s, no further `FRAG_LOADING` events, and failure counters frozen; seeking did not restart loading either. Fixed by driving recovery from the application (see item 4 notes). Still open: why the CDN returns `HTTP 0` in the first place.

### 2. P0 — Complete diagnostics around the HLS fragment lifecycle

> **Audit: Completed and verified.** Everything listed shipped, and the trickiest part — that
> `frag.level` indexes the audio track list for audio fragments — was found on the TV and fixed
> across all four call sites. Two follow-ups remain and are carried forward: the QR capture does not
> yet carry the per-stream fragment detail the overlay now shows (→ **A8**), and the cost of the
> always-on collection has never been measured (→ **A11**). Do not re-propose the lifecycle
> instrumentation itself.

Implemented: the overlay now covers fragment load start/completion, buffer append start/completion,
emergency aborts, and a network/buffer-starvation/media-decode/other failure breakdown. See
`docs/playback-diagnostics-spec.md` (Segment Loading, Errors) and
`docs/playback-diagnostics-manual-test.md` (Segment Pipeline, Network Interruption, Buffer Starvation) for
the current behavior and manual test steps. The remaining bullets below describe the scope that was covered.

The current overlay already observes buffered fragments, level switches, and errors. Extend it only where the pinned HLS.js version exposes the events reliably:

- fragment load start/completion;
- buffer append start/completion;
- fragment load timeout or emergency abort;
- a clearer distinction between network failure, buffer starvation, media/decode failure, and normal level switching.

Keep the existing privacy and bounded-history rules:

- show hostnames only;
- never show full URLs, query parameters, cookies, or tokens;
- clean up every listener and timer;
- keep diagnostic state local to the current playback session.

Also verify and, if necessary, correct the Auto/Fixed label. It must describe the actual HLS mode, not merely the presence of multiple levels.

### 3. P1 — Make fixed-quality and adaptive-quality semantics explicit

> **Audit: Completed and verified.** Both the original scope and the on-device follow-up shipped, and
> the level-normalisation rule that fixed it lives in `src/utils/hlsLevels.ts`. One stated remainder
> stays open — exposing a master playlist's internal ABR levels as separate fixed choices — carried
> forward as part of **A13**. Note that the roadmap text below still says "the P0 on-device
> validation from item 1" is open; that validation happened, and item 1 records its result.

The current player can select a level in an adaptive HLS stream, while some other stream variants may effectively be fixed-quality URLs. First document and test that distinction.

Then:

- expose an explicit `Auto` option only for a genuine master playlist with multiple HLS levels;
- use HLS.js automatic level selection for Auto mode;
- keep fixed-quality options deterministic;
- do not present Auto for a one-level HLS stream where it cannot provide adaptation;
- keep the selected mode and quality visible in diagnostics.

The implementation must preserve the existing manual quality behavior while making it clear whether a user selected a fixed level or delegated selection to HLS.js.

**Implemented**: [Make Auto/Fixed HLS quality mode explicit](https://github.com/kaaburgh/kinopub.webos/commit/6d5535df4215453ea8a5085d814924180812cef6). An explicit `Авто` option is now offered only when the loaded manifest turns out to be a genuine multi-level master playlist (checked after `MANIFEST_PARSED`), and selecting it delegates to HLS.js ABR (`currentLevel = -1`) instead of pinning a level. Fixed-quality selection is unchanged and deterministic, playback always starts pinned to the requested quality, and the selected mode/quality is now shown both in the player quality badge and the diagnostics overlay next to the existing HLS.js-derived mode. Still open: exposing the internal ABR levels of a master playlist as separate fixed choices, and the P0 on-device validation from item 1.

**Follow-up fix**: on-device validation on the LG G5 showed fixed-quality selection had no effect at all — the diagnostics overlay reported `selected quality: 480p` while `currentLevel` stayed at the top level and `mode` stayed `auto`. Cause: levels were resolved by exact `level.height` equality against the API quality name, which only holds for 16:9 content. A 2.39:1 encode advertises 854x302 / 1280x536 / 1920x804 / 3840x1606 for what the API calls 480p / 720p / 1080p / 2160p, so no level ever matched, nothing was ever pinned, and HLS.js silently stayed in its default ABR mode. Levels are now normalized to the quality they actually represent (the larger of the advertised height and the 16:9-equivalent height implied by the width) and matched nearest-first, and the overlay shows both the normalized name and the real resolution per level.

### 4. P1 — Add controlled quality fallback after evidence is collected

> **Audit: Partially implemented, and the item now covers two different problems.** What shipped is
> _recovery_, not quality fallback: fatal-error recovery with a drainable budget, a stall watchdog,
> and a decode-health indicator. The network half of the original motivation is **Dropped** — ABR
> already handles it, confirmed by observation on a busy evening. The decode half is still open and
> deliberately gated on evidence (→ **A13**), and the evidence it is gated on has not been collected
> (→ **A5**). The recovery work itself surfaced two live defects: the exhausted state is invisible to
> the viewer (→ **A1**) and the watchdog's reload still flushes the buffer (→ **A7**).

Only after the failure mode and Auto mode are validated, add automatic quality reduction for repeated playback problems.

The first version should be conservative:

- trigger only on a combination of sustained buffer starvation/stalls or repeated recoverable HLS failures;
- lower quality by one available level at a time;
- use a cooldown and hysteresis so the player does not oscillate between levels;
- never override a deliberate manual-quality choice without a clear user-visible indication;
- allow recovery to a higher level only after stable playback;
- keep the fallback disabled for fixed one-level sources;
- show the reason and current mode in diagnostics.

If a source cannot adapt in place, treat switching to another source URL as a separate implementation path rather than silently pretending it is ABR.

**Partially implemented (recovery only, not quality fallback).** Fatal HLS errors are now recovered from: a fatal network error restarts loading with capped exponential backoff, and a fatal media error goes through `recoverMediaError` (plus `swapAudioCodec` on a second consecutive failure). The attempt budget resets once a _media_ fragment buffers on the stream that was failing, and the current recovery state and reason are shown in the overlay.

**Follow-up fix:** the budget originally reset on any `FRAG_BUFFERED` for that stream, which included the init segment. Restarting the loading engine is exactly what refetches an init segment, so recovery manufactured its own proof of success: every retry reloaded the init segment, cleared the budget it had just spent, and went round again. Two LG G5 captures 91 s apart caught it — failed requests climbing 65 → 325 (~2.9/s, no decay), decoded frames frozen at 165, and `recovery` pinned at `attempts=1/6` throughout, in a ~4 s loop of fatal → `startLoad()` → init segment → retries → fatal against one segment the CDN answered with `HTTP 0`. With the budget able to drain, the backoff finally escalates (1→2→4→8→8→8 s) and the player gives up after roughly a minute, reporting `gave up after 6` instead of hammering the CDN indefinitely. The rule now lives in `src/utils/hlsRecovery.ts` with unit tests, since it is subtle and failed silently. Quality switching also moved from `currentLevel` to `nextLevel`, because `currentLevel` flushes the entire buffer to apply the switch instantly -- that is what converted a stream coasting through network failures on 82 s of buffer into an unrecoverable stall. The automatic _quality reduction_ described above is still open and deliberately separate from error recovery.

**Scope narrowed after on-device observation.** Two distinct problems were being conflated here:

- _Network_ — quality already moves on its own when the connection degrades, observed on a busy
  evening. HLS.js ABR covers this; nothing more is needed.
- _Decode_ — the decoder struggling is a different failure, and reducing quality automatically for
  it would be acting on a signal nobody has validated yet. So this ships an **indicator only**:
  a corner badge driven by the dropped-frame ratio over a sliding window, plus hard decode errors.
  See `docs/playback-diagnostics-spec.md` (Decode Health Indicator). Automatic reduction stays open
  until captures show what the decode failure actually looks like.

### 5. P1 — Reduce excessive subtitle brightness, especially in HDR

> **Audit: Partially implemented.** The manual opacity control shipped and is not to be redone. The
> reproduction and isolation steps — the part that would establish whether there is an HDR-specific
> component at all — have never been performed, so the scene-adaptive follow-up rests on an
> unverified premise. Carried forward as **A12**, which also folds in the review's finding that the
> HDR badge a tester would rely on is itself a codec guess.

**Status:** the manual subtitle brightness/opacity control described below has been implemented (in-player Settings popup, persisted via storage, applied through `video::cue { opacity: var(--subtitle-opacity) }` so it covers native `<track>` and HLS.js-rendered cues alike). The reproduction/isolation steps and the scene-adaptive follow-up are still open.

The current subtitle size and position are already satisfactory and should not be changed. The remaining issue is that subtitles appear excessively bright, as if rendered at full brightness, with a possible HDR-specific component.

First reproduce and isolate the behavior:

- compare the same subtitle and scene in SDR and HDR;
- check whether the excessive brightness is present on all content or primarily on HDR content;
- determine whether the effect comes from the subtitle color/opacity, HDR tone mapping, or the LG webOS compositor;
- verify whether native `<track>` and `::cue` styling on the LG G5 reliably supports the required color/opacity control.

The first implementation should provide a user-controlled subtitle brightness/opacity setting:

- keep the current size and screen position unchanged;
- apply the setting consistently to the subtitle text and any outline, shadow, or background;
- persist it across subtitle switching, seeking, source/quality changes, and player reloads;
- use the native track path if it can enforce the setting reliably;
- use a custom subtitle layer only if native styling cannot provide dependable control on webOS.

Treat scene-adaptive brightness as a follow-up enhancement, not a prerequisite for the manual control:

- investigate whether reliable, low-cost scene/luminance information is available on the LG G5 playback path;
- only implement automatic adaptation if it can work without destabilizing playback or adding unacceptable CPU/GPU cost;
- if frame analysis or webOS rendering limitations make it unreliable, keep the manual brightness control as the supported solution.

### 6. P2 — Make the build and TV-install loop reproducible

> **Audit: Completed, validation incomplete.** `docs/build-and-install.md` and `docs/ci.md` exist, CI
> builds and packages on every push, and the "Build and package" job — including the check that
> `out/kinopub.webos_v<version>.ipk` was produced — passed on `master` at `ccab33e` (run
> `30903800595`). What has never been confirmed is the second half: that the resulting IPK installs
> and launches on a TV. Nobody has walked the document end to end. Carried forward as **A14**, along
> with the stale claims in both documents that the project has no tests.

Update the project documentation so the fork can be built and installed without relying on instructions or release links from the original repository.

Document:

- the required Node/Yarn setup;
- `yarn build`;
- `yarn package` and the resulting IPK location;
- installation with `ares-install`;
- the LG Developer Mode session renewal step;
- the short manual smoke test after installation.

Keep lint/build checks part of the normal change loop, especially for player and media changes.

---

## Active roadmap

Ordered by priority, then by what unblocks what.

### A1 — Tell the viewer when playback has failed

> **Implemented, validation incomplete.** `src/components/player/playbackFailureNotice.tsx` shows a
> centred panel once every recovery path is spent, with the reason and a `Повторить` button that
> rebuilds the media pipeline from the frozen position. The terminal state is derived in
> `media.new.tsx` (`getFailure`): the stall watchdog must be exhausted, and the fatal budget too but
> only if a fatal error ever engaged it — requiring both unconditionally would have excluded the
> non-fatal CDN stall the watchdog exists for. It stays silent while anything is still being tried;
> a source played without hls.js falls back to the media
> element's own `error`, which is what closes the "`MediaRef.error` has no consumers" finding. Retry
> rebuilds rather than restarts, via a nonce in the media effect's dependencies, because a fatal
> hls.js error leaves the loading engine dead. See `docs/playback-diagnostics-spec.md` (Playback
> Failure Notice). **Not yet exercised on a TV** — the focus behaviour, the Enact interaction, and
> whether the retry resumes cleanly from the saved position are exactly what the manual checklist
> now covers and nobody has run.

- **Status:** Completed, validation incomplete
- **Depends on:** None
- **Priority:** High
- **Category:** Playback UX
- **Origin:** Review §4.1; the unbuilt half of item 4's recovery work
- **Problem or opportunity:** When every recovery budget is spent the application stops trying and
  says nothing. The viewer sees a frozen frame with no explanation and no action. The recovery-budget
  fix was correct — hammering the CDN forever was worse — but it converted an infinite-retry failure
  into a silent one.
- **Concrete evidence:** `MediaRef` exposes `error` (`media.new.tsx:132`, `:899-904`) and nothing
  reads it: `grep -rn "\.error\b"` over `src/components/player`, `src/components/media` and
  `src/views/video` returns no consumers. The exhausted paths at `media.new.tsx:423-433`, `:461-471`,
  `:501-502` and `:666-676` all return without any user-visible effect. The only surface that reports
  the state is the `recovery:` line in an overlay reached through Settings →
  `Диагностика воспроизведения`.
- **Motivation and expected benefit:** This is the single most visible remaining gap, and it also
  converts a dead end into a data source: whatever the viewer chooses (retry, lower quality, leave)
  is information the recovery episode currently has to guess at.
- **Proposed direction:** Surface the terminal state from the media layer — the two `RecoveryState`
  records already carry `exhausted`, `limit` and `lastReason` — and render a message with at least
  one action. Retry should rebuild the HLS instance rather than call `startLoad()` on a stopped
  engine. Check first what Enact's `VideoPlayer` already renders in a `NETWORK_NO_SOURCE` state
  (blind spot 9) rather than building over the top of it. Wording in Russian, matching
  `settings.tsx`. Keep it out of the way while recovery is still in progress: this is for the end
  state, not for every retry.
- **Dependencies and sequencing:** None. Pairs naturally with **A2**, which needs the same "the
  player is finished" moment.
- **Compatibility risks:** Low. New UI only; must not steal focus from the Enact controls or trap
  Back — the handler-ordering trap in **A9** applies.
- **Confidence:** code — high. Device behaviour of the Enact fallback: unknown.
- **Validation and acceptance criteria:** Reproduce a segment the CDN refuses; confirm the message
  appears only after both budgets report `exhausted`, that the offered action works, and that Back
  still leaves the player immediately. Add to `docs/playback-diagnostics-manual-test.md`.
- **Estimated scope:** Small–medium; one component plus a state passed up from `media.new.tsx`.

### A2 — Report the recovery episode when the viewer leaves

> **Implemented, validation incomplete.** An unmount-only effect in `media.new.tsx` closes any
> in-flight episode as `teardown`. It is deliberately separate from the source effect, whose cleanup
> also runs on every source change and therefore cannot tell a departure from a quality switch.
> `EpisodeEnd` now records _how_ an episode ended — `progress`, `grace-period`, `source-change`,
> `manual-retry`, `teardown` — carried to Sentry as `playback_episode_ended_by`, and only
> `grace-period` is reported at `error` level, since the rest were ended deliberately by someone.
> Four unit tests cover the new endings. **Still open:** whether the event is actually _delivered_
> rather than merely queued when the view tears down, and what happens when the viewer exits the app
> entirely (`window.close()` from `views.tsx:20`) rather than returning to the item screen.

- **Status:** Completed, validation incomplete
- **Depends on:** None
- **Priority:** High
- **Category:** Error reporting
- **Origin:** Review §4.2, §5
- **Problem or opportunity:** An in-flight recovery episode is discarded, unsent, when the player
  unmounts. The most common ending of a broken session — the viewer gives up and presses Back, or
  switches episode — produces no Sentry event at all, so `playback_episode` counts are drawn from a
  filtered sample that over-represents viewers who waited 30 s.
- **Concrete evidence:** `createPlaybackEpisodeTracker.reset` finishes an open episode as `abandoned`
  (`playbackEpisode.ts:235-241`) and is called from exactly one place, the source-change effect body
  at `media.new.tsx:350`. The effect's cleanup (`:543-562`) never touches `episodeRef`.
  `views/video/video.tsx:209` keys `<Player>` on `currentVideo.id`, so an episode change remounts the
  player through that same cleanup.
- **Motivation and expected benefit:** Without this, every conclusion drawn from episode outcomes is
  biased, including the answer to **A6**. It is a few lines.
- **Proposed direction:** Flush from the effect cleanup. Distinguish the ending: "abandoned by user"
  is a different fact from "abandoned after the grace period" and they should not be grouped
  together — either a distinct outcome or a tag. Note that Sentry may not flush before the page/view
  tears down; check whether the event is actually delivered, not merely queued.
- **Dependencies and sequencing:** Do before **A6**, whose data this corrupts.
- **Compatibility risks:** Very low. Guard against a double report when unmount and source change
  coincide — `finish()` already no-ops on a closed episode (`playbackEpisode.ts:101-103`).
- **Confidence:** code — high.
- **Validation and acceptance criteria:** A unit test that the tracker reports on a caller-driven
  teardown; on device, stall a stream, press Back, and confirm exactly one event with the new outcome
  arrives in Sentry.
- **Estimated scope:** Small.

### A22 — Report persistent non-fatal playback wedges

> **Implemented, validation incomplete.** Issue [#37](https://github.com/kaaburgh/kinopub.webos/issues/37)
> exposed a gap in the episode trigger: a TV can remain non-playable while hls.js continues to emit
> only non-fatal errors, leaving the `playback_id` on the QR capture with no searchable Sentry event.
> The watchdog now opens one `persistent-wedge` episode after the existing 8 s persistence threshold.
> It waits for actual media progress before calling the episode recovered, keeps appends that produce
> no playable range from faking recovery, and carries the latest safe HLS/media/watchdog context into
> the existing single report. Unit coverage and the media scenario assertion are in place. The
> scenario suite still requires the checked-in hls.js 1.6.15 dependency; the local checkout currently
> has an unrelated user edit to 1.0.10, and LG G5 delivery remains unvalidated.

- **Status:** Completed, validation incomplete
- **Depends on:** None
- **Priority:** High
- **Category:** Error reporting / playback diagnostics
- **Origin:** [#37](https://github.com/kaaburgh/kinopub.webos/issues/37), related to [#35](https://github.com/kaaburgh/kinopub.webos/issues/35) and [#36](https://github.com/kaaburgh/kinopub.webos/issues/36)
- **Evidence:** code — episode trigger, bounded breadcrumbing, context fields, and unit/scenario
  assertions; runtime — unit tests and typecheck under Node 14; device — not collected.
- **Follow-up:** Run the persistent-wedge capture on the LG G5 and confirm the event is delivered with
  the photographed `playback_id`, rather than merely queued during teardown.

### A3 — Report backend and API failures

> **Implemented, validation incomplete.** `src/api/base.ts` now reports three kinds of failure —
> `unreachable`, `http`, `malformed` — through `logApiFailure`, one per endpoint per kind per
> session. The return contract is unchanged, deliberately: the OAuth device flow reads
> `response.error`, so reporting sits beside the existing behaviour rather than reshaping it. Query
> strings are stripped and numeric path segments collapsed to `{id}` before anything is tagged, so
> no `access_token` leaves and tag cardinality stays bounded. Exempt from status reporting: 401, and
> the single OAuth grant that polls (`device_token`) — not the grants that start pairing or renew a
> session, since a broken refresh logs the viewer out and is the failure most worth hearing about.
> Transport failures are reported on every request. Rules and tests live in
> `src/utils/apiFailures.ts` (21 tests). **Not yet seen against the real backend** — the exemptions
> are reasoned from the code, and the one that would hurt if wrong is the polling exemption, since a
> regression there floods the quota during device pairing and nothing would say so until the quota
> was gone.

- **Status:** Completed, validation incomplete
- **Depends on:** None
- **Priority:** High
- **Category:** Error reporting / observability
- **Origin:** Review §4.10
- **Problem or opportunity:** The API client catches every failure and reports none of it. The stated
  experience is that problems are most often with KinoPub itself or with the app; the playback path
  now has an elaborate reporting pipeline and the backend-facing layer has nothing.
- **Concrete evidence:** `src/api/base.ts:56-73` returns `{ error: String(ex) }` on any thrown
  request. A non-2xx response is not treated as a failure at all, so an HTML error page surfaces as a
  JSON parse error with the status already discarded; `response.status === 401` clears tokens
  (`:62-64`) and then still calls `response.json()`. `grep -rn "logError\|logException\|Sentry"` over
  `src/` finds `logException` used once (`hooks/useDeviceAuthorizationEffect.ts:53`) and `logError`
  (`utils/logging.ts:73`) never called.
- **Motivation and expected benefit:** Turns "the app was weird last night" into a specific endpoint,
  status and time. It is also the cheapest large gain available, because the reporting and scrubbing
  infrastructure already exists.
- **Proposed direction:** Preserve the HTTP status and the endpoint path; report non-2xx and thrown
  requests with the same one-per-session-per-kind discipline `logPlaybackIssue` uses
  (`logging.ts:112-116`) so a flapping backend cannot flood the quota. Endpoint path and status only
  — never the query string, which carries `access_token` (`base.ts:49-54`); `scrubUrls` already
  reduces URLs to hostnames but the token is a parameter, so it must not be put in the message in the
  first place. Consider whether 401 should be reported at all, since it is a normal expiry.
- **Dependencies and sequencing:** Best done with **A9**, which touches the same request path.
- **Compatibility risks:** Low, but the `{ error }` return shape is consumed by callers; changing it
  is a larger change than adding reporting beside it.
- **Confidence:** code — high.
- **Validation and acceptance criteria:** Point the client at an unreachable host and confirm one
  Sentry event with the status and path, no token, and no repeat flood. A unit test over the error
  mapping if `base.ts` is refactored enough to allow one.
- **Estimated scope:** Small–medium.

### A4 — Decide what telemetry this fork sends, and where

> **Decided and implemented.** All three sub-decisions were made by the repository owner:
>
> 1. **The GA tag is gone entirely**, not repointed. Sentry already covers what it collected:
>    `@sentry/tracing`'s `BrowserTracing` records CLS, LCP, FID, FCP and TTFB as pageload
>    measurements (`node_modules/@sentry/tracing/dist/browser/metrics.js`), the same five metrics the
>    GA callback forwarded, into a project this fork owns. On the TV the tag collected little
>    besides: the app is not served over http, which is what makes `IS_WEB` false and selects
>    `MemoryRouter`, so no page view after the first was ever recorded. Removed with it:
>    `src/utils/analytics.ts`, `src/reportWebVitals.ts`, the `web-vitals` dependency and the
>    `@types/gtag.js` types. Nothing is left that could hit the `ReferenceError` the earlier review
>    of this item flagged, because no `gtag` reference survives.
> 2. **The Pages deployment is removed** — `deploy-pages.yml` deleted. It was unused, and publishing
>    a bundle carrying this fork's Sentry DSN meant anonymous visitors' errors were charged to a
>    project meant for one television. Decommissioning the already-published `gh-pages` branch and
>    turning Pages off in repository settings is a manual step for the owner; the workflow removal
>    only stops new deployments.
> 3. **No Sentry runtime gate is needed**, since the web surface is going away. `docs/ci.md` records
>    that gating comes first if a web build is ever wanted again.
>
> `netlify.toml`, a second inherited deployment config with the same consequence, was removed in a
> follow-up. Two further decisions were taken by the owner and split out rather than folded in here:
> a web build is still wanted, but for reproducing playback problems rather than for publishing
> (**A18**), and the DSN stays in source for now with rotation and relocation tracked separately
> (**A19**).

- **Status:** Completed
- **Depends on:** None
- **Priority:** High
- **Category:** Privacy / configuration
- **Origin:** Review §4.9, §4.13
- **Problem or opportunity:** The Sentry DSN was replaced on an explicit argument — telemetry was
  going to a third party and was invisible to whoever debugs this fork — and an equivalent inherited
  channel was left in place. Separately, `master` is published publicly with the new DSN embedded.
- **Concrete evidence:** `public/index.html:8-15` loads
  `https://www.googletagmanager.com/gtag/js?id=G-2QFN9YLY57` at startup and configures that
  inherited property; `src/utils/analytics.ts` feeds Web Vitals into it from `src/index.tsx:35`. The
  argument for replacing the DSN is recorded verbatim at `docs/playback-diagnostics-spec.md:264-266`
  and applies unchanged to this tag. `.github/workflows/deploy-pages.yml` publishes every push to
  `master`, and `git ls-remote --heads origin` shows `gh-pages` live at `a6dc3619`, so the bundle
  containing `logging.ts:16`'s DSN is served to anonymous visitors.
- **Motivation and expected benefit:** Ends an inconsistency between a stated decision and the
  shipped artefact, and stops web visitors from consuming the owner's Sentry quota or posting to the
  DSN.
- **Proposed direction:** Three separable decisions. (1) The GA tag: remove, or repoint at a property
  the owner controls — removing also deletes an unconditional external request at startup, which is
  worth something on a TV. (2) The Pages deployment: keep, or restrict it. (3) If Pages stays,
  consider gating Sentry initialisation on the webOS runtime so only the TV app reports. Whichever is
  chosen, record the reasoning in the spec so the next reader does not have to re-derive it.
- **Dependencies and sequencing:** None. Do before drawing conclusions from Sentry volume.
- **Compatibility risks:** Removing the inline script alone would break the app at runtime. `gtag` is
  declared only by that script (`public/index.html:12`), and optional chaining does not protect
  against an _undeclared_ identifier — `gtag?.(…)` at `analytics.ts:6` would throw
  `ReferenceError: gtag is not defined` rather than no-op. `src/index.tsx:35` still passes
  `sendWebVitalsToGoogleAnalytics` to `reportWebVitals` unconditionally, and
  `src/reportWebVitals.ts:4-11` registers it with five `web-vitals` callbacks, so the throw would
  land on real metric events. TypeScript will not catch it: `@types/gtag.js` declares the global.
  Remove the callback and its wiring together with the tag, or guard with
  `typeof gtag !== 'undefined'`.
- **Confidence:** code — high. Whether the Pages deployment is wanted is the owner's call, not a
  defect.
- **Validation and acceptance criteria:** Load the built app with the network panel open and confirm
  no request to `googletagmanager.com`; confirm the intended Sentry behaviour on both surfaces.
- **Estimated scope:** Small, once the decisions are made.

### A5 — Validate the decode-health thresholds on the LG G5

- **Status:** Investigation first — blocked on device evidence
- **Depends on:** None
- **Priority:** High
- **Category:** Diagnostics correctness
- **Origin:** Review §5; narrowed scope of item 4
- **Problem or opportunity:** The badge's thresholds are reasoned, not measured. If the panel's
  baseline dropped-frame ratio during clean playback is above 1%, the badge is permanently yellow and
  is worse than no badge; if it never reaches 1% even while visibly stuttering, it never appears.
- **Concrete evidence:** `DECODE_WARNING_RATIO = 0.01` / `DECODE_SEVERE_RATIO = 0.05`
  (`decodeHealth.ts:48-49`), with the module itself stating there is no normative threshold
  (`:4-5`). `DECODE_MIN_FRAMES = 120` and the 30 s window are equally unmeasured. Nothing in the
  repository records what an LG G5 reports.
- **Motivation and expected benefit:** This gates **A13**. Acting on an unvalidated signal is exactly
  what item 4 was narrowed to avoid, so the narrowing is only honest if the validation happens.
- **Proposed direction:** No code change first. Play 10–15 clean minutes with the overlay open and
  record `frames`, `dropped` and `dropped %`; repeat on content known to stutter and on 2160p. Then
  decide whether the thresholds move, whether `DECODE_MIN_FRAMES` is right at TV frame rates, and
  whether `getVideoPlaybackQuality` is implemented usefully on this firmware at all — the overlay
  shows `not available` if it is absent (`playbackDiagnostics.tsx:1038`).
- **Dependencies and sequencing:** Blocks **A13**. Independent of everything else.
- **Compatibility risks:** None; observation only.
- **Confidence:** device — none yet. That is the point of the item.
- **Validation and acceptance criteria:** Numbers for clean and stuttering playback recorded in this
  roadmap, and either a justified threshold change or an explicit "the defaults hold, and here is the
  measurement that says so".
- **Estimated scope:** Small — one viewing session.

### A21 — Establish the newest known-good hls.js baseline on the LG G5

- **Status:** Investigation first — restore the known-good baseline, then search for the newest safe release
- **Depends on:** None
- **Priority:** Medium
- **Category:** Playback compatibility
- **Origin:** hls.js upgrade PRs #26–#30 and the LG G5 regression observed after #28
- **Problem or opportunity:** `master` currently pins `hls.js@1.7.0-rc.2`, but a real title that plays
  on commit `c07b9c3` immediately before that upgrade wedges on the upgraded build. The scenario
  suite passes on 1.7.0-rc.2 because it exercises HLS/network/recovery logic, not the television's
  decoder and real MSE implementation. Keeping a version with a confirmed device regression as the
  development baseline risks building more recovery logic around a library compatibility problem.
- **Concrete evidence:** PR #28 upgraded from 1.0.10 to 1.7.0-rc.2 and ran the scenario suite against
  both versions successfully. PR #30 then captured the device-only regression: playback stopped at
  0.2 s with `readyState=1` and `bufferAppendNoProgress`, while the same title played on the commit
  immediately before the upgrade. PR #27's 1.5.20 experiment also exposed a separate comparison
  hazard: newer package entry points can resolve to the ESM build with different transmuxer-worker
  behaviour, so a version test is only meaningful if the actual browser bundle/runtime path is held
  constant and recorded.
- **Motivation and expected benefit:** Put day-to-day development back on a version that is known to
  work on the target television, while still finding the newest safe hls.js rather than freezing the
  dependency forever. This gives future playback changes a trustworthy baseline and turns the
  upgrade from a one-shot leap into a falsifiable compatibility experiment.
- **Proposed direction:** Separate operational safety from the investigation. First, revert the
  working baseline to `hls.js@1.0.10` in a dedicated change without reverting any application fixes,
  diagnostics, scenario tests, or recovery work added since the upgrade. Keep the cross-version
  scenario suite green. Then test the newest stable hls.js candidate available at investigation time
  and sample older stable checkpoints as needed to understand compatibility. Treat every candidate as
  an independent device result: a bad midpoint does not rule out a later release that may have fixed
  the regression, so continue testing later releases instead of narrowing a single monotonic
  first-bad/newest-good boundary. For each candidate, verify the actual bundled hls.js entry point and
  worker behaviour before comparing results. Use the same LG G5 matrix every time: the known-regressing
  title from cold start; a normal HLS title; seek into an unbuffered region; Auto and fixed-quality
  switching; alternate audio selection; and an HDR title. Do not promote a candidate from
  browser/scenario evidence alone.
- **Dependencies and sequencing:** The rollback should precede unrelated playback-behaviour changes
  so those changes are evaluated against a known-good library baseline. The version search can then
  run independently, but conclusions in **A6** and **A20** must record which hls.js baseline produced
  the evidence. **A18** remains useful as a fast pre-device filter, not as the acceptance gate.
- **Compatibility risks:** High if treated as a mechanical dependency bump. hls.js changed loader
  deadlines, retry ownership, package entry points and worker behaviour across the range already
  tested. A candidate can pass every repository test and still fail on webOS MSE/decoder behaviour;
  conversely, a scenario difference may be an intentional upstream policy change rather than a
  regression. Keep version-only changes isolated from player-policy changes.
- **Confidence:** device — high that 1.7.0-rc.2 introduced a regression for the observed title;
  runtime — high that 1.0.10 and 1.7.0-rc.2 differ in error/retry behaviour; unknown which releases
  above 1.0.10 are safe on the target device.
- **Validation and acceptance criteria:** The operational rollback leaves the complete repository
  test/scenario suite green and restores the known-regressing title on the LG G5. The investigation
  ends with a recorded newest-known-good hls.js version that passes the same suite plus the complete
  device matrix above, with the bundled entry point/worker mode recorded. A failed candidate does not
  terminate testing of later releases. If no tested candidate above 1.0.10 passes, keep 1.0.10 pinned
  and record the tested candidates and their results rather than weakening the device gate.
- **Estimated scope:** Small for the rollback; medium for the version search because device passes,
  not code volume, are the limiting factor.

### A6 — Answer whether the stall watchdog rescues playback

- **Status:** Investigation first — blocked on device evidence
- **Depends on:** A2
- **Priority:** Medium
- **Category:** Playback recovery
- **Origin:** Review §7.2; the unanswered half of item 1
- **Problem or opportunity:** The watchdog's escalation shape — restart at 8 s, playlist reload at
  20 s, three reloads — is a guess. The `playback_recovered_after` tag was built specifically to
  falsify it and no data from it appears anywhere. Related and still unanswered: _why_ the CDN
  returns `HTTP 0` for particular segments after a seek.
- **Concrete evidence:** `STALL_RESTART_AFTER`, `STALL_RELOAD_AFTER`, `STALL_MAX_RELOADS`
  (`media.new.tsx:64-66`) carry no derivation. The tag is set at `logging.ts:177-179`. `ROADMAP.md`
  item 1 records two different segments (`sn 57`, `sn 46`) failing on the same title and host while
  the opening of the file buffered normally.

  **The hls.js upgrade changes the arithmetic, and the scenario tests measured it.** Against a
  hanging edge on 1.0.10, hls.js produced non-fatal timeouts every twenty seconds and did not reach
  a fatal error for about four and a half minutes; the watchdog acted at sixty seconds. That gap was
  the whole case for having a watchdog. On 1.7.0-rc.2 the same scenario reaches a fatal error at
  seventy seconds — hls.js abandons a silent request after `maxTimeToFirstByteMs` (ten seconds)
  rather than the two-minute whole-response deadline, and its gap controller reports the frozen
  picture itself as a non-fatal `bufferStalledError` at fifty seconds. The watchdog still moves
  first, but by ten seconds instead of three minutes.

  What has _not_ changed is the part that matters most: neither the timeouts nor `bufferStalledError`
  make hls.js refetch the playlist, and fresh segment URLs are what actually moves a stream off a
  dead edge. So the watchdog's reload still does something nothing else does — but its restart step,
  which only re-plans against the same URLs, now overlaps almost entirely with hls.js's own
  escalation and is the first candidate for removal if the device data supports it.

  **First real data, from a Sentry episode captured on the TV
  ([#18](https://github.com/kaaburgh/kinopub.webos/issues/18)).** Two things it settles and one it
  does not:

  - _The failure is edge-specific, not only segment-specific._ Every request to
    `…ams-static-01.cdntogo.net` for that asset returned `0` or `502` across two minutes, while
    every request to `…ams-static-03.cdntogo.net` returned `200` — including the playlist retries
    that hls.js made after each failure. So a working edge was reachable throughout. The playlist
    reload does move to `-03`, but the segment URLs it returns still point at `-01`, which is why
    retrying changes nothing. Whether the app can influence that is the open question; it may be a
    CDN-side problem no client can route around.
  - _The watchdog escalation ran and did not rescue playback._ `watchdog-restart` at 136 s, then
    `watchdog-reload`, and the reload immediately provoked a fatal audio-track error. The episode
    closed as `recovered … via media-recover`, but that "recovery" was `recoverMediaError()`
    restarting the film from the beginning — so the success metric counted a destructive restart as
    a success. Treat `playback_recovered_after` totals with that in mind until more episodes exist.
  - _Still unanswered:_ why the object is missing from that edge in the first place, and whether the
    sequential-play experiment below reproduces it.

  **The reload is more expensive than it looked.** Every `watchdog-reload` discards the entire
  buffer: `loadSource()` triggers `MANIFEST_LOADING`, which triggers `BUFFER_RESET`, which removes
  the SourceBuffers. There is no cheaper way to refresh a VOD playlist in this hls.js version (see
  **A7**, dropped for that reason). So the escalation trades everything already downloaded for a
  chance at fresh segment URLs, and the episode above suggests it did not take that chance
  successfully. That raises the bar for keeping it: if the data says the reload rarely rescues
  playback, removing it is a real option rather than a tidy-up.

- **Motivation and expected benefit:** Either the reload works, in which case the numbers can be
  tuned with evidence and the fatal-retry budget could arguably escalate to it sooner; or it does
  not, in which case a third of the recovery machinery is ceremony and should be cut.
- **Proposed direction:** Two parts. (a) Collect `playback_recovered_after` over real use and group
  by it. (b) Run the discriminating experiment for the `HTTP 0` cause: play sequentially to a
  timestamp that fails after a seek, without seeking. If it plays, the trigger is the seek, not the
  segment — which points at range requests or token scoping rather than a bad edge.
- **Dependencies and sequencing:** Needs **A2** first, or the sample is biased.
- **Compatibility risks:** None; observation only.
- **Confidence:** device — none. `code` for the mechanism.
- **Validation and acceptance criteria:** A recorded distribution of `playback_recovered_after`
  values, and a stated conclusion about the seek hypothesis, both written into this roadmap.
- **Estimated scope:** Small in code, spread over real viewing.

### A7 — Stop the watchdog's playlist reload from flushing the buffer

- **Status:** Dropped — the premise was wrong
- **Depends on:** None
- **Priority:** —
- **Category:** Playback recovery
- **Origin:** Review §4.3, which is corrected in `TECHNICAL_REVIEW.md`

**Why it is dropped.** The item claimed the buffer survived a watchdog reload and was discarded by
the `currentLevel` assignment in `MANIFEST_PARSED`. Only the second half was true, and it does not
matter, because the buffer is already gone by then.

`loadSource()` triggers `MANIFEST_LOADING`. `stream-controller.onManifestLoading()` responds with
`BUFFER_RESET` (`node_modules/hls.js/dist/hls.js:9182-9189`), and `BufferController.onBufferReset()`
calls `mediaSource.removeSourceBuffer()` for every buffer type (`:4341-4365`). So every reload
discards everything buffered, before the new manifest is parsed, whichever property the level is
then assigned to. An implementation of this item was written, reviewed, and reverted for exactly
that reason.

The original finding rested on a real observation — `loadSource()` does not detach the media element
when the URL is unchanged — and drew a conclusion from it that a second path invalidated. Checking
one mechanism that could have preserved the buffer, then concluding it was preserved, is the mistake
worth remembering here.

**What replaces it.** Nothing to build: there is no public API in this hls.js version to refresh a
VOD playlist without the reset. `startLoad()` does not refetch level details, and the level
controller's playlist loading is internal. The cost is therefore a property of the reload
escalation, and belongs in the decision about whether that escalation earns its place — see **A6**,
which now records it.

### A8 — Make the QR capture carry everything the overlay shows

> **Implemented, validation incomplete.** The QR payload now uses format v2 and carries the latest
> fragment separately for each HLS stream, the decode-health severity, and an explicit
> `SOURCE_CHANGED` seam across HLS replacement. The reference decoder remains backward-compatible
> with v1 captures. Regression coverage exercises v2 round-tripping, legacy v1 decoding, and settled
> in-place quality switches before HLS replacement. **Still open:** the two acceptance checks below
> require an LG G5 capture with alternate audio and a quality switch. The problem/evidence/direction
> below are retained as the pre-implementation rationale.

- **Status:** Completed, validation incomplete
- **Depends on:** None
- **Priority:** Medium
- **Category:** Diagnostics correctness
- **Origin:** Review §5, §4.6; follow-up to item 2
- **Problem or opportunity:** The capture is how a device observation reaches anyone who can act on
  it, so anything on the screen but not in the capture is invisible to the person diagnosing. The
  most recent commit added a per-stream distinction to the screen and not to the capture. Separately,
  the event history is the one piece of diagnostic state not reset when the HLS instance changes, so
  a capture taken after a quality switch silently mixes two sources.
- **Concrete evidence:** `ExportCapture.lastFragment` is a single object
  (`diagnosticsExport.ts:95-101`) populated from `lastFragments.main` only
  (`playbackDiagnostics.tsx:865`), while the overlay renders one line per stream (`:1078-1080`). The
  reset effect clears six pieces of state at `playbackDiagnostics.tsx:679-686` and not `history`.
  `docs/playback-diagnostics-spec.md:332-334` states the equivalence rule this violates, and `:255`
  requires diagnostic state to be discarded when playback unmounts.
- **Motivation and expected benefit:** Restores the property the spec asks for, and removes a way for
  a capture to mislead.
- **Proposed direction:** Carry `lastFragments` per stream on the `f|` line (repeat the line with a
  stream tag; the decoder skips unknown lines by design, so a `FORMAT_VERSION` bump plus a matching
  `scripts/decode-diagnostics.js` change in the same commit is the contract). For history, prefer a
  `source changed` marker over clearing — history across a switch is often what you want to see, as
  long as the seam is visible. Also add the decode-health severity, which the badge shows and the
  capture does not.
- **Dependencies and sequencing:** None.
- **Compatibility risks:** Low, but the format is versioned for a reason: encoder and decoder must
  change together, and the payload must not outgrow `MAX_CHUNKS` (`diagnosticsExport.ts:28`) — the
  encoder already halves history and finally throws rather than emit an unreadable header (`:359-370`).
- **Confidence:** code — high.
- **Validation and acceptance criteria:** Take a capture on a stream with alternate audio; the
  decoded report shows both streams and matches the screen. Switch quality, capture, and confirm the
  seam is visible in the decoded event list.
- **Estimated scope:** Small–medium; three files must move together.

### A9 — Bound API requests, and stop Back from waiting on one

> **Implemented, validation incomplete.** All API requests now have a 15 s deadline. Runtimes with
> `AbortController` abort the underlying fetch; the Chrome-35-compatible fallback rejects the caller
> on the same deadline without assuming that DOM API exists. Back no longer awaits the player progress
> sync, and the remote-key stack has explicit priorities so overlays/local interception run before
> route navigation independently of mount or re-registration order. Focused tests cover the timeout
> fallback, successful-request timer cleanup, priority ordering, and popup consumption after a later
> default-priority registration. Exact-head CI was green on implementation head
> `90559219b7d1ddb6a71aa2d40e9c789b996d2c02`. **Still open:** the acceptance checks below require a
> real network failure on the target runtime/device; synthetic tests do not establish real webOS
> network behaviour.

- **Status:** Completed, validation incomplete
- **Depends on:** None
- **Priority:** Medium
- **Category:** Robustness / UX
- **Origin:** Review §4.11
- **Problem or opportunity:** No request in the application had a deadline, and the remote-key stack
  awaited each handler in turn — so leaving the player could wait for a progress-sync POST to finish
  or fail. During a network failure, which is when a viewer most wants to leave.
- **Concrete evidence:** `src/api/base.ts` now enforces a 15 s deadline with an `AbortController` guard
  and a Promise timeout fallback; `src/components/player/player.tsx` starts progress sync without
  awaiting it on Back; `src/utils/keyboard.ts` orders handlers by explicit priority while preserving
  newest-registration-first semantics within one priority. Views navigation is lowest priority and
  popup/diagnostics interception uses overlay priority. Unit coverage exercises the no-
  `AbortController` path and deterministic Back ordering.
- **Motivation and expected benefit:** Makes the app escapable in the one state where it previously
  was not, and makes every API call fail in bounded application time.
- **Implemented direction:** The shared API path races every request against a 15 s timeout and aborts
  the underlying fetch where supported; older webOS falls back to a bounded caller-visible rejection.
  Progress sync on Back is fire-and-forget. `registerButtonHandler` exposes explicit numeric priority,
  with overlay/local handlers above route navigation so ordering no longer depends on mount timing.
- **Dependencies and sequencing:** Pairs with **A3**; timeout failures continue through the existing
  API error/reporting path.
- **Compatibility risks:** `AbortController` is Chrome 66 and the target is `chrome 35`, so the guarded
  fallback is intentional and covered by tests. On the fallback path the underlying legacy fetch can
  continue after the caller has timed out; the application no longer waits for it.
- **Confidence:** code/runtime — high for bounded caller-visible behaviour and explicit handler
  ordering; device — not yet established for real network-drop behaviour.
- **Validation and acceptance criteria:** With the network dropped mid-playback, Back leaves the
  player without a perceptible delay; a request against an unreachable host fails within the timeout.
  These two real-network observations remain outstanding.
- **Estimated scope:** Small.

### A10 — Add a render error boundary

> **Implemented, validation incomplete.** `ErrorBoundary` now wraps `Views` in `App/App.tsx`, catches
> render/lifecycle failures below the routing surface, reports the original exception through
> `logException`, and replaces the failed tree with a Russian reload fallback instead of a black
> screen. Focused regression coverage deliberately throws from a child and verifies fallback
> rendering, exactly one reporting call, and the reload action. **Still open:** LG-device evidence for
> remote focus/readability and actual reload recovery, plus confirmation that the real Sentry event is
> delivered rather than only that the reporting helper was called.

- **Status:** Completed, validation incomplete
- **Depends on:** None
- **Priority:** Medium
- **Category:** Robustness
- **Origin:** Review §4.12
- **Problem or opportunity:** A render-time throw unmounts the whole tree and leaves a black screen
  with no route back — on a TV, that means killing the app from the launcher.
- **Concrete evidence:** `src/components/errorBoundary/errorBoundary.tsx` implements the class
  boundary and calls `logException` from `componentDidCatch`; `src/App/App.tsx` wraps `Views` with it.
  `src/components/errorBoundary/errorBoundary.test.tsx` mounts a deliberately throwing child and
  verifies the fallback, one report, and the reload action.
- **Motivation and expected benefit:** Converts the worst failure mode the app has into a message
  with a way out.
- **Implemented direction:** Keep one boundary around `Views`; the fallback uses the existing Button
  component with focus requested and reloads the page. Event-handler and asynchronous exceptions are
  deliberately outside the boundary's scope. A tighter player-only boundary remains a possible
  follow-up only if evidence shows it is useful; it is not part of A10's completed implementation.
- **Dependencies and sequencing:** None.
- **Compatibility risks:** Low. Boundaries do not catch errors in event handlers or async code, so
  this is not a general safety net. Remote focus and real page reload behaviour remain device-only.
- **Confidence:** code — high for render/lifecycle containment and the reporting/reload wiring;
  device — not yet established for focus/readability/reload recovery or Sentry delivery.
- **Validation and acceptance criteria:** The focused regression test establishes that a throwing
  child renders the fallback, invokes `logException` once, and can invoke reload. On the LG G5,
  deliberately trigger a render failure and confirm the fallback is readable, the reload action can
  be focused/activated with the remote, reload recovers the app, and exactly one Sentry event arrives.
- **Estimated scope:** Small.

### A11 — Measure the cost of always-on diagnostics collection

- **Status:** Investigation first
- **Depends on:** None
- **Priority:** Medium
- **Category:** Performance
- **Origin:** Review §4.7; follow-up to item 2
- **Problem or opportunity:** Diagnostics collection runs for the whole playback session whether or
  not anything is on screen, and its cost on TV hardware has never been measured — least of all
  during the failure storm, when the device is already struggling.
- **Concrete evidence:** The listener effects depend on `target.video` / `target.hls`, not `visible`
  (`playbackDiagnostics.tsx:645`, `:670`), and the component is always mounted (`player.tsx:255`).
  Every HLS event runs `getHlsEventDetails` (`:551-586`) and `pushHistory` → `setHistory` with a fresh
  30-element array (`:604-615`). Each `ERROR` triggers three state updates (`:767-772`). Item 4
  records ~2.9 failed requests per second during the captured failure.
- **Motivation and expected benefit:** Either it is cheap and can be forgotten, or diagnostics are
  making the failure they are observing worse — which would matter a great deal.
- **Proposed direction:** Measure before changing anything. The obvious fix (collect only while
  visible) destroys the feature's main value, because the run-up to a stall is what you want to see.
  If it is expensive, cheaper shapes exist: keep history in a ref and copy into state only while
  visible; drop the high-frequency `BUFFER_APPENDING`/`BUFFER_APPENDED` pair when hidden; coalesce
  repeated `ERROR`s the way `playbackEpisode` already does.
- **Dependencies and sequencing:** Independent.
- **Compatibility risks:** Any change here risks losing exactly the events the overlay exists to
  show; the acceptance criteria must include "the history still covers the run-up to a stall".
- **Confidence:** code — high that it runs; no evidence about cost.
- **Validation and acceptance criteria:** A recorded before/after observation on the TV during normal
  playback and during a failure — dropped-frame ratio and subjective UI responsiveness are the
  available instruments.
- **Estimated scope:** Small to measure; unknown to fix.

### A18 — A web build for reproducing playback problems, with scripted scenarios

- **Status:** Implemented, validation incomplete — scripted scenarios, the browser Sentry gate, and all five
  local browser procedures (refused segment, non-fatal stall, unbuffered seek, bandwidth collapse, and teardown) exist; real-backend browser validation remains open
- **Depends on:** None
- **Priority:** Medium
- **Category:** Test infrastructure
- **Origin:** Requested after **A4** removed the public deployment; enables **A5**, **A6**, **A11**

> **The scripted half is done, in-process rather than in a browser.** > `src/components/media/media.scenarios.test.tsx` mounts the real player over a scripted CDN
> (`src/testing/hlsCdn.ts`) and drives the real hls.js through the observed failures: a refused
> segment, a hanging edge, an edge escaped by refetching the playlist, the terminal failure notice,
> and a manual retry. The substitution point is hls.js's `config.loader`, so the same scenarios can
> be re-run against a new hls.js to see which of this player's workarounds it has made redundant —
> see [Playback scenario tests](./docs/playback-scenario-tests.md). They run in CI in under two
> seconds because the clock is virtual.
>
> They found one live defect immediately, now fixed: see **A20**.
>
> Multi-level scenarios work too: the mock reports each fragment at the size its level's declared
> bitrate implies and takes a configurable link time to deliver it, so hls.js's bandwidth estimate
> is meaningful and its level choice is deterministic. That covers quality switching, moving between
> audio groups, and ABR adapting to a link that cannot carry the top rendition.
>
> **The browser-safety prerequisite is now implemented.** `src/utils/enviroment.ts` exposes the
> existing HTTP/HTTPS origin distinction through a testable runtime helper, and `src/utils/logging.ts`
> skips `Sentry.init` for that browser runtime while preserving the packaged `file:` / webOS path.
> Focused regression coverage checks HTTP, HTTPS, and packaged-file classification. This prevents a
> local or preview browser reproduction session from reporting into the television's Sentry project.
>
> **The first browser procedure now exists, but has not yet produced runtime evidence.** > `docs/browser-scenarios/refused-segment.js` launches Chromium through a locally available
> Playwright installation and leaves ordinary backend/CDN traffic real. After playback is visibly
> progressing, the operator arms the script; it will select a target only when both an explicit CDN
> hostname and a mandatory non-secret media-fragment path discriminator match, then abort that exact
> request and its retries. The selected full URL stays in process memory and is never printed. The
> documented expected end state is the existing `Повторить` terminal failure notice. If a safe path
> discriminator cannot distinguish media segments from keys, subtitles, and unrelated CDN requests,
> the procedure fails closed and the run must not be counted as refused-segment evidence. This
> GitHub-only agent environment has not executed the real-backend/CDN procedure, so reproducibility
> remains unestablished rather than inferred from code or CI.
>
> **The second browser procedure now exists, also without runtime evidence.** > `docs/browser-scenarios/nonfatal-stall.js` keeps requests pending at Playwright's routing boundary
> only when the same explicit CDN-host and mandatory non-secret media-fragment path discriminator
> match. It opens the existing diagnostics before arming and counts a run as non-fatal-stall evidence
> only when watchdog restart/reload progression is visible and fatal recovery does not become causal
> before the terminal notice. The companion Markdown procedure records setup, cleanup, privacy, and
> the browser-vs-TV evidence boundary. This GitHub-only agent environment has not executed it against
> the real backend/CDN, so reproducibility remains unestablished.
>
> **The third browser procedure now exists, also without runtime evidence.** > `docs/browser-scenarios/unbuffered-seek.js` chooses a forward target outside the live `<video>.buffered`
> ranges, performs only `video.currentTime = target`, and leaves backend/CDN traffic real. Matching
> media-fragment requests are observed only behind the same explicit CDN-host and mandatory non-secret
> fragment-path discriminator. The named application outcome is `resumed`, `terminal-failure`, or
> `timeout`; `resumed` requires observable playback progress after the seek target has been reached,
> rather than treating the assigned `currentTime` as recovery. The companion Markdown procedure records
> setup, cleanup, privacy, and the browser-vs-TV evidence boundary. This GitHub-only agent environment
> has not executed it against the real backend/CDN, so reproducibility and the cause of the TV's
> `HTTP 0` remain unestablished.
>
> **The fourth browser procedure now exists, also without runtime evidence.** > `docs/browser-scenarios/bandwidth-collapse.js` keeps a genuine multi-level HLS stream in Auto mode
> and uses Chromium DevTools Protocol network emulation to shape the browser network path without
> manufacturing hls.js events, level state, or responses. A run is accepted only when diagnostics
> show a lower `currentLevel` and the video then advances by at least the configured progress window
> after that first observed downshift. The configured throughput is synthetic and is not a measured
> connection threshold. The companion Markdown procedure records setup, cleanup, privacy, and the
> browser-vs-TV evidence boundary. This GitHub-only agent environment has not executed it against the
> real backend/CDN, so reproducibility remains unestablished.
>
> **The fifth browser procedure now exists, also without runtime evidence.** > `docs/browser-scenarios/teardown.js` keeps matching media-fragment requests pending behind the same
> explicit CDN-host and mandatory non-secret fragment-path discriminator until the existing terminal
> failure notice appears. It then sends one Escape/Back through the application's normal key path and
> accepts success only when the route leaves the player and the `<video>` element is unmounted. The
> companion Markdown procedure records setup, cleanup, privacy, and the browser-vs-TV evidence
> boundary. This GitHub-only agent environment has not executed it against the real backend/CDN, so
> reproducibility remains unestablished.
>
> All planned browser procedures now exist; what remains open is executing them reproducibly against
> the real backend/CDN. The previous plan to use that browser harness to prove **A2** Sentry delivery is no longer valid:
> the gate intentionally disables Sentry in browser sessions, so actual teardown-event delivery
> remains a television acceptance check under **A2**, not an A18 browser result.

- **Problem or opportunity:** Every open investigation in this roadmap is gated on somebody sitting
  in front of a television at the moment a rare failure happens, then reading it back through a QR
  code. A browser build would put the same player somewhere with real developer tools — network
  throttling, request blocking, a debugger, `chrome://media-internals` — and let a failure be
  _induced_ rather than waited for. That turns "reproduce the stall" from an evening of luck into a
  scripted run.
- **Concrete evidence:** The app already runs in a browser: `src/utils/enviroment.ts` selects
  `BrowserRouter` when the origin is http, `yarn start` serves it, and until **A4** it was built and
  published on every push to `master`. What was removed was the _public_ deployment, not the
  capability. `isWebRuntime` now makes that distinction directly testable, and browser sessions skip
  `Sentry.init` while packaged `file:` execution keeps the television telemetry path.
  `docs/browser-scenarios/refused-segment.js` plus its README define the refused-segment procedure,
  `docs/browser-scenarios/nonfatal-stall.js` plus its companion Markdown file define the second local
  procedure, `docs/browser-scenarios/unbuffered-seek.js` plus its companion Markdown file define the
  third, `docs/browser-scenarios/bandwidth-collapse.js` plus its companion Markdown file define the
  fourth, and `docs/browser-scenarios/teardown.js` plus its companion Markdown file define the fifth.
  The request-targeting procedures preserve the mandatory fail-closed fragment discriminator and all
  five preserve the privacy boundary; none of the real-backend/CDN runs has yet been executed. Meanwhile **A5** (decode thresholds), **A6**
  (does the watchdog rescue anything, and why does the CDN answer `HTTP 0` after a seek) and **A11**
  (cost of always-on diagnostics) still need device evidence; the browser harness can shorten
  reproduction work but cannot replace those target observations.
- **Motivation and expected benefit:** The specific scenarios worth scripting are the ones already
  observed on the TV and never reproduced on demand:
  - a segment the CDN refuses — the documented procedure now exists; once executed reproducibly it
    should confirm the fatal-error budget drains, the backoff escalates, and the failure notice appears;
  - a non-fatal stall — the documented procedure now exists; once executed reproducibly it should
    confirm the watchdog's restart/reload escalation and then the notice without fatal recovery
    becoming causal first;
  - a seek into an unbuffered region — the documented procedure now exists; once executed
    reproducibly it should distinguish actual post-seek playback progress from merely reaching the
    assigned target while recording only bounded matching media-fragment outcomes;
  - bandwidth collapse — the documented procedure now exists; once executed reproducibly it should
    show a lower HLS level followed by continued playback progress under a synthetically shaped
    Chromium network path;
  - a stall followed by leaving the player — the documented procedure now exists; once executed
    reproducibly it should exercise the application-side teardown path through normal Back handling,
    route change, and video unmount. Actual Sentry delivery remains under **A2** because browser
    Sentry is deliberately disabled.
- **Proposed direction:** Local or preview-only, never a permanent public URL: **A4** removed that
  for a reason and this must not quietly restore it. The browser Sentry gate and all five planned
  procedures are now in place. Execute those procedures before claiming they are reproducible. Keep
  the scripts beside `docs/` as documented procedures, not as CI jobs —
  they exercise a real backend and a real CDN, which does not belong in CI.
- **Dependencies and sequencing:** The Sentry gate prerequisite is complete. Nothing else blocks the
  browser harness. Doing it before another TV session would make that session far more productive.
- **Compatibility risks:** The honest limit, and it should be written into the scripts rather than
  discovered later: **a browser is not the television**. The webOS decoder, the panel's frame
  pacing, the CDN's behaviour towards the TV's address and user agent, and Chromium's MSE
  implementation all differ. A scenario that reproduces in a browser proves the _application_ logic
  handles it; one that does not reproduce proves nothing about the TV. Decode-health thresholds
  (**A5**) in particular cannot be validated this way.
- **Confidence:** code — high for the browser classification, Sentry wiring, and all five procedures'
  evidence/privacy rules; runtime — focused tests cover HTTP/HTTPS versus packaged-file
  classification. None of the real-network browser procedures has been run, so their runtime
  reproducibility is unknown; all LG-device behaviour remains device evidence only.
- **Validation and acceptance criteria:** Each browser scenario drives the player to a named,
  observable application end state — for example budget exhausted, notice shown, ABR level changed,
  or teardown completed — reproducibly, from a documented command. For the refused-segment case,
  evidence is valid only when the configured non-secret discriminator uniquely selects media
  fragments rather than keys/subtitles/other CDN requests. For the non-fatal-stall case, diagnostics
  must show watchdog restart/reload progression without fatal recovery becoming causal before the
  terminal notice. For the unbuffered-seek case, the chosen target must be outside the live buffered
  ranges, a matching media-fragment request must be observed after the seek, and `resumed` is valid
  only after observable playback progression beyond the reached seek target. For bandwidth collapse,
  diagnostics must start in Auto mode with multiple levels and a level above zero; success requires a
  lower `currentLevel` followed by observable playback progression after that downshift. The shaped
  throughput is an input to the experiment, not a measured threshold. For teardown, at least one
  matching media-fragment request must be held until the terminal failure notice appears; success
  then requires normal Back handling to leave the player route and unmount the `<video>` element.
  Actual Sentry delivery remains device evidence under **A2**. A scenario that only works sometimes
  is not finished. The browser gate itself is
  covered by focused runtime classification tests; actual
  Sentry delivery remains device evidence under **A2** and is not an A18 browser acceptance
  criterion.
- **Estimated scope:** Medium. Procedure implementation is complete; real-backend browser validation remains.

### A20 — Media recovery is a blunt instrument for the errors it is used on

- **Status:** Partially implemented — investigation continues
- **Depends on:** A5, A6
- **Priority:** Medium
- **Category:** Playback recovery
- **Origin:** [#18](https://github.com/kaaburgh/kinopub.webos/issues/18), while fixing what it
  reported

> **Root cause found and fixed; the general question stays open.** The scenario tests from **A18**
> reproduced the restart on the first run, and showed that the earlier fix could never have engaged.
> The trigger is not a mismatched audio group at all: it is the watchdog's own
> `hls.loadSource(currentSrc); hls.startLoad(position);` pair. `loadSource()` clears hls.js's
> audio-track list and fetches the manifest asynchronously, while `startLoad()` synchronously
> reloads the _old_ level — so `selectInitialTrack()` runs against a list that has just been
> emptied, finds nothing, and raises a fatal `mediaError / audioTrackLoadError`. Because the list is
> empty rather than mismatched, the guard `hls.audioTracks?.length` was false and the code fell
> through to `recoverMediaError()` exactly as before. This matches the Sentry trail in #18, where
> the error arrived 54 ms after `watchdog-reload`.
>
> The watchdog now waits for `MANIFEST_PARSED` before resuming, which removes the race rather than
> handling its symptom, and `audioTrackLoadError` no longer reaches `recoverMediaError()` at all — a
> repeat is recorded as unrecoverable instead, since this error never comes from the decoder.
> Reverting either change makes _"recovers from a bad edge without restarting the film"_ fail.
>
> **The second symptom is fixed too, and had the same shape.** The audio track reverting to the
> default after a recovery was not a consequence of `recoverMediaError()` at all: the restoration
> that was supposed to prevent it had been registered on `MANIFEST_PARSED`, where `hls.audioTracks`
> is still `[]` because hls.js empties the list at `MANIFEST_LOADING` and only refills it when a
> level starts loading. It therefore never ran, not once. Reproduced with the scenario harness: pick
> the non-default track, provoke a watchdog reload, and hls.js is playing the group's default while
> the settings menu still says otherwise. It is now restored on `AUDIO_TRACKS_UPDATED`, the event
> that announces the new group — which also fires immediately before hls.js picks its own initial
> track, so naming it there is what stops the fallback. Covered by _"keeps the viewer's audio track
> through a recovery"_.
>
> A third, cosmetic defect surfaced alongside: the stall watchdog's budget was capped at
> `STALL_MAX_RELOADS * 2`, but its escalation ends on a restart, so the overlay could render "7/6".
> The cap now matches the escalation.
>
> **A gap the scenario harness exposed, and a decision to make.** Once the harness stopped starting
> playback on its own — the element now stays paused until the player calls `play()` on `canplay`,
> as it does on the television — a stream that fails from its very _first_ segment turns out to
> reach no failure notice at all. The stall watchdog stands down while `video.paused` is true, and
> nothing has buffered, so `canplay` never fires and `play()` is never called; the watchdog
> therefore never engages, its budget is never spent, and `getFailure()` requires a spent stall
> budget before it will report anything. hls.js still escalates and the fatal budget still runs out,
> but the viewer is left on a black screen indefinitely rather than being told.
>
> The scenarios stage their outages after playback is under way, which is the reported case and the
> only one they can currently speak to. Whether the terminal state should also be reachable from a
> spent _fatal_ budget alone is a change to the rule in `getFailure()`, argued at length when it was
> written, and is deliberately not being made as a side effect of test work.
>
> The general question — which recoveries suit which error details — still wants episode data across
> more failures.

- **Problem or opportunity:** Every fatal `mediaError` goes through `recoverMediaError()`, which
  detaches and re-attaches the media element. That is a very large hammer, and the two symptoms
  reported in #18 — playback restarting from the beginning, and the audio track reverting — were
  both consequences of the hammer rather than of the original fault. Those are fixed by preserving
  position and re-applying the selection, but the underlying question is untouched: is a full
  detach/attach the right response to, say, an audio-track playlist that failed to load?
- **Concrete evidence:** The capture in #18 recorded
  `recovery: reason=mediaError / audioTrackLoadError`. hls.js's buffer controller does
  `media.removeAttribute('src'); media.load()` on detach
  (`node_modules/hls.js/dist/hls.js:4319-4325`), which resets `currentTime` and drops every buffered
  range; on re-attach the stream controller resumes from `config.startPosition` (`:3042-3044`). The
  same capture showed the CDN refusing one specific segment (`sn 14`, `HTTP 0` then `HTTP 502`) for
  minutes on end, so the audio-track failure may well be the same edge problem wearing a different
  hat.
- **Motivation and expected benefit:** A cheaper recovery for playlist-level failures would avoid
  rebuilding the pipeline at all, and rebuilding it is exactly what produced two viewer-visible
  regressions. Fewer sledgehammers, fewer things to put back afterwards.
- **Proposed direction:** Learn first. `playback_recovered_after` and the episode breadcrumbs now
  record which recovery ran and whether it worked; group by `playback_reason` to see which error
  details actually reach the media path and how often each recovery succeeds. Only then consider
  splitting the response — for instance retrying an audio-track playlist directly, and reserving
  `recoverMediaError()` for genuine decode failures.
- **Dependencies and sequencing:** Needs episode data, so it follows the same device session as
  **A5** and **A6**. Nothing to build until then.
- **Compatibility risks:** Changing which recovery runs for which error is the riskiest edit in this
  area, and it has already produced two regressions when done implicitly. It should not be done on a
  hunch.
- **Confidence:** runtime — high on the mechanism, read from the pinned hls.js. `assumed` on whether
  a narrower recovery would work at all.
- **Validation and acceptance criteria:** A recorded breakdown of media-path errors by `details`
  and outcome, then a decision written down either way — including "leave it alone", which is a
  legitimate result.
- **Estimated scope:** Small to investigate; unknown to change.

### A19 — Move the Sentry DSN out of the source and rotate it

- **Status:** Open
- **Depends on:** None
- **Priority:** Low
- **Category:** Configuration / privacy
- **Origin:** **A4**, deferred deliberately by the repository owner
- **Problem or opportunity:** The DSN is a literal in tracked source, in a public repository, and was
  additionally served in a public bundle for as long as the GitHub Pages deployment was live. A DSN
  is an ingest endpoint, not a credential — the worst case is somebody posting junk events into the
  project and spending the quota — which is why this is Low rather than urgent, and why the
  convention is common enough to be unremarkable. It is still worth fixing.
- **Concrete evidence:** `src/utils/logging.ts:16` holds the value inline. The repository is public.
  `.github/workflows/deploy-pages.yml` published the built bundle to `gh-pages` until **A4** removed
  it; retiring the already-published branch is a manual step recorded there.
- **Motivation and expected benefit:** Rotating invalidates whatever was exposed; moving the value
  to configuration means the next fork, or the next public build, does not inherit this one's
  project — which is exactly the mistake this fork inherited from upstream and spent **A4** undoing.
- **Proposed direction:** Read it from `process.env.REACT_APP_SENTRY_DSN`, alongside the API
  configuration already in `.env`, and skip `Sentry.init` entirely when it is absent so a build
  without the value is silent rather than broken. Then rotate the key in Sentry and update the
  value. Note that `.env` is tracked, so this relocates the value rather than hiding it — the real
  protection is the rotation plus the ability to supply a different value at build time. Pairs
  naturally with the runtime gate **A18** needs.
- **Dependencies and sequencing:** None. Worth doing in the same change as **A18**'s Sentry gate,
  since both touch initialisation.
- **Compatibility risks:** Low, but note that `.env` is read at build time by `react-scripts`, so a
  missing value fails silently at runtime rather than loudly at build — the skip-init path has to be
  deliberate.
- **Confidence:** code — high.
- **Validation and acceptance criteria:** A build with no DSN configured starts and plays with no
  Sentry traffic; a build with one configured reports as before; the old key no longer accepts
  events.
- **Estimated scope:** Small.

### A12 — Reproduce and isolate subtitle brightness, including whether HDR is involved

> **Reproduced on the TV; the HDR component is real.** > [#19](https://github.com/kaaburgh/kinopub.webos/issues/19) records it: at 100% subtitles are
> "much brighter than the video itself" in HDR, 25% was the best of the offered values, and SDR sat
> around 50-75%. So the premise this item existed to test holds, and one setting cannot serve both.
>
> **Shipped:** the range now reaches 15% and 10%, since 25% was simultaneously the floor and the
> preferred value; brightness is remembered per title (and so per series), which sidesteps HDR
> detection entirely for anything watched twice; and the diagnostics panel is grey rather than pure
> white, which is what an HDR display maps to peak brightness.
>
> **Then the signal turned out to exist.** The overlay was given the two candidate signals precisely
> to find out, and `video range: PQ` was read off two HDR titles on the TV. So `VIDEO-RANGE` _is_
> declared in these manifests — hls.js preserves it on `level.attrs` even though it does not parse
> it — and selecting the brightness automatically no longer requires a guess. HDR titles now default
> to 25% and SDR to 75%, stored separately, with any per-title choice still outranking both. The
> `HDR` badge moved to the same signal, retiring the codec guess the review flagged: it treated
> every HEVC stream as HDR.
>
> **Still open:** whether reducing the cue _colour_ would beat reducing its opacity. Opacity fades
> the cue background along with the text, costing contrast on bright scenes, while a dimmer colour
> lowers emitted luminance and keeps it. That is a change of mechanism and wants a device before it
> is made. Also unvalidated: that `VIDEO-RANGE` reads `SDR` rather than being absent on SDR titles.
> If it is simply missing there, the fallback still lands on the SDR default so the brightness comes
> out right, but the `HDR` badge would stay silent where it should be.

- **Status:** Implemented — validation on device outstanding
- **Depends on:** None
- **Priority:** Medium
- **Category:** Subtitles / HDR
- **Origin:** Item 5's unperformed reproduction steps; review §4.8
- **Problem or opportunity:** The manual opacity control shipped, but the premise it was built on —
  that there is an HDR-specific component — has never been tested. The scene-adaptive follow-up would
  be built on an unverified assumption, and the signal a tester would use to sort HDR from SDR
  content is itself a guess.
- **Concrete evidence:** Item 5 lists four isolation steps; nothing in the repository records any of
  them being done. `player.tsx:77-80` derives `isHDR` from `codec` containing `hevc`,
  `codec === 'h265'` (not lower-cased, unlike the `hevc` test one line above), or the quality _name_
  containing `hdr` — HEVC is a codec, HDR is a transfer characteristic, so SDR HEVC content gets an
  HDR badge.
- **Motivation and expected benefit:** Either the manual control is the answer and item 5 can close,
  or there is a real HDR-specific effect worth solving properly. Fixing the badge is a prerequisite
  for telling the two apart.
- **Proposed direction:** First check whether the API exposes a genuine HDR or transfer-characteristic
  flag (`src/api/typings.ts`) and correct or remove the badge accordingly. Then run item 5's four
  steps on the TV: same scene in SDR and HDR, at fixed opacity, photographed. Only then decide about
  scene-adaptive brightness.
- **Dependencies and sequencing:** The badge fix should land first so the observation is trustworthy.
- **Compatibility risks:** `::cue` support on webOS is exactly what is in question; do not replace the
  native subtitle path on a hypothesis.
- **Confidence:** code — high for the badge. device — none for the brightness question.
- **Validation and acceptance criteria:** Photographs of the same scene in both modes attached to a
  written conclusion in this roadmap; the badge appears only on content that is actually HDR.
- **Estimated scope:** Small for the badge; a viewing session for the isolation.

### A13 — Quality-selection follow-ups: decode-driven reduction, and ABR levels as fixed choices

- **Status:** Open — blocked on **A5**
- **Depends on:** A5
- **Priority:** Low
- **Category:** Playback quality
- **Origin:** The live remainders of items 3 and 4, consolidated
- **Problem or opportunity:** Two related open ends. (a) Automatic quality reduction when the
  _decoder_ struggles — deliberately not built, because it would act on an unvalidated signal.
  (b) A master playlist's internal ABR levels are not offered as separate fixed choices, so on an
  adaptive stream the user can pick from the API's quality list or delegate to ABR, but cannot pin a
  level the manifest exposes and the API does not.
- **Concrete evidence:** Item 4's narrowing paragraph states (a) explicitly. For (b), `getSourceTracks`
  prepends only an `Авто` entry to the API-derived list (`media.new.tsx:229-237`), while
  `hls.levels` is separately rendered in the overlay (`playbackDiagnostics.tsx:1073`).
- **Motivation and expected benefit:** (a) would let the app respond to a decoder problem instead of
  only reporting it. (b) is a small completeness gain, most useful while diagnosing.
- **Proposed direction:** Do not start (a) until **A5** says what a real decode problem looks like on
  this panel. When it does: reduce one level at a time via `nextLevel` (never `currentLevel` — see
  **A7**), with hysteresis and a cooldown, never silently overriding a deliberate manual choice, and
  showing the reason in diagnostics. Item 4's original bullet list still describes the shape wanted.
  (b) is independent and small.
- **Dependencies and sequencing:** (a) strictly after **A5**; benefits from **A7** landing first.
- **Compatibility risks:** High for (a) relative to its value — this is the one item that changes what
  the player does to a stream that is currently playing, and the fork has already been bitten twice in
  this area (`currentLevel` flushing the buffer, exact-height matching pinning nothing).
- **Confidence:** assumed. The premise of (a) is precisely what **A5** exists to test.
- **Validation and acceptance criteria:** For (a): a decode problem reproduced on the TV, a single
  reduction observed, no oscillation over 10 minutes, and the reason visible in diagnostics. For (b):
  each manifest level selectable and reflected in `currentLevel`.
- **Estimated scope:** Medium for (a); small for (b).

### A14 — Walk the build-and-install document end to end on a TV

- **Status:** Open — blocked on device evidence
- **Depends on:** None
- **Priority:** Low
- **Category:** Build / release
- **Origin:** Item 6's unvalidated half; review §6, §4.16
- **Problem or opportunity:** The document exists and CI proves the IPK is _built_; nobody has
  confirmed it installs and launches, which is the claim the document actually makes.
- **Concrete evidence:** CI run `30903800595` (`master` @ `ccab33e`) shows "Build and package"
  green, including the check that `out/kinopub.webos_v<version>.ipk` exists. Nothing beyond that.
  Two related staleness bugs: `.github/workflows/ci.yml:41-42` and `docs/ci.md:36-37` both state the
  project has no test files, when there are 3 suites and 41 tests, and `--passWithNoTests` would now
  hide a suite that stopped being discovered.
- **Motivation and expected benefit:** The document's whole purpose is independence from upstream
  release links; that is only true once someone has followed it.
- **Proposed direction:** Follow `docs/build-and-install.md` on a clean machine through
  `ares-install` and the smoke test, correcting whatever is wrong. Separately, drop
  `--passWithNoTests` and fix both stale "no test files" claims.
- **Dependencies and sequencing:** None.
- **Compatibility risks:** None.
- **Confidence:** code — high for the stale claims. device — untested for the install loop.
- **Validation and acceptance criteria:** A build installed on the TV by following only this
  document; CI fails if the test suites disappear.
- **Estimated scope:** Small.

### A15 — Truth up the specification documents

- **Status:** Completed, validation incomplete
- **Depends on:** A4
- **Priority:** Low
- **Category:** Documentation
- **Origin:** Review §4.15
- **Problem or opportunity:** `docs/playback-diagnostics-spec.md` states two things that are no longer
  true, one of which it also contradicts within the same document. The specs are the only place the
  reasoning is recorded; where they are demonstrably stale a reader cannot tell which of the
  unverifiable parts are stale too.
- **Concrete evidence:** `:389-395` lists five reported conditions
  (`fatal-network-recovery-exhausted`, `fatal-media-recovery-exhausted`, `fatal-unrecoverable`,
  `stall-watchdog-exhausted`, `decode-health-severe`); `src/utils/logging.ts:88` defines
  `PlaybackIssue` as `'decode-health-severe'` alone, and the same document says so correctly at
  `:430-433`. Separately, `:264-266` still argues the Sentry DSN "belongs to the upstream project",
  which was the reasoning for replacing it — done at `logging.ts:16`.
- **Motivation and expected benefit:** Cheap, and restores the documents' credibility.
- **Implemented direction:** Replaced the stale standalone-condition list with the recovery-episode
  model plus `decode-health-severe`, rewrote the QR rationale around network independence rather than
  the obsolete upstream-DSN premise, and corrected the adjacent report-volume rule so it distinguishes
  session-scoped standalone issues, endpoint-scoped API failures, and recovery episodes.
- **Dependencies and sequencing:** None. Followed **A4**, whose telemetry decisions the spec now records.
- **Compatibility risks:** None.
- **Confidence:** code — high; both contradictions are visible side by side.
- **Validation and acceptance criteria:** No claim in the spec contradicts the code or another part of
  the spec; `yarn check:docs` and `yarn format:check` still pass.
- **Estimated scope:** Small.

### A16 — Retire dead code and small inherited defects

- **Status:** Partially implemented
- **Depends on:** None
- **Priority:** Low
- **Category:** Maintenance
- **Origin:** Review §4.14, §4.4
- **Problem or opportunity:** A batch of small items, each individually harmless, that together make
  the code harder to trust — notably a dead module that is still a type source for live code.
- **Concrete evidence:**
  - **Completed substep:** `src/views/video/video.tsx` now imports `SourceTrack` through the live
    `components/media` barrel, and the dead legacy `src/components/media/media.tsx` implementation
    has been removed. The nearby `onAudioChange` `@ts-expect-error` was left untouched because this
    bounded cleanup produced no evidence that it belongs to the legacy type source.
  - `player.tsx:194-203` appends `#subtitle-opacity-style` to `document.head` and never removes it —
    the one lifecycle asymmetry in otherwise careful cleanup code.
  - **Completed substep:** `MediaEvents` now derives from `typeof MEDIA_EVENTS[number]`, and the
    generated wrapper map uses `React.ReactEventHandler<HTMLVideoElement>` instead of generic
    `Function`; the local `@ts-expect-error` is gone. This restores type coverage for the live event
    props without intending a runtime behaviour change.
  - **Completed substep:** fatal-network retry timeouts are tracked in a `Set<NodeJS.Timeout>`; each
    callback removes its own timer, `fatalRetryPendingRef` stays true while another retry remains
    pending, and media-effect cleanup clears every remaining retry timeout before HLS destruction.
    Retry counts, backoff delays, and hls.js recovery policy are unchanged.
  - `scripts/package.js:12` builds IPKs under `netflix`, `amazon`, `ivi`, `youtube`, `ui30` as well as
    the real id. Inherited, documented around rather than decided on.
- **Motivation and expected benefit:** Removes traps for whoever reads this next, and closes a real
  hole in type coverage on the player's props.
- **Implemented progress / remaining direction:** Three bounded maintenance substeps are complete:
  `MediaEvents` now covers the live event-name values; `video.tsx` now takes `SourceTrack` from the
  live `components/media` barrel with the dead legacy `media.tsx` removed; and fatal-network retry
  timers are tracked and cleaned up as a set without changing retry policy. The nearby
  `onAudioChange` `@ts-expect-error` remains intentionally untouched pending separate evidence. Remove
  the style element on unmount. Decide about the extra app ids deliberately.
- **Dependencies and sequencing:** None, but do not bundle with a behavioural change — the value here
  is that the diff is boring.
- **Confidence:** code — high, except the concurrency premise for the timer, which is reasoned from
  hls.js's controller structure rather than observed (medium).
- **Validation and acceptance criteria:** The completed `MediaEvents`, legacy-media type-source, and
  retry-timer substeps have green typecheck, lint, test and build CI; the retry-timer change also
  passed ES5 validation. Remaining A16 cleanup must preserve those checks; playback and quality
  switching unchanged on the TV remains device acceptance where a remaining cleanup can affect
  playback behaviour.
- **Estimated scope:** Small.

### A17 — Find out whether upstream has moved, and whether older webOS still works

- **Status:** Investigation first
- **Depends on:** None
- **Priority:** Low
- **Category:** Compatibility
- **Origin:** Review §3, §7.5, §7.6
- **Problem or opportunity:** Two unknowns that could each invalidate assumptions cheaply. This fork
  has no upstream remote, so nobody knows whether `alexeyeryshev/kinopub.webos` or
  `adascal/kinopub.webos` has shipped fixes since the fork point. And `README.md` claims webOS v3+
  while the fork has added CSS that predates neither target nor firmware has been checked against.
- **Concrete evidence:** `git remote -v` shows only `origin`; the last inherited commit is `58bd3ea`
  (2026-03-07). `README.md` states "webOS v3+". ES built-ins are safe — `src/polyfills.ts` imports all
  of `core-js` and `src/index.tsx:1` loads it first — and every DOM API the fork added is behind a
  `typeof` guard. But `gap` on **flex** containers (`playbackDiagnostics.tsx:932`, `:978`, `:1061`)
  is Chrome 84 and cannot be polyfilled: on a webOS 4 panel (Chrome 53) the diagnostics sections
  would sit flush against each other rather than fail outright.
- **Motivation and expected benefit:** Adding an upstream remote is a one-line change that turns an
  unknown into a diff. The webOS claim is either true or the README is wrong, and both are cheap to
  settle.
- **Proposed direction:** Add an `upstream` remote and fetch it; review `58bd3ea..upstream/master`
  for anything worth taking. Separately, either test on an older panel or narrow the README's claim
  to what has actually been run.
- **Dependencies and sequencing:** None.
- **Compatibility risks:** None from looking.
- **Confidence:** code — high for the CSS analysis. Everything else: unknown by construction.
- **Validation and acceptance criteria:** A written statement of what upstream has changed and what
  is worth taking, and a README claim matching what has been verified.
- **Estimated scope:** Small.

---

## Constraints and non-goals

- Keep the pinned React, Enact/webOS, TypeScript, and HLS.js versions unless a separate compatibility task is approved.
- Do not change network, retry, source-selection, or decoder behavior before the diagnostic validation identifies the relevant failure mode.
- Do not assume that a fixed-quality stream can be made adaptive without a master playlist or another source URL.
- Preserve the current diagnostic privacy guarantees.
- Preserve the currently acceptable subtitle size and position while working on subtitle brightness.
- New dependencies stay exceptional. The one addition so far is `qrcode-generator`, which has no
  transitive dependencies and does not touch the playback path; the reasoning is recorded in
  `docs/playback-diagnostics-spec.md`.
- Node.js 14 is a build requirement, not a preference: the pinned `react-scripts` 4 / webpack 4
  toolchain fails on Node.js 17 and newer with `ERR_OSSL_EVP_UNSUPPORTED`. Reproduced during the
  review on Node 22.
