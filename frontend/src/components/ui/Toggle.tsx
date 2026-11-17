import { cn } from './primitives';

export function Toggle({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn('flex items-center gap-2 disabled:opacity-50', label && 'text-xs font-medium')}
      role="switch"
      aria-checked={checked}
    >
      <span
        className={cn(
          'relative inline-flex h-5 w-8 shrink-0 items-center rounded-full transition-colors',
          checked ? 'bg-chart-green' : 'bg-muted',
        )}
      >
        <span
          className={cn(
            'inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform',
            checked ? 'translate-x-3.5' : 'translate-x-0.5',
          )}
        />
      </span>
      {label && <span>{label}</span>}
    </button>
  );
}