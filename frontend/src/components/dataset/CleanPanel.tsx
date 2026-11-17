import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Wand2, Play, Plus } from 'lucide-react';
import { features } from '@/lib/features';
import { Card, Button, Select, Field, Badge, cn } from '@/components/ui';
import { toast } from '@/components/ui';
import { DataTable } from '@/components/dataset/DataTable';
import type { CleanResponse } from '@/lib/features';

const OPS: { op: string; label: string; desc: string; needs: 'column' | 'none' | 'subset'; params: { key: string; label: string; kind: 'text' | 'select'; options?: string[] }[] }[] = [
  { op: 'remove_duplicates', label: 'Remove duplicates', desc: 'Drop duplicate rows', needs: 'none', params: [] },
  { op: 'drop_missing', label: 'Drop missing rows', desc: 'Remove rows with nulls', needs: 'column', params: [] },
  { op: 'fill_missing', label: 'Fill missing values', desc: 'Replace nulls', needs: 'column', params: [{ key: 'method', label: 'Method', kind: 'select', options: ['constant', 'mean', 'median', 'mode'] }, { key: 'value', label: 'Value', kind: 'text' }] },
  { op: 'trim', label: 'Trim whitespace', desc: 'Strip spaces', needs: 'column', params: [] },
  { op: 'lowercase', label: 'Lowercase', desc: 'Convert to lowercase', needs: 'column', params: [] },
  { op: 'uppercase', label: 'Uppercase', desc: 'Convert to uppercase', needs: 'column', params: [] },
  { op: 'titlecase', label: 'Title case', desc: 'Capitalize words', needs: 'column', params: [] },
  { op: 'replace_values', label: 'Replace values', desc: 'Swap occurrences', needs: 'column', params: [{ key: 'from', label: 'From', kind: 'text' }, { key: 'to', label: 'To', kind: 'text' }] },
  { op: 'regex_replace', label: 'Regex replace', desc: 'Pattern substitution', needs: 'column', params: [{ key: 'pattern', label: 'Pattern', kind: 'text' }, { key: 'replacement', label: 'Replacement', kind: 'text' }] },
  { op: 'parse_dates', label: 'Parse dates', desc: 'Convert to datetime', needs: 'column', params: [] },
  { op: 'fix_dtype', label: 'Fix data types', desc: 'Auto-convert types', needs: 'column', params: [] },
  { op: 'detect_outliers', label: 'Detect outliers', desc: 'Flag outliers (IQR)', needs: 'column', params: [] },
  { op: 'remove_outliers', label: 'Remove outliers', desc: 'Drop outlier rows (IQR)', needs: 'column', params: [] },
  { op: 'winsorize', label: 'Winsorize', desc: 'Cap extreme values', needs: 'column', params: [{ key: 'limits', label: 'Limits (e.g. 0.05)', kind: 'text' }] },
  { op: 'clip', label: 'Clip values', desc: 'Clamp to range', needs: 'column', params: [{ key: 'min', label: 'Min', kind: 'text' }, { key: 'max', label: 'Max', kind: 'text' }] },
  { op: 'drop_column', label: 'Drop column', desc: 'Remove a column', needs: 'column', params: [] },
];

export function CleanPanel({ datasetId }: { datasetId: string }) {
  const [op, setOp] = useState<string>('remove_duplicates');
  const [columns, setColumns] = useState<string[]>([]);
  const [params, setParams] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<CleanResponse | null>(null);
  const qc = useQueryClient();
  const selected = OPS.find((o) => o.op === op)!;

  const { data: prof } = useQuery({ queryKey: ['profile', datasetId], queryFn: () => features.datasets.profile(datasetId) });
  const cols = (prof?.profile.columns ?? []).map((c) => c.name);

  const apply = async () => {
    const opParams: Record<string, unknown> = { columns };
    for (const p of selected.params) {
      if (params[p.key] !== undefined && params[p.key] !== '') opParams[p.key] = params[p.key];
    }
    setBusy(true);
    try {
      const res = await features.datasets.clean(datasetId, [{ op, params: opParams }], `Clean: ${selected.label}`);
      qc.invalidateQueries({ queryKey: ['datasets'] });
      setPreview(res);
      toast('Cleaned', `${selected.label} applied — ${res.quality.score}/100 quality.`, 'success');
    } catch (e) {
      toast('Clean failed', e instanceof Error ? e.message : 'Could not apply operation.', 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <div className="space-y-4">
        <Card className="p-4">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold"><Wand2 className="h-3.5 w-3.5 text-primary" /> Cleaning operation</div>
          <div className="flex flex-wrap gap-1.5">
            {OPS.map((o) => (
              <button key={o.op} onClick={() => setOp(o.op)}
                className={cn('rounded-lg px-2.5 py-1.5 text-[11px] font-medium transition', op === o.op ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground hover:text-foreground')}>
                {o.label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">{selected.desc}</p>
        </Card>

        <Card className="space-y-3 p-4">
          {selected.needs !== 'none' && (
            <Field label="Target column(s)" hint={selected.needs === 'subset' ? 'Leave empty for all columns' : 'Pick at least one'}>
              <Select value={columns[0] ?? ''} onChange={(e) => setColumns([e.target.value])}>
                <option value="">— select —</option>
                {cols.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            </Field>
          )}
          {selected.params.map((p) => (
            <Field key={p.key} label={p.label}>
              {p.kind === 'select' ? (
                <Select value={params[p.key] ?? ''} onChange={(e) => setParams((s) => ({ ...s, [p.key]: e.target.value }))}>
                  {p.options!.map((o) => <option key={o} value={o}>{o}</option>)}
                </Select>
              ) : (
                <input value={params[p.key] ?? ''} onChange={(e) => setParams((s) => ({ ...s, [p.key]: e.target.value }))}
                  placeholder={p.key === 'limits' ? '0.05' : p.label}
                  className="h-9 w-full rounded-lg border border-input bg-card px-3 text-[13px] outline-none focus:border-primary/50" />
              )}
            </Field>
          ))}
          <Button className="w-full" onClick={apply} loading={busy} disabled={selected.needs !== 'none' && !columns.length}>
            <Play className="h-3.5 w-3.5" /> Apply operation
          </Button>
          <div className="flex flex-wrap gap-1.5">
            <Badge tone="blue">New version {preview?.dataset.version ?? 'will be created'}</Badge>
          </div>
        </Card>
      </div>
      <Card className="p-4">
        <div className="mb-3 text-xs font-semibold">Result preview</div>
        {preview ? <DataTable data={preview.preview} height={360} /> : (
          <div className="flex flex-col items-center justify-center gap-2 py-16 text-xs text-muted-foreground">
            <Plus className="h-5 w-5" />
            Run a cleaning operation to see the result here.
          </div>
        )}
      </Card>
    </div>
  );
}