import { useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Database, Upload, Trash2, MoreHorizontal, Star, StarOff, FileUp, FileSpreadsheet, Search } from 'lucide-react';
import { features } from '@/lib/features';
import { useUI } from '@/store/ui';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, Modal, ConfirmDialog, Menu, Select, Field, Button, EmptyState, LoadingBlock, Badge } from '@/components/ui';
import { toast } from '@/components/ui';
import { timeAgo, formatCompact, formatBytes } from '@/lib/format';
import type { ProjectItem, DatasetItem } from '@/lib/types';

function UploadModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [projectId, setProjectId] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { data: projects } = useQuery({ queryKey: ['projects'], queryFn: features.projects.list });
  const qc = useQueryClient();
  const navigate = useNavigate();
  const sel = projectId || useUI.getState().projectId || '';

  const pick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const list = Array.from(e.target.files ?? []);
    setFiles((f) => [...f, ...list]);
    if (e.target) e.target.value = '';
  };

  const upload = async () => {
    if (!files.length || !sel) return;
    setBusy(true);
    let ok = 0;
    for (const f of files) {
      try {
        const res = await features.datasets.upload(f, sel);
        qc.invalidateQueries({ queryKey: ['datasets'] });
        qc.invalidateQueries({ queryKey: ['projects'] });
        toast('Imported', `${res.dataset.name} — ${formatCompact(res.dataset.row_count)} rows.`, 'success');
        ok += 1;
      } catch (e) {
        toast('Import failed', `${f.name}: ${e instanceof Error ? e.message : 'error'}`, 'error');
      }
    }
    setBusy(false);
    setFiles([]);
    if (ok) {
      onClose();
      navigate('/datasets');
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Import data" description="CSV, Excel (.xlsx), JSON, Parquet — up to a few hundred MB locally." size="md"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={upload} loading={busy} disabled={!files.length || !sel}>
            <Upload className="h-3.5 w-3.5" /> Import {files.length > 1 ? `${files.length} files` : ''}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Target project">
          <Select value={sel} onChange={(e) => setProjectId(e.target.value)}>
            <option value="">Select a project…</option>
            {(projects ?? []).map((p: ProjectItem) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </Select>
        </Field>
        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); pick({ target: { files: e.dataTransfer.files, value: '' } } as React.ChangeEvent<HTMLInputElement>); }}
          className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-border py-10 text-center transition hover:border-primary/50 hover:bg-muted/40"
        >
          <input ref={inputRef} type="file" multiple accept=".csv,.tsv,.txt,.xlsx,.xls,.json,.parquet,.arrow" hidden onChange={pick} />
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary"><FileUp className="h-6 w-6" /></div>
          <div className="text-[13px] font-semibold">Drop files here or click to browse</div>
          <div className="text-[11px] text-muted-foreground">The first row is used as column headers.</div>
        </div>
        {files.length > 0 && (
          <div className="space-y-1.5">
            {files.map((f) => (
              <div key={f.name} className="flex items-center gap-2.5 rounded-xl border border-border px-3 py-2">
                <FileSpreadsheet className="h-4 w-4 text-chart-green" />
                <span className="min-w-0 flex-1 truncate text-xs">{f.name}</span>
                <span className="text-[10px] text-muted-foreground">{formatBytes(f.size)}</span>
                <button onClick={() => setFiles((x) => x.filter((y) => y.name !== f.name))} className="text-muted-foreground hover:text-destructive">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
}

export default function Datasets() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DatasetItem | null>(null);
  const [query, setQuery] = useState('');
  const { projectId } = useUI();

  const { data, isLoading } = useQuery({ queryKey: ['datasets'], queryFn: features.datasets.list });

  const datasets = useMemo(() => {
    const list = ((data ?? []) as DatasetItem[]).filter((d) => (projectId ? d.project_id === projectId : true));
    const q = query.trim().toLowerCase();
    const filtered = q ? list.filter((d) => d.name.toLowerCase().includes(q) || (d.tags ?? []).some((t) => t.includes(q))) : list;
    return [...filtered].sort((a, b) => Number(b.is_favorite) - Number(a.is_favorite) || b.updated_at.localeCompare(a.updated_at));
  }, [data, projectId, query]);

  const toggleFavorite = async (d: DatasetItem) => {
    const next = await features.datasets.update(d.id, { is_favorite: !d.is_favorite });
    qc.setQueryData(['datasets'], (old: DatasetItem[]) => (old ?? []).map((x) => (x.id === next.id ? next : x)));
  };

  const remove = async () => {
    if (!deleteTarget) return;
    try {
      await features.datasets.remove(deleteTarget.id);
      qc.invalidateQueries({ queryKey: ['datasets'] });
      toast('Dataset deleted', deleteTarget.name);
    } catch (e) {
      toast('Failed', e instanceof Error ? e.message : 'Could not delete.', 'error');
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-7">
      <PageHeader
        title="Datasets"
        description="Every analysis starts here — import once, explore everywhere."
        actions={
          <Button onClick={() => setUploadOpen(true)}>
            <Upload className="h-3.5 w-3.5" /> Import data
          </Button>
        }
      />

      {isLoading ? (
        <LoadingBlock />
      ) : !datasets.length ? (
        <Card className="p-6">
          <EmptyState
            icon={<Database className="h-8 w-8" />}
            title="No datasets yet"
            description="Upload a CSV or Excel file, or load a demo dataset in just one click."
            action={<Button onClick={() => setUploadOpen(true)}><Upload className="h-3.5 w-3.5" /> Import data</Button>}
          />
        </Card>
      ) : (
        <>
          <div className="mb-5 flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search datasets…"
                className="h-9 w-full rounded-lg border border-input bg-card pl-8 pr-3 text-[13px] outline-none focus:border-primary/50 focus:ring-2 focus:ring-ring/20 sm:w-64"
              />
            </div>
            {!projectId && <span className="text-[11px] text-muted-foreground">Showing across all projects</span>}
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {datasets.map((d) => (
              <Card key={d.id} className="group relative flex cursor-pointer flex-col gap-3 p-5 transition hover:border-primary/40"
                onClick={() => navigate(`/datasets/${d.id}`)}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-chart-green/15 text-chart-green">
                    <Database className="h-5 w-5" />
                  </div>
                  <Menu
                    className="opacity-0 transition group-hover:opacity-100"
                    trigger={<button onClick={(e) => e.stopPropagation()} className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted"><MoreHorizontal className="h-4 w-4" /></button>}
                    items={[
                      { key: 'fav', label: d.is_favorite ? 'Remove favorite' : 'Favorite', icon: d.is_favorite ? <StarOff className="h-3.5 w-3.5" /> : <Star className="h-3.5 w-3.5" />, onClick: () => toggleFavorite(d) },
                      { key: 'del', label: 'Delete', danger: true, icon: <Trash2 className="h-3.5 w-3.5" />, onClick: () => setDeleteTarget(d) },
                    ]}
                  />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="truncate text-sm font-semibold">{d.name}</span>
                    {d.is_favorite && <Star className="h-3.5 w-3.5 shrink-0 fill-warning text-warning" />}
                  </div>
                  <div className="mt-0.5 text-[11px] text-muted-foreground">
                    {formatCompact(d.row_count)} rows · {d.column_count} columns · {formatBytes(d.size_bytes)}
                  </div>
                </div>
                <div className="mt-auto flex items-center justify-between border-t border-border/60 pt-3">
                  <div className="flex gap-1.5">
                    <Badge tone={d.quality_score != null && d.quality_score >= 95 ? 'green' : d.quality_score != null ? 'orange' : 'muted'}>
                      {d.quality_score != null ? `${d.quality_score}/100` : 'no score'}
                    </Badge>
                    <Badge tone="blue">{d.format.toUpperCase()}</Badge>
                  </div>
                  <span className="text-[10px] text-muted-foreground">{timeAgo(d.updated_at)}</span>
                </div>
              </Card>
            ))}
            <button
              onClick={() => setUploadOpen(true)}
              className="flex min-h-[150px] flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-border text-muted-foreground transition hover:border-primary/50 hover:text-foreground"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted"><Upload className="h-5 w-5" /></div>
              <span className="text-xs font-medium">Import dataset</span>
            </button>
          </div>
        </>
      )}

      <UploadModal open={uploadOpen} onClose={() => setUploadOpen(false)} />
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={remove}
        title="Delete dataset?"
        message={`"${deleteTarget?.name}" will be permanently removed from the workspace.`}
        danger
      />
    </div>
  );
}