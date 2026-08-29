import { createPlaybackHarness } from 'testing/playbackHarness';

const STREAM = {
  segmentCount: 150,
  segmentDuration: 4,
  levels: [{ name: '1080p', bandwidth: 20000000, resolution: '1920x804', codecs: 'mp4a.40.2' }],
};

jest.setTimeout(120000);

describe('stall watchdog seek jitter regression', () => {
  beforeEach(() => {
    jest.useFakeTimers('modern');
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('does not mistake currentTime jitter in a non-playable state for playback progress', async () => {
    const harness = createPlaybackHarness({ cdn: STREAM, autoPlay: true });

    await harness.advance(30000);
    expect(harness.steps).toEqual([]);

    const stuckAt = harness.video.currentTime;
    harness.playback.wedge();

    // Reproduce the hypothesis from issue #36 at the application boundary: the media element is
    // non-playable (`readyState` 1), yet seek/gap handling keeps nudging currentTime. The old
    // watchdog treated every one-tick position change as healthy playback and restarted its stall
    // timer forever. A position change is only meaningful progress when the element also has
    // playable data, so these nudges must not suppress recovery.
    for (let second = 0; second < 12; second += 1) {
      harness.playback.seek(stuckAt + (second % 2 === 0 ? 0.05 : 0));
      // eslint-disable-next-line no-await-in-loop
      await harness.advance(1000, 100);
      expect(harness.video.readyState).toBe(1);
    }

    expect(harness.steps.map((step) => step.message)).toContain('watchdog-restart');
    expect(harness.player.recovery.attempts).toBeGreaterThan(0);

    harness.destroy();
  });
});
