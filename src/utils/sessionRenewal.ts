/**
 * Rules for renewing the KinoPub session.
 *
 * The client used to treat every unsuccessful refresh as the end of the session: it cleared the
 * tokens first and looked at the answer second. A television that is switched on starts the app
 * before its network is up, so the refresh failed for reasons that had nothing to do with the
 * token, the token was gone, and the viewer was asked to pair the TV again — on every power-on.
 *
 * The rule here is the opposite default: only the backend can end a session, and only by answering
 * that it refuses the token. Anything that is not such an answer keeps the tokens and is retried.
 */

export type SessionRenewal =
  /** New tokens arrived. */
  | 'renewed'
  /** The backend answered that it will not renew this session. Pairing is the only way back. */
  | 'rejected'
  /** No usable answer: nothing came back, something other than the API answered, or it was busy. */
  | 'unavailable';

export type ApiAnswer<T> = {
  body: T;
  /** HTTP status, or undefined when nothing came back — unreachable, or timed out. */
  status?: number;
  /** False when the answer was not JSON, which means something in front of the API answered. */
  parsed: boolean;
};

/**
 * RFC 6749 §5.2 errors. A token endpoint that answers with one of these has understood the request
 * and refused it, whatever HTTP status it chose to send them with.
 */
const REFUSAL_ERRORS = [
  'invalid_request',
  'invalid_client',
  'invalid_grant',
  'unauthorized_client',
  'unsupported_grant_type',
  'invalid_scope',
];

/**
 * Whether an answer says nothing about the request itself, so the same request may succeed later.
 *
 * Not JSON covers a captive portal or a proxy error page while the network comes up; 408 and 429
 * ask to come back later; 5xx is the backend failing. None of them is a statement about the token.
 */
export function isTransientAnswer({ status, parsed }: Pick<ApiAnswer<unknown>, 'status' | 'parsed'>) {
  return status === undefined || !parsed || status === 408 || status === 429 || status >= 500;
}

export function classifySessionRenewal({
  status,
  parsed,
  body,
}: ApiAnswer<{ access_token?: string; refresh_token?: string; error?: string }>): SessionRenewal {
  if (isTransientAnswer({ status, parsed })) {
    return 'unavailable';
  }

  if (!body.error && body.access_token && body.refresh_token) {
    return 'renewed';
  }

  // A JSON 4xx from the token endpoint is the backend refusing — 401 for credentials it does not
  // accept, 400 for an `invalid_grant` refresh token. Retrying the same token cannot change that.
  if (status !== undefined && status >= 400 && status < 500) {
    return 'rejected';
  }

  // A success status without tokens is malformed rather than a refusal, unless it names one.
  return body.error && REFUSAL_ERRORS.indexOf(body.error) !== -1 ? 'rejected' : 'unavailable';
}

export const RETRY_BASE_DELAY_MS = 2 * 1000;
export const RETRY_MAX_DELAY_MS = 30 * 1000;

/** 2 s, 4 s, 8 s, … up to 30 s: quick while the network is coming up, quiet if it stays down. */
export function retryDelayMs(attempt: number) {
  return Math.min(RETRY_BASE_DELAY_MS * Math.pow(2, Math.max(attempt, 0)), RETRY_MAX_DELAY_MS);
}
