import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart3, Activity, Sparkles, Layers, Save,
} from 'lucide-react';
import { features } from '@/lib/features';
import { ChartView, Legend } from '@/components/charts/chartEngine';
import { CHART_TYPE_LABELS } from '@/lib/format';
import { Card, Select, Field, Button, Badge, cn, LoadingBlock } from '@/components/ui';
import { toast } from '@/components/ui';
import type { ChartData, ChartRecommendation } from '@/lib/types';

interface ChartBuilderProps {
  datasetId: string;
  onSaved?: () => void;
}

const TYPE_GROUPS: { label: string; types: string[] }[] = [
  { label: 'Comparison', types: ['bar', 'column', 'grouped_bar', 'grouped_column', 'stacked_bar', 'stacked_column', 'hundred_bar', 'hundred_column'] },
  { label: 'Trend', types: ['line', 'area', 'waterfall'] },
  { label: 'Distribution', types: ['histogram', 'scatter', 'bubble', 'box', 'heatmap'] },
  { label: 'Part-to-whole', types: ['pie', 'donut', 'treemap', 'sunburst', 'funnel', 'radar'] },
  { label: 'Summary', types: ['kpi', 'gauge', 'table'] },
];

const NEEDS_SERIES = new Set(['stacked_bar', 'stacked_column', 'grouped_bar', 'grouped_column', 'hundred_bar', 'hundred_column']);
const MEASURE_TYPES = new Set(['pie', 'donut', 'bar', 'column', 'line', 'area', 'treemap', 'funnel', 'radar', 'waterfall', 'stacked_bar', 'stacked_column', 'grouped_bar', 'grouped_column', 'hundred_bar', 'hundred_column', 'kpi', 'gauge']);
const XTYPE_TYPES = new Set(['histogram', 'scatter', 'bubble', 'pie', 'donut', 'bar', 'column', 'line', 'area', 'treemap', 'funnel', 'radar', 'waterfall', 'stacked_bar', 'stacked_column', 'grouped_bar', 'grouped_column', 'hundred_bar', 'hundred_column', 'heatmap', 'sunburst', 'box']);
const BIN_TYPES = new Set(['histogram']);

