import * as Sentry from '@sentry/browser';
import { Integrations as TracingIntegrations } from '@sentry/tracing';

import { ApiFailure, apiFailureKey, describeApiFailure, isServerFault, normalizeEndpoint } from 'utils/apiFailures';
import { APP_VERSION } from 'utils/app';
import { IS_WEB } from 'utils/enviroment';
import { EpisodeSink, EpisodeSummary } from 'utils/playbackEpisode';

/**
 * Playback failures are reported here as well as in the on-screen diagnostics.
 *
 * The QR capture exists because the network is exactly what breaks during a stall, so it stays the
 * reliable path. Sentry covers the more common case: the app or the backend misbehaving while the
 * connection is fine. The two are complementary, not alternatives.
 */
if (!IS_WEB) {
  Sentry.init({
    release: APP_VERSION,
    dsn: 'https://627d68f05165b49ebcb52675dc97e3bc@o4511850860576768.ingest.de.sentry.io/4511850884431952',
    integrations: [new TracingIntegrations.BrowserTracing()],
    tracesSampleRate: 1.0,
    // Stream URLs carry access tokens in their query string, and they turn up in breadcrumbs, request
    // data and error messages alike. Reduce every URL to its hostname before anything leaves the TV —
    // the same rule the diagnostics overlay follows.
    beforeSend: scrubEvent,
    beforeBreadcrumb: scrubBreadcrumb,
    // The recovery trail is the payload: a stalled episode wants its whole chain of retries and
    // watchdog actions attached, and the default of 100 leaves room for that once repeated errors
    // are aggregated rather than breadcrumbed one by one.
    maxBreadcrumbs: 100,
  });
}

/**
 * Ties one playback attempt to everything it reported.
 *
 * Sentry has no notion of "this viewing", and its own session id is neither shown to a viewer nor
 * searchable in a useful way. So the player mints its own: short enough to read off a television
 * screen and type into Sentry's search (`playback_id:XXXXXX`), and set as a tag on the global scope
 * so every breadcrumb, issue and episode report from that attempt carries it. The diagnostics
 * overlay shows the same value, which is what makes a photographed screen and a Sentry event
 * findable from each other.
 *
 * The alphabet omits characters that are read wrong off a panel: no O/0, no I/1, no S/5.
 */
const PLAYBACK_ID_ALPHABET = 'ABCDEFGHJKLMNPQRTUVWXYZ2346789';
const PLAYBACK_ID_LENGTH = 6;

let playbackSessionId: string | undefined;

/**
 * One random byte, from the platform's cryptographic source where there is one.
 *
 * Not because this is a secret -- it is printed on the television the moment it is minted -- but
 * because the only property that matters is that two viewings do not produce the same label, and
 * `Math.random()` on an old embedded V8 gives no distribution guarantee worth relying on for that.
 */
function randomByte() {
  const webCrypto = (window as Window & { crypto?: Crypto }).crypto;

  if (typeof webCrypto?.getRandomValues === 'function') {
    return webCrypto.getRandomValues(new Uint8Array(1))[0];
  }

  // Reached only where there is no `crypto` at all, which today means jsdom under jest. A
  // correlation label for a diagnostics screen is not a security context.
  // lgtm[js/insecure-randomness]
  return Math.floor(Math.random() * 256);
}

export function startPlaybackSession() {
  // The largest multiple of the alphabet length that fits in a byte. Bytes at or above it are
  // discarded rather than folded, so no character is more likely than any other.
  const ceiling = 256 - (256 % PLAYBACK_ID_ALPHABET.length);
  let id = '';

  while (id.length < PLAYBACK_ID_LENGTH) {
    const byte = randomByte();

    if (byte < ceiling) {
      id += PLAYBACK_ID_ALPHABET[byte % PLAYBACK_ID_ALPHABET.length];
    }
  }

  playbackSessionId = id;
  Sentry.configureScope((scope) => scope.setTag('playback_id', id));

  return id;
}

