import { Button } from "./Button";
import { cx } from "./cx";

type Props = {
  /** What happened and what to do, in one sentence (DESIGN.md §9): "Couldn't load jobs. Check your connection and pull to refresh." */
  text: string;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
};

/** The error twin of EmptyState: a broken ring, one sentence, one secondary button. */
export function ErrorState({ text, onRetry, retryLabel = "Try again", className }: Props) {
  return (
    <div role="alert" className={cx("flex flex-col items-start gap-4", className)}>
      <svg width="56" height="56" viewBox="0 0 56 56" fill="none" aria-hidden className="text-danger">
        <circle cx="28" cy="28" r="22" stroke="currentColor" strokeWidth="2" strokeDasharray="70 68" strokeLinecap="round" opacity="0.7" />
        <circle cx="28" cy="28" r="2.5" fill="currentColor" />
      </svg>
      <p className="t-body max-w-[32ch] text-text-muted">{text}</p>
      {onRetry && <Button variant="secondary" onClick={onRetry}>{retryLabel}</Button>}
    </div>
  );
}
