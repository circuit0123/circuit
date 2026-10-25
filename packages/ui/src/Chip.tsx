import { X } from "lucide-react";
import { cx } from "./cx";

type Props = {
  label: string;
  selected?: boolean;
  onToggle?: () => void;
  onRemove?: () => void;
  className?: string;
  /** `lg` is the onboarding pick: 40px, body size, selected = the brand fill (DESIGN.md §4 steps 9 and 10). */
  size?: "md" | "lg";
};

/** Static, selectable (onToggle) or removable (onRemove). Tap target stays 44px via the hit area. */
export function Chip({ label, selected, onToggle, onRemove, className, size = "md" }: Props) {
  const base = "inline-flex min-h-8 items-center gap-1 rounded-full px-3 t-footnote";
  if (onToggle && size === "lg") {
    return (
      <button
        type="button"
        aria-pressed={!!selected}
        onClick={onToggle}
        className={cx("inline-flex min-h-10 items-center rounded-full px-4 t-body font-medium transition-colors", selected ? "bg-primary text-on-primary" : "bg-surface-2 text-text", className)}
      >
        {label}
      </button>
    );
  }
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
