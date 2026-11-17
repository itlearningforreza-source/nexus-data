import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Play, Save, Download, Clock, Table2, BookOpen, Database, ChevronRight, ChevronDown,
} from 'lucide-react';
import { features } from '@/lib/features';
import { Card, Button, Select, Badge } from '@/components/ui';
import { toast } from '@/components/ui';
import { DataTable } from '@/components/dataset/DataTable';
import type { SQLResult } from '@/lib/types';
import { formatNumber } from '@/lib/format';

const SNIPPETS = [
  { name: 'All rows', sql: 'SELECT * FROM "{table}" LIMIT 100;' },
  { name: 'Top rows by column', sql: 'SELECT * FROM "{table}" ORDER BY "{column}" DESC LIMIT 50;' },
  { name: 'Group by + agg', sql: 'SELECT "{column}", COUNT(*) AS count, AVG("{aggregate}") AS avg\nFROM "{table}"\nGROUP BY 1\nORDER BY 2 DESC;' },
  { name: 'Filter', sql: 'SELECT * FROM "{table}"\nWHERE "{column}" > 0 AND "{column}" IS NOT NULL\nLIMIT 100;' },
  { name: 'Row count', sql: 'SELECT COUNT(*) AS row_count\nFROM "{table}";' },
  { name: 'Column distinct', sql: 'SELECT DISTINCT {columncols}\nFROM "{table}"\nLIMIT 50;' },
  { name: 'Summary stats', sql: 'SELECT COUNT(*) AS n,\n       AVG("{aggregate}") AS mean,\n       MIN("{aggregate}") AS min,\n       MAX("{aggregate}") AS max\nFROM "{table}";' },
  { name: 'Join two tables', sql: 'SELECT a.*, b.*\nFROM "{table}" a\nLEFT JOIN "{table2}" b ON a.id = b.id\nLIMIT 100;' },
];

