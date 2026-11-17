import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { LayoutDashboard, Plus, Trash2, MoreHorizontal } from 'lucide-react';
import { features } from '@/lib/features';
import { timeAgo } from '@/lib/format';
import type { DashboardItem } from '@/lib/types';
import { useUI } from '@/store/ui';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button, Card, EmptyState, Input, Modal, Menu, toast, ConfirmDialog } from '@/components/ui';

export default function Dashboards() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const projectId = useUI((s) => s.projectId);
  const { data: dashboards = [], isLoading } = useQuery<DashboardItem[]>({
    queryKey: ['dashboards'],
    queryFn: features.dashboards.list,
  });
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [creating, setCreating] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<DashboardItem | null>(null);

  const handleCreate = async () => {
    if (!projectId || !name.trim()) return;
    setCreating(true);
    try {
      await features.dashboards.create(projectId, name.trim());
      toast('Dashboard created', undefined, 'success');
      queryClient.invalidateQueries({ queryKey: ['dashboards'] });
      setOpen(false);
      setName('');
    } catch {
      toast('Failed to create dashboard', undefined, 'error');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    try {
      await features.dashboards.remove(confirmDelete.id);
      toast('Dashboard deleted', undefined, 'success');
      queryClient.invalidateQueries({ queryKey: ['dashboards'] });
    } catch {
      toast('Failed to delete dashboard', undefined, 'error');
    }
  };

  return (
    <div>
      <PageHeader
        title="Dashboards"
        description="Combine charts into a single dashboard view"
        actions={
          <Button leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setOpen(true)}>
            New dashboard
          </Button>
        }
      />

      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-muted-foreground text-xs">Loading…</div>
      ) : dashboards.length === 0 ? (
        <EmptyState
          icon={<LayoutDashboard className="h-8 w-8" />}
          title="No dashboards yet"
          description="Create a dashboard to arrange your charts in a unified layout."
          action={
            <Button size="sm" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setOpen(true)}>
              New dashboard
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {dashboards.map((d) => (
            <Card
              key={d.id}
              className="group cursor-pointer p-5 transition-colors hover:border-primary/30"
              onClick={() => navigate(`/dashboards/${d.id}`)}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <h3 className="truncate text-sm font-semibold text-foreground">{d.name}</h3>
                  {d.description && (
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">{d.description}</p>
                  )}
                </div>
                <Menu
                  trigger={
                    <button
                      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreHorizontal className="h-3.5 w-3.5" />
                    </button>
                  }
                  items={[
                    { key: 'delete', label: 'Delete', icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onClick: () => { setConfirmDelete(d); } },
                  ]}
                />
              </div>
              <div className="mt-3 flex items-center gap-3 text-[11px] text-muted-foreground">
                <span>{d.layout?.length ?? 0} tiles</span>
                <span className="text-border">·</span>
                <span>{timeAgo(d.updated_at)}</span>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => { setOpen(false); setName(''); }}
        title="New dashboard"
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => { setOpen(false); setName(''); }}>Cancel</Button>
            <Button size="sm" loading={creating} disabled={!name.trim()} onClick={handleCreate}>Create</Button>
          </>
        }
      >
        <Input
          placeholder="Dashboard name"
          value={name}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setName(e.target.value)}
          onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => { if (e.key === 'Enter') handleCreate(); }}
          autoFocus
        />
      </Modal>

      <ConfirmDialog
        open={!!confirmDelete}
        onClose={() => setConfirmDelete(null)}
        onConfirm={handleDelete}
        title="Delete dashboard"
        message={`Are you sure you want to delete "${confirmDelete?.name}"? This cannot be undone.`}
        danger
      />
    </div>
  );
}
