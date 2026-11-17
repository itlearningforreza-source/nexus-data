import { create } from 'zustand';

const THEME_KEY = 'nexus_theme';
const PROJECT_KEY = 'nexus_project';

type Theme = 'light' | 'dark';

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === 'light' || saved === 'dark') return saved;
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
  } catch {
    // noop
  }
  return 'dark';
}

interface UIState {
  theme: Theme;
  paletteOpen: boolean;
  projectId: string | null;
  projectName: string | null;
  sidebarCollapsed: boolean;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;
  setPaletteOpen: (open: boolean) => void;
  setProject: (id: string | null, name?: string | null) => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useUI = create<UIState>((set, get) => ({
  theme: initialTheme(),
  paletteOpen: false,
  projectId: localStorage.getItem(PROJECT_KEY),
  projectName: localStorage.getItem(PROJECT_KEY + '_name'),
  sidebarCollapsed: false,
  setTheme: (t) => {
    localStorage.setItem(THEME_KEY, t);
    document.documentElement.classList.toggle('dark', t === 'dark');
    set({ theme: t });
  },
  toggleTheme: () => get().setTheme(get().theme === 'dark' ? 'light' : 'dark'),
  setPaletteOpen: (open) => set({ paletteOpen: open }),
  setProject: (id, name) => {
    if (id) {
      localStorage.setItem(PROJECT_KEY, id);
      if (name) localStorage.setItem(PROJECT_KEY + '_name', name);
      set({ projectId: id, projectName: name ?? get().projectName });
    } else {
      localStorage.removeItem(PROJECT_KEY);
      localStorage.removeItem(PROJECT_KEY + '_name');
      set({ projectId: null, projectName: null });
    }
  },
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
}));

export function applyInitialTheme() {
  const t = useUI.getState().theme;
  document.documentElement.classList.toggle('dark', t === 'dark');
}

window.addEventListener('nexus:logout', async () => {
  const { setToken, setStoredUser } = await import('@/lib/api');
  const { useAuth } = await import('@/store/auth');
  setToken(null);
  setStoredUser(null);
  useAuth.getState().logout();
});