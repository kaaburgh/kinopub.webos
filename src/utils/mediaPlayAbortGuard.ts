import * as Sentry from '@sentry/browser';

import { getPlaybackSessionId } from 'utils/logging';

export type ExpectedMediaPlayInterruption = 'load' | 'pause';

type MediaPlayPrototype = Pick<HTMLMediaElement, 'play'>;
type GuardedPlay = HTMLMediaElement['play'] & { __kinopubExpectedAbortGuard?: boolean };
type ExpectedInterruptionSink = (action: ExpectedMediaPlayInterruption) => void;

/**
 * Chrome/webOS rejects a pending `play()` promise with AbortError when application lifecycle code
 * interrupts it with pause or a new load. Those rejections are expected consequences of the later
 * action, not independent playback failures. Keep the classifier deliberately narrow so unrelated
 * AbortErrors and every non-AbortError continue through the normal unhandled/reported path.
 */
export function getExpectedMediaPlayInterruption(error: unknown): ExpectedMediaPlayInterruption | undefined {
  if (!error || typeof error !== 'object') {
    return undefined;
  }

  const candidate = error as { name?: unknown; message?: unknown };

  if (candidate.name !== 'AbortError' || typeof candidate.message !== 'string') {
    return undefined;
  }

  const message = candidate.message.toLowerCase();

  if (message.indexOf('interrupted by a call to pause()') !== -1) {
    return 'pause';
  }

  if (message.indexOf('interrupted by a new load request') !== -1) {
    return 'load';
  }

  return undefined;
}

function breadcrumbExpectedInterruption(action: ExpectedMediaPlayInterruption) {
  const playbackId = getPlaybackSessionId();

  Sentry.addBreadcrumb({
    category: 'media.play',
    level: 'info',
    message: 'Expected play() interruption',
    data: playbackId ? { action, playback_id: playbackId } : { action },
  });
}

/**
 * Installs one process-wide guard at the media API boundary.
 *
 * Some player paths intentionally ignore the promise from `play()`, so guarding only individual
 * call sites is brittle: a future autoplay path could reintroduce the same unhandled rejection.
 * Wrapping the browser method once gives every call the same narrow policy while preserving the
 * original promise for successful and unexpected failures. The process-wide lifetime is deliberate.
 */
export function installMediaPlayAbortGuard(
  prototype: MediaPlayPrototype | undefined = typeof HTMLMediaElement === 'undefined' ? undefined : HTMLMediaElement.prototype,
  onExpectedInterruption: ExpectedInterruptionSink = breadcrumbExpectedInterruption,
) {
  if (!prototype) {
    return;
  }

  const currentPlay = prototype.play as GuardedPlay;

  if (currentPlay.__kinopubExpectedAbortGuard) {
    return;
  }

  const originalPlay = currentPlay;
  const guardedPlay: GuardedPlay = function (this: HTMLMediaElement) {
    const result = originalPlay.call(this);

    // Older embedded browsers may still expose the legacy void-returning play() API.
    if (!result || typeof result.catch !== 'function') {
      return result;
    }

    return result.catch((error: unknown) => {
      const interruption = getExpectedMediaPlayInterruption(error);

      if (!interruption) {
        throw error;
      }

      onExpectedInterruption(interruption);
    });
  };

  guardedPlay.__kinopubExpectedAbortGuard = true;
  prototype.play = guardedPlay;
}
