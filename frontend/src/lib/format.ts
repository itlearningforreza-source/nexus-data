export function formatNumber(v: unknown, opts?: Intl.NumberFormatOptions): string {
  const n = Number(v);
  if (v === null || v === undefined || Number.isNaN(n)) return '–';
  return new Intl.NumberFormat('en-US', opts ?? { maximumFractionDigits: 2 }).format(n);
}

export function formatCompact(v: number): string {
  return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(v);
}

export function formatCurrency(v: unknown, currency = 'USD'): string {
  const n = Number(v);
  if (Number.isNaN(n)) return '–';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 2 }).format(n);
}

export function formatPercent(v: unknown, digits = 1): string {
  const n = Number(v);
  if (Number.isNaN(n)) return '–';
  return `${(n * 100).toFixed(digits)}%`;
}

export function formatBytes(bytes: number): string {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i ? 1 : 0)} ${units[i]}`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '–';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatDateShort(iso: string | null | undefined): string {
  if (!iso) return '–';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return '';
  const secs = Math.floor((Date.now() - d) / 1000);
  if (secs < 60) return 'just now';
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return formatDateShort(iso);
}

export function round(v: number, digits = 2): number {
  const f = Math.pow(10, digits);
  return Math.round(v * f) / f;
}

export function cellToString(v: unknown): string {
  if (v === null || v === undefined) return '';
  if (typeof v === 'object') {
    try {
      return JSON.stringify(v);
    } catch {
      return String(v);
    }
  }
  return String(v);
}

export const CHART_TYPE_LABELS: Record<string, string> = {
  bar: 'Bar',
  column: 'Column',
  line: 'Line',
  area: 'Area',
  pie: 'Pie',
  donut: 'Donut',
  scatter: 'Scatter',
  bubble: 'Bubble',
  histogram: 'Histogram',
  heatmap: 'Heatmap',
  treemap: 'Treemap',
  radar: 'Radar',
  funnel: 'Funnel',
  gauge: 'Gauge',
  kpi: 'KPI',
  table: 'Table',
  box: 'Box Plot',
  stacked_bar: 'Stacked Bar',
  stacked_column: 'Stacked Column',
  hundred_bar: '100% Bar',
  sunburst: 'Sunburst',
  waterfall: 'Waterfall',
  grouped_bar: 'Grouped Bar',
  grouped_column: 'Grouped Column',
  hundred_stacked_bar: '100% Stacked Bar',
};

export const CHART_TYPES = Object.keys(CHART_TYPE_LABELS);

export function truncate(s: string, n = 40): string {
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}