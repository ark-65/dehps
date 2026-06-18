import { AsyncPipe, DatePipe, DecimalPipe, JsonPipe, NgClass } from '@angular/common';
import { Component } from '@angular/core';
import {
  BehaviorSubject,
  Subject,
  catchError,
  filter,
  forkJoin,
  map,
  mergeWith,
  of,
  shareReplay,
  startWith,
  switchMap,
  tap,
} from 'rxjs';
import {
  DashboardPayload,
  ExperimentDetail,
  ExperimentSummary,
  ServiceStatusItem,
  ServiceStatusPayload,
  TrainingAdvisorAdviceRow,
  TrainingAdvisorSummary,
  TrainingResult,
  TrainingRoundDetail,
  TrainingRoundListItem,
  TrainingRoundSummary,
  TrainingStatusPayload,
  TrainingTargetResult,
  TrainingWeightSignalSeries,
  advisorSourceLabel,
  advisorVerdictText,
  compareExperiments,
  combinationDistribution,
  hitRate,
  latestStatus,
  phaseText,
  percent,
  progressRate,
  reportStatus,
  serviceStatusLabel,
  signedNumber,
  signedPercent,
  sortedServiceStatuses,
  trainModeText,
  trainingStatusText,
} from './dashboard.model';
import { DashboardService } from './dashboard.service';
import { TrainingStatusStreamState } from './dashboard.service';
import { ChartOption, EchartComponent } from './echart.component';

type ExperimentsPayload = Pick<DashboardPayload, 'experiments' | 'pipelineRuns' | 'syncRuns' | 'featureDistributions'>;

type ExperimentsState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; payload: ExperimentsPayload; latestStatus: string }
  | { status: 'error'; message: string };

type DetailState =
  | { status: 'idle' }
  | { status: 'loading'; experimentKey: string }
  | { status: 'ready'; detail: ExperimentDetail | null; reportStatus: string }
  | { status: 'error'; experimentKey: string; message: string };

type TrainingRoundsState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; rounds: TrainingRoundListItem[] }
  | { status: 'error'; message: string };

type TrainingRoundDetailState =
  | { status: 'idle' }
  | { status: 'loading'; key: string }
  | { status: 'ready'; detail: TrainingRoundDetail | null }
  | { status: 'error'; key: string; message: string };

type TrainingWeightSignalsState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; series: TrainingWeightSignalSeries[] }
  | { status: 'error'; message: string };

type ServiceStatusState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; payload: ServiceStatusPayload; services: ServiceStatusItem[] }
  | { status: 'error'; message: string };

type DashboardTab = 'training' | 'training-rounds' | 'experiments' | 'service-status';
type WeightTrendGroup = {
  key: string;
  title: string;
  kind: 'weights' | 'reward';
  fields?: readonly (readonly [string, string])[];
};

type ChartTooltipParam = {
  data?: unknown;
  dataIndex?: number;
  marker?: string;
  seriesName?: string;
  value?: unknown;
  axisValue?: unknown;
  axisValueLabel?: string;
};

const ROUND_ZOOM_DEFAULT_WINDOW = 120;
const ROUND_ZOOM_THRESHOLD = ROUND_ZOOM_DEFAULT_WINDOW;
const ROUND_ZOOM_GRID_BOTTOM = 82;
const ROUND_ZOOM_SLIDER_BOTTOM = 14;
const ROUND_ZOOM_SLIDER_HEIGHT = 20;
const SIGNAL_ZOOM_DEFAULT_WINDOW = 160;
const SIGNAL_ZOOM_THRESHOLD = 120;

