import { cx } from "./cx";

export function SegmentedControl<T extends string>({ items, value, onChange, label, className }: { items: { id: T; label: string }[]; value: T; onChange: (id: T) => void; label: string; className?: string }) {
  return (
    <div role="radiogroup" aria-label={label} className={cx("inline-flex rounded-full bg-surface-2 p-1", className)}>
      {items.map((it) => (
        <button
          key={it.id}
          role="radio"
          aria-checked={it.id === value}
          onClick={() => onChange(it.id)}
          className={cx("min-h-9 rounded-full px-4 t-caption transition-colors duration-150", it.id === value ? "bg-surface font-semibold text-text" : "text-text-muted")}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}
