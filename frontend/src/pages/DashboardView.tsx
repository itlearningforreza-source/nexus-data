import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Plus, Save, LayoutDashboard, X } from 'lucide-react';
import { features } from '@/lib/features';
import type { DashboardItem, ChartItem } from '@/lib/types';
import { Button, Card, EmptyState, LoadingBlock, Modal, Select, toast } from '@/components/ui';
import { ChartView } from '@/components/charts/chartEngine';

interface Tile {
  id: string;
  chart_id: string;
  name: string;
  chart_type: string;
  data: unknown;
}

export default function DashboardView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: dashboard, isLoading } = useQuery<DashboardItem>({
    queryKey: ['dashboard', id],
    queryFn: () => features.dashboards.get(id!),
    enabled: !!id,
  });

  const { data: charts = [] } = useQuery<ChartItem[]>({
    queryKey: ['charts', 'saved'],
    queryFn: features.charts.list,
  });

  const [layout, setLayout] = useState<Tile[]>([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [addOpen, setAddOpen] = useState(false);
  const [selectedChartId, setSelectedChartId] = useState('');
  const [saving, setSaving] = useState(false);
  const [layoutLoaded, setLayoutLoaded] = useState(false);

  if (dashboard && !layoutLoaded) {
    setName(dashboard.name);
    setDescription(dashboard.description ?? '');
    if (dashboard.layout?.length) {
      setLayout(dashboard.layout as unknown as Tile[]);
    }
    setLayoutLoaded(true);
  }

  const addTile = () => {
    const chart = charts.find((c) => c.id === selectedChartId);
    if (!chart) return;
    const chartData = (chart as any).data?.data ?? (chart as any).data ?? null;
    setLayout((prev) => [
      ...prev,
      { id: crypto.randomUUID(), chart_id: chart.id, name: chart.name, chart_type: chart.chart_type, data: chartData },
    ]);
    setAddOpen(false);
    setSelectedChartId('');
  };

  const removeTile = (tileId: string) => {
    setLayout((prev) => prev.filter((t) => t.id !== tileId));
  };

  const handleSave = async () => {
    if (!id) return;
    setSaving(true);
    try {
      await features.dashboards.update(id, {
        name: name.trim() || dashboard?.name,
        description: description.trim() || undefined,
        layout: layout as unknown as Record<string, unknown>[],
      });
      toast('Dashboard saved', undefined, 'success');
      queryClient.invalidateQueries({ queryKey: ['dashboard', id] });
    } catch {
      toast('Failed to save dashboard', undefined, 'error');
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) return <LoadingBlock />;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/dashboards')}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="min-w-0">
            <input
              className="block w-full bg-transparent text-2xl font-bold tracking-tight text-foreground outline-none placeholder:text-muted-foreground focus:ring-0"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Untitled dashboard"
            />
            <input
              className="mt-0.5 block w-full max-w-xl bg-transparent text-sm text-muted-foreground outline-none placeholder:text-muted-foreground/50 focus:ring-0"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Add a description…"
            />
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setAddOpen(true)}>
            Add tile
          </Button>
          <Button size="sm" loading={saving} leftIcon={<Save className="h-3.5 w-3.5" />} onClick={handleSave}>
            Save layout
          </Button>
        </div>
      </div>

      {charts.length === 0 ? (
        <EmptyState
          icon={<LayoutDashboard className="h-8 w-8" />}
          title="No saved charts"
          description="Create some charts first, then come back to build a dashboard."
        />
      ) : layout.length === 0 ? (
        <EmptyState
          icon={<LayoutDashboard className="h-8 w-8" />}
          title="Empty dashboard"
          description={'Click "Add tile" to place charts on this dashboard.'}
          action={
            <Button size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setAddOpen(true)}>
              Add tile
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {layout.map((tile) => (
            <Card key={tile.id} className="p-0 overflow-hidden">
              <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
                <span className="truncate text-xs font-medium text-foreground">{tile.name}</span>
                <button
                  onClick={() => removeTile(tile.id)}
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
              <div className="px-3 py-2">
                {tile.data ? (
                  <ChartView data={tile.data as any} chartType={tile.chart_type} height={280} />
                ) : (
                  <div className="flex h-[280px] items-center justify-center text-xs text-muted-foreground">No data</div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={addOpen}
        onClose={() => { setAddOpen(false); setSelectedChartId(''); }}
        title="Add tile"
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => { setAddOpen(false); setSelectedChartId(''); }}>Cancel</Button>
            <Button size="sm" disabled={!selectedChartId} onClick={addTile}>Add</Button>
          </>
        }
      >
        <label className="mb-1 block text-xs font-medium text-foreground">Select chart</label>
        <Select value={selectedChartId} onChange={(e) => setSelectedChartId(e.target.value)}>
          <option value="">Choose a chart…</option>
          {charts.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </Select>
      </Modal>
    </div>
  );
}
