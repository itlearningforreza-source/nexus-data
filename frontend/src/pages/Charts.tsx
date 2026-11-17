import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { BarChart3, Grid2x2, List, Trash2 } from 'lucide-react';
import { features } from '@/lib/features';
import { ChartView, Legend } from '@/components/charts/chartEngine';
import { Card, EmptyState, cn } from '@/components/ui';
import { toast } from '@/components/ui';
import { PageHeader } from '@/components/layout/PageHeader';
import { CHART_TYPE_LABELS } from '@/lib/format';
import type { ChartData, ChartItem } from '@/lib/types';

function unwrap(item: ChartItem): ChartData | null {
  const d = item.data as unknown;
  if (d && typeof d === 'object' && 'data' in (d as object)) return (d as { data: ChartData | null }).data;
  return d as ChartData | null;
}

export default function Charts() {
  const [layout, setLayout] = useState<'grid' | 'rows'>('grid');
  const qc = useQueryClient();
  const { data: charts, isLoading } = useQuery({ queryKey: ['charts'], queryFn: () => features.charts.list() });

  const remove = async (item: ChartItem) => {
    try {
      await features.charts.remove(item.id);
      qc.invalidateQueries({ queryKey: ['charts'] });
      toast('Chart deleted', undefined, 'success');
    } catch (e) {
      toast('Delete failed', e instanceof Error ? e.message : 'Could not delete chart.', 'error');
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Charts"
        description="Saved charts from your datasets — open any dataset hub to build more."
        actions={
          <>
            <button className={cn('rounded-lg p-1.5 transition', layout === 'grid' ? 'bg-foreground text-background' : 'text-muted-foreground')} onClick={() => setLayout('grid')}><Grid2x2 className="h-4 w-4" /></button>
            <button className={cn('rounded-lg p-1.5 transition', layout === 'rows' ? 'bg-foreground text-background' : 'text-muted-foreground')} onClick={() => setLayout('rows')}><List className="h-4 w-4" /></button>
          </>
        }
      />

      {isLoading && <div className="flex h-40 items-center justify-center text-xs text-muted-foreground">Loading charts…</div>}

      {charts && charts.length === 0 && (
        <EmptyState
          icon={<BarChart3 className="h-6 w-6" />}
          title="No saved charts yet"
          description="Build a chart from a dataset hub and save it to see it here."
          action={<Link to="/datasets" className="text-xs font-medium text-primary hover:underline">Go to datasets</Link>}
        />
      )}

      {charts && charts.length > 0 && (
        <div className={cn(layout === 'grid' ? 'grid gap-4 md:grid-cols-2' : 'space-y-4')}>
          {charts.map((item) => {
            const data = unwrap(item);
            return (
              <Card key={item.id} className="group p-4">
                <div className="mb-3 flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-semibold">{item.name}</span>
                      <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">{CHART_TYPE_LABELS[item.chart_type] ?? item.chart_type}</span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground">
                      <span className="max-w-40 truncate">{item.dataset_id}</span>
                    </div>
                  </div>
                  <button onClick={() => remove(item)} className="text-muted-foreground/40 opacity-0 transition hover:text-destructive group-hover:opacity-100"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
                <div className="h-64">
                  {data ? (
                    <ChartView chartType={item.chart_type} data={data} />
                  ) : (
                    <div className="flex h-full items-center justify-center text-xs text-muted-foreground">No data (chart may reference a removed dataset / column).</div>
                  )}
                </div>
                {(data?.series?.length ?? 0) > 1 && <Legend series={(data?.series ?? []).map((s) => ({ name: s.name }))} />}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}