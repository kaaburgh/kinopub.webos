import { getExpectedMediaPlayInterruption, installMediaPlayAbortGuard } from './mediaPlayAbortGuard';

function abortError(message: string) {
  const error = new Error(message);
  error.name = 'AbortError';
  return error;
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });

  return { promise, resolve, reject };
}

describe('media play AbortError guard', () => {
  test('classifies only the known pause and load interruption messages', () => {
    expect(getExpectedMediaPlayInterruption(abortError('The play() request was interrupted by a call to pause().'))).toBe('pause');
    expect(getExpectedMediaPlayInterruption(abortError('The play() request was interrupted by a new load request.'))).toBe('load');
    expect(getExpectedMediaPlayInterruption(abortError('The play() request was interrupted for another reason.'))).toBeUndefined();
    expect(getExpectedMediaPlayInterruption(new Error('decoder failed'))).toBeUndefined();
  });

  test.each([
    ['pause', 'The play() request was interrupted by a call to pause().'],
    ['load', 'The play() request was interrupted by a new load request.'],
  ] as const)('handles an expected %s interruption before it can escape as an unhandled rejection', async (action, message) => {
    const pending = deferred<void>();
    const prototype = { play: jest.fn(() => pending.promise) as HTMLMediaElement['play'] };
    const onExpectedInterruption = jest.fn();

    installMediaPlayAbortGuard(prototype, onExpectedInterruption);

    const guardedPromise = prototype.play.call({} as HTMLMediaElement);
    pending.reject(abortError(message));

    await expect(guardedPromise).resolves.toBeUndefined();
    expect(onExpectedInterruption).toHaveBeenCalledTimes(1);
    expect(onExpectedInterruption).toHaveBeenCalledWith(action);
  });

  test('keeps unexpected AbortErrors rejected', async () => {
    const pending = deferred<void>();
    const prototype = { play: jest.fn(() => pending.promise) as HTMLMediaElement['play'] };

    installMediaPlayAbortGuard(prototype, jest.fn());

    const guardedPromise = prototype.play.call({} as HTMLMediaElement);
    const error = abortError('The play() request was interrupted for another reason.');
    pending.reject(error);

    await expect(guardedPromise).rejects.toBe(error);
  });

  test('keeps non-AbortError play failures rejected even when their message mentions pause', async () => {
    const pending = deferred<void>();
    const prototype = { play: jest.fn(() => pending.promise) as HTMLMediaElement['play'] };

    installMediaPlayAbortGuard(prototype, jest.fn());

    const guardedPromise = prototype.play.call({} as HTMLMediaElement);
    const error = new Error('The play() request was interrupted by a call to pause().');
    pending.reject(error);

    await expect(guardedPromise).rejects.toBe(error);
  });

  test('does not stack wrappers when installation runs twice', () => {
    const originalPlay = jest.fn(() => Promise.resolve()) as HTMLMediaElement['play'];
    const prototype = { play: originalPlay };

    installMediaPlayAbortGuard(prototype, jest.fn());
    const onceGuarded = prototype.play;
    installMediaPlayAbortGuard(prototype, jest.fn());

    expect(prototype.play).toBe(onceGuarded);
  });
});
