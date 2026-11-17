import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { BrainCircuit, Play, Cpu, ChevronDown, ChevronUp } from 'lucide-react';
import { features } from '@/lib/features';
import { api } from '@/lib/api';
import { Card, Button, Select, Field, Badge, cn } from '@/components/ui';
import { toast } from '@/components/ui';
import { formatNumber } from '@/lib/format';
import type { MLTrainResult, MLModelRecord } from '@/lib/types';

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

function MetricBadge({ m }: { m: Record<string, unknown> }) {
  const bits = Object.entries(m).filter(([k]) => ['r2', 'accuracy', 'f1', 'mae', 'rmse', 'mse'].includes(k));
  return (
    <div className="flex flex-wrap gap-1.5">
      {bits.map(([k, v]) => (
        <Badge key={k} tone="blue">
          {metricLabel(k)} <span className="ml-1 font-mono">{typeof v === 'number' ? formatNumber(v) : ''}</span>
        </Badge>
      ))}
    </div>
  );
}

export function MLPanel({ datasetId }: { datasetId: string }) {
  const [target, setTarget] = useState('');
  const [task, setTask] = useState('auto');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<MLTrainResult | null>(null);
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);
  const qc = useQueryClient();

  const { data: prof } = useQuery({ queryKey: ['profile', datasetId], queryFn: () => features.datasets.profile(datasetId) });
  const numeric = (prof?.profile.columns ?? []).filter((c) => c.numeric).map((c) => c.name);
  const { data: models } = useQuery({ queryKey: ['ml-models', datasetId], queryFn: () => features.ml.models() });

  const featuresList = selectedFeatures.length ? selectedFeatures : undefined;
  const toggleFeature = (c: string) =>
    setSelectedFeatures((s) => (s.includes(c) ? s.filter((x) => x !== c) : [...s, c]));

  const train = async () => {
    if (!target) return;
    setBusy(true);
    setResult(null);
    try {
      const res = await features.ml.train(datasetId, target, {
        task: task !== 'auto' ? task : undefined,
        features: featuresList,
        test_size: 0.2,
      });
      setResult(res);
      qc.invalidateQueries({ queryKey: ['ml-models'] });
      toast('Training complete', `Best model: ${res.best_model} (${metricLabel('r2' in res.best_metrics ? 'r2' : Object.keys(res.best_metrics)[0] ?? '')} ${formatNumber(res.best_metric)}).`, 'success');
    } catch (e) {
      toast('Training failed', e instanceof Error ? e.message : 'Could not train model.', 'error');
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
      <Card className="space-y-4 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs font-semibold"><Cpu className="h-4 w-4 text-primary" /> Model training</div>
          <Badge tone="purple">AutoML</Badge>
        </div>

        <div className="grid gap-3 lg:grid-cols-[280px_1fr]">
          <div className="space-y-3">
            <Field label="Target column" hint="What to predict (numeric)">
              <Select value={target} onChange={(e) => setTarget(e.target.value)}>
                <option value="">— select —</option>
                {numeric.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </Field>
            <Field label="Task">
              <Select value={task} onChange={(e) => setTask(e.target.value)}>
                {TASKS.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              </Select>
            </Field>
            <Button className="w-full" onClick={train} loading={busy} disabled={!target}>
              <Play className="h-3.5 w-3.5" /> Train models
            </Button>
          </div>

          <div>
            <div className="mb-2 text-[11px] font-medium text-muted-foreground">
              Features — {selectedFeatures.length ? `${selectedFeatures.length} selected` : 'all numeric auto-selected'}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {numeric.filter((c) => c !== target).map((c) => (
                <button key={c} onClick={() => toggleFeature(c)}
                  className={cn('rounded-lg px-2 py-1 text-[11px] font-medium transition', selectedFeatures.includes(c) ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground')}>
                  {c}
                </button>
              ))}
              {!numeric.filter((c) => c !== target).length && <span className="text-[11px] text-muted-foreground">No numeric features to predict with.</span>}
            </div>
          </div>
        </div>
      </Card>

      {result && (
        <Card className="space-y-4 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs font-semibold"><BrainCircuit className="h-4 w-4 text-primary" /> Training results</div>
            <div className="flex gap-1.5">
              <Badge tone="green">Best: {result.best_model}</Badge>
              <Badge tone="blue">n={result.sample_size} · train {result.train_size} / test {result.test_size}</Badge>
            </div>
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
                  <MetricBadge m={m.metrics} />
                </button>
                {expanded === m.algorithm && (
                  <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-muted-foreground md:grid-cols-4">
                    {Object.entries(m.metrics).map(([k, v]) => (
                      <div key={k} className="rounded-lg bg-muted/50 px-2.5 py-1.5">
                        <span className="opacity-70">{metricLabel(k)}</span>
                        <div className="font-mono text-xs text-foreground">{typeof v === 'number' ? formatNumber(v) : String(v)}</div>
                      </div>
                    ))}
                    <div className="rounded-lg bg-muted/50 px-2.5 py-1.5">
                      <span className="opacity-70">time</span>
                      <div className="font-mono text-xs text-foreground">{(m.duration_ms / 1000).toFixed(1)}s</div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {result.feature_importance.length > 0 && (
            <div>
              <div className="mb-2 text-[11px] font-medium text-muted-foreground">Feature importance</div>
              <div className="space-y-1.5">
                {result.feature_importance.map((f) => (
                  <div key={f.feature} className="flex items-center gap-2 text-xs">
                    <span className="w-36 truncate text-muted-foreground">{f.feature}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full bg-gradient-to-r from-chart-blue to-chart-purple" style={{ width: `${f.normalized * 100}%` }} />
                    </div>
                    <span className="w-12 text-right font-mono tabular-nums">{f.normalized.toFixed(3)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {(models ?? []).filter((m) => m.dataset_id === datasetId).length > 0 && (
        <Card className="p-4">
          <div className="mb-2 text-xs font-semibold">Saved models</div>
          <div className="space-y-2">
            {(models ?? []).filter((m) => m.dataset_id === datasetId).map((m) => (
              <div key={m.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-xs">
                <span className="font-medium">{m.name}</span>
                <span className="flex items-center gap-2">
                  <Badge tone="blue">{m.task}</Badge>
                  <span className="text-muted-foreground">Target: {m.target}</span>
                  <button className="text-muted-foreground hover:text-destructive" onClick={() => deleteModel(m)}>Delete</button>
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}