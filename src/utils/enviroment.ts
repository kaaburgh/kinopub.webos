export function isWebRuntime(origin: string) {
  return origin.startsWith('http');
}

export function shouldInitSentry(isWeb: boolean, dsn?: string): dsn is string {
  return !isWeb && Boolean(dsn);
}

export const IS_WEB = isWebRuntime(window.location.origin);
