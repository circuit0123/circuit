"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { X } from "lucide-react";
import { useCallback, useEffect } from "react";
import { Avatar } from "./Avatar";
import { VerifiedBadge } from "./Badge";
import { Button } from "./Button";
import { WireVisual, whenSpoken, type WireUpdate } from "./LiveWire";
import { useOverlay } from "./overlay";
import { fade, sheetSpring, spring } from "./theme";

type Props = {
  open: boolean;
  updates: WireUpdate[];
  index: number;
  onIndex: (i: number) => void;
  onClose: () => void;
  onAction: (u: WireUpdate) => void;
  /** Leave the action out for an update (an intro, for an under-18 member). */
  hideAction?: (u: WireUpdate) => boolean;
};

const SWIPE = 80;

/**
 * Full-screen Update view (DESIGN.md §4, Update.dc.html): the picture, who and when, what happened, why it matters to you, one action.
 * Swipe sideways between updates, down to close; the left and right edges of the picture, the arrow keys and Esc do the same, so no
 * gesture is required.
 */
export function UpdateView({ open, updates, index, onIndex, onClose, onAction, hideAction }: Props) {
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
            <AnimatePresence mode="wait" initial={false}>
              <motion.div key={u.key} className="flex min-h-0 flex-1 flex-col" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={fade}>
                <div className="relative h-[66%] min-h-[180px] shrink bg-surface">
                  <div className="h-full w-full"><WireVisual visual={u.visual} className={u.visual.kind === "pattern" ? "opacity-30" : undefined} /></div>
                  <button type="button" onClick={prev} disabled={index === 0} aria-label="Previous update" className="absolute inset-y-20 left-0 w-[30%] disabled:pointer-events-none" />
                  <button type="button" onClick={next} aria-label={index + 1 >= updates.length ? "Close" : "Next update"} className="absolute inset-y-20 right-0 w-[30%]" />
                </div>
                <div className="shrink-0 px-4 pb-[calc(24px+env(safe-area-inset-bottom))] pt-6">
                  <div className="flex items-center gap-3">
                    <Avatar id={u.person.id} name={u.person.name} src={u.person.photo} size={40} />
                    <div className="min-w-0">
                      <p className="t-headline">{u.person.name} <VerifiedBadge level={u.person.level} /></p>
                      <p className="t-subhead text-text-muted">{u.meta} · <span aria-label={whenSpoken(u.when)}>{u.when}</span></p>
                    </div>
                  </div>
                  <h2 className="mt-4 text-[22px] font-medium leading-[1.25] tracking-[-0.012em]">{u.headline}</h2>
                  <p className="t-subhead mt-2 text-text-muted">{u.reason}</p>
                  {!hideAction?.(u) && <Button variant="primary" className="mt-5 w-full" onClick={() => onAction(u)}>{u.actionLabel}</Button>}
                </div>
              </motion.div>
            </AnimatePresence>
            <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between px-4 pt-[calc(20px+env(safe-area-inset-top))]">
              <button onClick={onClose} aria-label="Close" className="pointer-events-auto flex h-11 w-11 items-center justify-center rounded-full bg-surface/60 text-text backdrop-blur-[20px] backdrop-saturate-[1.8]">
                <X size={20} strokeWidth={2} />
              </button>
              <span className="num rounded-full bg-surface/60 px-3 py-1.5 t-subhead text-text-muted backdrop-blur-[20px] backdrop-saturate-[1.8]" aria-live="polite">{index + 1} of {updates.length}</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
