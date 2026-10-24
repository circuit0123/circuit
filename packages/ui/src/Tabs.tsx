"use client";

import { useId } from "react";
import { cx } from "./cx";

type Item<T extends string> = { id: T; label: string };

/** Tab switch is a 150ms crossfade in the panel, never a slide (DESIGN.md §7). */
export function Tabs<T extends string>({ items, value, onChange, label, className }: { items: Item<T>[]; value: T; onChange: (id: T) => void; label: string; className?: string }) {
  const uid = useId();
  const move = (e: React.KeyboardEvent, i: number) => {
    const n = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : null;
    if (n === null) return;
    e.preventDefault();
    onChange(items[(n + items.length) % items.length].id);
  };
  return (
    <div role="tablist" aria-label={label} className={cx("flex border-b border-separator", className)}>
      {items.map((it, i) => {
        const on = it.id === value;
        return (
          <button
            key={it.id}
            role="tab"
            id={`${uid}-${it.id}`}
            aria-selected={on}
            tabIndex={on ? 0 : -1}
            onClick={() => onChange(it.id)}
            onKeyDown={(e) => move(e, i)}
            className={cx("relative min-h-11 flex-1 px-3 t-body", on ? "font-semibold text-text" : "text-text-muted")}
          >
            {it.label}
            <span className={cx("absolute inset-x-3 bottom-0 h-0.5 rounded-full transition-opacity duration-150", on ? "bg-text opacity-100" : "opacity-0")} aria-hidden />
          </button>
        );
      })}
    </div>
  );
}
