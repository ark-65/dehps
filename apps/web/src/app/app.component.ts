import { AsyncPipe, DatePipe, DecimalPipe, JsonPipe, NgClass } from '@angular/common';
import { Component } from '@angular/core';
import { BehaviorSubject, Subject, catchError, map, merge, of, startWith, switchMap, tap, timer } from 'rxjs';
import {
  DashboardPayload,
  ExperimentDetail,
  ExperimentSummary,
  TrainingResult,
  TrainingStatusPayload,
  compareExperiments,
  combinationDistribution,
  hitRate,
  latestStatus,
  phaseText,
  percent,
  progressRate,
  reportStatus,
  signedNumber,
  signedPercent,
  trainModeText,
  trainingStatusText,
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
  private readonly refreshRequests = new Subject<void>();
  private readonly detailRequests = new BehaviorSubject<string | null>(null);
  selectedExperimentKey: string | null = null;
  selectedComparisonKey: string | null = null;

  readonly compareExperiments = compareExperiments;
  readonly combinationDistribution = combinationDistribution;
  readonly hitRate = hitRate;
  readonly phaseText = phaseText;
  readonly percent = percent;
  readonly progressRate = progressRate;
  readonly signedNumber = signedNumber;
  readonly signedPercent = signedPercent;
  readonly trainModeText = trainModeText;
  readonly trainingStatusText = trainingStatusText;
  readonly state$ = merge(timer(0, 30000).pipe(map(() => undefined)), this.refreshRequests).pipe(
    switchMap(() =>
      this.dashboardService.load().pipe(
        tap((payload) => this.ensureSelection(payload)),
        map((payload): DashboardState => ({ status: 'ready', payload, latestStatus: latestStatus(payload) })),
        catchError((error: unknown) =>
          of({
            status: 'error' as const,
            message: error instanceof Error ? error.message : '仪表盘数据加载失败',
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
            message: error instanceof Error ? error.message : '实验详情加载失败',
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
    if (this.selectedComparisonKey === experimentKey) {
      this.selectedComparisonKey = null;
    }
    this.detailRequests.next(experimentKey);
    this.writeHash();
  }

  selectComparison(experimentKey: string): void {
    this.selectedComparisonKey = experimentKey || null;
    this.writeHash();
  }

  findExperiment(payload: DashboardPayload, experimentKey: string | null): ExperimentSummary | null {
    if (!experimentKey) {
      return null;
    }
    return payload.experiments.find((experiment) => experiment.experimentKey === experimentKey) ?? null;
  }

  runStatusText(status: string): string {
    const labels: Record<string, string> = {
      success: '成功',
      failed: '失败',
      running: '运行中',
      pending: '等待中',
      skipped: '已跳过',
    };
    return labels[status] ?? status;
  }

  processText(status: TrainingStatusPayload): string {
    if (status.processAlive === null) {
      return '未知';
    }
    return status.processAlive ? '进程存活' : '进程未存活';
  }

  progressText(status: TrainingStatusPayload): string {
    const progress = status.latestProgress;
    if (!progress) {
      return '暂无进行中的 target 进度';
    }
    return `第 ${progress.round} 轮：${progress.targetIndex}/${progress.targetTotal}，目标期 ${progress.issue}`;
  }

  configSummary(result: TrainingResult | null): string {
    if (!result || Object.keys(result.config).length === 0) {
      return '暂无配置';
    }
    return Object.entries(result.config)
      .map(([key, value]) => `${this.configLabel(key)} ${value.toFixed(3)}`)
      .join('，');
  }

  compactPath(filePath: string | null): string {
    if (!filePath) {
      return '无';
    }
    return filePath.replace('/home/ark/workspace/dehps/', '');
  }

  logText(status: TrainingStatusPayload): string {
    return status.logTail.length ? status.logTail.join('\n') : '暂无训练日志';
  }

  roundBestLabel(result: TrainingResult | null): string {
    if (!result) {
      return '暂无结果';
    }
    return `Top10000 ${result.top_10000_hits}/${result.evaluated_draws}，Top1000 ${result.top_1000_hits}/${result.evaluated_draws}，最佳排名 ${result.best_rank}`;
  }

  private configLabel(key: string): string {
    const labels: Record<string, string> = {
      structural_weight: '结构',
      frequency_weight: '频率',
      omission_weight: '遗漏',
      previous_consecutive_weight: '上期连号',
      previous_overlap_weight: '上期重叠',
      previous_parity_shape_weight: '奇偶形态',
      previous_zone_shape_weight: '分区形态',
    };
    return labels[key] ?? key;
  }

  private ensureSelection(payload: DashboardPayload): void {
    this.readHashOnce();
    const selectedExists = payload.experiments.some(
      (experiment) => experiment.experimentKey === this.selectedExperimentKey,
    );
    const comparisonExists = payload.experiments.some(
      (experiment) => experiment.experimentKey === this.selectedComparisonKey,
    );
    const nextKey = selectedExists ? this.selectedExperimentKey : payload.experiments[0]?.experimentKey;
    if (nextKey && nextKey !== this.selectedExperimentKey) {
      this.selectExperiment(nextKey);
    } else if (nextKey) {
      this.detailRequests.next(nextKey);
      this.writeHash();
    }
    if (!comparisonExists) {
      this.selectedComparisonKey =
        payload.experiments.find((experiment) => experiment.experimentKey !== this.selectedExperimentKey)
          ?.experimentKey ?? null;
      this.writeHash();
    }
  }

  private hashRead = false;

  private readHashOnce(): void {
    if (this.hashRead || typeof window === 'undefined') {
      return;
    }
    this.hashRead = true;
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    this.selectedExperimentKey = params.get('experiment');
    this.selectedComparisonKey = params.get('compare');
  }

  private writeHash(): void {
    if (typeof window === 'undefined') {
      return;
    }
    const params = new URLSearchParams();
    if (this.selectedExperimentKey) {
      params.set('experiment', this.selectedExperimentKey);
    }
    if (this.selectedComparisonKey) {
      params.set('compare', this.selectedComparisonKey);
    }
    const nextHash = params.toString();
    if (window.location.hash.replace(/^#/, '') !== nextHash) {
      window.history.replaceState(null, '', nextHash ? `#${nextHash}` : window.location.pathname);
    }
  }
}
