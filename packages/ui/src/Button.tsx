import { forwardRef } from "react";
import { cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "text" | "destructive";

const variants: Record<ButtonVariant, string> = {
  primary: "bg-primary text-on-primary",
  secondary: "bg-surface-2 text-text",
  text: "bg-transparent text-text",
  destructive: "bg-surface text-danger",
};

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  icon?: React.ReactNode;
};

/** 50px tall on mobile, full width at the bottom of forms and sheets (pass className="w-full"). One primary per screen. Icons are always paired with a label. */
export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = "secondary", icon, className, children, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx(
        "inline-flex min-h-[50px] items-center justify-center gap-2 rounded-control px-5 t-body font-semibold transition-transform active:scale-[0.97] disabled:opacity-50 disabled:active:scale-100 lg:min-h-11",
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

type LinkProps = React.AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: ButtonVariant };

/** A link that looks like a Button (50px on every screen size): for calls to action that leave the page, e.g. on the landing site. */
export function LinkButton({ variant = "secondary", className, children, ...rest }: LinkProps) {
  return (
    <a
      data-press
      className={cx("inline-flex min-h-[50px] items-center justify-center gap-2 rounded-control px-7 t-body font-semibold transition-transform active:scale-[0.97]", variants[variant], className)}
      {...rest}
    >
      {children}
    </a>
  );
}
