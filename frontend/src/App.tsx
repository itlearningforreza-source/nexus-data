import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CommandPalette } from '@/components/layout/CommandPalette';
import { Shell } from '@/components/layout/Shell';
import { Toast } from '@/components/ui';
import { useAuth } from '@/store/auth';
import { applyInitialTheme } from '@/store/ui';

import Auth from '@/pages/Auth';
import Overview from '@/pages/Overview';
import Projects from '@/pages/Projects';
import Datasets from '@/pages/Datasets';
import DatasetHub from '@/pages/DatasetHub';
import SqlWorkbench from '@/pages/SqlWorkbench';
import Charts from '@/pages/Charts';
import Stats from '@/pages/Stats';
import ML from '@/pages/ML';
import Dashboards from '@/pages/Dashboards';
import DashboardView from '@/pages/DashboardView';
import Reports from '@/pages/Reports';
import ReportView from '@/pages/ReportView';
import Notebooks from '@/pages/Notebooks';
import NotebookView from '@/pages/NotebookView';
import AiChat from '@/pages/AiChat';
import Settings from '@/pages/Settings';
import Spreadsheet from '@/pages/Spreadsheet';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function RequireAuth() {
  const { token } = useAuth();
  return token ? <Outlet /> : <Navigate to="/auth" replace />;
}

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    document.getElementById('app-scroll')?.scrollTo({ top: 0 });
  }, [pathname]);
  return null;
}

function App() {
  useEffect(() => {
    applyInitialTheme();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ScrollToTop />
        <Toast />
        <CommandPalette />
        <Routes>
          <Route path="/auth" element={<Auth />} />
          <Route element={<RequireAuth />}>
            <Route element={<Shell />}>
              <Route index element={<Overview />} />
              <Route path="projects" element={<Projects />} />
              <Route path="projects/:id" element={<ProjectFallback />} />
              <Route path="datasets" element={<Datasets />} />
              <Route path="datasets/:id" element={<DatasetHub />} />
              <Route path="sql" element={<SqlWorkbench />} />
              <Route path="charts" element={<Charts />} />
              <Route path="stats" element={<Stats />} />
              <Route path="ml" element={<ML />} />
              <Route path="dashboards" element={<Dashboards />} />
              <Route path="dashboards/:id" element={<DashboardView />} />
              <Route path="reports" element={<Reports />} />
              <Route path="reports/:id" element={<ReportView />} />
              <Route path="notebooks" element={<Notebooks />} />
              <Route path="notebooks/:id" element={<NotebookView />} />
              <Route path="ai" element={<AiChat />} />
              <Route path="settings" element={<Settings />} />
            <Route path="spreadsheet" element={<Spreadsheet />} />
            <Route path="spreadsheet/:id" element={<Spreadsheet />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

function ProjectFallback() {
  return <Navigate to="/projects" replace />;
}

export default App;