import { cx } from "./cx";

/** A surface: fill and radius, never a border as well (DESIGN.md §5 "Never a border AND a background on the same element"). No shadow: depth comes from layering. */
export function Card({ className, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cx("rounded-card bg-surface", className)} {...rest} />;
}
