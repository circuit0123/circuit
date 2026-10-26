"use client";

import { useRef } from "react";
import { ACCENTS, type Accent } from "./ThemeProvider";
import { cx } from "./cx";

type Props = {
  value: Accent;
  onChange: (a: Accent) => void;
  /** The line shown in the live preview (a Live wire node, the way the accent looks in use). */
  previewText?: string;
  className?: string;
};

/** Paints `css` with the accent's dark or light colour: both are drawn, the theme decides which one shows (no JavaScript, no flash). */
function Tone({ accent, as: Tag = "span", css, className }: { accent: Accent; as?: "span"; css: (hex: string) => React.CSSProperties; className?: string }) {
  const a = ACCENTS.find((x) => x.id === accent)!;
  return (
    <>
      <Tag aria-hidden className={cx("only-dark", className)} style={css(a.dark)} />
      <Tag aria-hidden className={cx("only-light", className)} style={css(a.light)} />
    </>
  );
}

/**
 * The six accents as large swatches with a live preview (DESIGN.md §5, onboarding step 13 and Settings → Appearance). A radio group:
 * arrow keys move the choice, the chosen swatch wears a ring. There is no free colour picker.
 */
export function AccentPicker({ value, onChange, previewText = "Divya shipped offline sync", className }: Props) {
  const group = useRef<HTMLDivElement>(null);
  const move = (to: number) => {
    const next = ACCENTS[(to + ACCENTS.length) % ACCENTS.length];
    onChange(next.id);
    group.current?.querySelector<HTMLButtonElement>(`[data-accent-id="${next.id}"]`)?.focus();
  };
  return (
    <div className={className}>
      <div ref={group} role="radiogroup" aria-label="Accent colour" className="grid grid-cols-3 gap-x-3 gap-y-6">
        {ACCENTS.map((a, i) => {
          const on = a.id === value;
          return (
            <button
              key={a.id}
              type="button"
              role="radio"
              aria-checked={on}
              data-accent-id={a.id}
              tabIndex={on ? 0 : -1}
              onClick={() => onChange(a.id)}
              onKeyDown={(e) => {
                if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); move(i + 1); }
                else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); move(i - 1); }
              }}
              className={cx("flex flex-col items-center gap-2.5 rounded-control py-1 t-subhead active:opacity-80", on ? "text-text" : "text-text-muted")}
            >
              <span className={cx("relative block h-16 w-16 rounded-full", on && "ring-2 ring-text ring-offset-4 ring-offset-bg")}>
                <Tone accent={a.id} className="absolute inset-0 rounded-full" css={(hex) => ({ background: hex })} />
              </span>
              {a.label}
            </button>
          );
        })}
      </div>
      <div aria-label="Preview" role="group" className="mt-10 flex items-center gap-4 rounded-card bg-surface p-4">
        <span className="relative block h-11 w-11 shrink-0 rounded-control bg-surface-2">
          <Tone accent={value} className="absolute inset-0 rounded-control" css={(hex) => ({ border: `2px solid ${hex}` })} />
        </span>
        <p className="t-body min-w-0 flex-1">{previewText}</p>
        <span className="relative block h-2.5 w-2.5 shrink-0 rounded-full">
          <Tone accent={value} className="absolute inset-0 rounded-full" css={(hex) => ({ background: hex })} />
        </span>
      </div>
    </div>
  );
}
