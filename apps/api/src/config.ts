export const DEFAULT_API_PORT = 3000;

export function parseApiPort(value: string | undefined, defaultPort = DEFAULT_API_PORT): number {
  if (value === undefined || value.trim() === '') {
    return defaultPort;
  }
  const port = Number(value);
  if (!Number.isInteger(port) || port < 0 || port > 65535) {
    return defaultPort;
  }
  return port;
}
