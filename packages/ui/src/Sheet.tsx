"use client";

import { AnimatePresence, animate, motion, useDragControls, useMotionValue, useReducedMotion } from "motion/react";
import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { cx } from "./cx";
import { useOverlay } from "./overlay";
import { fade, sheetSpring } from "./theme";

export type Detent = "medium" | "large";

type Props = {
  open: boolean;
  onClose: () => void;
  title: string;
  /** Where it opens. Default: medium. */
  detent?: Detent;
  /** Heights it can rest at. Default: both. A sheet with one detent can only be dismissed, not resized. */
  detents?: Detent[];
  children: React.ReactNode;
  className?: string;
  /** Where to draw it. Default: the end of <body>. /design passes a themed panel so the sheet wears that panel's theme. */
  container?: HTMLElement | null;
};

const SHARE = { medium: 0.5, large: 0.92 } as const;

function useDesktop() {
  const [on, setOn] = useState(false);
  useEffect(() => {
    const m = window.matchMedia("(min-width: 1024px)");
    const f = () => setOn(m.matches);
    f();
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, []);
  return on;
}

/**
 * A sheet with detents (DESIGN.md §5 "iOS-quality patterns"): springs up to medium (half the screen) or large, has a grabber,
 * drags between detents and dismisses by distance or flick, dims the page and scales the page behind to 0.94 (anything marked
 * `data-page-behind`). Drag from the header; the content scrolls on its own. On desktop it is a centred dialog.
 */
export function Sheet({ open, onClose, title, detent = "medium", detents = ["medium", "large"], children, className, container }: Props) {
  const desktop = useDesktop();
  const reduce = useReducedMotion();
  const ref = useOverlay(open, onClose);
  const id = useId();
  const controls = useDragControls();
  const y = useMotionValue(0);
  const [at, setAt] = useState<Detent>(detent);

  const vh = typeof window === "undefined" ? 800 : window.innerHeight;
  const full = Math.round(vh * SHARE.large);
  const stopY = (d: Detent) => full - Math.round(vh * SHARE[d]);
  const closedY = full + 24;

  // Reset to the requested detent each time it opens, and tell the page behind to step back.
  useEffect(() => {
    if (!open) return;
    setAt(detent);
    const d = document.documentElement;
    d.dataset.sheetOpen = "";
    d.style.setProperty("--sheet-origin", `${window.scrollY + window.innerHeight / 2}px`);
    return () => { delete d.dataset.sheetOpen; };
  }, [open, detent]);

  if (typeof document === "undefined") return null;

  const snap = (to: Detent) => { setAt(to); animate(y, stopY(to), sheetSpring); };
  const release = (vy: number) => {
    const cur = y.get();
    const stops = [...detents].sort((a, b) => stopY(a) - stopY(b)); // top (large) first
    const lowest = stopY(stops[stops.length - 1]);
    if (vy > 800 || cur > lowest + (closedY - lowest) * 0.45) { onClose(); return; }
    if (Math.abs(vy) > 400) {
      const pick = vy < 0 ? stops.find((d) => stopY(d) < cur - 4) ?? stops[0] : [...stops].reverse().find((d) => stopY(d) > cur + 4) ?? stops[stops.length - 1];
      snap(pick);
      return;
    }
    snap(stops.reduce((a, b) => (Math.abs(stopY(b) - cur) < Math.abs(stopY(a) - cur) ? b : a)));
  };

  const header = (
    <div
      className="shrink-0 touch-none select-none px-4 pb-2 pt-2"
      onPointerDown={desktop ? undefined : (e) => controls.start(e)}
    >
      <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-text-subtle/50" aria-hidden />
      <h2 id={id} className="t-headline">{title}</h2>
    </div>
  );
  const body = <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 pb-[calc(24px+env(safe-area-inset-bottom))]">{children}</div>;

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center lg:items-center">
          <motion.div className="absolute inset-0 bg-black/60" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={fade} />
          {desktop ? (
            <motion.div
              ref={ref}
              role="dialog"
              aria-modal="true"
              aria-labelledby={id}
              tabIndex={-1}
              className={cx("relative flex max-h-[80dvh] w-full max-w-lg flex-col rounded-sheet bg-surface shadow-lift outline-none", className)}
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              transition={reduce ? fade : sheetSpring}
            >
              {header}
              {body}
            </motion.div>
          ) : (
            <motion.div
              ref={ref}
              role="dialog"
              aria-modal="true"
              aria-labelledby={id}
              tabIndex={-1}
              className={cx("relative flex w-full flex-col rounded-t-sheet bg-surface shadow-lift outline-none", className)}
              style={{ height: full, y: reduce ? 0 : y }}
              initial={reduce ? { opacity: 0 } : { y: closedY }}
              animate={reduce ? { opacity: 1 } : { y: stopY(at) }}
              exit={reduce ? { opacity: 0 } : { y: closedY }}
              transition={reduce ? fade : sheetSpring}
              drag={reduce ? false : "y"}
              dragControls={controls}
              dragListener={false}
              dragMomentum={false}
              dragElastic={0}
              onDrag={() => { if (y.get() < 0) y.set(0); }}
              onDragEnd={(_, info) => release(info.velocity.y)}
            >
              {header}
              {body}
            </motion.div>
          )}
        </div>
      )}
    </AnimatePresence>,
    container ?? document.body,
  );
}
