import {
  findHlsFixedLevelChoiceByFingerprint,
  findHlsFixedLevelIndex,
  getHlsFixedLevelChoices,
  getHlsFixedLevelFingerprint,
  getHlsFixedLevelSourceName,
} from './hlsLevels';

describe('exact HLS level choices', () => {
  const levels = [
    { width: 1920, height: 804, bitrate: 4000000, videoCodec: 'avc1.640028' },
    { width: 1920, height: 804, bitrate: 8000000, videoCodec: 'avc1.640032' },
    { width: 1280, height: 536, bitrate: 2500000, videoCodec: 'avc1.64001f' },
  ];

  test('keeps every manifest level selectable even when resolutions repeat', () => {
    expect(getHlsFixedLevelChoices(levels)).toEqual([
      { index: 0, name: 'HLS 1: 1080p (1920x804)' },
      { index: 1, name: 'HLS 2: 1080p (1920x804)' },
      { index: 2, name: 'HLS 3: 720p (1280x536)' },
    ]);
  });

  test('resolves only names generated for the current manifest', () => {
    const second = getHlsFixedLevelSourceName(levels[1], 1);

    expect(findHlsFixedLevelIndex(levels, second)).toBe(1);
    expect(findHlsFixedLevelIndex(levels, 'HLS 4: 2160p (3840x1606)')).toBe(-1);
  });

  test('restores the same rendition when a replacement manifest reorders equal-resolution levels', () => {
    const fingerprint = getHlsFixedLevelFingerprint(levels[0]);
    const reordered = [levels[1], levels[0], levels[2]];

    expect(findHlsFixedLevelChoiceByFingerprint(reordered, fingerprint)).toEqual({
      index: 1,
      name: 'HLS 2: 1080p (1920x804)',
    });
  });

  test('fails closed when rendition fingerprints collide', () => {
    const collidingLevels = [
      { width: 1920, height: 804, bitrate: 4000000, videoCodec: 'avc1.640028' },
      { width: 1920, height: 804, bitrate: 4000000, videoCodec: 'avc1.640028' },
    ];
    const fingerprint = getHlsFixedLevelFingerprint(collidingLevels[0]);

    expect(findHlsFixedLevelChoiceByFingerprint(collidingLevels, fingerprint)).toBeUndefined();
  });

  test('falls back to a deterministic level label when dimensions are unavailable', () => {
    expect(getHlsFixedLevelSourceName({}, 0)).toBe('HLS 1: качество неизвестно');
  });
});
