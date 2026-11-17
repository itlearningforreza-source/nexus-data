import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Settings2, User, Database, Bell, LogOut, Check, Moon, Sun } from 'lucide-react';
import { features } from '@/lib/features';
import { api } from '@/lib/api';
import { Card, Button, Input, Field, Toggle, cn } from '@/components/ui';
import { toast } from '@/components/ui';
import { PageHeader } from '@/components/layout/PageHeader';
import { useAuth } from '@/store/auth';
import { useUI } from '@/store/ui';
import type { User as UserType } from '@/lib/types';
import { timeAgo, formatBytes } from '@/lib/format';

export default function Settings() {
  const user = useAuth((s) => s.user);
  const setUser = useAuth((s) => s.setUser);
  const logout = useAuth((s) => s.logout);
  const qc = useQueryClient();
  const { theme, setTheme, sidebarCollapsed, setSidebarCollapsed } = useUI();

  const [name, setName] = useState(user?.name ?? '');
  const [email, setEmail] = useState(user?.email ?? '');
  const [notify, setNotify] = useState(true);
  const [busy, setBusy] = useState(false);

  const { data: datasets } = useDatasets();

  const saveProfile = async () => {
    setBusy(true);
    try {
      const res = await api<{ user: UserType }>('/api/auth/me', { method: 'PATCH', body: { name: name || undefined, email: email || undefined } });
      setUser(res.user);
      toast('Profile updated', 'Your details were saved.', 'success');
    } catch (e) {
      toast('Update failed', e instanceof Error ? e.message : 'Could not update profile.', 'error');
    } finally {
      setBusy(false);
    }
  };

  const storageBytes = (datasets ?? []).reduce((acc, d) => acc + (d.size_bytes ?? 0), 0);

  const onLogout = () => {
    logout();
    qc.clear();
    window.location.href = '/auth';
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageHeader title="Settings" description="Manage your profile, preferences and workspace." />

      <Card className="p-5">
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold"><User className="h-3.5 w-3.5 text-primary" /> Profile</div>
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Name">
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Email">
              <Input value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Member since {timeAgo(user?.created_at)}</span>
            <Button size="sm" onClick={saveProfile} loading={busy} disabled={!name.trim() || !email.trim()}>
              <Check className="h-3.5 w-3.5" /> Save changes
            </Button>
          </div>
        </div>
      </Card>

      <Card className="p-5">
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold"><Settings2 className="h-3.5 w-3.5 text-primary" /> Appearance</div>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">Theme</div>
              <div className="text-xs text-muted-foreground">Light or dark appearance.</div>
            </div>
            <div className="flex items-center gap-1 rounded-lg bg-muted p-1">
              {(['light', 'dark'] as const).map((t) => (
                <button key={t} onClick={() => setTheme(t)}
                  className={cn('flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium capitalize transition', theme === t ? 'bg-foreground text-background' : 'text-muted-foreground')}>
                  {t === 'light' ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />} {t}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between border-t border-border/60 pt-3">
            <div>
              <div className="text-sm font-medium">Compact sidebar</div>
              <div className="text-xs text-muted-foreground">Collapse the navigation sidebar by default.</div>
            </div>
            <Toggle checked={sidebarCollapsed} onChange={setSidebarCollapsed} />
          </div>
        </div>
      </Card>

      <Card className="p-5">
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold"><Database className="h-3.5 w-3.5 text-primary" /> Workspace</div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatBox label="Datasets" value={(datasets ?? []).length.toLocaleString()} />
          <StatBox label="Storage" value={formatBytes(storageBytes)} />
          <StatBox label="Rows" value={(datasets ?? []).reduce((a, d) => a + (d.row_count ?? 0), 0).toLocaleString()} />
          <StatBox label="Projects" value="—" />
        </div>
      </Card>

      <Card className="p-5">
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold"><Bell className="h-3.5 w-3.5 text-primary" /> Notifications</div>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium">Job completion alerts</div>
            <div className="text-xs text-muted-foreground">Show a toast when long-running tasks finish.</div>
          </div>
          <Toggle checked={notify} onChange={setNotify} />
        </div>
      </Card>

      <Card className="flex items-center justify-between p-5">
        <div>
          <div className="text-sm font-medium text-destructive">Sign out</div>
          <div className="text-xs text-muted-foreground">You will need to log in again.</div>
        </div>
        <Button variant="outline" className="border-destructive/40 text-destructive hover:bg-destructive/10" onClick={onLogout}>
          <LogOut className="h-3.5 w-3.5" /> Sign out
        </Button>
      </Card>
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border p-3">
      <div className="text-[10px] uppercase text-muted-foreground">{label}</div>
      <div className="mt-0.5 font-mono text-base font-bold tabular-nums">{value}</div>
    </div>
  );
}

function useDatasets() {
  const { data } = useQuery({ queryKey: ['datasets'], queryFn: () => features.datasets.list() });
  return { data };
}