import type { ButtonHTMLAttributes } from "react";
import { cx } from "./cx";
import { Icon } from "./icons";

type Props = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onChange"> & {
  selected?: boolean;
  onToggle?: (next: boolean) => void;
};

/** A selectable chip (toggle button). Used for needs, offers, skills and filters. */
export function Chip({ selected = false, onToggle, className, children, ...rest }: Props) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={() => onToggle?.(!selected)}
      className={cx(
        "inline-flex min-h-11 items-center gap-1.5 rounded-full border px-4 text-base transition-colors duration-150",
        selected ? "border-line bg-line-wash font-semibold text-ink" : "border-rule bg-surface text-ink hover:border-ink-soft",
        className,
      )}
      {...rest}
    >
      {selected && <Icon name="check" size={16} strokeWidth={2.25} />}
      {children}
    </button>
  );
}
