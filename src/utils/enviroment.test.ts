import { isWebRuntime, shouldInitSentry } from './enviroment';

describe('isWebRuntime', () => {
  it('recognises local and preview HTTP origins as browser runtimes', () => {
    expect(isWebRuntime('http://localhost:3000')).toBe(true);
    expect(isWebRuntime('https://preview.example')).toBe(true);
  });

  it('leaves packaged file origins on the webOS path', () => {
    expect(isWebRuntime('file:///media/developer/apps/usr/palm/applications/app/index.html')).toBe(false);
  });
});

describe('shouldInitSentry', () => {
  it('enables configured packaged runtimes', () => {
    expect(shouldInitSentry(false, 'https://example.invalid/1')).toBe(true);
  });

  it('keeps browser and unconfigured packaged runtimes silent', () => {
    expect(shouldInitSentry(true, 'https://example.invalid/1')).toBe(false);
    expect(shouldInitSentry(false, undefined)).toBe(false);
    expect(shouldInitSentry(false, '')).toBe(false);
  });
});
