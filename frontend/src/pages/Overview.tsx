import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  FolderKanban, Database, BarChart3, FileText, ArrowRight, Plus, Sparkles,
  Braces, LayoutDashboard, FlaskConical, BrainCircuit, Zap,
} from 'lucide-react';
import { features } from '@/lib/features';
import { useAuth } from '@/store/auth';
import { Card, cn, LoadingBlock } from '@/components/ui';
import { formatCompact, timeAgo } from '@/lib/format';
import type { ProjectItem, DatasetItem } from '@/lib/types';

function StatCard({ icon: Icon, label, value, tone, to }: { icon: typeof Database; label: string; value: string; tone: string; to: string }) {
  const navigate = useNavigate();
  return (
    <button onClick={() => navigate(to)} className="group text-left">
      <Card className="flex items-center gap-3.5 p-4 transition group-hover:border-primary/40">
        <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-xl', tone)}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <div className="text-lg font-bold leading-none tabular-nums">{value}</div>
          <div className="mt-1 text-[11px] text-muted-foreground">{label}</div>
        </div>
      </Card>
    </button>
  );
}

const FEATURES = [
  { title: 'Spreadsheet', desc: 'Explore any dataset in a fast grid', icon: Database, to: '/datasets', color: 'bg-chart-blue/15 text-chart-blue' },
  { title: 'SQL Workbench', desc: 'Query across datasets in real time', icon: Braces, to: '/sql', color: 'bg-chart-purple/15 text-chart-purple' },
  { title: 'Visualize', desc: 'Build charts with one click', icon: BarChart3, to: '/charts', color: 'bg-chart-orange/15 text-chart-orange' },
  { title: 'Dashboards', desc: 'Compose insights into living views', icon: LayoutDashboard, to: '/dashboards', color: 'bg-chart-green/15 text-chart-green' },
  { title: 'Notebooks', desc: 'Sandboxed Python at your fingertips', icon: FlaskConical, to: '/notebooks', color: 'bg-chart-cyan/15 text-chart-cyan' },
  { title: 'AI Analyst', desc: 'Ask questions in plain language', icon: BrainCircuit, to: '/ai', color: 'bg-chart-pink/15 text-chart-pink' },
];

