"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useId } from "react";
import { cx } from "./cx";
import { useOverlay } from "./overlay";
import { fade, sheetSpring } from "./theme";

type Props = { open: boolean; onClose: () => void; title: string; children: React.ReactNode; className?: string };

/** Springs up from the bottom; drag down (or flick) to dismiss. On desktop it sits centred. */
export function BottomSheet({ open, onClose, title, children, className }: Props) {
  const reduce = useReducedMotion();
  const ref = useOverlay(open, onClose);
  const id = useId();
  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center lg:items-center">
          <motion.div className="absolute inset-0 bg-black/60" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={fade} />
          <motion.div
            ref={ref}
            role="dialog"
            aria-modal="true"
            aria-labelledby={id}
            tabIndex={-1}
            className={cx("relative max-h-[90dvh] w-full max-w-lg overflow-y-auto rounded-t-sheet bg-surface p-4 pb-8 shadow-lift outline-none lg:rounded-sheet", className)}
            initial={reduce ? { opacity: 0 } : { y: "100%" }}
            animate={reduce ? { opacity: 1 } : { y: 0 }}
            exit={reduce ? { opacity: 0 } : { y: "100%" }}
            transition={reduce ? fade : sheetSpring}
            drag={reduce ? false : "y"}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.6 }}
            onDragEnd={(_, i) => { if (i.offset.y > 120 || i.velocity.y > 600) onClose(); }}
          >
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-separator" aria-hidden />
            <h2 id={id} className="t-headline mb-3">{title}</h2>
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
