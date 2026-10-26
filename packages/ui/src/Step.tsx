"use client";

import { ChevronLeft } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";
import { cx } from "./cx";
import { BarButton } from "./TopBar";
import { fade, pushSpring } from "./theme";

type StepProps = {
  title: string;
  subhead?: string;
  /** 0 to 1. A thin bar at the very top, never step numbers (DESIGN.md §4). Omit on screens outside onboarding. */
  progress?: number;
  onBack?: () => void;
  /** "Skip" as a text button top-right, only on optional steps. */
  onSkip?: () => void;
  /** Something above the title, e.g. the logo mark on the last screen (Ready.dc.html). */
  lead?: React.ReactNode;
  /** The one primary button, pinned to the bottom (50px, full width), plus anything small under it. */
  footer?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
};

/**
 * One thing per screen (DESIGN.md §4 "Sign-up and onboarding"): progress bar, back chevron, a Large
 * title, one short subhead, the single input or choice, then the primary button at the bottom.
 * A centred 440px column on desktop.
 */
export function Step({ title, subhead, progress, onBack, onSkip, lead, footer, children, className }: StepProps) {
  const ref = useEdgeSwipeBack(onBack);
  return (
    <main ref={ref} className="mx-auto flex min-h-dvh w-full max-w-[440px] flex-col px-4 lg:justify-center lg:pb-12">
      {progress !== undefined && (
        <div className="fixed inset-x-0 top-0 z-30 h-[3px] bg-surface-2" role="progressbar" aria-label="Progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)}>
          <motion.div className="h-full origin-left bg-live" initial={false} animate={{ scaleX: Math.min(1, Math.max(0, progress)) }} transition={pushSpring} style={{ width: "100%" }} />
        </div>
      )}
      <header className="-mx-2 flex min-h-11 items-center justify-between pt-[env(safe-area-inset-top)]">
        {onBack ? <BarButton label="Back" onClick={onBack}><ChevronLeft size={24} strokeWidth={1.75} /></BarButton> : <span className="h-11 w-11" aria-hidden />}
        {onSkip && <button type="button" onClick={onSkip} className="min-h-11 px-3 t-body text-text-muted active:opacity-80">Skip</button>}
      </header>
      {lead && <div className="mt-8">{lead}</div>}
      <h1 className={cx("t-large", lead ? "mt-6" : "mt-4")}>{title}</h1>
      {subhead && <p className="t-callout mt-2 text-text-muted">{subhead}</p>}
      <div className={cx("mt-6 flex-1 lg:flex-none", className)}>{children}</div>
      {footer && <footer className="sticky bottom-0 -mx-4 flex flex-col gap-2 bg-bg px-4 lg:mt-8 pb-[max(16px,env(safe-area-inset-bottom))] pt-3">{footer}</footer>}
    </main>
  );
}

const EDGE = 24;
const COMMIT = 72;

/** Swiping right from the left edge goes back, as on every pushed screen (DESIGN.md §4). Touch only; never while a field has focus or motion is reduced. */
function useEdgeSwipeBack(onBack?: () => void) {
  const ref = useRef<HTMLElement>(null);
  const back = useRef(onBack);
  useEffect(() => { back.current = onBack; }, [onBack]);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let start: { x: number; y: number } | null = null;
    const down = (e: TouchEvent) => {
      const t = e.touches[0];
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      start = t.clientX <= EDGE && back.current && !reduce ? { x: t.clientX, y: t.clientY } : null;
    };
    const move = (e: TouchEvent) => {
      if (!start) return;
      const t = e.touches[0];
      const dx = t.clientX - start.x;
      const dy = Math.abs(t.clientY - start.y);
      if (dy > dx) { start = null; return; }
      if (dx >= COMMIT) { start = null; back.current?.(); }
    };
    const end = () => { start = null; };
    el.addEventListener("touchstart", down, { passive: true });
    el.addEventListener("touchmove", move, { passive: true });
    el.addEventListener("touchend", end, { passive: true });
    return () => { el.removeEventListener("touchstart", down); el.removeEventListener("touchmove", move); el.removeEventListener("touchend", end); };
  }, []);
  return ref;
}

/** Slides steps in from the right (and back from the left), as pushed screens do. A 150ms fade when motion is reduced. */
export function StepTransition({ stepKey, direction = 1, children }: { stepKey: string; direction?: 1 | -1; children: React.ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <div className="overflow-x-clip">
      <AnimatePresence initial={false} mode="popLayout" custom={direction}>
        <motion.div
          key={stepKey}
          custom={direction}
          variants={{
            enter: (d: number) => (reduce ? { opacity: 0 } : { x: d > 0 ? "100%" : "-30%", opacity: d > 0 ? 1 : 0.6 }),
            center: { x: 0, opacity: 1 },
            exit: (d: number) => (reduce ? { opacity: 0 } : { x: d > 0 ? "-30%" : "100%", opacity: d > 0 ? 0.6 : 1 }),
          }}
          initial="enter"
          animate="center"
          exit="exit"
          transition={reduce ? fade : pushSpring}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
