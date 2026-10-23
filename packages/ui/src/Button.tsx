import type { ButtonHTMLAttributes } from "react";
import { cx } from "./cx";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "quiet" | "danger";
  size?: "md" | "sm";
};

const variants = {
  primary: "bg-line text-white hover:bg-[#1a3fb8] disabled:bg-ink-soft",
  secondary: "bg-surface text-ink border border-rule hover:border-ink-soft",
  quiet: "bg-transparent text-line hover:bg-line-wash",
  danger: "bg-alert text-white hover:bg-[#8f1e18]",
};

export function Button({ variant = "primary", size = "md", className, type = "button", ...rest }: Props) {
  return (
    <button
      type={type}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-control font-semibold transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-70",
        size === "md" ? "min-h-11 px-4 text-base" : "min-h-11 px-3 text-sm",
        variants[variant],
        className,
      )}
      {...rest}
    />
  );
}
