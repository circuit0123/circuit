"use client";

import { ChevronLeft } from "lucide-react";
import { animate, motion, useMotionValue, useReducedMotion } from "motion/react";
import { useRef } from "react";
import { cx } from "./cx";
import { LargeTitleHeader } from "./LargeTitleHeader";
import { fade, pushSpring } from "./theme";
import { BarButton, TopBar } from "./TopBar";

/**
 * A top-level tab screen (DESIGN.md §5 "Large titles"): the bar, then a Large title that collapses into the bar on scroll, with 8px
 * between it and the first block. Content is a stack of `Section`s; they bring their own side padding, so a feed can run edge to edge.
 */
export function Screen({ title, left, right, children, className }: { title: string; left?: React.ReactNode; right?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <>
      <TopBar title={title} left={left} right={right} mobileOnly />
      {/* The first block sits 8px under the title (the h1's padding), not a section gap away. */}
      <div className={cx("[&>h1+*]:mt-0", className)}>
        <LargeTitleHeader title={title} />
        {children}
      </div>
    </>
  );
}

type PushProps = {
  title?: string;
  /** Draw `title` as a Large title under the bar (Notifications.dc.html) instead of centred in it. */
  largeTitle?: boolean;
  /** Text next to the back chevron, e.g. "Today": where Back goes. */
  backLabel?: string;
  onBack: () => void;
  right?: React.ReactNode;
  /** Pinned to the bottom (a sticky Apply button, a message composer). */
  footer?: React.ReactNode;
  /** No side padding on a phone, so rows and their hairlines run edge to edge; the content brings its own 16px (`px-4 lg:px-0`). */
  bleed?: boolean;
  children: React.ReactNode;
  className?: string;
};

/**
 * A pushed screen: slides in from the right (0.4s, no bounce), has a back chevron, and a swipe from
 * the left edge goes back following the finger. Tab swiping is off here (DESIGN.md §3).
 */
export function PushScreen({ title, largeTitle, backLabel, onBack, right, footer, bleed, children, className }: PushProps) {
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
      <header className={cx("material sticky top-0 z-20 grid min-h-11 grid-cols-[1fr_auto_1fr] items-center border-b px-2 pt-[env(safe-area-inset-top)]", largeTitle ? "border-transparent" : "border-separator")}>
        <div className="flex justify-start">
          {backLabel ? (
            <button type="button" onClick={leave} aria-label={`Back to ${backLabel}`} className="flex min-h-11 items-center gap-0.5 rounded-full pl-1 pr-3 t-body active:opacity-80">
              <ChevronLeft size={24} strokeWidth={1.75} aria-hidden />{backLabel}
            </button>
          ) : (
            <BarButton label="Back" onClick={leave}><ChevronLeft size={24} strokeWidth={1.75} /></BarButton>
          )}
        </div>
        <span className="t-headline min-w-0 truncate text-center">{largeTitle ? null : title}</span>
        <div className="flex justify-end">{right}</div>
      </header>
      <div className={cx("mx-auto w-full max-w-[600px] pb-24 pt-4", bleed ? "lg:px-4" : "px-4", className)}>
        {largeTitle && title && <h1 className={cx("t-large -mt-4 pb-2 pt-1", bleed && "px-4 lg:px-0")}>{title}</h1>}
        {children}
      </div>
      {footer && (
        <div className="material fixed inset-x-0 bottom-0 z-20 border-t border-separator px-4 pb-[calc(12px+env(safe-area-inset-bottom))] pt-3">
          <div className="mx-auto w-full max-w-[600px]">{footer}</div>
        </div>
      )}
    </motion.div>
  );
}
