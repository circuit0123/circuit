import { Children } from "react";
import { cx } from "./cx";

type Props = {
  /** Small caption above the group, in `text-muted`. */
  header?: string;
  /** Explanation below the group. */
  footer?: string;
  children: React.ReactNode;
  className?: string;
};

/**
 * An inset grouped list (DESIGN.md §5 "iOS-quality patterns"): rows on one `surface` with 10px corners and a hairline between rows,
 * inset to line up with the text. Used for settings, profile About and account screens. Holds ListRows.
 */
export function GroupedList({ header, footer, children, className }: Props) {
  const rows = Children.toArray(children);
  return (
    <section className={cx("px-4 lg:px-0", className)}>
      {header && <h2 className="t-footnote mb-2 px-4 uppercase text-text-muted">{header}</h2>}
      <ul className="overflow-hidden rounded-group bg-surface">
        {rows.map((row, i) => (
          <li key={i} className={cx(i > 0 && "border-t border-separator ml-4")}>{row}</li>
        ))}
      </ul>
      {footer && <p className="t-footnote mt-2 px-4 text-text-muted">{footer}</p>}
    </section>
  );
}
