/**
 * Playback failures from the TV, replayed against a scripted CDN.
 *
 * Each test stages a network condition that was actually observed on the device and then asserts
 * two separate things: what hls.js does with it, and what this player does on top. The split is the
 * point. When hls.js is upgraded, the first group says whether the library's own behaviour changed;
 * the second says whether the recovery code here is still earning its place, or whether the new
 * version already handles the case and the code can go.
 *
 * The only substitution is the CDN, at the HTTP boundary (`testing/hlsCdn`). Playlist parsing,
 * level selection, the non-fatal retry ladder and the escalation to a fatal error are all performed
 * by the real hls.js. See `docs/playback-scenario-tests.md` for how to use these at upgrade time.
 */
import { AUTO_SOURCE_NAME } from 'components/media/media.new';
import { createPlaybackHarness } from 'testing/playbackHarness';

const STREAM = {
  segmentCount: 150,
  segmentDuration: 4,
  // A realistic UHD bitrate, which is what keeps hls.js's forward buffer near 30s. At a low
  // declared bandwidth it would happily fetch the entire playlist before playback started, and no
  // outage staged afterwards could ever be felt.
  levels: [{ name: '1080p', bandwidth: 20000000, resolution: '1920x804', codecs: 'mp4a.40.2', videoRange: 'PQ' as const }],
};

/**
 * A master with two levels, whose audio groups list the same languages in opposite orders.
 *
 * The ordering is the point: it is legal, the API's mixed AVC+HEVC playlists can produce it, and it
 * is what tells a selection made by position apart from one made by name. `throughput` matters as
 * much -- hls.js picks a level from a bandwidth estimate, so without a link that costs something
 * the estimate is meaningless and the choice flaps.
 */
const ADAPTIVE = {
  segmentCount: 150,
  segmentDuration: 4,
  levels: [
    { name: '1080p', bandwidth: 20000000, resolution: '1920x804', codecs: 'mp4a.40.2', audioGroup: 'aud1' },
    { name: '720p', bandwidth: 6000000, resolution: '1280x536', codecs: 'mp4a.40.2', audioGroup: 'aud2' },
  ],
  audioRenditions: [
    { groupId: 'aud1', name: 'Русский', language: 'ru', default: true },
    { groupId: 'aud1', name: 'English', language: 'en' },
    { groupId: 'aud2', name: 'English', language: 'en', default: true },
    { groupId: 'aud2', name: 'Русский', language: 'ru' },
  ],
};

const QUALITY_TRACKS = [
  { src: 'https://cdn.test/master.m3u8', type: 'application/x-mpegURL', name: '1080p', default: true },
  { src: 'https://cdn.test/master.m3u8', type: 'application/x-mpegURL', name: '720p' },
];

const LANGUAGES = [
  { name: 'Русский', number: '1', lang: 'ru', default: true },
  { name: 'English', number: '2', lang: 'en' },
];

/** The recovery steps by name; the tracker files them all under one breadcrumb category. */
const actions = (harness: { steps: { message: string }[] }) => harness.steps.map((step) => step.message);

jest.setTimeout(120000);

