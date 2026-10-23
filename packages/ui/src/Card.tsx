import { cx } from "./cx";

/** Surface with a hairline border. No shadow: depth comes from layering (DESIGN.md §5). */
export function Card({ className, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cx("rounded-card border border-border bg-surface", className)} {...rest} />;
}
