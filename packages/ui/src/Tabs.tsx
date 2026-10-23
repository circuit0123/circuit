"use client";
import { useId, type KeyboardEvent } from "react";
import { cx } from "./cx";

type Tab = { id: string; label: string };

/** Controlled tab list. Arrow keys move between tabs; give the panel `role="tabpanel" id={panelId}`. */
export function Tabs({ tabs, value, onChange, label, panelId }: { tabs: Tab[]; value: string; onChange: (id: string) => void; label: string; panelId: string }) {
  const base = useId();
  const onKey = (e: KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.id === value);
    const next = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : null;
    if (next === null) return;
    e.preventDefault();
    const t = tabs[(next + tabs.length) % tabs.length];
    onChange(t.id);
    document.getElementById(`${base}-${t.id}`)?.focus();
  };
  return (
    <div role="tablist" aria-label={label} onKeyDown={onKey} className="flex gap-1 border-b border-rule">
      {tabs.map((t) => (
        <button
          key={t.id}
          id={`${base}-${t.id}`}
          role="tab"
          type="button"
          aria-selected={t.id === value}
          aria-controls={panelId}
          tabIndex={t.id === value ? 0 : -1}
          onClick={() => onChange(t.id)}
          className={cx(
            "-mb-px min-h-11 border-b-2 px-4 font-semibold",
            t.id === value ? "border-line text-ink" : "border-transparent text-ink-soft hover:text-ink",
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
