import { settleHlsSourceQuality, transitionHlsSource } from './diagnosticsSourceHistory';

describe('diagnostics HLS source history', () => {
  it('uses the settled in-place quality as the outgoing side of a later replacement', () => {
    const firstHls = {};
    const replacementHls = {};

    let state = transitionHlsSource(null, firstHls, '720p').state;

    // The player selection changes before hls.js proves the switch. Do not rewrite history yet.
    state = transitionHlsSource(state, firstHls, '1080p').state;
    expect(state.quality).toBe('720p');

    // LEVEL_SWITCHED is the proof that the existing instance really adopted the selection.
    state = settleHlsSourceQuality(state, firstHls, '1080p')!;

    const replacement = transitionHlsSource(state, replacementHls, '1080p');

    expect(replacement.change).toBe('1080p -> 1080p');
    expect(replacement.state).toEqual({ hls: replacementHls, quality: '1080p' });
  });

  it('keeps the old outgoing quality when a replacement happens before the in-place switch settles', () => {
    const firstHls = {};
    const replacementHls = {};

    let state = transitionHlsSource(null, firstHls, '720p').state;
    state = transitionHlsSource(state, firstHls, '1080p').state;

    const replacement = transitionHlsSource(state, replacementHls, '1080p');

    expect(replacement.change).toBe('720p -> 1080p');
  });
});
