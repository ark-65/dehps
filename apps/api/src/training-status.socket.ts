import type { Server as HttpServer } from 'node:http';
import { WebSocketServer } from 'ws';
import { ResearchService } from './research.service';
import { TrainingStatusHub } from './training-status.hub';

const TRAINING_STATUS_WS_PATH = '/training-status/ws';
const HEARTBEAT_MS = 15000;

export function attachTrainingStatusSocket(
  server: HttpServer,
  trainingStatusHub: TrainingStatusHub,
  researchService: ResearchService,
): WebSocketServer {
  const socketServer = new WebSocketServer({
    server,
    path: TRAINING_STATUS_WS_PATH,
    perMessageDeflate: false,
  });

  socketServer.on('connection', (socket) => {
    trainingStatusHub.addClient(socket);
    const cached = trainingStatusHub.latestStatus();
    if (cached) {
      trainingStatusHub.sendStatus(socket, cached);
      return;
    }
    void researchService
      .trainingStatus()
      .then((payload) => {
        trainingStatusHub.publishStatus(payload);
      })
      .catch((error: unknown) => {
        trainingStatusHub.sendError(socket, error instanceof Error ? error.message : '训练状态读取失败');
      });
  });

  setInterval(() => {
    trainingStatusHub.publishHeartbeat();
  }, HEARTBEAT_MS).unref();

  return socketServer;
}