/**
 * Ends the attempt, so later events are not filed under it.
 *
 * Without this the tag outlives the player on Sentry's global scope, and a search for a
 * photographed id would return whatever the viewer did next -- browsing, an API failure, an
 * unrelated crash -- as though it had happened during that playback.
 */
export function endPlaybackSession() {
  playbackSessionId = undefined;
  Sentry.configureScope((scope) => scope.setTag('playback_id', undefined));
}

/** The current attempt's id, or undefined before playback has started. */
export function getPlaybackSessionId() {
  return playbackSessionId;
}

const URL_PATTERN = /\bhttps?:\/\/[^\s"'<>]+/gi;

function hostnameOf(url: string) {
  try {
    return new URL(url).hostname;
  } catch (e) {
    const match = url.match(/^(?:[a-z]+:)?\/\/([^/?#]+)/i);

    return match?.[1] || '[url]';
  }
}

/** Replaces every URL in a string with its bare hostname. */
export function scrubUrls<T>(value: T): T {
  if (typeof value === 'string') {
    return value.replace(URL_PATTERN, (url) => hostnameOf(url)) as unknown as T;
  }

  if (Array.isArray(value)) {
    return value.map(scrubUrls) as unknown as T;
  }

  if (value && typeof value === 'object') {
    const result: Record<string, unknown> = {};

    Object.entries(value as Record<string, unknown>).forEach(([key, entry]) => {
      result[key] = scrubUrls(entry);
    });

    return result as unknown as T;
  }

  return value;
}

/**
 * Exact playback positions and absolute buffered ranges are viewing data, not diagnostics we may
 * send off the television. Strip them at the reporting boundary as well as at the producer so a
 * future context field cannot accidentally bypass the privacy rule.
 */
function scrubPlaybackEpisode(summary: EpisodeSummary) {
  const context = summary.context ? { ...summary.context } : undefined;

  if (context) {
    delete context.currentTime;
    delete context.position;
    delete context.bufferedRanges;
  }

  return scrubUrls({ ...summary, context });
}

function scrubEvent(event: Sentry.Event) {
  return scrubUrls(event);
}

function scrubBreadcrumb(breadcrumb: Sentry.Breadcrumb) {
  return scrubUrls(breadcrumb);
}

export function logError(message: string) {
  Sentry.captureMessage(message);
}

export function logException(exception: any) {
  Sentry.captureException(exception);
}

/**
 * Standalone playback problems, reported once per session.
 *
 * Failures the player tries to recover from are *not* here: they belong to a recovery episode,
 * which reports the whole chain and its outcome as one event (see `sentryEpisodeSink`). Sending
 * both would tell the same story twice and spend the quota doing it.
 */
export type PlaybackIssue = 'decode-health-severe';

export type PlaybackIssueContext = {
  reason?: string;
  /** Hostname only — never a full URL. */
  host?: string;
  quality?: string;
  streamingType?: string;
  attempts?: number;
  limit?: number;
  droppedRatio?: number;
  decodeErrors?: number;
  levelCount?: number;
  currentLevel?: number;
  bandwidthEstimate?: number;
};

/**
 * One report per issue per playback session.
 *
 * This matters more than it looks. The failure this project has been chasing produces a few hundred
 * errors a minute; reporting each one would bury the signal and burn the quota in a single evening.
 * The interesting fact is "this session hit this wall", not how many times it bounced off it.
 */
const reportedIssues = new Set<PlaybackIssue>();

export function resetPlaybackIssueReports() {
  reportedIssues.clear();
}

export function logPlaybackIssue(issue: PlaybackIssue, context: PlaybackIssueContext = {}) {
  if (reportedIssues.has(issue)) {
    return;
  }

  reportedIssues.add(issue);

  Sentry.withScope((scope) => {
    scope.setTag('playback_issue', issue);

    if (context.reason) {
      scope.setTag('playback_reason', context.reason);
    }

    if (context.host) {
      scope.setTag('playback_host', context.host);
    }

    if (context.streamingType) {
      scope.setTag('streaming_type', context.streamingType);
    }

    scope.setContext('playback', scrubUrls({ ...context }));
    // Playback keeps going through these, so they are warnings rather than crashes.
    scope.setLevel(Sentry.Severity.Warning);

    Sentry.captureMessage(`playback: ${issue}`);
  });
}

/**
 * Backend failures, one report per endpoint per kind per session.
 *
 * The complaint this exists to answer is "the app was weird last night", which the playback
 * pipeline cannot explain when the cause was the service behind it. What reaches Sentry is the
 * normalised path, the method and the status — never the query string, which carries `access_token`
 * on every authenticated request. `normalizeEndpoint` strips it here rather than trusting callers.
 */
const reportedApiFailures = new Set<string>();

export function logApiFailure(failure: ApiFailure) {
  const key = apiFailureKey(failure);

  if (reportedApiFailures.has(key)) {
    return;
  }

  reportedApiFailures.add(key);

  const endpoint = normalizeEndpoint(failure.endpoint);

  Sentry.withScope((scope) => {
    scope.setTag('api_failure', failure.kind);
    scope.setTag('api_endpoint', endpoint);
    scope.setTag('api_method', failure.method);

    if (failure.status !== undefined) {
      scope.setTag('api_status', String(failure.status));
    }

    scope.setContext(
      'api',
      scrubUrls({
        kind: failure.kind,
        endpoint,
        method: failure.method,
        status: failure.status,
        reason: failure.reason,
      }),
    );
    scope.setLevel(isServerFault(failure) ? Sentry.Severity.Error : Sentry.Severity.Warning);

    Sentry.captureMessage(describeApiFailure(failure));
  });
}

/**
 * Sends recovery episodes to Sentry: each step as a breadcrumb, one event when the episode
 * concludes. The breadcrumbs Sentry has collected by then ride along with that event, so the
 * report answers not just "what failed" but "what the player did about it, and whether it worked".
 */
export const sentryEpisodeSink: EpisodeSink = {
  breadcrumb: (crumb) => {
    Sentry.addBreadcrumb({
      category: crumb.category,
      message: crumb.message,
      level: crumb.level === 'error' ? Sentry.Severity.Error : crumb.level === 'warning' ? Sentry.Severity.Warning : Sentry.Severity.Info,
      data: crumb.data ? scrubUrls(crumb.data) : undefined,
    });
  },

  report: (summary: EpisodeSummary) => {
    Sentry.withScope((scope) => {
      scope.setTag('playback_episode', summary.outcome);
      scope.setTag('playback_episode_trigger', summary.trigger);

      if (summary.lastReason) {
        scope.setTag('playback_reason', summary.lastReason);
      }

      if (summary.host) {
        scope.setTag('playback_host', summary.host);
      }

      // The action that immediately preceded recovery is the single most useful field here: it is
      // what tells us which recovery path actually works against this failure.
      if (summary.recoveredAfter) {
        scope.setTag('playback_recovered_after', summary.recoveredAfter);
      }

      // How the episode ended, not just whether it was lost. Filtering on this is what separates
      // "the player ran out of options" from "the viewer stopped waiting", which are the same
      // outcome and completely different facts.
      scope.setTag('playback_episode_ended_by', summary.endedBy);

      scope.setContext('playback_episode', scrubPlaybackEpisode(summary));
      // Only the player giving up on its own is an error. A viewer who leaves, or retries by hand,
      // ended the episode deliberately -- worth recording, not worth paging over.
      scope.setLevel(
        summary.outcome === 'abandoned' && summary.endedBy === 'grace-period' ? Sentry.Severity.Error : Sentry.Severity.Warning,
      );

      Sentry.captureMessage(
        summary.outcome === 'abandoned'
          ? `playback: recovery abandoned after ${Math.round(summary.durationMs / 1000)}s (${summary.endedBy})`
          : `playback: recovered after ${Math.round(summary.durationMs / 1000)}s via ${summary.recoveredAfter || 'retry'}`,
      );
    });
  },
};
