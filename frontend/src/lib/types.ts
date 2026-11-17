export interface User {
  id: number;
  email: string;
  name: string;
  avatar_color: string;
  created_at: string;
}

export interface ProjectItem {
  id: string;
  name: string;
  description: string | null;
  owner_id: number;
  is_archived: boolean;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
  counts?: {
    datasets: number;
    charts: number;
    dashboards: number;
    notebooks: number;
    reports: number;
    models?: number;
  };
}

export interface DatasetColumn {
  id: string;
  name: string;
  index: number;
  data_type: string;
  nullable: boolean;
}

export interface DatasetItem {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  source_type: string;
  original_filename: string | null;
  format: string;
  version: number;
  row_count: number;
  column_count: number;
  size_bytes: number;
  quality_score: number | null;
  tags: string[];
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
  columns?: DatasetColumn[];
}

export interface Preview {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
}

export interface ProfileColumnStats {
  count?: number;
  min?: number;
  max?: number;
  range?: number;
  mean?: number;
  median?: number;
  sum?: number;
  std?: number;
  var?: number;
  first_quartile?: number;
  third_quartile?: number;
  iqr?: number;
  p5?: number;
  p25?: number;
  p50?: number;
  p75?: number;
  p95?: number;
  p99?: number;
  skewness?: number;
  kurtosis?: number;
  mode?: number | string;
}

export interface ProfileColumn {
  name: string;
  dtype: 'integer' | 'float' | 'boolean' | 'datetime' | 'categorical' | 'object';
  pandas_dtype: string;
  numeric: boolean;
  null_count: number;
  null_pct: number;
  unique_count: number;
  cardinality_ratio: number;
  total: number;
  sample: unknown[];
  stats: ProfileColumnStats;
  top_values: { value: unknown; count: number; pct: number }[];
}

export interface ProfileResponse {
  row_count: number;
  column_count: number;
  null_cells: number;
  null_pct: number;
  columns: ProfileColumn[];
}

export interface QualityIssue {
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  column: string | null;
  message: string;
  remediation: string;
}

export interface QualityResult {
  score: number;
  subscores: { completeness: number; validity: number; consistency: number; uniqueness: number };
  issues: QualityIssue[];
  issues_count: number;
  row_count: number;
  duplicate_rows: number;
  missing_count: number;
}

export interface ProfileQualityResponse {
  profile: ProfileResponse;
  quality: QualityResult;
  dataset: DatasetItem;
}

export interface ChartData {
  labels?: string[];
  values?: number[];
  series?: { name: string; values: number[] }[];
  stacked?: boolean;
  hundred?: boolean;
  grouped?: boolean;
  x_column?: string;
  y_column?: string;
  color_column?: string;
  points?: { x: number; y: number; size?: number; color?: string; label?: string }[];
  kpi?: { label: string; value: number | string; aggregation: string; column: string; row_count: number };
  gauge?: { value: number; min: number; max: number; label: string };
  boxes?: { name: string; min: number; q1: number; median: number; q3: number; max: number; outliers: number[]; count: number }[];
  categories?: string[];
  values_raw?: number[];
  column?: string;
  group_by?: string;
  edges?: number[];
  columns?: string[];
  rows?: unknown[][];
  row_count?: number;
  bins?: number;
  [key: string]: unknown;
}

export interface ChartItem {
  id: string;
  name: string;
  chart_type: string;
  config: Record<string, unknown>;
  dataset_id: string;
  project_id: string;
  data: ChartData | null;
  created_at: string;
}

export interface ChartRecommendation {
  chart_type: string;
  x: string;
  y: string;
  dimension: string;
  measure: string;
  reason: string;
}

export interface ChartSchemaColumn {
  name: string;
  type: 'numeric' | 'datetime' | 'boolean' | 'categorical';
  distinct_count: number;
  null_pct: number;
}

export interface SQLQueryItem {
  id: string;
  sql: string;
  name: string;
  is_saved: boolean;
  project_id: string | null;
  dataset_id: string | null;
  execution_time_ms: number;
  row_count: number;
  created_at: string;
  updated_at: string;
}

export interface SQLResult {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
  execution_time_ms: number;
  byte_size: number;
  query_id?: string;
}

export interface SQLTableSchema {
  dataset_id: string;
  name: string;
  table_name: string;
  columns: { name: string; type: string }[];
  row_count: number;
}

