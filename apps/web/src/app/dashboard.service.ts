import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import {
  DashboardPayload,
  ExperimentDetail,
  ExperimentSummary,
  FeatureDistribution,
  PipelineRunSummary,
  SyncRunSummary,
  TrainingStatusPayload,
} from './dashboard.model';

export type TrainingConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';

export type TrainingStatusStreamState = {
  connection: TrainingConnectionState;
  payload: TrainingStatusPayload | null;
  message: string | null;
};

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

@Injectable({ providedIn: 'root' })
export class DashboardService {
  constructor(private readonly http: HttpClient) {}

  load(): Observable<DashboardPayload> {
    return this.http.get<DashboardPayload>('/dashboard');
  }

  loadExperiments(): Observable<ExperimentSummary[]> {
    return this.http.get<ExperimentSummary[]>('/experiments');
  }

  loadPipelineRuns(): Observable<PipelineRunSummary[]> {
    return this.http.get<PipelineRunSummary[]>('/pipeline-runs');
  }

  loadSyncRuns(): Observable<SyncRunSummary[]> {
    return this.http.get<SyncRunSummary[]>('/sync-runs');
  }

  loadExperimentDetail(experimentKey: string): Observable<ExperimentDetail | null> {
    return this.http.get<ExperimentDetail | null>(`/experiments/${encodeURIComponent(experimentKey)}`);
  }

  loadFeatureDistributions(): Observable<FeatureDistribution[]> {
    return this.http.get<FeatureDistribution[]>('/feature-distributions');
  }

  loadTrainingStatus(): Observable<TrainingStatusPayload> {
    return this.http.get<TrainingStatusPayload>('/training-status');
  }

  watchTrainingStatus(): Observable<TrainingStatusStreamState> {
    return new Observable((subscriber) => {
      let closedBySubscriber = false;
      let socket: WebSocket | null = null;
      let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
      let reconnectAttempt = 0;
      let latestPayload: TrainingStatusPayload | null = null;

      const connect = () => {
        subscriber.next({
          connection: reconnectAttempt === 0 ? 'connecting' : 'reconnecting',
          payload: latestPayload,
          message: reconnectAttempt === 0 ? '正在连接训练实时通道' : '实时通道已断开，正在重连',
        });
        socket = new WebSocket(this.trainingStatusSocketUrl());

        socket.onopen = () => {
          subscriber.next({ connection: 'connected', payload: latestPayload, message: null });
        };

        socket.onmessage = (event) => {
          try {
            const message = JSON.parse(String(event.data)) as TrainingStatusSocketMessage;
            if (message.type === 'training_status') {
              latestPayload = message.payload;
              subscriber.next({ connection: 'connected', payload: latestPayload, message: null });
            } else if (message.type === 'heartbeat') {
              subscriber.next({ connection: 'connected', payload: latestPayload, message: null });
            } else if (message.type === 'error') {
              subscriber.next({ connection: 'connected', payload: latestPayload, message: message.message });
            }
          } catch (error) {
            subscriber.next({
              connection: 'disconnected',
              payload: latestPayload,
              message: error instanceof Error ? error.message : '训练实时消息解析失败',
            });
          }
        };

        socket.onerror = () => {
          if (socket && socket.readyState !== WebSocket.CLOSED && socket.readyState !== WebSocket.CLOSING) {
            socket.close();
          }
        };

        socket.onclose = () => {
          if (closedBySubscriber) {
            subscriber.complete();
            return;
          }
          reconnectAttempt += 1;
          subscriber.next({ connection: 'reconnecting', payload: latestPayload, message: '实时通道已断开，正在重连' });
          reconnectTimer = setTimeout(connect, 2000);
        };
      };

      connect();

      return () => {
        closedBySubscriber = true;
        if (reconnectTimer) {
          clearTimeout(reconnectTimer);
        }
        if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
          socket.close();
        }
      };
    });
  }

  private trainingStatusSocketUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const port = window.location.port === '4200' ? '3000' : window.location.port;
    const host = port ? `${window.location.hostname}:${port}` : window.location.host;
    return `${protocol}//${host}/training-status/ws`;
  }
}
