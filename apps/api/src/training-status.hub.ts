import { Injectable } from '@nestjs/common';
import { WebSocket } from 'ws';
import { TrainingStatusPayload } from './research.types';

export type TrainingStatusSocketMessage =
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

@Injectable()
export class TrainingStatusHub {
  private readonly clients = new Set<WebSocket>();
  private latest: TrainingStatusPayload | null = null;

  addClient(socket: WebSocket): void {
    this.clients.add(socket);
    socket.on('close', () => {
      this.clients.delete(socket);
    });
  }

  latestStatus(): TrainingStatusPayload | null {
    return this.latest;
  }

  publishStatus(payload: TrainingStatusPayload): void {
    this.latest = payload;
    this.broadcast({ type: 'training_status', emittedAt: new Date().toISOString(), payload });
  }

  publishHeartbeat(): void {
    if (this.clients.size > 0) {
      this.broadcast({ type: 'heartbeat', emittedAt: new Date().toISOString() });
    }
  }

  sendStatus(socket: WebSocket, payload: TrainingStatusPayload): void {
    this.send(socket, { type: 'training_status', emittedAt: new Date().toISOString(), payload });
  }

  sendError(socket: WebSocket, message: string): void {
    this.send(socket, { type: 'error', emittedAt: new Date().toISOString(), message });
  }

  private broadcast(message: TrainingStatusSocketMessage): void {
    for (const client of this.clients) {
      this.send(client, message);
    }
  }

  private send(socket: WebSocket, message: TrainingStatusSocketMessage): void {
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message));
    }
  }
}