describe('playback scenarios', () => {
  beforeEach(() => {
    jest.useFakeTimers('modern');
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('plays a healthy stream without recovering anything', async () => {
    const harness = createPlaybackHarness({ cdn: STREAM, autoPlay: true });

    await harness.advance(60000);

    expect(harness.hlsErrors).toEqual([]);
    expect(harness.steps).toEqual([]);
    expect(harness.episodes).toEqual([]);
    expect(harness.player.failure).toBeUndefined();
    expect(harness.player.recovery).toMatchObject({ attempts: 0, exhausted: false });
    // Playing for a minute means having played roughly a minute of it.
    expect(harness.video.currentTime).toBeGreaterThan(55);
    expect(harness.player.videoRange).toBe('PQ');

    harness.destroy();
  });

  describe('a CDN edge that refuses every segment', () => {
    it('is retried by hls.js several times before it becomes fatal', async () => {
      const harness = createPlaybackHarness({ cdn: STREAM, autoPlay: true });
      harness.cdn.intercept((request) => (request.kind === 'fragment' ? { status: 502 } : undefined));

      await harness.advance(200000, 200);

      const firstFatal = harness.hlsErrors.findIndex((error) => error.fatal);

      // hls.js's own behaviour: a refused segment is retried internally, and only the exhaustion of
      // that ladder is reported as fatal. This is why the player must not treat a non-fatal
      // `fragLoadError` as something to act on -- doing so would fight hls.js's own retries.
      expect(firstFatal).toBeGreaterThanOrEqual(5);
      expect(harness.hlsErrors.slice(0, firstFatal).every((error) => error.reason === 'networkError / fragLoadError')).toBe(true);
      expect(harness.hlsErrors[firstFatal].reason).toBe('networkError / fragLoadError');

      // And the player's: no fatal-error recovery is attempted until hls.js escalates.
      const firstFatalRetry = harness.steps.find((step) => step.message === 'fatal-retry');
      expect(firstFatalRetry?.at).toBeGreaterThanOrEqual(harness.hlsErrors[firstFatal].at);

      harness.destroy();
    });

    it('gives up and reports a terminal failure once every budget is spent', async () => {
      // The outage starts after playback is under way, which is both the reported case and the only
      // one the watchdog can see: it stands down while the element is paused, and the element stays
      // paused until something has buffered. See the note in ROADMAP A20 on what that leaves open
      // for a stream that fails from its very first segment.
      const harness = createPlaybackHarness({ cdn: STREAM, autoPlay: true });
      harness.cdn.intercept((request) =>
        request.kind === 'fragment' && harness.cdn.segmentIndexOf(request.path) >= 4 ? { status: 502 } : undefined,
      );

      await harness.advance(700000, 200);

      expect(harness.player.failure).toMatchObject({ kind: 'recovery-exhausted', reason: 'networkError / fragLoadError' });
      expect(actions(harness)).toEqual(expect.arrayContaining(['watchdog-restart', 'watchdog-reload', 'fatal-retry']));

      // The report has to say which budget ran out, because that is what distinguishes a stream
      // nobody can serve from a decoder that cannot cope.
      const exhausted = harness.episodes.flatMap((episode) => episode.exhausted);
      expect(exhausted).toEqual(expect.arrayContaining(['stall-watchdog', 'fatal-network']));
      expect(harness.episodes.map((episode) => episode.outcome)).toContain('abandoned');

      // The overlay renders this as "attempts of limit", so a budget that can be overspent shows
      // the viewer a number larger than its own cap.
      expect(harness.player.recovery.attempts).toBeLessThanOrEqual(harness.player.recovery.limit);

      harness.destroy();
    });
  });

  it('escapes a bad edge by refetching the playlist', async () => {
    // Two edges, the first broken: the playlist refetch is what hands out URLs on the second one.
    // This is the failure the watchdog exists for, taken from a Sentry trail in which every
    // request to one edge returned 0 or 502 while a sibling edge served 200s throughout.
    const harness = createPlaybackHarness({
      cdn: { ...STREAM, edges: ['edge-01.cdn.test', 'edge-01.cdn.test', 'edge-03.cdn.test'] },
      autoPlay: true,
    });

    harness.cdn.intercept((request) =>
      request.kind === 'fragment' && request.host === 'edge-01.cdn.test' && harness.cdn.segmentIndexOf(request.path) >= 12
        ? { status: 502 }
        : undefined,
    );

    await harness.advance(120000, 100);

    // hls.js does not do this on its own: nothing in the library refetches a VOD playlist because
    // playback stopped moving, so without the watchdog the picture stays frozen on the last frame.
    expect(actions(harness)).toEqual(expect.arrayContaining(['watchdog-restart', 'watchdog-reload']));
    expect(harness.cdn.requestsMatching((request) => request.host === 'edge-03.cdn.test').length).toBeGreaterThan(0);

    // And playback carried on past the point the broken edge stopped serving.
    expect(harness.video.currentTime).toBeGreaterThan(12 * STREAM.segmentDuration);
    expect(harness.player.failure).toBeUndefined();

    harness.destroy();
  });

  it('recovers from a bad edge without restarting the film', async () => {
    // The regression from issue #18. `loadSource()` clears hls.js's audio-track state and fetches
    // a new manifest asynchronously, so resuming before it arrives makes hls.js reselect an audio
    // track from an empty list and raise a fatal `mediaError / audioTrackLoadError`. Answering
    // that with `recoverMediaError()` detaches the media element, which resets `currentTime` to
    // zero -- a fifty-minute film restarting from the beginning, with the wrong audio.
    const harness = createPlaybackHarness({
      cdn: {
        ...STREAM,
        edges: ['edge-01.cdn.test', 'edge-01.cdn.test', 'edge-03.cdn.test'],
        levels: [{ ...STREAM.levels[0], audioGroup: 'aud1' }],
        audioRenditions: [
          { groupId: 'aud1', name: 'Русский', language: 'ru', default: true },
          { groupId: 'aud1', name: 'English', language: 'en' },
        ],
      },
      audioTracks: [
        { name: 'Русский', number: '1', lang: 'ru', default: true },
        { name: 'English', number: '2', lang: 'en' },
      ],
      autoPlay: true,
    });

    harness.cdn.intercept((request) =>
      request.kind === 'fragment' && request.host === 'edge-01.cdn.test' && harness.cdn.segmentIndexOf(request.path) >= 12
        ? { status: 502 }
        : undefined,
    );

    await harness.advance(120000, 100);

    expect(actions(harness)).toContain('watchdog-reload');
    expect(harness.hlsErrors.map((error) => error.reason)).not.toContain('mediaError / audioTrackLoadError');
    // `recoverMediaError()` is the destructive path; nothing here should have needed it.
    expect(actions(harness)).not.toContain('media-recover');
    expect(harness.video.currentTime).toBeGreaterThan(12 * STREAM.segmentDuration);

    harness.destroy();
  });

  it("keeps the viewer's audio track through a recovery", async () => {
    // The other symptom reported in issue #18: playback resumed in a different language from the
    // one the settings menu still displayed. `loadSource()` empties hls.js's audio-track list and
    // resets the selected track name, so once the replacement manifest arrives hls.js picks the
    // group's default -- unless the player names the track again at the point the new group appears.
    const harness = createPlaybackHarness({
      cdn: {
        ...STREAM,
        edges: ['edge-01.cdn.test', 'edge-01.cdn.test', 'edge-03.cdn.test'],
        levels: [{ ...STREAM.levels[0], audioGroup: 'aud1' }],
        audioRenditions: [
          { groupId: 'aud1', name: 'Русский', language: 'ru', default: true },
          { groupId: 'aud1', name: 'English', language: 'en' },
        ],
      },
      audioTracks: [
        { name: 'Русский', number: '1', lang: 'ru', default: true },
        { name: 'English', number: '2', lang: 'en' },
      ],
      autoPlay: true,
    });

    await harness.advance(20000);
    harness.interact((player) => {
      player.audioTrack = 'English';
    });
    await harness.advance(2000);
    expect(harness.player.hls!.audioTracks[harness.player.hls!.audioTrack].name).toBe('English');

    harness.cdn.intercept((request) =>
      request.kind === 'fragment' && request.host === 'edge-01.cdn.test' && harness.cdn.segmentIndexOf(request.path) >= 20
        ? { status: 502 }
        : undefined,
    );

    await harness.advance(200000);

    expect(actions(harness)).toContain('watchdog-reload');
    // The player's own view of the choice never changed, so a mismatch here is the settings menu
    // and the audio disagreeing -- which is exactly what was reported.
    expect(harness.player.audioTrack).toBe('English');
    expect(harness.player.hls!.audioTracks[harness.player.hls!.audioTrack].name).toBe('English');

    harness.destroy();
  });

  it('does not credit the buffer with bytes the link has not delivered yet', async () => {
    // A property of the harness rather than of the player, but the multi-level scenarios below are
    // only meaningful if it holds: the buffer is modelled from what the CDN delivered, so crediting
    // a fragment when it was *requested* would let a link too slow to keep up look healthy, and
    // "no recovery engaged" would stop being evidence of anything.
    const harness = createPlaybackHarness({
      cdn: { ...ADAPTIVE, throughput: 9000000 },
      sourceTracks: QUALITY_TRACKS,
      autoPlay: true,
    });

    // Stop as soon as a fragment has been asked for. Even the smaller rendition is 3 MB, which
    // takes over two seconds on this link, so nothing can have arrived yet.
    while (harness.cdn.requestsOfKind('fragment').length === 0) {
      // eslint-disable-next-line no-await-in-loop
      await harness.advance(100);
    }

    expect(harness.playback.bufferedEnd).toBe(0);
    await harness.advance(1000);
    expect(harness.playback.bufferedEnd).toBe(0);

    await harness.advance(15000);
    expect(harness.playback.bufferedEnd).toBeGreaterThan(0);

    harness.destroy();
  });

  it("keeps the viewer's audio track across a quality switch that changes the audio group", async () => {
    // Switching quality moves to a level whose audio group lists the same languages in the opposite
    // order. hls.js has not forgotten the selection here -- it re-finds the track by name -- so the
    // player must leave it alone. Re-applying its own index over that would swap the language in
    // the middle of a film, and the settings menu would go on displaying the old one.
    const harness = createPlaybackHarness({
      cdn: { ...ADAPTIVE, throughput: 40000000 },
      sourceTracks: QUALITY_TRACKS,
      audioTracks: LANGUAGES,
      autoPlay: true,
    });

    await harness.advance(30000);
    harness.interact((player) => {
      player.audioTrack = 'English';
    });
    await harness.advance(4000);

    const chosen = harness.player.hls!;
    expect(chosen.audioTracks[chosen.audioTrack].name).toBe('English');

    harness.interact((player) => {
      player.sourceTrack = '720p';
    });
    await harness.advance(40000);

    const after = harness.player.hls!;
    // The group really did change, so this is not passing by never exercising the path.
    expect(after.audioTracks.map((track) => track.name)).toEqual(['English', 'Русский']);
    expect(after.audioTracks[after.audioTrack].name).toBe('English');
    expect(harness.player.audioTrack).toBe('English');
    // A quality switch is not a failure; nothing should have recovered anything.
    expect(harness.hlsErrors).toEqual([]);
    // Well past the switch, which happened at 34s.
    expect(harness.video.currentTime).toBeGreaterThan(45);

    harness.destroy();
  });

  it('lets hls.js pick a level the link can carry, without the watchdog getting involved', async () => {
    // A link that comfortably carries the lower level and cannot carry the upper one. This is
    // hls.js's own job, and the assertion is as much about the player staying out of the way: a
    // stream that adapts is not a stream that stalled, and no recovery should engage.
    const harness = createPlaybackHarness({
      cdn: { ...ADAPTIVE, throughput: 9000000 },
      sourceTracks: QUALITY_TRACKS,
      audioTracks: LANGUAGES,
      autoPlay: true,
    });

    await harness.advance(10000);
    harness.interact((player) => {
      player.sourceTrack = AUTO_SOURCE_NAME;
    });
    await harness.advance(120000);

    const hls = harness.player.hls!;
    // hls.js sorts levels by bitrate, so index 0 is the 6 Mbps rendition the link can sustain.
    expect(hls.autoLevelEnabled).toBe(true);
    expect(hls.levels.map((level) => level.bitrate)).toEqual([6000000, 20000000]);
    expect(hls.loadLevel).toBe(0);

    expect(harness.steps).toEqual([]);
    expect(harness.player.failure).toBeUndefined();
    expect(harness.video.currentTime).toBeGreaterThan(110);

    harness.destroy();
  });

  it('reacts to a hanging edge just ahead of hls.js, which now escalates one too', async () => {
    // The worst version of the failure: the connection is accepted and then abandoned.
    //
    // This scenario is where the upgrade to 1.7 showed most. On 1.0.10 hls.js produced non-fatal
    // timeouts every twenty seconds and did not call the stream broken for four and a half minutes,
    // which was the whole case for the stall watchdog. 1.7 abandons a silent request after
    // `maxTimeToFirstByteMs` -- ten seconds, not the two-minute whole-response deadline -- reports
    // the stall itself through its gap controller, and reaches a fatal error inside ninety seconds.
    // The watchdog still moves first, but by seconds rather than minutes.
    const harness = createPlaybackHarness({ cdn: STREAM, autoPlay: true });
    harness.cdn.intercept((request) =>
      request.kind === 'fragment' && harness.cdn.segmentIndexOf(request.path) >= 12 ? { hang: true } : undefined,
    );

    await harness.advance(200000, 200);

    // hls.js's own behaviour.
    const reasons = harness.hlsErrors.map((error) => error.reason);
    expect(reasons).toContain('networkError / fragLoadTimeOut');
    // New in 1.6+: hls.js notices the frozen picture itself, though only to report it.
    expect(reasons).toContain('mediaError / bufferStalledError');

    const firstFatal = harness.hlsErrors.find((error) => error.fatal);
    expect(firstFatal?.reason).toBe('networkError / fragLoadTimeOut');

    // The player's. The watchdog is still what refetches the playlist -- neither the timeouts nor
    // `bufferStalledError` make hls.js ask for new segment URLs, and that is what actually moves a
    // stream off a dead edge. But the margin is the thing to watch: if a future version escalates
    // before the watchdog's first action, this fails, and the watchdog has stopped earning its
    // place. It was over three minutes on 1.0.10.
    const firstAction = harness.steps.find((step) => step.message.startsWith('watchdog-'));
    expect(firstAction).toBeDefined();
    expect(firstAction!.at).toBeLessThan(firstFatal!.at);
    expect(actions(harness)).toEqual(expect.arrayContaining(['watchdog-restart', 'watchdog-reload']));

    harness.destroy();
  });

  it('escalates when the element wedges with a little buffer still ahead of it', async () => {
    // Taken from a capture on the television: playback stopped at 0.2 s of a sixty-five minute film
    // with `readyState` 1 and two 0.6 s islands of buffer, one of them ahead of the playhead. hls.js
    // reported `bufferAppendNoProgress` twice -- appended bytes were not becoming buffered range --
    // and the player did nothing for two minutes, its recovery counter reading 0 of 6.
    //
    // The reason it did nothing is the sliver: half a second ahead of the playhead cleared the
    // watchdog's threshold, so a wedged pipeline was indistinguishable from healthy playback.
    const harness = createPlaybackHarness({ cdn: STREAM, autoPlay: true });

    await harness.advance(30000);
    expect(harness.steps).toEqual([]);

    harness.playback.wedge();
    await harness.advance(150000);

    // hls.js notices, but only says so: none of this is fatal, and it never refetches a playlist.
    expect(harness.hlsErrors.map((error) => error.reason)).toContain('mediaError / bufferStalledError');
    expect(harness.hlsErrors.some((error) => error.fatal)).toBe(false);

    // The player has to be the one that acts, and it has to reach an answer rather than sit there.
    expect(actions(harness)).toEqual(expect.arrayContaining(['watchdog-restart', 'watchdog-reload']));
    expect(harness.player.failure).toMatchObject({ kind: 'recovery-exhausted' });
    expect(harness.player.recovery.attempts).toBeLessThanOrEqual(harness.player.recovery.limit);
    expect(harness.episodes).toHaveLength(1);
    expect(harness.episodes[0]).toMatchObject({
      trigger: 'persistent-wedge',
      outcome: 'abandoned',
      fatalCount: 0,
      context: {
        readyState: 1,
        networkState: expect.any(Number),
        seeking: expect.any(Boolean),
        currentTime: expect.any(Number),
        bufferedRanges: expect.any(String),
        latestHlsError: {
          category: 'buffer',
          reason: 'mediaError / bufferStalledError',
          fatal: false,
        },
        recovery: expect.objectContaining({ stallExhausted: true }),
        watchdog: expect.objectContaining({ actions: expect.any(Number) }),
      },
    });

    harness.destroy();
  });

  it('starts from a clean budget on a manual retry and resumes when the CDN recovers', async () => {
    const harness = createPlaybackHarness({ cdn: STREAM, autoPlay: true });
    const stopFailing = harness.cdn.intercept((request) =>
      request.kind === 'fragment' && harness.cdn.segmentIndexOf(request.path) >= 4 ? { status: 502 } : undefined,
    );

    await harness.advance(700000, 200);
    expect(harness.player.failure).toBeDefined();

    stopFailing();
    harness.reload();
    await harness.advance(60000, 100);

    // All of the watchdog's state lives in closure variables, so a retry that reused them would
    // inherit a spent budget and declare the fresh attempt dead within seconds.
    expect(harness.player.failure).toBeUndefined();
    expect(harness.player.recovery).toMatchObject({ exhausted: false });
    expect(harness.video.currentTime).toBeGreaterThan(0);

    harness.destroy();
  });
});
