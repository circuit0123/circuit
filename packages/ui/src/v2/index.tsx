import { cx } from "../cx";

/** UI v2 building blocks (docs/ui-v2-plan.md §2). Colours come from the --c-* tokens, which exist only under <html data-ui="v2">. */

/** The PM logo, copied from PMHome.dc.html: emerald arc, three nodes, "circuit" in Geist. Not the brand file; see the plan, risk 1. */
export function LogoV2({ height = 23, wordmark = true, className }: { height?: number; wordmark?: boolean; className?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-2", className)}>
      <svg width={(height * 32) / 23} height={height} viewBox="6 22 88 62" role="img" aria-label="Circuit">
        <defs>
          <mask id="logo-v2-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="100" height="100">
            <rect x="0" y="0" width="100" height="100" fill="#fff" />
            <circle cx="20" cy="68" r="11" fill="#000" />
            <circle cx="80" cy="68" r="11" fill="#000" />
            <circle cx="50" cy="39.5" r="8" fill="#000" />
          </mask>
        </defs>
        <path d="M20 68 C20 30, 80 30, 80 68" fill="none" stroke="#2FBF8A" strokeWidth="7" strokeLinecap="round" mask="url(#logo-v2-mask)" />
        <circle cx="20" cy="68" r="7" fill="#2FBF8A" />
        <circle cx="80" cy="68" r="7" fill="#2FBF8A" />
        <circle cx="50" cy="39.5" r="4" fill="#ECEDEF" />
      </svg>
      {wordmark && <span className="text-[18px] font-semibold tracking-[-0.035em]" style={{ fontSize: Math.round((height * 18) / 23) }}>circuit</span>}
    </span>
  );
}

/** Two-line display headline; the second line is outlined. One per screen. */
export function BigHeadline({ first, second, size = "app", as: Tag = "h1", className }: { first: string; second?: string; size?: "app" | "landing"; as?: "h1" | "h2"; className?: string }) {
  return (
    <Tag className={cx("m-0 font-bold leading-[0.97] tracking-[-0.055em]", size === "app" ? "text-[54px]" : "text-[clamp(60px,9vw,132px)]", className)}>
      {first}
      {second && (
        <>
          <br />
          <span style={{ color: "transparent", WebkitTextStroke: "1.5px var(--c-muted)" }}>{second}</span>
        </>
      )}
    </Tag>
  );
}

/** The rotated emerald band behind content. Decorative. The parent needs `relative overflow-hidden`. */
export function EmeraldBand({ className, rotate = -6 }: { className?: string; rotate?: number }) {
  return <div aria-hidden className={cx("pointer-events-none absolute bg-c-brand", className)} style={{ transform: `rotate(${rotate}deg)` }} />;
}

/** Featured card: grey shell, inner dark panel, and the stacked "deck" behind it. */
export function HeroCard({ children, deck = true, className }: { children: React.ReactNode; deck?: boolean; className?: string }) {
  return (
    <div className={cx("relative", className)}>
      {deck && (
        <>
          <div aria-hidden className="absolute inset-0 rounded-[22px] bg-c-brand" style={{ transform: "rotate(3deg)" }} />
          <div aria-hidden className="absolute inset-0 rounded-[22px] border border-c-border bg-c-card" style={{ transform: "rotate(-2deg)" }} />
        </>
      )}
      <div className="relative rounded-[22px] bg-c-hero p-2 text-c-hero-text">
        <div className="rounded-2xl bg-c-bg p-4">{children}</div>
      </div>
    </div>
  );
}

/** 40×40 round icon button. `label` is required: every icon button is named. */
export function IconButton({ label, children, className, ...rest }: { label: string } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" aria-label={label} {...rest} className={cx("relative flex h-10 w-10 items-center justify-center rounded-full border border-c-border bg-c-card text-c-text", className)}>
      {children}
    </button>
  );
}

/** Geist Mono uppercase label. 12px minimum (the plan bans muted text below 12px). */
export function MonoLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cx("font-mono text-[12px] uppercase tracking-[0.02em] text-c-muted", className)}>{children}</span>;
}

/** Toggle chip: off is a grey card, on is the tinted emerald pill. Uses aria-pressed. */
export function ChipV2({ on, onClick, children, className }: { on: boolean; onClick: () => void; children: React.ReactNode; className?: string }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cx("h-9 rounded-[10px] border px-3 text-[14px] font-medium", on ? "border-c-brand bg-c-bright-bg text-c-bright" : "border-c-border bg-c-card text-c-text", className)}
    >
      {children}
    </button>
  );
}
