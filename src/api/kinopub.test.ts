import KinopubApiClient from './kinopub';

jest.mock('utils/logging', () => ({ logApiFailure: jest.fn() }));

type Tokens = { access_token?: string; refresh_token?: string };

/**
 * The real client keeps tokens in localStorage and cookies. These tests are about the decisions the
 * client makes, so a plain object stands in for that storage — shared between instances when a test
 * needs it, because every hook creates its own `ApiClient` while the tokens are process-wide.
 */
class TestClient extends KinopubApiClient {
  store: { tokens: Tokens };

  constructor(store: { tokens: Tokens }) {
    super('client', 'secret', 'https://api.test');

    this.store = store;
  }

  protected getAccessToken() {
    return this.store.tokens.access_token as string;
  }

  protected getRefreshToken() {
    return this.store.tokens.refresh_token as string;
  }

  protected saveTokens({ access_token, refresh_token }: { access_token: string; refresh_token: string; expires_in: number }) {
    this.store.tokens = { access_token, refresh_token };
  }

  protected clearTokens() {
    this.store.tokens = {};
  }
}

const deviceInfo = { title: 'Kinopub', hardware: 'LG', software: 'webOS' };

const setWindowValue = (name: string, value: unknown) => {
  Object.defineProperty(window, name, {
    configurable: true,
    writable: true,
    value,
  });
};

