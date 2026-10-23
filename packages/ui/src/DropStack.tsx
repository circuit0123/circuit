"use client";

import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { UserPlus, X } from "lucide-react";
import { VerifiedBadge, BridgeBadge } from "./Badge";
import { Button } from "./Button";
import { Skeleton } from "./Skeleton";
import { cx } from "./cx";
import { fade, initials, spring, toneFor } from "./theme";
import type { Person } from "./types";

export type DropCard = { id: number; person: Person; reason: string; bridge: boolean; answered: "intro" | "skip" | null };
type Props = {
  cards: DropCard[];
  onAnswer: (id: number, answer: "intro" | "skip") => void;
  /** Shown when all three are answered, e.g. "tomorrow at 8". */
  doneText: string;
  className?: string;
};

const THROW_FRACTION = 0.3;
const THROW_VELOCITY = 800;

/** The Daily Drop: finite, three cards. Swipe right = intro, left = skip; both buttons are always present. */
export function DropStack({ cards, onAnswer, doneText, className }: Props) {
  const [gone, setGone] = useState<Set<number>>(() => new Set(cards.filter((c) => c.answered).map((c) => c.id)));
  const live = cards.filter((c) => !gone.has(c.id) && !c.answered);
  const top = live[0];
  const topRef = useRef<CardHandle>(null);
  const answer = (id: number, a: "intro" | "skip") => { setGone((g) => new Set(g).add(id)); onAnswer(id, a); };

  if (!top) {
    return (
      <div className={cx("rounded-card border border-border bg-surface px-5 py-8", className)}>
        <p className="t-headline">{doneText}</p>
        <p className="t-body mt-1 text-text-muted">Take a look at Pulse below.</p>
      </div>
    );
  }
  return (
    <section aria-label="Daily Drop" className={className}>
      <p className="t-caption mb-2 text-text-muted" aria-live="polite">{cards.length - live.length + 1} of {cards.length} today</p>
      <div className="relative" style={{ aspectRatio: "4 / 5", maxHeight: "min(70dvh, 560px)" }}>
        {live.slice(1, 3).reverse().map((c, n, arr) => (
          <div key={c.id} aria-hidden className="absolute inset-0 rounded-card border border-border bg-surface-2" style={{ transform: `translateY(${(arr.length - n) * 8}px) scale(${1 - (arr.length - n) * 0.04})`, zIndex: -(arr.length - n) }} />
        ))}
        <TopCard key={top.id} ref={topRef} card={top} onThrow={(a) => answer(top.id, a)} />
      </div>
      <div className="mt-6 flex gap-3">
        <Button className="flex-1" icon={<X size={20} strokeWidth={1.75} />} onClick={() => topRef.current?.throw("skip")}>Skip</Button>
        <Button variant="primary" className="flex-1" icon={<UserPlus size={20} strokeWidth={1.75} />} onClick={() => topRef.current?.throw("intro")}>Intro me</Button>
      </div>
    </section>
  );
}

type CardHandle = { throw: (a: "intro" | "skip") => void };

const TopCard = forwardRef<CardHandle, { card: DropCard; onThrow: (a: "intro" | "skip") => void }>(function TopCard({ card, onThrow }, ref) {
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-300, 0, 300], [-8, 0, 8]);
  const introOpacity = useTransform(x, [20, 120], [0, 1]);
  const skipOpacity = useTransform(x, [-120, -20], [1, 0]);
  const el = useRef<HTMLDivElement>(null);
  const tone = toneFor(card.person.name);
  const done = useRef(false);

  const fling = (a: "intro" | "skip") => {
    if (done.current) return;
    done.current = true;
    const width = el.current?.offsetWidth ?? 360;
    if (reduce) { onThrow(a); return; }
    animate(x, (a === "intro" ? 1 : -1) * width * 1.4, { ...spring, onComplete: () => onThrow(a) });
  };
  useImperativeHandle(ref, () => ({ throw: fling }));

  const p = card.person;
  return (
    <motion.div
      ref={el}
      className="absolute inset-0 touch-pan-y overflow-hidden rounded-card border border-border bg-surface shadow-lift"
      style={{ x, rotate: reduce ? 0 : rotate }}
      drag={reduce ? false : "x"}
      dragSnapToOrigin
      dragMomentum={false}
      dragElastic={1}
      onDragEnd={(_, i) => {
        const w = el.current?.offsetWidth ?? 360;
        if (i.offset.x > w * THROW_FRACTION || i.velocity.x > THROW_VELOCITY) fling("intro");
        else if (i.offset.x < -w * THROW_FRACTION || i.velocity.x < -THROW_VELOCITY) fling("skip");
      }}
      initial={reduce ? { opacity: 0 } : false}
      animate={{ opacity: 1 }}
      transition={fade}
    >
      <div className="flex h-[58%] items-center justify-center" style={{ background: tone.bg, color: tone.fg }} aria-hidden>
        <span className="font-semibold" style={{ fontSize: 96, letterSpacing: "-0.02em" }}>{initials(p.name)}</span>
      </div>
      <motion.span style={{ opacity: introOpacity }} className="pointer-events-none absolute left-4 top-4 rounded-full bg-text px-3 py-1 t-caption font-semibold text-bg" aria-hidden>Intro me</motion.span>
      <motion.span style={{ opacity: skipOpacity }} className="pointer-events-none absolute right-4 top-4 rounded-full bg-text px-3 py-1 t-caption font-semibold text-bg" aria-hidden>Skip</motion.span>
      <div className="flex h-[42%] flex-col gap-1 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="t-title min-w-0 truncate">{p.name}</h2>
          <VerifiedBadge level={p.level} />
          {card.bridge && <BridgeBadge />}
        </div>
        <p className="t-caption text-text-muted">{[p.headline || p.role, p.place].filter(Boolean).join(", ")}</p>
        <p className="t-body mt-2 line-clamp-3">{card.reason}</p>
      </div>
    </motion.div>
  );
});

export function DropSkeleton() {
  return (
    <div aria-hidden>
      <Skeleton className="mb-2 h-4 w-24" />
      <Skeleton className="aspect-[4/5] max-h-[560px] w-full rounded-card" />
    </div>
  );
}
