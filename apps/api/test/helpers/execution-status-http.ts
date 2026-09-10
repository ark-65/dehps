/** Integration probe: actual API module, no database providers or credentials. */
import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { ExecutionStatusModule } from '../../src/execution-status';

async function main() {
  if (process.env.DEHPS_EXECUTION_TEST_ADMIN_DSN || process.env.DB_PASSWORD) {
    throw new Error('status API probe must receive no database credentials');
  }
  const app = await NestFactory.create(ExecutionStatusModule, { logger: false });
  try {
    await app.listen(0, '127.0.0.1');
    const sources = JSON.parse(process.env.DEHPS_EXECUTION_STATUS_SOURCES ?? '[]');
    if (sources.length !== 1) throw new Error('probe requires exactly one configured domain');
    const response = await fetch(await app.getUrl() + '/execution-status/' + encodeURIComponent(sources[0].controlPlane));
    if (!response.ok) throw new Error('configured execution status endpoint failed');
    console.log(JSON.stringify(await response.json()));
  } finally { await app.close(); }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
