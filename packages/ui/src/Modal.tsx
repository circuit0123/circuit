"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useId } from "react";
import { cx } from "./cx";
import { useOverlay } from "./overlay";
import { fade, sheetSpring } from "./theme";

type Props = { open: boolean; onClose: () => void; title: string; children: React.ReactNode; className?: string };

export function Modal({ open, onClose, title, children, className }: Props) {
  const reduce = useReducedMotion();
  const ref = useOverlay(open, onClose);
  const id = useId();
  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div className="absolute inset-0 bg-black/60" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={fade} />
          <motion.div
            ref={ref}
            role="dialog"
            aria-modal="true"
            aria-labelledby={id}
            tabIndex={-1}
            className={cx("relative w-full max-w-sm rounded-sheet bg-surface p-6 shadow-lift outline-none", className)}
            initial={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.96 }}
            transition={reduce ? fade : sheetSpring}
          >
            <h2 id={id} className="t-title mb-3">{title}</h2>
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
