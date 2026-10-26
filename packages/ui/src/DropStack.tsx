"use client";

import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { Avatar, PatternArt } from "./Avatar";
import { VerifiedBadge, BridgeBadge } from "./Badge";
import { Button } from "./Button";
import { firstName } from "./LiveWire";
import { MatchStrength, type Strength } from "./MatchStrength";
import { cx } from "./cx";
import { Skeleton } from "./Skeleton";
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
export type DropStackHandle = {
  /** The intro was sent: the top card (if it is this one) flies off to the right. */
  introSent: (id: number) => void;
};
type Props = {
  cards: DropCard[];
  /** Skip, by button or swipe left. The card has already left. */
  onSkip: (id: number) => void;
  /** Intro me, by button or swipe right. The card springs back and waits: the caller confirms, then calls `introSent`. */
  onAskIntro: (id: number) => void;
  className?: string;
};

const THROW_FRACTION = 0.3;
const THROW_VELOCITY = 800;

/** The Daily Drop: finite, three cards. Swipe right = intro, left = skip; both buttons are always present, inside the card (Main.dc.html). */
export const DropStack = forwardRef<DropStackHandle, Props>(function DropStack({ cards, onSkip, onAskIntro, className }, ref) {
  const [gone, setGone] = useState<Set<number>>(() => new Set(cards.filter((c) => c.answered).map((c) => c.id)));
  const live = cards.filter((c) => !gone.has(c.id) && !c.answered);
  const top = live[0];
  const topRef = useRef<CardHandle>(null);
  const leave = (id: number, a: "intro" | "skip") => { setGone((g) => new Set(g).add(id)); if (a === "skip") onSkip(id); };
  useImperativeHandle(ref, () => ({ introSent: (id) => { if (top?.id === id) topRef.current?.throw("intro"); } }));

  return (
    <section aria-label="Daily Drop" data-no-swipe className={className}>
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="t-headline">Your drop</h2>
        <span className="t-subhead text-text-muted" aria-live="polite">{top ? cards.length - live.length + 1 : cards.length} of {cards.length}</span>
      </div>
      {top ? (
        <div className="relative pb-3">
          {live.slice(1, 3).reverse().map((c, n, arr) => (
            <div key={c.id} aria-hidden className="absolute inset-x-0 top-0 bottom-0 rounded-card bg-surface-2" style={{ transform: `translateY(${(arr.length - n) * 6}px) scale(${1 - (arr.length - n) * 0.04})`, zIndex: -(arr.length - n) }} />
          ))}
          <TopCard key={top.id} ref={topRef} card={top} onAsk={() => onAskIntro(top.id)} onThrow={(a) => leave(top.id, a)} />
        </div>
      ) : (
        <div className="py-12">
          <p className="text-[22px] font-medium leading-tight tracking-[-0.012em]">That's today's drop.</p>
          <p className="t-body mt-2 text-text-muted">New one tomorrow at 8.</p>
        </div>
      )}
    </section>
  );
});

