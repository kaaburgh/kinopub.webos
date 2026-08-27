import { findHlsFixedLevelIndex, getHlsFixedLevelChoices, getHlsFixedLevelSourceName } from './hlsLevels';

describe('exact HLS level choices', () => {
  const levels = [
    { width: 1920, height: 804 },
    { width: 1920, height: 804 },
    { width: 1280, height: 536 },
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

  test('falls back to a deterministic level label when dimensions are unavailable', () => {
    expect(getHlsFixedLevelSourceName({}, 0)).toBe('HLS 1: качество неизвестно');
  });
});
