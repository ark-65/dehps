import { isPlatformBrowser } from '@angular/common';
import {
  AfterViewInit,
  Component,
  ElementRef,
  Inject,
  Input,
  OnChanges,
  OnDestroy,
  PLATFORM_ID,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import * as echarts from 'echarts/core';
import { BarChart, LineChart, ScatterChart } from 'echarts/charts';
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { ECharts, EChartsCoreOption } from 'echarts/core';

echarts.use([
  BarChart,
  LineChart,
  ScatterChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
]);

@Component({
  selector: 'app-echart',
  standalone: true,
  template: '<div #host class="echart-host" [style.height]="height"></div>',
  styles: [
    `
      :host {
        display: block;
        min-width: 0;
      }

      .echart-host {
        width: 100%;
        min-height: 260px;
      }
    `,
  ],
})
export class EchartComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input() option: EChartsCoreOption | null = null;
  @Input() height = '320px';
  @ViewChild('host', { static: true }) private readonly host?: ElementRef<HTMLDivElement>;

  private chart: ECharts | null = null;
  private readonly browser: boolean;
  private resizeObserver: ResizeObserver | null = null;

  constructor(@Inject(PLATFORM_ID) platformId: object) {
    this.browser = isPlatformBrowser(platformId);
  }

  ngAfterViewInit(): void {
    if (!this.browser || !this.host) {
      return;
    }
    this.chart = echarts.init(this.host.nativeElement, undefined, { renderer: 'canvas' });
    this.resizeObserver = new ResizeObserver(() => this.chart?.resize());
    this.resizeObserver.observe(this.host.nativeElement);
    this.render();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['option'] || changes['height']) {
      this.render();
    }
  }

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect();
    this.chart?.dispose();
  }

  private render(): void {
    if (!this.chart || !this.option) {
      return;
    }
    this.chart.setOption(this.option, true);
  }
}

export type ChartOption = EChartsCoreOption;
