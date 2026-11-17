import { type ReactNode, useEffect, useRef, useState } from 'react';
import { cn } from './primitives';

interface Tab {
  id: string;
  label: ReactNode;
  icon?: ReactNode;
  badge?: number;
}

export function Tabs({
  tabs,
  active,
  onChange,
  className,
  tabClassName,
}: {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
  tabClassName?: string;
}) {
  return (
    <div className={cn('scrollbar-thin flex items-center gap-0.5 overflow-x-auto border-b border-border', className)}>
      {tabs.map((t) => {
        const isActive = t.id === active;
        return (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            className={cn(
              'flex h-9 shrink-0 items-center gap-1.5 px-3 text-[12.5px] font-medium transition-colors',
              'relative -mb-px border-b-2',
              isActive ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground',
              tabClassName,
            )}
          >
            {t.icon}
            {t.label}
            {t.badge !== undefined && t.badge > 0 && (
              <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-chart-blue/15 px-1 text-[10px] font-semibold text-chart-blue">
                {t.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export function PillTabs({
  tabs,
  active,
  onChange,
  className,
}: {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
}) {
  return (
    <div className={cn('scrollbar-thin flex items-center gap-1 overflow-x-auto', className)}>
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={cn(
            'shrink-0 rounded-full px-3 py-1.5 text-xs font-medium transition-all',
            active === t.id ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground hover:text-foreground',
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function useClickOutside<T extends HTMLElement>(callback: () => void) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) callback();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [callback]);
  return ref;
}

export function Menu({
  trigger,
  items,
  align = 'right',
  className,
}: {
  trigger: ReactNode;
  items: { key: string; label: ReactNode; icon?: ReactNode; danger?: boolean; disabled?: boolean; onClick?: () => void }[];
  align?: 'left' | 'right';
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useClickOutside<HTMLDivElement>(() => setOpen(false));

  return (
    <div ref={ref} className={cn('relative', className)}>
      <div onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}>{trigger}</div>
      {open && (
        <div
          className={cn(
            'absolute z-40 mt-1 min-w-[180px] overflow-hidden rounded-xl border border-border bg-card py-1 shadow-pop animate-scale-in',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          {items.map((item) => (
            <button
              key={item.key}
              disabled={item.disabled}
              onClick={(e) => {
                e.stopPropagation();
                item.onClick?.();
                setOpen(false);
              }}
              className={cn(
                'flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs font-medium transition-colors',
                item.danger ? 'text-destructive hover:bg-destructive/10' : 'text-foreground hover:bg-muted',
                item.disabled && 'opacity-40',
              )}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}