const answer = (status: number, body: object) =>
  ({
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response);

/** Something in front of the API answered instead of it: a proxy, a captive portal, a CDN edge. */
const htmlPage = (status: number) =>
  ({
    status,
    json: () => Promise.reject(new SyntaxError('Unexpected token <')),
  } as unknown as Response);

const unreachable = () => Promise.reject(new TypeError('Failed to fetch'));

type Route = (url: string) => Promise<Response> | Response | undefined;

/** Answers each request with the first route that claims it; an unclaimed request fails the test. */
function installBackend(...routes: Route[]) {
  const fetchMock = jest.fn((url: string) => {
    for (const route of routes) {
      const response = route(url);

      if (response) {
        return Promise.resolve(response);
      }
    }

    throw new Error(`Unexpected request: ${url}`);
  });

  setWindowValue('fetch', fetchMock);

  return fetchMock;
}

const isRefresh = (url: string) => url.includes('/oauth2/token') && url.includes('grant_type=refresh_token');
const isDeviceCode = (url: string) => url.includes('/oauth2/device') && url.includes('grant_type=device_code');
const isDevicePoll = (url: string) => url.includes('/oauth2/device') && url.includes('grant_type=device_token');
const isNotify = (url: string) => url.includes('/v1/device/notify');
const isUser = (url: string) => url.includes('/v1/user');

const renewed = (access_token: string, refresh_token: string) => answer(200, { access_token, refresh_token, expires_in: 3600 });

const deviceCode = (user_code: string) =>
  answer(200, { code: `device-${user_code}`, user_code, verification_uri: 'https://kino.pub/device', interval: 5, expires_in: 600 });

async function flushPromises() {
  for (let i = 0; i < 20; i += 1) {
    await Promise.resolve();
  }
}

/** Advances virtual time in steps, letting the awaited request chain run between them. */
async function advance(ms: number, step = 1000) {
  for (let elapsed = 0; elapsed < ms; elapsed += step) {
    jest.advanceTimersByTime(step);
    await flushPromises();
  }
}

function track<T>(promise: Promise<T>) {
  const state = { settled: false, rejected: false };

  promise.then(
    () => {
      state.settled = true;
    },
    () => {
      state.settled = true;
      state.rejected = true;
    },
  );

  return state;
}

describe('KinopubApiClient session renewal', () => {
  const originalFetch = window.fetch;
  const clients: TestClient[] = [];

  const createClient = (store: { tokens: Tokens }) => {
    const client = new TestClient(store);

    clients.push(client);

    return client;
  };

  beforeEach(() => {
    jest.useFakeTimers('modern');
  });

  afterEach(() => {
    clients.splice(0).forEach((client) => client.clearTimers());
    jest.useRealTimers();
    setWindowValue('fetch', originalFetch);
  });

  it('keeps the refresh token through a startup with no network, and renews once it returns', async () => {
    let networkUp = false;
    const store = { tokens: { refresh_token: 'r1' } };
    const client = createClient(store);
    const onConfirm = jest.fn();

    installBackend(
      () => (networkUp ? undefined : unreachable()),
      (url) => (isRefresh(url) ? renewed('a2', 'r2') : undefined),
      (url) => (isNotify(url) ? answer(200, {}) : undefined),
    );

    const authorization = track(client.deviceAuthorization(deviceInfo, onConfirm));

    await advance(10 * 1000);

    expect(store.tokens.refresh_token).toBe('r1');
    expect(authorization.settled).toBe(false);

    networkUp = true;
    await advance(60 * 1000);

    expect(authorization).toEqual({ settled: true, rejected: false });
    expect(onConfirm).not.toHaveBeenCalled();
    expect(store.tokens).toEqual({ access_token: 'a2', refresh_token: 'r2' });
  });

  it('waits for the renewal even while the access token is still valid', async () => {
    // Starting early would send the first screen's requests into a dead network, and their
    // `{ error }` bodies would be cached as data and never refetched once it came back.
    let networkUp = false;
    const store = { tokens: { access_token: 'a1', refresh_token: 'r1' } };
    const client = createClient(store);
    const onConfirm = jest.fn();

    installBackend(
      () => (networkUp ? undefined : unreachable()),
      (url) => (isRefresh(url) ? renewed('a2', 'r2') : undefined),
      (url) => (isNotify(url) ? answer(200, {}) : undefined),
    );

    const authorization = track(client.deviceAuthorization(deviceInfo, onConfirm));

    await advance(10 * 1000);

    expect(authorization.settled).toBe(false);
    expect(store.tokens).toEqual({ access_token: 'a1', refresh_token: 'r1' });

    networkUp = true;
    await advance(60 * 1000);

    expect(authorization).toEqual({ settled: true, rejected: false });
    expect(onConfirm).not.toHaveBeenCalled();
    expect(store.tokens).toEqual({ access_token: 'a2', refresh_token: 'r2' });
  });

  it.each([
    ['answers with an HTML error page', htmlPage(403)],
    ['answers 503', answer(503, { error: 'server_error' })],
    ['rate-limits', answer(429, { error: 'too_many_requests' })],
  ])('keeps the session when the token endpoint %s', async (_, failure) => {
    const store = { tokens: { refresh_token: 'r1' } };
    const client = createClient(store);
    const onConfirm = jest.fn();
    let failed = false;

    installBackend(
      (url) => {
        if (isRefresh(url) && !failed) {
          failed = true;

          return failure;
        }

        return undefined;
      },
      (url) => (isRefresh(url) ? renewed('a2', 'r2') : undefined),
      (url) => (isNotify(url) ? answer(200, {}) : undefined),
    );

    const authorization = track(client.deviceAuthorization(deviceInfo, onConfirm));

    await advance(60 * 1000);

    expect(authorization).toEqual({ settled: true, rejected: false });
    expect(onConfirm).not.toHaveBeenCalled();
    expect(store.tokens).toEqual({ access_token: 'a2', refresh_token: 'r2' });
  });

  it.each([
    ['400 invalid_grant', answer(400, { error: 'invalid_grant' })],
    ['401', answer(401, { error: 'unauthorized' })],
  ])('starts pairing when the backend refuses the refresh token with %s', async (_, refusal) => {
    const store = { tokens: { access_token: 'a1', refresh_token: 'r1' } as Tokens };
    const client = createClient(store);
    const onConfirm = jest.fn();

    installBackend(
      (url) => (isRefresh(url) ? refusal : undefined),
      (url) => (isDeviceCode(url) ? deviceCode('ABC123') : undefined),
      (url) => (isDevicePoll(url) ? answer(400, { error: 'authorization_pending' }) : undefined),
    );

    client.deviceAuthorization(deviceInfo, onConfirm);

    await advance(5 * 1000);

    expect(store.tokens).toEqual({});
    expect(onConfirm).toHaveBeenCalledWith('ABC123', 'https://kino.pub/device');
  });

  it('sends one refresh request when several clients renew at once', async () => {
    const store = { tokens: { refresh_token: 'r1' } };
    const fetchMock = installBackend(
      (url) => (isRefresh(url) ? renewed('a2', 'r2') : undefined),
      (url) => (isNotify(url) ? answer(200, {}) : undefined),
    );

    await Promise.all([createClient(store).deviceAuthorization(deviceInfo), createClient(store).deviceAuthorization(deviceInfo)]);

    expect(fetchMock.mock.calls.filter(([url]) => isRefresh(url))).toHaveLength(1);
    expect(store.tokens).toEqual({ access_token: 'a2', refresh_token: 'r2' });
  });

  it('renews an expired access token on 401 and retries the request once', async () => {
    const store = { tokens: { access_token: 'a1', refresh_token: 'r1' } };
    const fetchMock = installBackend(
      (url) => (isUser(url) && url.includes('access_token=a1') ? answer(401, { error: 'unauthorized' }) : undefined),
      (url) => (isRefresh(url) ? renewed('a2', 'r2') : undefined),
      (url) => (isUser(url) && url.includes('access_token=a2') ? answer(200, { user: { username: 'viewer' } }) : undefined),
    );

    const [first, second] = await Promise.all([createClient(store).user(), createClient(store).user()]);

    expect(first).toEqual({ user: { username: 'viewer' } });
    expect(second).toEqual({ user: { username: 'viewer' } });
    expect(fetchMock.mock.calls.filter(([url]) => isRefresh(url))).toHaveLength(1);
    expect(store.tokens).toEqual({ access_token: 'a2', refresh_token: 'r2' });
  });

  it('keeps the session when a 401 cannot be renewed because the network is gone', async () => {
    const store = { tokens: { access_token: 'a1', refresh_token: 'r1' } };

    installBackend(
      (url) => (isUser(url) ? answer(401, { error: 'unauthorized' }) : undefined),
      (url) => (isRefresh(url) ? unreachable() : undefined),
    );

    await expect(createClient(store).user()).resolves.toEqual({ error: 'unauthorized' });
    expect(store.tokens).toEqual({ access_token: 'a1', refresh_token: 'r1' });
  });

  it('ends the session on 401 when there is no refresh token to renew it with', async () => {
    const store = { tokens: { access_token: 'a1' } as Tokens };

    installBackend((url) => (isUser(url) ? answer(401, { error: 'unauthorized' }) : undefined));

    await createClient(store).user();

    expect(store.tokens).toEqual({});
  });

  it('keeps polling the same pairing code through a transient failure', async () => {
    const store = { tokens: {} as Tokens };
    const client = createClient(store);
    const onConfirm = jest.fn();
    let polls = 0;

    installBackend(
      (url) => (isDeviceCode(url) ? deviceCode('ABC123') : undefined),
      (url) => {
        if (!isDevicePoll(url)) {
          return undefined;
        }

        polls += 1;

        return polls === 1 ? unreachable() : renewed('a1', 'r1');
      },
      (url) => (isNotify(url) ? answer(200, {}) : undefined),
    );

    const authorization = track(client.deviceAuthorization(deviceInfo, onConfirm));

    await advance(30 * 1000);

    expect(authorization).toEqual({ settled: true, rejected: false });
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(store.tokens).toEqual({ access_token: 'a1', refresh_token: 'r1' });
  });

  it('does not clear a session another authorization established while it waited to retry', async () => {
    // The authorization effect can start a second attempt on the same client while the first is
    // still asking for a code. If the second pairs first, the first must not wipe that session.
    const store = { tokens: {} as Tokens };
    const client = createClient(store);
    const onConfirm = jest.fn();
    let answerFirstCodeRequest: (response: Response) => void = () => undefined;
    let codeRequests = 0;

    const fetchMock = installBackend(
      (url) => {
        if (!isDeviceCode(url)) {
          return undefined;
        }

        codeRequests += 1;

        return codeRequests === 1
          ? new Promise<Response>((resolve) => {
              answerFirstCodeRequest = resolve;
            })
          : deviceCode(`CODE${codeRequests}`);
      },
      (url) => (isDevicePoll(url) ? renewed('a1', 'r1') : undefined),
      (url) => (isRefresh(url) ? renewed('a2', 'r2') : undefined),
      (url) => (isNotify(url) ? answer(200, {}) : undefined),
    );

    const first = track(client.deviceAuthorization(deviceInfo, onConfirm));

    await flushPromises();

    const second = track(client.deviceAuthorization(deviceInfo, onConfirm));

    await advance(10 * 1000);

    expect(second).toEqual({ settled: true, rejected: false });
    expect(store.tokens).toEqual({ access_token: 'a1', refresh_token: 'r1' });

    answerFirstCodeRequest(answer(503, { error: 'server_error' }));
    await advance(60 * 1000);

    // As before this change: the retry finds the stored session and renews it instead of pairing.
    expect(first).toEqual({ settled: true, rejected: false });
    expect(store.tokens).toEqual({ access_token: 'a2', refresh_token: 'r2' });
    expect(fetchMock.mock.calls.filter(([url]) => isDeviceCode(url))).toHaveLength(2);
  });
});
