import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Sigma, Repeat, FlaskConical, Activity } from 'lucide-react';
import { features } from '@/lib/features';
import { Card, Button, Select, Field, Tabs, cn } from '@/components/ui';
import { toast } from '@/components/ui';
import { formatNumber, cellToString } from '@/lib/format';

const TESTS: { id: string; label: string }[] = [
  { id: 'ttest', label: 'T-test' },
  { id: 'anova', label: 'ANOVA' },
  { id: 'chi_square', label: 'Chi-square' },
  { id: 'mann_whitney', label: 'Mann-Whitney' },
  { id: 'wilcoxon', label: 'Wilcoxon' },
  { id: 'kruskal', label: 'Kruskal-Wallis' },
];

function strength(r: number) {
  const a = Math.abs(r);
  if (a > 0.7) return 'strong';
  if (a > 0.4) return 'moderate';
  if (a > 0.2) return 'weak';
  return 'negligible';
}

export function StatsPanel({ datasetId }: { datasetId: string }) {
  const [tab, setTab] = useState('descriptive');
  const qc = useQueryClient();

  const { data: prof } = useQuery({ queryKey: ['profile', datasetId], queryFn: () => features.datasets.profile(datasetId) });
  const numeric = (prof?.profile.columns ?? []).filter((c) => c.numeric).map((c) => c.name);
  const categories = (prof?.profile.columns ?? []).filter((c) => !c.numeric).map((c) => c.name);

  const desc = useQuery({ queryKey: ['stats-desc', datasetId], queryFn: () => features.stats.descriptive(datasetId), enabled: tab === 'descriptive' });
  const corr = useQuery({ queryKey: ['stats-corr', datasetId], queryFn: () => features.stats.correlation(datasetId), enabled: tab === 'correlation' });

  const [test, setTest] = useState('anova');
  const [testCol, setTestCol] = useState('');
  const [testGroup, setTestGroup] = useState('');
  const [testResult, setTestResult] = useState<{ test: string; statistic: number; p_value: number; interpretation: string; significant: boolean } | null>(null);
  const [testBusy, setTestBusy] = useState(false);

  const runTest = async () => {
    const t = TESTS.find((x) => x.id === test)!;
    const params: Record<string, unknown> = {};
    if (t.id === 'ttest' || t.id === 'mann_whitney' || t.id === 'wilcoxon') { params.column = testCol; params.group = testGroup; }
    if (t.id === 'anova' || t.id === 'kruskal') { params.value = testCol; params.groups = testGroup; }
    if (t.id === 'chi_square') { params.col_a = testCol; params.col_b = testGroup; }
    setTestBusy(true);
    try {
      const res = await features.stats.test(datasetId, test, params);
      setTestResult(res as typeof testResult);
      qc.invalidateQueries({ queryKey: ['stats-history'] });
    } catch (e) {
      toast('Test failed', e instanceof Error ? e.message : 'Could not run test.', 'error');
    } finally {
      setTestBusy(false);
    }
  };

  const rows = useMemo(() => {
    if (!desc.data?.columns) return [];
    return Object.entries(desc.data.columns);
  }, [desc.data]);

  const corrPairs = useMemo(() => corr.data?.pairs ?? [], [corr.data]);
  const maxAbs = Math.max(...corrPairs.map((p) => Math.abs(p.r)), 0.0001);

  return (
    <>
      <Tabs
        tabs={[
          { id: 'descriptive', label: 'Descriptive', icon: <Sigma className="h-3.5 w-3.5" /> },
          { id: 'correlation', label: 'Correlation', icon: <Repeat className="h-3.5 w-3.5" /> },
          { id: 'tests', label: 'Hypothesis tests', icon: <FlaskConical className="h-3.5 w-3.5" /> },
        ]}
        active={tab}
        onChange={setTab}
      />
      {tab === 'descriptive' && (
        <div className="scrollbar-thin mt-4 overflow-auto rounded-xl border border-border" style={{ maxHeight: 460 }}>
          {desc.isLoading && <div className="p-10 text-center text-xs text-muted-foreground">Computing statistics…</div>}
          {rows.length > 0 && (
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-muted/95">
                <tr>
                  <th className="px-3 py-2 font-semibold text-muted-foreground">Metric</th>
                  {rows.map(([c]) => <th key={c} className="whitespace-nowrap px-2 py-2 font-semibold text-muted-foreground">{c}</th>)}
                </tr>
              </thead>
              <tbody>
                {[
                  ['count', 'count'], ['missing', 'missing'], ['mean', 'mean'], ['median', 'median'], ['mode', 'mode'],
                  ['std', 'std'], ['var', 'var'], ['min', 'min'], ['max', 'max'], ['range', 'range'],
                  ['q1', 'Q1'], ['q3', 'Q3'], ['iqr', 'IQR'], ['skewness', 'skewness'], ['kurtosis', 'kurtosis'],
                ].map(([key, label]) => (
                  <tr key={key} className="border-t border-border/60">
                    <td className="whitespace-nowrap px-3 py-1.5 font-medium text-muted-foreground">{label}</td>
                    {rows.map(([, stats]) => {
                      const v = (stats as Record<string, unknown>)[key];
                      const str = typeof v === 'number' ? formatNumber(v) : v === null || v === undefined ? '–' : cellToString(v);
                      return <td key={key} className="whitespace-nowrap px-2 py-1.5 tabular-nums">{str}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === 'correlation' && (
        <div className="mt-4 space-y-3">
          {corr.isLoading && <div className="p-6 text-center text-xs text-muted-foreground">Computing correlations…</div>}
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {corrPairs.sort((a, b) => Math.abs(b.r) - Math.abs(a.r)).map((p, i) => {
              const w = (Math.abs(p.r) / maxAbs) * 100;
              return (
                <Card key={i} className="p-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold">{p.x} × {p.y}</span>
                    <span className={cn('font-mono font-semibold', p.r >= 0 ? 'text-chart-blue' : 'text-chart-pink')}>
                      {p.r.toFixed(3)}
                    </span>
                  </div>
                  <div className="relative mt-2 h-2 overflow-hidden rounded-full bg-muted">
                    <div className={cn('h-full rounded-full', p.r >= 0 ? 'bg-chart-blue' : 'bg-chart-pink')} style={{ width: `${w}%` }} />
                  </div>
                  <div className="mt-1.5 flex items-center justify-between text-[10px] text-muted-foreground">
                    <span>{strength(p.r)} {p.significant ? '· significant' : ''}</span>
                    <span>p={p.p_value.toFixed(4)} · n={p.n}</span>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {tab === 'tests' && (
        <div className="mt-4 grid gap-4 lg:grid-cols-[320px_1fr]">
          <Card className="space-y-3 p-4">
            <Field label="Statistical test">
              <Select value={test} onChange={(e) => setTest(e.target.value)}>
                {TESTS.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              </Select>
            </Field>
            <Field label={test === 'chi_square' ? 'Column A (categorical)' : 'Value column (numeric)'}>
              <Select value={testCol} onChange={(e) => setTestCol(e.target.value)}>
                <option value="">—</option>
                {(test === 'chi_square' ? categories : numeric).map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </Field>
            <Field label={test === 'chi_square' ? 'Column B (categorical)' : 'Group column (categorical)'}>
              <Select value={testGroup} onChange={(e) => setTestGroup(e.target.value)}>
                <option value="">—</option>
                {categories.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </Field>
            <Button className="w-full" onClick={runTest} loading={testBusy} disabled={!testCol}>
              <FlaskConical className="h-3.5 w-3.5" /> Run test
            </Button>
          </Card>
          <Card className="p-5">
            {!testResult ? (
              <div className="flex h-full flex-col items-center justify-center gap-2 py-10 text-xs text-muted-foreground">
                <Activity className="h-5 w-5" />
                Pick a test and columns to see the result.
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold">{TESTS.find((t) => t.id === testResult.test)?.label ?? testResult.test}</span>
                  <span className={cn('rounded-full px-2.5 py-1 text-[11px] font-semibold', testResult.significant ? 'bg-chart-green/15 text-chart-green' : 'bg-muted text-muted-foreground')}>
                    {testResult.significant ? 'Significant' : 'Not significant'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-xl border border-border p-3">
                    <div className="text-[10px] uppercase text-muted-foreground">Statistic</div>
                    <div className="mt-0.5 font-mono text-lg font-bold tabular-nums">{formatNumber(testResult.statistic)}</div>
                  </div>
                  <div className="rounded-xl border border-border p-3">
                    <div className="text-[10px] uppercase text-muted-foreground">p-value</div>
                    <div className="mt-0.5 font-mono text-lg font-bold tabular-nums">{testResult.p_value.toFixed(5)}</div>
                  </div>
                </div>
                <p className="rounded-xl bg-muted/50 px-3 py-2.5 text-xs leading-relaxed text-muted-foreground">{testResult.interpretation}</p>
              </div>
            )}
          </Card>
        </div>
      )}
    </>
  );
}