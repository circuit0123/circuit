"use client";

import { useEffect, useRef } from "react";
import { cx } from "./cx";

/** Fades the inline title and hairline in as the large title scrolls under the bar. Tied to scroll position, not time. */
function useCollapse(ref: React.RefObject<HTMLElement | null>, fixed?: number) {
  useEffect(() => {
    const el = ref.current;
    if (!el || fixed !== undefined) return;
    let raf = 0;
    const update = () => {
      raf = 0;
      if (!el.offsetParent) return; // pane is hidden
      const c = Math.min(1, Math.max(0, (window.scrollY - 8) / 32));
      el.style.setProperty("--collapse", String(c));
    };
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(update); };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => { window.removeEventListener("scroll", onScroll); cancelAnimationFrame(raf); };
  }, [ref, fixed]);
}

export type TopBarProps = {
  /** Inline title; it appears as the large title collapses. */
  title?: string;
  left?: React.ReactNode;
  right?: React.ReactNode;
  /** Hide on desktop, where the left rail and the large title do the job. */
  mobileOnly?: boolean;
  /** Draw in the flow instead of sticking to the top of the window, with the title fixed at this collapse (0 = large title showing, 1 = collapsed). For /design. */
  inline?: number;
  className?: string;
};

/** Translucent top bar (DESIGN.md §5 Materials). 44px plus the top safe area. Its title fades in as the Large title scrolls under it. */
export function TopBar({ title, left, right, mobileOnly, inline, className }: TopBarProps) {
  const ref = useRef<HTMLElement>(null);
  useCollapse(ref, inline);
  return (
    <header
      ref={ref}
      className={cx("material z-20 grid min-h-11 grid-cols-[1fr_auto_1fr] items-center px-2 pt-[env(safe-area-inset-top)]", inline === undefined ? "sticky top-0" : "relative", mobileOnly && "lg:hidden", className)}
      style={{ "--collapse": inline ?? 0 } as React.CSSProperties}
    >
      <div className="flex justify-start">{left}</div>
      <div className="min-w-0 text-center">
        {title && <span className="t-headline block truncate" style={{ opacity: "var(--collapse)" }}>{title}</span>}
      </div>
      <div className="flex justify-end">{right}</div>
      <span aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-separator" style={{ opacity: "var(--collapse)" }} />
    </header>
  );
}

/** A 44px round icon button for bars. Always has a label for screen readers. */
export function BarButton({ label, children, ...rest }: { label: string } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" aria-label={label} className="relative flex h-11 w-11 items-center justify-center rounded-full active:opacity-80" {...rest}>
      {children}
    </button>
  );
}
