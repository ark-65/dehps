import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { DashboardPayload, ExperimentDetail, FeatureDistribution } from './dashboard.model';

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
}
