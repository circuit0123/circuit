import { cx } from "./cx";

export type Strength = "strong" | "good";

/** DESIGN.md §4: words, never a low percentage. Under 0.55 there is no label (and no drop card). */
export function strengthLabel(score: number): Strength | null {
  if (score >= 0.75) return "strong";
  if (score >= 0.55) return "good";
  return null;
}

export function MatchStrength({ strength, className }: { strength: Strength | null | undefined; className?: string }) {
  if (!strength) return null;
  return (
    <span className={cx("inline-flex items-center rounded-full bg-surface-2 px-2 py-0.5 t-micro font-semibold", strength === "strong" ? "text-success" : "text-text", className)}>
      {strength === "strong" ? "Strong match" : "Good match"}
    </span>
  );
}
