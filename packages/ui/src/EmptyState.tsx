import { cx } from "./cx";

/** A plain open ring: the app's shape of "nothing here yet". One sentence, one action. */
export function EmptyState({ text, action, className }: { text: string; action?: React.ReactNode; className?: string }) {
  return (
    <div className={cx("flex flex-col items-start gap-4 px-4 py-8", className)}>
      <svg width="56" height="56" viewBox="0 0 56 56" fill="none" aria-hidden className="text-border">
        <circle cx="28" cy="28" r="22" stroke="currentColor" strokeWidth="2" strokeDasharray="110 28" strokeLinecap="round" />
      </svg>
      <p className="t-body max-w-[32ch] text-text-muted">{text}</p>
      {action}
    </div>
  );
}
