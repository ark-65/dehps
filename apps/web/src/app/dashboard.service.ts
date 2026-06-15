import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { DashboardPayload } from './dashboard.model';

@Injectable({ providedIn: 'root' })
export class DashboardService {
  constructor(private readonly http: HttpClient) {}

  load(): Observable<DashboardPayload> {
    return this.http.get<DashboardPayload>('/dashboard');
  }
}
