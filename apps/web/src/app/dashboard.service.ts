import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { DashboardPayload, ExperimentDetail, FeatureDistribution, TrainingStatusPayload } from './dashboard.model';

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

  loadExperimentDetail(experimentKey: string): Observable<ExperimentDetail | null> {
    return this.http.get<ExperimentDetail | null>(`/experiments/${encodeURIComponent(experimentKey)}`);
  }

  loadFeatureDistributions(): Observable<FeatureDistribution[]> {
    return this.http.get<FeatureDistribution[]>('/feature-distributions');
  }

  loadTrainingStatus(): Observable<TrainingStatusPayload> {
    return this.http.get<TrainingStatusPayload>('/training-status');
  }

  watchTrainingStatus(): Observable<TrainingStatusPayload> {
    return new Observable((subscriber) => {
      let closedBySubscriber = false;
      const socket = new WebSocket(this.trainingStatusSocketUrl());

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(String(event.data)) as TrainingStatusSocketMessage;
          if (message.type === 'training_status') {
            subscriber.next(message.payload);
          } else if (message.type === 'error') {
            subscriber.error(new Error(message.message));
          }
        } catch (error) {
          subscriber.error(error instanceof Error ? error : new Error('训练实时消息解析失败'));
        }
      };

      socket.onerror = () => {
        subscriber.error(new Error('训练 WebSocket 连接失败'));
      };

      socket.onclose = () => {
        if (closedBySubscriber) {
          subscriber.complete();
        } else {
          subscriber.error(new Error('训练 WebSocket 已断开'));
        }
      };

      return () => {
        closedBySubscriber = true;
        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
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
