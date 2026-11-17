import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, CornerDownLeft, Database, FileText, LayoutDashboard, Braces, FlaskConical, FolderKanban, BarChart3, ExternalLink } from 'lucide-react';
import { useUI } from '@/store/ui';
import { features } from '@/lib/features';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/components/ui';
import type { ProjectItem, DatasetItem } from '@/lib/types';

type Entry = {
  kind: 'nav' | 'project' | 'dataset' | 'chart' | 'dashboard' | 'report' | 'query' | 'notebook';
  title: string;
  subtitle?: string;
  icon: typeof Database;
  route: string;
};

const NAV_ENTRIES: Entry[] = [
  { kind: 'nav', title: 'Overview', icon: FolderKanban, route: '/' },
  { kind: 'nav', title: 'Projects', icon: FolderKanban, route: '/projects' },
  { kind: 'nav', title: 'Datasets', icon: Database, route: '/datasets' },
  { kind: 'nav', title: 'SQL Workbench', icon: Braces, route: '/sql' },
  { kind: 'nav', title: 'Charts', icon: BarChart3, route: '/charts' },
  { kind: 'nav', title: 'Dashboards', icon: LayoutDashboard, route: '/dashboards' },
  { kind: 'nav', title: 'Reports', icon: FileText, route: '/reports' },
  { kind: 'nav', title: 'Notebooks', icon: FlaskConical, route: '/notebooks' },
  { kind: 'nav', title: 'AI Analyst', icon: FlaskConical, route: '/ai' },
  { kind: 'nav', title: 'Statistics', icon: BarChart3, route: '/stats' },
  { kind: 'nav', title: 'AutoML', icon: BarChart3, route: '/ml' },
  { kind: 'nav', title: 'Account settings', icon: FolderKanban, route: '/settings' },
];

export function CommandPalette() {
  const { paletteOpen, setPaletteOpen } = useUI();
  const [query, setQuery] = useState('');
  const [index, setIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const { data: projects } = useQuery({
    queryKey: ['projects', 'palette'],
    queryFn: () => features.projects.list(),
    enabled: paletteOpen,
    refetchOnMount: false,
  });

  useEffect(() => {
    if (paletteOpen) {
      setQuery('');
      setIndex(0);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [paletteOpen]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen(!paletteOpen);
      }
      if (e.key === 'Escape') setPaletteOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [paletteOpen, setPaletteOpen]);

  const entries = useMemo<Entry[]>(() => {
    const out: Entry[] = [...NAV_ENTRIES];
    for (const p of (projects ?? []) as ProjectItem[]) {
      out.push({ kind: 'project', title: p.name, subtitle: 'Project', icon: FolderKanban, route: `/projects/${p.id}` });
      for (const d of ((p as ProjectItem & { datasets?: DatasetItem[] }).datasets ?? []).slice(0, 10)) {
        out.push({ kind: 'dataset', title: d.name, subtitle: 'Dataset', icon: Database, route: `/datasets/${d.id}` });
      }
    }
    return out;
  }, [projects]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter((e) => e.title.toLowerCase().includes(q) || (e.subtitle ?? '').toLowerCase().includes(q));
  }, [entries, query]);

  useEffect(() => setIndex(0), [filtered.length]);

  if (!paletteOpen) return null;

  const go = (e: Entry) => {
    setPaletteOpen(false);
    navigate(e.route);
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center bg-black/40 pt-[16vh] backdrop-blur-sm"
      onMouseDown={() => setPaletteOpen(false)}
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-2xl border border-border bg-card shadow-float"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="relative">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                e.preventDefault();
                setIndex((i) => Math.min(i + 1, filtered.length - 1));
              } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setIndex((i) => Math.max(i - 1, 0));
              } else if (e.key === 'Enter') {
                const entry = filtered[index];
                if (entry) go(entry);
              }
            }}
            placeholder="Search projects, datasets, navigation…"
            className="h-14 w-full bg-transparent pl-11 pr-4 text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>
        <div className="max-h-80 overflow-y-auto border-t border-border p-1.5 scrollbar-thin">
          {filtered.map((entry, i) => (
            <button
              key={`${entry.kind}-${entry.title}-${i}`}
              onMouseEnter={() => setIndex(i)}
              onClick={() => go(entry)}
              className={cn(
                'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition',
                i === index && 'bg-muted',
              )}
            >
              <entry.icon className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-medium">{entry.title}</div>
                {entry.subtitle && <div className="truncate text-[10px] text-muted-foreground">{entry.subtitle}</div>}
              </div>
              {i === index && <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
              {entry.kind !== 'nav' && <ExternalLink className="h-3 w-3 shrink-0 text-muted-foreground/60" />}
            </button>
          ))}
          {!filtered.length && (
            <div className="px-3 py-8 text-center text-xs text-muted-foreground">No results for “{query}”</div>
          )}
        </div>
        <div className="flex items-center gap-3 border-t border-border px-4 py-2 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-1"><CornerDownLeft className="h-3 w-3" /> select</span>
          <span>↑↓ navigate</span>
          <span>esc close</span>
        </div>
      </div>
    </div>
  );
}