import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  LayoutGrid, FolderKanban, Database, Braces, BarChart3, LayoutDashboard, FileText,
  FlaskConical, Sparkles, BarChart4, BrainCircuit, Search, Settings, LogOut, PanelLeft,
  Sun, Moon, Zap, ChevronRight, Boxes, Plus, Table,
} from 'lucide-react';
import { useAuth } from '@/store/auth';
import { useUI } from '@/store/ui';
import { features } from '@/lib/features';
import { cn } from '@/components/ui';
import type { ProjectItem } from '@/lib/types';

interface NavItem {
  to: string;
  label: string;
  icon: typeof Database;
  end?: boolean;
}

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: 'Workspace',
    items: [
      { to: '/', label: 'Overview', icon: LayoutGrid, end: true },
      { to: '/projects', label: 'Projects', icon: FolderKanban },
    ],
  },
  {
    section: 'Build',
    items: [
      { to: '/datasets', label: 'Datasets', icon: Database },
      { to: '/spreadsheet', label: 'Spreadsheet', icon: Table },
      { to: '/sql', label: 'SQL', icon: Braces },
      { to: '/charts', label: 'Charts', icon: BarChart3 },
      { to: '/dashboards', label: 'Dashboards', icon: LayoutDashboard },
      { to: '/reports', label: 'Reports', icon: FileText },
    ],
  },
  {
    section: 'Analyze',
    items: [
      { to: '/notebooks', label: 'Notebooks', icon: FlaskConical },
      { to: '/ai', label: 'AI Analyst', icon: BrainCircuit },
      { to: '/stats', label: 'Statistics', icon: BarChart4 },
      { to: '/ml', label: 'AutoML', icon: Sparkles },
    ],
  },
];

function UserMenu() {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (menu && !menu.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open, menu]);

  const initials = (user?.name ?? '?')
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="relative" ref={setMenu}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2.5 rounded-lg p-1.5 text-left transition hover:bg-muted"
      >
        <div
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
          style={{ background: user?.avatar_color || '#5E5CE6' }}
        >
          {initials}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-xs font-semibold">{user?.name ?? 'Guest'}</div>
          <div className="truncate text-[10px] text-muted-foreground">{user?.email ?? ''}</div>
        </div>
      </button>
      {open && (
        <div className="absolute bottom-12 left-0 z-50 w-56 overflow-hidden rounded-xl border border-border bg-card p-1 shadow-pop">
          <button
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs transition hover:bg-muted"
            onClick={() => {
              setOpen(false);
              navigate('/settings');
            }}
          >
            <Settings className="h-3.5 w-3.5" /> Account settings
          </button>
          <button
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-destructive transition hover:bg-muted"
            onClick={() => {
              setOpen(false);
              logout();
              navigate('/auth');
            }}
          >
            <LogOut className="h-3.5 w-3.5" /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

function ProjectSwitcher() {
  const { projectId, projectName, setProject } = useUI();
  const { data } = useQuery({ queryKey: ['projects'], queryFn: features.projects.list, enabled: true });
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState<HTMLDivElement | null>(null);
  const locations = useLocation();

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (menu && !menu.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open, menu]);

  const projects = (data ?? []) as ProjectItem[];
  useEffect(() => {
    if (!projectId && projects.length && locations.pathname !== '/projects') {
      setProject(projects[0].id, projects[0].name);
    }
  }, [projects.length, projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const current = projects.find((p) => p.id === projectId);

  return (
    <div className="relative" ref={setMenu}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex max-w-[260px] items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs font-semibold transition hover:bg-muted"
      >
        <Boxes className="h-3.5 w-3.5 text-primary" />
        <span className="truncate">{current?.name ?? projectName ?? 'Select project'}</span>
        <ChevronRight className={cn('h-3 w-3 text-muted-foreground transition', open && 'rotate-90')} />
      </button>
      {open && (
        <div className="absolute left-0 top-9 z-50 w-72 overflow-hidden rounded-xl border border-border bg-card p-1 shadow-pop">
          <div className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Projects</div>
          <div className="max-h-72 overflow-y-auto scrollbar-thin">
            {projects.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setProject(p.id, p.name);
                  setOpen(false);
                }}
                className={cn(
                  'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs transition hover:bg-muted',
                  p.id === projectId && 'bg-muted font-semibold',
                )}
              >
                <FolderKanban className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span className="truncate">{p.name}</span>
                {p.counts?.datasets != null && (
                  <span className="ml-auto text-[10px] text-muted-foreground">{p.counts.datasets} datasets</span>
                )}
              </button>
            ))}
            {!projects.length && <div className="px-3 py-4 text-center text-xs text-muted-foreground">No projects yet</div>}
          </div>
        </div>
      )}
    </div>
  );
}

