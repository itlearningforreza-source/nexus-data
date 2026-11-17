import { create } from 'zustand';

export interface ToastItem {
  id: number;
  title: string;
  message?: string;
  tone?: 'default' | 'success' | 'error';
}

interface ToastState {
  toasts: ToastItem[];
  push: (title: string, message?: string, tone?: ToastItem['tone']) => void;
  dismiss: (id: number) => void;
}

let seq = 1;

export const useToast = create<ToastState>((set) => ({
  toasts: [],
  push: (title, message, tone = 'default') => {
    const id = seq++;
    set((s) => ({ toasts: [...s.toasts, { id, title, message, tone }] }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 3600);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

export function toast(title: string, message?: string, tone?: ToastItem['tone']) {
  useToast.getState().push(title, message, tone);
}

export function Toast() {
  const toasts = useToast((s) => s.toasts);
  const dismiss = useToast((s) => s.dismiss);
  return (
    <div className="pointer-events-none fixed bottom-6 left-1/2 z-[70] flex w-full max-w-sm -translate-x-1/2 flex-col gap-2 px-4">
      {toasts.map((t) => (
        <div
          key={t.id}
          className="pointer-events-auto flex items-start gap-3 rounded-xl border border-border bg-card/95 px-3.5 py-2.5 shadow-float backdrop-blur-xl animate-fade-in"
          onClick={() => dismiss(t.id)}
        >
          <span
            className={
              'mt-0.5 h-2 w-2 shrink-0 rounded-full ' +
              (t.tone === 'success' ? 'bg-chart-green' : t.tone === 'error' ? 'bg-destructive' : 'bg-chart-blue')
            }
          />
          <div className="min-w-0">
            <div className="text-xs font-semibold">{t.title}</div>
            {t.message && <div className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{t.message}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}