export interface SQLSnippet {
  id: string;
  name: string;
  sql: string;
  description: string;
}

export interface StatsDescriptiveResult {
  columns: Record<
    string,
    {
      count: number;
      missing: number;
      mean: number;
      median: number;
      mode: unknown;
      std: number;
      var: number;
      min: number;
      max: number;
      range: number;
      q1: number;
      q3: number;
      iqr: number;
      skewness: number;
      kurtosis: number;
      percentiles: Record<string, number>;
    }
  >;
}

export interface CorrelationPair {
  x: string;
  y: string;
  r: number;
  p_value: number;
  n: number;
  strength: string;
  significant: boolean;
}

export interface StatsTestResult {
  test: string;
  statistic: number;
  p_value: number;
  sample_size: number;
  interpretation: string;
  significant: boolean;
  [key: string]: unknown;
}

export interface RegressionResult {
  test: string;
  r_squared: number;
  adjusted_r_squared: number;
  rmse: number;
  mae: number;
  mse: number;
  observations: number;
  features: string[];
  coefficients: { feature: string; coefficient: number; std_error: number; t_stat: number; p_value: number; significant: boolean }[];
  equation: string;
  interpretation: string;
}

export interface TimeSeriesResult {
  series: { date: string; value: number; moving_average: number | null }[];
  trend: { slope: number; direction: string };
  growth: { mean: number; cagr: number };
  count: number;
  start: string;
  end: string;
  freq: string;
  window: number;
}

export interface MLModelItem {
  algorithm: string;
  metrics: Record<string, unknown>;
  duration_ms: number;
}

export interface MLTrainResult {
  task: string;
  target: string;
  features: string[];
  sample_size: number;
  train_size: number;
  test_size: number;
  models: MLModelItem[];
  best_model: string;
  best_metric: number;
  best_metrics: Record<string, unknown>;
  feature_importance: { feature: string; importance: number; normalized: number }[];
}

export interface MLModelRecord {
  id: string;
  name: string;
  task: string;
  target: string;
  metrics: Record<string, unknown>;
  feature_importance: { feature: string; importance: number; normalized: number }[];
  dataset_id: string;
  created_at: string;
}

export interface NotebookCell {
  type: 'code' | 'markdown';
  content: string;
}

export interface NotebookItem {
  id: string;
  name: string;
  cells: NotebookCell[];
  project_id: string;
  version: number;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
}

export interface NotebookRunOutput {
  stdout: string;
  figures: string[];
  df_preview: { columns: string[]; rows: unknown[][]; shape: number[]; dtypes: Record<string, string> } | null;
  vars: { name: string; type: string; value?: string }[];
  error: string | null;
}

export interface AIArtifact {
  type: 'chart';
  chart_type: string;
  config: Record<string, unknown>;
  data: ChartData | null;
  error: string | null;
}

export interface AIMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  artifacts: AIArtifact[];
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ReportSection {
  type: string;
  content?: string;
  text?: string;
  title?: string;
  dataset_id?: string;
  column?: string;
  aggregation?: string;
  chart_id?: string;
  columns?: string[];
  config?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ReportItem {
  id: string;
  name: string;
  description: string | null;
  sections: ReportSection[];
  template: string;
  project_id: string;
  version: number;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
}

export interface DashboardItem {
  id: string;
  name: string;
  description: string | null;
  layout: Record<string, unknown>[];
  project_id: string;
  version: number;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
}

export interface JobItem {
  id: string;
  name: string;
  task: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  result: unknown;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface DemoEntry {
  name: string;
  description: string;
}

export interface SearchResult {
  projects: { id: string; name: string; description: string | null; type: 'project' }[];
  datasets: (DatasetItem & { type: 'dataset' })[];
  charts: { id: string; name: string; type: 'chart'; chart_type: string; dataset_id: string }[];
  dashboards: { id: string; name: string; type: 'dashboard' }[];
  reports: { id: string; name: string; type: 'report' }[];
  queries: { id: string; name: string; sql: string; type: 'query' }[];
  notebooks: { id: string; name: string; type: 'notebook' }[];
  columns: { dataset_id: string; dataset_name: string; name: string; type: 'column' }[];
}

export interface ArtifactPrepared {
  type: 'chart';
  chart_type: string;
  data: ChartData | null;
}