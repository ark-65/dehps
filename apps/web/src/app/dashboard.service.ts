import { HttpClient } from '@angular/common/http';
import { Injectable, NgZone } from '@angular/core';
import { Observable } from 'rxjs';
import {
  DashboardPayload,
  ExperimentDetail,
  ExperimentSummary,
  FeatureDistribution,
  PipelineRunSummary,
  ServiceStatusPayload,
  SyncRunSummary,
  TrainingNextCandidatesPayload,
  TrainingRoundDetail,
  TrainingRoundListItem,
  TrainingStatusPayload,
  TrainingWeightSignalSeries,
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
  constructor(
    private readonly http: HttpClient,
    private readonly zone: NgZone,
  ) {}

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

  loadTrainingRounds(): Observable<TrainingRoundListItem[]> {
    return this.http.get<TrainingRoundListItem[]>('/training-rounds?limit=50');
  }

  loadTrainingRoundDetail(runId: string, roundIndex: number): Observable<TrainingRoundDetail | null> {
    return this.http.get<TrainingRoundDetail | null>(
      `/training-rounds/${encodeURIComponent(runId)}/${encodeURIComponent(String(roundIndex))}`,
    );
  }

  loadTrainingWeightSignals(): Observable<TrainingWeightSignalSeries[]> {
    return this.http.get<TrainingWeightSignalSeries[]>('/training-weight-signals?limit=1000');
  }

  loadTrainingNextCandidates(lineKey = 'static_100'): Observable<TrainingNextCandidatesPayload> {
    return this.http.get<TrainingNextCandidatesPayload>(
      `/training-next-candidates?limit=10000&lineKey=${encodeURIComponent(lineKey)}`,
    );
  }

  loadServiceStatus(): Observable<ServiceStatusPayload> {
    return this.http.get<ServiceStatusPayload>('/service-status');
  }

  watchTrainingStatus(): Observable<TrainingStatusStreamState> {
    return new Observable((subscriber) => {
      let closedBySubscriber = false;
      let socket: WebSocket | null = null;
      let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
      let connectTimer: ReturnType<typeof setTimeout> | null = null;
      let reconnectAttempt = 0;
      let latestPayload: TrainingStatusPayload | null = null;
      let activeUrlIndex = 0;
      let opened = false;
      let fallbackUrlIndex: number | null = null;
      const socketUrls = this.trainingStatusSocketUrls();

      const clearConnectTimer = () => {
        if (connectTimer) {
          clearTimeout(connectTimer);
          connectTimer = null;
        }
      };

      const emit = (state: TrainingStatusStreamState) => {
        this.zone.run(() => subscriber.next(state));
      };

      const connect = (urlIndex = activeUrlIndex) => {
        activeUrlIndex = urlIndex;
        opened = false;
        emit({
          connection: reconnectAttempt === 0 ? 'connecting' : 'reconnecting',
          payload: latestPayload,
          message: reconnectAttempt === 0 ? '正在连接训练实时通道' : '实时通道已断开，正在重连',
        });
        socket = new WebSocket(socketUrls[activeUrlIndex]);
        connectTimer = setTimeout(() => {
          if (socket?.readyState === WebSocket.CONNECTING) {
            fallbackUrlIndex = socketUrls[activeUrlIndex + 1] ? activeUrlIndex + 1 : null;
            socket.close();
          }
        }, 5000);

        socket.onopen = () => {
          opened = true;
          clearConnectTimer();
          reconnectAttempt = 0;
          emit({ connection: 'connected', payload: latestPayload, message: null });
        };

        socket.onmessage = (event) => {
          try {
            const message = JSON.parse(String(event.data)) as TrainingStatusSocketMessage;
            if (message.type === 'training_status') {
              latestPayload = message.payload;
              emit({ connection: 'connected', payload: latestPayload, message: null });
            } else if (message.type === 'heartbeat') {
              return;
            } else if (message.type === 'error') {
              emit({ connection: 'connected', payload: latestPayload, message: message.message });
            }
          } catch (error) {
            emit({
              connection: 'connected',
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
          clearConnectTimer();
          if (closedBySubscriber) {
            this.zone.run(() => subscriber.complete());
            return;
          }
          if (!opened && fallbackUrlIndex !== null) {
            const nextUrlIndex = fallbackUrlIndex;
            fallbackUrlIndex = null;
            connect(nextUrlIndex);
            return;
          }
          reconnectAttempt += 1;
          emit({ connection: 'reconnecting', payload: latestPayload, message: '实时通道已断开，正在重连' });
          reconnectTimer = setTimeout(() => connect(activeUrlIndex), 2000);
        };
      };

      connect();

      return () => {
        closedBySubscriber = true;
        if (reconnectTimer) {
          clearTimeout(reconnectTimer);
        }
        clearConnectTimer();
        if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
          socket.close();
        }
      };
    });
  }

  private trainingStatusSocketUrls(): string[] {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const sameOrigin = `${protocol}//${window.location.host}/training-status/ws`;
    if (window.location.port !== '4200') {
      return [sameOrigin];
    }
    const apiFallback = `${protocol}//${window.location.hostname}:3000/training-status/ws`;
    return sameOrigin === apiFallback ? [sameOrigin] : [sameOrigin, apiFallback];
  }
}
