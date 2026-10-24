"use client";

import { ChevronLeft } from "lucide-react";
import { animate, motion, useMotionValue, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";
import { cx } from "./cx";
import { fade, pushSpring } from "./theme";

/** Fades the inline title and hairline in as the large title scrolls under the bar. Tied to scroll position, not time. */
function useCollapse(ref: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
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
  }, [ref]);
}

type BarProps = {
  /** Inline title; it appears as the large title collapses. */
  title?: string;
  /** Show this in the centre all the time (the Circuit wordmark on Home). */
  wordmark?: React.ReactNode;
  left?: React.ReactNode;
  right?: React.ReactNode;
  /** Hide on desktop, where the left rail and the large title do the job. */
  mobileOnly?: boolean;
  className?: string;
};

/** Translucent top bar (DESIGN.md §5 Materials). 44px plus the top safe area. */
export function ScreenBar({ title, wordmark, left, right, mobileOnly, className }: BarProps) {
  const ref = useRef<HTMLElement>(null);
  useCollapse(ref);
  return (
    <header
      ref={ref}
      className={cx("material sticky top-0 z-20 grid min-h-11 grid-cols-[1fr_auto_1fr] items-center px-2 pt-[env(safe-area-inset-top)]", mobileOnly && "lg:hidden", className)}
      style={{ "--collapse": 0 } as React.CSSProperties}
    >
      <div className="flex justify-start">{left}</div>
      <div className="min-w-0 text-center">
        {wordmark ?? (title && <span className="t-headline block truncate" style={{ opacity: "var(--collapse)" }}>{title}</span>)}
      </div>
      <div className="flex justify-end">{right}</div>
      <span aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-separator" style={{ opacity: wordmark ? 1 : "var(--collapse)" }} />
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

/** A top-level tab screen: bar, a Large title that collapses into the bar, then the content. */
export function Screen({ title, right, children, className }: { title: string; right?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <>
      <ScreenBar title={title} right={right} mobileOnly />
      <div className={cx("px-4 lg:px-0", className)}>
        <h1 className="t-large pb-3 pt-1 lg:pt-8">{title}</h1>
        {children}
      </div>
    </>
  );
}

type PushProps = {
  title?: string;
  onBack: () => void;
  right?: React.ReactNode;
  /** Pinned to the bottom (a sticky Apply button, a message composer). */
  footer?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
};

/**
 * A pushed screen: slides in from the right (0.4s, no bounce), has a back chevron, and a swipe from
 * the left edge goes back following the finger. Tab swiping is off here (DESIGN.md §3).
 */
export function PushScreen({ title, onBack, right, footer, children, className }: PushProps) {
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const start = useRef<{ x0: number; y0: number; t: number; vx: number; lastX: number; lastT: number; on: boolean } | null>(null);
  const width = () => (typeof window === "undefined" ? 375 : window.innerWidth);
  const leave = () => { if (reduce) onBack(); else animate(x, width(), { ...pushSpring, onComplete: onBack }); };

  return (
    <motion.div
      className="min-h-dvh bg-bg"
      initial={reduce ? { opacity: 0 } : { x: "100%" }}
      animate={reduce ? { opacity: 1 } : { x: 0 }}
      transition={reduce ? fade : pushSpring}
      style={{ x: reduce ? 0 : x, touchAction: "pan-y" }}
      onPointerDown={(e) => {
        if (reduce || e.pointerType === "mouse" || e.clientX > 24) return;
        start.current = { x0: e.clientX, y0: e.clientY, t: e.timeStamp, vx: 0, lastX: e.clientX, lastT: e.timeStamp, on: false };
      }}
      onPointerMove={(e) => {
        const s = start.current;
        if (!s) return;
        const dx = e.clientX - s.x0;
        if (!s.on) {
          if (Math.abs(dx) < 10) return;
          if (dx < 0 || Math.abs(e.clientY - s.y0) > dx * 0.577) { start.current = null; return; }
          s.on = true;
          e.currentTarget.setPointerCapture(e.pointerId);
        }
        s.vx = 0.8 * s.vx + 0.2 * ((e.clientX - s.lastX) / Math.max(1, e.timeStamp - s.lastT)) * 1000;
        s.lastX = e.clientX; s.lastT = e.timeStamp;
        x.set(Math.max(0, dx));
      }}
      onPointerUp={() => {
        const s = start.current;
        start.current = null;
        if (!s?.on) return;
        if (x.get() / width() > 0.35 || s.vx > 600) leave();
        else animate(x, 0, pushSpring);
      }}
      onPointerCancel={() => { if (start.current?.on) animate(x, 0, pushSpring); start.current = null; }}
    >
      <header className="material sticky top-0 z-20 grid min-h-11 grid-cols-[1fr_auto_1fr] items-center border-b border-separator px-2 pt-[env(safe-area-inset-top)]">
        <div className="flex justify-start">
          <BarButton label="Back" onClick={leave}><ChevronLeft size={24} strokeWidth={1.75} /></BarButton>
        </div>
        <span className="t-headline min-w-0 truncate text-center">{title}</span>
        <div className="flex justify-end">{right}</div>
      </header>
      <div className={cx("mx-auto w-full max-w-[600px] px-4 pb-24 pt-4", className)}>{children}</div>
      {footer && (
        <div className="material fixed inset-x-0 bottom-0 z-20 border-t border-separator px-4 pb-[calc(12px+env(safe-area-inset-bottom))] pt-3">
          <div className="mx-auto w-full max-w-[600px]">{footer}</div>
        </div>
      )}
    </motion.div>
  );
}
