import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Play, Cpu, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import { features } from '@/lib/features';
import { api } from '@/lib/api';
import { Card, Button, Select, Field, Badge, cn, EmptyState } from '@/components/ui';
import { toast } from '@/components/ui';
import { ChartView } from '@/components/charts/chartEngine';
import { PageHeader } from '@/components/layout/PageHeader';
import { timeAgo, formatNumber } from '@/lib/format';
import type { MLTrainResult, MLModelRecord, ChartData } from '@/lib/types';

const TASKS = [
  { id: 'auto', label: 'Auto (infer from data)' },
  { id: 'regression', label: 'Regression' },
  { id: 'classification', label: 'Classification' },
  { id: 'clustering', label: 'Clustering (unsupervised)' },
  { id: 'anomaly_detection', label: 'Anomaly detection' },
];

function metricLabel(key: string) {
  const map: Record<string, string> = { r2: 'R²', mae: 'MAE', rmse: 'RMSE', mse: 'MSE', accuracy: 'Accuracy', f1: 'F1' };
  return map[key] ?? key;
}

export default function ML() {
  const [datasetId, setDatasetId] = useState('');
  const [target, setTarget] = useState('');
  const [task, setTask] = useState('auto');
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<MLTrainResult | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const qc = useQueryClient();

  const { data: datasets } = useQuery({ queryKey: ['datasets'], queryFn: () => features.datasets.list() });
  const { data: prof } = useQuery({ queryKey: ['profile', datasetId], queryFn: () => features.datasets.profile(datasetId), enabled: !!datasetId });
  const numeric = (prof?.profile.columns ?? []).filter((c) => c.numeric).map((c) => c.name);
  const { data: models } = useQuery({ queryKey: ['ml-models'], queryFn: () => features.ml.models() });

  const impChart: ChartData | null = result && result.feature_importance.length
    ? { labels: result.feature_importance.map((f) => f.feature), values: result.feature_importance.map((f) => f.importance), x_column: 'feature', y_column: 'importance' } as ChartData
    : null;

  const train = async () => {
    if (!target) return;
    setBusy(true);
    setResult(null);
    try {
      const res = await features.ml.train(datasetId, target, { task: task !== 'auto' ? task : undefined, features: selectedFeatures.length ? selectedFeatures : undefined, test_size: 0.2 });
      setResult(res);
      qc.invalidateQueries({ queryKey: ['ml-models'] });
      toast('Training complete', `Best: ${res.best_model} · ${formatNumber(res.best_metric)}.`, 'success');
    } catch (e) {
      toast('Training failed', e instanceof Error ? e.message : 'Could not train.', 'error');
    } finally {
      setBusy(false);
    }
  };

  const deleteModel = async (m: MLModelRecord) => {
    try {
      await api<void>(`/api/ml/models/${m.id}`, { method: 'DELETE' });
      qc.invalidateQueries({ queryKey: ['ml-models'] });
      toast('Model deleted', undefined, 'success');
    } catch {
      toast('Delete failed', undefined, 'error');
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Machine Learning" description="Train AutoML models on your datasets, compare algorithms, and inspect feature importance." />

      <Card className="space-y-4 p-4">
        <div className="grid gap-3 lg:grid-cols-3">
          <Field label="Dataset">
            <Select value={datasetId} onChange={(e) => { setDatasetId(e.target.value); setTarget(''); setResult(null); }}>
              <option value="">— select —</option>
              {(datasets ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </Select>
          </Field>
          <Field label="Target column (numeric)">
            <Select value={target} onChange={(e) => setTarget(e.target.value)} disabled={!datasetId}>
              <option value="">—</option>
              {numeric.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
          </Field>
          <Field label="Task">
            <Select value={task} onChange={(e) => setTask(e.target.value)}>
              {TASKS.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
            </Select>
          </Field>
        </div>
        <div>
          <div className="mb-2 text-[11px] font-medium text-muted-foreground">
            Features — {selectedFeatures.length ? `${selectedFeatures.length} selected` : 'all numeric auto-selected'}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {numeric.filter((c) => c !== target).map((c) => (
              <button key={c} onClick={() => setSelectedFeatures((s) => (s.includes(c) ? s.filter((x) => x !== c) : [...s, c]))}
                className={cn('rounded-lg px-2 py-1 text-[11px] font-medium transition', selectedFeatures.includes(c) ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground')}>
                {c}
              </button>
            ))}
          </div>
        </div>
        <Button onClick={train} loading={busy} disabled={!target}><Play className="h-3.5 w-3.5" /> Train models</Button>
      </Card>

      {result && (
        <Card className="space-y-4 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1.5 text-xs font-semibold"><Cpu className="h-4 w-4 text-primary" /> Result</span>
            <Badge tone="green">Best: {result.best_model} · {metricLabel('r2' in result.best_metrics ? 'r2' : Object.keys(result.best_metrics)[0] ?? 'metric')} {formatNumber(result.best_metric)}</Badge>
            <Badge tone="blue">n={result.sample_size} · {result.task}</Badge>
          </div>
          <div className="space-y-2">
            {result.models.map((m) => (
              <div key={m.algorithm} className="rounded-xl border border-border p-3">
                <button className="flex w-full items-center justify-between" onClick={() => setExpanded(expanded === m.algorithm ? null : m.algorithm)}>
                  <span className="flex items-center gap-2 text-sm font-semibold">
                    {m.algorithm}
                    {m.algorithm === result.best_model && <Badge tone="green">best</Badge>}
                    {expanded === m.algorithm ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  </span>
                  <span className="flex flex-wrap gap-1.5">
                    {Object.entries(m.metrics).filter(([k]) => ['r2', 'accuracy', 'f1', 'mae', 'rmse', 'mse'].includes(k)).map(([k, v]) => (
                      <Badge key={k} tone="blue">{metricLabel(k)} <span className="ml-1 font-mono">{typeof v === 'number' ? formatNumber(v) : ''}</span></Badge>
                    ))}
                  </span>
                </button>
                {expanded === m.algorithm && (
                  <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-muted-foreground md:grid-cols-4">
                    {Object.entries(m.metrics).map(([k, v]) => (
                      <div key={k} className="rounded-lg bg-muted/50 px-2.5 py-1.5">
                        <span className="opacity-70">{metricLabel(k)}</span>
                        <div className="font-mono text-xs text-foreground">{typeof v === 'number' ? formatNumber(v) : String(v)}</div>
                      </div>
                    ))}
                    <div className="rounded-lg bg-muted/50 px-2.5 py-1.5"><span className="opacity-70">time</span><div className="font-mono text-xs text-foreground">{(m.duration_ms / 1000).toFixed(1)}s</div></div>
                  </div>
                )}
              </div>
            ))}
          </div>
          {impChart && (
            <div>
              <div className="mb-2 text-[11px] font-medium text-muted-foreground">Feature importance</div>
              <div className="h-64"><ChartView chartType="column" data={impChart} /></div>
            </div>
          )}
        </Card>
      )}

      <div className="space-y-2">
        <div className="text-sm font-semibold">Saved models</div>
        {(models ?? []).length === 0 && (
          <EmptyState icon={<Cpu className="h-5 w-5" />} title="No trained models yet" description="Train a model above and it will be listed here for reuse." />
        )}
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {(models ?? []).map((m) => (
            <Card key={m.id} className="p-3">
              <div className="flex items-start justify-between">
                <div className="min-w-0">
                  <div className="truncate text-xs font-semibold">{m.name}</div>
                  <div className="mt-0.5 text-[10px] text-muted-foreground">Target: {m.target} · {timeAgo(m.created_at)}</div>
                </div>
                <button onClick={() => deleteModel(m)} className="text-muted-foreground/50 transition hover:text-destructive"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                <Badge tone="purple">{m.task}</Badge>
                {Object.entries(m.metrics).filter(([k]) => ['r2', 'accuracy', 'f1'].includes(k)).map(([k, v]) => (
                  <Badge key={k} tone="muted">{metricLabel(k)} {typeof v === 'number' ? formatNumber(v) : ''}</Badge>
                ))}
              </div>
              <Link to={`/stats?dataset=${m.dataset_id}`} className="mt-2 inline-block text-[10px] font-medium text-primary hover:underline">Analyze dataset →</Link>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}