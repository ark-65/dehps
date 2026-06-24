export const DEFAULT_API_PORT = 3000;
export const DEFAULT_DB_PORT = 54329;

export function parsePort(value: string | undefined, defaultPort: number): number {
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

export function parseApiPort(value: string | undefined, defaultPort = DEFAULT_API_PORT): number {
  return parsePort(value, defaultPort);
}

export function parseDbPort(value: string | undefined, defaultPort = DEFAULT_DB_PORT): number {
  return parsePort(value, defaultPort);
}
