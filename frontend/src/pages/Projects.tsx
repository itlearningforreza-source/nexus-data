import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  FolderKanban, Plus, Trash2, MoreHorizontal, Star, StarOff, Copy, Database,
} from 'lucide-react';
import { features } from '@/lib/features';
import { useUI } from '@/store/ui';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, Modal, ConfirmDialog, Menu, Input, Field, Button, EmptyState, LoadingBlock, Badge } from '@/components/ui';
import { toast } from '@/components/ui';
import { timeAgo, formatCompact } from '@/lib/format';
import type { ProjectItem, DemoEntry } from '@/lib/types';

function CreateProjectModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [busy, setBusy] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();

  const create = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const p = await features.projects.create(name.trim(), desc.trim() || undefined);
      qc.invalidateQueries({ queryKey: ['projects'] });
      toast('Project created', `"${p.name}" is ready.`);
      onClose();
      navigate(`/projects/${p.id}`);
    } catch (e) {
      toast('Failed', e instanceof Error ? e.message : 'Could not create project.', 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Create project" description="Projects group datasets, charts and dashboards." size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={create} loading={busy} disabled={!name.trim()}>
            <Plus className="h-3.5 w-3.5" /> Create
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Name">
          <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Quarterly analysis" onKeyDown={(e) => e.key === 'Enter' && create()} />
        </Field>
        <Field label="Description" hint="Optional">
          <Input value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="What is this project about?" />
        </Field>
      </div>
    </Modal>
  );
}

