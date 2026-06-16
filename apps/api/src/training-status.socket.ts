import type { Server as HttpServer } from 'node:http';
import { WebSocket, WebSocketServer } from 'ws';
import { ResearchService } from './research.service';
import { TrainingStatusPayload } from './research.types';

const TRAINING_STATUS_WS_PATH = '/training-status/ws';
const TRAINING_STATUS_POLL_MS = 1000;
const HEARTBEAT_MS = 15000;

type TrainingStatusSocketMessage =
  | {
      type: 'training_status';
      emittedAt: string;
      payload: TrainingStatusPayload;
    }
  | {
      type: 'heartbeat';
      emittedAt: string;
    }
  | {
      type: 'error';
      emittedAt: string;
      message: string;
    };

export function attachTrainingStatusSocket(server: HttpServer, researchService: ResearchService): WebSocketServer {
  const socketServer = new WebSocketServer({
    server,
    path: TRAINING_STATUS_WS_PATH,
    perMessageDeflate: false,
  });
  const clients = new Set<WebSocket>();
  let lastSnapshot = '';
  let polling = false;

  async function publishSnapshot(force = false): Promise<void> {
    if (polling || clients.size === 0) {
      return;
    }
    polling = true;
    try {
      const payload = await researchService.trainingStatus();
      const snapshot = JSON.stringify(payload);
      if (force || snapshot !== lastSnapshot) {
        lastSnapshot = snapshot;
        broadcast({ type: 'training_status', emittedAt: new Date().toISOString(), payload });
      }
    } catch (error) {
      broadcast({
        type: 'error',
        emittedAt: new Date().toISOString(),
        message: error instanceof Error ? error.message : '训练状态读取失败',
      });
    } finally {
      polling = false;
    }
  }

  function broadcast(message: TrainingStatusSocketMessage): void {
    const serialized = JSON.stringify(message);
    for (const client of clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(serialized);
      }
    }
  }

  socketServer.on('connection', (socket) => {
    clients.add(socket);
    void publishSnapshot(true);

    socket.on('close', () => {
      clients.delete(socket);
    });
  });

  setInterval(() => {
    void publishSnapshot();
  }, TRAINING_STATUS_POLL_MS).unref();

  setInterval(() => {
    if (clients.size > 0) {
      broadcast({ type: 'heartbeat', emittedAt: new Date().toISOString() });
    }
  }, HEARTBEAT_MS).unref();

  return socketServer;
}
