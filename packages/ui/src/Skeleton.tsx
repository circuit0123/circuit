import { cx } from "./cx";

/** A static placeholder block. No shimmer (DESIGN.md). */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cx("rounded-control bg-rule/70", className)} />;
}

export function SkeletonList({ rows = 3, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="rounded-card border border-rule bg-surface p-4">
          <Skeleton className="mb-3 h-5 w-2/5" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      ))}
    </div>
  );
}