export function Shell() {
  const collapsed = useUI((s) => s.sidebarCollapsed);
  const toggleSidebar = useUI((s) => s.toggleSidebar);
  const theme = useUI((s) => s.theme);
  const toggleTheme = useUI((s) => s.toggleTheme);
  const setPaletteOpen = useUI((s) => s.setPaletteOpen);
  const navigate = useNavigate();
  const location = useLocation();
  const token = useAuth((s) => s.token);
  const loading = useAuth((s) => s.loading);
  const { projectId } = useUI();

  const { data: projects } = useQuery({
    queryKey: ['projects', 'top'],
    queryFn: () => features.projects.list(),
    enabled: !!token,
    refetchOnMount: false,
  });

  const topProject = (projects ?? []).find((p) => p.id === projectId) ?? (projects?.length ? projects[0] : null);

  useEffect(() => {
    if (topProject && useUI.getState().projectId !== topProject.id) {
      useUI.getState().setProject(topProject.id, topProject.name);
    }
  }, [topProject?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!loading && !token) {
    return null;
  }

  const pageTitle =
    NAV.flatMap((s) => s.items)
      .filter((i) => (i.end ? location.pathname === i.to : location.pathname.startsWith(i.to)))
      .map((i) => i.label)[0] ?? 'Workspace';

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <aside
        className={cn(
          'flex shrink-0 flex-col border-r border-border bg-card/40 backdrop-blur transition-all duration-200',
          collapsed ? 'w-16' : 'w-60',
        )}
      >
        <div className="flex h-14 items-center gap-2.5 border-b border-border/60 px-4">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-purple text-white shadow-subtle">
            <Zap className="h-4 w-4" />
          </div>
          {!collapsed && (
            <>
              <div className="text-sm font-bold tracking-tight">Nexus</div>
              <div className="text-[10px] text-muted-foreground">DATA</div>
            </>
          )}
        </div>

        <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4 scrollbar-thin">
          {NAV.map((group) => (
            <div key={group.section} className={collapsed ? '' : 'space-y-0.5'}>
              {!collapsed && (
                <div className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                  {group.section}
                </div>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    title={collapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-xs font-medium transition',
                        isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                        collapsed && 'justify-center px-2',
                      )
                    }
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-border/60 p-3">
          <button
            onClick={toggleTheme}
            className={cn(
              'mb-1 flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-xs text-muted-foreground transition hover:bg-muted hover:text-foreground',
              collapsed && 'justify-center px-2',
            )}
            title={collapsed ? 'Toggle theme' : undefined}
          >
            {theme === 'dark' ? <Sun className="h-4 w-4 shrink-0" /> : <Moon className="h-4 w-4 shrink-0" />}
            {!collapsed && <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>}
          </button>
          {!collapsed ? (
            <UserMenu />
          ) : (
            <div className="flex justify-center pt-1">
              <button
                onClick={() => navigate('/settings')}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted"
              >
                <Settings className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card/60 px-4 backdrop-blur">
          <button
            onClick={toggleSidebar}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted"
          >
            <PanelLeft className="h-4 w-4" />
          </button>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span className="font-medium text-foreground">{topProject?.name ?? 'Nexus'}</span>
              <ChevronRight className="h-3 w-3" />
              <span>{pageTitle}</span>
            </div>
          </div>
          <div className="hidden items-center gap-2 md:flex">
            {topProject && (
              <ProjectSwitcher />
            )}
            <button
              onClick={() => setPaletteOpen(true)}
              className="flex h-8 items-center gap-2 rounded-lg border border-border bg-card px-3 text-xs text-muted-foreground transition hover:bg-muted"
            >
              <Search className="h-3.5 w-3.5" />
              <span className="hidden lg:inline">Search anything…</span>
              <kbd className="ml-1 rounded border border-border bg-muted px-1 text-[10px]">⌘K</kbd>
            </button>
            <button
              onClick={() => navigate('/projects')}
              className="flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-xs font-semibold text-white transition hover:opacity-90"
            >
              <Plus className="h-3.5 w-3.5" /> New
            </button>
          </div>
        </header>

        <main className="scrollbar-thin relative min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}