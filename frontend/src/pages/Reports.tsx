import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, FileText, MoreVertical, Download, Trash2 } from 'lucide-react';
import { features, blobDownload } from '@/lib/features';
import type { ReportItem } from '@/lib/types';
import { timeAgo } from '@/lib/format';
import { useUI } from '@/store/ui';
import { toast } from '@/components/ui/toast';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button, Card, EmptyState, Input, Modal, ConfirmDialog, Spinner } from '@/components/ui';

export default function Reports() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const projectId = useUI((s) => s.projectId);

  const { data, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: () => features.reports.list(),
  });

  const reports = (data ?? []) as ReportItem[];

  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);

  const [menuId, setMenuId] = useState<string | null>(null);
  const [exportingId, setExportingId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!newName.trim() || !projectId) return;
    setCreating(true);
    try {
      await features.reports.create(projectId, newName.trim());
      toast('Report created', undefined, 'success');
      qc.invalidateQueries({ queryKey: ['reports'] });
      setCreateOpen(false);
      setNewName('');
    } catch {
      toast('Failed to create report', undefined, 'error');
    } finally {
      setCreating(false);
    }
  };

  const handleExport = async (r: ReportItem) => {
    setExportingId(r.id);
    try {
      const data = await features.reports.export(r.id, 'pdf');
      blobDownload(data.url, `${r.name}.pdf`);
      toast('Export started', undefined, 'success');
    } catch {
      toast('Export failed', undefined, 'error');
    } finally {
      setExportingId(null);
      setMenuId(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await features.reports.remove(deleteId);
      toast('Report deleted', undefined, 'success');
      qc.invalidateQueries({ queryKey: ['reports'] });
    } catch {
      toast('Failed to delete', undefined, 'error');
    } finally {
      setDeleteId(null);
    }
  };

  return (
    <div className="p-6">
      <PageHeader
        title="Reports"
        description="Compose structured, shareable report documents from your datasets."
        actions={
          <Button leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setCreateOpen(true)}>
            New report
          </Button>
        }
      />

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Spinner className="h-5 w-5" />
        </div>
      ) : reports.length === 0 ? (
        <EmptyState
          icon={<FileText className="h-8 w-8" />}
          title="No reports yet"
          description="Create your first report to document and share your analysis."
          action={
            <Button leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setCreateOpen(true)}>
              New report
            </Button>
          }
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {reports.map((r) => (
            <Card
              key={r.id}
              className="group relative cursor-pointer p-4 transition hover:ring-1 hover:ring-primary/30"
              onClick={() => navigate(`/reports/${r.id}`)}
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-semibold leading-snug text-foreground line-clamp-2">{r.name}</h3>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setMenuId(menuId === r.id ? null : r.id);
                  }}
                  className="shrink-0 rounded-md p-1 text-muted-foreground opacity-0 transition hover:bg-muted group-hover:opacity-100"
                  aria-label="Report actions"
                >
                  <MoreVertical className="h-3.5 w-3.5" />
                </button>
              </div>
              <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                {r.description || 'No description'}
              </p>
              <div className="mt-3 flex items-center gap-3 text-[11px] text-muted-foreground">
                <span>{r.sections?.length ?? 0} sections</span>
                <span>{timeAgo(r.updated_at)}</span>
              </div>
              {menuId === r.id && (
                <div
                  className="absolute right-3 top-9 z-10 w-40 overflow-hidden rounded-xl border border-border bg-card p-1 shadow-pop"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    disabled={exportingId === r.id}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs transition hover:bg-muted disabled:opacity-50"
                    onClick={() => handleExport(r)}
                  >
                    <Download className="h-3.5 w-3.5" /> Export PDF
                  </button>
                  <button
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-destructive transition hover:bg-muted"
                    onClick={() => {
                      setDeleteId(r.id);
                      setMenuId(null);
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Delete
                  </button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={createOpen}
        onClose={() => {
          setCreateOpen(false);
          setNewName('');
        }}
        title="New report"
        footer={
          <>
            <Button variant="ghost" onClick={() => { setCreateOpen(false); setNewName(''); }}>
              Cancel
            </Button>
            <Button loading={creating} disabled={!newName.trim() || !projectId} onClick={handleCreate}>
              Create
            </Button>
          </>
        }
      >
        <Input
          autoFocus
          placeholder="Report name…"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
        />
      </Modal>

      <ConfirmDialog
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="Delete report"
        message="This will permanently delete the report and its sections. This cannot be undone."
        danger
      />
    </div>
  );
}