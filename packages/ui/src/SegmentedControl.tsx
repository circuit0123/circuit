"use client";

import { useRef } from "react";
import { cx } from "./cx";

type Props<T extends string> = { items: { id: T; label: string }[]; value: T; onChange: (id: T) => void; label: string; className?: string };

/** A segmented control instead of tabs inside a screen (DESIGN.md §5). Arrow keys move the choice; it keeps its own swipe, so the tab pager ignores it. */
export function SegmentedControl<T extends string>({ items, value, onChange, label, className }: Props<T>) {
  const ref = useRef<HTMLDivElement>(null);
  const move = (e: React.KeyboardEvent, i: number) => {
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = items[(i + step + items.length) % items.length];
    onChange(next.id);
    ref.current?.querySelector<HTMLElement>(`[data-id="${next.id}"]`)?.focus();
  };
  return (
    <div ref={ref} role="radiogroup" data-no-swipe aria-label={label} className={cx("inline-flex rounded-full bg-surface-2 p-1", className)}>
      {items.map((it, i) => (
        <button
          key={it.id}
          data-id={it.id}
          role="radio"
          aria-checked={it.id === value}
          tabIndex={it.id === value ? 0 : -1}
          onKeyDown={(e) => move(e, i)}
          onClick={() => onChange(it.id)}
          className={cx("min-h-9 rounded-full px-4 t-footnote transition-colors duration-150", it.id === value ? "bg-surface-3 font-semibold text-text" : "text-text")}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}
