import { AsyncPipe, DatePipe, DecimalPipe, JsonPipe, NgClass } from '@angular/common';
import { Component } from '@angular/core';
import { BehaviorSubject, catchError, map, of, startWith, switchMap } from 'rxjs';
import { DashboardPayload, combinationDistribution, latestStatus, percent } from './dashboard.model';
import { DashboardService } from './dashboard.service';

type DashboardState =
  | { status: 'loading' }
  | { status: 'ready'; payload: DashboardPayload; latestStatus: string }
  | { status: 'error'; message: string };

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [AsyncPipe, DatePipe, DecimalPipe, JsonPipe, NgClass],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  private readonly refreshRequests = new BehaviorSubject<void>(undefined);

  readonly combinationDistribution = combinationDistribution;
  readonly percent = percent;
  readonly state$ = this.refreshRequests.pipe(
    switchMap(() =>
      this.dashboardService.load().pipe(
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

  constructor(private readonly dashboardService: DashboardService) {}

  refresh(): void {
    this.refreshRequests.next();
  }
}
