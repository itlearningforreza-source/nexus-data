import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, LayoutDashboard, Table2, Sparkles, Wand2, Workflow, BarChart3, Activity, BrainCircuit, Star, Trash2, Clock, RefreshCw, Tag,
} from 'lucide-react';
import { features } from '@/lib/features';
import { Card, PillTabs, Badge, EmptyState, cn } from '@/components/ui';
import { toast } from '@/components/ui';
import { DataTable, DataTableStat } from '@/components/dataset/DataTable';
import { ProfileQualityView } from '@/components/dataset/ProfileQuality';
import { CleanPanel } from '@/components/dataset/CleanPanel';
import { TransformPanel } from '@/components/dataset/TransformPanel';
import { ChartBuilder } from '@/components/dataset/ChartBuilder';
import { StatsPanel } from '@/components/dataset/StatsPanel';
import { MLPanel } from '@/components/dataset/MLPanel';
import { formatBytes, formatDate, timeAgo } from '@/lib/format';

export default function DatasetHub() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [selectedTab, setSelectedTab] = useState('overview');
  const { data: dataset, isLoading } = useQuery({ queryKey: ['dataset', id], queryFn: () => features.datasets.get(id!) });
  const { data: preview } = useQuery({ queryKey: ['preview', id], queryFn: () => features.datasets.preview(id!, 60), enabled: !!id && !isLoading });
  const { data: versions } = useQuery({ queryKey: ['versions', id], queryFn: () => features.datasets.versions(id!), enabled: !!id });
  const { data: prof } = useQuery({ queryKey: ['profile', id], queryFn: () => features.datasets.profile(id!), enabled: !!id });

  const toggleFavorite = async () => {
    if (!dataset) return;
    await features.datasets.update(dataset.id, { is_favorite: !dataset.is_favorite });
    qc.invalidateQueries({ queryKey: ['datasets'] });
    qc.invalidateQueries({ queryKey: ['dataset', dataset.id] });
  };

  const remove = async () => {
    if (!dataset) return;
    try {
      await features.datasets.remove(dataset.id);
      toast('Deleted', 'Dataset removed.', 'success');
      navigate('/datasets');
    } catch (e) {
      toast('Delete failed', e instanceof Error ? e.message : 'Could not delete.', 'error');
    }
  };

  if (isLoading) {
    return <div className="flex h-64 items-center justify-center text-xs text-muted-foreground">Loading dataset…</div>;
  }
  if (!dataset) {
    return (
      <EmptyState icon={<Table2 className="h-6 w-6" />} title="Dataset not found"
        description="It may have been deleted." action={<Link to="/datasets" className="text-xs font-medium text-primary">Back to datasets</Link>} />
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Link to="/datasets" className="mt-1.5 text-muted-foreground transition hover:text-foreground"><ArrowLeft className="h-4 w-4" /></Link>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold tracking-tight">{dataset.name}</h1>
              <button onClick={toggleFavorite} className={cn('transition', dataset.is_favorite ? 'text-amber-400' : 'text-muted-foreground/40 hover:text-muted-foreground')}>
                <Star className="h-4 w-4" fill={dataset.is_favorite ? 'currentColor' : 'none'} />
              </button>
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {dataset.description || `Imported from ${dataset.original_filename ?? dataset.source_type}`} · updated {timeAgo(dataset.updated_at)}
            </p>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <Badge tone="blue">{dataset.format.toUpperCase()}</Badge>
              <Badge tone="muted">v{dataset.version}</Badge>
              {dataset.tags.map((t) => (
                <span key={t} className="flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"><Tag className="h-2.5 w-2.5" />{t}</span>
              ))}
              <Link to={`/sql?dataset=${dataset.id}`} className="text-[11px] font-medium text-primary hover:underline">Open in SQL</Link>
              <button onClick={() => qc.invalidateQueries({ queryKey: ['profile', id] })} className="text-[11px] font-medium text-muted-foreground hover:text-foreground">Re-profile</button>
              <button onClick={remove} className="text-[11px] font-medium text-muted-foreground hover:text-destructive"><Trash2 className="mr-0.5 inline h-3 w-3" /> Delete</button>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <Badge tone={dataset.quality_score === null ? 'muted' : (dataset.quality_score ?? 0) >= 75 ? 'green' : (dataset.quality_score ?? 0) >= 50 ? 'orange' : 'red'}>
            Quality {dataset.quality_score === null ? 'pending' : `${dataset.quality_score}/100`}
          </Badge>
        </div>
      </div>

      <PillTabs
        tabs={[
          { id: 'overview', label: 'Overview', icon: <LayoutDashboard className="h-3.5 w-3.5" /> },
          { id: 'profile', label: 'Profile & Quality', icon: <Sparkles className="h-3.5 w-3.5" /> },
          { id: 'clean', label: 'Clean', icon: <Wand2 className="h-3.5 w-3.5" /> },
          { id: 'transform', label: 'Transform', icon: <Workflow className="h-3.5 w-3.5" /> },
          { id: 'visualize', label: 'Visualize', icon: <BarChart3 className="h-3.5 w-3.5" /> },
          { id: 'stats', label: 'Statistics', icon: <Activity className="h-3.5 w-3.5" /> },
          { id: 'ml', label: 'Machine Learning', icon: <BrainCircuit className="h-3.5 w-3.5" /> },
        ]}
        active={selectedTab}
        onChange={setSelectedTab}
      />

      <div className="tabular-nums">
        {selectedTab === 'overview' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
              <DataTableStat label="Rows" value={dataset.row_count.toLocaleString()} />
              <DataTableStat label="Columns" value={dataset.column_count} />
              <DataTableStat label="Size" value={formatBytes(dataset.size_bytes)} />
              <DataTableStat label="Quality" value={dataset.quality_score === null ? '—' : String(dataset.quality_score)} />
              <DataTableStat label="Version" value={`v${dataset.version}`} />
              <DataTableStat label="Profile" value={(prof?.profile.column_count ?? 0).toLocaleString()} />
            </div>

            <Card className="p-4">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-semibold">Data preview</span>
                <span className="text-[11px] text-muted-foreground">{preview?.row_count.toLocaleString() ?? '...'} rows</span>
              </div>
              {preview ? <DataTable data={preview} height={400} /> : <div className="py-8 text-center text-xs text-muted-foreground">Loading…</div>}
            </Card>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="p-4">
                <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold"><Clock className="h-3.5 w-3.5 text-primary" /> Version history</div>
                {versions && versions.length ? (
                  <div className="space-y-1.5">
                    {versions.map((v) => (
                      <div key={v.id} className="flex items-center justify-between rounded-lg bg-muted/40 px-3 py-2 text-xs">
                        <span className="font-medium">v{v.version} <span className="ml-1 text-muted-foreground">{v.note || '—'}</span></span>
                        <span className="flex items-center gap-2 text-[11px] text-muted-foreground">
                          {formatDate(v.created_at)}
                          {v.version !== dataset.version && (
                            <button className="font-medium text-primary hover:underline" onClick={async () => {
                              await features.datasets.restore(dataset.id, v.id);
                              qc.invalidateQueries({ queryKey: ['dataset', id] });
                              qc.invalidateQueries({ queryKey: ['preview', id] });
                              qc.invalidateQueries({ queryKey: ['profile', id] });
                              toast('Restored', `Restored v${v.version}.`, 'success');
                            }}>restore</button>
                          )}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : <p className="text-[11px] text-muted-foreground">No version history yet.</p>}
              </Card>
              <Card className="p-4">
                <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold"><RefreshCw className="h-3.5 w-3.5 text-primary" /> Profile snapshot</div>
                {prof && (
                  <div className="space-y-2 text-xs">
                    <div className="flex items-center justify-between"><span className="text-muted-foreground">Null cells</span><span className="font-mono">{prof.profile.null_cells.toLocaleString()} ({prof.profile.null_pct.toFixed(1)}%)</span></div>
                    <div className="flex items-center justify-between"><span className="text-muted-foreground">Quality score</span><span className="font-semibold">{prof.quality.score}/100</span></div>
                    <div className="flex items-center justify-between"><span className="text-muted-foreground">Issues</span><span className="font-semibold">{prof.quality.issues.length}</span></div>
                    <div className="flex flex-wrap gap-1 pt-1">
                      {prof.quality.subscores && Object.entries(prof.quality.subscores).map(([k, v]) => (
                        <Badge key={k} tone="muted">{k} {typeof v === 'number' ? `${v}/100` : ''}</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </Card>
            </div>
          </div>
        )}
        {selectedTab === 'profile' && <ProfileQualityView datasetId={dataset.id} />}
        {selectedTab === 'clean' && <CleanPanel datasetId={dataset.id} />}
        {selectedTab === 'transform' && <TransformPanel datasetId={dataset.id} />}
        {selectedTab === 'visualize' && <ChartBuilder datasetId={dataset.id} onSaved={() => toast('Chart saved', 'Saved — open in the Charts gallery.', 'success')} />}
        {selectedTab === 'stats' && <StatsPanel datasetId={dataset.id} />}
        {selectedTab === 'ml' && <MLPanel datasetId={dataset.id} />}
      </div>
    </div>
  );
}