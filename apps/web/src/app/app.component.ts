import { AsyncPipe, DatePipe, DecimalPipe, JsonPipe, NgClass } from '@angular/common';
import { Component } from '@angular/core';
import { BehaviorSubject, catchError, map, of, startWith, switchMap, tap } from 'rxjs';
import {
  DashboardPayload,
  ExperimentDetail,
  combinationDistribution,
  latestStatus,
  percent,
  reportStatus,
} from './dashboard.model';
import { DashboardService } from './dashboard.service';

type DashboardState =
  | { status: 'loading' }
  | { status: 'ready'; payload: DashboardPayload; latestStatus: string }
  | { status: 'error'; message: string };

type DetailState =
  | { status: 'idle' }
  | { status: 'loading'; experimentKey: string }
  | { status: 'ready'; detail: ExperimentDetail | null; reportStatus: string }
  | { status: 'error'; experimentKey: string; message: string };

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [AsyncPipe, DatePipe, DecimalPipe, JsonPipe, NgClass],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  private readonly refreshRequests = new BehaviorSubject<void>(undefined);
  private readonly detailRequests = new BehaviorSubject<string | null>(null);
  selectedExperimentKey: string | null = null;

  readonly combinationDistribution = combinationDistribution;
  readonly percent = percent;
  readonly state$ = this.refreshRequests.pipe(
    switchMap(() =>
      this.dashboardService.load().pipe(
        tap((payload) => this.ensureSelection(payload)),
        map((payload): DashboardState => ({ status: 'ready', payload, latestStatus: latestStatus(payload) })),
        catchError((error: unknown) =>
          of({
            status: 'error' as const,
            message: error instanceof Error ? error.message : 'Unable to load dashboard data',
          }),
        ),
        startWith({ status: 'loading' as const }),
      ),
    ),
  );
  readonly detailState$ = this.detailRequests.pipe(
    switchMap((experimentKey) => {
      if (!experimentKey) {
        return of({ status: 'idle' as const });
      }
      return this.dashboardService.loadExperimentDetail(experimentKey).pipe(
        map(
          (detail): DetailState => ({
            status: 'ready',
            detail,
            reportStatus: reportStatus(detail),
          }),
        ),
        catchError((error: unknown) =>
          of({
            status: 'error' as const,
            experimentKey,
            message: error instanceof Error ? error.message : 'Unable to load experiment detail',
          }),
        ),
        startWith({ status: 'loading' as const, experimentKey }),
      );
    }),
  );

  constructor(private readonly dashboardService: DashboardService) {}

  refresh(): void {
    this.refreshRequests.next();
    if (this.selectedExperimentKey) {
      this.detailRequests.next(this.selectedExperimentKey);
    }
  }

  selectExperiment(experimentKey: string): void {
    this.selectedExperimentKey = experimentKey;
    this.detailRequests.next(experimentKey);
  }

  private ensureSelection(payload: DashboardPayload): void {
    const selectedExists = payload.experiments.some(
      (experiment) => experiment.experimentKey === this.selectedExperimentKey,
    );
    const nextKey = selectedExists ? this.selectedExperimentKey : payload.experiments[0]?.experimentKey;
    if (nextKey && nextKey !== this.selectedExperimentKey) {
      this.selectExperiment(nextKey);
    }
  }
}
