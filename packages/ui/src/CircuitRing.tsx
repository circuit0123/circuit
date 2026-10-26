"use client";

import { motion, useReducedMotion } from "motion/react";
import { useEffect, useId } from "react";
import { Avatar } from "./Avatar";
import { cx } from "./cx";
import { fade } from "./theme";

export type RingMember = {
  id: number;
  /** What the ring shows beside the avatar: "You" or a first name. */
  label: string;
  name: string;
  /** This person said yes: their segment of the ring (from them to the person they help) is lit. */
  lit: boolean;
};

type Props = {
  /** The three people in ring order, starting with the viewer at the top; each one helps the next. */
  members: [RingMember, RingMember, RingMember];
  /** Small line in the middle: "2 of 3 in". */
  centre: string;
  /** Read by screen readers instead of the picture: "Priya and Arjun accepted, waiting for you". */
  label: string;
  /** Play the closing moment now (DESIGN.md §7). It runs once; `onDone` fires when it ends. */
  closing?: boolean;
  onDone?: () => void;
  className?: string;
};

// Geometry from Circuits.dc.html: a 240×210 box, centre (120, 110), radius 88, nodes at the top and the two lower corners.
const NODES = [{ x: 120, y: 22 }, { x: 196.2, y: 154 }, { x: 43.8, y: 154 }] as const;
const ARCS = ["M120 22 A88 88 0 0 1 196.2 154", "M196.2 154 A88 88 0 0 1 43.8 154", "M43.8 154 A88 88 0 0 1 120 22"] as const;
const SEGMENT = 0.3; // s per segment
const SWEEP = 0.6;
const TOTAL_MS = 1600;

/**
 * The circuit ring (DESIGN.md §4 Circuits, §6 CircuitRing): three people on a ring, each segment lit in the signature gradient once
 * its person says yes. The closing moment (§7): the three segments draw in sequence (3 × 300ms), the gradient sweeps once around
 * (600ms), the avatars pulse once; 1.6s in all. With reduced motion it is a static closed ring with a checkmark that fades in.
 */
export function CircuitRing({ members, centre, label, closing = false, onDone, className }: Props) {
  const reduce = useReducedMotion();
  const gid = `sig${useId().replace(/:/g, "")}`;

  useEffect(() => {
    if (!closing || !onDone) return;
    const t = setTimeout(onDone, reduce ? 150 : TOTAL_MS);
    return () => clearTimeout(t);
  }, [closing, onDone, reduce]);

  const allIn = members.every((m) => m.lit);
  const stroke = `url(#${gid})`;

  return (
    <div className={cx("relative mx-auto h-[210px] w-[240px]", className)} data-closing={closing ? "" : undefined} data-closed={allIn ? "" : undefined}>
      <svg width="240" height="210" viewBox="0 0 240 210" fill="none" role="img" aria-label={label}>
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" style={{ stopColor: "var(--current)" }} />
            <stop offset="1" style={{ stopColor: "var(--bridge)" }} />
          </linearGradient>
        </defs>
        {ARCS.map((d, i) => (
          <path key={`dim${i}`} d={d} stroke="var(--surface-3)" strokeWidth={4} strokeLinecap="round" />
        ))}
        {ARCS.map((d, i) => {
          if (!members[i].lit) return null;
          if (closing && !reduce) {
            return (
              <motion.path
                key={`lit${i}`}
                data-segment={i}
                d={d}
                stroke={stroke}
                strokeWidth={4}
                strokeLinecap="round"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: SEGMENT, delay: i * SEGMENT, ease: "easeOut" }}
              />
            );
          }
          return (
            <motion.path
              key={`lit${i}`}
              data-segment={i}
              d={d}
              stroke={stroke}
              strokeWidth={4}
              strokeLinecap="round"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={fade}
            />
          );
        })}
        {closing && !reduce && (
          // The sweep: a short bright stretch of the gradient travels once around the closed ring (transform and opacity only).
          <motion.g
            style={{ originX: "120px", originY: "110px" }}
            initial={{ rotate: 0, opacity: 0 }}
            animate={{ rotate: 360, opacity: [0, 1, 1, 0] }}
            transition={{ duration: SWEEP, delay: 3 * SEGMENT, ease: "easeInOut" }}
          >
            <circle cx="120" cy="110" r="88" stroke={stroke} strokeWidth={7} strokeLinecap="round" strokeDasharray="60 493" transform="rotate(-90 120 110)" />
          </motion.g>
        )}
      </svg>

      {members.map((m, i) => {
        const n = NODES[i];
        return (
          <motion.span
            key={m.id}
            className="absolute flex rounded-full ring-4 ring-surface"
            style={{ left: n.x - 20, top: n.y - 20 }}
            initial={false}
            animate={closing && !reduce ? { scale: [1, 1.12, 1] } : { scale: 1 }}
            transition={{ duration: 0.3, delay: closing && !reduce ? 3 * SEGMENT + SWEEP - 0.2 : 0 }}
          >
            <Avatar id={m.id} name={m.name} size={40} />
          </motion.span>
        );
      })}

      {/* Names: beside the top node, under the two lower ones. Hidden from screen readers: the ring's label says it all. */}
      <span aria-hidden className="t-subhead absolute left-[148px] top-[10px]">{members[0].label}</span>
      <span aria-hidden className="t-subhead absolute top-[178px] w-24 text-center" style={{ left: NODES[1].x - 48 }}>{members[1].label}</span>
      <span aria-hidden className="t-subhead absolute top-[178px] w-24 text-center" style={{ left: NODES[2].x - 48 }}>{members[2].label}</span>

      <span aria-hidden className="t-subhead absolute inset-x-0 top-[92px] flex items-center justify-center gap-1.5 text-text-muted">
        {allIn && reduce && (
          <motion.svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={fade} data-check>
            <path d="M5 12.5l4.5 4.5L19 7.5" />
          </motion.svg>
        )}
        {centre}
      </span>
    </div>
  );
}

/** A completed circuit in the history: a small closed ring (Circuits.dc.html "Completed"). */
export function MiniRing({ label }: { label: string }) {
  return (
    <svg width="44" height="44" viewBox="0 0 44 44" fill="none" role="img" aria-label={label}>
      <circle cx="22" cy="22" r="17" stroke="var(--surface-3)" strokeWidth={3} />
    </svg>
  );
}
