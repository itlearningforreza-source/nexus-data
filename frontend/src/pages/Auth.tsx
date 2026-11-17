import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap, Github, Twitter, Mail, User, KeyRound } from 'lucide-react';
import { useAuth } from '@/store/auth';
import { toast } from '@/components/ui';

export default function Auth() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const { login, register, token } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (token) navigate('/');
  }, [token, navigate]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (mode === 'register') {
        if (name.trim().length < 2) throw new Error('Name must be at least 2 characters.');
        await register(name.trim(), email.trim(), password);
      } else {
        await login(email.trim(), password);
      }
      navigate('/');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Authentication failed.';
      setError(msg);
      toast('Authentication failed', msg, 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="grid w-full max-w-4xl overflow-hidden rounded-3xl border border-border bg-card shadow-float md:grid-cols-2">
        <div className="hidden flex-col justify-between bg-gradient-to-br from-primary via-blue to-purple p-10 text-white md:flex">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/20 backdrop-blur">
              <Zap className="h-5 w-5" />
            </div>
            <div className="text-lg font-bold tracking-tight">Nexus Data</div>
          </div>
          <div>
            <h1 className="text-3xl font-bold leading-tight tracking-tight">
              Your data,
              <br />
              fully under control.
            </h1>
            <p className="mt-3 max-w-sm text-sm leading-relaxed text-white/80">
              Import, clean, analyze, and visualize data with spreadsheets, SQL, notebooks and AI — all running locally on your machine.
            </p>
          </div>
          <div className="flex gap-4 text-[11px] text-white/70">
            <span className="flex items-center gap-1.5"><Zap className="h-3 w-3" /> 100% local</span>
            <span className="flex items-center gap-1.5"><KeyRound className="h-3 w-3" /> Private by design</span>
          </div>
        </div>

        <div className="flex flex-col justify-center p-8 md:p-10">
          <div className="mb-6 md:hidden">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-white">
                <Zap className="h-4 w-4" />
              </div>
              <div className="text-sm font-bold">Nexus Data</div>
            </div>
          </div>

          <div className="mb-6 flex rounded-xl bg-muted p-1">
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(''); }}
                className={`flex-1 rounded-lg py-2 text-xs font-semibold transition ${
                  mode === m ? 'bg-card shadow-subtle text-foreground' : 'text-muted-foreground'
                }`}
              >
                {m === 'login' ? 'Sign in' : 'Create account'}
              </button>
            ))}
          </div>

          <h2 className="text-xl font-bold tracking-tight">{mode === 'login' ? 'Welcome back' : 'Get started'}</h2>
          <p className="mb-6 mt-1 text-xs text-muted-foreground">
            {mode === 'login' ? 'Sign in to your workspace.' : 'Create your account to begin.'}
          </p>

          <form onSubmit={submit} className="flex flex-col gap-3.5">
            {mode === 'register' && (
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium">Full name</label>
                <div className="relative">
                  <User className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Ada Lovelace"
                    className="h-10 w-full rounded-xl border border-input bg-card pl-9 pr-3 text-[13px] outline-none transition focus:border-primary/50 focus:ring-2 focus:ring-ring/20"
                  />
                </div>
              </div>
            )}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium">Email</label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="ada@example.com"
                  required
                  className="h-10 w-full rounded-xl border border-input bg-card pl-9 pr-3 text-[13px] outline-none transition focus:border-primary/50 focus:ring-2 focus:ring-ring/20"
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium">Password</label>
              <div className="relative">
                <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  className="h-10 w-full rounded-xl border border-input bg-card pl-9 pr-3 text-[13px] outline-none transition focus:border-primary/50 focus:ring-2 focus:ring-ring/20"
                />
              </div>
            </div>

            {error && <div className="rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</div>}

            <button
              type="submit"
              disabled={busy}
              className="mt-1 flex h-10 items-center justify-center gap-2 rounded-xl bg-primary text-[13px] font-semibold text-white shadow-subtle transition hover:opacity-90 disabled:opacity-50"
            >
              {busy ? (
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="4"/><path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="4" strokeLinecap="round"/></svg>
              ) : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <div className="mt-8 flex items-center justify-center gap-4 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1"><Github className="h-3 w-3" /> Local-first</span>
            <span className="flex items-center gap-1"><Twitter className="h-3 w-3" /> No cloud</span>
          </div>
        </div>
      </div>
    </div>
  );
}