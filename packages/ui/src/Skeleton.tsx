import { cx } from "./cx";

/** Loading placeholder. DESIGN.md §11: skeletons for every loading state, no spinners. */
export function Skeleton({ className, round }: { className?: string; round?: boolean }) {
  return <div aria-hidden className={cx("skeleton", round ? "rounded-full" : "rounded-lg", className)} />;
}
