"use client";

import { Lightbulb, MessageCircle, UserPlus } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { cx } from "./cx";

export type ReactionKind = "helpful" | "intro_me" | "lets_talk";
const KINDS = [
  { id: "helpful", label: "Helpful", Icon: Lightbulb },
  { id: "intro_me", label: "Intro me", Icon: UserPlus },
  { id: "lets_talk", label: "Let's talk", Icon: MessageCircle },
] as const;

/** No counts anywhere (DESIGN.md §8). Tapping scales the icon 1 → 1.25 → 1 in 220ms. */
export function ReactionBar({ active, onToggle, className }: { active: ReactionKind[]; onToggle: (k: ReactionKind, on: boolean) => void; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <div className={cx("flex gap-2", className)} role="group" aria-label="React">
      {KINDS.map(({ id, label, Icon }) => {
        const on = active.includes(id);
        return (
          <button
            key={id}
            aria-pressed={on}
            onClick={() => { navigator.vibrate?.(8); onToggle(id, !on); }}
            className={cx("flex min-h-11 flex-1 items-center justify-center gap-2 rounded-full px-3 t-caption", on ? "bg-text font-semibold text-bg" : "bg-surface-2 text-text")}
          >
            <motion.span key={String(on)} animate={reduce ? undefined : { scale: [1, 1.25, 1] }} transition={{ duration: 0.22 }} className="flex">
              <Icon size={20} strokeWidth={1.75} fill={on && id === "helpful" ? "currentColor" : "none"} aria-hidden />
            </motion.span>
            {label}
          </button>
        );
      })}
    </div>
  );
}
