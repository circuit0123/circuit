import { forwardRef } from "react";
import { cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";

const variants: Record<ButtonVariant, string> = {
  primary: "bg-accent text-on-accent",
  secondary: "bg-surface-2 text-text border border-border",
  ghost: "bg-transparent text-text",
  destructive: "bg-transparent text-danger border border-danger",
};

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  icon?: React.ReactNode;
};

/** 48px tall on mobile. One primary per screen. Icons are always paired with a label. */
export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = "secondary", icon, className, children, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx(
        "inline-flex min-h-12 items-center justify-center gap-2 rounded-full px-5 t-body font-semibold transition-transform active:scale-[0.97] disabled:opacity-50 disabled:active:scale-100 lg:min-h-11",
        variants[variant],
        className,
      )}
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
});
