"use client";

import { motion, useReducedMotion } from "motion/react";
import { Avatar } from "./Avatar";
import { Skeleton } from "./Skeleton";
import { fade } from "./theme";

export type Circle = { key: string; name: string; seen: boolean; photo?: string | null };

/** Horizontal circles, 64px. Unseen = signature ring. A labelled list for screen readers. */
export function TodayStrip({ circles, onOpen }: { circles: Circle[]; onOpen: (key: string) => void }) {
  const reduce = useReducedMotion();
  return (
    <ul aria-label="Today" className="no-scrollbar -mx-4 flex gap-4 overflow-x-auto px-4 py-3 lg:mx-0 lg:px-0">
      {circles.map((c, i) => (
        <motion.li
          key={c.key}
          className="relative w-16 shrink-0"
          initial={reduce || i > 7 ? false : { opacity: 0, y: reduce ? 0 : 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={reduce ? fade : { delay: i * 0.04, type: "spring", stiffness: 380, damping: 32 }}
        >
          <button className="flex w-full flex-col items-center gap-1" onClick={() => onOpen(c.key)}>
            <Avatar name={c.name} src={c.photo} size={64} ring={c.seen ? "seen" : "unseen"} />
            <span className="t-micro block w-full truncate text-center text-text-muted" aria-hidden>{c.name.split(" ")[0]}</span>
            <span className="sr-only">{c.name}, {c.seen ? "seen" : "new"}</span>
          </button>
        </motion.li>
      ))}
    </ul>
  );
}

export function TodayStripSkeleton() {
  return (
    <div className="flex gap-4 py-3" aria-hidden>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex w-16 shrink-0 flex-col items-center gap-1">
          <Skeleton round className="h-16 w-16" />
          <Skeleton className="h-3 w-10" />
        </div>
      ))}
    </div>
  );
}
