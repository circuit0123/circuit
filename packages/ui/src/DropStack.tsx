"use client";

import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { UserPlus, X } from "lucide-react";
import { Avatar, PatternArt } from "./Avatar";
import { VerifiedBadge, BridgeBadge } from "./Badge";
import { Button } from "./Button";
import { Chip } from "./Chip";
import { firstName } from "./LiveWire";
import { MatchStrength, type Strength } from "./MatchStrength";
import { Skeleton } from "./Skeleton";
import { cx } from "./cx";
import { fade, spring } from "./theme";
import type { Person } from "./types";

export type DropCard = {
  id: number;
  person: Person;
  /** The first sentence of the match reason. It is the headline when `helpWith` is missing. */
  reason: string;
  /** The rest of the reason, shown under the name. */
  detail?: string;
  /** The capability they offer that you need, e.g. "mentoring". */
  helpWith?: string | null;
  /** Best mutual connection, e.g. Meera, mentor. */
  via?: { id: number; name: string; photo?: string | null; role: string } | null;
  /** Their best build log image, used when they have no photo. */
  image?: { src: string; alt: string } | null;
  /** Up to 3 things they offer that you need. */
  offers: string[];
  strength: Strength | null;
  bridge: boolean;
  answered: "intro" | "skip" | null;
};
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
      <div className="relative pb-3">
        {live.slice(1, 3).reverse().map((c, n, arr) => (
          <div key={c.id} aria-hidden className="absolute inset-x-0 top-0 bottom-0 rounded-card border border-border bg-surface-2" style={{ transform: `translateY(${(arr.length - n) * 6}px) scale(${1 - (arr.length - n) * 0.04})`, zIndex: -(arr.length - n) }} />
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
      className="relative touch-pan-y overflow-hidden rounded-card border border-border bg-surface shadow-lift"
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
      <div className="flex flex-col gap-2 px-4 pb-3 pt-4">
        <h2 className="t-title line-clamp-3">
          {card.helpWith ? (
            <>{firstName(p.name)} can help you with <span className="text-accent">{card.helpWith}</span></>
          ) : (
            card.reason
          )}
        </h2>
        {card.via && (
          <p className="t-caption flex items-center gap-2 text-text-muted">
            <span className="flex -space-x-1.5">
              <Avatar id={card.via.id} name={card.via.name} src={card.via.photo} size={20} className="ring-2 ring-surface" />
              <Avatar id={p.id} name={p.name} src={p.photo} size={20} className="ring-2 ring-surface" />
            </span>
            via {firstName(card.via.name)}, {card.via.role}
          </p>
        )}
      </div>
      <div className="relative w-full overflow-hidden bg-surface-2" style={{ aspectRatio: "4 / 3" }}>
        {p.photo || card.image ? (
          <img src={p.photo ?? card.image!.src} alt={p.photo ? "" : card.image!.alt} className="h-full w-full object-cover" />
        ) : (
          <PatternArt id={p.id} initial={p.name[0]} banner />
        )}
        <motion.span style={{ opacity: introOpacity }} className="pointer-events-none absolute left-4 top-4 rounded-full bg-text px-3 py-1 t-caption font-semibold text-bg" aria-hidden>Intro me</motion.span>
        <motion.span style={{ opacity: skipOpacity }} className="pointer-events-none absolute right-4 top-4 rounded-full bg-text px-3 py-1 t-caption font-semibold text-bg" aria-hidden>Skip</motion.span>
      </div>
      <div className="flex flex-col gap-2 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="t-headline min-w-0 truncate">{p.name}</h3>
          <VerifiedBadge level={p.level} />
        </div>
        <p className="t-caption text-text-muted">{[p.headline || p.role, p.place].filter(Boolean).join(", ")}</p>
        {card.detail && <p className="t-body line-clamp-2">{card.detail}</p>}
        {(card.offers.length > 0 || card.strength || card.bridge) && (
          <div className="flex flex-wrap items-center gap-2">
            {card.offers.slice(0, 3).map((o) => <Chip key={o} label={o} />)}
            <MatchStrength strength={card.strength} />
            {card.bridge && <BridgeBadge />}
          </div>
        )}
      </div>
    </motion.div>
  );
});

export function DropSkeleton() {
  return (
    <div aria-hidden>
      <Skeleton className="mb-2 h-4 w-24" />
      <Skeleton className="h-[480px] w-full rounded-card" />
    </div>
  );
}
