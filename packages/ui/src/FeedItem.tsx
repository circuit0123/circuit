import { cx } from "./cx";

/**
 * One item of a feed (build log, role, activity). No border and no background: it sits on `bg`, with 16px above and below
 * and one full-width hairline, so two items are 32px apart (DESIGN.md §5 "No boxes around everything").
 */
export function FeedItem({ className, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return <div data-feed-item className={cx("border-b border-separator py-4", className)} {...rest} />;
}
