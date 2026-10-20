import { RETRY_MAX_DELAY_MS, classifySessionRenewal, isTransientAnswer, retryDelayMs } from './sessionRenewal';

const tokens = { access_token: 'a', refresh_token: 'r' };

describe('classifySessionRenewal', () => {
  it('accepts new tokens', () => {
    expect(classifySessionRenewal({ status: 200, parsed: true, body: tokens })).toBe('renewed');
  });

  it.each([
    ['nothing came back', { status: undefined, parsed: false, body: { error: 'TypeError: Failed to fetch' } }],
    ['an HTML error page answered', { status: 403, parsed: false, body: { error: 'SyntaxError: Unexpected token <' } }],
    ['the backend failed', { status: 500, parsed: true, body: { error: 'server_error' } }],
    ['the backend is rate limiting', { status: 429, parsed: true, body: {} }],
    ['the request timed out upstream', { status: 408, parsed: true, body: {} }],
    ['a success status came without tokens', { status: 200, parsed: true, body: {} }],
    ['a success status named no refusal', { status: 200, parsed: true, body: { error: 'temporarily_unavailable' } }],
  ])('keeps the session when %s', (_, answer) => {
    expect(classifySessionRenewal(answer)).toBe('unavailable');
  });

  it.each([
    ['400 invalid_grant', { status: 400, parsed: true, body: { error: 'invalid_grant' } }],
    ['401', { status: 401, parsed: true, body: { error: 'unauthorized' } }],
    ['a JSON 4xx without an error code', { status: 403, parsed: true, body: {} }],
    ['an RFC 6749 refusal behind a success status', { status: 200, parsed: true, body: { error: 'invalid_grant' } }],
  ])('ends the session on %s', (_, answer) => {
    expect(classifySessionRenewal(answer)).toBe('rejected');
  });

  it('does not trust tokens that arrive alongside an error', () => {
    expect(classifySessionRenewal({ status: 400, parsed: true, body: { ...tokens, error: 'invalid_grant' } })).toBe('rejected');
  });
});

describe('isTransientAnswer', () => {
  it('treats the authorization-pending poll answer as an answer, not an outage', () => {
    expect(isTransientAnswer({ status: 400, parsed: true })).toBe(false);
  });
});

describe('retryDelayMs', () => {
  it('backs off exponentially and stays bounded', () => {
    expect([0, 1, 2, 3].map(retryDelayMs)).toEqual([2000, 4000, 8000, 16000]);
    expect(retryDelayMs(10)).toBe(RETRY_MAX_DELAY_MS);
    expect(retryDelayMs(-1)).toBe(2000);
  });
});
