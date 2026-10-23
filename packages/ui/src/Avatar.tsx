import { cx } from "./cx";

function initials(name: string) {
  const parts = name.replace(/^(dr|mr|ms|mrs)\.?\s+/i, "").trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

/** Initials only: no photos, so nothing to load and nothing identifying in the DOM. */
export function Avatar({ name, size = 40, className }: { name: string; size?: number; className?: string }) {
  return (
    <span
      aria-hidden="true"
      style={{ width: size, height: size, fontSize: size * 0.4 }}
      className={cx("inline-flex shrink-0 items-center justify-center rounded-full bg-line-wash font-display font-bold text-line", className)}
    >
      {initials(name)}
    </span>
  );
}
