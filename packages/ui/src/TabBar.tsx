"use client";

import { motion, useTransform, type MotionValue } from "motion/react";
import { cx } from "./cx";

export type TabItem = { id: string; label: string; href: string; icon: React.ReactNode; dot?: boolean };

type Props = {
  tabs: TabItem[];
  /** The shown tab, or null on a pushed screen. */
  active: string | null;
  /** Fractional index of the shown tab: the indicator slides with a swipe. */
  progress: MotionValue<number>;
  onSelect: (id: string) => void;
};

/** Mobile bottom bar (DESIGN.md §3): icons with labels, translucent material, a selection indicator that follows swipes. */
export function TabBar({ tabs, active, progress, onSelect }: Props) {
  const x = useTransform(progress, (v) => `${v * 100}%`);
  return (
    <nav aria-label="Main" className="material fixed inset-x-0 bottom-0 z-30 border-t border-separator pb-[env(safe-area-inset-bottom)] lg:hidden">
      <div className="relative grid" style={{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` }}>
        {active && (
          <motion.span aria-hidden className="pointer-events-none absolute top-0 flex justify-center" style={{ width: `${100 / tabs.length}%`, x }}>
            <span className="h-0.5 w-8 rounded-full bg-text" />
          </motion.span>
        )}
        {tabs.map((t) => (
          <a
            key={t.id}
            href={t.href}
            aria-current={t.id === active ? "page" : undefined}
            onClick={(e) => {
              if (e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
              e.preventDefault();
              onSelect(t.id);
            }}
            className={cx("relative flex min-h-[52px] flex-col items-center justify-center gap-0.5 t-caption active:opacity-80", t.id === active ? "font-semibold text-text" : "text-text-muted")}
          >
            <span className="relative">
              {t.icon}
              {t.dot && <span aria-hidden className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-live ring-2 ring-bg" />}
            </span>
            {t.label}
          </a>
        ))}
      </div>
    </nav>
  );
}
