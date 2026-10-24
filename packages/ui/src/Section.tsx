import { cx } from "./cx";

type Props = {
  /** Title 3 header with 12px below it. Leave out when the content brings its own heading. */
  title?: string;
  /** Names the region for screen readers. Defaults to `title`. */
  label?: string;
  /** Run edge to edge (feeds with full-bleed media). Otherwise 16px on a phone, 0 on desktop where the column has its own edges. */
  bleed?: boolean;
  className?: string;
  children: React.ReactNode;
};

/** A block of a screen (DESIGN.md §5 "Breathing room"): 40px of space above it on a phone, 56px on desktop, and none above the first one. */
export function Section({ title, label, bleed, className, children }: Props) {
  return (
    <section aria-label={label ?? title} className={cx("mt-section first:mt-0", !bleed && "px-4 lg:px-0", className)}>
      {title && <h2 className="t-title3 mb-3">{title}</h2>}
      {children}
    </section>
  );
}
