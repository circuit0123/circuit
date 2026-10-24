"use client";

import { useId } from "react";
import { cx } from "./cx";

type Props = React.InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  /** One sentence. Shown under the field; what the person typed is never cleared. */
  error?: string | null;
  hint?: string;
};

/** A labelled text input: 12px radius, surface-2 fill, 50px tall. */
export function TextField({ label, error, hint, className, id, ...rest }: Props) {
  const uid = useId();
  const fid = id ?? uid;
  return (
    <div className={cx("flex flex-col gap-2", className)}>
      <label htmlFor={fid} className="t-footnote text-text-muted">{label}</label>
      <input
        id={fid}
        aria-invalid={!!error}
        aria-describedby={error ? `${fid}-err` : hint ? `${fid}-hint` : undefined}
        className={cx("min-h-[50px] w-full rounded-control bg-surface-2 px-4 t-body text-text outline-none placeholder:text-text-subtle", error && "ring-1 ring-danger")}
        {...rest}
      />
      {error ? <p id={`${fid}-err`} role="alert" className="t-footnote text-danger">{error}</p> : hint ? <p id={`${fid}-hint`} className="t-footnote text-text-subtle">{hint}</p> : null}
    </div>
  );
}

type CodeProps = {
  value: string;
  onChange: (v: string) => void;
  /** Called once all digits are in. */
  onComplete?: (v: string) => void;
  length?: number;
  label: string;
  error?: string | null;
  disabled?: boolean;
};

/** A one-time code: one box per digit, auto-advance, backspace goes back, paste fills every box. */
export function CodeField({ value, onChange, onComplete, length = 6, label, error, disabled }: CodeProps) {
  const uid = useId();
  const set = (next: string) => {
    const v = next.replace(/\D/g, "").slice(0, length);
    onChange(v);
    if (v.length === length) onComplete?.(v);
  };
  const focus = (i: number) => document.getElementById(`${uid}-${Math.max(0, Math.min(length - 1, i))}`)?.focus();
  return (
    <div>
      <div role="group" aria-label={label} className="flex justify-between gap-2">
        {Array.from({ length }, (_, i) => (
          <input
            key={i}
            id={`${uid}-${i}`}
            inputMode="numeric"
            autoComplete={i === 0 ? "one-time-code" : "off"}
            pattern="[0-9]*"
            maxLength={length}
            disabled={disabled}
            aria-label={`Digit ${i + 1} of ${length}`}
            aria-invalid={!!error}
            value={value[i] ?? ""}
            onFocus={(e) => e.currentTarget.select()}
            onChange={(e) => {
              const digits = e.target.value.replace(/\D/g, "");
              if (!digits) return;
              // One digit types in place; several (paste, autofill) fill from this box on.
              set(value.slice(0, i) + digits + value.slice(i + digits.length));
              focus(i + digits.length);
            }}
            onKeyDown={(e) => {
              if (e.key === "Backspace") {
                e.preventDefault();
                if (value[i]) set(value.slice(0, i) + value.slice(i + 1));
                else { set(value.slice(0, Math.max(0, i - 1)) + value.slice(i)); focus(i - 1); }
              } else if (e.key === "ArrowLeft") focus(i - 1);
              else if (e.key === "ArrowRight") focus(i + 1);
            }}
            className={cx("h-14 min-w-0 flex-1 rounded-control bg-surface-2 text-center t-title2 num text-text outline-none", error && "ring-1 ring-danger")}
          />
        ))}
      </div>
      {error && <p role="alert" className="t-footnote mt-3 text-danger">{error}</p>}
    </div>
  );
}
