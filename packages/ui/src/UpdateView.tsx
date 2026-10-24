"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useCallback, useEffect } from "react";
import { Avatar } from "./Avatar";
import { VerifiedBadge } from "./Badge";
import { Button } from "./Button";
import { WireVisual, firstName, whenSpoken, type WireUpdate } from "./LiveWire";
import { useOverlay } from "./overlay";
import { fade, sheetSpring, spring } from "./theme";

type Props = {
  open: boolean;
  updates: WireUpdate[];
  index: number;
  onIndex: (i: number) => void;
  onClose: () => void;
  onAction: (u: WireUpdate) => void;
};

const SWIPE = 80;

/**
 * Full-screen Update view (DESIGN.md §4): the picture, what happened, why it matters to you, one action.
 * Swipe sideways between updates, down to close. Buttons do the same, so no gesture is required.
 */
export function UpdateView({ open, updates, index, onIndex, onClose, onAction }: Props) {
  const reduce = useReducedMotion();
  const ref = useOverlay(open, onClose);
  const u = updates[index];
  const next = useCallback(() => (index + 1 >= updates.length ? onClose() : onIndex(index + 1)), [index, updates.length, onClose, onIndex]);
  const prev = useCallback(() => onIndex(Math.max(0, index - 1)), [index, onIndex]);
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => { if (e.key === "ArrowRight") next(); if (e.key === "ArrowLeft") prev(); };
    document.addEventListener("keydown", k);
    return () => document.removeEventListener("keydown", k);
  }, [open, next, prev]);

  return (
    <AnimatePresence>
      {open && u && (
        <motion.div
          ref={ref}
          role="dialog"
          aria-modal="true"
          aria-label="Update"
          tabIndex={-1}
          className="fixed inset-0 z-50 flex flex-col bg-bg outline-none lg:items-center lg:bg-black/80"
          initial={reduce ? { opacity: 0 } : { y: "100%" }}
          animate={reduce ? { opacity: 1 } : { y: 0 }}
          exit={reduce ? { opacity: 0 } : { y: "100%" }}
          transition={reduce ? fade : sheetSpring}
        >
          <motion.div
            className="relative flex min-h-0 w-full flex-1 flex-col bg-bg lg:max-w-[460px]"
            drag={reduce ? false : true}
            dragDirectionLock
            dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
            dragElastic={{ left: 0.5, right: 0.5, top: 0, bottom: 0.6 }}
            dragSnapToOrigin
            transition={spring}
            onDragEnd={(_, d) => {
              if (d.offset.y > 140 || d.velocity.y > 700) onClose();
              else if (d.offset.x < -SWIPE || d.velocity.x < -600) next();
              else if (d.offset.x > SWIPE || d.velocity.x > 600) prev();
            }}
          >
            <p className="t-footnote px-4 pt-3 text-text-muted" aria-live="polite">{index + 1} of {updates.length}</p>
            <div className="flex items-center gap-3 px-4 py-2">
              <Avatar id={u.person.id} name={u.person.name} src={u.person.photo} size={40} />
              <div className="min-w-0 flex-1">
                <p className="t-body truncate font-semibold">{u.person.name} <VerifiedBadge level={u.person.level} /></p>
                <p className="t-footnote truncate text-text-muted">{whenSpoken(u.when)}</p>
              </div>
              <button onClick={onClose} aria-label="Close" className="flex h-11 w-11 items-center justify-center rounded-full text-text">
                <X size={24} strokeWidth={1.75} />
              </button>
            </div>
            <AnimatePresence mode="wait" initial={false}>
              <motion.div key={u.key} className="flex min-h-0 flex-1 flex-col overflow-y-auto" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={fade}>
                <div className="relative w-full overflow-hidden bg-surface-2" style={{ aspectRatio: "4 / 5", maxHeight: "55dvh" }}>
                  <WireVisual visual={u.visual} />
                </div>
                <div className="flex flex-col gap-1 px-4 py-4">
                  <h2 className="t-title2">{u.headline}</h2>
                  <p className="t-body text-text-muted">{u.reason}</p>
                </div>
              </motion.div>
            </AnimatePresence>
            <div className="flex items-center gap-3 px-4 pb-6 pt-2">
              <button onClick={prev} disabled={index === 0} aria-label={`Previous update, ${firstName(updates[Math.max(0, index - 1)].person.name)}`} className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-surface-2 text-text disabled:opacity-40">
                <ChevronLeft size={24} strokeWidth={1.75} />
              </button>
              <Button variant="primary" className="flex-1" onClick={() => onAction(u)}>{u.actionLabel}</Button>
              <button onClick={next} aria-label={index + 1 >= updates.length ? "Close" : "Next update"} className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-surface-2 text-text">
                <ChevronRight size={24} strokeWidth={1.75} />
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
