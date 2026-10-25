import { BadgeCheck, MapPin, Lock, Waypoints } from "lucide-react";
import { cx } from "./cx";

const LABELS = { 1: "Email verified", 2: "Work verified", 3: "Verified by Circuit" } as const;

/** Verification levels 1–3 (F7). Weight and strength of the mark change with the level, not colour: the accent is kept for what is live (DESIGN.md §5). */
export function VerifiedBadge({ level, className }: { level: number; className?: string }) {
  if (level < 1) return null;
  const l = Math.min(level, 3) as 1 | 2 | 3;
  return (
    <span
      role="img"
      aria-label={LABELS[l]}
      title={LABELS[l]}
      className={cx("inline-flex shrink-0 align-middle", l === 1 ? "text-text-muted" : "text-text", className)}
    >
      <BadgeCheck size={16} strokeWidth={l === 3 ? 2.5 : 1.75} />
    </span>
  );
}

const pill = "inline-flex items-center gap-1 rounded-full px-2 py-0.5 t-footnote font-semibold";

export function BridgeBadge({ className }: { className?: string }) {
  return (
    <span className={cx(pill, "bg-surface-2 text-bridge", className)}>
      <Waypoints size={12} strokeWidth={1.75} aria-hidden />
      Bridge match
    </span>
  );
}

export function HiringBadge({ className }: { className?: string }) {
  return <span className={cx(pill, "bg-surface-3 text-live", className)}>Hiring</span>;
}

export function PrivateBadge({ className }: { className?: string }) {
  return (
    <span className={cx(pill, "bg-surface-3 text-text-muted", className)}>
      <Lock size={12} strokeWidth={1.75} aria-hidden />
      Private
    </span>
  );
}

export function DistanceBadge({ km, className }: { km: number; className?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-1 t-footnote text-text-muted", className)}>
      <MapPin size={14} strokeWidth={1.75} aria-hidden />
      <span className="num">{km < 10 ? km.toFixed(1) : Math.round(km)} km</span>
    </span>
  );
}
