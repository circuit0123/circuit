import { ChevronRight } from "lucide-react";
import { cx } from "./cx";

type Props = {
  title: string;
  /** A second line in `text-muted`. Makes the row 64px instead of 56px. */
  subtitle?: string;
  /** An Avatar or an icon, 16px from the text. */
  leading?: React.ReactNode;
  /** A value shown in `text-muted` before the chevron ("Dark", "Off"). */
  value?: string;
  /** Anything at the end that is not a value (a Toggle, a Badge). */
  trailing?: React.ReactNode;
  /** Show the chevron. Defaults to true when the row is a link or button. */
  chevron?: boolean;
  /** Danger styling for destructive rows ("Delete account"). */
  danger?: boolean;
  href?: string;
  onClick?: () => void;
  className?: string;
};

/** One row of a list: min 56px (64px with a subtitle), 16px between the leading item and the text (DESIGN.md §5 "Rows"). A link, a button, or plain. */
export function ListRow({ title, subtitle, leading, value, trailing, chevron, danger, href, onClick, className }: Props) {
  const interactive = !!href || !!onClick;
  const body = (
    <>
      {leading && <span className="flex shrink-0 items-center justify-center">{leading}</span>}
      <span className="min-w-0 flex-1 text-left">
        <span className={cx("t-body block", danger ? "text-danger" : "text-text")}>{title}</span>
        {subtitle && <span className="t-subhead block text-text-muted">{subtitle}</span>}
      </span>
      {value && <span className="t-body shrink-0 text-text-muted">{value}</span>}
      {trailing}
      {(chevron ?? interactive) && <ChevronRight aria-hidden size={20} strokeWidth={1.75} className="shrink-0 text-text-subtle" />}
    </>
  );
  const base = cx("flex w-full items-center gap-4 px-4 py-2", subtitle ? "min-h-row-sub" : "min-h-row", interactive && "active:opacity-80", className);
  if (href) return <a href={href} data-press className={base}>{body}</a>;
  if (onClick) return <button type="button" onClick={onClick} className={base}>{body}</button>;
  return <div className={base}>{body}</div>;
}
