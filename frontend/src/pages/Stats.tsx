import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Sigma, Repeat, TrendingUp, GitCompareArrows } from 'lucide-react';
import { features } from '@/lib/features';
import { Card, Button, Select, Field, Tabs, Badge, cn } from '@/components/ui';
import { toast } from '@/components/ui';
import { ChartView } from '@/components/charts/chartEngine';
import { PageHeader } from '@/components/layout/PageHeader';
import { formatNumber } from '@/lib/format';
import type { ChartData, ProfileColumn } from '@/lib/types';

export default function Stats() {
  const [datasetId, setDatasetId] = useState('');
  const [tab, setTab] = useState('descriptive');
  const [target, setTarget] = useState('');
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);
  const [dateCol, setDateCol] = useState('');
  const [valueCol, setValueCol] = useState('');
  const [windowN, setWindowN] = useState(7);

  const { data: datasets } = useQuery({ queryKey: ['datasets'], queryFn: () => features.datasets.list() });
  const { data: prof } = useQuery({ queryKey: ['profile', datasetId], queryFn: () => features.datasets.profile(datasetId), enabled: !!datasetId });
  const numeric = (prof?.profile.columns ?? []).filter((c) => c.numeric).map((c: ProfileColumn) => c.name);
  const dates = (prof?.profile.columns ?? []).filter((c) => c.dtype === 'datetime').map((c: ProfileColumn) => c.name);
  const categorical = (prof?.profile.columns ?? []).filter((c) => !c.numeric).map((c: ProfileColumn) => c.name);

  const desc = useQuery({ queryKey: ['stats-descriptive', datasetId], queryFn: () => features.stats.descriptive(datasetId), enabled: !!datasetId && tab === 'descriptive' });
  const corr = useQuery({ queryKey: ['stats-correlation', datasetId], queryFn: () => features.stats.correlation(datasetId), enabled: !!datasetId && tab === 'correlation' });
  const reg = useQuery({ queryKey: ['stats-reg', datasetId, target], queryFn: () => features.stats.regression(datasetId, target, selectedFeatures.join(',')), enabled: !!datasetId && !!target && tab === 'regression' });
  const ts = useQuery({ queryKey: ['stats-ts', datasetId, dateCol, valueCol, windowN], queryFn: () => features.stats.timeSeries(datasetId, dateCol, valueCol, windowN), enabled: !!datasetId && !!dateCol && !!valueCol && tab === 'time-series' });

  const runReg = async () => {
    if (!target) return;
    try {
      await reg.refetch();
    } catch (e) {
      toast('Regression failed', e instanceof Error ? e.message : 'Could not run.', 'error');
    }
  };

  const coefChart: ChartData | null = useMemo(() => {
    if (!reg.data) return null;
    return { labels: reg.data.features, values: reg.data.coefficients.map((c) => c.coefficient), x_column: 'feature', y_column: 'coefficient', color_column: undefined } as ChartData;
  }, [reg.data]);

  const tsChart: ChartData | null = useMemo(() => {
    if (!ts.data) return null;
    return {
      labels: ts.data.series.map((s) => s.date),
      values: ts.data.series.map((s) => s.value),
      series: [
        { name: valueCol, values: ts.data.series.map((s) => s.value) },
        { name: `MA(${windowN})`, values: ts.data.series.map((s) => s.moving_average ?? NaN) },
      ],
      x_column: 'date',
      y_column: valueCol,
    } as ChartData;
  }, [ts.data, valueCol, windowN]);

  const corrPairs = corr.data?.pairs ?? [];

  return (
    <div className="space-y-4">
      <PageHeader title="Statistics" description="Descriptive stats, correlations, hypothesis testing, regression and time-series analysis." />

      <Card className="flex flex-wrap items-center gap-3 p-3">
        <label className="text-xs font-medium text-muted-foreground">Dataset</label>
        <Select value={datasetId} onChange={(e) => setDatasetId(e.target.value)} className="w-64">
          <option value="">— select a dataset —</option>
          {(datasets ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </Select>
        {!datasetId && <span className="text-[11px] text-muted-foreground">Choose a dataset to unlock the analysis tools.</span>}
      </Card>

      {datasetId && (
        <>
          <Tabs
            tabs={[
              { id: 'descriptive', label: 'Descriptive', icon: <Sigma className="h-3.5 w-3.5" /> },
              { id: 'correlation', label: 'Correlation', icon: <Repeat className="h-3.5 w-3.5" /> },
              { id: 'regression', label: 'Regression', icon: <GitCompareArrows className="h-3.5 w-3.5" /> },
              { id: 'time-series', label: 'Time series', icon: <TrendingUp className="h-3.5 w-3.5" /> },
            ]}
            active={tab} onChange={setTab}
          />
          {tab === 'descriptive' && (
            <div className="scrollbar-thin mt-4 overflow-auto rounded-xl border border-border" style={{ maxHeight: 520 }}>
              {desc.isLoading && <div className="p-10 text-center text-xs text-muted-foreground">Computing…</div>}
              {desc.data && (
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-muted/95">
                    <tr>
                      <th className="px-3 py-2 font-semibold text-muted-foreground">Metric</th>
                      {Object.keys(desc.data.columns).map((c) => <th key={c} className="whitespace-nowrap px-2 py-2 font-semibold text-muted-foreground">{c}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {['count', 'missing', 'mean', 'median', 'mode', 'std', 'min', 'max', 'range', 'q1', 'q3', 'iqr', 'skewness', 'kurtosis'].map((key) => (
                      <tr key={key} className="border-t border-border/60">
                        <td className="whitespace-nowrap px-3 py-1.5 font-medium text-muted-foreground">{key}</td>
                        {Object.values(desc.data.columns).map((stats, i) => {
                          const v = (stats as Record<string, unknown>)[key];
                          const str = typeof v === 'number' ? String(v.toFixed(2)) : (v === null || v === undefined ? '–' : String(v));
                          return <td key={i} className="whitespace-nowrap px-2 py-1.5 font-mono tabular-nums">{str}</td>;
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {tab === 'correlation' && (
            <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {corr.isLoading && <div className="col-span-full p-6 text-center text-xs text-muted-foreground">Computing correlations…</div>}
              {corrPairs.sort((a, b) => Math.abs(b.r) - Math.abs(a.r)).map((p, i) => (
                <Card key={i} className="p-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold">{p.x} × {p.y}</span>
                    <span className={cn('font-mono font-semibold', p.r >= 0 ? 'text-chart-blue' : 'text-chart-pink')}>{p.r.toFixed(3)}</span>
                  </div>
                  <div className="relative mt-2 h-2 overflow-hidden rounded-full bg-muted">
                    <div className={cn('h-full rounded-full', p.r >= 0 ? 'bg-chart-blue' : 'bg-chart-pink')} style={{ width: `${(Math.abs(p.r) * 100).toFixed(0)}%` }} />
                  </div>
                  <div className="mt-1.5 text-[10px] text-muted-foreground">{p.strength} · p={p.p_value.toFixed(4)} · n={p.n}</div>
                </Card>
              ))}
            </div>
          )}

          {tab === 'regression' && (
            <div className="mt-4 grid gap-4 lg:grid-cols-[300px_1fr]">
              <Card className="space-y-3 p-4">
                <Field label="Target (dependent variable)">
                  <Select value={target} onChange={(e) => setTarget(e.target.value)}>
                    <option value="">—</option>
                    {numeric.map((c) => <option key={c} value={c}>{c}</option>)}
                  </Select>
                </Field>
                <Field label="Features (comma separated, optional)">
                  <Select value={selectedFeatures.join(',')} onChange={(e) => setSelectedFeatures(e.target.value ? e.target.value.split(',').map((s) => s.trim()) : [])}>
                    <option value="">Auto-select</option>
                    {numeric.filter((c) => c !== target).map((c) => <option key={c} value={c}>{c}</option>)}
                  </Select>
                </Field>
                <Button className="w-full" onClick={runReg} disabled={!target} loading={reg.isFetching}>Run regression</Button>
              </Card>
              <div className="space-y-3">
                {!reg.data && !reg.isLoading && (
                  <Card className="p-8 text-center text-xs text-muted-foreground">Pick a target and run regression to see results.</Card>
                )}
                {reg.isLoading && <Card className="p-8 text-center text-xs text-muted-foreground">Fitting OLS…</Card>}
                {reg.data && (
                  <>
                    <Card className="p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold">Linear regression</span>
                        <Badge tone="green">R² {formatNumber(reg.data.r_squared)}</Badge>
                        <Badge tone="blue">adj. R² {formatNumber(reg.data.adjusted_r_squared)}</Badge>
                        <Badge tone="muted">RMSE {formatNumber(reg.data.rmse)}</Badge>
                        <Badge tone="muted">n={reg.data.observations}</Badge>
                      </div>
                      <p className="mt-2 font-mono text-xs text-muted-foreground">{reg.data.equation}</p>
                      <p className="mt-2 rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground">{reg.data.interpretation}</p>
                    </Card>
                    <Card className="p-4">
                      <div className="mb-2 text-xs font-semibold">Coefficients</div>
                      <div className="grid gap-2 md:grid-cols-2">
                        {reg.data.coefficients.map((c) => (
                          <div key={c.feature} className="rounded-lg border border-border px-3 py-2 text-xs">
                            <div className="flex items-center justify-between">
                              <span className="font-semibold">{c.feature}</span>
                              <Badge tone={c.significant ? 'green' : 'muted'}>{c.significant ? 'significant' : 'n.s.'}</Badge>
                            </div>
                            <div className="mt-1 flex justify-between font-mono text-[11px] text-muted-foreground">
                              <span>β = {c.coefficient.toFixed(4)}</span>
                              <span>p = {c.p_value.toFixed(4)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </Card>
                    {coefChart && (
                      <Card className="p-4">
                        <div className="mb-2 text-xs font-semibold">Coefficient magnitude</div>
                        <div className="h-64"><ChartView chartType="column" data={coefChart} /></div>
                      </Card>
                    )}
                  </>
                )}
              </div>
            </div>
          )}

          {tab === 'time-series' && (
            <div className="mt-4 grid gap-4 lg:grid-cols-[300px_1fr]">
              <Card className="space-y-3 p-4">
                <Field label="Date column">
                  <Select value={dateCol} onChange={(e) => setDateCol(e.target.value)}>
                    <option value="">—</option>
                    {dates.map((c) => <option key={c} value={c}>{c}</option>)}
                    {!dates.length && categorical.map((c) => <option key={c} value={c}>{c}</option>)}
                  </Select>
                </Field>
                <Field label="Value column">
                  <Select value={valueCol} onChange={(e) => setValueCol(e.target.value)}>
                    <option value="">—</option>
                    {numeric.map((c) => <option key={c} value={c}>{c}</option>)}
                  </Select>
                </Field>
                <Field label="Moving-average window">
                  <input type="number" min={1} value={windowN} onChange={(e) => setWindowN(Number(e.target.value) || 7)}
                    className="h-9 w-full rounded-lg border border-input bg-card px-3 text-[13px] outline-none focus:border-primary/50" />
                </Field>
              </Card>
              <div className="space-y-3">
                {!ts.data && !ts.isLoading && <Card className="p-8 text-center text-xs text-muted-foreground">Pick a date and value column to plot the series.</Card>}
                {ts.isLoading && <Card className="p-8 text-center text-xs text-muted-foreground">Analyzing series…</Card>}
                {ts.data && (
                  <>
                    <Card className="p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold">{valueCol} over time</span>
                        <Badge tone="blue">{ts.data.count} points · {ts.data.freq}</Badge>
                        <Badge tone={ts.data.trend.direction === 'up' ? 'green' : 'red'}>{ts.data.trend.direction === 'up' ? '↑' : '↓'} {ts.data.trend.slope > 0 ? 'upward' : 'downward'}</Badge>
                        <Badge tone="muted">CAGR {formatNumber(ts.data.growth.cagr)}% · {ts.data.start} → {ts.data.end}</Badge>
                      </div>
                      <div className="mt-3 h-72"><ChartView chartType="line" data={tsChart!} /></div>
                    </Card>
                  </>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}