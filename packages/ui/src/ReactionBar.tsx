"use client";

import { motion, useReducedMotion } from "motion/react";
import { cx } from "./cx";

export type ReactionKind = "helpful" | "intro_me" | "lets_talk";
const KINDS = [
  { id: "helpful", label: "Helpful" },
  { id: "intro_me", label: "Intro me" },
  { id: "lets_talk", label: "Let's talk" },
] as const;

/** Three text buttons, no counts (DESIGN.md §8). A chosen one is semibold and `text`, not just a colour. Tapping scales the label 1 → 1.25 → 1 in 220ms. */
export function ReactionBar({ active, onToggle, hide, className }: { active: ReactionKind[]; onToggle: (k: ReactionKind, on: boolean) => void; /** Reactions to leave out, e.g. "intro_me" for under-18 members. */ hide?: ReactionKind[]; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <div className={cx("flex gap-6", className)} role="group" aria-label="React">
      {KINDS.filter((k) => !hide?.includes(k.id)).map(({ id, label }) => {
        const on = active.includes(id);
        return (
          <button
            key={id}
            aria-pressed={on}
            onClick={() => { navigator.vibrate?.(8); onToggle(id, !on); }}
            className={cx("min-h-11 t-subhead active:opacity-80", on ? "font-semibold text-text" : "text-text-muted")}
          >
            <motion.span key={String(on)} animate={reduce ? undefined : { scale: [1, 1.25, 1] }} transition={{ duration: 0.22 }} className="inline-block">
              {label}
            </motion.span>
          </button>
        );
      })}
    </div>
  );
}
