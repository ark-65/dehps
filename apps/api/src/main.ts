import 'reflect-metadata';

import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { parseApiPort } from './config';
import { ResearchService } from './research.service';
import { TrainingStatusHub } from './training-status.hub';
import { attachTrainingStatusSocket } from './training-status.socket';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.enableCors();
  attachTrainingStatusSocket(app.getHttpServer(), app.get(TrainingStatusHub), app.get(ResearchService));
  const port = parseApiPort(process.env.API_PORT);
  await app.listen(port);
  console.log(`Training status WebSocket listening on ws://localhost:${port}/training-status/ws`);
}

void bootstrap();