/** The card's content without the gesture: used by the Daily Drop stack and by the last onboarding screen (static). */
export function DropCardFace({ card, compact, children }: { card: DropCard; /** The reveal at the end of sign-up (Ready.dc.html): the reason, the mutual and one line about the person; no picture, chips or detail. */ compact?: boolean; /** The actions, inside the card's padding. */ children?: React.ReactNode }) {
  const p = card.person;
  const via = card.via && (
    <p className={cx("flex items-center gap-2 text-text-muted", compact ? "t-footnote" : "t-subhead")}>
      <span className="flex -space-x-1.5">
        <Avatar id={card.via.id} name={card.via.name} src={card.via.photo} size={20} className="ring-2 ring-surface" />
        <Avatar id={p.id} name={p.name} src={p.photo} size={20} className="ring-2 ring-surface" />
      </span>
      via {firstName(card.via.name)}, {card.via.role}
    </p>
  );
  const lead = card.helpWith ? (
    <>{firstName(p.name)} can help you with <span className="font-semibold">{card.helpWith}</span></>
  ) : (
    card.reason
  );
  if (compact) {
    return (
      <div className="flex flex-col gap-3 p-surface">
        <h2 className="t-title3">{lead}</h2>
        {via}
        <div className="mt-2 flex items-center gap-3">
          <Avatar id={p.id} name={p.name} src={p.photo} size={44} />
          <div className="min-w-0">
            <p className="t-headline min-w-0">{p.name}</p>
            <p className="t-footnote text-text-muted">{[p.headline || p.role, p.place].filter(Boolean).join(" · ")}</p>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="p-surface">
      <h3 className="text-[22px] font-medium leading-[1.25] tracking-[-0.012em]">{lead}</h3>
      {via && <div className="mt-3">{via}</div>}
      <div className="mt-4 h-[120px] overflow-hidden rounded-group bg-surface-2 lg:h-[140px]">
        {p.photo || card.image ? (
          <img src={p.photo ?? card.image!.src} alt={p.photo ? "" : card.image!.alt} className="h-full w-full object-cover" />
        ) : (
          <PatternArt id={p.id} initial={p.name[0]} banner />
        )}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-x-1.5 gap-y-1">
        <p className="t-headline min-w-0">{p.name}</p>
        <VerifiedBadge level={p.level} />
        {card.bridge && <BridgeBadge className="ml-1" />}
      </div>
      <p className="t-subhead mt-1 text-text-muted">{[p.headline || p.role, p.place].filter(Boolean).join(" · ")}</p>
      {card.detail && <p className="t-subhead mt-3 max-w-[540px]">{card.detail}</p>}
      {card.offers.length > 0 && (
        <ul aria-label="What they offer you need" className="mt-4 flex flex-wrap gap-2">
          {card.offers.slice(0, 3).map((o) => <li key={o} className="rounded-full bg-surface-2 px-3 py-1.5 t-subhead">{o}</li>)}
        </ul>
      )}
      {card.strength && <p className="mt-3"><MatchStrength strength={card.strength} plain /></p>}
      {children}
    </div>
  );
}

type CardHandle = { throw: (a: "intro" | "skip") => void };

const TopCard = forwardRef<CardHandle, { card: DropCard; onAsk: () => void; onThrow: (a: "intro" | "skip") => void }>(function TopCard({ card, onAsk, onThrow }, ref) {
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

  return (
    <motion.div
      ref={el}
      className="relative touch-pan-y overflow-hidden rounded-card bg-surface shadow-lift"
      style={{ x, rotate: reduce ? 0 : rotate }}
      drag={reduce ? false : "x"}
      dragSnapToOrigin
      dragMomentum={false}
      dragElastic={1}
      onDragEnd={(_, i) => {
        const w = el.current?.offsetWidth ?? 360;
        if (i.offset.x > w * THROW_FRACTION || i.velocity.x > THROW_VELOCITY) onAsk();
        else if (i.offset.x < -w * THROW_FRACTION || i.velocity.x < -THROW_VELOCITY) fling("skip");
      }}
      initial={reduce ? { opacity: 0 } : false}
      animate={{ opacity: 1 }}
      transition={fade}
    >
      <DropCardFace card={card}>
        <Button variant="primary" className="mt-5 w-full" onClick={onAsk}>Intro me</Button>
        <button type="button" onClick={() => fling("skip")} className="mt-0 flex min-h-11 w-full items-center justify-center t-body text-text-muted active:opacity-80">Skip</button>
      </DropCardFace>
      <motion.span style={{ opacity: introOpacity }} className="pointer-events-none absolute left-4 top-4 rounded-full bg-text px-3 py-1 t-footnote font-semibold text-bg" aria-hidden>Intro me</motion.span>
      <motion.span style={{ opacity: skipOpacity }} className="pointer-events-none absolute right-4 top-4 rounded-full bg-text px-3 py-1 t-footnote font-semibold text-bg" aria-hidden>Skip</motion.span>
    </motion.div>
  );
});

export function DropSkeleton() {
  return (
    <div aria-hidden>
      <div className="mb-3 flex items-baseline justify-between"><Skeleton className="h-5 w-24" /><Skeleton className="h-4 w-10" /></div>
      <Skeleton className="h-[460px] w-full rounded-card" />
    </div>
  );
}
