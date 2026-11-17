import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Workflow, Play, Plus, Trash2, GripVertical } from 'lucide-react';
import { features } from '@/lib/features';
import { Card, Button, Select, Field, Input, Badge } from '@/components/ui';
import { toast } from '@/components/ui';
import { DataTable } from '@/components/dataset/DataTable';
import type { TransformResponse } from '@/lib/features';
import type { ProfileColumn } from '@/lib/types';

type Step = { id: string; op: string; params: Record<string, unknown> };

const STEPS: { op: string; label: string }[] = [
  { op: 'select', label: 'Select columns' },
  { op: 'filter', label: 'Filter rows' },
  { op: 'rename', label: 'Rename' },
  { op: 'calculate', label: 'Calculate' },
  { op: 'aggregate', label: 'Aggregate' },
  { op: 'sort', label: 'Sort' },
  { op: 'normalize', label: 'Normalize' },
  { op: 'encode', label: 'Encode' },
  { op: 'sample', label: 'Sample' },
  { op: 'dropna', label: 'Drop nulls' },
  { op: 'fillna', label: 'Fill nulls' },
  { op: 'slice', label: 'Slice rows' },
];

let stepSeq = 1;

function StepEditor({ step, cols, onPatch }: { step: Step; cols: string[]; onPatch: (params: Record<string, unknown>) => void }) {
  const p = step.params;
  const rules = [
    ['eq', 'equals'], ['neq', 'not equals'], ['gt', '>'], ['gte', '≥'], ['lt', '<'], ['lte', '≤'],
    ['contains', 'contains'], ['startswith', 'starts with'], ['endswith', 'ends with'], ['notnull', 'not null'], ['isnull', 'is null'],
  ];

  switch (step.op) {
    case 'select':
      return (
        <Field label="Columns to keep">
          <Select value={String((p.columns as string[] ?? [])[0] ?? '')} onChange={(e) => onPatch({ columns: [e.target.value] })}>
            <option value="">—</option>
            {cols.map((c) => <option key={c} value={c}>{c}</option>)}
          </Select>
        </Field>
      );
    case 'filter':
      return (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <Field label="Column">
              <Select value={String(p.column ?? '')} onChange={(e) => onPatch({ ...p, column: e.target.value })}>
                <option value="">—</option>
                {cols.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </Field>
            <Field label="Rule">
              <Select value={String(p.rule ?? 'eq')} onChange={(e) => onPatch({ ...p, rule: e.target.value })}>
                {rules.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </Select>
            </Field>
          </div>
          {!['notnull', 'isnull'].includes(String(p.rule)) && (
            <Field label="Value">
              <Input value={String(p.value ?? '')} onChange={(e) => onPatch({ ...p, value: e.target.value })} />
            </Field>
          )}
        </div>
      );
    case 'rename':
      return (
        <div className="grid grid-cols-2 gap-2">
          <Field label="From">
            <Select value={String(p.from ?? '')} onChange={(e) => onPatch({ mapping: { ...(p.mapping ?? {}), [e.target.value]: String(p.to ?? '') }, from: e.target.value })}>
              <option value="">—</option>
              {cols.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
          </Field>
          <Field label="To">
            <Input value={String(p.to ?? '')} onChange={(e) => onPatch({ ...p, to: e.target.value, mapping: { ...(p.mapping ?? {}), [String(p.from ?? '')]: e.target.value } })} />
          </Field>
        </div>
      );
    case 'calculate':
      return (
        <div className="space-y-2">
          <Field label="New column name">
            <Input value={String(p.column ?? 'calculated')} onChange={(e) => onPatch({ ...p, column: e.target.value || 'calculated' })} />
          </Field>
          <Field label="Expression" hint="e.g. revenue - cost  ·  use column names directly">
            <Input value={String(p.expression ?? '')} onChange={(e) => onPatch({ ...p, expression: e.target.value })} />
          </Field>
        </div>
      );
    case 'aggregate':
      return (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <Field label="Group by">
              <Select value={String((p.group_by as string[] ?? [])[0] ?? '')} onChange={(e) => onPatch({ ...p, group_by: [e.target.value] })}>
                <option value="">—</option>
                {cols.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </Field>
            <Field label="Aggregate column">
              <Select value={String(p.aggregate ?? '')} onChange={(e) => onPatch({ ...p, aggregate: e.target.value })}>
                <option value="">—</option>
                {cols.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </Field>
          </div>
          <Field label="Function">
            <Select value={String(p.func ?? 'sum')} onChange={(e) => onPatch({ ...p, func: e.target.value })}>
              {['sum', 'mean', 'median', 'min', 'max', 'count', 'nunique', 'std', 'first'].map((f) => <option key={f} value={f}>{f}</option>)}
            </Select>
          </Field>
        </div>
      );
    case 'sort':
      return (
        <div className="grid grid-cols-2 gap-2">
          <Field label="Column">
            <Select value={String((p.by as string[] ?? [])[0] ?? '')} onChange={(e) => onPatch({ by: [e.target.value], ascending: p.ascending ?? true })}>
              <option value="">—</option>
              {cols.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
          </Field>
          <Field label="Direction">
            <Select value={String(p.ascending ?? true)} onChange={(e) => onPatch({ ...p, ascending: e.target.value === 'true' })}>
              <option value="true">Ascending</option>
              <option value="false">Descending</option>
            </Select>
          </Field>
        </div>
      );
    case 'normalize':
      return (
        <div className="space-y-2">
          <Field label="Column(s) — comma separated">
            <Input value={String((p.columns as string[] ?? []).join(', '))} onChange={(e) => onPatch({ ...p, columns: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} />
          </Field>
          <Field label="Method">
            <Select value={String(p.method ?? 'minmax')} onChange={(e) => onPatch({ ...p, method: e.target.value })}>
              {['minmax', 'zscore', 'log', 'rank'].map((m) => <option key={m} value={m}>{m}</option>)}
            </Select>
          </Field>
        </div>
      );
    case 'encode':
      return (
        <Field label="Column(s) — comma separated">
          <Input value={String((p.columns as string[] ?? []).join(', '))} onChange={(e) => onPatch({ ...p, columns: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} />
        </Field>
      );
    case 'sample':
      return (
        <div className="grid grid-cols-2 gap-2">
          <Field label="Rows (n)">
            <Input type="number" value={String(p.n ?? 1000)} onChange={(e) => onPatch({ ...p, n: Number(e.target.value) || 1000 })} />
          </Field>
          <Field label="Fraction (optional)">
            <Input type="number" step="0.05" placeholder="0.5" value={p.frac === undefined ? '' : String(p.frac)} onChange={(e) => onPatch({ ...p, frac: e.target.value ? Number(e.target.value) : undefined })} />
          </Field>
        </div>
      );
    case 'dropna':
      return <p className="text-[11px] text-muted-foreground">Drops any row containing a missing value.</p>;
    case 'fillna':
      return (
        <Field label="Fill value">
          <Input value={String(p.value ?? '')} onChange={(e) => onPatch({ ...p, value: e.target.value })} />
        </Field>
      );
    case 'slice':
      return (
        <div className="grid grid-cols-2 gap-2">
          <Field label="Start">
            <Input type="number" value={String(p.start ?? 0)} onChange={(e) => onPatch({ ...p, start: Number(e.target.value) || 0 })} />
          </Field>
          <Field label="End">
            <Input type="number" placeholder="end" value={p.end === undefined ? '' : String(p.end)} onChange={(e) => onPatch({ ...p, end: e.target.value ? Number(e.target.value) : undefined })} />
          </Field>
        </div>
      );
    default:
      return null;
  }
}

export function TransformPanel({ datasetId }: { datasetId: string }) {
  const [steps, setSteps] = useState<Step[]>([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TransformResponse | null>(null);
  const qc = useQueryClient();
  const { data: prof } = useQuery({ queryKey: ['profile', datasetId], queryFn: () => features.datasets.profile(datasetId) });
  const cols = (prof?.profile.columns ?? []).map((c: ProfileColumn) => c.name);

  const add = (op: string) => setSteps((s) => [...s, { id: `s${stepSeq++}`, op, params: {} }]);
  const patch = (id: string, params: Record<string, unknown>) =>
    setSteps((s) => s.map((st) => (st.id === id ? { ...st, params } : st)));

  const canRun = steps.length > 0;
  const apply = async () => {
    setBusy(true);
    try {
      const res = await features.datasets.transform(datasetId, steps.map(({ op, params }) => ({ op, params })), 'Pipeline run');
      qc.invalidateQueries({ queryKey: ['datasets'] });
      setResult(res);
      toast('Transformed', `${steps.length} step(s) applied.`, 'success');
    } catch (e) {
      toast('Transform failed', e instanceof Error ? e.message : 'Could not apply pipeline.', 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs font-semibold"><Workflow className="h-4 w-4 text-primary" /> Transformation pipeline</div>
          <div className="flex flex-wrap gap-1">
            {STEPS.map((s) => (
              <button key={s.op} onClick={() => add(s.op)} className="flex items-center gap-1 rounded-lg bg-muted px-2.5 py-1.5 text-[11px] font-medium text-muted-foreground transition hover:text-foreground">
                <Plus className="h-3 w-3" /> {s.label}
              </button>
            ))}
          </div>
        </div>

        {!steps.length && (
          <div className="flex flex-col items-center gap-1 py-8 text-xs text-muted-foreground">
            Add steps to build a pipeline — select, filter, calculate, aggregate…
          </div>
        )}

        <div className="space-y-2">
          {steps.map((step, i) => (
            <div key={step.id} className="flex gap-2 rounded-xl border border-border bg-muted/30 p-3">
              <div className="flex items-center gap-1.5 pt-2.5">
                <GripVertical className="h-3.5 w-3.5 text-muted-foreground/40" />
                <span className="text-[10px] font-mono text-muted-foreground/60">{i + 1}</span>
              </div>
              <div className="min-w-0 flex-1">
                <div className="mb-2 flex items-center justify-between">
                  <Badge tone="purple">{STEPS.find((s) => s.op === step.op)?.label ?? step.op}</Badge>
                  <button className="text-muted-foreground hover:text-destructive" onClick={() => setSteps((s) => s.filter((x) => x.id !== step.id))}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
                <StepEditor step={step} cols={cols} onPatch={(params) => patch(step.id, params)} />
              </div>
            </div>
          ))}
        </div>

        {steps.length > 0 && (
          <div className="mt-3 flex items-center justify-between border-t border-border/60 pt-3">
            <span className="text-[11px] text-muted-foreground">{steps.length} step(s) · run creates a new version</span>
            <Button onClick={apply} loading={busy} disabled={!canRun}><Play className="h-3.5 w-3.5" /> Run pipeline</Button>
          </div>
        )}
      </Card>

      {result && (
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-semibold">Result — {result.dataset.name} v{result.dataset.version}</span>
            <Badge tone="green">{result.dataset.row_count} rows</Badge>
          </div>
          <DataTable data={result.preview} height={340} />
        </Card>
      )}
    </div>
  );
}