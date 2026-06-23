export const DEFAULT_API_PORT = 3000;

export function parseApiPort(value: string | undefined, defaultPort = DEFAULT_API_PORT): number {
  const rawPort = value?.trim();
  if (rawPort === undefined || rawPort === '' || !/^\d+$/.test(rawPort)) {
    return defaultPort;
  }
  const port = Number(rawPort);
  if (!Number.isInteger(port) || port < 0 || port > 65535) {
    return defaultPort;
  }
  return port;
}