function DemoModal({ open, onClose, projectId }: { open: boolean; onClose: () => void; projectId: string }) {
  const [busyName, setBusyName] = useState<string | null>(null);
  const qc = useQueryClient();
  const { data: demos, isLoading } = useQuery({ queryKey: ['demo-list'], queryFn: features.datasets.demos, enabled: open });
  const navigate = useNavigate();

  const run = async (name: string) => {
    setBusyName(name);
    try {
      const res = await features.datasets.importDemo(name, projectId);
      qc.invalidateQueries({ queryKey: ['datasets'] });
      toast('Dataset imported', `${res.dataset.name} — ${formatCompact(res.dataset.row_count)} rows.`, 'success');
      onClose();
      navigate(`/datasets/${res.dataset.id}`);
    } catch (e) {
      toast('Import failed', e instanceof Error ? e.message : 'Could not import.', 'error');
    } finally {
      setBusyName(null);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Load a demo dataset" description="Pre-built sample data to explore Nexus right away." size="md">
      <div className="space-y-3">
        {isLoading && <LoadingBlock />}
        {!isLoading && demos?.length ? (
          demos.map((d: DemoEntry) => (
            <button
              key={d.name}
              disabled={busyName !== null}
              onClick={() => run(d.name)}
              className="flex w-full items-center justify-between rounded-xl border border-border px-4 py-3 text-left transition hover:border-primary/40 hover:bg-muted"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-chart-green/15 text-chart-green"><Database className="h-4 w-4" /></div>
                <div>
                  <div className="text-[13px] font-semibold">{d.name}</div>
                  <div className="text-[11px] text-muted-foreground">{d.description}</div>
                </div>
              </div>
              {busyName === d.name && <span className="text-xs text-muted-foreground">Importing…</span>}
            </button>
          ))
        ) : null}
      </div>
    </Modal>
  );
}

export default function Projects() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { setProject, projectId } = useUI();
  const [createOpen, setCreateOpen] = useState(false);
  const [demoOpen, setDemoOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProjectItem | null>(null);
  const [query, setQuery] = useState('');

  const { data, isLoading } = useQuery({ queryKey: ['projects'], queryFn: features.projects.list });
  const projects = useMemo(() => {
    const list = (data ?? []) as ProjectItem[];
    const q = query.trim().toLowerCase();
    const filtered = q ? list.filter((p) => p.name.toLowerCase().includes(q)) : list;
    return [...filtered].sort((a, b) => Number(b.is_favorite ?? 0) - Number(a.is_favorite ?? 0) || b.updated_at.localeCompare(a.updated_at));
  }, [data, query]);

  const toggleFavorite = async (p: ProjectItem) => {
    const next = await features.projects.update(p.id, { is_favorite: !p.is_favorite });
    qc.setQueryData(['projects'], (old: ProjectItem[]) => (old ?? []).map((x) => (x.id === next.id ? next : x)));
  };

  const remove = async () => {
    if (!deleteTarget) return;
    try {
      await features.projects.remove(deleteTarget.id);
      qc.invalidateQueries({ queryKey: ['projects'] });
      if (deleteTarget.id === projectId) setProject(null);
      toast('Project deleted', deleteTarget.name);
    } catch (e) {
      toast('Failed', e instanceof Error ? e.message : 'Could not delete.', 'error');
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-7">
      <PageHeader
        title="Projects"
        description="Each project collects datasets, charts, dashboards and reports around one goal."
        actions={
          <>
            <Button variant="outline" onClick={() => setDemoOpen(true)}><Database className="h-3.5 w-3.5" /> Load demo</Button>
            <Button onClick={() => setCreateOpen(true)}><Plus className="h-3.5 w-3.5" /> New project</Button>
          </>
        }
      />

      {isLoading ? (
        <LoadingBlock />
      ) : !projects.length && !query ? (
        <Card className="p-6">
          <EmptyState
            icon={<FolderKanban className="h-8 w-8" />}
            title="No projects yet"
            description="Create a project to group datasets, or import a demo dataset to explore immediately."
            action={<Button onClick={() => setCreateOpen(true)}><Plus className="h-3.5 w-3.5" /> Create your first project</Button>}
          />
        </Card>
      ) : (
        <>
          <div className="mb-4">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search projects…"
              className="h-9 w-full max-w-xs rounded-lg border border-input bg-card px-3 text-[13px] outline-none focus:border-primary/50 focus:ring-2 focus:ring-ring/20"
            />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {projects.map((p) => (
              <Card key={p.id} className="group relative flex cursor-pointer flex-col gap-3 p-5 transition hover:border-primary/40"
                onClick={() => { setProject(p.id, p.name); navigate(`/projects/${p.id}`); }}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary/80 to-purple/80 text-white shadow-subtle">
                    <FolderKanban className="h-5 w-5" />
                  </div>
                  <Menu
                    className="opacity-0 transition group-hover:opacity-100"
                    trigger={<button onClick={(e) => e.stopPropagation()} className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted"><MoreHorizontal className="h-4 w-4" /></button>}
                    items={[
                      { key: 'fav', label: p.is_favorite ? 'Remove favorite' : 'Favorite', icon: p.is_favorite ? <StarOff className="h-3.5 w-3.5" /> : <Star className="h-3.5 w-3.5" />, onClick: () => toggleFavorite(p) },
                      { key: 'dup', label: 'Duplicate', icon: <Copy className="h-3.5 w-3.5" />, onClick: async () => { await features.projects.duplicate(p.id); qc.invalidateQueries({ queryKey: ['projects'] }); toast('Duplicated', p.name); } },
                      { key: 'del', label: 'Delete', danger: true, icon: <Trash2 className="h-3.5 w-3.5" />, onClick: () => setDeleteTarget(p) },
                    ]}
                  />
                </div>
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="truncate text-sm font-semibold">{p.name}</span>
                    {p.is_favorite && <Star className="h-3.5 w-3.5 fill-warning text-warning" />}
                  </div>
                  {p.description && <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">{p.description}</p>}
                </div>
                <div className="mt-auto flex items-center justify-between border-t border-border/60 pt-3">
                  <div className="flex gap-2">
                    <Badge tone="blue">{p.counts?.datasets ?? 0} datasets</Badge>
                    <Badge tone="purple">{p.counts?.charts ?? 0} charts</Badge>
                    <Badge tone="muted">{p.counts?.dashboards ?? 0} dash</Badge>
                  </div>
                  <span className="text-[10px] text-muted-foreground">{timeAgo(p.updated_at)}</span>
                </div>
              </Card>
            ))}
            <button
              onClick={() => setCreateOpen(true)}
              className="flex min-h-[150px] flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-border text-muted-foreground transition hover:border-primary/50 hover:text-foreground"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted"><Plus className="h-5 w-5" /></div>
              <span className="text-xs font-medium">New project</span>
            </button>
          </div>
        </>
      )}

      <CreateProjectModal open={createOpen} onClose={() => setCreateOpen(false)} />
      <DemoModal open={demoOpen} onClose={() => setDemoOpen(false)} projectId={projectId ?? ''} />
      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={remove}
        title="Delete project?"
        message={`"${deleteTarget?.name}" and everything in it will be permanently removed.`}
        danger
      />
    </div>
  );
}