export default function Overview() {
  const user = useAuth((s) => s.user);
  const navigate = useNavigate();
  const name = user?.name?.split(' ')[0] ?? 'there';

  const projectsQ = useQuery({ queryKey: ['projects', 'overview'], queryFn: features.projects.list });
  const datasetsQ = useQuery({ queryKey: ['datasets', 'overview'], queryFn: features.datasets.list });
  const chartsQ = useQuery({ queryKey: ['charts', 'overview'], queryFn: features.charts.list });
  const reportsQ = useQuery({ queryKey: ['reports', 'overview'], queryFn: features.reports.list });

  const projects = (projectsQ.data ?? []) as ProjectItem[];
  const datasets = (datasetsQ.data ?? []) as DatasetItem[];
  const loading = projectsQ.isLoading;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  const recent = [...projects].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 4);
  const recentDatasets = [...datasets].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 4);

  return (
    <div className="mx-auto max-w-6xl px-6 py-7">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">{new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</div>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">{greeting}, {name}.</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">Here's what's happening across your workspace.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => navigate('/projects')}
            className="flex h-9 items-center gap-2 rounded-xl border border-border bg-card px-3.5 text-xs font-semibold transition hover:bg-muted"
          >
            <Plus className="h-3.5 w-3.5" /> New project
          </button>
          <button
            onClick={() => navigate('/ai')}
            className="flex h-9 items-center gap-2 rounded-xl bg-primary px-3.5 text-xs font-semibold text-white transition hover:opacity-90"
          >
            <Sparkles className="h-3.5 w-3.5" /> Ask AI
          </button>
        </div>
      </div>

      {loading ? (
        <LoadingBlock />
      ) : (
        <>
          <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard icon={FolderKanban} label="Projects" value={String(projects.length)} tone="bg-chart-blue/15 text-chart-blue" to="/projects" />
            <StatCard icon={Database} label="Datasets" value={String(datasets.length)} tone="bg-chart-green/15 text-chart-green" to="/datasets" />
            <StatCard icon={BarChart3} label="Charts" value={String((chartsQ.data ?? []).length)} tone="bg-chart-orange/15 text-chart-orange" to="/charts" />
            <StatCard icon={FileText} label="Reports" value={String(reportsQ.data?.length ?? 0)} tone="bg-chart-purple/15 text-chart-purple" to="/reports" />
          </div>

          <div className="mb-8 grid gap-6 lg:grid-cols-2">
            <Card className="p-5">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold">Recent projects</h2>
                <button onClick={() => navigate('/projects')} className="flex items-center gap-1 text-[11px] font-medium text-primary hover:underline">
                  View all <ArrowRight className="h-3 w-3" />
                </button>
              </div>
              {!recent.length ? (
                <div className="py-8 text-center">
                  <div className="text-xs text-muted-foreground">No projects yet — create your first one to get started.</div>
                  <button
                    onClick={() => navigate('/projects')}
                    className="mt-3 flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-xs font-semibold text-white"
                  >
                    <Plus className="h-3.5 w-3.5" /> Create project
                  </button>
                </div>
              ) : (
                <div className="space-y-1.5">
                  {recent.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => navigate(`/projects/${p.id}`)}
                      className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-muted"
                    >
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary/80 to-purple/80 text-white">
                        <FolderKanban className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-[13px] font-semibold">{p.name}</div>
                        <div className="text-[11px] text-muted-foreground">
                          {p.counts?.datasets ?? 0} datasets · {p.counts?.charts ?? 0} charts
                        </div>
                      </div>
                      <span className="text-[11px] text-muted-foreground">{timeAgo(p.updated_at)}</span>
                    </button>
                  ))}
                </div>
              )}
            </Card>

            <Card className="p-5">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold">Recent datasets</h2>
                <button onClick={() => navigate('/datasets')} className="flex items-center gap-1 text-[11px] font-medium text-primary hover:underline">
                  View all <ArrowRight className="h-3 w-3" />
                </button>
              </div>
              {!recentDatasets.length ? (
                <div className="py-8 text-center">
                  <div className="text-xs text-muted-foreground">Import a CSV/Excel file or load a demo dataset.</div>
                  <button
                    onClick={() => navigate('/datasets')}
                    className="mt-3 flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-xs font-semibold text-white"
                  >
                    <Database className="h-3.5 w-3.5" /> Go to datasets
                  </button>
                </div>
              ) : (
                <div className="space-y-1.5">
                  {recentDatasets.map((d) => (
                    <button
                      key={d.id}
                      onClick={() => navigate(`/datasets/${d.id}`)}
                      className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-muted"
                    >
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-chart-green/15 text-chart-green">
                        <Database className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-[13px] font-semibold">{d.name}</div>
                        <div className="text-[11px] text-muted-foreground">
                          {formatCompact(d.row_count)} rows · {d.column_count} cols
                          {d.quality_score != null && <> · score {d.quality_score}</>}
                        </div>
                      </div>
                      <span className="text-[11px] text-muted-foreground">{timeAgo(d.updated_at)}</span>
                    </button>
                  ))}
                </div>
              )}
            </Card>
          </div>

          <div>
            <h2 className="mb-3 text-sm font-semibold">Jump into a tool</h2>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              {FEATURES.map((f) => (
                <button key={f.title} onClick={() => navigate(f.to)}>
                  <Card className="flex h-full flex-col gap-2.5 p-4 transition hover:border-primary/40">
                    <div className={cn('flex h-9 w-9 items-center justify-center rounded-xl', f.color)}>
                      <f.icon className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="text-[13px] font-semibold">{f.title}</div>
                      <div className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{f.desc}</div>
                    </div>
                  </Card>
                </button>
              ))}
            </div>
          </div>

          <div className="mt-8 flex items-center gap-2 rounded-2xl border border-dashed border-border bg-card/40 p-4 text-[11px] text-muted-foreground">
            <Zap className="h-3.5 w-3.5 text-warning" />
            Tip: press <span className="mx-0.5 rounded border border-border bg-muted px-1">⌘K</span> to search anything, anywhere.
          </div>
        </>
      )}
    </div>
  );
}