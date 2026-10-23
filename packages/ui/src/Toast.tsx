"use client";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { cx } from "./cx";

type ToastItem = { id: number; text: string; tone: "info" | "error" };
const Ctx = createContext<(text: string, tone?: "info" | "error") => void>(() => {});
export const useToast = () => useContext(Ctx);

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((text: string, tone: "info" | "error" = "info") => {
    const id = nextId++;
    setItems((xs) => [...xs, { id, text, tone }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 5000);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex flex-col items-center gap-2 px-4 md:bottom-6">
        {items.map((t) => (
          <p key={t.id} className={cx("fade-in pointer-events-auto rounded-control px-4 py-3 text-base font-semibold text-white shadow-sheet", t.tone === "error" ? "bg-alert" : "bg-ink")}>
            {t.text}
          </p>
        ))}
      </div>
    </Ctx.Provider>
  );
}
