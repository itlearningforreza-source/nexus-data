import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, MoreVertical, Trash2, Pencil, FlaskConical } from 'lucide-react';
import { features } from '@/lib/features';
import type { NotebookItem } from '@/lib/types';
import { timeAgo } from '@/lib/format';
import { useUI } from '@/store/ui';
import { toast } from '@/components/ui/toast';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Button,
  Card,
  EmptyState,
  Input,
  Modal,
  ConfirmDialog,
  Spinner,
} from '@/components/ui';

export default function Notebooks() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const projectId = useUI((s) => s.projectId);

  const { data, isLoading } = useQuery({
    queryKey: ['notebooks'],
    queryFn: () => features.notebooks.list(),
  });

  const notebooks = (data ?? []) as NotebookItem[];

  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);

  const [menuId, setMenuId] = useState<string | null>(null);
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameVal, setRenameVal] = useState('');
  const [renaming, setRenaming] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!newName.trim() || !projectId) return;
    setCreating(true);
    try {
      await features.notebooks.create(newName.trim(), projectId);
      toast('Notebook created', undefined, 'success');
      qc.invalidateQueries({ queryKey: ['notebooks'] });
      setCreateOpen(false);
      setNewName('');
    } catch {
      toast('Failed to create notebook', undefined, 'error');
    } finally {
      setCreating(false);
    }
  };

  const handleRename = async () => {
    if (!renameId || !renameVal.trim()) return;
    setRenaming(true);
    try {
      await features.notebooks.update(renameId, { name: renameVal.trim() });
      toast('Renamed', undefined, 'success');
      qc.invalidateQueries({ queryKey: ['notebooks'] });
      setRenameId(null);
    } catch {
      toast('Failed to rename', undefined, 'error');
    } finally {
      setRenaming(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await features.notebooks.remove(deleteId);
      toast('Notebook deleted', undefined, 'success');
      qc.invalidateQueries({ queryKey: ['notebooks'] });
    } catch {
      toast('Failed to delete', undefined, 'error');
    } finally {
      setDeleteId(null);
    }
  };

  return (
    <div className="p-6">
      <PageHeader
        title="Notebooks"
        description="Interactive Python notebooks for data analysis."
        actions={
          <Button leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setCreateOpen(true)}>
            New notebook
          </Button>
        }
      />

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Spinner className="h-5 w-5" />
        </div>
      ) : notebooks.length === 0 ? (
        <EmptyState
          icon={<FlaskConical className="h-8 w-8" />}
          title="No notebooks yet"
          description="Create your first notebook to start exploring data with code."
          action={
            <Button leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setCreateOpen(true)}>
              New notebook
            </Button>
          }
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {notebooks.map((nb) => (
            <Card
              key={nb.id}
              className="group relative cursor-pointer p-4 transition hover:ring-1 hover:ring-primary/30"
              onClick={() => navigate(`/notebooks/${nb.id}`)}
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-semibold leading-snug text-foreground line-clamp-2">{nb.name}</h3>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setMenuId(menuId === nb.id ? null : nb.id);
                  }}
                  className="shrink-0 rounded-md p-1 text-muted-foreground opacity-0 transition hover:bg-muted group-hover:opacity-100"
                >
                  <MoreVertical className="h-3.5 w-3.5" />
                </button>
              </div>
              <div className="mt-2 flex items-center gap-3 text-[11px] text-muted-foreground">
                <span>{nb.cells?.length ?? 0} cells</span>
                <span>{timeAgo(nb.updated_at)}</span>
              </div>
              {menuId === nb.id && (
                <div
                  className="absolute right-3 top-9 z-10 w-36 overflow-hidden rounded-xl border border-border bg-card p-1 shadow-pop"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs transition hover:bg-muted"
                    onClick={() => {
                      setRenameId(nb.id);
                      setRenameVal(nb.name);
                      setMenuId(null);
                    }}
                  >
                    <Pencil className="h-3.5 w-3.5" /> Rename
                  </button>
                  <button
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-destructive transition hover:bg-muted"
                    onClick={() => {
                      setDeleteId(nb.id);
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
        onClose={() => { setCreateOpen(false); setNewName(''); }}
        title="New notebook"
        footer={
          <>
            <Button variant="ghost" onClick={() => { setCreateOpen(false); setNewName(''); }}>Cancel</Button>
            <Button loading={creating} disabled={!newName.trim()} onClick={handleCreate}>Create</Button>
          </>
        }
      >
        <Input
          autoFocus
          placeholder="Notebook name…"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
        />
      </Modal>

      <Modal
        open={!!renameId}
        onClose={() => { setRenameId(null); setRenameVal(''); }}
        title="Rename notebook"
        footer={
          <>
            <Button variant="ghost" onClick={() => { setRenameId(null); setRenameVal(''); }}>Cancel</Button>
            <Button loading={renaming} disabled={!renameVal.trim()} onClick={handleRename}>Rename</Button>
          </>
        }
      >
        <Input
          autoFocus
          value={renameVal}
          onChange={(e) => setRenameVal(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleRename()}
        />
      </Modal>

      <ConfirmDialog
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="Delete notebook"
        message="This will permanently delete the notebook and all its cells. This cannot be undone."
        danger
      />
    </div>
  );
}
