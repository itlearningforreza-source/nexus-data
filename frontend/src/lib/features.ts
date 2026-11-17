import { api } from './api';
import type {
  ProjectItem, DatasetItem, Preview, ProfileColumn, QualityResult,
  ChartData, ChartItem, ChartRecommendation, ChartSchemaColumn,
  SQLQueryItem, SQLResult, SQLTableSchema, SQLSnippet,
  StatsDescriptiveResult, CorrelationPair, StatsTestResult, RegressionResult, TimeSeriesResult,
  MLTrainResult, MLModelRecord, NotebookItem, NotebookRunOutput,
  AIMessage, Conversation, ReportItem, DashboardItem, JobItem,
  SearchResult, User,
} from './types';

export interface CleanResponse {
  dataset: DatasetItem;
  preview: Preview;
  quality: QualityResult;
}

export interface TransformResponse extends CleanResponse {
  transformation_id: string;
}

export const features = {
  auth: {
    login: (email: string, password: string) =>
      api<{ access_token: string; token_type: string; user: User }>('/api/auth/login', { method: 'POST', body: { email, password } }),
    register: (name: string, email: string, password: string) =>
      api<{ access_token: string; token_type: string; user: User }>('/api/auth/register', { method: 'POST', body: { name, email, password } }),
    me: () => api<{ user: User }>('/api/auth/me'),
  },

  users: {
    projects: () => api<{ projects: ProjectItem[] }>('/api/users/projects').then((r) => r.projects),
    update: (body: Partial<{ name: string; avatar_color: string }>) =>
      api<{ user: User }>('/api/users/me', { method: 'PATCH', body }).then((r) => r.user),
  },

  projects: {
    list: () => api<{ projects: ProjectItem[] }>('/api/users/projects').then((r) => r.projects),
    get: (id: string) => api<{ project: ProjectItem }>(`/api/projects/${id}`).then((r) => r.project),
    create: (name: string, description?: string) =>
      api<{ project: ProjectItem }>('/api/projects', { method: 'POST', body: { name, description: description ?? null } }).then((r) => r.project),
    update: (id: string, body: Partial<{ name: string; description: string; is_archived: boolean; is_favorite: boolean }>) =>
      api<{ project: ProjectItem }>(`/api/projects/${id}`, { method: 'PATCH', body }).then((r) => r.project),
    remove: (id: string) => api<{ ok: boolean }>(`/api/projects/${id}`, { method: 'DELETE' }),
    duplicate: (id: string) => api<{ project: ProjectItem }>(`/api/projects/${id}/duplicate`, { method: 'POST' }).then((r) => r.project),
  },

  datasets: {
    demos: () => api<{ datasets: { name: string; description: string }[] }>('/api/datasets/demo-list').then((r) => r.datasets),
    upload: (file: File, projectId: string, extra: File[] = []) => {
      const form = new FormData();
      form.append('file', file);
      form.append('project_id', projectId);
      for (const f of extra) form.append('files', f);
      return api<{ dataset: DatasetItem; preview: Preview }>('/api/datasets/upload', { method: 'POST', form });
    },
    importDemo: (name: string, projectId: string) =>
      api<{ dataset: DatasetItem; preview: Preview }>('/api/datasets/import-demo', { method: 'POST', body: { name, project_id: projectId } }),
    list: () => api<{ datasets: DatasetItem[] }>('/api/datasets').then((r) => r.datasets),
    get: (id: string) => api<{ dataset: DatasetItem }>(`/api/datasets/${id}`).then((r) => r.dataset),
    preview: (id: string, limit = 100, start = 0) =>
      api<Preview>(`/api/datasets/${id}/preview`, { method: 'POST', body: { limit: Math.min(limit, 500), start } }),
    profile: (id: string, refresh = false) =>
      api<{ profile: { row_count: number; column_count: number; null_cells: number; null_pct: number; columns: ProfileColumn[] }; quality: QualityResult; dataset: DatasetItem }>(
        `/api/datasets/${id}/profile${refresh ? '?refresh=true' : ''}`,
      ),
    clean: (id: string, operations: Record<string, unknown>[], note?: string) =>
      api<CleanResponse>(`/api/datasets/${id}/clean`, { method: 'POST', body: { operations, note: note ?? null } }),
    transform: (id: string, steps: Record<string, unknown>[], note?: string) =>
      api<TransformResponse>(`/api/datasets/${id}/transform`, { method: 'POST', body: { steps, note: note ?? null } }),
    versions: (id: string) =>
      api<{ versions: { id: string; version: number; note: string; created_at: string }[] }>(`/api/datasets/${id}/versions`).then((r) => r.versions),
    restore: (id: string, versionId: string) =>
      api<{ dataset: DatasetItem; preview: Preview }>(`/api/datasets/${id}/restore/${versionId}`, { method: 'POST' }),
    update: (id: string, body: Partial<{ name: string; description: string; tags: string[]; is_favorite: boolean }>) =>
      api<{ dataset: DatasetItem }>(`/api/datasets/${id}`, { method: 'PATCH', body }).then((r) => r.dataset),
    remove: (id: string) => api<{ ok: boolean }>(`/api/datasets/${id}`, { method: 'DELETE' }),
  },

  sql: {
    run: (opts: { sql: string; dataset_ids: string[]; save?: boolean; save_name?: string; project_id?: string; limit?: number }) =>
      api<SQLResult>('/api/sql/run', { method: 'POST', body: { ...opts, save: opts.save ?? false, save_name: opts.save_name ?? 'Untitled query', limit: opts.limit ?? 10000 } }),
    schema: () => api<{ tables: SQLTableSchema[] }>('/api/sql/schema').then((r) => r.tables),
    history: () => api<{ queries: SQLQueryItem[] }>('/api/sql/history').then((r) => r.queries),
    queries: () => api<{ queries: SQLQueryItem[] }>('/api/sql/queries').then((r) => r.queries),
    snippets: () => api<{ snippets: SQLSnippet[] }>('/api/sql/snippets').then((r) => r.snippets),
    snapshot: (opts: { sql: string; dataset_ids: string[]; project_id?: string; save_name?: string }) =>
      api<{ query: SQLQueryItem }>('/api/sql/snapshot', { method: 'POST', body: opts }),
  },

  charts: {
    schema: (datasetId: string) => api<{ columns: ChartSchemaColumn[] }>(`/api/charts/schema?dataset_id=${datasetId}`).then((r) => r.columns),
    recommend: (datasetId: string) =>
      api<{ recommendations: ChartRecommendation[] }>(`/api/charts/recommend?dataset_id=${datasetId}`).then((r) => r.recommendations),
    build: (datasetId: string, chartType: string, config: Record<string, unknown>) =>
      api<{ data: ChartData | null; error?: string | null; chart_type: string }>(`/api/charts/build?dataset_id=${datasetId}`, {
        method: 'POST',
        body: { chart_type: chartType, config, name: '', save: false },
      }),
    save: (datasetId: string, chartType: string, config: Record<string, unknown>, name: string) =>
      api<{ chart: ChartItem }>(`/api/charts/save?dataset_id=${datasetId}`, {
        method: 'POST',
        body: { chart_type: chartType, config, name, save: true },
      }).then((r) => r.chart),
    list: () => api<{ charts: ChartItem[] }>('/api/charts/saved').then((r) => r.charts),
    remove: (id: string) => api<{ ok: boolean }>(`/api/charts/${id}`, { method: 'DELETE' }),
  },

  stats: {
    descriptive: (datasetId: string, columns = '') =>
      api<{ result: StatsDescriptiveResult }>(`/api/statistics/descriptive?dataset_id=${datasetId}${columns ? `&columns=${encodeURIComponent(columns)}` : ''}`).then((r) => r.result),
    correlation: (datasetId: string, columns = '', method = 'pearson') =>
      api<{ result: { pairs: CorrelationPair[]; method: string } }>(
        `/api/statistics/correlation?dataset_id=${datasetId}${columns ? `&columns=${encodeURIComponent(columns)}` : ''}&method=${method}`,
      ).then((r) => r.result),
    test: (datasetId: string, test: string, params: Record<string, unknown>) =>
      api<{ result: StatsTestResult; analysis_id: string }>('/api/statistics/test', { method: 'POST', body: { test, params, dataset_id: datasetId } }).then((r) => r.result),
    regression: (datasetId: string, target: string, features = '') =>
      api<{ result: RegressionResult }>(
        `/api/statistics/linear-regression?dataset_id=${datasetId}&target=${encodeURIComponent(target)}${features ? `&features=${features.split(',').map(encodeURIComponent).join(',')}` : ''}`,
      ).then((r) => r.result),
    timeSeries: (datasetId: string, dateColumn: string, valueColumn: string, window = 7) =>
      api<{ result: TimeSeriesResult }>(
        `/api/statistics/time-series?dataset_id=${datasetId}&date_column=${encodeURIComponent(dateColumn)}&value_column=${encodeURIComponent(valueColumn)}&window=${window}`,
      ).then((r) => r.result),
    history: (datasetId: string) =>
      api<{ analyses: { id: string; kind: string; created_at: string }[] }>(`/api/statistics/history?dataset_id=${datasetId}`).then((r) => r.analyses),
  },

  ml: {
    train: (datasetId: string, target: string, body: Partial<{ features: string[]; task: string; algorithms: string[]; test_size: number }>) =>
      api<{ result: MLTrainResult; model_id: string }>(`/api/ml/train?dataset_id=${datasetId}&target=${encodeURIComponent(target)}`, { method: 'POST', body, timeout: 300000 }).then((r) => r.result),
    models: () => api<{ models: MLModelRecord[] }>('/api/ml/models').then((r) => r.models),
  },

  notebooks: {
    list: () => api<{ notebooks: NotebookItem[] }>('/api/notebooks').then((r) => r.notebooks),
    create: (name: string, projectId: string) => api<{ notebook: NotebookItem }>('/api/notebooks', { method: 'POST', body: { name, project_id: projectId } }).then((r) => r.notebook),
    get: (id: string) => api<{ notebook: NotebookItem }>(`/api/notebooks/${id}`).then((r) => r.notebook),
    update: (id: string, body: Partial<{ name: string; cells: unknown[] }>) =>
      api<{ notebook: NotebookItem }>(`/api/notebooks/${id}`, { method: 'PATCH', body }).then((r) => r.notebook),
    remove: (id: string) => api<{ ok: boolean }>(`/api/notebooks/${id}`, { method: 'DELETE' }),
    run: (id: string, code: string, datasetId: string) =>
      api<{ output: NotebookRunOutput }>(`/api/notebooks/${id}/run-cell`, { method: 'POST', body: { code, dataset_id: datasetId }, timeout: 180000 }).then((r) => r.output),
  },

  ai: {
    conversations: () => api<{ conversations: Conversation[] }>('/api/ai/conversations').then((r) => r.conversations),
    createConversation: () => api<{ conversation: Conversation }>('/api/ai/conversations', { method: 'POST' }).then((r) => r.conversation),
    getConversation: (id: string) =>
      api<{ conversation: Conversation; messages: AIMessage[] }>(`/api/ai/conversations/${id}`).then((r) => ({ ...r.conversation, messages: r.messages })),
    ask: (datasetId: string, message: string, conversationId: string) =>
      api<{ message: AIMessage; conversation: Conversation }>('/api/ai/ask', {
        method: 'POST',
        body: { message, dataset_id: datasetId, conversation_id: conversationId ?? null },
        timeout: 180000,
      }),
  },

  reports: {
    create: (projectId: string, name: string, description?: string, template = 'default') =>
      api<{ report: ReportItem }>('/api/reports', { method: 'POST', body: { project_id: projectId, name, description: description ?? null, template } }).then((r) => r.report),
    get: (id: string) => api<{ report: ReportItem }>(`/api/reports/${id}`).then((r) => r.report),
    update: (id: string, body: Partial<{ name: string; description: string; sections: unknown[]; template: string }>) =>
      api<{ report: ReportItem }>(`/api/reports/${id}`, { method: 'PATCH', body }).then((r) => r.report),
    previewHtml: (id: string) => api<{ html: string }>(`/api/reports/${id}/preview`, { method: 'POST' }).then((r) => r.html),
    export: (id: string, format: 'html' | 'pdf' | 'markdown' | 'docx') =>
      api<{ file: string; url: string; format: string }>(`/api/reports/${id}/export?format=${format}`, { method: 'POST' }),
    remove: (id: string) => api<{ ok: boolean }>(`/api/reports/${id}`, { method: 'DELETE' }),
    list: () => api<{ reports: ReportItem[] }>('/api/reports').then((r) => r.reports),
  },

  dashboards: {
    list: () => api<{ dashboards: DashboardItem[] }>('/api/dashboards').then((r) => r.dashboards),
    create: (projectId: string, name: string, description?: string) =>
      api<{ dashboard: DashboardItem }>('/api/dashboards', { method: 'POST', body: { project_id: projectId, name, description: description ?? null } }).then((r) => r.dashboard),
    get: (id: string) => api<{ dashboard: DashboardItem }>(`/api/dashboards/${id}`).then((r) => r.dashboard),
    update: (id: string, body: Partial<{ name: string; description: string; layout: unknown[] }>) =>
      api<{ dashboard: DashboardItem }>(`/api/dashboards/${id}`, { method: 'PATCH', body }).then((r) => r.dashboard),
    remove: (id: string) => api<{ ok: boolean }>(`/api/dashboards/${id}`, { method: 'DELETE' }),
  },

  exportData: {
    run: (body: { format: string; dataset_id?: string; query_id?: string; sql?: string; project_id?: string; limit?: number }) =>
      api<{ file: string; url: string; format: string }>('/api/export', { method: 'POST', body: { ...body, limit: body.limit ?? 100000 } }),
  },

  jobs: {
    list: () => api<{ jobs: JobItem[] }>('/api/jobs').then((r) => r.jobs),
  },

  search: {
    all: (q: string) => api<{ results: SearchResult }>(`/api/search?q=${encodeURIComponent(q)}`).then((r) => r.results),
  },

  spreadsheet: {
    createWorkbook: (datasetId: string, sheetName = 'Sheet1', rows = 100, cols = 26) =>
      api<{ workbook_id: string; sheets: string[]; message: string }>('/api/spreadsheet/workbook', {
        method: 'POST',
        body: { dataset_id: datasetId, sheet_name: sheetName, rows, cols },
      }),
    getWorkbook: (workbookId: string) =>
      api<{ workbook_id: string; sheets: Record<string, { rows: number; cols: number; formulas: number }>; named_ranges: string[] }>(`/api/spreadsheet/workbook/${workbookId}`),
    evaluateFormula: (workbookId: string, formula: string, sheetName: string, row: number, col: number) =>
      api<{ value: unknown; error: string | null; dependencies: string[]; dependents: string[] }>(`/api/spreadsheet/workbook/${workbookId}/evaluate`, {
        method: 'POST',
        body: { formula, sheet_name: sheetName, row, col },
      }),
    setCell: (workbookId: string, sheetName: string, row: number, col: number, value: unknown, formula?: string) =>
      api<{ value: unknown; recalculated: Record<string, unknown>; error: string | null }>(`/api/spreadsheet/workbook/${workbookId}/cell`, {
        method: 'POST',
        body: { workbook_id: workbookId, sheet_name: sheetName, row, col, value, formula },
      }),
    recalculate: (workbookId: string, changedCells: [string, number, number][]) =>
      api<{ recalculated: Record<string, unknown>; count: number }>(`/api/spreadsheet/workbook/${workbookId}/recalculate`, {
        method: 'POST',
        body: { changed_cells: changedCells },
      }),
    getDependencies: (workbookId: string) =>
      api<{ nodes: { id: string; label: string; formula: string; type: string }[]; edges: { from: string; to: string }[] }>(`/api/spreadsheet/workbook/${workbookId}/dependencies`),
    createNamedRange: (workbookId: string, name: string, sheetName: string, startRow: number, startCol: number, endRow: number, endCol: number) =>
      api<{ name: string; reference: string }>(`/api/spreadsheet/workbook/${workbookId}/named-range`, {
        method: 'POST',
        body: { workbook_id: workbookId, name, sheet_name: sheetName, start_row: startRow, start_col: startCol, end_row: endRow, end_col: endCol },
      }),
    listNamedRanges: (workbookId: string) =>
      api<{ named_ranges: Record<string, string> }>(`/api/spreadsheet/workbook/${workbookId}/named-ranges`),
    autocomplete: (workbookId: string, sheetName: string, partial: string, row: number, col: number) =>
      api<{ suggestions: { label: string; type: string; detail: string; documentation?: string }[] }>(`/api/spreadsheet/workbook/${workbookId}/autocomplete`, {
        method: 'POST',
        body: { workbook_id: workbookId, sheet_name: sheetName, partial, row, col },
      }),
    listFunctions: () =>
      api<{ functions: { name: string; min_args: number; max_args: number; variadic: boolean; categories: string[] }[]; categories: Record<string, { name: string; min_args: number; max_args: number; variadic: boolean; categories: string[] }[]> }>('/api/spreadsheet/functions'),
  },
};

export function blobDownload(url: string, fallbackName = 'export') {
  const a = document.createElement('a');
  a.href = url;
  a.download = fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
}