import {
  BufferAppendStagesByType,
  FragLoadStagesByStream,
  PendingAppends,
  completeAppend,
  formatBufferAppendStages,
  formatFragLoadStages,
  resetAppends,
  startAppend,
} from './segmentPipeline';

const now = 100_000;

// Alternate audio, mid-stall on the video side: the longest state the overlay line has to hold.
const stalledLoads: FragLoadStagesByStream = {
  main: { status: 'loading', height: 2160, level: 5, sn: 1234, startedAt: now - 12_300 },
  audio: { status: 'loaded', level: 0, sn: 1234, startedAt: now - 100, durationSeconds: 0.1 },
};
const stalledAppends: BufferAppendStagesByType = {
  video: { status: 'appending', startedAt: now - 12_300 },
  audio: { status: 'appended', startedAt: now - 100, durationSeconds: 0.1 },
};

/**
 * The overlay's own `load:` line fits on the TV at about 44 characters (#38, LG capture); the 58
 * character `append:` line did not. Hold both lines to what is known to fit.
 */
const KNOWN_TO_FIT = 44;

describe('segment pipeline on the overlay', () => {
  it('names each buffer once, with the time it took', () => {
    const appends: BufferAppendStagesByType = {
      video: { status: 'appended', startedAt: now - 200, durationSeconds: 0.2 },
      audio: { status: 'appended', startedAt: now - 100, durationSeconds: 0.1 },
    };

    expect(formatBufferAppendStages(appends, 'compact', now)).toBe('video 0.2s · audio 0.1s');
  });

  it('marks the stage still in progress, so a stall points at one buffer or stream', () => {
    expect(formatBufferAppendStages(stalledAppends, 'compact', now)).toBe('video 12.3s pending · audio 0.1s');
    expect(formatFragLoadStages(stalledLoads, 'compact', now)).toBe('2160p 12.3s pending · audio 0.1s');
  });

  it('keeps the worst case on one line', () => {
    expect(`load: ${formatFragLoadStages(stalledLoads, 'compact', now)}`.length).toBeLessThanOrEqual(KNOWN_TO_FIT);
    expect(`append: ${formatBufferAppendStages(stalledAppends, 'compact', now)}`.length).toBeLessThanOrEqual(KNOWN_TO_FIT);
  });

  it('labels the main stream by level when its quality is unknown, and says when a load was aborted', () => {
    const loads: FragLoadStagesByStream = {
      main: { status: 'aborted', level: 3, startedAt: now - 500 },
      audio: { status: 'loaded', startedAt: now - 100 },
    };

    expect(formatFragLoadStages(loads, 'compact', now)).toBe('level 3 aborted · audio n/a');
  });

  it('says idle when nothing has happened yet', () => {
    expect(formatFragLoadStages({}, 'compact', now)).toBe('idle');
    expect(formatBufferAppendStages({}, 'compact', now)).toBe('idle');
  });
});

describe('segment pipeline in the QR capture', () => {
  // The capture keeps the detailed form the decoder and earlier captures already use.
  it('is unchanged', () => {
    expect(formatFragLoadStages(stalledLoads, 'detailed', now)).toBe(
      'main: 2160p, sn 1234 - loading (12.3 s); audio: track 0, sn 1234 - loaded in 0.1 s',
    );
    expect(formatFragLoadStages({ main: { status: 'aborted', level: 3, startedAt: now } }, 'detailed', now)).toBe(
      'main: level 3 - aborted (low bandwidth)',
    );
    expect(formatBufferAppendStages(stalledAppends, 'detailed', now)).toBe('video: appending (12.3 s); audio: appended in 0.1 s');
    expect(formatBufferAppendStages({}, 'detailed', now)).toBe('idle');
  });
});

describe('pending appends', () => {
  const chunk = (id: number) => ({ id });

  it('stays in progress until the fragment data that follows an init segment completes', () => {
    const pending: PendingAppends = new Map();
    const first = chunk(1);

    // hls.js queues the init segment and the data for one type back to back, sharing the chunk.
    startAppend(pending, 'video', first, 1000);
    startAppend(pending, 'video', first, 1010);

    expect(completeAppend(pending, 'video', first, 1050)).toEqual({ status: 'appending', startedAt: 1010 });
    expect(completeAppend(pending, 'video', first, 1210)).toEqual({ status: 'appended', startedAt: 1010, durationSeconds: 0.2 });
    expect(pending.size).toBe(0);
  });

  it('keeps buffer types apart', () => {
    const pending: PendingAppends = new Map();
    const first = chunk(1);

    startAppend(pending, 'video', first, 1000);
    startAppend(pending, 'audio', first, 1000);

    expect(completeAppend(pending, 'audio', first, 1100)).toEqual({ status: 'appended', startedAt: 1000, durationSeconds: 0.1 });
    expect(pending.get('video')).toHaveLength(1);
  });

  it('recovers from an append hls.js dropped without reporting it', () => {
    const pending: PendingAppends = new Map();
    const dropped = chunk(1);
    const next = chunk(2);

    // Failed, or discarded by a buffer reset: no BUFFER_APPENDED will ever arrive for it.
    startAppend(pending, 'video', dropped, 1000);
    startAppend(pending, 'video', next, 5000);

    // The queue runs in order, so the first is gone once the second completes.
    expect(completeAppend(pending, 'video', next, 5300)).toEqual({ status: 'appended', startedAt: 5000, durationSeconds: 0.3 });
    expect(pending.size).toBe(0);
  });

  it('times appends after a buffer reset from their own start', () => {
    const pending: PendingAppends = new Map();
    const discarded = chunk(1);
    const next = chunk(2);

    // recoverMediaError() mid-append: hls.js drops the queued append with its SourceBuffers.
    startAppend(pending, 'video', discarded, 1000);
    resetAppends(pending);

    expect(startAppend(pending, 'video', next, 9000)).toEqual({ status: 'appending', startedAt: 9000 });
    expect(completeAppend(pending, 'video', next, 9200)).toEqual({ status: 'appended', startedAt: 9000, durationSeconds: 0.2 });
  });

  it('cannot time an append whose start it never saw', () => {
    const pending: PendingAppends = new Map();

    expect(completeAppend(pending, 'video', chunk(1), 1000)).toEqual({ status: 'appended', startedAt: 1000, durationSeconds: undefined });
  });

  it('falls back to the oldest pending append when hls.js passes no chunk', () => {
    const pending: PendingAppends = new Map();

    startAppend(pending, 'video', undefined, 1000);

    expect(completeAppend(pending, 'video', undefined, 1400)).toEqual({ status: 'appended', startedAt: 1000, durationSeconds: 0.4 });
  });
});