export function ChartBuilder({ datasetId, onSaved }: ChartBuilderProps) {
  const [chartType, setChartType] = useState('column');
  const [x, setX] = useState('');
  const [y, setY] = useState('');
  const [color, setColor] = useState('');
  const [value, setValue] = useState('');
  const [bins, setBins] = useState(20);
  const [agg, setAgg] = useState('sum');
  const [result, setResult] = useState<{ data: ChartData | null; error?: string | null } | null>(null);
  const [busy, setBusy] = useState(false);
  const [savedName, setSavedName] = useState('');
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { data: schema, isLoading } = useQuery({
    queryKey: ['charts-schema', datasetId],
    queryFn: () => features.charts.schema(datasetId),
    enabled: !!datasetId,
  });
  const { data: recs } = useQuery({
    queryKey: ['charts-recommend', datasetId],
    queryFn: () => features.charts.recommend(datasetId),
    enabled: !!datasetId,
  });

  const numericCols = useMemo(() => (schema ?? []).filter((c) => c.type === 'numeric').map((c) => c.name), [schema]);
  const dimCols = useMemo(() => (schema ?? []).filter((c) => c.type !== 'numeric').map((c) => c.name), [schema]);

  useEffect(() => {
    if (!schema?.length) return;
    setX((v) => v || (dimCols.includes('category') ? 'category' : (dimCols[0] ?? numericCols[0] ?? '')));
    setY((v) => v || (numericCols[0] ?? ''));
    setValue((v) => v || (numericCols[0] ?? ''));
    setColor((v) => v || (dimCols[0] ?? ''));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schema?.length, datasetId]);

  const config = useMemo(() => {
    if (XTYPE_TYPES.has(chartType) && chartType !== 'histogram' && chartType !== 'scatter' && chartType !== 'bubble' && chartType !== 'box' && chartType !== 'heatmap') {
      return { x, y, color: NEEDS_SERIES.has(chartType) ? color : undefined, aggregation: agg, limit: 30 };
    }
    if (chartType === 'histogram') return { x, bins };
    if (chartType === 'scatter' || chartType === 'bubble') return { x, y, color };
    if (chartType === 'box') return { y, group_by: x || undefined };
    if (chartType === 'heatmap') return { x, y, value };
    if (chartType === 'kpi' || chartType === 'gauge') return { y, aggregation: agg, label: savedName || y };
    if (chartType === 'table') return {};
    return { x, y };
  }, [chartType, x, y, color, value, bins, agg, savedName]);

  const build = async (ct = chartType, cfgOverride?: Record<string, unknown>) => {
    const cfg = cfgOverride ?? config;
    setBusy(true);
    try {
      const res = await features.charts.build(datasetId, ct, cfg);
      setResult({ data: res.data, error: res.error });
    } catch (e) {
      setResult({ data: null, error: e instanceof Error ? e.message : 'Failed to build chart.' });
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!datasetId) return;
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => build(chartType), 350);
    return () => { if (debounce.current) clearTimeout(debounce.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartType, x, y, color, value, bins, agg, datasetId]);

  const useRec = (r: ChartRecommendation) => {
    setChartType(r.chart_type);
    if (r.x) setX(r.x);
    if (r.y) setY(r.y);
    if (r.dimension) setColor(r.dimension);
  };

  const save = async () => {
    if (!result?.data || !savedName.trim()) {
      toast('Name required', 'Enter a name before saving this chart.', 'error');
      return;
    }
    try {
      await features.charts.save(datasetId, chartType, config, savedName.trim());
      toast('Chart saved', savedName.trim(), 'success');
      setSavedName('');
      onSaved?.();
    } catch (e) {
      toast('Save failed', e instanceof Error ? e.message : 'Could not save.', 'error');
    }
  };

  if (isLoading) return <LoadingBlock label="Loading schema…" />;

  return (
    <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
      {/* Controls */}
      <div className="space-y-4">
        <div className="space-y-2 rounded-2xl border border-border bg-card p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold">Chart type</span>
            <Badge tone="blue">{CHART_TYPE_LABELS[chartType] ?? chartType}</Badge>
          </div>
          {TYPE_GROUPS.map((g) => (
            <div key={g.label}>
              <div className="mb-1 mt-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">{g.label}</div>
              <div className="flex flex-wrap gap-1">
                {g.types.map((t) => (
                  <button
                    key={t}
                    onClick={() => setChartType(t)}
                    className={cn(
                      'rounded-lg px-2 py-1 text-[11px] font-medium transition',
                      chartType === t ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground hover:text-foreground',
                    )}
                  >
                    {CHART_TYPE_LABELS[t] ?? t}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        <Card className="space-y-3 p-4">
          <div className="text-xs font-semibold">Configuration</div>

          {XTYPE_TYPES.has(chartType) && (
            <Field label={chartType === 'box' ? 'Group by' : chartType === 'histogram' ? 'Numeric column' : 'Dimension (X)'}>
              <Select value={x} onChange={(e) => setX(e.target.value)}>
                <option value="">—</option>
                {XTYPE_TYPES.has(chartType) && chartType !== 'histogram' && chartType !== 'scatter' && chartType !== 'bubble'
                  ? dimCols.map((c) => <option key={c} value={c}>{c}</option>)
                  : [...dimCols, ...numericCols].map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </Field>
          )}

          {MEASURE_TYPES.has(chartType) && (
            <Field label="Measure (Y)">
              <Select value={y} onChange={(e) => setY(e.target.value)}>
                <option value="">—</option>
                {numericCols.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </Field>
          )}

          {NEEDS_SERIES.has(chartType) && (
            <Field label="Series / color">
              <Select value={color} onChange={(e) => setColor(e.target.value)}>
                <option value="">—</option>
                {dimCols.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </Field>
          )}

          {chartType === 'heatmap' && (
            <Field label="Value">
              <Select value={value} onChange={(e) => setValue(e.target.value)}>
                <option value="">—</option>
                {numericCols.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </Field>
          )}

          {BIN_TYPES.has(chartType) && (
            <Field label="Bins">
              <input
                type="number"
                min={5}
                max={50}
                value={bins}
                onChange={(e) => setBins(Number(e.target.value))}
                className="h-9 w-full rounded-lg border border-input bg-card px-3 text-[13px] outline-none focus:border-primary/50"
              />
            </Field>
          )}

          {(chartType === 'kpi' || chartType === 'gauge' || (MEASURE_TYPES.has(chartType) && chartType !== 'pie' && chartType !== 'donut')) && (
            <Field label="Aggregation">
              <Select value={agg} onChange={(e) => setAgg(e.target.value)}>
                {['sum', 'mean', 'median', 'min', 'max', 'count', 'std'].map((a) => <option key={a} value={a}>{a}</option>)}
              </Select>
            </Field>
          )}

          <Button variant="outline" size="sm" onClick={() => build()} loading={busy}>
            <Activity className="h-3.5 w-3.5" /> Rebuild
          </Button>
        </Card>

        {recs?.length ? (
          <Card className="p-4">
            <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold">
              <Sparkles className="h-3.5 w-3.5 text-warning" /> Suggested charts
            </div>
            <div className="space-y-1.5">
              {recs.slice(0, 5).map((r, i) => (
                <button
                  key={i}
                  onClick={() => useRec(r)}
                  className="w-full rounded-xl border border-border px-3 py-2 text-left transition hover:border-primary/40 hover:bg-muted"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold">{CHART_TYPE_LABELS[r.chart_type] ?? r.chart_type}</span>
                    <span className="text-[10px] text-muted-foreground">{r.x} · {r.y}</span>
                  </div>
                  <div className="mt-0.5 text-[10px] leading-snug text-muted-foreground">{r.reason}</div>
                </button>
              ))}
            </div>
          </Card>
        ) : null}

        <Card className="space-y-3 p-4">
          <div className="text-xs font-semibold">Save chart</div>
          <input
            value={savedName}
            onChange={(e) => setSavedName(e.target.value)}
            placeholder="Chart name"
            className="h-9 w-full rounded-lg border border-input bg-card px-3 text-[13px] outline-none focus:border-primary/50"
          />
          <Button size="sm" className="w-full" onClick={save} disabled={!result?.data}>
            <Save className="h-3.5 w-3.5" /> Save to workspace
          </Button>
        </Card>
      </div>

      {/* Preview */}
      <Card className="min-w-0 p-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <BarChart3 className="h-4 w-4 text-primary" />
            {CHART_TYPE_LABELS[chartType] ?? chartType}
            {x && y && <span className="text-[11px] font-normal text-muted-foreground">— {x} × {y}</span>}
          </div>
          {busy && <span className="text-[11px] text-muted-foreground">Rendering…</span>}
        </div>
        {result?.error ? (
          <div className="rounded-xl bg-destructive/10 px-4 py-6 text-center text-xs text-destructive">{result.error}</div>
        ) : result?.data ? (
          <>
            {chartType === 'kpi' || chartType === 'gauge' ? (
              <ChartView data={result.data} chartType={chartType} height={220} />
            ) : (
              <ChartView data={result.data} chartType={chartType} height={360} />
            )}
            {result.data.series?.length ? <Legend series={result.data.series} /> : null}
          </>
        ) : (
          <div className="flex items-center justify-center py-16 text-xs text-muted-foreground">
            <Layers className="mr-2 h-4 w-4" /> Configure the chart to preview it.
          </div>
        )}
      </Card>
    </div>
  );
}