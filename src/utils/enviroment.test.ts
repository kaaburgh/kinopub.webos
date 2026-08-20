import { isWebRuntime } from './enviroment';

describe('isWebRuntime', () => {
  it('recognises local and preview HTTP origins as browser runtimes', () => {
    expect(isWebRuntime('http://localhost:3000')).toBe(true);
    expect(isWebRuntime('https://preview.example')).toBe(true);
  });

  it('leaves packaged file origins on the webOS path', () => {
    expect(isWebRuntime('file:///media/developer/apps/usr/palm/applications/app/index.html')).toBe(false);
  });
});
