import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Play, Trash2, Plus, Save, Type, Code2, Loader2, ArrowLeft } from 'lucide-react';
import { features } from '@/lib/features';
import type { NotebookCell, NotebookRunOutput } from '@/lib/types';
import { toast } from '@/components/ui/toast';
import { Button, Card, EmptyState, Select, Spinner } from '@/components/ui';

function CellOutput({ output }: { output: NotebookRunOutput }) {
  const { error, stdout, figures, df_preview, vars } = output;
  return (
    <div className="mt-2 space-y-2">
      {error && <div className="rounded-xl bg-destructive/10 p-3 font-mono text-xs text-destructive">{error}</div>}
      {stdout && <pre className="whitespace-pre rounded-xl bg-muted/40 p-3 font-mono text-[11px]">{stdout}</pre>}
      {figures?.map((fig, i) => <img key={i} src={fig} className="max-h-80 rounded-xl" alt={`Figure ${i + 1}`} />)}
      {df_preview && (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                {df_preview.columns.map((c) => (
                  <th key={c} className="px-2 py-1.5 text-left font-medium text-muted-foreground">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {df_preview.rows.slice(0, 50).map((row, ri) => (
                <tr key={ri} className="hover:bg-muted/30">
                  {row.map((cell, ci) => <td key={ci} className="px-2 py-1 font-mono">{String(cell ?? '')}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
          {df_preview.rows.length > 50 && (
            <div className="px-2 py-1 text-[10px] text-muted-foreground">Showing 50 of {df_preview.rows.length} rows</div>
          )}
        </div>
      )}
      {vars?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {vars.map((v) => (
            <span key={v.name} className="rounded-md bg-muted px-2 py-0.5 font-mono text-[10px] text-muted-foreground">{v.name}: {v.type}</span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function NotebookView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: notebook, isLoading } = useQuery({ queryKey: ['notebook', id], queryFn: () => features.notebooks.get(id!), enabled: !!id });
  const { data: datasets } = useQuery({ queryKey: ['datasets'], queryFn: () => features.datasets.list() });
  const [cells, setCells] = useState<NotebookCell[]>([]);
  const [dirty, setDirty] = useState(false);
  const [outputs, setOutputs] = useState<Record<number, NotebookRunOutput>>({});
  const [running, setRunning] = useState<Record<number, boolean>>({});
  const [selectedDataset, setSelectedDataset] = useState('');
  const [editingMd, setEditingMd] = useState<Record<number, boolean>>({});
  const [mdDraft, setMdDraft] = useState<Record<number, string>>({});

  useEffect(() => {
    if (notebook) { setCells(notebook.cells.map((c) => ({ type: c.type, content: c.content }))); setDirty(false); }
  }, [notebook?.id]);

  const updateCell = useCallback((idx: number, content: string) => {
    setCells((p) => p.map((c, i) => (i === idx ? { ...c, content } : c)));
    setDirty(true);
  }, []);

  const handleSave = async () => {
    if (!id) return;
    try { await features.notebooks.update(id, { cells }); setDirty(false); toast('Saved', undefined, 'success'); }
    catch { toast('Failed to save', undefined, 'error'); }
  };

  const handleRun = async (idx: number) => {
    const cell = cells[idx];
    if (cell.type !== 'code' || !id || !selectedDataset) return;
    setRunning((p) => ({ ...p, [idx]: true }));
    try {
      const output = await features.notebooks.run(id, cell.content, selectedDataset);
      setOutputs((p) => ({ ...p, [idx]: output }));
    } catch {
      setOutputs((p) => ({ ...p, [idx]: { stdout: '', figures: [], df_preview: null, vars: [], error: 'Execution failed' } }));
    } finally { setRunning((p) => ({ ...p, [idx]: false })); }
  };

  const addCell = (type: 'code' | 'markdown') => { setCells((p) => [...p, { type, content: '' }]); setDirty(true); };
  const removeCell = (idx: number) => {
    setCells((p) => p.filter((_, i) => i !== idx));
    setOutputs((p) => { const n = { ...p }; delete n[idx]; return n; });
    setDirty(true);
  };

  const datasetList = (datasets ?? []) as { id: string; name: string }[];

  if (isLoading) return <div className="flex items-center justify-center py-20"><Spinner className="h-5 w-5" /></div>;
  if (!notebook) return (
    <div className="p-6"><EmptyState icon={<Code2 className="h-8 w-8" />} title="Notebook not found"
      action={<Button onClick={() => navigate('/notebooks')}>Back to notebooks</Button>} /></div>
  );

  const CellActions = ({ idx, type }: { idx: number; type: string }) => (
    <div className="ml-auto flex items-center gap-1">
      {type === 'code' && (
        <Button variant="ghost" size="xs"
          leftIcon={running[idx] ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
          onClick={() => handleRun(idx)} disabled={running[idx] || !selectedDataset}>Run</Button>
      )}
      <Button variant="ghost" size="xs" onClick={() => removeCell(idx)}><Trash2 className="h-3 w-3" /></Button>
    </div>
  );

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b border-border px-6 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="ghost" size="sm" leftIcon={<ArrowLeft className="h-3.5 w-3.5" />} onClick={() => navigate('/notebooks')}>Notebooks</Button>
          <div className="h-4 w-px bg-border" />
          <h1 className="text-sm font-semibold">{notebook.name}</h1>
          <div className="ml-auto flex items-center gap-2">
            <Select value={selectedDataset} onChange={(e) => setSelectedDataset(e.target.value)} className="w-48 text-xs">
              <option value="">Select dataset…</option>
              {datasetList.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </Select>
            <Button variant="secondary" size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => addCell('code')}>Code</Button>
            <Button variant="secondary" size="sm" leftIcon={<Type className="h-3.5 w-3.5" />} onClick={() => addCell('markdown')}>Markdown</Button>
            <Button size="sm" leftIcon={<Save className="h-3.5 w-3.5" />} onClick={handleSave} disabled={!dirty}>Save</Button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {cells.length === 0 ? (
          <EmptyState icon={<Code2 className="h-8 w-8" />} title="Empty notebook" description="Add a code or markdown cell to get started." />
        ) : (
          <div className="mx-auto max-w-4xl space-y-3">
            {cells.map((cell, idx) => (
              <Card key={idx} className="overflow-hidden">
                <div className="flex items-center gap-2 border-b border-border bg-muted/30 px-3 py-1.5">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-muted text-[10px] font-bold text-muted-foreground">{idx + 1}</span>
                  <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">{cell.type}</span>
                  <CellActions idx={idx} type={cell.type} />
                </div>
                <div className="p-3">
                  {cell.type === 'code' ? (
                    <textarea value={cell.content} onChange={(e) => updateCell(idx, e.target.value)}
                      rows={Math.min(20, Math.max(3, cell.content.split('\n').length))}
                      className="w-full resize-none rounded-xl bg-muted/60 p-3 font-mono text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                      spellCheck={false} />
                  ) : editingMd[idx] ? (
                    <div className="space-y-2">
                      <textarea value={mdDraft[idx] ?? cell.content}
                        onChange={(e) => setMdDraft((p) => ({ ...p, [idx]: e.target.value }))}
                        rows={Math.min(20, Math.max(3, (mdDraft[idx] ?? cell.content).split('\n').length))}
                        className="w-full resize-none rounded-xl border border-border bg-card p-3 font-mono text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                        spellCheck={false} />
                      <div className="flex gap-1.5">
                        <Button size="xs" onClick={() => { updateCell(idx, mdDraft[idx] ?? cell.content); setEditingMd((p) => ({ ...p, [idx]: false })); }}>Apply</Button>
                        <Button variant="ghost" size="xs" onClick={() => { setEditingMd((p) => ({ ...p, [idx]: false })); delete mdDraft[idx]; }}>Cancel</Button>
                      </div>
                    </div>
                  ) : (
                    <div className="cursor-pointer whitespace-pre-wrap rounded-xl bg-muted/30 p-3 text-sm leading-relaxed text-foreground/80 hover:bg-muted/50"
                      onClick={() => { setEditingMd((p) => ({ ...p, [idx]: true })); setMdDraft((p) => ({ ...p, [idx]: cell.content })); }}>
                      {cell.content || <span className="italic text-muted-foreground">Click to edit…</span>}
                    </div>
                  )}
                </div>
                {cell.type === 'code' && outputs[idx] && (
                  <div className="border-t border-border px-3 pb-3 pt-2"><CellOutput output={outputs[idx]} /></div>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
