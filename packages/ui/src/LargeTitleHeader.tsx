import { cx } from "./cx";

/** The Large title (34/600) every tab screen starts with. It scrolls under the TopBar, whose inline title fades in as it goes (iOS behaviour). */
export function LargeTitleHeader({ title, className }: { title: string; className?: string }) {
  return <h1 className={cx("t-large px-4 pb-2 pt-1 lg:px-0 lg:pt-10", className)}>{title}</h1>;
}