export default function SqlWorkbench() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sql, setSql] = useState('');
  const [activeDataset, setActiveDataset] = useState(searchParams.get('dataset') ?? 'all');
  const [savedName, setSavedName] = useState('');
  const [showSave, setShowSave] = useState(false);
  const [result, setResult] = useState<SQLResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState(true);
  const [tablesOpen, setTablesOpen] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false);
  const taRef = useRef<HTMLTextAreaElement>(null);

  const { data: datasets } = useQuery({ queryKey: ['datasets'], queryFn: () => features.datasets.list() });
  const { data: schema, refetch: refetchSchema } = useQuery({ queryKey: ['sql-schema'], queryFn: () => features.sql.schema() });
  const { data: history } = useQuery({ queryKey: ['sql-history'], queryFn: () => features.sql.history() });
  const { data: snippets } = useQuery({ queryKey: ['sql-snippets'], queryFn: () => features.sql.snippets() });

  useEffect(() => {
    const ds = searchParams.get('dataset');
    if (ds) setActiveDataset(ds);
  }, [searchParams]);

  const datasetIds = useMemo(() => {
    if (!datasets) return [];
    return activeDataset === 'all' ? datasets.map((d) => d.id) : [activeDataset];
  }, [datasets, activeDataset]);

  const tableFor = (datasetId: string) => schema?.find((t) => t.dataset_id === datasetId)?.table_name;

  const insertAtCursor = (text: string) => {
    setSummary(false);
    const el = taRef.current;
    if (!el) { setSql((s) => s + text); return; }
    const start = el.selectionStart ?? sql.length;
    const end = el.selectionEnd ?? sql.length;
    setSql(sql.slice(0, start) + text + sql.slice(end));
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(start + text.length, start + text.length);
    });
  };

  const runSql = async (value?: string, save = false) => {
    const body = value ?? sql;
    if (!body.trim()) return;
    setBusy(true);
    try {
      const res = await features.sql.run({ sql: body, dataset_ids: datasetIds, save, save_name: savedName || 'Untitled query' });
      setResult(res);
      refetchSchema();
      toast(save ? 'Query saved' : 'Query ran', `${res.row_count.toLocaleString()} rows in ${res.execution_time_ms}ms.`, save ? 'success' : undefined);
    } catch (e) {
      toast('Query failed', e instanceof Error ? e.message : 'Could not run query.', 'error');
    } finally {
      setBusy(false);
      setShowSave(false);
    }
  };

  const exportCsv = () => {
    if (!result) return;
    const header = result.columns.join(',');
    const lines = result.rows.map((r) =>
      r.map((v) => {
        const s = v === null || v === undefined ? '' : String(v);
        return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
      }).join(','));
    const blob = new Blob([[header, ...lines].join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'query-result.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const applySnippet = (s: { name: string; sql: string }) => {
    if (!schema?.length) return;
    const table = activeDataset === 'all'
      ? schema[0].name
      : (tableFor(activeDataset) ?? schema[0].name);
    const find = async (tblName: string) => {
      const cols = schema?.find((t) => t.name === tblName)?.columns ?? [];
      setSql(
        s.sql
          .replace('{table2}', schema?.find((t) => t.name !== tblName)?.name ?? tblName)
          .replace('{columncols}', cols.slice(0, 5).map((c) => `"${c.name}"`).join(', '))
          .replace('{column}', cols?.[0]?.name ?? 'id')
          .replace('{aggregate}', cols.map((c) => c.name).find((c) => ['integer', 'real', 'float', 'double'].some((x) => String(cols.find((cl) => cl.name === c)?.type).toLowerCase().includes(x))) ?? cols?.[0]?.name ?? 'id')
          .replace('{table}', tblName),
      );
    };
    find(table);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-auto text-xl font-semibold tracking-tight">SQL Workbench</h1>
        <Badge tone="blue"><Database className="mr-1 h-3 w-3" /> {datasetIds.length} table(s) selected</Badge>
      </div>

      <div className="grid gap-4 xl:grid-cols-[240px_1fr_260px]">
        <div className="space-y-4">
          <Card className="p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-semibold"><Table2 className="h-3.5 w-3.5 text-primary" /> Tables</span>
              <button onClick={() => setTablesOpen((o) => !o)}>{tablesOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}</button>
            </div>
            {tablesOpen && (
              <div className="space-y-2">
                {(schema ?? []).map((t) => (
                  <div key={t.dataset_id}>
                    <button className="w-full rounded-lg bg-muted/40 px-2 py-1.5 text-left text-[11px] font-semibold transition hover:bg-muted"
                      onDoubleClick={() => insertAtCursor(`"${t.name}"`)} onClick={() => setActiveDataset(t.dataset_id)}>
                      {t.name} <span className="float-right text-[10px] font-normal text-muted-foreground">{t.row_count.toLocaleString()}</span>
                    </button>
                    <div className="mt-1 flex flex-wrap gap-1 pl-1.5">
                      {t.columns.slice(0, 8).map((c) => (
                        <button key={c.name} className="rounded border border-border/60 px-1 py-px text-[10px] font-mono text-muted-foreground hover:text-primary"
                          onClick={() => insertAtCursor(`"${t.name}"."${c.name}"`)} title={`${c.type}`}>
                          {c.name}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
                {(schema ?? []).length === 0 && <p className="text-[11px] text-muted-foreground">No tables yet — upload a dataset first.</p>}
              </div>
            )}
          </Card>

          <Card className="p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-semibold"><BookOpen className="h-3.5 w-3.5 text-primary" /> Snippets</span>
            </div>
            <div className="space-y-1">
              {(snippets ?? []).slice(0, 8).map((s) => (
                <button key={s.id} className="w-full rounded-lg px-2 py-1 text-left text-[11px] text-muted-foreground transition hover:bg-muted hover:text-foreground"
                  onClick={() => applySnippet({ name: s.name, sql: s.sql })}>
                  {s.name}
                </button>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-3">
          <Card className="overflow-hidden p-0">
            <div className="flex items-center gap-2 border-b border-border px-3 py-2">
              <Select value={activeDataset} onChange={(e) => { setActiveDataset(e.target.value); setSearchParams(e.target.value === 'all' ? {} : { dataset: e.target.value }); }} className="w-48">
                <option value="all">All datasets</option>
                {(datasets ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </Select>
              {showSave && (
                <input value={savedName} onChange={(e) => setSavedName(e.target.value)} placeholder="Query name"
                  className="h-8 w-44 rounded-lg border border-input bg-card px-2.5 text-xs outline-none focus:border-primary/50" />
              )}
              <div className="ml-auto flex items-center gap-1.5">
                <Button size="sm" variant="ghost" onClick={() => setShowSave((s) => !s)}><Save className="h-3.5 w-3.5" /> Save</Button>
                <Button size="sm" onClick={() => { if (showSave && savedName) setShowSave(false); runSql(undefined, showSave); }} loading={busy}>
                  <Play className="h-3.5 w-3.5" /> Run
                </Button>
              </div>
            </div>
            <textarea ref={taRef} value={sql} onChange={(e) => { setSql(e.target.value); setSummary(false); }}
              placeholder={`-- Write SQL. Tables: ${(schema ?? []).map((t) => t.name).join(', ') || 'none yet'}\nSELECT * FROM "${schema?.[0]?.name ?? 'my_table'}" LIMIT 100`}
              spellCheck={false}
              className="h-64 w-full resize-y bg-card p-3 font-mono text-[12.5px] leading-relaxed outline-none placeholder:text-muted-foreground/40"
            />
            {summary && <div className="border-t border-border bg-muted/30 px-3 py-1.5 text-[11px] text-muted-foreground">Ctrl/Cmd + Enter to run · double-click a table/column to insert</div>}
            <div className="flex flex-wrap gap-1.5 border-t border-border px-3 py-2">
              {SNIPPETS.map((s) => (
                <button key={s.name} className="rounded-lg bg-muted px-2 py-1 text-[10px] font-medium text-muted-foreground transition hover:text-foreground"
                  onClick={() => applySnippet(s)}>
                  {s.name}
                </button>
              ))}
            </div>
          </Card>

          {result && (
            <Card className="p-0">
              <div className="flex items-center justify-between border-b border-border px-3 py-2">
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-semibold">Result</span>
                  <Badge tone="muted">{result.row_count.toLocaleString()} rows</Badge>
                  <Badge tone="muted">{result.execution_time_ms}ms</Badge>
                  {result.truncated && <Badge tone="orange">truncated</Badge>}
                </div>
                <div className="flex items-center gap-1.5">
                  <Button size="sm" variant="ghost" onClick={exportCsv}><Download className="h-3.5 w-3.5" /> CSV</Button>
                </div>
              </div>
              <DataTable data={result} height={420} />
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <Card className="p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-semibold"><Clock className="h-3.5 w-3.5 text-primary" /> History</span>
              <button onClick={() => setHistoryOpen((o) => !o)}>{historyOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}</button>
            </div>
            {historyOpen && (
              <div className="mt-2 space-y-1">
                {(history ?? []).slice(0, 12).map((q) => (
                  <button key={q.id} className="w-full truncate rounded-lg px-2 py-1.5 text-left text-[11px] transition hover:bg-muted"
                    onClick={() => { setSql(q.sql); setSummary(false); }}>
                    <span className="block truncate font-mono text-[10.5px] text-foreground/90">{q.sql.split('\n')[0]}</span>
                    <span className="mt-0.5 block text-[10px] text-muted-foreground">{q.is_saved ? `Saved · ${q.name}` : 'Ran'} · {q.row_count} rows</span>
                  </button>
                ))}
                {(history ?? []).length === 0 && <p className="text-[11px] text-muted-foreground">No history yet.</p>}
              </div>
            )}
          </Card>
          {result && (
            <Card className="p-3">
              <div className="text-xs font-semibold">Query stats</div>
              <div className="mt-2 space-y-1.5 text-[11px] text-muted-foreground">
                <div className="flex justify-between"><span>Bytes</span><span className="font-mono text-foreground">{formatNumber(result.byte_size)}</span></div>
                <div className="flex justify-between"><span>Truncated</span><span className="font-mono text-foreground">{result.truncated ? 'yes' : 'no'}</span></div>
                {result.query_id && <div className="flex justify-between"><span>Saved id</span><span className="max-w-[120px] truncate font-mono text-foreground">{result.query_id}</span></div>}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}