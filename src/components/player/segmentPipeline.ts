/**
 * The Segment Pipeline section: what the fragment loader and the SourceBuffers are doing right now.
 *
 * Two renderings of the same state. The overlay column is narrow and read off a television, so it
 * gets a compact form that fits one line even mid-stall with alternate audio. The QR capture keeps
 * the detailed form, fragment numbers and all: it costs no screen space, and the capture is what
 * reaches someone diagnosing remotely.
 */

export type FragLoadStage = {
  status: 'loading' | 'loaded' | 'aborted';
  level?: number;
  height?: number;
  sn?: number | string;
  startedAt: number;
  durationSeconds?: number;
};

// Keyed by `frag.type` ('main' | 'audio' | 'subtitle'): main and audio fragments load concurrently
// on streams with alternate audio, so a single shared stage would let one hide a stall in the other.
export type FragLoadStagesByStream = Record<string, FragLoadStage>;

export type BufferAppendStage = {
  status: 'appending' | 'appended';
  startedAt: number;
  durationSeconds?: number;
};

// Keyed by the SourceBuffer type ('video' | 'audio' | 'audiovideo') for the same reason: video and
// audio buffers append independently, so one completing must not hide a stall in the other.
export type BufferAppendStagesByType = Record<string, BufferAppendStage>;

type Format = 'compact' | 'detailed';

function formatDuration(seconds: number | undefined, format: Format) {
  if (seconds === undefined || !Number.isFinite(seconds)) {
    return 'n/a';
  }

  return format === 'compact' ? `${seconds.toFixed(1)}s` : `${seconds.toFixed(1)} s`;
}

function elapsedSeconds(startedAt: number, now: number) {
  return (now - startedAt) / 1000;
}

function formatStages<T>(stages: Record<string, T>, formatEntry: (key: string, stage: T) => string, format: Format) {
  const entries = Object.keys(stages).map((key) => formatEntry(key, stages[key]));

  if (!entries.length) {
    return 'idle';
  }

  return entries.join(format === 'compact' ? ' · ' : '; ');
}

function formatFragLoadStage(streamType: string, stage: FragLoadStage, format: Format, now: number) {
  const quality = stage.height
    ? `${stage.height}p`
    : stage.level !== undefined
    ? streamType === 'main'
      ? `level ${stage.level}`
      : `track ${stage.level}`
    : 'unknown level';

  if (format === 'compact') {
    // The stream is named only when it is not the video: `2160p` is unambiguous on its own, and the
    // track and fragment number are in Last Fragment and Recent Events already.
    const label = streamType === 'main' ? (stage.height || stage.level !== undefined ? quality : 'main') : streamType;

    if (stage.status === 'loading') {
      return `${label} ${formatDuration(elapsedSeconds(stage.startedAt, now), format)} pending`;
    }

    if (stage.status === 'aborted') {
      return `${label} aborted`;
    }

    return `${label} ${formatDuration(stage.durationSeconds, format)}`;
  }

  const snLabel = stage.sn !== undefined && stage.sn !== null ? `, sn ${stage.sn}` : '';
  const value =
    stage.status === 'loading'
      ? `loading (${formatDuration(elapsedSeconds(stage.startedAt, now), format)})`
      : stage.status === 'aborted'
      ? 'aborted (low bandwidth)'
      : `loaded in ${formatDuration(stage.durationSeconds, format)}`;

  return `${streamType}: ${quality}${snLabel} - ${value}`;
}

function formatBufferAppendStage(bufferType: string, stage: BufferAppendStage, format: Format, now: number) {
  if (format === 'compact') {
    return stage.status === 'appending'
      ? `${bufferType} ${formatDuration(elapsedSeconds(stage.startedAt, now), format)} pending`
      : `${bufferType} ${formatDuration(stage.durationSeconds, format)}`;
  }

  return stage.status === 'appending'
    ? `${bufferType}: appending (${formatDuration(elapsedSeconds(stage.startedAt, now), format)})`
    : `${bufferType}: appended in ${formatDuration(stage.durationSeconds, format)}`;
}

/** `2160p 0.4s · audio 0.1s` on the overlay; `main: 2160p, sn 12 - loaded in 0.4 s; …` in the capture. */
export function formatFragLoadStages(stages: FragLoadStagesByStream, format: Format, now = Date.now()) {
  return formatStages(stages, (streamType, stage) => formatFragLoadStage(streamType, stage, format, now), format);
}

/** `video 0.2s · audio 0.1s` on the overlay; `video: appended in 0.2 s; …` in the capture. */
export function formatBufferAppendStages(stages: BufferAppendStagesByType, format: Format, now = Date.now()) {
  return formatStages(stages, (bufferType, stage) => formatBufferAppendStage(bufferType, stage, format, now), format);
}

type PendingAppend = {
  /** The `chunkMeta` hls.js passes with both BUFFER_APPENDING and the matching BUFFER_APPENDED. */
  chunk: unknown;
  startedAt: number;
};

/**
 * Appends hls.js has queued and not yet reported complete, oldest first, per SourceBuffer type.
 *
 * One slot per type is not enough: hls.js queues the init segment and the fragment data for the
 * same type back to back, both before either completes. And a plain FIFO is not enough either: an
 * append that fails, or is discarded when the buffer is reset, is dropped from hls.js's queue without
 * a BUFFER_APPENDED, so it would sit at the head forever. hls.js runs each type's queue strictly in
 * order, so when an append completes, everything queued before it has finished one way or another —
 * which is what lets `completeAppend` discard those without knowing why they went. That ordering
 * only holds within one set of SourceBuffers, though; see `resetAppends`.
 */
export type PendingAppends = Map<string, PendingAppend[]>;

export function startAppend(pending: PendingAppends, bufferType: string, chunk: unknown, now: number): BufferAppendStage {
  const queue = pending.get(bufferType) || [];

  queue.push({ chunk, startedAt: now });
  pending.set(bufferType, queue);

  return { status: 'appending', startedAt: queue[0].startedAt };
}

export function completeAppend(pending: PendingAppends, bufferType: string, chunk: unknown, now: number): BufferAppendStage {
  const queue = pending.get(bufferType) || [];
  // Without a chunk to match on, the oldest is the best guess, since the queue runs in order.
  const index = chunk === undefined ? (queue.length ? 0 : -1) : queue.findIndex((append) => append.chunk === chunk);
  const startedAt = index === -1 ? undefined : queue[index].startedAt;
  const remaining = index === -1 ? queue : queue.slice(index + 1);

  if (remaining.length) {
    pending.set(bufferType, remaining);

    return { status: 'appending', startedAt: remaining[0].startedAt };
  }

  pending.delete(bufferType);

  return {
    status: 'appended',
    startedAt: startedAt ?? now,
    durationSeconds: startedAt !== undefined ? (now - startedAt) / 1000 : undefined,
  };
}

/**
 * Forget every pending append because hls.js has thrown its SourceBuffers away.
 *
 * hls.js 1.0.10 rebuilds the buffers and their operation queue without a BUFFER_APPENDED for what
 * was queued: on MEDIA_DETACHING (which `recoverMediaError()` goes through) and on BUFFER_RESET
 * (a new `loadSource()`). The same hls.js instance carries on, so nothing else clears the queue, and
 * an append left in it would keep timing the next one from when the discarded append started.
 */
export function resetAppends(pending: PendingAppends) {
  pending.clear();
}