const WEIGHT_TREND_GROUPS: readonly WeightTrendGroup[] = [
  {
    key: 'base',
    title: '权重演化 - 基础',
    kind: 'weights',
    fields: [
      ['structural_weight', '结构'],
      ['frequency_weight', '频率'],
      ['omission_weight', '遗漏'],
    ],
  },
  {
    key: 'shape',
    title: '权重演化 - 形态',
    kind: 'weights',
    fields: [
      ['previous_consecutive_weight', '上期连号'],
      ['previous_overlap_weight', '上期重叠'],
      ['previous_parity_shape_weight', '奇偶形态'],
      ['dynamic_parity_transition_weight', '动态奇偶转移'],
      ['previous_zone_shape_weight', '分区形态'],
      ['qian_kun_pattern_weight', '乾坤卦象'],
      ['zone_ratio_weight', '区间比'],
      ['big_small_ratio_weight', '大小比'],
      ['parity_ratio_weight', '奇偶比'],
      ['prime_composite_weight', '质合比'],
      ['mod012_weight', '012路'],
      ['tail_distribution_weight', '尾数分布'],
    ],
  },
  {
    key: 'trend',
    title: '权重演化 - 走势',
    kind: 'weights',
    fields: [
      ['recent_neighbor_weight', '近期开奖邻号'],
      ['lagged_consecutive_weight', '隔期连号链'],
      ['recent_gap_shape_weight', '跳号间距'],
      ['recent_sum_span_weight', '和值跨度'],
      ['first_last_sum_weight', '首尾合'],
      ['span_trend_weight', '首尾差/跨度'],
      ['sum_trend_weight', '和值走势'],
      ['ac_trend_weight', 'AC值走势'],
      ['sum_tail_weight', '和尾走势'],
      ['consecutive_trend_weight', '连号走势'],
      ['repeat_trend_weight', '重号走势'],
      ['weekday_trend_weight', '开奖日走势'],
    ],
  },
  {
    key: 'omission',
    title: '权重演化 - 遗漏',
    kind: 'weights',
    fields: [
      ['red_omission_shape_weight', '红球遗漏形态'],
      ['sum_span_omission_weight', '和值跨度遗漏'],
      ['stable_range_weight', '稳定区间'],
    ],
  },
  {
    key: 'reward',
    title: '权重演化 - 奖惩',
    kind: 'reward',
  },
];

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [AsyncPipe, DatePipe, DecimalPipe, EchartComponent, JsonPipe, NgClass],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  private readonly trainingRefreshRequests = new Subject<void>();
  private readonly trainingWeightSignalsRefreshRequests = new Subject<void>();
  private readonly experimentsRefreshRequests = new Subject<void>();
  private readonly trainingRoundsRefreshRequests = new Subject<void>();
  private readonly serviceStatusRefreshRequests = new Subject<void>();
  private readonly activeTabRequests = new BehaviorSubject<DashboardTab>('training');
  private readonly detailRequests = new BehaviorSubject<string | null>(null);
  private readonly trainingRoundDetailRequests = new BehaviorSubject<TrainingRoundListItem | null>(null);
  selectedExperimentKey: string | null = null;
  selectedComparisonKey: string | null = null;
  selectedTrainingRoundKey: string | null = null;
  activeTab: DashboardTab = 'training';

  readonly compareExperiments = compareExperiments;
  readonly advisorSourceLabel = advisorSourceLabel;
  readonly advisorVerdictText = advisorVerdictText;
  readonly combinationDistribution = combinationDistribution;
  readonly hitRate = hitRate;
  readonly phaseText = phaseText;
  readonly percent = percent;
  readonly progressRate = progressRate;
  readonly signedNumber = signedNumber;
  readonly signedPercent = signedPercent;
  readonly serviceStatusLabel = serviceStatusLabel;
  readonly trainModeText = trainModeText;
  readonly trainingStatusText = trainingStatusText;
  readonly trainingStream$ = this.dashboardService.watchTrainingStatus().pipe(
    mergeWith(
      this.trainingRefreshRequests.pipe(
        switchMap(() =>
          this.dashboardService.loadTrainingStatus().pipe(
            map(
              (payload): TrainingStatusStreamState => ({
                connection: 'connected',
                payload,
                message: '已手动刷新训练快照',
              }),
            ),
            catchError((error: unknown) =>
              of({
                connection: 'disconnected' as const,
                payload: null,
                message: error instanceof Error ? error.message : '训练状态手动刷新失败',
              }),
            ),
          ),
        ),
      ),
    ),
    shareReplay({ bufferSize: 1, refCount: true }),
  );
  readonly experimentsState$ = this.activeTabRequests.pipe(
    filter((tab) => tab === 'experiments'),
    map(() => undefined),
  ).pipe(
    mergeWith(this.experimentsRefreshRequests),
    switchMap(() =>
      forkJoin({
        experiments: this.dashboardService.loadExperiments(),
        pipelineRuns: this.dashboardService.loadPipelineRuns(),
        syncRuns: this.dashboardService.loadSyncRuns(),
        featureDistributions: this.dashboardService.loadFeatureDistributions(),
      }).pipe(
        tap((payload) => this.ensureSelection(payload)),
        map((payload): ExperimentsState => ({ status: 'ready', payload, latestStatus: latestStatus(payload) })),
        catchError((error: unknown) =>
          of({
            status: 'error' as const,
            message: error instanceof Error ? error.message : '实验数据加载失败',
          }),
        ),
        startWith({ status: 'loading' as const }),
      ),
    ),
    startWith({ status: 'idle' as const }),
    shareReplay({ bufferSize: 1, refCount: true }),
  );
  readonly trainingRoundsState$ = this.activeTabRequests.pipe(
    filter((tab) => tab === 'training-rounds'),
    map(() => undefined),
  ).pipe(
    mergeWith(this.trainingRoundsRefreshRequests),
    switchMap(() =>
      this.dashboardService.loadTrainingRounds().pipe(
        tap((rounds) => this.ensureTrainingRoundSelection(rounds)),
        map((rounds): TrainingRoundsState => ({ status: 'ready', rounds })),
        catchError((error: unknown) =>
          of({
            status: 'error' as const,
            message: error instanceof Error ? error.message : '训练轮次加载失败',
          }),
        ),
        startWith({ status: 'loading' as const }),
      ),
    ),
    startWith({ status: 'idle' as const }),
    shareReplay({ bufferSize: 1, refCount: true }),
  );
  readonly trainingWeightSignalsState$ = this.activeTabRequests.pipe(
    filter((tab) => tab === 'training'),
    map(() => undefined),
  ).pipe(
    mergeWith(this.trainingWeightSignalsRefreshRequests),
    switchMap(() =>
      this.dashboardService.loadTrainingWeightSignals().pipe(
        map((series): TrainingWeightSignalsState => ({ status: 'ready', series })),
        catchError((error: unknown) =>
          of({
            status: 'error' as const,
            message: error instanceof Error ? error.message : '权重KDJ加载失败',
          }),
        ),
        startWith({ status: 'loading' as const }),
      ),
    ),
    startWith({ status: 'idle' as const }),
    shareReplay({ bufferSize: 1, refCount: true }),
  );
  readonly serviceStatusState$ = this.activeTabRequests.pipe(
    filter((tab) => tab === 'service-status'),
    map(() => undefined),
  ).pipe(
    mergeWith(this.serviceStatusRefreshRequests),
    switchMap(() =>
      this.dashboardService.loadServiceStatus().pipe(
        map((payload): ServiceStatusState => ({ status: 'ready', payload, services: sortedServiceStatuses(payload) })),
        catchError((error: unknown) =>
          of({
            status: 'error' as const,
            message: error instanceof Error ? error.message : '服务状态加载失败',
          }),
        ),
        startWith({ status: 'loading' as const }),
      ),
    ),
    startWith({ status: 'idle' as const }),
    shareReplay({ bufferSize: 1, refCount: true }),
  );
  readonly trainingRoundDetailState$ = this.trainingRoundDetailRequests.pipe(
    switchMap((round) => {
      if (!round) {
        return of({ status: 'idle' as const });
      }
      const key = this.trainingRoundKey(round);
      return this.dashboardService.loadTrainingRoundDetail(round.runId, round.roundIndex).pipe(
        map((detail): TrainingRoundDetailState => ({ status: 'ready', detail })),
        catchError((error: unknown) =>
          of({
            status: 'error' as const,
            key,
            message: error instanceof Error ? error.message : '训练轮次详情加载失败',
          }),
        ),
        startWith({ status: 'loading' as const, key }),
      );
    }),
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
    if (this.activeTab === 'training') {
      this.trainingRefreshRequests.next();
      this.trainingWeightSignalsRefreshRequests.next();
      return;
    }
    if (this.activeTab === 'training-rounds') {
      this.trainingRoundsRefreshRequests.next();
      return;
    }
    if (this.activeTab === 'service-status') {
      this.serviceStatusRefreshRequests.next();
      return;
    }
    this.experimentsRefreshRequests.next();
    if (this.selectedExperimentKey) {
      this.detailRequests.next(this.selectedExperimentKey);
    }
  }

  selectTab(tab: DashboardTab): void {
    this.activeTab = tab;
    this.activeTabRequests.next(tab);
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

  selectTrainingRound(round: TrainingRoundListItem): void {
    this.selectedTrainingRoundKey = this.trainingRoundKey(round);
    this.trainingRoundDetailRequests.next(round);
  }

  trainingRoundKey(round: TrainingRoundListItem): string {
    return `${round.runId}:${round.roundIndex}`;
  }

  trainingRoundSummary(round: TrainingRoundListItem): string {
    return `${trainModeText(round.trainMode)} / 窗口 ${round.trainWindow} / 回归 ${round.evalWindow} / TopN ${round.topN}`;
  }

  trainingRoundHitSummary(round: TrainingRoundListItem): string {
    return `Top10000 ${round.top10000Hits}/${round.evalWindow}，Top1000 ${round.top1000Hits}/${round.evalWindow}，Top100 ${round.top100Hits}/${round.evalWindow}`;
  }

  trainingRoundRed5Summary(round: TrainingRoundListItem): string {
    return `红5Top10000 ${round.red5Top10000Hits}/${round.evalWindow}，红5Top100 ${round.red5Top100Hits}/${round.evalWindow}`;
  }

  targetHitRows(detail: TrainingRoundDetail): TrainingTargetResult[] {
    const hits = detail.targetResults.filter((target) => target.hitTop10000 || target.hitRed5Top10000);
    return hits.length ? hits : detail.targetResults.slice(0, 20);
  }

  numbersText(numbers: number[]): string {
    return numbers.length ? numbers.map((number) => this.ballText(number)).join(' ') : '无';
  }

  findExperiment(payload: ExperimentsPayload, experimentKey: string | null): ExperimentSummary | null {
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

  streamStatusText(stream: TrainingStatusStreamState | null): string {
    const connection = stream?.connection ?? 'connecting';
    const labels: Record<TrainingStatusStreamState['connection'], string> = {
      connecting: '连接中',
      connected: 'WebSocket 已连接',
      reconnecting: '重连中',
      disconnected: '已断开',
    };
    return labels[connection];
  }

  streamDetailText(stream: TrainingStatusStreamState | null): string {
    if (stream?.message) {
      return stream.message;
    }
    if (stream?.payload) {
      const updatedAt = stream.payload.latestProgress?.loggedAt ?? stream.payload.updatedAt;
      return updatedAt ? `最后推送 ${updatedAt}` : '训练变化会实时推送';
    }
    return '正在等待训练实时快照';
  }

  processText(status: TrainingStatusPayload): string {
    if (status.processAlive === null) {
      return '未知';
    }
    return status.processAlive ? '进程存活' : '进程未存活';
  }

  serviceStatusClass(service: ServiceStatusItem): string {
    return `service-${service.status}`;
  }

  serviceLevelClass(status: ServiceStatusPayload['overall']): string {
    return `service-${status}`;
  }

  serviceProcessText(service: ServiceStatusItem): string {
    if (service.processAlive === null) {
      return service.pid ? `PID ${service.pid} / 未知` : '无 PID';
    }
    return service.processAlive ? `PID ${service.pid} / 存活` : `PID ${service.pid} / 未存活`;
  }

  serviceHeartbeatText(service: ServiceStatusItem): string {
    if (service.heartbeatAgeSeconds === null) {
      return service.heartbeatAt || '无心跳';
    }
    if (service.heartbeatAgeSeconds < 90) {
      return `${service.heartbeatAgeSeconds} 秒前`;
    }
    const minutes = Math.floor(service.heartbeatAgeSeconds / 60);
    if (minutes < 90) {
      return `${minutes} 分钟前`;
    }
    const hours = Math.floor(minutes / 60);
    if (hours < 48) {
      return `${hours} 小时前`;
    }
    return `${Math.floor(hours / 24)} 天前`;
  }

  serviceMetricRows(service: ServiceStatusItem): { key: string; value: string }[] {
    return Object.entries(service.metrics)
      .filter((entry) => entry[1] !== null && entry[1] !== undefined)
      .slice(0, 6)
      .map(([key, value]) => ({
        key,
        value: this.serviceMetricValue(value),
      }));
  }

  private serviceMetricValue(value: unknown): string {
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return String(value);
    }
    if (Array.isArray(value)) {
      return value.length ? value.join(', ') : '空';
    }
    if (value && typeof value === 'object') {
      return JSON.stringify(value);
    }
    return '无';
  }

  progressText(status: TrainingStatusPayload): string {
    const progress = status.latestProgress;
    if (!progress) {
      return '暂无进行中的 target 进度';
    }
    return `第 ${progress.round} 轮：${progress.targetIndex}/${progress.targetTotal}，目标期 ${progress.issue}`;
  }

  progressDetailText(status: TrainingStatusPayload): string {
    const progress = status.latestProgress;
    const pushedAt = progress?.loggedAt ?? status.updatedAt;
    const pushedText = pushedAt ? `最后推送 ${pushedAt}` : '等待首个进度事件';
    return `${pushedText} / 当前设置每 10 个目标期推送一帧`;
  }

  matrixCacheText(status: TrainingStatusPayload): string {
    const cache = status.featureMatrixCache;
    if (!cache) {
      return '未启用';
    }
    const hitText = cache.cacheHit === true ? '缓存命中' : cache.cacheHit === false ? '缓存重建' : '缓存未知';
    return `${status.matrixBackend || cache.backend || '矩阵'} / ${hitText}`;
  }

  matrixCacheDetailText(status: TrainingStatusPayload): string {
    const cache = status.featureMatrixCache;
    if (!cache) {
      return '等待训练状态';
    }
    const rows = cache.filteredCount ?? status.universeSize ?? 0;
    const excluded = cache.excludedCount ?? 0;
    const seconds = cache.buildSeconds ?? 0;
    return `矩阵 ${rows.toLocaleString('zh-CN')} 行 / 排除 ${excluded.toLocaleString('zh-CN')} 组 / ${seconds.toFixed(2)} 秒`;
  }

  prefilterText(status: TrainingStatusPayload): string {
    const latest = status.prefilter?.latest;
    if (!latest) {
      return '等待预筛';
    }
    const generated = latest.generatedConfigCount ?? 0;
    const refined = latest.refinedConfigCount ?? 0;
    return `${generated} -> ${refined}`;
  }

  prefilterDetailText(status: TrainingStatusPayload): string {
    const latest = status.prefilter?.latest;
    if (!latest) {
      return status.prefilter?.description || '每轮先轻量预筛，再完整精排';
    }
    const targets = latest.targetCount ?? 0;
    const workers = latest.targetWorkerCount ?? status.workers ?? 0;
    const seconds = latest.elapsedSeconds ?? 0;
    const stagnation = latest.stagnationRounds ?? 0;
    const diversity = latest.diversityAddedCount ?? 0;
    const validation = latest.frozenValidationWindow ?? 0;
    return `预筛 ${targets} 期 / ${workers} 核 / ${seconds.toFixed(1)} 秒 / 停滞 ${stagnation} 轮 / 多样性 ${diversity} / 验证 ${validation}`;
  }

  advisorStatusText(summary: TrainingAdvisorSummary): string {
    if (!summary.enabled) {
      return '未启用';
    }
    return summary.status || summary.mode || 'ready';
  }

  advisorSummaries(status: TrainingStatusPayload): TrainingAdvisorSummary[] {
    return status.advisorSummaries ?? [];
  }

  advisorCountsText(summary: TrainingAdvisorSummary): string {
    const selected = summary.selectedCount ?? 0;
    const rejected = summary.rejectedCount ?? 0;
    const downweighted = summary.downweightedCount ?? 0;
    return `selected ${selected} / rejected ${rejected} / downweighted ${downweighted}`;
  }

  advisorFieldsText(summary: TrainingAdvisorSummary): string {
    if (!summary.fields.length) {
      return '无字段';
    }
    const visible = summary.fields.slice(0, 8);
    const suffix = summary.fields.length > visible.length ? ` +${summary.fields.length - visible.length}` : '';
    return `${visible.join(', ')}${suffix}`;
  }

  advisorNumberText(value: number | null): string {
    return value === null ? '无' : value.toFixed(6);
  }

  advisorTopAdviceRows(summary: TrainingAdvisorSummary): TrainingAdvisorAdviceRow[] {
    return summary.advice.slice(0, 6);
  }

  hasRoundCharts(status: TrainingStatusPayload): boolean {
    if (status.rounds.length || status.recentRounds.length) {
      return true;
    }
    return false;
  }

  firstRoundEmptyText(status: TrainingStatusPayload): string {
    const progress = status.latestProgress;
    if (!progress) {
      return '当前 run 已启动，正在等待第一条 WebSocket 进度事件。';
    }
    return `当前第 ${progress.round} 轮已评估 ${progress.targetIndex}/${progress.targetTotal} 个目标期，最新目标期 ${progress.issue}。`;
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
    return `Top10000 ${result.top_10000_hits}/${result.evaluated_draws}，Top1000 ${result.top_1000_hits}/${result.evaluated_draws}，红5Top100 ${result.red5.top_100_hits}/${result.evaluated_draws}，Top5万 ${result.rank_quality.top_50000_hits}/${result.evaluated_draws}，最差排名 ${result.worst_rank}`;
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

  qianKunLinesText(status: TrainingStatusPayload): string {
    if (!status.qianKun.latest_pattern) {
      return '无';
    }
    const lines = status.qianKun.latest_lines.length ? status.qianKun.latest_lines.join(' ') : '无爻象';
    return `${status.qianKun.latest_pattern} / ${lines}`;
  }

  liveProgressOption(status: TrainingStatusPayload): ChartOption {
    const progress = status.latestProgress;
    const completed = progress?.targetIndex ?? 0;
    const total = progress?.targetTotal ?? status.evalWindow ?? 0;
    const remaining = Math.max(0, total - completed);
    const rate = total ? completed / total : 0;
    const elapsed = progress?.elapsedSeconds ?? 0;
    return {
      title: {
        text: '实时回归进度',
        left: 12,
        top: 8,
        textStyle: { fontSize: 14, fontWeight: 700 },
        subtext: progress
          ? `第 ${progress.round} 轮 / 目标期 ${progress.issue} / 训练样本 ${progress.trainDraws} 期 / 已耗时 ${elapsed.toFixed(1)} 秒`
          : '等待训练进度事件',
        subtextStyle: { color: '#64717d', fontSize: 12 },
      },
      color: ['#327857', '#d9dee3'],
      tooltip: {
        trigger: 'axis',
        formatter: () =>
          progress
            ? `当前轮 ${completed}/${total}<br/>完成率 ${(rate * 100).toFixed(2)}%<br/>目标期 ${progress.issue}<br/>训练样本 ${progress.trainDraws} 期`
            : '暂无进度',
      },
      legend: { top: 8, right: 12 },
      grid: { left: 62, right: 24, top: 78, bottom: 42 },
      xAxis: { type: 'value', max: Math.max(total, 1), name: '目标期数' },
      yAxis: { type: 'category', data: ['当前轮'] },
      series: [
        {
          name: '已评估',
          type: 'bar',
          stack: 'progress',
          data: [completed],
          label: {
            show: true,
            position: 'insideRight',
            formatter: `${completed}/${total}`,
          },
        },
        {
          name: '未评估',
          type: 'bar',
          stack: 'progress',
          data: [remaining],
          label: {
            show: remaining > 0,
            position: 'insideRight',
            formatter: `剩余 ${remaining}`,
          },
        },
      ],
    };
  }

  hitTrendOption(status: TrainingStatusPayload): ChartOption {
    const rounds = this.chartRounds(status);
    const xAxis = rounds.map((round) => `R${round.round}`);
    return this.baseLineOption({
      title: '命中趋势',
      rounds,
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
      rounds,
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

  rewardTrendOption(status: TrainingStatusPayload, title = '奖惩机制'): ChartOption {
    const rounds = this.chartRounds(status);
    const xAxis = rounds.map((round) => `R${round.round}`);
    const dataZoom = this.roundRangeDataZoom(rounds);
    return {
      title: { text: title, left: 12, top: 8, textStyle: { fontSize: 14, fontWeight: 700 } },
      color: ['#327857', '#987a24', '#4d7c9f', '#b5413f', '#8c5a2b', '#4472a5'],
      tooltip: this.roundAxisTooltip(rounds),
      legend: { type: 'scroll', top: 38, left: 12, right: 12 },
      grid: this.roundRangeGrid({ left: 48, right: 24, top: 92, bottom: 42 }, rounds),
      xAxis: this.roundCategoryXAxis(xAxis, rounds),
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
          name: '排名质量奖励',
          type: 'bar',
          stack: 'reward',
          data: rounds.map((round) => round.best?.reward.rankQualityReward ?? 0),
        },
        {
          name: '排名惩罚',
          type: 'bar',
          stack: 'reward',
          data: rounds.map((round) => -(round.best?.reward.rankPenalty ?? 0)),
        },
        {
          name: '尾部惩罚',
          type: 'bar',
          stack: 'reward',
          data: rounds.map((round) => -(round.best?.reward.tailRiskPenalty ?? 0)),
        },
        {
          name: '综合分',
          type: 'line',
          smooth: true,
          symbolSize: 7,
          data: rounds.map((round) => round.best?.reward.objectiveScore ?? 0),
        },
      ],
      ...(dataZoom.length ? { dataZoom } : {}),
    };
  }

  rankBandOption(status: TrainingStatusPayload): ChartOption {
    const rounds = this.chartRounds(status);
    const xAxis = rounds.map((round) => `R${round.round}`);
    return this.baseLineOption({
      title: '整体排名前移',
      rounds,
      xAxis,
      yName: '覆盖期数',
      series: [
        this.lineSeries('Top5万', rounds.map((round) => round.best?.rank_quality.top_50000_hits ?? 0), '#327857'),
        this.lineSeries('Top10万', rounds.map((round) => round.best?.rank_quality.top_100000_hits ?? 0), '#4472a5'),
        this.lineSeries('Top25万', rounds.map((round) => round.best?.rank_quality.top_250000_hits ?? 0), '#987a24'),
        this.lineSeries('Top50万', rounds.map((round) => round.best?.rank_quality.top_500000_hits ?? 0), '#8c5a2b'),
      ],
    });
  }

  tailRiskOption(status: TrainingStatusPayload): ChartOption {
    const rounds = this.chartRounds(status);
    const xAxis = rounds.map((round) => `R${round.round}`);
    return this.baseLineOption({
      title: '尾部风险',
      rounds,
      xAxis,
      yName: '期数',
      series: [
        this.lineSeries('超过75万', rounds.map((round) => round.best?.rank_quality.tail_over_750000_count ?? 0), '#987a24'),
        this.lineSeries('超过90万', rounds.map((round) => round.best?.rank_quality.tail_over_900000_count ?? 0), '#a85c38'),
        this.lineSeries('超过100万', rounds.map((round) => round.best?.rank_quality.tail_over_1000000_count ?? 0), '#b5413f'),
      ],
      markLineValue: 0,
      markLineName: '目标 0',
    });
  }

  redFiveTrendOption(status: TrainingStatusPayload): ChartOption {
    const rounds = this.chartRounds(status);
    const xAxis = rounds.map((round) => `R${round.round}`);
    return this.baseLineOption({
      title: '红5近似命中',
      rounds,
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

  qianKunDistributionOption(status: TrainingStatusPayload): ChartOption {
    const patterns = status.qianKun.patterns.slice(0, 16);
    return {
      title: { text: '乾坤卦象分布', left: 12, top: 8, textStyle: { fontSize: 14, fontWeight: 700 } },
      color: ['#327857', '#987a24'],
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const values = Array.isArray(params) ? params : [];
          const first = values[0] as { dataIndex?: number } | undefined;
          const pattern = patterns[first?.dataIndex ?? 0];
          if (!pattern) {
            return '暂无卦象分布';
          }
          const title = pattern.icon ? `${pattern.icon} ${pattern.label}` : pattern.label;
          return `${title}<br/>pattern ${pattern.pattern}<br/>爻象 ${pattern.lines.join(' ')}<br/>全窗口 ${pattern.count}<br/>近${status.qianKun.recent_window}期 ${pattern.recent_count}`;
        },
      },
      legend: { top: 8, right: 12 },
      grid: { left: 48, right: 24, top: 58, bottom: 64 },
      xAxis: {
        type: 'category',
        data: patterns.map((pattern) => (pattern.icon ? `${pattern.icon} ${pattern.label}` : pattern.label)),
        axisLabel: { rotate: 30 },
      },
      yAxis: { type: 'value', name: '次数' },
      series: [
        {
          name: '全窗口',
          type: 'bar',
          data: patterns.map((pattern) => pattern.count),
        },
        {
          name: `近${status.qianKun.recent_window}期`,
          type: 'bar',
          data: patterns.map((pattern) => pattern.recent_count),
        },
      ],
    };
  }

  weightTrendGroups(status: TrainingStatusPayload): Array<{ key: string; option: ChartOption }> {
    return WEIGHT_TREND_GROUPS.map((group) => ({
      key: group.key,
      option:
        group.kind === 'reward'
          ? this.rewardTrendOption(status, group.title)
          : this.weightTrendOption(status, group),
    }));
  }

  weightKdjGroups(series: TrainingWeightSignalSeries[]): Array<{ key: string; option: ChartOption }> {
    const byWeight = new Map(series.map((item) => [item.weightName, item]));
    return WEIGHT_TREND_GROUPS.filter((group) => group.kind === 'weights').map((group) => ({
      key: group.key,
      option: this.weightKdjOption(byWeight, group),
    }));
  }

  private weightKdjOption(seriesByWeight: Map<string, TrainingWeightSignalSeries>, group: WeightTrendGroup): ChartOption {
    const fields = group.fields ?? [];
    const selected = fields
      .map(([field, label]) => ({ field, label, series: seriesByWeight.get(field) ?? null }))
      .filter((item): item is { field: string; label: string; series: TrainingWeightSignalSeries } => Boolean(item.series));
    const pointCount = Math.max(0, ...selected.map((item) => item.series.points.length));
    const xAxis = selected[0]?.series.points.map((point) => point.issue) ?? [];
    const chartSeries = selected.flatMap((item) => [
      this.lineSeries(
        `${item.label} K`,
        item.series.points.map((point) => point.kValue),
        '#4472a5',
      ),
      this.lineSeries(
        `${item.label} D`,
        item.series.points.map((point) => point.dValue),
        '#327857',
      ),
      this.lineSeries(
        `${item.label} J`,
        item.series.points.map((point) => point.jValue),
        '#a85c38',
      ),
    ]);
    const dataZoom = this.signalRangeDataZoom(pointCount);
    return {
      title: { text: group.title.replace('权重演化', '权重KDJ'), left: 12, top: 8, textStyle: { fontSize: 14, fontWeight: 700 } },
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => this.signalTooltipText(selected[0]?.series ?? null, params),
      },
      legend: { type: 'scroll', top: 38, left: 12, right: 12 },
      grid: { left: 58, right: 24, top: 92, bottom: dataZoom.length ? 82 : 42 },
      xAxis: {
        type: 'category',
        data: xAxis,
        axisLabel: { hideOverlap: true },
        axisTick: { alignWithLabel: true },
      },
      yAxis: { type: 'value', name: 'KDJ' },
      series: chartSeries,
      ...(dataZoom.length ? { dataZoom } : {}),
    };
  }

  private weightTrendOption(status: TrainingStatusPayload, group: WeightTrendGroup): ChartOption {
    const rounds = this.chartRounds(status);
    const xAxis = rounds.map((round) => `R${round.round}`);
    const fields = group.fields ?? [];
    return this.groupedLineOption({
      title: group.title,
      rounds,
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
        round.best?.as_of_issue || result.as_of_issue,
      ]),
    );
    const dataZoom = this.roundRangeDataZoom(rounds);
    return {
      title: { text: '候选分布', left: 12, top: 8, textStyle: { fontSize: 14, fontWeight: 700 } },
      color: ['#4472a5'],
      tooltip: {
        trigger: 'item',
        formatter: (params: unknown) => {
          const value = (params as { value?: unknown[] }).value ?? [];
          const issue = value[7] ? `<br/>期号 ${value[7]}` : '';
          return `轮次 R${value[0]}${issue}<br/>候选 #${value[5]}<br/>中位排名 ${value[1]}<br/>Top10000 ${value[2]} / Top1000 ${value[3]}<br/>红5Top100 ${value[4]}<br/>综合分 ${value[6]}`;
        },
      },
      grid: this.roundRangeGrid({ left: 62, right: 24, top: 58, bottom: 42 }, rounds),
      xAxis: this.roundValueXAxis(rounds),
      yAxis: { type: 'value', name: '中位排名', inverse: true },
      series: [
        {
          name: '候选',
          type: 'scatter',
          symbolSize: (value: unknown) => 8 + Number((value as unknown[])[2] ?? 0) * 4,
          data: points,
        },
      ],
      ...(dataZoom.length ? { dataZoom } : {}),
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
      dynamic_parity_transition_weight: '动态奇偶转移',
      previous_zone_shape_weight: '分区形态',
      recent_neighbor_weight: '近期开奖邻号',
      lagged_consecutive_weight: '隔期连号链',
      recent_gap_shape_weight: '跳号间距',
      recent_sum_span_weight: '和值跨度',
      qian_kun_pattern_weight: '乾坤卦象',
      first_last_sum_weight: '首尾合',
      span_trend_weight: '首尾差/跨度',
      sum_trend_weight: '和值走势',
      ac_trend_weight: 'AC值走势',
      zone_ratio_weight: '区间比',
      big_small_ratio_weight: '大小比',
      parity_ratio_weight: '奇偶比',
      prime_composite_weight: '质合比',
      mod012_weight: '012路',
      tail_distribution_weight: '尾数分布',
      sum_tail_weight: '和尾走势',
      red_omission_shape_weight: '红球遗漏形态',
      sum_span_omission_weight: '和值跨度遗漏',
      consecutive_trend_weight: '连号走势',
      repeat_trend_weight: '重号走势',
      stable_range_weight: '稳定区间',
      weekday_trend_weight: '开奖日走势',
    };
    return labels[key] ?? key;
  }

  private chartRounds(status: TrainingStatusPayload): TrainingRoundSummary[] {
    return status.rounds.length ? status.rounds : [...status.recentRounds].reverse();
  }

  private groupedLineOption({
    title,
    rounds,
    xAxis,
    yName,
    series,
  }: {
    title: string;
    rounds: TrainingRoundSummary[];
    xAxis: string[];
    yName: string;
    series: Record<string, unknown>[];
  }): ChartOption {
    const dataZoom = this.roundRangeDataZoom(rounds);
    return {
      title: { text: title, left: 12, top: 8, textStyle: { fontSize: 14, fontWeight: 700 } },
      tooltip: this.roundAxisTooltip(rounds),
      legend: { type: 'scroll', top: 38, left: 12, right: 12 },
      grid: this.roundRangeGrid({ left: 58, right: 24, top: 92, bottom: 42 }, rounds),
      xAxis: this.roundCategoryXAxis(xAxis, rounds),
      yAxis: { type: 'value', name: yName },
      series,
      ...(dataZoom.length ? { dataZoom } : {}),
    };
  }

  private baseLineOption({
    title,
    rounds,
    xAxis,
    yName,
    series,
    inverse = false,
    markLineValue,
    markLineName,
  }: {
    title: string;
    rounds: TrainingRoundSummary[];
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
    const dataZoom = this.roundRangeDataZoom(rounds);
    return {
      title: { text: title, left: 12, top: 8, textStyle: { fontSize: 14, fontWeight: 700 } },
      tooltip: this.roundAxisTooltip(rounds),
      legend: { top: 8, right: 12 },
      grid: this.roundRangeGrid({ left: 62, right: 24, top: 58, bottom: 42 }, rounds),
      xAxis: this.roundCategoryXAxis(xAxis, rounds),
      yAxis: { type: 'value', name: yName, inverse },
      series: nextSeries,
      ...(dataZoom.length ? { dataZoom } : {}),
    };
  }

  private roundRangeDataZoom(rounds: readonly TrainingRoundSummary[]): Record<string, unknown>[] {
    if (!this.hasRoundRangeZoom(rounds)) {
      return [];
    }
    const start = this.roundRangeZoomStart(rounds.length);
    return [
      {
        type: 'inside',
        xAxisIndex: 0,
        start,
        end: 100,
        filterMode: 'filter',
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        moveOnMouseWheel: true,
      },
      {
        type: 'slider',
        xAxisIndex: 0,
        start,
        end: 100,
        filterMode: 'filter',
        bottom: ROUND_ZOOM_SLIDER_BOTTOM,
        height: ROUND_ZOOM_SLIDER_HEIGHT,
        brushSelect: false,
        labelFormatter: (value: number | string) => this.roundZoomLabel(rounds, value),
      },
    ];
  }

  private hasRoundRangeZoom(rounds: readonly TrainingRoundSummary[]): boolean {
    return rounds.length > ROUND_ZOOM_THRESHOLD;
  }

  private roundRangeZoomStart(roundCount: number): number {
    return Math.max(0, ((roundCount - ROUND_ZOOM_DEFAULT_WINDOW) / roundCount) * 100);
  }

  private roundRangeGrid(grid: Record<string, number>, rounds: readonly TrainingRoundSummary[]): Record<string, number> {
    if (!this.hasRoundRangeZoom(rounds)) {
      return grid;
    }
    return { ...grid, bottom: ROUND_ZOOM_GRID_BOTTOM };
  }

  private roundCategoryXAxis(xAxis: string[], rounds: readonly TrainingRoundSummary[]): Record<string, unknown> {
    return {
      type: 'category',
      data: xAxis,
      axisLabel: this.roundAxisLabel(rounds),
      axisTick: { alignWithLabel: true },
    };
  }

  private roundValueXAxis(rounds: readonly TrainingRoundSummary[]): Record<string, unknown> {
    const firstRound = rounds[0]?.round;
    const lastRound = rounds.at(-1)?.round;
    return {
      type: 'value',
      name: '轮次',
      min: firstRound,
      max: lastRound,
      minInterval: 1,
      axisLabel: {
        hideOverlap: true,
        formatter: (value: number) => `R${Math.round(value)}`,
      },
    };
  }

  private roundAxisLabel(rounds: readonly TrainingRoundSummary[]): Record<string, unknown> {
    const label: Record<string, unknown> = { hideOverlap: true };
    if (rounds.length > 40 && !this.hasRoundRangeZoom(rounds)) {
      label['interval'] = 'auto';
    }
    return label;
  }

  private roundAxisTooltip(rounds: readonly TrainingRoundSummary[]): Record<string, unknown> {
    return {
      trigger: 'axis',
      formatter: (params: unknown) => this.roundTooltipText(rounds, params),
    };
  }

  private roundTooltipText(rounds: readonly TrainingRoundSummary[], params: unknown): string {
    const values = (Array.isArray(params) ? params : [params]).filter(Boolean) as ChartTooltipParam[];
    const first = values[0];
    if (!first) {
      return '暂无轮次数据';
    }
    const round = typeof first.dataIndex === 'number' ? rounds[first.dataIndex] : null;
    const issueText = round?.best?.as_of_issue ? ` / 期号 ${round.best.as_of_issue}` : '';
    const title = round ? `R${round.round}${issueText}` : String(first.axisValueLabel ?? first.axisValue ?? '轮次');
    const lines = values.map((item) => {
      const label = item.seriesName ?? '值';
      const marker = item.marker ?? '';
      return `${marker}${label}: ${this.tooltipValueText(item.value ?? item.data)}`;
    });
    return [title, ...lines].join('<br/>');
  }

  private tooltipValueText(value: unknown): string {
    if (value === null || value === undefined) {
      return '无';
    }
    if (Array.isArray(value)) {
      return value.map((item) => this.tooltipValueText(item)).join(', ');
    }
    if (typeof value === 'number') {
      return value.toLocaleString('zh-CN');
    }
    return String(value);
  }

  private roundZoomLabel(rounds: readonly TrainingRoundSummary[], value: number | string): string {
    if (typeof value === 'number' && Number.isFinite(value)) {
      const roundedValue = Math.round(value);
      const valueRound = rounds.find((round) => round.round === roundedValue);
      if (valueRound) {
        return `R${valueRound.round}`;
      }
      const indexRound = rounds[roundedValue];
      if (indexRound) {
        return `R${indexRound.round}`;
      }
    }
    return String(value);
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

  private signalRangeDataZoom(pointCount: number): Record<string, unknown>[] {
    if (pointCount <= SIGNAL_ZOOM_THRESHOLD) {
      return [];
    }
    const start = Math.max(0, ((pointCount - SIGNAL_ZOOM_DEFAULT_WINDOW) / pointCount) * 100);
    return [
      {
        type: 'inside',
        start,
        end: 100,
        filterMode: 'filter',
        zoomOnMouseWheel: true,
        moveOnMouseWheel: true,
      },
      {
        type: 'slider',
        start,
        end: 100,
        filterMode: 'filter',
        bottom: ROUND_ZOOM_SLIDER_BOTTOM,
        height: ROUND_ZOOM_SLIDER_HEIGHT,
        brushSelect: false,
      },
    ];
  }

  private signalTooltipText(series: TrainingWeightSignalSeries | null, params: unknown): string {
    const values = (Array.isArray(params) ? params : [params]).filter(Boolean) as ChartTooltipParam[];
    const first = values[0];
    const point = series && typeof first?.dataIndex === 'number' ? series.points[first.dataIndex] : null;
    const header = point ? `期号 ${point.issue}${point.drawDate ? ` / ${point.drawDate}` : ''}` : String(first?.axisValueLabel ?? first?.axisValue ?? '权重KDJ');
    const rows = values
      .map((item) => `${item.marker ?? ''}${item.seriesName}: ${typeof item.value === 'number' ? item.value.toFixed(3) : item.value}`)
      .join('<br/>');
    const offset = point ? `<br/>建议偏移 ${point.recommendedOffset.toFixed(4)} / 分数差 ${point.objectiveDelta.toFixed(3)}` : '';
    return `${header}<br/>${rows}${offset}`;
  }

  private ensureSelection(payload: ExperimentsPayload): void {
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

  private ensureTrainingRoundSelection(rounds: TrainingRoundListItem[]): void {
    if (!rounds.length) {
      this.selectedTrainingRoundKey = null;
      this.trainingRoundDetailRequests.next(null);
      return;
    }
    const selected = rounds.find((round) => this.trainingRoundKey(round) === this.selectedTrainingRoundKey) ?? rounds[0];
    this.selectTrainingRound(selected);
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
