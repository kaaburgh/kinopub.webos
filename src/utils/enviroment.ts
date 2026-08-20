export function isWebRuntime(origin: string) {
  return origin.startsWith('http');
}

export const IS_WEB = isWebRuntime(window.location.origin);
