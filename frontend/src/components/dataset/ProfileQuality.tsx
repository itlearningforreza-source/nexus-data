import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ShieldAlert, Columns, Rows } from 'lucide-react';
import { features } from '@/lib/features';
import { Card, Badge, cn } from '@/components/ui';
import { LoadingBlock } from '@/components/ui';
import { formatNumber, formatCompact, cellToString } from '@/lib/format';
import type { ProfileQualityResponse, ProfileColumn } from '@/lib/types';

function dtypeTone(dtype: string) {
  if (dtype === 'integer' || dtype === 'float') return 'blue';
  if (dtype.startsWith('datetime')) return 'purple';
  if (dtype === 'boolean') return 'green';
  return 'orange';
}

function ColCard({ col, totalRows }: { col: ProfileColumn; totalRows: number }) {
  const stats = col.stats ?? {};
  const isNum = col.numeric;
  const pct = (v?: number) => (v !== undefined && totalRows ? ((v / totalRows) * 100) : 0);

  const bars = useMemo(() => {
    const v = col.top_values ?? [];
    if (!v.length) return null;
    return v.slice(0, 6);
  }, [col.top_values]);

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-[13px] font-semibold">{col.name}</div>
          <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-muted-foreground">
            <Badge tone={dtypeTone(col.dtype) as 'blue'}>{col.dtype}</Badge>
            <span>{formatCompact(col.null_count + col.unique_count)} values</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs font-bold tabular-nums">{formatNumber(100 - col.null_pct * 100, { maximumFractionDigits: 0 })}%</div>
          <div className="text-[9px] text-muted-foreground">complete</div>
        </div>
      </div>

      <div className="flex gap-0.5">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-chart-green" style={{ width: `${(1 - col.null_pct) * 100}%` }} />
        </div>
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div className={cn('h-full rounded-full', (col.cardinality_ratio ?? 1) > 0.5 ? 'bg-chart-blue' : 'bg-chart-orange')} style={{ width: `${Math.min(100, (col.cardinality_ratio ?? 1) * 100)}%` }} />
        </div>
      </div>
      <div className="flex justify-between text-[9px] text-muted-foreground">
        <span>{col.null_count} nulls</span>
        <span>{formatCompact(col.unique_count)} unique</span>
      </div>

      {isNum && stats && (
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-border/60 pt-2.5 text-[10px]">
          <div className="flex justify-between"><span className="text-muted-foreground">Min</span><span className="tabular-nums">{formatNumber(stats.min)}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Max</span><span className="tabular-nums">{formatNumber(stats.max)}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Mean</span><span className="tabular-nums">{formatNumber(stats.mean)}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Median</span><span className="tabular-nums">{formatNumber(stats.median)}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Std dev</span><span className="tabular-nums">{formatNumber(stats.std)}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Skew</span><span className="tabular-nums">{formatNumber(stats.skewness)}</span></div>
        </div>
      )}

      {bars && (
        <div className="border-t border-border/60 pt-2.5">
          <div className="mb-1 text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">Top values</div>
          <div className="space-y-1">
            {bars.map((t, i) => {
              const max = bars[0]?.count || 1;
              return (
                <div key={i} className="flex items-center gap-2">
                  <span className="w-20 truncate text-[10px] text-muted-foreground">{cellToString(t.value) || '∅'}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded bg-muted">
                    <div className="h-full rounded bg-chart-blue/70" style={{ width: `${(t.count / max) * 100}%` }} />
                  </div>
                  <span className="w-10 text-right text-[9px] tabular-nums text-muted-foreground">{pct(t.count).toFixed(0)}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
}

export function ProfileQualityView({ datasetId }: { datasetId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['profile', datasetId],
    queryFn: () => features.datasets.profile(datasetId),
  });

  if (isLoading) return <LoadingBlock label="Profiling dataset…" />;
  const res = data as ProfileQualityResponse | undefined;
  if (!res) return null;
  const { profile, quality } = res;

  const sevTone = (s: string) => (s === 'critical' ? 'red' : s === 'high' ? 'red' : s === 'medium' ? 'orange' : 'muted');
  const scoreColor = quality.score >= 95 ? 'text-chart-green' : quality.score >= 80 ? 'text-chart-orange' : 'text-destructive';

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-4">
        {[
          { label: 'Rows', value: formatCompact(profile.row_count), icon: <Rows className="h-4 w-4" />, tone: 'text-chart-blue' },
          { label: 'Columns', value: String(profile.column_count), icon: <Columns className="h-4 w-4" />, tone: 'text-chart-purple' },
          { label: 'Missing cells', value: formatCompact(profile.null_cells), icon: <ShieldAlert className="h-4 w-4" />, tone: 'text-warning' },
          { label: 'Quality score', value: String(quality.score ?? '—'), icon: <ShieldAlert className="h-4 w-4" />, tone: scoreColor },
        ].map((s) => (
          <Card key={s.label} className="flex items-center gap-3 p-4">
            <div className={s.tone}>{s.icon}</div>
            <div>
              <div className="text-lg font-bold leading-none tabular-nums">{s.value}</div>
              <div className="mt-1 text-[10px] text-muted-foreground">{s.label}</div>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <div>
          <div className="mb-2 text-xs font-semibold">Columns ({profile.columns.length})</div>
          <div className="grid max-h-[560px] gap-3 overflow-y-auto pr-1 scrollbar-thin sm:grid-cols-2 xl:grid-cols-3">
            {profile.columns.map((c) => <ColCard key={c.name} col={c} totalRows={profile.row_count} />)}
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold">Data quality</span>
            <Badge tone={quality.score >= 95 ? 'green' : quality.score >= 80 ? 'orange' : 'red'}>{quality.score}/100</Badge>
          </div>
          <Card className="p-4">
            <div className="mb-3 flex items-center gap-4">
              {Object.entries(quality.subscores).map(([k, v]) => (
                <div key={k} className="flex-1">
                  <div className="mb-1 flex items-center justify-between text-[9px] uppercase tracking-wide text-muted-foreground">
                    <span>{k}</span><span className="tabular-nums">{v.toFixed(0)}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full bg-chart-blue" style={{ width: `${v}%` }} />
                  </div>
                </div>
              ))}
            </div>
            <div className="space-y-2">
              {quality.issues.length === 0 && (
                <div className="py-4 text-center text-xs text-chart-green">No quality issues — clean as a whistle.</div>
              )}
              {quality.issues.map((issue, i) => (
                <div key={i} className="flex items-start gap-2.5 rounded-xl border border-border bg-muted/30 px-3 py-2">
                  <ShieldAlert className={cn('mt-0.5 h-3.5 w-3.5 shrink-0', issue.severity === 'critical' || issue.severity === 'high' ? 'text-destructive' : 'text-warning')} />
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold">{issue.title}</div>
                    <div className="mt-0.5 text-[10.5px] leading-snug text-muted-foreground">{issue.message}</div>
                    <div className="mt-1 text-[9.5px] text-chart-blue">{issue.remediation}</div>
                  </div>
                  <Badge tone={sevTone(issue.severity) as 'red'}>{issue.severity}</Badge>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}