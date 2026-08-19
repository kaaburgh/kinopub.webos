const { buildCompactText, FORMAT_VERSION } = require('./diagnosticsExport');
// Keep this dynamic: TypeScript checks JS tests under `src`, and a literal require would pull the
// Node-only reference decoder outside tsconfig's `rootDir` into the application program.
const decoderPath = ['..', '..', '..', 'scripts', 'decode-diagnostics'].join('/');
const { formatReport, parseCompactText } = require(decoderPath);

describe('diagnostics export format', () => {
  it('round-trips per-stream fragments, decode severity, and source-change markers in v2', () => {
    const text = buildCompactText({
      capturedAt: 1000,
      appVersion: '1.3.0',
      lastFragments: {
        audio: { level: 1, bytes: 1200, loadSeconds: 0.25, ageSeconds: 1.5 },
        main: { level: 2, height: 1080, bytes: 8000, loadSeconds: 0.5, ageSeconds: 1 },
      },
      decode: { totalFrames: 2400, droppedFrames: 48, severity: 'warning' },
      events: [{ timestamp: 900, source: 'hls', name: 'SOURCE_CHANGED', details: '720p -> 1080p' }],
    });

    expect(FORMAT_VERSION).toBe(2);
    expect(text).toContain('f|main|2|1080|8000|0.5|1');
    expect(text).toContain('f|audio|1||1200|0.25|1.5');
    expect(text).toContain('q|2400|48|warning');

    const report = parseCompactText(text);

    expect(report.lastFragments).toEqual({
      main: { level: '2', height: '1080', bytes: '8000', loadSeconds: '0.5', ageSeconds: '1' },
      audio: { level: '1', height: undefined, bytes: '1200', loadSeconds: '0.25', ageSeconds: '1.5' },
    });
    expect(report.decode).toEqual({ totalFrames: 2400, droppedFrames: 48, severity: 'warning' });
    expect(report.events).toEqual([{ timestamp: 900, source: 'hls', name: 'SOURCE_CHANGED', details: '720p -> 1080p' }]);

    const formatted = formatReport(report);

    expect(formatted).toContain('lastFrag[main]: level=2');
    expect(formatted).toContain('lastFrag[audio]: track=1');
    expect(formatted).toContain('decode:   frames=2400 dropped=48 severity=warning');
  });

  it('keeps v1 captures readable as an implicit main fragment', () => {
    const report = parseCompactText(['v|1|1000|1.2.0', 'f|2|1080|8000|0.5|1', 'q|2400|48'].join('\n'));

    expect(report.lastFragment).toEqual({
      level: '2',
      height: '1080',
      bytes: '8000',
      loadSeconds: '0.5',
      ageSeconds: '1',
    });
    expect(report.lastFragments.main).toEqual(report.lastFragment);
    expect(report.decode).toEqual({ totalFrames: 2400, droppedFrames: 48, severity: undefined });
    expect(formatReport(report)).toContain('lastFrag[main]: level=2');
  });
});
