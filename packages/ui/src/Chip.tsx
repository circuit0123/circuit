import { X } from "lucide-react";
import { cx } from "./cx";

type Props = {
  label: string;
  selected?: boolean;
  onToggle?: () => void;
  onRemove?: () => void;
  className?: string;
};

/** Static, selectable (onToggle) or removable (onRemove). Tap target stays 44px via the hit area. */
export function Chip({ label, selected, onToggle, onRemove, className }: Props) {
  const base = "inline-flex min-h-8 items-center gap-1 rounded-full px-3 t-footnote";
  if (onToggle) {
    return (
      <button
        type="button"
        aria-pressed={!!selected}
        onClick={onToggle}
        className={cx(base, "relative before:absolute before:-inset-1.5 before:content-['']", selected ? "bg-text text-bg font-semibold" : "bg-surface-2 text-text", className)}
      >
        {label}
      </button>
    );
  }
  return (
    <span className={cx(base, "bg-surface-2 text-text", className)}>
      {label}
      {onRemove && (
        <button type="button" onClick={onRemove} aria-label={`Remove ${label}`} className="-mr-1 inline-flex h-6 w-6 items-center justify-center rounded-full text-text-muted">
          <X size={14} strokeWidth={1.75} />
        </button>
      )}
    </span>
  );
}
