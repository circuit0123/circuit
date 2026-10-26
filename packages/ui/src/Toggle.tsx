"use client";

import { cx } from "./cx";

type Props = {
  checked: boolean;
  onChange: (on: boolean) => void;
  /** What a screen reader hears ("Swipe between tabs", "Intros by email"). */
  label: string;
  disabled?: boolean;
  className?: string;
};

/**
 * An on/off switch (Appearance.dc.html): 51×31, white knob, the track takes the accent when on. A `role="switch"` button, so Space and
 * Enter flip it. Put it in a ListRow's `trailing`.
 */
export function Toggle({ checked, onChange, label, disabled, className }: Props) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cx(
        "relative h-[31px] w-[51px] shrink-0 rounded-full transition-colors duration-200 disabled:opacity-50",
        checked ? "bg-live" : "bg-surface-3 ring-1 ring-inset ring-separator",
        className,
      )}
    >
      <span
        aria-hidden
        className={cx("absolute top-0.5 h-[27px] w-[27px] rounded-full bg-white shadow-[0_2px_6px_rgba(0,0,0,.3)] transition-[left] duration-200 motion-reduce:transition-none", checked ? "left-[22px]" : "left-0.5")}
      />
    </button>
  );
}
