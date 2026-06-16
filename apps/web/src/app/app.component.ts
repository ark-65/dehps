import { AsyncPipe, DatePipe, DecimalPipe, JsonPipe, NgClass } from '@angular/common';
import { Component } from '@angular/core';
import {
  BehaviorSubject,
  Subject,
  catchError,
  map,
  merge,
  of,
  retry,
  shareReplay,
  startWith,
  switchMap,
  tap,
  timer,
} from 'rxjs';
import {
  DashboardPayload,
  ExperimentDetail,
  ExperimentSummary,
  TrainingResult,
  TrainingRoundSummary,
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
import { ChartOption, EchartComponent } from './echart.component';

type DashboardState =
  | { status: 'loading' }
  | { status: 'ready'; payload: DashboardPayload; latestStatus: string }
  | { status: 'error'; message: string };

type DetailState =
  | { status: 'idle' }
  | { status: 'loading'; experimentKey: string }
  | { status: 'ready'; detail: ExperimentDetail | null; reportStatus: string }
  | { status: 'error'; experimentKey: string; message: string };

type DashboardTab = 'training' | 'experiments';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [AsyncPipe, DatePipe, DecimalPipe, EchartComponent, JsonPipe, NgClass],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  private readonly refreshRequests = new Subject<void>();
  private readonly detailRequests = new BehaviorSubject<string | null>(null);
  selectedExperimentKey: string | null = null;
  selectedComparisonKey: string | null = null;
  activeTab: DashboardTab = 'training';

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
  readonly liveTrainingStatus$ = this.dashboardService.watchTrainingStatus().pipe(
    retry({ delay: () => timer(2000) }),
    startWith(null),
    catchError(() => of(null)),
    shareReplay({ bufferSize: 1, refCount: true }),
  );
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

  selectTab(tab: DashboardTab): void {
    this.activeTab = tab;
    if (tab === 'experiments' && this.selectedExperimentKey) {
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
    return `Top10000 ${result.top_10000_hits}/${result.evaluated_draws}，Top1000 ${result.top_1000_hits}/${result.evaluated_draws}，红5Top100 ${result.red5.top_100_hits}/${result.evaluated_draws}，最佳排名 ${result.best_rank}`;
  }

  redFivePairText(result: TrainingResult | null): string {
    const pairs = result?.red5.pairs ?? [];
    if (!pairs.length) {
      return '暂无红5差异样本';
    }
    return pairs
      .slice(0, 4)
      .map(
        (pair) =>
          `真实缺 ${this.ballText(pair.missing_number)} / 候选多 ${this.ballText(pair.extra_number)}：${pair.count} 次`,
      )
      .join('，');
  }

  hitTrendOption(status: TrainingStatusPayload): ChartOption {
    const rounds = this.chartRounds(status);
    const xAxis = rounds.map((round) => `R${round.round}`);
    return this.baseLineOption({
      title: '命中趋势',
      xAxis,
      yName: '命中期数',
      series: [
        this.lineSeries('Top10000', rounds.map((round) => round.best?.top_10000_hits ?? 0), '#327857'),
        this.lineSeries('Top1000', rounds.map((round) => round.best?.top_1000_hits ?? 0), '#4472a5'),
        this.lineSeries('Top100', rounds.map((round) => round.best?.top_100_hits ?? 0), '#a85c38'),
      ],
      markLineValue: 4,
      markLineName: '下一目标 4/100',
    });
  }

  rankTrendOption(status: TrainingStatusPayload): ChartOption {
    const rounds = this.chartRounds(status);
    const xAxis = rounds.map((round) => `R${round.round}`);
    return this.baseLineOption({
      title: '排名分布',
      xAxis,
      yName: '排名',
      inverse: true,
      series: [
        this.lineSeries('最佳排名', rounds.map((round) => round.best?.best_rank ?? null), '#327857'),
        this.lineSeries('中位排名', rounds.map((round) => round.best?.median_rank ?? null), '#4472a5'),
        this.lineSeries('最差排名', rounds.map((round) => round.best?.worst_rank ?? null), '#8c5a2b'),
      ],
    });
  }

  rewardTrendOption(status: TrainingStatusPayload): ChartOption {
    const rounds = this.chartRounds(status);
    const xAxis = rounds.map((round) => `R${round.round}`);
    return {
      title: { text: '奖惩机制', left: 12, top: 8, textStyle: { fontSize: 14, fontWeight: 700 } },
      color: ['#327857', '#987a24', '#b5413f', '#4472a5'],
      tooltip: { trigger: 'axis' },
      legend: { top: 8, right: 12 },
      grid: { left: 48, right: 24, top: 58, bottom: 42 },
      xAxis: { type: 'category', data: xAxis },
      yAxis: { type: 'value', name: '分数' },
      series: [
        {
          name: '命中奖励',
          type: 'bar',
          stack: 'reward',
          data: rounds.map((round) => round.best?.reward.hitReward ?? 0),
        },
        {
          name: '红5近似奖励',
          type: 'bar',
          stack: 'reward',
          data: rounds.map((round) => round.best?.reward.red5Reward ?? 0),
        },
        {
          name: '排名惩罚',
          type: 'bar',
          stack: 'reward',
          data: rounds.map((round) => -(round.best?.reward.rankPenalty ?? 0)),
        },
        {
          name: '综合分',
          type: 'line',
          smooth: true,
          symbolSize: 7,
          data: rounds.map((round) => round.best?.reward.objectiveScore ?? 0),
        },
      ],
    };
  }

  redFiveTrendOption(status: TrainingStatusPayload): ChartOption {
    const rounds = this.chartRounds(status);
    const xAxis = rounds.map((round) => `R${round.round}`);
    return this.baseLineOption({
      title: '红5近似命中',
      xAxis,
      yName: '命中期数',
      series: [
        this.lineSeries('红5 Top100', rounds.map((round) => round.best?.red5.top_100_hits ?? 0), '#987a24'),
        this.lineSeries('红5 Top1000', rounds.map((round) => round.best?.red5.top_1000_hits ?? 0), '#4472a5'),
        this.lineSeries('红5 Top10000', rounds.map((round) => round.best?.red5.top_10000_hits ?? 0), '#327857'),
      ],
    });
  }

  redFiveDifferenceOption(result: TrainingResult | null): ChartOption {
    const numbers = Array.from({ length: 33 }, (_, index) => this.ballText(index + 1));
    const missingCounts = result?.red5.missing_counts ?? {};
    const extraCounts = result?.red5.extra_counts ?? {};
    return {
      title: { text: '红5差异号分布', left: 12, top: 8, textStyle: { fontSize: 14, fontWeight: 700 } },
      color: ['#b5413f', '#4472a5'],
      tooltip: { trigger: 'axis' },
      legend: { top: 8, right: 12 },
      grid: { left: 48, right: 24, top: 58, bottom: 42 },
      xAxis: { type: 'category', data: numbers },
      yAxis: { type: 'value', name: '次数' },
      series: [
        {
          name: '真实缺失号',
          type: 'bar',
          data: numbers.map((number) => missingCounts[number] ?? 0),
        },
        {
          name: '候选多选号',
          type: 'bar',
          data: numbers.map((number) => extraCounts[number] ?? 0),
        },
      ],
    };
  }

  weightTrendOption(status: TrainingStatusPayload): ChartOption {
    const rounds = this.chartRounds(status);
    const xAxis = rounds.map((round) => `R${round.round}`);
    const fields = [
      ['structural_weight', '结构'],
      ['frequency_weight', '频率'],
      ['omission_weight', '遗漏'],
      ['previous_consecutive_weight', '上期连号'],
      ['previous_overlap_weight', '上期重叠'],
      ['previous_zone_shape_weight', '分区形态'],
    ] as const;
    return this.baseLineOption({
      title: '权重演化',
      xAxis,
      yName: '权重',
      series: fields.map(([field, label]) =>
        this.lineSeries(
          label,
          rounds.map((round) => round.best?.config[field] ?? null),
        ),
      ),
    });
  }

  candidateScatterOption(status: TrainingStatusPayload): ChartOption {
    const rounds = this.chartRounds(status);
    const points = rounds.flatMap((round) =>
      round.topResults.map((result, index) => [
        round.round,
        result.median_rank,
        result.top_10000_hits,
        result.top_1000_hits,
        result.red5.top_100_hits,
        index + 1,
        result.reward.objectiveScore,
      ]),
    );
    return {
      title: { text: '候选分布', left: 12, top: 8, textStyle: { fontSize: 14, fontWeight: 700 } },
      color: ['#4472a5'],
      tooltip: {
        trigger: 'item',
        formatter: (params: unknown) => {
          const value = (params as { value?: unknown[] }).value ?? [];
          return `轮次 R${value[0]}<br/>候选 #${value[5]}<br/>中位排名 ${value[1]}<br/>Top10000 ${value[2]} / Top1000 ${value[3]}<br/>红5Top100 ${value[4]}<br/>综合分 ${value[6]}`;
        },
      },
      grid: { left: 62, right: 24, top: 58, bottom: 42 },
      xAxis: { type: 'value', name: '轮次', minInterval: 1 },
      yAxis: { type: 'value', name: '中位排名', inverse: true },
      series: [
        {
          name: '候选',
          type: 'scatter',
          symbolSize: (value: unknown) => 8 + Number((value as unknown[])[2] ?? 0) * 4,
          data: points,
        },
      ],
    };
  }

  private ballText(number: number): string {
    return number.toString().padStart(2, '0');
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

  private chartRounds(status: TrainingStatusPayload): TrainingRoundSummary[] {
    return status.rounds.length ? status.rounds : [...status.recentRounds].reverse();
  }

  private baseLineOption({
    title,
    xAxis,
    yName,
    series,
    inverse = false,
    markLineValue,
    markLineName,
  }: {
    title: string;
    xAxis: string[];
    yName: string;
    series: Record<string, unknown>[];
    inverse?: boolean;
    markLineValue?: number;
    markLineName?: string;
  }): ChartOption {
    const nextSeries = markLineValue === undefined
      ? series
      : series.map((item, index) =>
          index === 0
            ? {
                ...item,
                markLine: {
                  silent: true,
                  symbol: 'none',
                  lineStyle: { color: '#a85c38', type: 'dashed' },
                  data: [{ yAxis: markLineValue, name: markLineName }],
                },
              }
            : item,
        );
    return {
      title: { text: title, left: 12, top: 8, textStyle: { fontSize: 14, fontWeight: 700 } },
      tooltip: { trigger: 'axis' },
      legend: { top: 8, right: 12 },
      grid: { left: 62, right: 24, top: 58, bottom: 42 },
      xAxis: { type: 'category', data: xAxis },
      yAxis: { type: 'value', name: yName, inverse },
      series: nextSeries,
    };
  }

  private lineSeries(name: string, data: Array<number | null>, color?: string): Record<string, unknown> {
    return {
      name,
      type: 'line',
      smooth: true,
      symbolSize: 7,
      connectNulls: true,
      color,
      data,
    };
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
