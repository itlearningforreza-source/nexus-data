import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Download, Table2 } from 'lucide-react';
import { Button, EmptyState } from '@/components/ui';
import { toast } from '@/components/ui';
import { cellToString, formatCompact, formatNumber } from '@/lib/format';

export interface TableLike {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated?: boolean;
}

export function DataTable({ data, height = 380, pageRows = 50, loading }: { data: TableLike | null; height?: number; pageRows?: number; loading?: boolean }) {
  const [page, setPage] = useState(0);
  const total = data?.row_count ?? 0;
  const pages = Math.max(1, Math.ceil(total / pageRows));
  const start = page * pageRows;
  const slice = (data?.rows ?? []).slice(start, start + pageRows);

  useEffect(() => {
    if (page >= pages) setPage(0);
  }, [pages, page]);

  const exportCsv = () => {
    if (!data) return;
    try {
      const esc = (v: unknown) => {
        const s = cellToString(v);
        return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
      };
      const csv = [data.columns.map(esc).join(','), ...data.rows.map((r) => r.map(esc).join(','))].join('\n');
      const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'data.csv';
      a.click();
      URL.revokeObjectURL(a.href);
      toast('Exported', 'CSV downloaded.', 'success');
    } catch {
      toast('Export failed', 'Could not export.', 'error');
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground"><span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" /> Loading…</div>;
  }

  if (!data || !data.columns.length) {
    return <EmptyState icon={<Table2 className="h-8 w-8" />} title="No data" description="Nothing to display for this dataset." />;
  }

  return (
    <div className="flex flex-col" style={{ height: 'auto' }}>
      <div className="scrollbar-thin overflow-auto rounded-xl border border-border" style={{ height }}>
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="sticky top-0 z-10 bg-muted/95 backdrop-blur">
              <th className="w-12 border-b border-border bg-muted/80 px-2 py-2 text-center font-mono text-[10px] text-muted-foreground"></th>
              {data.columns.map((c, i) => (
                <th key={c + i} className="whitespace-nowrap border-b border-border px-3 py-2 font-semibold text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <span className="font-mono text-[9px] text-muted-foreground/50">{i}</span>
                    {c}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {slice.map((row, ri) => (
              <tr key={start + ri} className={start + ri % 2 === 1 ? 'bg-muted/40' : ''}>
                <td className="border-r border-border/60 px-2 py-1.5 text-center font-mono text-[10px] text-muted-foreground/60">{start + ri + 1}</td>
                {row.map((v, ci) => {
                  const s = cellToString(v);
                  return (
                    <td key={ci} className="whitespace-nowrap border-b border-border/60 px-3 py-1.5">
                      <span className="tabular-nums text-foreground">{s === '' ? <span className="text-muted-foreground/50">—</span> : s}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {slice.length < total && (
          <div className="sticky bottom-0 flex items-center justify-center gap-2 border-t border-border bg-muted/90 py-2 text-[11px] text-muted-foreground backdrop-blur">
            Showing {start + 1}–{start + slice.length} of {formatCompact(total)} rows
          </div>
        )}
      </div>
      <div className="mt-2 flex items-center justify-between">
        <div className="text-[11px] text-muted-foreground">
          {data.row_count > (data.rows?.length ?? 0) ? `${formatCompact(data.rows?.length ?? 0)} rows loaded` : `${formatCompact(total)} rows`}
          {data.truncated && ' · truncated'}
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="xs" leftIcon={<Download className="h-3 w-3" />} onClick={exportCsv}>CSV</Button>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="min-w-16 text-center text-[11px] text-muted-foreground tabular-nums">
              {page + 1} / {pages}
            </span>
            <Button variant="ghost" size="icon" disabled={page >= pages - 1} onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function DataTableStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-border bg-card px-3.5 py-2.5">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm font-semibold tabular-nums">{typeof value === 'number' ? formatNumber(value) : value}</div>
    </div>
  );
}