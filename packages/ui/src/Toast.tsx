"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { fade, spring } from "./theme";

type ToastInput = { text: string; undo?: () => void; ms?: number; tone?: "error" };
type Item = ToastInput & { id: number };
const Ctx = createContext<(t: ToastInput) => void>(() => {});
export const useToast = () => useContext(Ctx);

/** One toast at a time, with an optional Undo. The action keeps its name: "Skipped" says what Skip did. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [item, setItem] = useState<Item | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const reduce = useReducedMotion();
  const show = useCallback((t: ToastInput) => {
    clearTimeout(timer.current);
    const id = Date.now();
    setItem({ ...t, id });
    timer.current = setTimeout(() => setItem((c) => (c?.id === id ? null : c)), t.ms ?? 5000);
  }, []);
  const value = useMemo(() => show, [show]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-[calc(72px+env(safe-area-inset-bottom))] z-[60] flex justify-center px-4 lg:bottom-6" role="status" aria-live="polite">
        <AnimatePresence>
          {item && (
            <motion.div
              key={item.id}
              className={`pointer-events-auto flex items-center gap-4 rounded-full py-2 pl-5 pr-2 text-bg shadow-lift ${item.tone === "error" ? "bg-danger" : "bg-text"}`}
              initial={reduce ? { opacity: 0 } : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={reduce ? fade : spring}
            >
              <span className="t-body">{item.text}</span>
              {item.undo && (
                <button className="min-h-11 rounded-full px-4 t-body font-semibold underline" onClick={() => { item.undo?.(); setItem(null); }}>
                  Undo
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </Ctx.Provider>
  );
}
