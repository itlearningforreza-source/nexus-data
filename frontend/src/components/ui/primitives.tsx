import clsx, { type ClassValue } from 'clsx';
import { type ButtonHTMLAttributes, type ReactNode } from 'react';

export { clsx };
export function cn(...inputs: ClassValue[]) {
  return clsx(...inputs);
}

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline';
type Size = 'xs' | 'sm' | 'md' | 'lg' | 'icon';

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-primary text-primary-foreground hover:bg-primary-hover shadow-subtle',
  secondary: 'bg-muted text-foreground hover:bg-accent',
  ghost: 'text-muted-foreground hover:bg-muted hover:text-foreground',
  danger: 'bg-destructive text-white hover:opacity-90',
  outline: 'border border-border bg-transparent hover:bg-muted',
};

const SIZES: Record<Size, string> = {
  xs: 'h-6 px-2 text-[11px] rounded-md gap-1',
  sm: 'h-7 px-2.5 text-xs rounded-lg gap-1.5',
  md: 'h-8.5 h-9 px-3.5 text-[13px] rounded-lg gap-2',
  lg: 'h-11 px-5 text-sm rounded-xl gap-2',
  icon: 'h-8 w-8 rounded-lg',
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leftIcon?: ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading,
  leftIcon,
  className,
  disabled,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap font-medium',
        'transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/40',
        'disabled:pointer-events-none disabled:opacity-45',
        'active:scale-[0.98]',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Spinner className="h-3.5 w-3.5" /> : leftIcon}
      {children}
    </button>
  );
}

export function Card({
  className,
  children,
  ...rest
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-border bg-card text-card-foreground shadow-subtle',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

export function Badge({
  className,
  tone = 'muted',
  children,
}: {
  className?: string;
  tone?: 'muted' | 'blue' | 'green' | 'red' | 'orange' | 'purple';
  children: ReactNode;
}) {
  const tones: Record<string, string> = {
    muted: 'bg-muted text-muted-foreground',
    blue: 'bg-chart-blue/15 text-chart-blue',
    green: 'bg-chart-green/15 text-chart-green',
    red: 'bg-destructive/15 text-destructive',
    orange: 'bg-warning/15 text-warning',
    purple: 'bg-chart-purple/15 text-chart-purple',
  };
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn('animate-spin', className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-label="Loading"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.2" strokeWidth="4" />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function LoadingBlock({
  label = 'Loading…',
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div className={cn('flex items-center justify-center gap-2 py-16 text-muted-foreground', className)}>
      <Spinner className="h-4 w-4" />
      <span className="text-xs">{label}</span>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-2 py-14 text-center', className)}>
      {icon && <div className="mb-1 text-muted-foreground">{icon}</div>}
      <div className="text-sm font-semibold text-foreground">{title}</div>
      {description && <div className="max-w-sm text-xs leading-relaxed text-muted-foreground">{description}</div>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-5 items-center rounded border border-border bg-muted px-1.5 text-[10px] font-medium text-muted-foreground">
      {children}
    </kbd>
  );
}

export function Divider({ className }: { className?: string }) {
  return <div className={cn('h-px w-full bg-border', className)} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-md bg-muted', className)} />;
}