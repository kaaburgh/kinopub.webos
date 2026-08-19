import { fetchWithTimeout } from './base';

const setWindowValue = (name: string, value: unknown) => {
  Object.defineProperty(window, name, {
    configurable: true,
    writable: true,
    value,
  });
};

describe('fetchWithTimeout', () => {
  const originalFetch = window.fetch;
  const originalAbortController = window.AbortController;

  afterEach(() => {
    jest.useRealTimers();
    setWindowValue('fetch', originalFetch);
    setWindowValue('AbortController', originalAbortController);
  });

  it('fails in bounded time when AbortController is unavailable', async () => {
    jest.useFakeTimers();
    setWindowValue('AbortController', undefined);
    setWindowValue('fetch', jest.fn(() => new Promise<Response>(() => undefined)));

    const request = fetchWithTimeout('/slow', undefined, 25);

    jest.advanceTimersByTime(25);

    await expect(request).rejects.toThrow('Request timed out after 25ms');
  });

  it('passes an abort signal and cancels its timer after a successful request', async () => {
    jest.useFakeTimers();
    const abort = jest.fn();
    const signal = {} as AbortSignal;

    class TestAbortController {
      signal = signal;
      abort = abort;
    }

    const response = {} as Response;
    const fetchMock = jest.fn().mockResolvedValue(response);
    setWindowValue('AbortController', TestAbortController);
    setWindowValue('fetch', fetchMock);

    await expect(fetchWithTimeout('/ok', { method: 'GET' }, 25)).resolves.toBe(response);
    expect(fetchMock).toHaveBeenCalledWith('/ok', { method: 'GET', signal });

    jest.advanceTimersByTime(25);
    expect(abort).not.toHaveBeenCalled();
  });
});
