"use client";

import { animate, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";
import { Avatar, PatternArt } from "./Avatar";
import { Button } from "./Button";
import { Skeleton } from "./Skeleton";
import { cx } from "./cx";

export type WireVerb = "shipped" | "hiring" | "needs" | "joined" | "closed a circuit";
export type WireVisualData =
  | { kind: "image"; src: string; alt: string }
  | { kind: "pattern"; id: string | number }
  | { kind: "circuit" };

/** One update on the Live wire. The node shows `visual` and `verb`; the Update view shows the rest. */
export type WireUpdate = {
  key: string;
  verb: WireVerb;
  visual: WireVisualData;
  person: { id: number; name: string; photo?: string | null; level: number };
  seen: boolean;
  /** Short relative time such as "4h". */
  when: string;
  /** One line of what happened. */
  headline: string;
  /** Why it matters to you, e.g. "You both build with Kotlin · 3 km away". */
  reason: string;
  actionLabel: string;
};

export const MAX_NODES = 12;
const PHRASE: Record<WireVerb, string> = {
  shipped: "shipped a build log",
  hiring: "is hiring",
  needs: "posted a need",
  joined: "joined",
  "closed a circuit": "closed a circuit",
};
export const firstName = (name: string) => name.replace(/^(dr|mr|ms|mrs|prof)\.?\s+/i, "").split(/\s+/)[0] ?? name;

/** "4h" to "4 hours ago", for screen readers. */
export function whenSpoken(when: string): string {
  const m = /^(\d+)([mhd])$/.exec(when);
  if (!m) return when === "now" ? "just now" : when;
  const unit = { m: "minute", h: "hour", d: "day" }[m[2] as "m" | "h" | "d"];
  return `${m[1]} ${unit}${m[1] === "1" ? "" : "s"} ago`;
}
export const spokenUpdate = (u: WireUpdate) => `${firstName(u.person.name)} ${PHRASE[u.verb]}, ${whenSpoken(u.when)}`;

/** The picture for an update: an image, a circuit pattern for a startup, or the ring for a closed circuit. */
export function WireVisual({ visual, className }: { visual: WireVisualData; className?: string }) {
  if (visual.kind === "image") return <img src={visual.src} alt={visual.alt} className={cx("h-full w-full object-cover", className)} />;
  if (visual.kind === "pattern") return <div className={cx("h-full w-full", className)}><PatternArt id={visual.id} banner /></div>;
  return (
    <svg viewBox="0 0 48 48" className={cx("h-full w-full bg-surface-2", className)} role="img" aria-label="A closed circuit of three people">
      <defs>
        <linearGradient id="wire-ring" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" style={{ stopColor: "var(--current)" }} />
          <stop offset="1" style={{ stopColor: "var(--bridge)" }} />
        </linearGradient>
      </defs>
      <circle cx="24" cy="24" r="13" fill="none" stroke="url(#wire-ring)" strokeWidth="3" />
      {[0, 120, 240].map((a) => (
        <circle key={a} cx={24 + 13 * Math.sin((a * Math.PI) / 180)} cy={24 - 13 * Math.cos((a * Math.PI) / 180)} r="4.2" fill="var(--surface)" stroke="url(#wire-ring)" strokeWidth="2.4" />
      ))}
    </svg>
  );
}

let played = false;
function alreadyPlayed(): boolean {
  if (played) return true;
  try { if (sessionStorage.getItem("circuit.wire") === "1") return true; } catch { /* storage can be blocked */ }
  return false;
}
function markPlayed() {
  played = true;
  try { sessionStorage.setItem("circuit.wire", "1"); } catch { /* storage can be blocked */ }
}

type Props = {
  updates: WireUpdate[];
  onOpen: (index: number) => void;
  /** Shown on the quiet-day line. */
  onEmptyAction?: () => void;
  className?: string;
};

/**
 * Circuit's own take on "what happened today": a thin trace with a node per update (DESIGN.md §4).
 * Unseen nodes are powered (current outline); a dot of current travels in once per session.
 */
export function LiveWire({ updates, onOpen, onEmptyAction, className }: Props) {
  const reduce = useReducedMotion();
  const nodes = updates.slice(0, MAX_NODES);
  const box = useRef<HTMLUListElement>(null);
  const first = useRef(true);

  useEffect(() => {
    const ul = box.current;
    if (!ul || !first.current || nodes.length === 0) return;
    first.current = false;
    const lit = [...ul.querySelectorAll<HTMLElement>("[data-lit]")];
    if (reduce || alreadyPlayed()) { markPlayed(); return; }
    markPlayed();
    lit.forEach((outline, i) => {
      const li = outline.closest("li") as HTMLElement;
      const dot = li.querySelector<HTMLElement>("[data-dot]");
      const delay = i * 0.08;
      outline.style.opacity = "0";
      animate(outline, { opacity: 1 }, { duration: 0.15, delay: delay + 0.6 });
      if (dot) {
        const d = li.offsetLeft + 26;
        animate(dot, { x: [-d, 0], opacity: [1, 1, 0] }, { duration: 0.6, ease: "easeOut", delay, times: [0, 0.85, 1] });
      }
    });
  }, [nodes.length, reduce]);

  if (nodes.length === 0) {
    return (
      <div className={cx("py-3", className)}>
        <div className="relative flex h-11 items-center"><span className="absolute inset-x-0 top-1/2 h-[1.5px] -translate-y-1/2 bg-separator" aria-hidden /></div>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
          <p className="t-body text-text-muted">Quiet on the wire today</p>
          {onEmptyAction && <Button variant="text" className="min-h-11 px-2" onClick={onEmptyAction}>Post a build log</Button>}
        </div>
      </div>
    );
  }
  return (
    <div className={cx("fade-edge-x -mx-4 overflow-x-auto px-4 no-scrollbar lg:mx-0 lg:px-0", className)}>
      <ul ref={box} aria-label="Live wire" className="relative flex w-max min-w-full gap-5 pr-8 lg:gap-7">
        <span className="pointer-events-none absolute inset-x-0 top-[22px] h-[1.5px] bg-separator" aria-hidden />
        {nodes.map((u, i) => (
          <li key={u.key} className="relative w-[52px] shrink-0 lg:w-14">
            <button className="flex w-full flex-col items-center gap-2" onClick={() => onOpen(i)}>
              <span className={cx("relative block h-11 w-11 transition-opacity duration-300", u.seen && "opacity-60")}>
                <span className="relative block h-full w-full overflow-hidden rounded-control bg-surface-2"><WireVisual visual={u.visual} /></span>
                {!u.seen && <span data-lit className="pointer-events-none absolute inset-0 rounded-control border-2 border-live" aria-hidden />}
                <span className="absolute -bottom-1 -right-1 rounded-full ring-2 ring-bg">
                  <Avatar id={u.person.id} name={u.person.name} src={u.person.photo} size={20} />
                </span>
              </span>
              <span className={cx("t-caption text-center leading-tight", u.seen ? "text-text-muted" : "text-text")} aria-hidden>{u.verb}</span>
              <span className="sr-only">{spokenUpdate(u)}{u.seen ? "" : ", new"}</span>
            </button>
            {!u.seen && <span data-dot className="pointer-events-none absolute left-[23px] top-[19px] h-1.5 w-1.5 rounded-full bg-live opacity-0" aria-hidden />}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function LiveWireSkeleton() {
  return (
    <div className="flex gap-5 pb-3" aria-hidden>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex w-[52px] shrink-0 flex-col items-center">
          <Skeleton className="h-11 w-11 rounded-control" />
          <Skeleton className="mt-2 h-3 w-10" />
        </div>
      ))}
    </div>
  );
}
