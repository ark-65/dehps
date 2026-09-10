/** Credential-free deployment entry for one read-only control-domain mount. */
import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { ExecutionStatusModule, parseExecutionStatusSources } from './execution-status';
import { parseApiPort } from './config';

export async function startExecutionStatusApi(port = parseApiPort(process.env.API_PORT)) {
  const sources = parseExecutionStatusSources(process.env.DEHPS_EXECUTION_STATUS_SOURCES);
  if (sources.length !== 1 || sources[0].root !== '/status') {
    throw new Error('standalone status API requires one explicit /status binding');
  }
  if (process.getuid?.() === 0) throw new Error('status API must run as a non-root UID');
  if (Object.entries(process.env).some(([key, value]) => value &&
    (/^(PG|DB_)/.test(key) || /(?:PASSWORD|SECRET|TOKEN|CREDENTIAL|DSN)/.test(key)))) {
    throw new Error('status API must receive no credentials');
  }
  const app = await NestFactory.create(ExecutionStatusModule, { logger: false });
  app.enableShutdownHooks();
  await app.listen(port, '0.0.0.0');
  return app;
}

if (require.main === module) {
  startExecutionStatusApi().catch(error => {
    console.error(error instanceof Error ? error.message : 'status API startup failed');
    process.exitCode = 1;
  });
}
